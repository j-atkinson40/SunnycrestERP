"""S-4 — CHARACTERIZATION of reconciliation matching, BEFORE extraction.

The precedence ladder (pattern -> exact-amount -> reference -> unmatched),
direction-honesty, ambiguity-skip, and confidences are already pinned by
test_reconciliation_matching_rework.py::TestMatchingHandMath. This file adds
the three pins that file doesn't carry, so the upcoming
reconciliation_service extraction is proven behavior-preserving across ALL
of the current behavior — including the parts that are wrong:

  1. The payroll asymmetry, as ARITHMETIC: `payroll` counts as auto-cleared
     AND flows into cleared_total / platform_cleared_balance / difference;
     `bank_fee` and `nsf` count as suggested and do NOT. Hand-computed so a
     sign error in the money math trips the test, not just a label change.
  2. Re-running matching CLOBBERS a manual classification when the txn also
     matches a rule — a reader would otherwise assume manual actions are
     respected. Pinned explicitly.
  3. The non-idempotence / double-clear (the Phase-2 handoff artifact): the
     matcher never durably marks a payment reconciled, so the SAME payment
     is cleared by two independent runs. This is a LIVE correctness bug the
     Phase-2 rewrite must fix with durable both-sides state; it is pinned
     here as current behavior, not endorsed.

Extract, don't fix. Cleans up its own companies (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationAdjustment,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.models.role import Role
from app.models.user import User

from app.api.routes.reconciliation import trigger_matching
from app.services import reconciliation_service


_CREATED_COMPANY_IDS: set[str] = set()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(scope="module", autouse=True)
def _cleanup_companies():
    yield
    if not _CREATED_COMPANY_IDS:
        return
    ids = list(_CREATED_COMPANY_IDS)
    s = SessionLocal()
    try:
        for model, col in (
            (ReconciliationTransaction, "tenant_id"),
            (ReconciliationAdjustment, "tenant_id"),
            (ReconciliationRun, "tenant_id"),
            (FinancialAccount, "tenant_id"),
            (CustomerPayment, "company_id"),
            (Customer, "company_id"),
            (User, "company_id"),
            (Role, "company_id"),
        ):
            s.query(model).filter(getattr(model, col).in_(ids)).delete(
                synchronize_session=False
            )
        s.query(Company).filter(Company.id.in_(ids)).delete(
            synchronize_session=False
        )
        s.commit()
    finally:
        s.close()


def _mk_company(db) -> str:
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()), name=f"RS4-{suffix}", slug=f"rs4-{suffix}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    _CREATED_COMPANY_IDS.add(co.id)
    return co.id


def _mk_user(db, co) -> User:
    role = Role(id=str(uuid.uuid4()), company_id=co, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    u = User(
        id=str(uuid.uuid4()), company_id=co, role_id=role.id,
        email=f"rs4-{uuid.uuid4().hex[:6]}@test.local", hashed_password="x",
        first_name="R", last_name="S", is_active=True,
    )
    db.add(u)
    db.commit()
    return u


def _mk_run(db, co, *, opening="1000", closing="2000") -> ReconciliationRun:
    acct = FinancialAccount(
        id=str(uuid.uuid4()), tenant_id=co,
        account_type="checking", account_name="Operating",
    )
    db.add(acct)
    db.flush()
    run = ReconciliationRun(
        id=str(uuid.uuid4()), tenant_id=co, financial_account_id=acct.id,
        statement_date=date(2026, 6, 30),
        statement_closing_balance=Decimal(closing),
        period_start=date(2026, 6, 1), opening_balance=Decimal(opening),
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


def _cp(db, co, cust, *, day, total, ref=None) -> CustomerPayment:
    p = CustomerPayment(
        id=str(uuid.uuid4()), company_id=co, customer_id=cust.id,
        payment_date=datetime(2026, 6, day, 12, tzinfo=timezone.utc),
        total_amount=Decimal(total), payment_method="check",
        reference_number=ref,
    )
    db.add(p)
    return p


class TestPayrollAsymmetryArithmetic:
    def test_payroll_hits_cleared_total_but_fee_and_nsf_do_not(self, db):
        """HAND MATH — three pattern-only lines, no candidates:
          T0 'GUSTO PAYROLL'  debit -5000 -> payroll  (auto;  cleared -5000)
          T1 'SERVICE CHARGE' debit  -15  -> bank_fee (suggested; cleared +0)
          T2 'NSF RETURNED'   debit -100  -> nsf      (suggested; cleared +0)
          auto 1 · suggested 2 · unmatched 0
          platform_cleared_balance = -5000 (payroll ONLY)
          difference = closing - opening - cleared
                     = 2000 - 1000 - (-5000) = 6000
        """
        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co, opening="1000", closing="2000")
        _txn(db, run, day=15, amount="-5000", desc="GUSTO PAYROLL", ttype="debit", order=0)
        _txn(db, run, day=16, amount="-15", desc="MONTHLY SERVICE CHARGE", ttype="debit", order=1)
        _txn(db, run, day=17, amount="-100", desc="NSF RETURNED CHECK", ttype="debit", order=2)
        db.commit()

        result = trigger_matching(run.id, current_user=user, db=db)
        assert result["auto_cleared"] == 1
        assert result["suggested"] == 2
        assert result["unmatched"] == 0

        db.refresh(run)
        # The arithmetic — payroll's signed amount only.
        assert run.platform_cleared_balance == Decimal("-5000")
        assert run.difference == Decimal("6000")

    def test_two_payrolls_accumulate_fees_still_excluded(self, db):
        # Two payrolls -> cleared_total sums both; a fee between them adds 0.
        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co, opening="0", closing="0")
        _txn(db, run, day=15, amount="-5000", desc="ADP PAYROLL", ttype="debit", order=0)
        _txn(db, run, day=16, amount="-25", desc="WIRE FEE", ttype="debit", order=1)
        _txn(db, run, day=30, amount="-4000", desc="PAYCHEX PAYROLL", ttype="debit", order=2)
        db.commit()

        trigger_matching(run.id, current_user=user, db=db)
        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("-9000")  # -5000 + -4000, fee excluded


class TestRerunClobbersManualAction:
    def test_rerun_overwrites_a_manual_classification_on_a_rule_hit(self, db):
        # A user manually classifies a transaction; someone re-runs matching;
        # the classification is silently overwritten because the txn also
        # matches a pattern rule. Pinned so no reader assumes manual actions
        # survive a re-run.
        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co)
        _txn(db, run, day=16, amount="-15", desc="MONTHLY SERVICE CHARGE", ttype="debit", order=0)
        db.commit()

        trigger_matching(run.id, current_user=user, db=db)  # run 1 -> bank_fee
        txn = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id
        ).first()
        assert txn.match_status == "bank_fee"

        # Manual reclassification.
        txn.match_status = "manually_matched"
        db.commit()

        trigger_matching(run.id, current_user=user, db=db)  # run 2 CLOBBERS
        db.refresh(txn)
        assert txn.match_status == "bank_fee"  # manual action lost


class TestNonIdempotentDoubleClaim:
    def test_the_same_payment_is_cleared_by_two_independent_runs(self, db):
        # The Phase-2 handoff artifact. The matcher never durably marks a
        # payment reconciled (it writes matched_record_id on the TXN, nothing
        # on the payment), so two overlapping statement runs each clear the
        # SAME CustomerPayment. Pinned as current behavior; the Phase-2
        # rewrite fixes it with durable both-sides state.
        co = _mk_company(db)
        user = _mk_user(db, co)
        cust = Customer(id=str(uuid.uuid4()), company_id=co, name="Hopkins FH", is_active=True)
        db.add(cust)
        db.flush()
        pay = _cp(db, co, cust, day=14, total="500")
        db.flush()

        run_a = _mk_run(db, co)
        _txn(db, run_a, day=15, amount="500", ttype="credit", order=0)
        run_b = _mk_run(db, co)
        _txn(db, run_b, day=15, amount="500", ttype="credit", order=0)
        db.commit()

        trigger_matching(run_a.id, current_user=user, db=db)
        trigger_matching(run_b.id, current_user=user, db=db)

        ta = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run_a.id
        ).first()
        tb = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run_b.id
        ).first()
        # BOTH runs cleared the SAME payment — the double-clear.
        assert ta.matched_record_id == pay.id
        assert tb.matched_record_id == pay.id
        assert ta.reconciliation_run_id != tb.reconciliation_run_id


class TestCreateAdjustmentDrain:
    def test_adjustment_created_and_run_recalculated(self, db):
        # FIX (was the double-count): adjustments_total is the SUM of all the
        # run's adjustments. The new adjustment is flushed before the sum, so
        # the sum already includes it — no `+ amount` on top.
        #
        # HAND MATH: closing 2000, opening 1000, no matching (cleared None->0),
        # checks/deposits 0, one adjustment +50.00:
        #   adjustments_total = sum(adjustments) = 50.00
        #   difference        = 2000 - 1000 - 0 - 0 + 0 + 50 = 1050.00
        # The no-adjustment baseline difference is 1000.00, so a single 50.00
        # adjustment moves difference by exactly 50.00 — NOT 100.00, which is
        # what the pre-fix double-count produced.
        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co, opening="1000", closing="2000")
        adj_id = reconciliation_service.create_adjustment(
            db, run_id=run.id, company_id=co, created_by=user.id,
            adjustment_type="bank_error", description="test adj", amount=50,
        )
        db.commit()
        adj = db.get(ReconciliationAdjustment, adj_id)
        assert adj is not None and adj.amount == Decimal("50")
        db.refresh(run)
        assert run.adjustments_total == Decimal("50.00")
        assert run.difference == Decimal("1050.00")

    def test_two_adjustments_sum_without_double_count(self, db):
        # The bug was amount-dependent, so a single-adjustment test alone
        # would not catch a partial fix. Two adjustments, 50.00 then 25.00:
        #   adjustments_total = 50 + 25 = 75.00  (the actual sum)
        #   difference        = 2000 - 1000 - 0 - 0 + 0 + 75 = 1075.00
        # (Pre-fix this produced 100.00 / 1100.00 — the second add double-
        # counted the second amount.)
        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co, opening="1000", closing="2000")
        reconciliation_service.create_adjustment(
            db, run_id=run.id, company_id=co, created_by=user.id,
            adjustment_type="bank_error", description="adj1", amount=50,
        )
        reconciliation_service.create_adjustment(
            db, run_id=run.id, company_id=co, created_by=user.id,
            adjustment_type="bank_error", description="adj2", amount=25,
        )
        db.commit()
        db.refresh(run)
        assert run.adjustments_total == Decimal("75.00")
        assert run.difference == Decimal("1075.00")
