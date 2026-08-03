"""Books Review Phase 2 Arc A-2 — the durable, non-destructive scoring rewrite.

Pins the NEW behavior the pre-rewrite characterization couldn't:
  * every non-keyword transaction gets a persisted candidate set;
  * exact single payment auto-commits + records its accepted candidate (no exception);
  * ambiguity, out-of-window, direction-mismatch, already-claimed each record a
    candidate with the right enum reason (audit trail, not silent drop);
  * the near-amount BAND surfaces a review candidate (never auto) and EXCLUDES
    anything past the band width — the $1-apart bulk stays clean;
  * the invoice/bill fallback catches the early-payment-discount / short-pay case
    (a deposit a couple percent below the invoice it settles), review-only;
  * every non-auto-committed transaction gets exactly one exception;
  * a re-run is idempotent (rebuilds this txn's candidates once, no duplicates).

Money is hand-math'd with the arithmetic shown; never computed by the code under
test. Cleans up its own `a2rec-*` tenants (COMPANY-LITTER ratchet).
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
    ReconciliationException,
    ReconciliationMatchCandidate,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.models.invoice import Invoice
from app.models.vendor import Vendor
from app.models.vendor_payment import VendorPayment
from app.services import reconciliation_service
from tests._cleanup import purge_companies_by_slug

_SLUG_PREFIX = "a2rec-"
_PERIOD_START = date(2026, 7, 1)
_STATEMENT_DATE = date(2026, 7, 31)
_BASE = date(2026, 7, 15)


@pytest.fixture
def env():
    """A company + user + financial account + an in-review run to hang bank
    transactions off. Returns a small namespace of ids + the live session."""
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"A2 {suffix}", slug=f"{_SLUG_PREFIX}{suffix}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Operating")
    s.add(acct); s.flush()
    run = ReconciliationRun(
        id=str(uuid.uuid4()), tenant_id=co.id, financial_account_id=acct.id,
        statement_date=_STATEMENT_DATE, statement_closing_balance=Decimal("0"),
        period_start=_PERIOD_START, opening_balance=Decimal("0"),
    )
    s.add(run); s.commit()
    yield type("Env", (), {"s": s, "co": co.id, "run": run})()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG_PREFIX}%")
    finally:
        s.close()


def _cust(env):
    c = Customer(id=str(uuid.uuid4()), company_id=env.co, name="Cust", is_active=True)
    env.s.add(c); env.s.flush()
    return c


def _vend(env):
    v = Vendor(id=str(uuid.uuid4()), company_id=env.co, name="Vend",
               account_number=f"V-{uuid.uuid4().hex[:6]}")
    env.s.add(v); env.s.flush()
    return v


def _txn(env, *, amount, ttype="credit", day=15, desc="deposit", ref=None, order=0):
    t = ReconciliationTransaction(
        id=str(uuid.uuid4()), tenant_id=env.co, reconciliation_run_id=env.run.id,
        transaction_date=date(2026, 7, day), description=desc, amount=Decimal(amount),
        transaction_type=ttype, reference_number=ref, sort_order=order)
    env.s.add(t); env.s.flush()
    return t


def _cp(env, cust, *, total, day=15, ref=None):
    p = CustomerPayment(id=str(uuid.uuid4()), company_id=env.co, customer_id=cust.id,
                        payment_date=datetime(2026, 7, day, 12, tzinfo=timezone.utc),
                        total_amount=Decimal(total), payment_method="check",
                        reference_number=ref)
    env.s.add(p); env.s.flush()
    return p


def _vp(env, vend, *, total, day=15, ref=None):
    p = VendorPayment(id=str(uuid.uuid4()), company_id=env.co, vendor_id=vend.id,
                      payment_date=datetime(2026, 7, day, 12, tzinfo=timezone.utc),
                      total_amount=Decimal(total), payment_method="check",
                      reference_number=ref)
    env.s.add(p); env.s.flush()
    return p


def _inv(env, cust, *, total, status="sent", paid="0"):
    iv = Invoice(id=str(uuid.uuid4()), company_id=env.co, customer_id=cust.id,
                 number=f"INV-{uuid.uuid4().hex[:6]}", status=status,
                 invoice_date=datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
                 due_date=datetime(2026, 7, 31, 12, tzinfo=timezone.utc),
                 subtotal=Decimal(total), total=Decimal(total), amount_paid=Decimal(paid))
    env.s.add(iv); env.s.flush()
    return iv


def _match(env):
    reconciliation_service.run_matching(env.s, env.run, env.co)
    env.s.commit()


def _cands(env, txn):
    return env.s.query(ReconciliationMatchCandidate).filter(
        ReconciliationMatchCandidate.reconciliation_transaction_id == txn.id
    ).order_by(ReconciliationMatchCandidate.rank).all()


def _exc(env, txn):
    return env.s.query(ReconciliationException).filter(
        ReconciliationException.reconciliation_transaction_id == txn.id
    ).one_or_none()


# ── auto-commit ──────────────────────────────────────────────────────────────
def test_exact_single_payment_auto_commits_and_records_accepted_candidate(env):
    cust = _cust(env)
    pay = _cp(env, cust, total="525.00", day=15)   # same day → conf 0.98
    txn = _txn(env, amount="525.00", day=15)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "auto_cleared"
    assert txn.matched_record_id == pay.id
    assert txn.match_confidence == Decimal("0.980")   # days_diff 0
    cands = _cands(env, txn)
    assert len(cands) == 1
    assert cands[0].candidate_record_id == pay.id
    assert cands[0].rejection_reason is None          # accepted = viable
    assert _exc(env, txn) is None                      # auto → no exception


# ── ambiguity ────────────────────────────────────────────────────────────────
def test_two_exact_payments_are_ambiguous_no_auto_two_candidates_one_exception(env):
    cust = _cust(env)
    p1 = _cp(env, cust, total="488.00", day=15)
    p2 = _cp(env, cust, total="488.00", day=15)
    txn = _txn(env, amount="488.00", day=15)          # no reference → no tiebreak
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"
    assert txn.matched_record_id is None
    cands = _cands(env, txn)
    assert {c.candidate_record_id for c in cands} == {p1.id, p2.id}
    assert all(c.rejection_reason is None for c in cands)   # both viable, neither chosen
    assert _exc(env, txn) is not None


# ── near-amount payment band ────────────────────────────────────────────────
def test_near_amount_payment_band_records_amount_mismatch_and_excludes_far(env):
    # deposit 1000.00, an in-band payment 980.00 (2% below), a far payment 900.00.
    #   in-band:  |1000 - 980| / 980  = 20/980  = 0.020408 ≤ 0.03  → AMOUNT_MISMATCH
    #   far:      |1000 - 900| / 900  = 100/900 = 0.111111 > 0.03  → NOT a candidate
    cust = _cust(env)
    near = _cp(env, cust, total="980.00", day=15)
    _cp(env, cust, total="900.00", day=15)            # far — must be excluded
    txn = _txn(env, amount="1000.00", day=15)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"             # near-miss never auto-commits
    cands = _cands(env, txn)
    assert len(cands) == 1                             # far one excluded
    assert cands[0].candidate_record_id == near.id
    assert cands[0].rejection_reason == "AMOUNT_MISMATCH"
    assert cands[0].rejection_detail["amount_delta"] == "20.00"
    assert Decimal("0") < cands[0].score < reconciliation_service.AUTO_COMMIT_THRESHOLD
    assert _exc(env, txn) is not None


# ── invoice fallback (the EPD / short-pay surface) ──────────────────────────
def test_epd_invoice_fallback_catches_short_pay(env):
    # The W-2 case-6 shape: invoice 4946.43, deposit 4847.50, NO payment.
    #   discount = 4946.43 * 0.02 = 98.8286 → 98.93
    #   deposit  = 4946.43 - 98.93 = 4847.50
    #   pct      = 98.93 / 4946.43 = 0.019999… ≤ 0.03  → AMOUNT_MISMATCH (invoice)
    cust = _cust(env)
    inv = _inv(env, cust, total="4946.43")
    txn = _txn(env, amount="4847.50", day=15)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"             # invoice match is review-only
    assert txn.matched_record_id is None
    cands = _cands(env, txn)
    assert len(cands) == 1
    assert cands[0].candidate_record_type == "invoice"
    assert cands[0].candidate_record_id == inv.id
    assert cands[0].rejection_reason == "AMOUNT_MISMATCH"
    assert cands[0].rejection_detail["amount_delta"] == "98.93"
    assert _exc(env, txn) is not None


def test_exact_invoice_fallback_is_viable_but_review_only_never_auto(env):
    # deposit exactly equals an open invoice, no payment exists. The invoice is a
    # VIABLE (NULL-reason) candidate but invoices never auto-commit.
    cust = _cust(env)
    inv = _inv(env, cust, total="4847.50")
    txn = _txn(env, amount="4847.50", day=15)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"
    assert txn.matched_record_id is None
    cands = _cands(env, txn)
    assert len(cands) == 1
    assert cands[0].candidate_record_type == "invoice"
    assert cands[0].candidate_record_id == inv.id
    assert cands[0].rejection_reason is None
    assert _exc(env, txn) is not None


def test_exact_payment_wins_over_the_invoice_fallback_no_double_count(env):
    # When a real payment matches exactly, the fallback is NOT consulted, so an
    # open invoice at the same amount does NOT become a competing candidate. This
    # is why adding invoices to the pool doesn't break the clean-match cases.
    cust = _cust(env)
    _inv(env, cust, total="525.00")                    # same amount as the deposit
    pay = _cp(env, cust, total="525.00", day=15)
    txn = _txn(env, amount="525.00", day=15)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "auto_cleared"
    assert txn.matched_record_id == pay.id
    cands = _cands(env, txn)
    assert len(cands) == 1                             # only the payment, no invoice
    assert cands[0].candidate_record_type == "customer_payment"


# ── out-of-window / direction mismatch / orphan ─────────────────────────────
def test_out_of_window_exact_payment_is_a_candidate_not_a_match(env):
    # payment exact but 6 days off (still inside the run window) → not auto.
    cust = _cust(env)
    pay = _cp(env, cust, total="733.00", day=9)        # txn day 15 → days_diff 6 > 5
    txn = _txn(env, amount="733.00", day=15)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"
    cands = _cands(env, txn)
    assert len(cands) == 1
    assert cands[0].candidate_record_id == pay.id
    assert cands[0].rejection_reason == "OUTSIDE_DATE_WINDOW"
    assert cands[0].rejection_detail["days_diff"] == 6
    assert _exc(env, txn) is not None


def test_opposite_direction_exact_is_a_direction_mismatch_candidate(env):
    # credit deposit, but only a VENDOR payment holds that amount.
    vend = _vend(env)
    vp = _vp(env, vend, total="777.00", day=15)
    txn = _txn(env, amount="777.00", ttype="credit", day=15)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"
    cands = _cands(env, txn)
    assert len(cands) == 1
    assert cands[0].candidate_record_id == vp.id
    assert cands[0].candidate_record_type == "vendor_payment"
    assert cands[0].rejection_reason == "DIRECTION_MISMATCH"
    assert _exc(env, txn) is not None


def test_orphan_deposit_no_candidates_still_makes_an_exception(env):
    # No payment, no invoice near it → zero candidates, but still an open review
    # item (the card form derives "manual categorization" from the empty set).
    txn = _txn(env, amount="377.00", day=15)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"
    assert _cands(env, txn) == []
    assert _exc(env, txn) is not None


# ── the $1-apart-bulk safety property ───────────────────────────────────────
def test_exact_matches_never_generate_band_noise_from_close_neighbors(env):
    # Two deposits $1.00 apart, each with its own exact payment. The band would
    # catch the neighbor (0.1% off) if it were explored — but exact auto-commit
    # short-circuits before the band, so each txn has exactly ONE candidate.
    cust = _cust(env)
    p1000 = _cp(env, cust, total="1000.00", day=15)
    p1001 = _cp(env, cust, total="1001.00", day=15)
    t1000 = _txn(env, amount="1000.00", day=15, order=0)
    t1001 = _txn(env, amount="1001.00", day=15, order=1)
    _match(env)

    for txn, pay in ((t1000, p1000), (t1001, p1001)):
        env.s.refresh(txn)
        assert txn.match_status == "auto_cleared"
        assert txn.matched_record_id == pay.id
        cands = _cands(env, txn)
        assert len(cands) == 1                          # no near-miss neighbor
        assert cands[0].rejection_reason is None


# ── idempotent re-run ───────────────────────────────────────────────────────
def test_rerun_rebuilds_candidates_once_no_duplicates(env):
    cust = _cust(env)
    _cp(env, cust, total="488.00", day=15)
    _cp(env, cust, total="488.00", day=15)             # ambiguous → 2 candidates + exception
    txn = _txn(env, amount="488.00", day=15)
    _match(env)
    assert len(_cands(env, txn)) == 2
    assert _exc(env, txn) is not None

    _match(env)                                         # second run must not accumulate
    assert len(_cands(env, txn)) == 2
    assert env.s.query(ReconciliationException).filter(
        ReconciliationException.reconciliation_transaction_id == txn.id).count() == 1
