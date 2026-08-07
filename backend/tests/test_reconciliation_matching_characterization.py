"""Reconciliation matching — behavior pins across the S-4 extraction AND the
Books Review Phase 2 A-2 rewrite.

The precedence ladder (pattern -> exact-amount -> reference -> unmatched),
direction-honesty, ambiguity-skip, and confidences are pinned by
test_reconciliation_matching_rework.py::TestMatchingHandMath. This file carries
three additional pins:

  1. FLIPPED BY L-2 (Ledger Posting): the payroll asymmetry is GONE, and what
     replaced it is visible here as ARITHMETIC. Pre-L-2 this class pinned
     `payroll` counting as auto-cleared and moving cleared_total while `bank_fee`
     and `nsf` did not — an asymmetry with no accounting behind it, on top of a
     deeper problem: payroll moved cleared_total while booking NOTHING, so the
     reconciliation reported money as cleared that the ledger had never seen.
     L-2 makes booking the licence to clear. These tenants have no GL
     configuration at all, so post-L-2 NOTHING clears here — the fail-closed
     path, hand-computed. The configured direction (all three book, all three
     clear) is pinned in test_reconciliation_gl_l2.py, which owns the L-2
     arithmetic in both directions.
  2. FLIPPED BY A-2: a re-run must NOT clobber a manual classification. The
     rewrite is non-destructive (only `unmatched` transactions are rescored),
     so a manual action survives a re-run even when the txn matches a rule.
     (Pre-rewrite this pinned the opposite — the clobber — as the live bug.)
  3. FLIPPED BY A-2: the same payment is NOT cleared by two independent runs.
     The rewrite seeds a `claimed` set from existing auto_cleared transactions,
     so a second run sees the payment already claimed and records it as an
     ALREADY_CLAIMED candidate instead of re-clearing it. (Pre-rewrite this
     pinned the double-clear as the live bug the Phase-2 rewrite must fix.)

Cleans up its own companies (COMPANY-LITTER ratchet).
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


class TestUnconfiguredTenantClearsNothing:
    """FLIPPED BY L-2. These tenants are created with no keyword→GL map and no
    GL account on the bank account, which is the state every tenant is in until
    someone configures it. Pre-L-2 that state still produced a cleared balance;
    post-L-2 it produces exceptions."""

    def test_no_gl_configuration_means_no_row_clears(self, db):
        """HAND MATH — three pattern-only lines, no GL configuration:
          T0 'GUSTO PAYROLL'  debit -5000 -> classified payroll,  CANNOT BOOK
          T1 'SERVICE CHARGE' debit  -15  -> classified bank_fee, CANNOT BOOK
          T2 'NSF RETURNED'   debit -100  -> classified nsf,      CANNOT BOOK
          auto 0 · suggested 0 · unmatched 3
          platform_cleared_balance = 0
          difference = closing - opening - cleared
                     = 2000 - 1000 - 0 = 1000

        PRE-L-2 THIS READ: auto 1 · suggested 2 · unmatched 0, cleared -5000,
        difference 6000. The -5000 was payroll clearing against a ledger with
        nothing in it — `journal_entries` was 0 platform-wide. The number moved
        because the label said "payroll", not because anything was booked.
        """
        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co, opening="1000", closing="2000")
        _txn(db, run, day=15, amount="-5000", desc="GUSTO PAYROLL", ttype="debit", order=0)
        _txn(db, run, day=16, amount="-15", desc="MONTHLY SERVICE CHARGE", ttype="debit", order=1)
        _txn(db, run, day=17, amount="-100", desc="NSF RETURNED CHECK", ttype="debit", order=2)
        db.commit()

        result = trigger_matching(run.id, current_user=user, db=db)
        assert result["auto_cleared"] == 0
        assert result["suggested"] == 0
        assert result["unmatched"] == 3

        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("0")
        assert run.difference == Decimal("1000")

    def test_two_payrolls_and_a_fee_still_clear_nothing(self, db):
        """PRE-L-2 THIS READ: cleared -9000 (the two payrolls, fee excluded).
        Post-L-2 the classification is unchanged — all three rows are still
        recognised — but recognition alone no longer moves money."""
        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co, opening="0", closing="0")
        _txn(db, run, day=15, amount="-5000", desc="ADP PAYROLL", ttype="debit", order=0)
        _txn(db, run, day=16, amount="-25", desc="WIRE FEE", ttype="debit", order=1)
        _txn(db, run, day=30, amount="-4000", desc="PAYCHEX PAYROLL", ttype="debit", order=2)
        db.commit()

        trigger_matching(run.id, current_user=user, db=db)
        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("0")


class TestRerunPreservesManualAction:
    def test_rerun_does_not_overwrite_a_manual_classification(self, db):
        # A-2 (flipped from the pre-rewrite characterization): a user manually
        # classifies a transaction; someone re-runs matching. The rewrite is
        # NON-DESTRUCTIVE — it only (re)scores transactions still `unmatched`, so
        # the manual action survives even though the txn also matches a rule.
        co = _mk_company(db)
        user = _mk_user(db, co)
        run = _mk_run(db, co)
        _txn(db, run, day=16, amount="-15", desc="MONTHLY SERVICE CHARGE", ttype="debit", order=0)
        db.commit()

        # Run 1. PRE-L-2 this left the row `bank_fee` on the strength of the
        # description alone; post-L-2 the tenant has no GL configuration, so the
        # row is classified but cannot book and stays `unmatched`. That makes
        # this pin STRICTER, not weaker: the row is now genuinely inside run 2's
        # rescore set, so "the manual action survives" is a real claim about the
        # non-destructive gate rather than a row the gate skipped anyway.
        trigger_matching(run.id, current_user=user, db=db)
        txn = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id
        ).first()
        assert txn.match_status == "unmatched"

        # Manual reclassification.
        txn.match_status = "manually_matched"
        db.commit()

        trigger_matching(run.id, current_user=user, db=db)  # run 2 must NOT clobber
        db.refresh(txn)
        assert txn.match_status == "manually_matched"  # manual action preserved


class TestNoDoubleClaimAcrossRuns:
    def test_a_claimed_payment_is_not_cleared_by_a_second_run(self, db):
        # A-2 (flipped from the pre-rewrite double-clear pin). The rewrite seeds
        # a `claimed` set from every existing auto_cleared transaction, so a
        # second overlapping statement run sees the payment already claimed by
        # the first and does NOT re-clear it — the double-clear is dead. The
        # claimed payment is still RECORDED as an ALREADY_CLAIMED candidate on
        # run_b's transaction (audit trail), it just isn't the accepted match.
        from app.models.financial_account import ReconciliationMatchCandidate

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
        # run_a claims the payment; run_b does NOT re-clear it.
        assert ta.matched_record_id == pay.id
        assert tb.matched_record_id is None
        assert ta.reconciliation_run_id != tb.reconciliation_run_id
        # run_b still surfaces the payment as an ALREADY_CLAIMED candidate.
        tb_cands = db.query(ReconciliationMatchCandidate).filter(
            ReconciliationMatchCandidate.reconciliation_transaction_id == tb.id
        ).all()
        assert [c.rejection_reason for c in tb_cands] == ["ALREADY_CLAIMED"]
        assert tb_cands[0].candidate_record_id == pay.id


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
