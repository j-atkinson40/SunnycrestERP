"""AR-2 — a customer payment's journal entry.

    Dr <the bank's GL account>    Cr <the tenant's AR control account>

CHECKS POST DIRECT TO BANK (operator's call). There is no undeposited-funds
account on the chart and none is being added, so a payment debits the bank at
the moment it is recorded.

**L-3's position survives unchanged because of that.** A reconciliation match
confirms the bank agrees; it posts nothing (`reconciliation_service.py:611-616`
sets `match_status` and `matched_record_*` and writes no `journal_entry_id`).
Cash is therefore debited exactly ONCE, at receipt. The second clause the AR-2
investigation anticipated — a transfer entry at deposit — is only needed under
undeposited funds and is not needed here.

THE TIMING DIFFERENCE THIS ACCEPTS: between recording and deposit the books show
money in the bank that is not there yet. That is a real, bounded difference and
it surfaces as date drift in reconciliation, which the ±5-day window
(`DATE_WINDOW_DAYS = 5`) already handles for the common case. Batch depositors
will exceed it and see those rows arrive in Books Review as ranked candidates
rather than clearing themselves — which is the system working, not an error.

THE BANK IS A TENANT DEFAULT NAMING A `FinancialAccount`, NOT A GL ACCOUNT.
`FinancialAccount.gl_account_id` (r153) already answers "which GL account
represents this bank account", and it is what reconciliation postings use as
their contra. Storing a separate cash mapping here would be a SECOND definition
of the same fact, free to drift from the first — which is precisely what
produced four different AR balance formulas. So the setting holds a
`FinancialAccount.id` and the GL leg is resolved through that account.

FAIL-OPEN ON THE RECORD, FAIL-CLOSED ON THE LEDGER. Every other posting site in
this arc refuses the whole operation when it cannot post. A payment is
different, and the difference is not a softening: **a payment is an event that
already happened in the world.** The cheque is in the drawer. Refusing to record
it does not un-receive the money — it means the books stop describing reality,
the customer still shows as owing, and a collections notice goes to someone who
has paid. So `post_payment` returns None rather than raising, the caller records
the payment regardless, and the gap is REPORTED (see `report_unposted_payment`)
rather than swallowed.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.journal_entry import JournalEntry

logger = logging.getLogger(__name__)

# The tenant's default bank account for recording receipts. Holds a
# `FinancialAccount.id` — see the module docstring on why not a GL id.
#
# A SEPARATE KEY rather than an `accounting_gl` purpose, deliberately: every
# `accounting_gl` value is a `TenantGLMapping.id`, and mixing a second id type
# into that dict would make the E-2 panel's picker wrong for one row and force
# every reader to know which purposes mean which kind of id.
PAYMENT_BANK_SETTINGS_KEY = "payment_bank_financial_account_id"

# Why a payment could not post. Same vocabulary shape as
# `reconciliation_gl.BLOCK_*` — the operator's fix differs per reason.
BLOCK_AR_UNCONFIGURED = "ar_gl_unconfigured"
BLOCK_BANK_UNCONFIGURED = "payment_bank_unconfigured"
BLOCK_BANK_GL_UNSET = "payment_bank_gl_unset"

_BLOCK_FIX = {
    BLOCK_AR_UNCONFIGURED: (
        "no accounts-receivable GL account is configured for this tenant"
    ),
    BLOCK_BANK_UNCONFIGURED: (
        "no default bank account is configured for recording payments"
    ),
    BLOCK_BANK_GL_UNSET: (
        "the default bank account has no GL cash account set on it"
    ),
}

_UNPOSTED_JOB_TYPE = "ar_payment_posting"
_UNPOSTED_ANOMALY_TYPE = "ar_payment_unposted"


def resolve_payment_legs(db: Session, company_id: str):
    """``(bank_mapping, ar_mapping, blocked_reason)`` — the reason is non-None
    iff either mapping is None. Never raises; the caller decides what a failure
    means, and for payments it means record-anyway.

    BOTH LEGS LIVE IN DIFFERENT PLACES and both must be set: the AR account on
    the tenant (`accounting_gl.ar`, E-2's panel) and the cash account on the
    bank account itself (`FinancialAccount.gl_account_id`, the per-account form
    from L-2.1e). Production today has the second one unset on its only bank
    account, so this returns a reason rather than legs.
    """
    from app.models.company import Company
    from app.models.financial_account import FinancialAccount
    from app.services.early_payment_discount_service import (
        ACCOUNTING_GL_SETTINGS_KEY,
    )
    from app.services.reconciliation_gl import contra_gl_with_reason, validate_gl_account

    company = db.query(Company).filter(Company.id == company_id).first()
    settings = (company.settings if company else None) or {}

    # AR leg. Resolved through the same validator every other boundary uses —
    # no second definition of "usable GL account" (L-2.2).
    accounting_gl = settings.get(ACCOUNTING_GL_SETTINGS_KEY) or {}
    ar_id = accounting_gl.get("ar") if isinstance(accounting_gl, dict) else None
    ar = validate_gl_account(db, company_id, ar_id) if ar_id else None
    if ar is None:
        return None, None, BLOCK_AR_UNCONFIGURED

    # Bank leg, via the FinancialAccount so there is one definition of which GL
    # account represents this bank.
    bank_id = settings.get(PAYMENT_BANK_SETTINGS_KEY)
    if not bank_id:
        return None, ar, BLOCK_BANK_UNCONFIGURED
    account = (
        db.query(FinancialAccount)
        .filter(
            FinancialAccount.id == bank_id,
            FinancialAccount.tenant_id == company_id,   # tenant-scoped, always
        )
        .first()
    )
    if account is None:
        return None, ar, BLOCK_BANK_UNCONFIGURED

    # `contra_gl_with_reason` is the SAME resolver reconciliation postings use
    # for their cash leg. Reusing it means a payment and a reconciliation entry
    # can never disagree about which account is this bank.
    cash, _reason = contra_gl_with_reason(db, account)
    if cash is None:
        return None, ar, BLOCK_BANK_GL_UNSET
    return cash, ar, None


def post_payment(db: Session, *, company_id: str, payment, user_id: str | None):
    """Book ``Dr bank / Cr AR`` for a recorded payment. Returns the entry, or
    ``None`` when it could not post — NEVER raises for a configuration gap.

    THE FULL PAYMENT POSTS, not the applied portion. The bank received the whole
    amount and the customer owes the whole amount less, whether or not it was
    matched to an invoice. Application is a subledger detail; an overpayment
    that posts only its applied part would leave real cash unrecorded.

    Flushes; does NOT commit — the caller owns the transaction, so the entry and
    the payment land together or not at all.
    """
    from app.services.reconciliation_gl import _Leg, _book_two_legged_entry

    cash, ar, reason = resolve_payment_legs(db, company_id)
    if reason is not None:
        logger.warning(
            "AR-2: payment %s recorded but NOT posted (%s) — tenant=%s amount=%s",
            payment.id, reason, company_id, payment.total_amount,
        )
        report_unposted_payment(
            db, company_id=company_id, payment=payment, reason=reason
        )
        return None

    amount = Decimal(str(payment.total_amount))
    entry = _book_two_legged_entry(
        db,
        company_id=company_id,
        # `subject` takes the DEBIT on a negative amount and the credit on a
        # positive one, so the sign is inverted here relative to a bank line: a
        # receipt is money IN, and cash must take the debit. Passing the amount
        # negated keeps the shared writer's one sign rule intact instead of
        # adding a second one.
        subject=_Leg.from_mapping(cash),
        contra=_Leg.from_mapping(ar),
        amount=-amount,
        entry_date=payment.payment_date,
        description=f"Customer payment {payment.reference_number or payment.id[:8]}",
        reference_number=payment.reference_number,
    )
    payment.journal_entry_id = entry.id
    return entry


_MISMATCH_ANOMALY_TYPE = "ar_payment_bank_mismatch"


def check_match_bank_consistency(
    db: Session, *, company_id: str, run_financial_account_id: str, payment_id: str
) -> bool:
    """AR-2.1 — did this payment post to the bank it actually landed in?

    Returns True when consistent (or unknowable), False when a mismatch was
    found and reported.

    THE FAILURE THIS EXISTS FOR. The bank a payment posts to is a TENANT
    DEFAULT, because `CustomerPayment` carries no bank field and asking at
    payment time is friction on a distinction most tenants do not have. With one
    operating account the default cannot be wrong. With two it can be — and it
    would be wrong SILENTLY, which is the shape this arc keeps refusing.

    The reconciliation match is the moment the truth arrives: the bank line
    belongs to a known `FinancialAccount`, so pairing it with a payment says
    where the money REALLY went. If that disagrees with where the payment
    posted, the default was wrong for this payment and both bank accounts are
    now misstated — one over, one under, by the same amount.

    So the default is not made safe by being a better guess. It is made safe by
    the mismatch being REPORTED, which is the same reasoning AR-1 applied to
    balance drift and the same container.

    Deliberately does NOT correct anything. Amending a posted entry from a
    background match is exactly the "corrects rather than reports" behaviour
    AR-1 spent a phase removing.
    """
    from app.models.customer_payment import CustomerPayment
    from app.models.financial_account import FinancialAccount
    from app.models.journal_entry import JournalEntryLine
    from app.services.reconciliation_gl import contra_gl_with_reason

    payment = (
        db.query(CustomerPayment)
        .filter(
            CustomerPayment.id == payment_id,
            CustomerPayment.company_id == company_id,
        )
        .first()
    )
    # Unposted payments are already reported by their own anomaly; re-reporting
    # them here would double-count one gap as two.
    if payment is None or payment.journal_entry_id is None:
        return True

    account = (
        db.query(FinancialAccount)
        .filter(
            FinancialAccount.id == run_financial_account_id,
            FinancialAccount.tenant_id == company_id,
        )
        .first()
    )
    if account is None:
        return True
    landed_in, _reason = contra_gl_with_reason(db, account)
    if landed_in is None:
        # The bank line's own account has no GL mapping. That is a
        # configuration gap the reconciliation surfaces on its own terms
        # (contra_gl_unset); not this check's business to duplicate.
        return True

    # Which GL account did the payment's entry actually debit?
    posted_to = (
        db.query(JournalEntryLine)
        .filter(
            JournalEntryLine.journal_entry_id == payment.journal_entry_id,
            JournalEntryLine.debit_amount > 0,
        )
        .first()
    )
    if posted_to is None or posted_to.gl_account_id == landed_in.id:
        return True

    logger.warning(
        "AR-2.1: payment %s posted to GL %s but its bank line belongs to %s "
        "(tenant=%s)",
        payment.id, posted_to.gl_account_id, landed_in.id, company_id,
    )
    _report_bank_mismatch(
        db, company_id=company_id, payment=payment,
        posted_to=posted_to, landed_in=landed_in, account_name=account.account_name,
    )
    return False


def _report_bank_mismatch(
    db: Session, *, company_id: str, payment, posted_to, landed_in, account_name: str
):
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.schemas.agent import AgentJobStatus, AnomalySeverity

    try:
        job = AgentJob(
            id=str(uuid.uuid4()), tenant_id=company_id,
            job_type=_UNPOSTED_JOB_TYPE, status=AgentJobStatus.COMPLETE.value,
            dry_run=False, trigger_type="event", run_log=[], anomaly_count=1,
            report_payload={
                "pipeline": "ar_payment_bank_mismatch",
                "payment_id": payment.id,
                "amount": str(payment.total_amount),
                "posted_to_gl_account_id": posted_to.gl_account_id,
                "landed_in_gl_account_id": landed_in.id,
            },
        )
        db.add(job)
        db.flush()
        db.add(AgentAnomaly(
            id=str(uuid.uuid4()), agent_job_id=job.id,
            severity=AnomalySeverity.WARNING.value,
            anomaly_type=_MISMATCH_ANOMALY_TYPE,
            entity_type="customer_payment", entity_id=payment.id,
            description=(
                f"Payment of ${payment.total_amount} posted to "
                f"{posted_to.gl_account_number or posted_to.gl_account_id}, but the "
                f"bank line that matched it belongs to {account_name} "
                f"({landed_in.account_number} — {landed_in.account_name}). Payments "
                "post to the tenant's default bank account; this one landed "
                "somewhere else, so both accounts are misstated by this amount "
                "until the entry is corrected. Nothing has been changed "
                "automatically."
            ),
            amount=Decimal(str(payment.total_amount)),
            resolved=False,
        ))
    except Exception:
        logger.exception(
            "AR-2.1: failed to report bank mismatch for payment %s (tenant=%s)",
            payment.id, company_id,
        )


def report_unposted_payment(db: Session, *, company_id: str, payment, reason: str):
    """Surface an unposted payment as operator-visible work.

    Fail-open is only safe if the gap is VISIBLE — otherwise it is just a
    silently incomplete ledger, which is the failure this arc exists to remove.
    Same container AR-1's drift reporting uses (`AgentJob` + one `AgentAnomaly`),
    for the same reason: it is the surface five migrated agents already stage
    into, and triage is where the operator works.

    Best-effort by design: a payment must record even if REPORTING the gap
    fails. That is the one place in this arc a broad catch is correct, and it is
    narrow — it wraps only the reporting, never the payment.
    """
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.schemas.agent import AgentJobStatus, AnomalySeverity

    try:
        job = AgentJob(
            id=str(uuid.uuid4()), tenant_id=company_id,
            job_type=_UNPOSTED_JOB_TYPE, status=AgentJobStatus.COMPLETE.value,
            dry_run=False, trigger_type="event", run_log=[], anomaly_count=1,
            report_payload={
                "pipeline": "ar_payment_posting",
                "payment_id": payment.id,
                "amount": str(payment.total_amount),
                "reason": reason,
            },
        )
        db.add(job)
        db.flush()
        db.add(AgentAnomaly(
            id=str(uuid.uuid4()), agent_job_id=job.id,
            severity=AnomalySeverity.WARNING.value,
            anomaly_type=_UNPOSTED_ANOMALY_TYPE,
            entity_type="customer_payment", entity_id=payment.id,
            description=(
                f"Payment of ${payment.total_amount} was recorded but did not "
                f"post to the ledger — {_BLOCK_FIX.get(reason, reason)}. The "
                "payment itself is correct and the customer's balance has moved; "
                "only the journal entry is missing. Configure the account and "
                "the entry can be written afterwards."
            ),
            amount=Decimal(str(payment.total_amount)),
            resolved=False,
        ))
    except Exception:
        # A payment must record even if reporting fails. Deliberately broad and
        # deliberately narrow in scope — see the docstring.
        logger.exception(
            "AR-2: failed to report unposted payment %s (tenant=%s)",
            payment.id, company_id,
        )
