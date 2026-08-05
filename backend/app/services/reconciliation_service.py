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

import hashlib
import logging
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationAdjustment,
    ReconciliationException,
    ReconciliationMatchCandidate,
    ReconciliationPaymentClaim,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.services.agents.period_lock import PeriodLockService
from app.services import reconciliation_gl
from app.services.reconciliation_gl import book_keyword_entry

logger = logging.getLogger(__name__)

# ── Keyword ladder (L-2) ─────────────────────────────────────────────────────
# The description patterns and their precedence are UNCHANGED from the original
# inline ladder — fee, then payroll, then nsf, first match wins, same
# confidences. Lifted to module scope only so the classification is nameable
# separately from what a classification now earns (a posting, or an exception).
#
# The vocabulary is code-fixed and matches `reconciliation_gl.KEYWORD_CLASSIFICATIONS`,
# which is what the tenant's settings map keys off.
_KEYWORD_LADDER: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("bank_fee", "0.90", ("SERVICE CHARGE", "MONTHLY FEE", "WIRE FEE", "OVERDRAFT", "ATM FEE")),
    ("payroll", "0.92", ("PAYROLL", "ADP", "GUSTO", "PAYCHEX")),
    ("nsf", "0.88", ("RETURNED", "NSF", "INSUFFICIENT", "REVERSAL")),
)

# The statuses a keyword row holds once it has cleared. A row in one of these
# states counts toward cleared_total ONLY if it actually booked — see the tally.
_KEYWORD_CLEARING_STATUSES: frozenset[str] = frozenset(
    c for (c, _conf, _kw) in _KEYWORD_LADDER
)


def _classify_keyword(description: str | None) -> tuple[str, Decimal] | None:
    """``(classification, confidence)`` for a description the ladder recognizes,
    else ``None``. Pure; first match wins, in ladder order."""
    desc_upper = (description or "").upper()
    for classification, confidence, keywords in _KEYWORD_LADDER:
        if any(kw in desc_upper for kw in keywords):
            return classification, Decimal(confidence)
    return None

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


def _try_claim(db: Session, company_id: str, payment_type: str, payment_id: str,
               txn_id: str, run_id: str) -> bool:
    """Attempt a durable UNIQUE(payment_id) claim inside a SAVEPOINT.

    Returns True if the claim was won, False if the race was LOST — another run
    claimed this payment between our pool load and our insert. The loss is
    LOGGED and returned, never swallowed: the caller records it as an
    ALREADY_CLAIMED candidate so the audit trail shows exactly what happened. A
    bare `except: pass` here would be the double-clear bug wearing a new hat —
    the loser must proceed as "candidate taken," not as "cleared anyway."

    The nested transaction (SAVEPOINT) is what keeps the OUTER transaction usable
    after the UNIQUE violation: only the claim insert rolls back, not the run's
    accumulated candidate/exception writes.
    """
    # Flush all prior pending changes OUTSIDE the savepoint first. Otherwise
    # begin_nested()'s own flush would emit them INSIDE the savepoint, and a claim
    # rollback would undo the run's accumulated candidate writes along with it.
    db.flush()
    try:
        with db.begin_nested():
            db.add(ReconciliationPaymentClaim(
                tenant_id=company_id, payment_type=payment_type, payment_id=payment_id,
                reconciliation_transaction_id=txn_id, reconciliation_run_id=run_id))
            db.flush()
        return True
    except IntegrityError:
        logger.warning(
            "reconciliation: claim race lost for %s %s (txn=%s, tenant=%s) — "
            "recording ALREADY_CLAIMED, not re-clearing",
            payment_type, payment_id, txn_id, company_id)
        return False


def _try_claim_group(db: Session, company_id: str, members: list[dict],
                     txn_id: str, run_id: str) -> bool:
    """ALL-OR-NONE claim of N payments for one transaction (B-5 one-to-many).

    Same savepoint + pre-flush discipline as `_try_claim`, but adds EVERY member
    in ONE savepoint so a UNIQUE(payment_id) violation on ANY member rolls back
    ALL of them — no partial claim, no half-reconciled transaction (which would
    be worse than not supporting one-to-many at all). Returns True if the whole
    group was claimed, False if any member was already taken.
    """
    from app.models.financial_account import ReconciliationPaymentClaim

    db.flush()  # persist prior pending OUTSIDE the savepoint (see _try_claim)
    try:
        with db.begin_nested():
            for m in members:
                db.add(ReconciliationPaymentClaim(
                    tenant_id=company_id, payment_type=m["type"], payment_id=m["id"],
                    reconciliation_transaction_id=txn_id, reconciliation_run_id=run_id))
            db.flush()
        return True
    except IntegrityError:
        logger.warning(
            "reconciliation: group claim lost for txn=%s (a member was already "
            "claimed) — rolled back ALL members, not partial-claiming", txn_id)
        return False


def _payment_group_id(member_ids: list[str]) -> str:
    """Deterministic group key over the SORTED member payment ids.

    THIS IS NOT A ROW ID in any table — it resolves to nothing by design; the
    members live in the candidate's `rejection_detail.members`. A reader seeing
    this in `candidate_record_id` or (once accepted) `txn.matched_record_id` —
    always paired with type `"payment_group"` — must read the members from
    detail / the claim rows, NEVER look this up as a payment. The `grp_` prefix
    makes that unmistakable. Reproducible: same member set → same key.
    """
    digest = hashlib.sha1(",".join(sorted(member_ids)).encode()).hexdigest()
    return f"grp_{digest[:31]}"  # 4 + 31 = 35 chars <= String(36)


def _find_payment_group(honest_pool, target: Decimal,
                        claimed: set[tuple[str, str]]) -> list | None:
    """Find an unclaimed subset of size 2 or 3 summing EXACTLY to `target`.

    Hash-based (~O(N^2)), NOT the exponential general subset-sum: k=2 via a
    complement lookup; k=3 via each pair + a complement lookup. Returns the first
    subset found (as pool tuples) or None. k is capped at 3 — the largest bundle
    this surfaces. Members must each be < target and not already claimed.
    """
    avail = [p for p in honest_pool if (p[0], p[1]) not in claimed and 0 < p[4] < target]
    by_amt: dict[Decimal, list] = {}
    for p in avail:
        by_amt.setdefault(p[4], []).append(p)
    n = len(avail)
    # k = 2
    for i in range(n):
        need = target - avail[i][4]
        for q in by_amt.get(need, []):
            if q[1] != avail[i][1]:
                return [avail[i], q]
    # k = 3
    for i in range(n):
        for j in range(i + 1, n):
            need = target - avail[i][4] - avail[j][4]
            if need <= 0:
                continue
            for q in by_amt.get(need, []):
                if q[1] not in (avail[i][1], avail[j][1]):
                    return [avail[i], avail[j], q]
    return None


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

    # L-2 posting inputs, resolved ONCE per run rather than per transaction: the
    # tenant (holder of the keyword→GL settings map) and the bank account (holder
    # of the contra/cash GL account). Both are LOUD on absence, matching this
    # module's loud-failure contract — a matcher that cannot identify the account
    # it is reconciling must refuse, not book against a guess.
    company = db.query(Company).filter(Company.id == company_id).one()
    financial_account = (
        db.query(FinancialAccount)
        .filter(FinancialAccount.id == run.financial_account_id)
        .one()
    )
    # ONE context for the whole run — the same object Books Review builds for a
    # page of rows, so the matcher's reason and the card's reason cannot come
    # from two implementations. Also drops the per-row cost: resolution used to
    # be three queries per keyword row (keyword leg, contra leg, period lock);
    # it is now three per RUN. A run is a consistent snapshot of configuration
    # by construction, which is the behavior you want anyway — a settings edit
    # mid-run should not split a statement across two rulesets.
    posting_ctx = reconciliation_gl.build_keyword_posting_context(
        db, company, [financial_account]
    )

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

    # The durable claim signal (A-3): the payment-claim table, UNIQUE(payment_id).
    # Seeded once here so a payment already claimed by ANY run is excluded from
    # auto-commit up front (recorded as ALREADY_CLAIMED, not re-cleared); the
    # in-memory set is then extended as this invocation wins new claims, which
    # covers the within-run case (two deposits, one payment). The migration
    # backfilled this table from historical auto_cleared transactions, so a
    # re-run after deploy sees prior matches as claimed. The DB UNIQUE is the
    # real cross-process guard; this set is the cheap up-front filter.
    claimed: set[tuple[str, str]] = {
        (pt, pid)
        for (pt, pid) in db.query(
            ReconciliationPaymentClaim.payment_type,
            ReconciliationPaymentClaim.payment_id,
        ).filter(ReconciliationPaymentClaim.tenant_id == company_id).all()
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
        # NOTE: payment CLAIMS are deliberately NOT cleared here. Only `unmatched`
        # transactions reach this point, and an unmatched txn holds no claim (a
        # claim is created only on auto-commit). Releasing a claim belongs to the
        # txn-delete cascade or the Arc B revert flow, not to a re-score.
        db.query(ReconciliationMatchCandidate).filter(
            ReconciliationMatchCandidate.reconciliation_transaction_id == txn.id,
        ).delete(synchronize_session=False)
        db.query(ReconciliationException).filter(
            ReconciliationException.reconciliation_transaction_id == txn.id,
        ).delete(synchronize_session=False)

        # (2) Keyword ladder — L-2: BOOKING IS THE LICENCE TO CLEAR.
        #
        # The classification vocabulary and its precedence are UNCHANGED (fee →
        # payroll → nsf, same patterns, same confidences). What changed is what
        # a classification EARNS. Before L-2 a keyword row set a status and
        # moved on, booking nothing — payroll went further and moved
        # cleared_total, which is the asymmetry this arc closes. Now every
        # keyword row must produce a balanced two-legged draft JE before it may
        # clear, and a row that cannot book does not clear:
        #
        #   both GL legs resolve + period open  → book draft JE, clear
        #   anything unresolvable               → stay unmatched, EXCEPTION
        #
        # The exception carries WHY (r154), because this is a third kind of
        # Books Review item: the system knows exactly what the row is and only
        # lacks somewhere to put it. That is a configuration fix, not a coding
        # decision, and the card says so.
        classified = _classify_keyword(txn.description)
        if classified is not None:
            classification, confidence = classified
            posting, blocked_reason = posting_ctx.decide(
                classification=classification,
                financial_account_id=financial_account.id,
                entry_date=txn.transaction_date,
            )
            if posting is not None:
                entry = book_keyword_entry(
                    db,
                    company_id=company_id,
                    posting=posting,
                    amount=txn.amount,
                    entry_date=txn.transaction_date,
                    description=txn.description or f"Reconciliation: {classification}",
                    reference_number=txn.reference_number,
                )
                txn.match_status = classification
                txn.match_confidence = confidence
                txn.journal_entry_id = entry.id
                continue
            # Fail closed. `match_status` is already "unmatched" (guaranteed by
            # the gate at the top of the loop), so the row stays out of
            # cleared_total by the same arithmetic that governs every other
            # unmatched row — no separate exclusion to keep in sync.
            db.add(ReconciliationException(
                tenant_id=company_id,
                reconciliation_transaction_id=txn.id,
                reconciliation_run_id=run.id,
                keyword_classification=classification,
                blocked_reason=blocked_reason,
            ))
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

        # ---- one-to-many: a single deposit covering N payments (B-5) ----------
        # Only when no exact single payment matched. k<=3, EXACT total, over the
        # unclaimed direction-honest pool; hash-based (~O(N^2)), not exponential.
        # EXCLUSIONS — stated so nobody reads this as complete:
        #   * a deposit covering 4+ payments will NOT surface (k capped at 3);
        #   * a deposit with a fee/discount netted out (not an exact sum) will NOT
        #     surface (exact-total only — the amount band does not compose here);
        #   * same-customer scoping is unavailable (bank lines carry no
        #     counterparty — the B-6 finding), so members can span customers.
        # Review-only: a payment_group NEVER auto-commits (accepted stays a single
        # payment or None); accepting it claims ALL members, all-or-none (B-5).
        if not saw_exact_payment:
            group = _find_payment_group(honest_pool, txn_amt, claimed)
            if group is not None:
                member_total = sum((m[4] for m in group), Decimal(0))
                cands.append(dict(
                    type="payment_group",
                    id=_payment_group_id([m[1] for m in group]),
                    score=BAND_MAX_SCORE,
                    reason=None,
                    detail={
                        "members": [{"type": m[0], "id": m[1], "amount": str(m[4])} for m in group],
                        "member_total": str(member_total),
                        "member_count": len(group),
                    },
                ))

        # ---- commit the decision (period-lock gated, atomically claimed) ------
        # `accepted` is always a PAYMENT here (invoices/bills/groups never auto-commit).
        if accepted is not None:
            lock = PeriodLockService.check_date_in_locked_period(
                db, company_id, txn.transaction_date)
            if lock is not None:
                # Viable exact match, but its accounting period is closed. Record
                # WHY it didn't clear (a policy gate, not a data problem) and
                # leave the transaction open for review — never write into a
                # locked period.
                accepted["reason"] = "PERIOD_LOCKED"
                accepted["detail"] = {
                    **(accepted.get("detail") or {}),
                    "period_start": lock.period_start.isoformat(),
                    "period_end": lock.period_end.isoformat(),
                }
                accepted = None
            elif _try_claim(db, company_id, accepted["type"], accepted["id"], txn.id, run.id):
                txn.match_status = "auto_cleared"
                txn.match_confidence = accepted["score"]
                txn.matched_record_type = accepted["type"]
                txn.matched_record_id = accepted["id"]
                claimed.add((accepted["type"], accepted["id"]))
            else:
                # Lost the claim race — mark the candidate ALREADY_CLAIMED (its
                # reason, persisted below) and fall through to unmatched+exception.
                accepted["reason"] = "ALREADY_CLAIMED"
                accepted["detail"] = {**(accepted.get("detail") or {}), "claim_race_lost": True}
                accepted = None
        # accepted may now be None (locked / race lost): stays "unmatched", an
        # exception is written below.

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
    # rows.
    #
    # L-2 CLOSES THE PAYROLL ASYMMETRY. Pre-L-2 the buckets were arbitrary:
    # `payroll` counted as cleared and moved cleared_total while booking
    # nothing; `bank_fee` and `nsf` were "suggested" and moved nothing, though
    # the ladder is no less certain about a service charge than about a Gusto
    # run. The rule is now uniform and has a reason behind it — A ROW COUNTS AS
    # CLEARED WHEN IT BOOKED — so all three classifications clear together when
    # they post, and none of them clears when it cannot.
    #
    # The test is `journal_entry_id`, NOT the status string, and that is
    # load-bearing rather than fastidious: `POST .../transactions/{id}/action`
    # with `mark_payroll` sets `match_status = "payroll"` by hand and books
    # nothing. Tallying on the label would let that manual action move
    # cleared_total against an empty ledger — precisely the defect this arc
    # exists to remove, reintroduced through a side door.
    #
    # `auto_cleared` counts unconditionally: it is the payment-match path, and
    # it still books nothing. A payment match clears on the strength of the
    # matched payment record, exactly as before.
    #
    # Corrected 2026-08-05 — this said "(that is L-3)", and L-3 did NOT close
    # it. L-3 closed the CODING accept and scoped `auto_cleared` out
    # deliberately, on the ground that a matched payment posts nothing because
    # reconciliation is not an economic event: the money was recognised when the
    # payment was recorded, and booking again would double-count cash.
    #
    # The gap is that the entry it should clear against does not exist —
    # `create_customer_payment` (sales_service.py:1637) writes no journal entry.
    # Closing that is AR-2, which is BLOCKED on an undeposited-funds account
    # existing on the tenant's chart (an accountant's call, not ours: the cash
    # account is unknown at payment time and the chart's nearest clearing
    # account is a liability). See the SCOPE note in
    # tests/test_reconciliation_gl_l2.py for the full reasoning.
    def _has_booked(t) -> bool:
        return t.journal_entry_id is not None

    def _is_cleared(t) -> bool:
        if t.match_status == "auto_cleared":
            return True
        if t.match_status in _KEYWORD_CLEARING_STATUSES:
            return _has_booked(t)
        return False

    auto_count = sum(1 for t in transactions if _is_cleared(t))
    # Structurally zero after L-2 and left in place deliberately: there is no
    # longer any state between "cleared" and "needs a human". A keyword row
    # either booked (cleared) or became an exception (unmatched). The field and
    # its API key stay so the run summary's shape does not churn for consumers.
    suggested_count = 0
    unmatched_count = sum(1 for t in transactions if t.match_status == "unmatched")
    cleared_total = sum((t.amount for t in transactions if _is_cleared(t)), Decimal(0))

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
