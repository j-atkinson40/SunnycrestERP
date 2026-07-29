"""W-1b — tenant wipe tool: derivation, guards, and a full throwaway-tenant
wipe/verify lifecycle. Runs against the test DB. Also verifies the three
guards (preserve-list assertion, blocker check, no hard-edge cycle) against
the REAL preserve-list — so a schema change that introduces a blocker or a
missing preserve name fails here rather than mid-wipe.

Cleans up its own throwaway tenant (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models.company import Company
from app.models.customer import Customer
from app.models.financial_account import FinancialAccount
from app.models.role import Role
from app.models.user import User

from scripts.wipe_tenant import (
    PRESERVE, COA_TABLES, DOCUMENT_TABLES, TRANSFER_TABLES,
    plan_wipe, execute_deletes, load_schema, build_predicate, derive_delete_set,
    transfer_predicates,
)

DEFAULT_PRESERVE = PRESERVE | COA_TABLES  # default flags: CoA kept, documents deleted


@pytest.fixture
def throwaway():
    """A disposable tenant with a delete-set row (customer) and a preserve-set
    row (financial_account), plus preserved identity rows."""
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"WIPE-SELFTEST {suffix}",
                 slug=f"wipe-selftest-{suffix}", is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role); s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"wipe-{suffix}@test.local", hashed_password="x",
                first_name="W", last_name="T", is_active=True)
    cust = Customer(id=str(uuid.uuid4()), company_id=co.id, name="Doomed Customer")
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Kept Operating")
    s.add_all([user, cust, acct]); s.commit()
    ids = {"co": co.id, "slug": co.slug}
    s.close()
    yield ids
    # teardown — remove the throwaway entirely (wipe leaves preserved rows behind)
    with engine.begin() as c:
        for stmt in (
            "DELETE FROM customers WHERE company_id=:c",
            "DELETE FROM financial_accounts WHERE tenant_id=:c",
            "DELETE FROM users WHERE company_id=:c",
            "DELETE FROM roles WHERE company_id=:c",
            "DELETE FROM companies WHERE id=:c",
        ):
            c.execute(text(stmt), {"c": ids["co"]})


def test_guards_hold_against_the_real_preserve_list():
    """GUARD verification (also the operator's blocker re-check): the real
    preserve-list has no missing names, no preserve->delete NOT NULL blocker,
    and every hard-edge cycle is resolvable by nulling a nullable in-cycle FK
    (no UNBREAKABLE cycle left)."""
    with engine.connect() as conn:
        (delete_set, order, break_edges, unbreakable, blockers,
         preds, child_only, unconfident) = plan_wipe(conn, DEFAULT_PRESERVE)
    assert unbreakable == set(), f"hard cycle with no nullable edge: {sorted(unbreakable)}"
    assert blockers == [], f"preserve->delete NOT NULL blockers: {blockers}"
    # child-only descendants (no tenant column) are pulled in (GUARD 2) + named
    assert "invoice_lines" in child_only
    # journal_entry_lines carries tenant_id, so it's scoped directly (delete-set), not child-only
    assert "journal_entry_lines" in delete_set
    assert "journal_entry_lines" not in child_only
    # the two known nominal cycles are resolved by an in-cycle null-break
    broken_tables = {ch for ch, col, pa in break_edges}
    assert "fh_cases" in broken_tables or "fh_case_contacts" in broken_tables
    assert "toolbox_talks" in broken_tables or "toolbox_talk_suggestions" in broken_tables
    # EVERY delete-set table has a confident tenant-scoping predicate. The
    # transfer tables are removed from unconfident (mode-controlled, not a gap);
    # employee_profiles is now scoped through preserved `users`. If this list is
    # non-empty, a NEW table with an unscopable shape has appeared — investigate,
    # don't relax the assertion.
    assert unconfident == [], f"unscopable delete-set tables: {unconfident}"


def test_preserve_list_assertion_hard_fails_on_bad_name():
    with engine.connect() as conn:
        with pytest.raises(ValueError, match="not in schema"):
            plan_wipe(conn, DEFAULT_PRESERVE | {"table_that_does_not_exist_xyz"})


def test_derivation_delete_vs_preserve():
    with engine.connect() as conn:
        delete_set, order, *_ , preds, child_only, _ = plan_wipe(conn, DEFAULT_PRESERVE)
    # a scoped operational table is in the delete-set
    assert "customers" in delete_set
    assert "invoices" in delete_set
    # preserved config is NOT in the delete-set
    assert "financial_accounts" not in delete_set
    assert "tax_rates" not in delete_set
    assert "company_modules" not in delete_set
    # CoA preserved by default (flag off)
    assert "tenant_gl_mappings" not in delete_set
    # child-only predicate is a scoping subquery, not a bare truth
    assert preds["invoice_lines"] and "IN (SELECT" in preds["invoice_lines"]


def test_coa_flag_moves_gl_mappings_into_delete_set():
    with engine.connect() as conn:
        ds_default, *_ = plan_wipe(conn, DEFAULT_PRESERVE)
        ds_coa, *_ = plan_wipe(conn, PRESERVE)  # PRESERVE without COA = --include-coa
    assert "tenant_gl_mappings" not in ds_default
    assert "tenant_gl_mappings" in ds_coa


def test_documents_delete_by_default_preserve_with_flag():
    with engine.connect() as conn:
        ds_default, *_ = plan_wipe(conn, DEFAULT_PRESERVE)
        ds_preserve_docs, *_ = plan_wipe(conn, DEFAULT_PRESERVE | DOCUMENT_TABLES)
    assert "documents" in ds_default            # deleted by default
    assert "documents" not in ds_preserve_docs  # --preserve-documents keeps it


def test_full_wipe_lifecycle(throwaway):
    co_id = throwaway["co"]
    with engine.connect() as conn:
        (delete_set, order, break_edges, unbreakable, blockers,
         preds, child_only, unconfident) = plan_wipe(conn, DEFAULT_PRESERVE)
        # dry-run counts for the throwaway: exactly the one customer
        n_cust = conn.execute(
            text(f'SELECT count(*) FROM customers WHERE {preds["customers"]}'),
            {"tid": co_id}).scalar()
    assert n_cust == 1

    # execute in a single transaction (scoped to the throwaway tenant)
    with engine.begin() as conn:
        nulled, deleted = execute_deletes(conn, co_id, order, preds, break_edges)
    assert deleted.get("customers") == 1

    # verify: delete-set cleared, preserve-set intact, identity intact
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM customers WHERE company_id=:c"),
                            {"c": co_id}).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM financial_accounts WHERE tenant_id=:c"),
                            {"c": co_id}).scalar() == 1  # PRESERVED
        assert conn.execute(text("SELECT count(*) FROM companies WHERE id=:c"),
                            {"c": co_id}).scalar() == 1  # PRESERVED
        assert conn.execute(text("SELECT count(*) FROM users WHERE company_id=:c"),
                            {"c": co_id}).scalar() == 1  # PRESERVED
        assert conn.execute(text("SELECT count(*) FROM roles WHERE company_id=:c"),
                            {"c": co_id}).scalar() == 1  # PRESERVED


def test_transfer_tables_are_mode_controlled_not_auto_scoped():
    """Two-party transfer records are never auto-scoped: no default, refuse to
    guess. None/'skip' → not deleted; the delete modes scope to one named side
    and pull children through the parent transfer."""
    # None and 'skip' both mean "don't delete these"
    for mode in (None, "skip"):
        tp = transfer_predicates(mode)
        assert all(tp[t] is None for t in TRANSFER_TABLES), mode
    # delete-as-home scopes the transfer to home_tenant_id; children follow it
    home = transfer_predicates("delete-as-home")
    assert home["licensee_transfers"] == '"home_tenant_id" = :tid'
    assert "home_tenant_id" in home["transfer_notifications"]
    assert "licensee_transfers" in home["transfer_notifications"]
    assert "home_tenant_id" in home["transfer_price_requests"]
    # delete-as-recipient scopes to the area (receiving) side
    rec = transfer_predicates("delete-as-recipient")
    assert rec["licensee_transfers"] == '"area_tenant_id" = :tid'
    assert "area_tenant_id" in rec["transfer_notifications"]
    # plan_wipe applies the mode predicate + drops them from `unconfident`
    with engine.connect() as conn:
        (_ds, _o, _be, _ub, _bl, preds, _co, unconfident) = \
            plan_wipe(conn, DEFAULT_PRESERVE, transfer_mode="delete-as-home")
    assert preds["licensee_transfers"] == '"home_tenant_id" = :tid'
    assert not any(t in unconfident for t in TRANSFER_TABLES)
