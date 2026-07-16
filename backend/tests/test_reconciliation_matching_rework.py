"""D-3 — reconciliation matching + the C-2 AP-agent rewire, pinned.

The last silent-zero session (audit C-4 + C-2). Hand-computed scenarios per
the D-1/D-2 standard, with independent cross-checks (matched + suggested +
unmatched == total lines, recounted from persisted match_status). Hermetic.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.financial_account import (
    FinancialAccount, ReconciliationRun, ReconciliationTransaction,
)
from app.models.vendor import Vendor
from app.models.vendor_bill import VendorBill
from app.models.vendor_payment import VendorPayment
from app.models.user import User
from app.models.role import Role


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _mk_company(db) -> str:
    suffix = uuid.uuid4().hex[:6]
    co = Company(id=str(uuid.uuid4()), name=f"D3-{suffix}", slug=f"d3-{suffix}",
                 is_active=True, vertical="manufacturing")
    db.add(co)
    db.commit()
    return co.id


def _mk_user(db, co_id) -> User:
    role = Role(id=str(uuid.uuid4()), company_id=co_id, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    u = User(id=str(uuid.uuid4()), company_id=co_id, role_id=role.id,
             email=f"d3-{uuid.uuid4().hex[:6]}@test.local", hashed_password="x",
             first_name="D", last_name="Three", is_active=True)
    db.add(u)
    db.commit()
    return u


def _dt(y, m, d):
    return datetime(y, m, d, 12, 0, tzinfo=timezone.utc)


def _mk_run(db, co_id) -> ReconciliationRun:
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co_id,
                            account_type="checking", account_name="Operating")
    db.add(acct)
    db.flush()
    run = ReconciliationRun(
        id=str(uuid.uuid4()), tenant_id=co_id, financial_account_id=acct.id,
        statement_date=date(2026, 6, 30), statement_closing_balance=Decimal("10000"),
        period_start=date(2026, 6, 1), opening_balance=Decimal("9000"),
    )
    db.add(run)
    db.commit()
    return run


def _txn(db, run, *, day, amount, desc="Check", ttype=None, ref=None, order=0):
    t = ReconciliationTransaction(
        id=str(uuid.uuid4()), tenant_id=run.tenant_id,
        reconciliation_run_id=run.id, transaction_date=date(2026, 6, day),
        description=desc, amount=Decimal(amount),
        transaction_type=ttype, reference_number=ref, sort_order=order,
    )
    db.add(t)
    return t


def _cp(db, co_id, cust, *, day, total, ref=None):
    p = CustomerPayment(id=str(uuid.uuid4()), company_id=co_id, customer_id=cust.id,
                        payment_date=_dt(2026, 6, day), total_amount=Decimal(total),
                        payment_method="check", reference_number=ref)
    db.add(p)
    return p


def _vp(db, co_id, vendor, *, day, total, ref=None):
    p = VendorPayment(id=str(uuid.uuid4()), company_id=co_id, vendor_id=vendor.id,
                      payment_date=_dt(2026, 6, day), total_amount=Decimal(total),
                      payment_method="check", reference_number=ref)
    db.add(p)
    return p


class TestMatchingHandMath:
    def test_both_directions_match_and_the_lie_is_dead(self, db):
        """HAND MATH (statement June 2026):
          T1 credit +500, 06-15  → CustomerPayment P1 $500 06-14 (1 day)
                                    → auto_cleared customer_payment, conf 0.95
          T2 debit  −300, 06-20  → VendorPayment  VP1 $300 06-20 (0 days)
                                    → auto_cleared vendor_payment, conf 0.98
          T3 credit +250 ref CHK-123 → TWO $250 customer candidates (exact-
                match skips on ambiguity) → REFERENCE match P2 → conf 0.97
          T4 credit +999          → no candidate → unmatched
          T5 'SERVICE CHARGE'     → bank_fee (suggested)
          T6 credit +777          → only a VENDOR payment holds $777 —
                DIRECTION-HONEST: a deposit never matches a vendor payment
                → unmatched
          Expected: auto 3 · suggested 1 · unmatched 2."""
        from app.api.routes.reconciliation import trigger_matching

        co = _mk_company(db)
        user = _mk_user(db, co)
        cust = Customer(id=str(uuid.uuid4()), company_id=co, name="Hopkins FH", is_active=True)
        vend = Vendor(id=str(uuid.uuid4()), company_id=co, name="Uline",
                      account_number=f"V-{uuid.uuid4().hex[:6]}")
        db.add_all([cust, vend])
        db.flush()
        run = _mk_run(db, co)

        p1 = _cp(db, co, cust, day=14, total="500")
        p2 = _cp(db, co, cust, day=18, total="250", ref="CHK-123")
        _cp(db, co, cust, day=19, total="250", ref="CHK-999")  # the ambiguity twin
        vp1 = _vp(db, co, vend, day=20, total="300")
        _vp(db, co, vend, day=21, total="777")  # T6's would-be cross-match

        _txn(db, run, day=15, amount="500", ttype="credit", order=0)
        _txn(db, run, day=20, amount="-300", ttype="debit", order=1)
        _txn(db, run, day=18, amount="250", ttype="credit", ref="CHK-123", order=2)
        _txn(db, run, day=25, amount="999", ttype="credit", order=3)
        _txn(db, run, day=26, amount="-15", desc="MONTHLY SERVICE CHARGE", ttype="debit", order=4)
        _txn(db, run, day=27, amount="777", ttype="credit", order=5)
        db.commit()

        result = trigger_matching(run.id, current_user=user, db=db)

        assert result["auto_cleared"] == 3
        assert result["suggested"] == 1
        assert result["unmatched"] == 2

        # Per-line assertions from persisted state.
        txns = {t.sort_order: t for t in db.query(ReconciliationTransaction)
                .filter(ReconciliationTransaction.reconciliation_run_id == run.id).all()}
        assert txns[0].matched_record_type == "customer_payment"
        assert txns[0].matched_record_id == p1.id
        assert txns[0].match_confidence == Decimal("0.950")
        assert txns[1].matched_record_type == "vendor_payment"
        assert txns[1].matched_record_id == vp1.id
        assert txns[1].match_confidence == Decimal("0.980")
        assert txns[2].matched_record_id == p2.id  # the reference match
        assert txns[2].match_confidence == Decimal("0.970")
        assert txns[3].match_status == "unmatched"
        assert txns[4].match_status == "bank_fee"
        assert txns[5].match_status == "unmatched"  # direction honesty

        # INDEPENDENT CROSS-CHECK: statuses recounted from persistence.
        statuses = [t.match_status for t in txns.values()]
        assert len(statuses) == 6
        assert statuses.count("auto_cleared") + statuses.count("bank_fee") + statuses.count("unmatched") == 6

    def test_loud_failure_never_an_all_unmatched_lie(self, db, monkeypatch):
        import app.api.routes.reconciliation as recon

        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co)
        _txn(db, run, day=15, amount="500", ttype="credit")
        db.commit()

        class _Broken:
            pass

        monkeypatch.setattr(recon, "CustomerPayment", _Broken, raising=False)
        # The module imports inside the function — patch the model module ref.
        import app.models.customer_payment as cpm
        monkeypatch.setattr(cpm, "CustomerPayment", _Broken)
        with pytest.raises(Exception):
            recon.trigger_matching(run.id, current_user=user, db=db)


class TestAPUpcomingRewire:
    def test_agent_output_matches_hand_expectation(self, db):
        """HAND MATH (relative to real today):
          B1 due today−5, $400 total $100 paid → OVERDUE alert ($300 balance)
          B2 due today+2, $200                 → DUE-SOON alert
          B3 due today+10, $500                → the 14-day digest (1 bill)
          Excluded: a PAID bill, a DRAFT bill, a zero-balance partial.
          alerts = 2 + digest 1 (+1 payment-run iff today is Monday)."""
        from app.services.agent_service import run_ap_upcoming_payments

        co = _mk_company(db)
        vend = Vendor(id=str(uuid.uuid4()), company_id=co, name="Auburn Aggregate",
                      account_number=f"V-{uuid.uuid4().hex[:6]}")
        db.add(vend)
        db.flush()
        today = date.today()

        def bill(total, paid, status, days_from_today):
            d = today + timedelta(days=days_from_today)
            b = VendorBill(
                id=str(uuid.uuid4()), company_id=co, vendor_id=vend.id,
                number=f"BILL-{uuid.uuid4().hex[:6]}", status=status,
                bill_date=_dt(2026, 6, 1),
                due_date=datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc),
                subtotal=Decimal(total), tax_amount=Decimal("0"),
                total=Decimal(total), amount_paid=Decimal(paid),
            )
            db.add(b)
            return b

        bill("400", "100", "partial", -5)   # overdue, $300 outstanding
        bill("200", "0", "approved", +2)    # due soon
        bill("500", "0", "pending", +10)    # digest
        bill("999", "999", "paid", -1)      # excluded by status
        bill("888", "0", "draft", +1)       # excluded by status
        bill("100", "100", "partial", -2)   # zero balance → skipped
        db.commit()

        result = run_ap_upcoming_payments(db, co)

        assert "error" not in result, f"agent failed: {result}"
        # bills_checked = the 4 open-status bills in window (incl. zero-balance)
        assert result["bills_checked"] == 4
        expected_alerts = 3 + (1 if today.weekday() == 0 else 0)
        assert result["alerts_created"] == expected_alerts

        from app.models.agent import AgentAlert
        alerts = db.query(AgentAlert).filter(AgentAlert.tenant_id == co).all()
        titles = " | ".join(a.title for a in alerts)
        assert "overdue" in titles
        assert "due in 2 days" in titles
        assert "Auburn Aggregate" in titles
        overdue = [a for a in alerts if a.alert_type == "ap_overdue"][0]
        assert "$300.00" in overdue.message  # partial reduces the balance alerted

    def test_broken_read_is_a_failed_job_never_a_silent_empty_run(self, db, monkeypatch):
        from app.services import agent_service
        import app.models.vendor_bill as vbm

        co = _mk_company(db)

        class _Broken:
            pass

        monkeypatch.setattr(vbm, "VendorBill", _Broken)
        result = agent_service.run_ap_upcoming_payments(db, co)

        # The agent framework's loud-record contract: the job is FAILED with
        # the error recorded — never a green run with zero alerts.
        assert "error" in result
        from app.models.agent import AgentJob
        job = (db.query(AgentJob)
               .filter(AgentJob.tenant_id == co, AgentJob.job_type == "ap_upcoming_payments")
               .order_by(AgentJob.created_at.desc()).first())
        assert job is not None and job.status == "failed"
        assert job.error_message
