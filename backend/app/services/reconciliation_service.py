"""Reconciliation matching engine.

Books Review Phase 2, Arc A-2 — the DURABLE, NON-DESTRUCTIVE rewrite. The
matcher now PROPOSES rather than DECIDES: every non-keyword transaction gets
a scored candidate set persisted in `reconciliation_match_candidates`, and
transactions that don't auto-commit get a `reconciliation_exceptions` row
(the Books Review workspace). Three properties this arc establishes, each of
which the prior engine violated (see the characterization tests it flips):

  1. NON-DESTRUCTIVE re-run. Only `unmatched` transactions are (re)scored;
     anything already resolved — a human's manual action OR a prior auto —
     is left untouched. (Flips the "re-run clobbers a manual action" pin.)
  2. NO double-clear. A `claimed` set — seeded from every existing
     `auto_cleared` transaction for this company, then extended as this
     invocation commits — prevents the SAME payment being cleared twice,
     within a run (two deposits, one payment) or across runs. The claimed
     payment is RETAINED as an `ALREADY_CLAIMED` candidate (audit trail),
     not silently consumed. (Flips the cross-run double-clear pin.)
  3. Candidates key to the TRANSACTION, so an auto-committed match keeps the
     record of what else was considered.

The exact-amount payment ladder (0.98/0.95/0.90 by date drift, 0.97 by
reference, ambiguity-skip, direction honesty) is preserved bit-for-bit — the
auto/suggested/unmatched HEADLINE counts do not move; what's new is the
durable candidate + exception substrate beneath them, plus the near-amount
BAND and the invoice/bill fallback that surface review candidates the exact
ladder never could (the early-payment-discount / short-pay case).

A-3 will replace the transaction-derived `claimed` set with a dedicated
payment-claim table (UNIQUE(payment_id), IntegrityError on race, period-lock
integration); A-2 uses the existing `auto_cleared` transactions as the
durable claim signal.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.financial_account import (
    ReconciliationAdjustment,
    ReconciliationException,
    ReconciliationMatchCandidate,
    ReconciliationRun,
    ReconciliationTransaction,
)

# ── A-2 scoring constants ────────────────────────────────────────────────────
# BOTH OF THESE ARE GUESSES, NOT TUNED VALUES. They are placeholders until real
# reconciliation data from the Sunnycrest cutover tells us what the true
# distributions are. Named as constants precisely so nobody later reads a magic
# number in the ladder as if it were calibrated. Revisit against cutover data.

# The score at/above which a PAYMENT candidate auto-commits. Set to the exact
# ladder's existing floor (the >2-and-≤5-day tier = 0.90) so A-2 preserves the
# prior engine's auto-commit behavior bit-for-bit: every match that used to
# auto-clear still does. GUESS — the real threshold comes from cutover data.
AUTO_COMMIT_THRESHOLD = Decimal("0.90")

# How far a candidate's amount may sit from the transaction and still be
# SURFACED (never auto-committed) as a near-amount candidate for human review.
# The lower bound is the load-bearing one: the largest legitimate short-pay we
# must catch is a standard early-payment discount — "2/10 net 30" = 2% — and the
# W-2 EPD test case is exactly 2.00% ($98.93 on a $4,946.43 invoice). Set to 3%
# so a 2% EPD sits comfortably INSIDE the band with margin, not fragile at its
# edge; too tight and the EPD deposit stops surfacing its invoice at all. GUESS
# above the 2% floor — the real width comes from cutover EPD/short-pay terms.
#
# ASYMMETRY NOTE: the band is applied SYMMETRICALLY (|delta| / candidate), but
# the 2%-EPD derivation above justifies only the LOWER side (deposit BELOW the
# candidate = discount / short-pay). A deposit ABOVE the candidate is an
# overpayment or a different invoice — a distinct signal this reasoning does not
# cover. Anyone widening this band should widen the lower side and justify the
# upper side separately (or split it into two bounds).
AMOUNT_BAND_PCT = Decimal("0.03")

# Ceiling score for a near-amount (band) candidate. DERIVED, not an independent
# knob: it is strictly below AUTO_COMMIT_THRESHOLD so a band candidate can never
# auto-commit — a consequence of the threshold, kept in sync with it.
BAND_MAX_SCORE = Decimal("0.85")

# Statement/payment date-drift window (days) for an exact-amount payment to be
# an auto-eligible candidate. Preserved from the prior engine (≤5 days).
DATE_WINDOW_DAYS = 5

# Invoice/vendor-bill statuses that represent OPEN receivable/payable balances a
# statement line could be settling. draft/paid/void/write_off are excluded.
_OPEN_INVOICE_STATUSES = ("sent", "partial", "overdue")
_OPEN_BILL_STATUSES = ("approved", "pending", "partial", "overdue")


def _days_diff(txn_date, rec_date) -> int:
    return abs((txn_date - rec_date).days) if rec_date else 999


def _exact_conf(days: int) -> Decimal:
    """The preserved exact-amount confidence ladder."""
    if days == 0:
        return Decimal("0.98")
    if days <= 2:
        return Decimal("0.95")
    return Decimal("0.90")  # days <= DATE_WINDOW_DAYS


def run_matching(db: Session, run: ReconciliationRun, company_id: str) -> dict:
    """Run the matching engine on a run's parsed transactions. Mutates the
    transactions + writes candidate/exception rows + the run's summary counts;
    does NOT commit (the caller owns the transaction). Returns
    {auto_cleared, suggested, unmatched, status}.
    """
    # CustomerPayment/VendorPayment imported HERE (not at module top) — the
    # original inline-import semantics preserved verbatim. The loud-failure test
    # patches app.models.customer_payment.CustomerPayment to force a broken read;
    # a call-time re-resolution is what lets that patch reach the binding. A
    # module-top import would bind once and defeat it — behavior-observable, so
    # the imports stay inline. Invoice/VendorBill join the same discipline.
    from app.models.customer_payment import CustomerPayment
    from app.models.invoice import Invoice
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_payment import VendorPayment

    transactions = db.query(ReconciliationTransaction).filter(
        ReconciliationTransaction.reconciliation_run_id == run.id,
    ).order_by(ReconciliationTransaction.sort_order).all()

    # Load platform records for matching — REAL models, LOUD (D-3).
    # LOUD-FAILURE CONTRACT: no fallback — a matcher that cannot read its inputs
    # refuses (an "everything's unmatched" screen from a broken read is the lie;
    # refusal is the truth).
    #
    # Payment dates are timestamptz; statement dates are DATE. End-inclusive at
    # day granularity (statement_date + 1, exclusive). period_start is nullable —
    # filter only when present; never invent a window.
    upper = run.statement_date + timedelta(days=1)
    cp_q = db.query(CustomerPayment).filter(
        CustomerPayment.company_id == company_id,
        CustomerPayment.deleted_at.is_(None),
        CustomerPayment.payment_date < upper,
    )
    vp_q = db.query(VendorPayment).filter(
        VendorPayment.company_id == company_id,
        VendorPayment.deleted_at.is_(None),
        VendorPayment.payment_date < upper,
    )
    if run.period_start:
        cp_q = cp_q.filter(CustomerPayment.payment_date >= run.period_start)
        vp_q = vp_q.filter(VendorPayment.payment_date >= run.period_start)
    payments = cp_q.all()
    vendor_payments = vp_q.all()

    # Flat, direction-honest payment pools: (type, id, date, ref, amount). A
    # credit line (deposit) matches CUSTOMER payments; a debit (withdrawal)
    # matches VENDOR payments; an untyped line consults both. The pool is NEVER
    # mutated (non-destructive) — the `claimed` set below is what prevents reuse.
    customer_pool = [
        ("customer_payment", p.id, p.payment_date.date() if p.payment_date else None,
         p.reference_number, Decimal(str(p.total_amount)))
        for p in payments
    ]
    vendor_pool = [
        ("vendor_payment", vp.id, vp.payment_date.date() if vp.payment_date else None,
         vp.reference_number, Decimal(str(vp.total_amount)))
        for vp in vendor_payments
    ]

    # Open-balance fallback pools (invoices for credits, bills for debits). Only
    # consulted for a deposit/withdrawal that finds NO exact payment — this is
    # what catches the early-payment-discount / short-pay case (a deposit a few
    # percent below the invoice it settles). Invoice matches NEVER auto-commit:
    # settling a statement line against an open receivable, with no payment
    # record, is a human decision (discount vs. short-pay vs. partial), so these
    # are review candidates only. Amount = the OPEN balance (total - paid).
    open_invoices = [
        ("invoice", iv.id, iv.invoice_date.date() if iv.invoice_date else None, None,
         Decimal(str(iv.total)) - Decimal(str(iv.amount_paid or 0)))
        for iv in db.query(Invoice).filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(_OPEN_INVOICE_STATUSES),
        ).all()
    ]
    open_invoices = [c for c in open_invoices if c[4] > 0]
    open_bills = [
        ("vendor_bill", b.id, b.bill_date.date() if b.bill_date else None, None,
         Decimal(str(b.total)) - Decimal(str(b.amount_paid or 0)))
        for b in db.query(VendorBill).filter(
            VendorBill.company_id == company_id,
            VendorBill.deleted_at.is_(None),
            VendorBill.status.in_(_OPEN_BILL_STATUSES),
        ).all()
    ]
    open_bills = [c for c in open_bills if c[4] > 0]

    def _payment_pools(txn_type):
        if txn_type == "credit":
            return customer_pool, vendor_pool          # (honest, opposite)
        if txn_type == "debit":
            return vendor_pool, customer_pool
        return customer_pool + vendor_pool, []         # untyped: both honest, no opposite

    def _fallback_pool(txn_type):
        if txn_type == "credit":
            return open_invoices
        if txn_type == "debit":
            return open_bills
        return open_invoices + open_bills

    # The durable claim signal (A-2). Seed from every payment already matched by
    # an existing auto_cleared transaction for this company — this is what stops
    # a second run (or a second deposit in the same run) re-clearing the same
    # payment. A-3 replaces this with a UNIQUE(payment_id) claim table.
    claimed: set[tuple[str, str]] = {
        (t, i)
        for (t, i) in db.query(
            ReconciliationTransaction.matched_record_type,
            ReconciliationTransaction.matched_record_id,
        ).filter(
            ReconciliationTransaction.tenant_id == company_id,
            ReconciliationTransaction.match_status == "auto_cleared",
            ReconciliationTransaction.matched_record_id.isnot(None),
        ).all()
    }

    for txn in transactions:
        # (1) NON-DESTRUCTIVE: only process transactions still open. A prior
        # auto-clear or a human's manual classification is authoritative and is
        # left exactly as-is — including its already-written candidates/exception.
        if txn.match_status != "unmatched":
            continue

        # Idempotent rebuild: this txn is being (re)scored, so clear any prior
        # candidates + exception for it before writing the fresh set. Bounded to
        # THIS transaction — resolved transactions (skipped above) keep theirs.
        db.query(ReconciliationMatchCandidate).filter(
            ReconciliationMatchCandidate.reconciliation_transaction_id == txn.id,
        ).delete(synchronize_session=False)
        db.query(ReconciliationException).filter(
            ReconciliationException.reconciliation_transaction_id == txn.id,
        ).delete(synchronize_session=False)

        # (2) Keyword ladder — UNCHANGED. These short-circuit: they set a status
        # and produce neither candidates nor an exception (they are their own
        # confirmation flow). payroll auto-clears and moves money; fee/nsf are
        # suggested and do not.
        desc_upper = (txn.description or "").upper()
        if any(kw in desc_upper for kw in ["SERVICE CHARGE", "MONTHLY FEE", "WIRE FEE", "OVERDRAFT", "ATM FEE"]):
            txn.match_status = "bank_fee"
            txn.match_confidence = Decimal("0.90")
            continue
        if any(kw in desc_upper for kw in ["PAYROLL", "ADP", "GUSTO", "PAYCHEX"]):
            txn.match_status = "payroll"
            txn.match_confidence = Decimal("0.92")
            continue
        if any(kw in desc_upper for kw in ["RETURNED", "NSF", "INSUFFICIENT", "REVERSAL"]):
            txn.match_status = "nsf"
            txn.match_confidence = Decimal("0.88")
            continue

        txn_amt = abs(Decimal(str(txn.amount)))
        honest_pool, opposite_pool = _payment_pools(txn.transaction_type)

        # Collect scored candidates. Each: dict(type,id,score,reason,detail).
        cands: list[dict] = []
        viable_exact: list[dict] = []   # NULL-reason exact payments, auto-eligible
        saw_exact_payment = False       # any exact payment at all (gates fallback)

        # ---- exact-amount payments in the honest pool -------------------------
        for (rtype, rid, rdate, rref, ramt) in honest_pool:
            if ramt != txn_amt:
                continue
            saw_exact_payment = True
            days = _days_diff(txn.transaction_date, rdate)
            if (rtype, rid) in claimed:
                cands.append(dict(type=rtype, id=rid, score=_exact_conf(min(days, DATE_WINDOW_DAYS)),
                                  reason="ALREADY_CLAIMED", detail={"days_diff": days}))
            elif days > DATE_WINDOW_DAYS:
                cands.append(dict(type=rtype, id=rid, score=Decimal("0.000"),
                                  reason="OUTSIDE_DATE_WINDOW", detail={"days_diff": days}))
            else:
                c = dict(type=rtype, id=rid, score=_exact_conf(days), reason=None,
                         detail={"days_diff": days}, ref=rref)
                cands.append(c)
                viable_exact.append(c)

        # ---- exact-amount in the OPPOSITE pool → direction mismatch (audit) ---
        for (rtype, rid, rdate, rref, ramt) in opposite_pool:
            if ramt == txn_amt:
                cands.append(dict(type=rtype, id=rid, score=Decimal("0.000"),
                                  reason="DIRECTION_MISMATCH",
                                  detail={"txn_type": txn.transaction_type}))

        # ---- decide the auto-commit ------------------------------------------
        accepted = None
        if len(viable_exact) == 1:
            accepted = viable_exact[0]                 # unambiguous exact → auto
        elif txn.reference_number:
            # Ambiguous (or no) exact amount → try a reference match across the
            # honest pool (amount-independent, preserved), skipping claimed.
            for (rtype, rid, rdate, rref, ramt) in honest_pool:
                if rref and rref == txn.reference_number and (rtype, rid) not in claimed:
                    hit = next((c for c in cands if c["id"] == rid and c["reason"] is None), None)
                    if hit is None:
                        hit = dict(type=rtype, id=rid, score=Decimal("0.97"),
                                   reason=None, detail={"matched_by": "reference"})
                        cands.append(hit)
                    else:
                        hit["score"] = Decimal("0.97")
                        hit["detail"] = {**(hit.get("detail") or {}), "matched_by": "reference"}
                    accepted = hit
                    break

        # ---- fallback: open invoices/bills, ONLY if no exact payment ----------
        # The early-payment-discount / short-pay surface. Review-only: recorded
        # as candidates, never auto-committed (accepted stays a payment or None).
        if not saw_exact_payment:
            for (rtype, rid, rdate, rref, ramt) in _fallback_pool(txn.transaction_type):
                if ramt <= 0:
                    continue
                delta = abs(txn_amt - ramt)
                if delta == 0:
                    cands.append(dict(type=rtype, id=rid, score=BAND_MAX_SCORE,
                                      reason=None, detail={"amount_delta": "0"}))
                else:
                    pct = delta / ramt
                    if pct <= AMOUNT_BAND_PCT:
                        closeness = Decimal("1") - (pct / AMOUNT_BAND_PCT)
                        cands.append(dict(
                            type=rtype, id=rid,
                            score=(BAND_MAX_SCORE * closeness).quantize(Decimal("0.001")),
                            reason="AMOUNT_MISMATCH",
                            detail={"amount_delta": str(delta),
                                    "amount_delta_pct": str(pct.quantize(Decimal("0.0001")))}))

        # ---- near-amount PAYMENT band, ONLY when no exact payment existed -----
        # Same guard as the invoice fallback: the band is the NO-exact-match
        # surface. Gating on `saw_exact_payment` (not merely `accepted is None`)
        # means an ambiguous exact case — two exact payments — does NOT also drag
        # in every OTHER payment within a few percent (cross-case band noise);
        # and the $1-apart bulk, which auto-commits on the exact path, never
        # reaches here at all.
        if not saw_exact_payment:
            for (rtype, rid, rdate, rref, ramt) in honest_pool:
                if ramt == txn_amt or ramt <= 0:
                    continue
                delta = abs(txn_amt - ramt)
                pct = delta / ramt
                if pct <= AMOUNT_BAND_PCT:
                    closeness = Decimal("1") - (pct / AMOUNT_BAND_PCT)
                    cands.append(dict(
                        type=rtype, id=rid,
                        score=(BAND_MAX_SCORE * closeness).quantize(Decimal("0.001")),
                        reason="AMOUNT_MISMATCH",
                        detail={"amount_delta": str(delta),
                                "amount_delta_pct": str(pct.quantize(Decimal("0.0001"))),
                                "days_diff": _days_diff(txn.transaction_date, rdate)}))

        # ---- commit the decision ---------------------------------------------
        if accepted is not None:
            txn.match_status = "auto_cleared"
            txn.match_confidence = accepted["score"]
            txn.matched_record_type = accepted["type"]
            txn.matched_record_id = accepted["id"]
            claimed.add((accepted["type"], accepted["id"]))
        # else: stays "unmatched" — an exception is written below.

        # ---- persist candidates (ranked best-first) + the exception ----------
        for rank, c in enumerate(sorted(cands, key=lambda c: c["score"], reverse=True), start=1):
            db.add(ReconciliationMatchCandidate(
                tenant_id=company_id,
                reconciliation_transaction_id=txn.id,
                candidate_record_type=c["type"],
                candidate_record_id=c["id"],
                score=c["score"],
                rank=rank,
                rejection_reason=c["reason"],
                rejection_detail=c.get("detail"),
            ))

        if txn.match_status == "unmatched":
            # The Books Review workspace row. Carries no match_status copy — the
            # transaction is authority; this just marks the item open for review.
            db.add(ReconciliationException(
                tenant_id=company_id,
                reconciliation_transaction_id=txn.id,
                reconciliation_run_id=run.id,
            ))

    # ---- run summary: RE-TALLY from persisted state ------------------------
    # Tallying the final match_status of every transaction (not incrementing as
    # we go) keeps the counts correct even when a re-run skips already-resolved
    # rows. payroll counts with auto per the preserved asymmetry; fee/nsf are
    # suggested and do NOT flow into cleared_total.
    auto_count = sum(1 for t in transactions if t.match_status in ("auto_cleared", "payroll"))
    suggested_count = sum(1 for t in transactions if t.match_status in ("bank_fee", "nsf"))
    unmatched_count = sum(1 for t in transactions if t.match_status == "unmatched")
    cleared_total = sum((t.amount for t in transactions
                         if t.match_status in ("auto_cleared", "payroll")), Decimal(0))

    run.auto_cleared_count = auto_count
    run.suggested_count = suggested_count
    run.unmatched_count = unmatched_count
    run.platform_cleared_balance = cleared_total
    run.difference = run.statement_closing_balance - (run.opening_balance or Decimal(0)) - cleared_total
    run.status = "in_review"

    return {
        "auto_cleared": auto_count,
        "suggested": suggested_count,
        "unmatched": unmatched_count,
        "status": "in_review",
    }


def create_adjustment(
    db: Session,
    *,
    run_id: str,
    company_id: str,
    created_by: str | None,
    adjustment_type: str,
    description: str | None,
    amount,
) -> str:
    """Create a reconciliation adjustment + recompute the run's
    adjustments_total and difference. Mutates in place; does NOT commit (the
    caller owns the transaction). Returns the new adjustment id. Pure move
    from the route — behavior unchanged (S-5 drain, so the route-write
    ratchet's financial-model allowlist doesn't carry this site)."""
    amount_dec = Decimal(str(amount))
    adj = ReconciliationAdjustment(
        tenant_id=company_id,
        reconciliation_run_id=run_id,
        adjustment_type=adjustment_type,
        description=description,
        amount=amount_dec,
        created_by=created_by,
    )
    db.add(adj)
    # LOAD-BEARING flush — do NOT remove, and do NOT let the sum() below run
    # before it. Two purposes: (1) populates adj.id (Python-default PK) for
    # the return, and (2) puts the new adjustment in the DB BEFORE the sum,
    # so `adjustments_total = sum(all adjustments)` is complete. Correctness
    # must NOT depend on implicit autoflush: with autoflush=False, or the sum
    # reordered first, the total would go UNDER by this adjustment's amount —
    # silently, the opposite direction of the double-count this replaced.
    db.flush()

    # Recalculate adjustments total and difference. The new adjustment was
    # flushed above, so the SUM over all of this run's adjustments already
    # includes it — adjustments_total IS that sum. (The prior code added
    # amount_dec on top of the sum, double-counting the new adjustment by
    # exactly its own amount; see the characterization test.)
    run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).first()
    if run:
        total_adjustments = db.query(
            func.coalesce(func.sum(ReconciliationAdjustment.amount), 0)
        ).filter(
            ReconciliationAdjustment.reconciliation_run_id == run_id,
        ).scalar()
        run.adjustments_total = total_adjustments
        run.difference = (
            run.statement_closing_balance
            - (run.opening_balance or Decimal(0))
            - (run.platform_cleared_balance or Decimal(0))
            - run.outstanding_checks_total
            + run.outstanding_deposits_total
            + run.adjustments_total
        )

    return adj.id
