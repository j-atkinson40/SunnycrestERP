"""Plaid B-3 pins — the close.

  * THE ZERO-DIFF MATCHER PIN: run-matching's source mentions nothing
    Plaid-shaped — from-feed rows flow through it as CSV rows do.
  * from-feed: posted-only, range, idempotent, unlinked-honest 409,
    isolation.
  * Linking management edges; disconnect's honest consequences.
  * The setup suggestion: fires for a connection-less admin, retires by
    REALITY (a connection exists → gone), dismissal final.
  * The category surface: override upsert/clear, seeded rows preserved.
"""
from __future__ import annotations

import inspect
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.financial_account import (
    FinancialAccount, ReconciliationRun, ReconciliationTransaction,
)
from app.models.plaid import BankAccount, BankTransaction, PlaidItem
from app.services.plaid import crypto as plaid_crypto


@pytest.fixture(scope="module", autouse=True)
def _fernet_key():
    import os
    from cryptography.fernet import Fernet
    prior = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    plaid_crypto.reset_fernet_cache()
    yield
    if prior is None:
        os.environ.pop("CREDENTIAL_ENCRYPTION_KEY", None)
    else:
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = prior
    plaid_crypto.reset_fernet_cache()


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    db = SessionLocal()
    sx = uuid.uuid4().hex[:6]
    co_a = Company(name="B3 A", slug=f"plaid3-a-{sx}")
    co_b = Company(name="B3 B", slug=f"plaid3-b-{sx}")
    db.add_all([co_a, co_b]); db.flush()
    fa = FinancialAccount(tenant_id=co_a.id, account_type="checking",
                          account_name="Operating")
    db.add(fa); db.flush()
    item = PlaidItem(
        tenant_id=co_a.id, plaid_item_id=f"item-{sx}",
        institution_id=f"ins-{sx}", institution_name="First Platypus Bank",
        access_token_encrypted=plaid_crypto.encrypt_token("access-b3"),
    )
    db.add(item); db.flush()
    chk = BankAccount(
        tenant_id=co_a.id, plaid_item_id=item.id,
        plaid_account_id=f"chk-{sx}", name="Checking", mask="0000",
        account_type="depository", account_subtype="checking",
        financial_account_id=fa.id,
    )
    db.add(chk); db.flush()

    def bt(txn_id, amount, d, pending=False, removed=False):
        row = BankTransaction(
            tenant_id=co_a.id, bank_account_id=chk.id,
            plaid_transaction_id=txn_id, amount=Decimal(amount),
            transaction_date=d, description=f"B3 {txn_id}",
            is_pending=pending,
        )
        if removed:
            from datetime import datetime, timezone
            row.removed_at = datetime.now(timezone.utc)
        db.add(row)
        return row

    bt("b3-in-range", "-55.00", date(2026, 7, 10))
    bt("b3-in-range-2", "120.00", date(2026, 7, 12))
    bt("b3-pending", "-9.00", date(2026, 7, 11), pending=True)
    bt("b3-removed", "-7.00", date(2026, 7, 11), removed=True)
    bt("b3-out-of-range", "-3.00", date(2026, 8, 5))
    db.commit()
    ids = {"a": co_a.id, "b": co_b.id, "fa": fa.id, "item": item.id,
           "chk": chk.id, "a_slug": co_a.slug}
    db.close()
    yield ids
    db = SessionLocal()
    for cid in (ids["a"], ids["b"]):
        for t in ("reconciliation_transactions", "reconciliation_runs",
                  "bank_transactions", "bank_accounts", "plaid_items",
                  "plaid_category_mappings", "financial_accounts",
                  "ponder_engagement"):
            col = "user_id" if t == "ponder_engagement" else "tenant_id"
            if t == "ponder_engagement":
                db.execute(sql_text(f"DELETE FROM {t} WHERE company_id = :c"), {"c": cid})
            else:
                db.execute(sql_text(f"DELETE FROM {t} WHERE tenant_id = :c"), {"c": cid})
        db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": cid})
    db.commit(); db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


class TestZeroDiffMatcher:
    def test_run_matching_source_knows_nothing_plaid(self):
        """THE GOVERNING CLAIM MADE LITERAL: the matching engine's source
        contains no Plaid/feed reference — from-feed rows are just rows."""
        import app.api.routes.reconciliation as recon
        src = inspect.getsource(recon.trigger_matching)
        for forbidden in ("plaid", "Plaid", "bank_transaction", "BankTransaction",
                          "feed"):
            assert forbidden not in src, f"matcher touched: {forbidden!r}"


def _mk_run(db, world, *, period_start=date(2026, 7, 1),
            statement=date(2026, 7, 31)):
    run = ReconciliationRun(
        tenant_id=world["a"], financial_account_id=world["fa"],
        statement_date=statement, statement_closing_balance=Decimal("100"),
        period_start=period_start,
    )
    db.add(run); db.commit()
    return run


def _populate(db, world, run, tenant=None):
    """Call the endpoint's core through the route function via TestClient-
    free direct invocation is complex; hit it through the service shape:
    reuse the route with a stub user."""
    from types import SimpleNamespace
    from app.api.routes.reconciliation import populate_from_feed
    user = SimpleNamespace(company_id=tenant or world["a"], id="u1")
    return populate_from_feed(run.id, current_user=user, db=db)


class TestPopulateFromFeed:
    def test_posted_only_range_and_backref(self, db, world):
        run = _mk_run(db, world)
        out = _populate(db, world, run)
        assert out["populated"] == 2  # pending, removed, out-of-range excluded
        rows = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id).all()
        assert {str(r.amount) for r in rows} == {"-55.00", "120.00"}
        assert all(r.bank_transaction_id for r in rows)
        types = {r.transaction_type for r in rows}
        assert types == {"debit", "credit"}

    def test_idempotent(self, db, world):
        run = _mk_run(db, world)
        _populate(db, world, run)
        out2 = _populate(db, world, run)
        assert out2["populated"] == 0
        assert out2["skipped_existing"] == 2

    def test_unlinked_honest_409(self, db, world):
        from fastapi import HTTPException
        fa2 = FinancialAccount(tenant_id=world["a"], account_type="savings",
                               account_name="Unlinked")
        db.add(fa2); db.flush()
        run = ReconciliationRun(
            tenant_id=world["a"], financial_account_id=fa2.id,
            statement_date=date(2026, 7, 31),
            statement_closing_balance=Decimal("0"),
        )
        db.add(run); db.commit()
        with pytest.raises(HTTPException) as e:
            _populate(db, world, run)
        assert e.value.status_code == 409
        assert "no linked bank account" in str(e.value.detail)

    def test_cross_tenant_404(self, db, world):
        from fastapi import HTTPException
        run = _mk_run(db, world)
        with pytest.raises(HTTPException) as e:
            _populate(db, world, run, tenant=world["b"])
        assert e.value.status_code == 404


class TestSetupSuggestion:
    def _build(self, db, world, company_id):
        from app.services.maps_of_content.engagement import build_suggestions
        return build_suggestions(
            db, user_id=str(uuid.uuid4()), company_id=company_id,
            vertical="manufacturing", role_slug="admin", is_admin=True,
        )

    def test_fires_without_connection_retires_by_reality(self, db, world):
        # Tenant B has no connection → fires with the why-line + href.
        out = self._build(db, world, world["b"])
        card = next((s for s in out if s["rule"] == "setup"), None)
        assert card is not None
        assert "live feed" in card["why"]
        # Re-pointed (Integrations area): the card opens the onboarding
        # walk; no direct href.
        assert card["ponder_key"] == "onboarding:connect-your-bank"
        # Tenant A HAS a connection → retired by reality, not by click.
        out_a = self._build(db, world, world["a"])
        assert all(s["rule"] != "setup" for s in out_a)

    def test_dismissal_final(self, db, world):
        from app.services.maps_of_content import engagement as eng
        uid = str(uuid.uuid4())
        eng.record(db, user_id=uid, company_id=world["b"],
                   ponder_key="setup:bank_connection", event="dismissed")
        db.commit()
        from app.services.maps_of_content.engagement import build_suggestions
        out = build_suggestions(
            db, user_id=uid, company_id=world["b"],
            vertical="manufacturing", role_slug="admin", is_admin=True,
        )
        assert all(s["rule"] != "setup" for s in out)


class TestDisconnectAndLink:
    def test_disconnect_stops_feed_keeps_history(self, db, world):
        from types import SimpleNamespace
        from app.api.routes.plaid import disconnect_item
        user = SimpleNamespace(company_id=world["a"], id="u1")
        out = disconnect_item(world["item"], current_user=user, db=db)
        assert "history and matches remain" in out["message"]
        db.expire_all()
        item = db.get(PlaidItem, world["item"])
        assert item.is_active is False and item.status == "disconnected"
        # History remains — the feed rows still stand.
        assert db.query(BankTransaction).filter(
            BankTransaction.tenant_id == world["a"]).count() >= 4
        # Reconnect state for later tests:
        item.is_active = True; item.status = "active"; db.commit()

    def test_link_cross_tenant_fa_404(self, db, world):
        from fastapi import HTTPException
        from types import SimpleNamespace
        from app.api.routes.plaid import link_bank_account, LinkAccountRequest
        fb = FinancialAccount(tenant_id=world["b"], account_type="checking",
                              account_name="B's account")
        db.add(fb); db.commit()
        user = SimpleNamespace(company_id=world["a"], id="u1")
        with pytest.raises(HTTPException) as e:
            link_bank_account(world["chk"], LinkAccountRequest(
                financial_account_id=fb.id), current_user=user, db=db)
        assert e.value.status_code == 404

    def test_unlink_is_honest(self, db, world):
        from types import SimpleNamespace
        from app.api.routes.plaid import link_bank_account, LinkAccountRequest
        user = SimpleNamespace(company_id=world["a"], id="u1")
        out = link_bank_account(world["chk"], LinkAccountRequest(
            financial_account_id=None), current_user=user, db=db)
        assert out["financial_account_id"] is None
        # Re-link for neighbors:
        link_bank_account(world["chk"], LinkAccountRequest(
            financial_account_id=world["fa"]), current_user=user, db=db)


class TestCategorySurface:
    def test_override_upsert_and_clear(self, db, world):
        from types import SimpleNamespace
        from app.api.routes.plaid import (
            CategoryOverrideRequest, list_category_mappings, set_category_override,
        )
        user = SimpleNamespace(company_id=world["a"], id="u1")
        set_category_override(CategoryOverrideRequest(
            plaid_category="BANK_FEES", expense_category="professional_fees",
        ), current_user=user, db=db)
        out = list_category_mappings(current_user=user, db=db)
        row = next(m for m in out["mappings"] if m["plaid_category"] == "BANK_FEES")
        assert row == {"plaid_category": "BANK_FEES",
                       "expense_category": "professional_fees", "source": "yours"}
        # The seeded platform row is untouched underneath:
        seeded = db.execute(sql_text(
            "SELECT expense_category FROM plaid_category_mappings "
            "WHERE tenant_id IS NULL AND plaid_category = 'BANK_FEES'")).scalar()
        assert seeded == "other_expense"
        # Clear → the seeded default shines through again.
        set_category_override(CategoryOverrideRequest(
            plaid_category="BANK_FEES", expense_category=None,
        ), current_user=user, db=db)
        out2 = list_category_mappings(current_user=user, db=db)
        row2 = next(m for m in out2["mappings"] if m["plaid_category"] == "BANK_FEES")
        assert row2["source"] == "seeded"

    def test_unknown_category_rejected(self, db, world):
        from fastapi import HTTPException
        from types import SimpleNamespace
        from app.api.routes.plaid import CategoryOverrideRequest, set_category_override
        user = SimpleNamespace(company_id=world["a"], id="u1")
        with pytest.raises(HTTPException) as e:
            set_category_override(CategoryOverrideRequest(
                plaid_category="BANK_FEES", expense_category="not_a_category",
            ), current_user=user, db=db)
        assert e.value.status_code == 400
