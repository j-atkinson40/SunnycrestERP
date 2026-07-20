"""Suite Season 1 / Session 1 pins — THE CASH WIRE.

The serializer's balance carry; sync's refresh (with as-of); the
forecast's opening-balance math hand-proven; credit-vs-cash sign
honesty; the browse view's isolation; the check monitor's write; the
health score's cash component reading the REAL position.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.plaid import BankAccount, PlaidItem
from app.services.plaid import crypto as plaid_crypto


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    from app.models.customer import Customer
    from app.models.role import Role
    from app.models.user import User
    db = SessionLocal()
    co = Company(name="CW1", slug=f"cw1-{uuid.uuid4().hex[:6]}")
    other = Company(name="CW1B", slug=f"cw1b-{uuid.uuid4().hex[:6]}")
    db.add_all([co, other]); db.flush()
    role = Role(company_id=co.id, name="CW1", slug=f"cw1-{uuid.uuid4().hex[:4]}")
    db.add(role); db.flush()
    usr = User(company_id=co.id, email=f"cw1-{uuid.uuid4().hex[:6]}@example.com",
               hashed_password="x", first_name="Pin", last_name="Cash",
               role_id=role.id)
    cust = Customer(company_id=co.id, name="CW1 FH",
                    account_number=f"CW-{uuid.uuid4().hex[:5]}")
    from app.models.vendor import Vendor
    vend = Vendor(company_id=co.id, name="CW1 Supply",
                  account_number=f"V-{uuid.uuid4().hex[:5]}")
    item = PlaidItem(
        tenant_id=co.id, plaid_item_id=f"item-{uuid.uuid4().hex[:10]}",
        institution_id="ins_cw1", institution_name="First Platypus Bank",
        access_token_encrypted=plaid_crypto.encrypt_token("access-test"),
    )
    db.add_all([usr, cust, vend, item]); db.flush()
    checking = BankAccount(
        tenant_id=co.id, plaid_item_id=item.id,
        plaid_account_id=f"chk-{uuid.uuid4().hex[:8]}", name="Checking",
        mask="0000", account_type="depository", account_subtype="checking",
        current_balance=Decimal("5000.00"), available_balance=Decimal("4800.00"),
        balance_as_of=datetime.now(timezone.utc),
    )
    card = BankAccount(
        tenant_id=co.id, plaid_item_id=item.id,
        plaid_account_id=f"crd-{uuid.uuid4().hex[:8]}", name="Business Card",
        mask="9999", account_type="credit", account_subtype="credit card",
        current_balance=Decimal("1000.00"),
        balance_as_of=datetime.now(timezone.utc),
    )
    loan = BankAccount(
        tenant_id=co.id, plaid_item_id=item.id,
        plaid_account_id=f"ln-{uuid.uuid4().hex[:8]}", name="Mortgage",
        mask="8888", account_type="loan", account_subtype="mortgage",
        current_balance=Decimal("56000.00"),
        balance_as_of=datetime.now(timezone.utc),
    )
    db.add_all([checking, card, loan]); db.commit()
    ids = {"co": co.id, "other": other.id, "user": usr.id, "cust": cust.id,
           "vend": vend.id,
           "item": item.id, "chk": checking.id, "card": card.id,
           "chk_plaid": checking.plaid_account_id,
           "card_plaid": card.plaid_account_id}
    db.close()
    yield ids
    db = SessionLocal()
    for stmt in (
        "DELETE FROM bank_transactions WHERE tenant_id = :c",
        "DELETE FROM bank_accounts WHERE tenant_id = :c",
        "DELETE FROM plaid_items WHERE tenant_id = :c",
        "DELETE FROM behavioral_insights WHERE tenant_id = :c",
        "DELETE FROM reconciliation_adjustments WHERE tenant_id = :c",
        "DELETE FROM reconciliation_runs WHERE tenant_id = :c",
        "DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE company_id = :c)",
        "DELETE FROM invoices WHERE company_id = :c",
        "DELETE FROM vendor_bills WHERE company_id = :c",
        "DELETE FROM vault_items WHERE company_id = :c",
        "DELETE FROM audit_logs WHERE company_id = :c",
        "DELETE FROM vaults WHERE company_id = :c",
        "DELETE FROM company_modules WHERE company_id = :c",
        "DELETE FROM financial_accounts WHERE tenant_id = :c",
        "DELETE FROM vendors WHERE company_id = :c",
        "DELETE FROM customers WHERE company_id = :c",
        "DELETE FROM users WHERE company_id = :c",
        "DELETE FROM roles WHERE company_id = :c",
        "DELETE FROM companies WHERE id = :c",
    ):
        for cid in (ids["co"], ids["other"]):
            try:
                db.execute(sql_text(stmt), {"c": cid})
                db.commit()
            except Exception:
                db.rollback()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


class TestSerializerCarry:
    def test_item_summary_carries_balances_with_as_of(self, db, world):
        from app.services.plaid.service import item_summary
        item = db.get(PlaidItem, world["item"])
        accounts = db.query(BankAccount).filter(
            BankAccount.plaid_item_id == item.id).all()
        out = item_summary(item, accounts)
        chk = next(a for a in out["accounts"] if a["name"] == "Checking")
        assert chk["current_balance"] == 5000.00
        assert chk["available_balance"] == 4800.00
        assert chk["balance_as_of"] is not None


class TestSyncRefresh:
    def test_sync_refreshes_balances_and_stamps_as_of(self, db, world, monkeypatch):
        from app.services.plaid import client as plaid_client
        from app.services.plaid import sync as plaid_sync

        monkeypatch.setattr(plaid_client, "sync_transactions",
                            lambda tok, cur, count=500: {
                                "added": [], "modified": [], "removed": [],
                                "next_cursor": "c1", "has_more": False})
        monkeypatch.setattr(plaid_client, "get_accounts",
                            lambda tok: {"accounts": [
                                {"account_id": world["chk_plaid"],
                                 "balances": {"current": 6200.50, "available": 6100.00}},
                                {"account_id": world["card_plaid"],
                                 "balances": {"current": 750.25, "available": None}},
                            ]})
        monkeypatch.setattr(plaid_sync, "access_token_for", lambda item: "tok")

        before = db.get(BankAccount, world["chk"]).balance_as_of
        item = db.get(PlaidItem, world["item"])
        counts = plaid_sync._sync_item(db, item, {}, dry_run=False,
                                       workflow_run_id=None)
        assert counts["balances_refreshed"] is True
        db.expire_all()
        chk = db.get(BankAccount, world["chk"])
        card = db.get(BankAccount, world["card"])
        assert float(chk.current_balance) == 6200.50
        assert float(card.current_balance) == 750.25
        assert chk.balance_as_of is not None and (
            before is None or chk.balance_as_of >= before)
        # restore the hand-math fixture values for later pins
        chk.current_balance = Decimal("5000.00")
        card.current_balance = Decimal("1000.00")
        db.commit()


class TestCreditVsCashSign:
    def test_cash_position_separates_owed_from_owned(self, db, world):
        # Direct service-shape check through the route function.
        from app.api.routes.plaid import cash_position

        class _U:
            company_id = world["co"]
        out = cash_position(current_user=_U(), db=db)
        assert out["connected"] is True
        assert out["cash_on_hand"] == 5000.00     # checking ONLY — the
        # $56,000 mortgage must never masquerade as cash
        assert out["credit_owed"] == 57000.00     # card + loan, both OWED
        assert "owed, not owned" in out["definition"]
        card = next(a for a in out["accounts"] if a["account_type"] == "credit")
        assert card["current_balance"] == 1000.00
        loan = next(a for a in out["accounts"] if a["account_type"] == "loan")
        assert loan["is_credit"] is True  # owed-class on the surface


class TestForecastOpening:
    def test_hand_proven_opening_and_projection(self, db, world):
        """Known balances + known AR/AP → the expected line, by hand:
        opening 5000 (credit excluded); week-1 AR 500 − AP 200 = +300 →
        projected 5300."""
        from app.models.invoice import Invoice
        from app.models.vendor_bill import VendorBill
        now = datetime.now(timezone.utc)
        inv = Invoice(id=str(uuid.uuid4()), company_id=world["co"],
                      number=f"INV-CW-{uuid.uuid4().hex[:5]}",
                      customer_id=world["cust"], status="open",
                      invoice_date=now, due_date=now + timedelta(days=2),
                      subtotal=Decimal("500.00"), tax_amount=Decimal("0.00"),
                      total=Decimal("500.00"))
        bill = VendorBill(id=str(uuid.uuid4()), company_id=world["co"],
                          vendor_id=world["vend"],
                          number=f"B-{uuid.uuid4().hex[:5]}",
                          status="approved",
                          bill_date=now, due_date=now + timedelta(days=2),
                          subtotal=Decimal("200.00"), total=Decimal("200.00"))
        db.add_all([inv, bill]); db.commit()
        try:
            from app.api.routes.financials_board import get_cashflow_forecast

            class _U:
                company_id = world["co"]
            out = get_cashflow_forecast(current_user=_U(), db=db)
            assert out["opening_cash"] == 5000.00
            assert out["opening_as_of"] is not None
            w1 = out["weeks"][0]
            assert w1["ar_expected"] == 500.0
            assert w1["ap_committed"] == 200.0
            assert w1["net"] == 300.0
            assert w1["projected_cash"] == 5300.0
            assert "credit" in out["definition"].lower()
        finally:
            db.delete(inv); db.delete(bill); db.commit()

    def test_no_bank_no_fake_zero(self, db, world):
        from app.api.routes.financials_board import get_cashflow_forecast

        class _U:
            company_id = world["other"]  # tenant with no feed
        out = get_cashflow_forecast(current_user=_U(), db=db)
        assert out["opening_cash"] is None  # honest absence, never fake 0
        assert "projected_cash" not in out["weeks"][0]


class TestBrowseIsolation:
    def test_other_tenant_sees_nothing(self, db, world):
        from app.api.routes.plaid import browse_transactions, cash_position

        class _U:
            company_id = world["other"]
        out = browse_transactions(current_user=_U(), db=db)
        assert out["total"] == 0 and out["items"] == []
        pos = cash_position(current_user=_U(), db=db)
        assert pos["connected"] is False and pos["accounts"] == []


class TestMonitorWrites:
    def test_stale_check_writes_an_insight(self, db, world):
        from app.models.financial_account import (
            FinancialAccount, ReconciliationAdjustment, ReconciliationRun,
        )
        from app.services.proactive_agents import run_uncleared_check_monitor
        acct = FinancialAccount(tenant_id=world["co"], account_name="Ops",
                                account_type="checking")
        db.add(acct); db.flush()
        run = ReconciliationRun(tenant_id=world["co"],
                                financial_account_id=acct.id,
                                statement_date=date.today(),
                                statement_closing_balance=Decimal("0.00"))
        db.add(run); db.flush()
        adj = ReconciliationAdjustment(
            tenant_id=world["co"], reconciliation_run_id=run.id,
            adjustment_type="outstanding_check",
            amount=Decimal("450.00"), description="Check #1042",
        )
        db.add(adj); db.flush()
        db.execute(sql_text(
            "UPDATE reconciliation_adjustments SET created_at = now() - interval '60 days' "
            "WHERE id = :i"), {"i": adj.id})
        db.commit()
        out = run_uncleared_check_monitor(db, world["co"])
        assert out["flagged"] == 1
        n = db.execute(sql_text(
            "SELECT count(*) FROM behavioral_insights WHERE tenant_id = :c "
            "AND headline LIKE '%outstanding 45+%'"), {"c": world["co"]}).scalar()
        assert n >= 1  # the count is no longer discarded


class TestHealthCashReal:
    def test_cash_component_reads_real_position(self, db, world):
        """5000 cash vs 200 AP due 30d → ratio 25 → the 95 band, with the
        numbers in factors — the old existence-heuristic void is dead."""
        from app.models.vendor_bill import VendorBill
        from app.services.financial_health_service import _calculate_cash_position
        now = datetime.now(timezone.utc)
        bill = VendorBill(id=str(uuid.uuid4()), company_id=world["co"],
                          vendor_id=world["vend"],
                          number=f"B2-{uuid.uuid4().hex[:5]}",
                          status="approved", bill_date=now,
                          due_date=now + timedelta(days=10),
                          subtotal=Decimal("200.00"), total=Decimal("200.00"))
        db.add(bill); db.commit()
        try:
            score, factors = _calculate_cash_position(db, world["co"])
            assert score == 95.0
            f = next(x for x in factors if x["factor"] == "cash_vs_ap_30d")
            assert f["cash_on_hand"] == 5000.00
            assert f["ap_due_30d"] == 200.00
        finally:
            db.delete(bill); db.commit()

    def test_no_feed_stated_neutral(self, db, world):
        from app.services.financial_health_service import _calculate_cash_position
        score, factors = _calculate_cash_position(db, world["other"])
        assert score == 70.0
        assert any(x["factor"] == "no_bank_feed" for x in factors)
