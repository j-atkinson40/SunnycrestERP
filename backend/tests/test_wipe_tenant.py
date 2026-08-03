"""W-1b/W-1c — tenant wipe tool: derivation, guards, chunked + resumable
deletion, disk floor, telemetry-first closure, and a full throwaway-tenant
wipe/verify lifecycle. Runs against the test DB. Verifies the guards against the
REAL preserve-list, so a schema change that introduces a blocker, a missing
preserve name, an unscopable table, or a books-critical table in the telemetry
closure fails HERE rather than mid-wipe.

W-1c withdrew atomicity: deletion is chunked into committed batches, idempotent,
and resumable (a single-transaction wipe of ~112k rows exhausted the prod volume
with WAL and crashed the DB for ~25h — see wipe_tenant.py docstring).

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

from scripts import wipe_tenant
from scripts.wipe_tenant import (
    PRESERVE, COA_TABLES, DOCUMENT_TABLES, TRANSFER_TABLES, TELEMETRY_ROOTS,
    plan_wipe, load_schema, transfer_predicates, verify_state,
    chunked_wipe, delete_table_chunked, assert_disk_floor, DiskFloorError,
    telemetry_closure, telemetry_books_conflict,
)

DEFAULT_PRESERVE = PRESERVE | COA_TABLES  # default flags: CoA kept, documents deleted
N_CUST = 5  # enough customers to span multiple batches (batch-boundary + resume tests)


@pytest.fixture
def throwaway():
    """A disposable tenant with N_CUST delete-set rows (customers) and a
    preserve-set row (financial_account), plus preserved identity rows."""
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
    custs = [Customer(id=str(uuid.uuid4()), company_id=co.id, name=f"Doomed {i}")
             for i in range(N_CUST)]
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Kept Operating")
    s.add_all([user, acct, *custs]); s.commit()
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


def _telemetry_first(conn, delete_set):
    """Helper: the telemetry-closure set for a plan (used as chunked_wipe first_set)."""
    return telemetry_closure(TELEMETRY_ROOTS, load_schema(conn)[3], delete_set)


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
        n_cust = conn.execute(
            text(f'SELECT count(*) FROM customers WHERE {preds["customers"]}'),
            {"tid": co_id}).scalar()
        # pre-wipe verify: delete-set NOT empty (has the customers)
        pre = verify_state(conn, co_id, DEFAULT_PRESERVE)
        first = _telemetry_first(conn, delete_set)
    assert n_cust == N_CUST
    assert pre["delete_set_remaining_total"] >= N_CUST
    assert pre["company_present"] is True

    # chunked, committed-batch execution (no disk guard in this focused test).
    # batch_size=2 with N_CUST=5 exercises multi-batch deletion within a table.
    with engine.connect() as conn:
        nulled, deleted, aborted = chunked_wipe(
            conn, co_id, order, preds, break_edges, first_set=first,
            batch_size=2, progress=False)
    assert aborted is False
    assert deleted.get("customers") == N_CUST

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
        post = verify_state(conn, co_id, DEFAULT_PRESERVE)
    assert post["delete_set_remaining_total"] == 0
    assert post["delete_set_remaining"] == {}
    assert post["company_present"] is True
    assert post["preserved"]["users"] == 1
    assert post["preserved"]["roles"] == 1
    assert all(n == 0 for n in post["cycle_backedges_nonnull"].values())


def test_batch_boundaries_delete_fully_across_batches(throwaway):
    """A table with more rows than one batch is fully deleted across multiple
    committed batches — the batch boundary must not leave a tail behind."""
    co_id = throwaway["co"]
    with engine.connect() as conn:
        preds = plan_wipe(conn, DEFAULT_PRESERVE)[5]
        # batch_size 2 with N_CUST=5 → 3 batches (2 + 2 + 1); all must go
        deleted = delete_table_chunked(conn, co_id, "customers", preds["customers"],
                                       batch_size=2, progress=False)
        remaining = conn.execute(text("SELECT count(*) FROM customers WHERE company_id=:c"),
                                 {"c": co_id}).scalar()
    assert deleted == N_CUST
    assert remaining == 0


def test_resume_after_partial_leaves_fully_wiped(throwaway):
    """A partial wipe followed by a re-run leaves the tenant fully wiped —
    idempotent + resumable, no state file. Re-running an already-wiped tenant is
    a clean no-op."""
    co_id = throwaway["co"]
    # PARTIAL: delete only 2 of the N_CUST customers (one batch), commit, stop.
    with engine.connect() as conn:
        conn.execute(text('DELETE FROM customers WHERE ctid IN '
                          '(SELECT ctid FROM customers WHERE company_id=:c LIMIT 2)'),
                     {"c": co_id})
        conn.commit()
        mid = conn.execute(text("SELECT count(*) FROM customers WHERE company_id=:c"),
                           {"c": co_id}).scalar()
    assert mid == N_CUST - 2  # partial state: some remain

    # RESUME: a full chunked_wipe finishes whatever remains
    with engine.connect() as conn:
        (delete_set, order, break_edges, *_rest) = plan_wipe(conn, DEFAULT_PRESERVE)
        preds = plan_wipe(conn, DEFAULT_PRESERVE)[5]
        first = _telemetry_first(conn, delete_set)
        _n, deleted, aborted = chunked_wipe(
            conn, co_id, order, preds, break_edges, first_set=first,
            batch_size=2, progress=False)
        remaining = conn.execute(text("SELECT count(*) FROM customers WHERE company_id=:c"),
                                 {"c": co_id}).scalar()
    assert aborted is False
    assert deleted.get("customers") == N_CUST - 2  # resume deleted only what remained
    assert remaining == 0

    # RE-RUN on the already-wiped tenant: nothing left to delete
    with engine.connect() as conn:
        (delete_set2, order2, be2, *_r) = plan_wipe(conn, DEFAULT_PRESERVE)
        preds2 = plan_wipe(conn, DEFAULT_PRESERVE)[5]
        first2 = _telemetry_first(conn, delete_set2)
        _n2, deleted2, aborted2 = chunked_wipe(
            conn, co_id, order2, preds2, be2, first_set=first2,
            batch_size=2, progress=False)
    assert aborted2 is False
    assert sum(deleted2.values()) == 0


def test_disk_floor_refuses_start_when_below(monkeypatch):
    """The disk floor refuses to start when free space is below it (reading mocked)."""
    monkeypatch.setattr(wipe_tenant, "read_free_bytes", lambda conn, data_dir: 1 * 1024**3)
    with pytest.raises(DiskFloorError, match="below floor"):
        assert_disk_floor(conn=None, data_dir="/x", floor_bytes=2 * 1024**3)


def test_disk_floor_passes_when_above(monkeypatch):
    monkeypatch.setattr(wipe_tenant, "read_free_bytes", lambda conn, data_dir: 5 * 1024**3)
    assert assert_disk_floor(conn=None, data_dir="/x", floor_bytes=2 * 1024**3) == 5 * 1024**3


def test_disk_guard_blind_refuses(monkeypatch):
    """If free space cannot be read at all, the guard REFUSES — a disk guard that
    can't see the disk is not a guard."""
    def _boom(conn, data_dir):
        raise RuntimeError("no df here")
    monkeypatch.setattr(wipe_tenant, "read_free_bytes", _boom)
    with pytest.raises(DiskFloorError, match="blind"):
        assert_disk_floor(conn=None, data_dir="/x", floor_bytes=1)


def test_telemetry_closure_guard_fails_on_books_critical():
    """If a books-critical table is a descendant of a telemetry root, the guard
    flags it (fail-loud tripwire). Synthetic edges put period_locks under a root."""
    edges = [
        ("agent_run_steps", "job_id", "agent_jobs", "NO ACTION", True),
        ("period_locks", "step_id", "agent_run_steps", "NO ACTION", False),  # the trap
    ]
    delete_set = {"agent_run_steps", "agent_jobs", "period_locks", "workflow_run_steps"}
    closure = telemetry_closure(TELEMETRY_ROOTS, edges, delete_set)
    assert "period_locks" in closure
    assert "period_locks" in telemetry_books_conflict(closure)


def test_telemetry_closure_real_schema_is_clean():
    """Against the REAL schema the telemetry closure reaches nothing
    books-critical — period_locks in particular hangs off agent_jobs, not the
    step roots. If this fails, a schema change made a books table a descendant of
    a telemetry root; investigate, do not relax."""
    with engine.connect() as conn:
        edges = load_schema(conn)[3]
        delete_set = plan_wipe(conn, DEFAULT_PRESERVE)[0]
    closure = telemetry_closure(TELEMETRY_ROOTS, edges, delete_set)
    assert "agent_run_steps" in closure and "workflow_run_steps" in closure
    assert "period_locks" not in closure
    assert telemetry_books_conflict(closure) == []


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
