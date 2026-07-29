"""Reconciliation matching engine.

S-4 extraction. The matching logic previously lived inline in
`routes/reconciliation.py::trigger_matching`; this is the same engine moved
to the service layer so it has a home to be guarded/rewritten in. PURE
MOVE — behavior is preserved bit-for-bit (verified by
test_reconciliation_matching_rework.py + test_reconciliation_matching_characterization.py).

NON-IDEMPOTENT BY CURRENT DESIGN — pinned, not endorsed:
  - Candidate consumption is in-memory, per-run; NO payment is durably
    marked reconciled, so the SAME payment can be cleared by two runs (the
    double-clear — a live correctness bug).
  - A re-run reclassifies every transaction from scratch, clobbering manual
    actions that also match a rule.
  - Exact-amount match fires only on a SINGLE candidate (ambiguity is
    dropped, not ranked); consumption is greedy first-come by sort_order.
The Phase-2 rewrite replaces this with durable, non-destructive both-sides
matching. This extraction deliberately changes none of it.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.financial_account import ReconciliationRun, ReconciliationTransaction


def run_matching(db: Session, run: ReconciliationRun, company_id: str) -> dict:
    """Run the matching engine on a run's parsed transactions. Mutates the
    transactions + the run's summary counts in place; does NOT commit (the
    caller owns the transaction). Returns
    {auto_cleared, suggested, unmatched, status}.
    """
    # CustomerPayment/VendorPayment imported HERE (not at module top) — the
    # original inline-import semantics preserved verbatim by the S-4 move.
    # The loud-failure test patches app.models.customer_payment.CustomerPayment
    # to force a broken read; a call-time re-resolution is what lets that
    # patch reach the binding. A module-top import would bind once and defeat
    # it — behavior-observable, so the extraction keeps the import inline.
    from app.models.customer_payment import CustomerPayment
    from app.models.vendor_payment import VendorPayment

    transactions = db.query(ReconciliationTransaction).filter(
        ReconciliationTransaction.reconciliation_run_id == run.id,
    ).order_by(ReconciliationTransaction.sort_order).all()

    # Load platform records for matching — REAL models, LOUD (D-3).
    # LOUD-FAILURE CONTRACT: no fallback — a matcher that cannot read its
    # inputs refuses (an "everything's unmatched" screen from a broken read
    # is the lie; refusal is the truth).
    #
    # Payment dates are timestamptz; statement dates are DATE. End-inclusive
    # at day granularity (statement_date + 1, exclusive). period_start is
    # nullable — filter only when present; never invent a window.
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

    # Direction-honest candidate pools (what the data carries): a credit
    # statement line (deposit) matches CUSTOMER payments; a debit
    # (withdrawal) matches VENDOR payments; an untyped line consults both.
    customer_by_amount: dict[str, list] = {}
    for p in payments:
        key = str(round(float(p.total_amount), 2))
        customer_by_amount.setdefault(key, []).append(
            ("customer_payment", p.id, p.payment_date.date() if p.payment_date else None, p.reference_number)
        )
    vendor_by_amount: dict[str, list] = {}
    for vp in vendor_payments:
        key = str(round(float(vp.total_amount), 2))
        vendor_by_amount.setdefault(key, []).append(
            ("vendor_payment", vp.id, vp.payment_date.date() if vp.payment_date else None, vp.reference_number)
        )

    def _pools_for(txn_type: str | None) -> list[dict[str, list]]:
        if txn_type == "credit":
            return [customer_by_amount]
        if txn_type == "debit":
            return [vendor_by_amount]
        return [customer_by_amount, vendor_by_amount]

    auto_count = 0
    suggested_count = 0
    unmatched_count = 0
    cleared_total = Decimal(0)

    for txn in transactions:
        amt = abs(float(txn.amount))
        amt_key = str(round(amt, 2))

        # Pattern recognition first
        desc_upper = txn.description.upper()
        if any(kw in desc_upper for kw in ["SERVICE CHARGE", "MONTHLY FEE", "WIRE FEE", "OVERDRAFT", "ATM FEE"]):
            txn.match_status = "bank_fee"
            txn.match_confidence = Decimal("0.90")
            suggested_count += 1
            continue
        if any(kw in desc_upper for kw in ["PAYROLL", "ADP", "GUSTO", "PAYCHEX"]):
            txn.match_status = "payroll"
            txn.match_confidence = Decimal("0.92")
            auto_count += 1
            cleared_total += txn.amount
            continue
        if any(kw in desc_upper for kw in ["RETURNED", "NSF", "INSUFFICIENT", "REVERSAL"]):
            txn.match_status = "nsf"
            txn.match_confidence = Decimal("0.88")
            suggested_count += 1
            continue

        # Exact amount match — direction-honest pool(s)
        pools = _pools_for(txn.transaction_type)
        candidates = []
        for pool in pools:
            candidates.extend(pool.get(amt_key, []))
        if len(candidates) == 1:
            rec_type, rec_id, rec_date, rec_ref = candidates[0]
            days_diff = abs((txn.transaction_date - rec_date).days) if rec_date else 999
            if days_diff <= 5:
                conf = Decimal("0.98") if days_diff == 0 else Decimal("0.95") if days_diff <= 2 else Decimal("0.90")
                txn.match_status = "auto_cleared"
                txn.match_confidence = conf
                txn.matched_record_type = rec_type
                txn.matched_record_id = rec_id
                auto_count += 1
                cleared_total += txn.amount
                for pool in pools:  # consumed — remove from its source pool
                    if candidates[0] in pool.get(amt_key, []):
                        pool[amt_key].remove(candidates[0])
                continue

        # Reference match — within the direction-honest pool(s)
        if txn.reference_number:
            _ref_pools = [c for pool in pools for c in pool.values()]
            for cands in _ref_pools:
                for c in cands:
                    if c[3] and c[3] == txn.reference_number:
                        txn.match_status = "auto_cleared"
                        txn.match_confidence = Decimal("0.97")
                        txn.matched_record_type = c[0]
                        txn.matched_record_id = c[1]
                        auto_count += 1
                        cleared_total += txn.amount
                        cands.remove(c)
                        break
                if txn.match_status == "auto_cleared":
                    break

        if txn.match_status == "unmatched":
            unmatched_count += 1

    # Update run
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
