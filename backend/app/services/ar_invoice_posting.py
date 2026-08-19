"""INV-1 — the invoice's journal entry: which accounts, and writing it.

    Dr <the tenant's AR control account>    Cr <the tenant's revenue account>

A-1 resolved the legs (`resolve_invoice_legs`); A-2 writes the entry
(`post_invoice`). Split that way on purpose — the account question is where the
fail-closed ruling lives, and the posting is mechanical once it holds.

⚠️ WHY THIS IS THE MIRROR OF `ar_payment_posting` AND NOT AN ADDITION TO IT.
The two are opposite faces of the same account: a payment books
`Dr bank / Cr AR`, an invoice books `Dr AR / Cr revenue`. Same shape, same
BLOCK_* vocabulary, same `(leg, leg, reason)` return — so a reader who has seen
one can read the other. What they must NOT share is a single function branching
on which event it is, which is the "two functions wearing one name" the
`/keyword-gl` vs `/accounting-gl` split already refused.

⚠️ FAIL-CLOSED ON THE LEDGER, FAIL-OPEN ON THE RECORD — AR-2's ruling, and the
invoice sits on the same side of it as the payment. An invoice is a document the
tenant has issued; refusing to record it does not un-issue it, and a customer
who has been billed still owes. So the invoice is created either way and the
POSTING is refused with a named reason. Unconfigured never means "post it to
something plausible."

⚠️ ONE REVENUE ACCOUNT, AND THE PLATFORM SAYS SO OUT LOUD.
Measured on production 2026-08-19: sunnycrest's chart carries THIRTEEN accounts
in the 5xxx block, every one categorised `cogs` —

    5000 REVENUE · 5010 PRECAST SALES · 5012 REDI-ROCK SALES ·
    5014 ROSETTA SALES · 5020 PRECAST-RESALE · 5110 FUNERAL SALES ·
    5120 FUNERAL-RESALE · 5150/5160 REFUNDS-RETURNS · 5165 FUNERAL REBATES ·
    5170 DAMAGE OR DEFECTIVE RESALE · 5210 FREIGHT · 5410 DISCOUNTS ALLOWED-CASH

The split is by PRODUCT LINE, and the platform cannot honour it: measured the
same day, `products.product_line` is NULL for all 33 products on every
production tenant, and only 7 of 12 issued sunnycrest invoice lines carry a
`product_id` at all. An invoice line has nothing to choose with.

So this is the payroll shape — one platform bucket against many chart accounts —
and the resolution is the same one payroll got: admit it. The tenant configures
ONE account; the split waits for the accountant. Deriving a line's account from
a product line that is universally null would produce a confident wrong answer,
which is worse than a refusal.

⚠️ `platform_category` IS NOT CONSULTED, AND THAT IS DELIBERATE. Every revenue
account on the real chart reads `cogs`; the column is an import-time
classification, not a signal. AR-0 ruled this for the AR account
(`early_payment_discount_service.resolve_ar_account`) and the same ruling holds
here — the tenant's explicit choice, validated at use, or nothing.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Why an invoice could not post. Same vocabulary shape as
# `ar_payment_posting.BLOCK_*` and `reconciliation_gl.BLOCK_*` — the operator's
# fix differs per reason, so the reason is per-leg rather than a single
# "unconfigured".
BLOCK_AR_UNCONFIGURED = "ar_gl_unconfigured"
BLOCK_REVENUE_UNCONFIGURED = "revenue_gl_unconfigured"
#: The invoice date falls in a closed period. NOT a configuration gap — the
#: tenant did everything right and the books are shut. Reported, never crashed:
#: `create_journal_entry` raises `PeriodLockedError` and this path catches it,
#: because fail-open on the RECORD means the invoice still issues.
BLOCK_PERIOD_LOCKED = "period_locked"

_BLOCK_FIX = {
    BLOCK_AR_UNCONFIGURED: (
        "no accounts-receivable GL account is configured for this tenant"
    ),
    BLOCK_REVENUE_UNCONFIGURED: (
        "no sales-revenue GL account is configured for this tenant"
    ),
    BLOCK_PERIOD_LOCKED: (
        "the invoice date falls in a closed accounting period"
    ),
}

_UNPOSTED_JOB_TYPE = "ar_invoice_posting"
_UNPOSTED_ANOMALY_TYPE = "ar_invoice_unposted"

#: Own numbering, per `journal_entry_service`'s stated discipline that callers
#: keep their own — `JE-` manual, `DISC-` EPD, `RECON-` reconciliation.
#:
#: ⚠️ AND THAT DISCIPLINE IS WHY THIS DOES NOT REUSE `_book_two_legged_entry`.
#: `post_payment` does, and inherits `RECON-` numbering as a side effect: every
#: payment entry on production reads `RECON-1001..1015` with
#: `entry_type='reconciliation'` though no reconciliation produced them
#: (measured 2026-08-19). Reusing it here would file invoice revenue under
#: reconciliation too, and the register would stop being legible at a glance.
_ENTRY_PREFIX = "INV"
_ENTRY_TYPE = "invoice"


def block_reason_text(reason: str | None) -> str | None:
    """The operator-facing sentence for a block reason, or None.

    A dict lookup rather than `.get(reason, "unknown")`: an unrecognised reason
    is a programming error and should surface as a KeyError in the caller's
    tests, not as the word "unknown" in a report an accountant reads.
    """
    return _BLOCK_FIX[reason] if reason else None


def resolve_invoice_legs(db: Session, company_id: str):
    """``(ar_mapping, revenue_mapping, blocked_reason)`` — the reason is non-None
    iff either mapping is None. Never raises; the caller decides what a failure
    means, and for invoices it means record-anyway-report-the-gap.

    BOTH LEGS ARE `accounting_gl` PURPOSES, unlike the payment path where the
    cash leg lives on the `FinancialAccount`. An invoice touches no bank account,
    so there is no second home to reconcile with — both sides are the tenant's
    stated choice of GL account for a purpose, and both are validated through
    `require_gl_account`, the single definition of "usable GL account" L-2.2
    consolidated to. No third check.

    THE AR LEG IS THE SAME ACCOUNT THE PAYMENT PATH CREDITS. That is the whole
    point of the arc: today AR is credited at payment and never debited at
    invoice, so the control account runs one-directional. Both paths resolving
    `accounting_gl.ar` through the same validator is what makes the two halves
    meet on the same account rather than on two accounts that happen to agree.
    """
    from app.models.company import Company
    from app.services.early_payment_discount_service import (
        ACCOUNTING_GL_SETTINGS_KEY,
    )
    from app.services.reconciliation_gl import validate_gl_account

    company = db.query(Company).filter(Company.id == company_id).first()
    settings = (company.settings if company else None) or {}
    accounting_gl = settings.get(ACCOUNTING_GL_SETTINGS_KEY) or {}
    if not isinstance(accounting_gl, dict):
        # A malformed blob is not a configured tenant. Treated as the AR gap
        # rather than crashing, because the operator's fix is the same panel.
        accounting_gl = {}

    ar_id = accounting_gl.get("ar")
    ar = validate_gl_account(db, company_id, ar_id) if ar_id else None
    if ar is None:
        # AR reported first when BOTH are missing: it is the leg the payment
        # path already depends on, so a tenant fixing it repairs two paths.
        return None, None, BLOCK_AR_UNCONFIGURED

    revenue_id = accounting_gl.get("revenue")
    revenue = validate_gl_account(db, company_id, revenue_id) if revenue_id else None
    if revenue is None:
        return ar, None, BLOCK_REVENUE_UNCONFIGURED

    # ⚠️ THE SAME ACCOUNT ON BOTH LEGS RECORDS NOTHING, and the platform has
    # already met this once — AR-0c's same-account guard fired on real input
    # when testco's AR was pointed at the bank's own contra. Caught here, at
    # resolution, rather than at `create_journal_entry`, so the operator gets a
    # reason naming the panel instead of a balanced-entry error naming nothing
    # they can act on.
    if ar.id == revenue.id:
        return ar, None, BLOCK_REVENUE_UNCONFIGURED

    return ar, revenue, None


def _next_entry_number(db: Session, company_id: str) -> str:
    """``INV-1001``, ``INV-1002``… scoped to the tenant.

    Mirrors `_book_two_legged_entry`'s scheme rather than inventing a second
    one: count this tenant's entries carrying the prefix and add to a 1000 base.
    Tenant-scoped, so two tenants never contend for a number.
    """
    from app.models.journal_entry import JournalEntry

    n = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.tenant_id == company_id,
            JournalEntry.entry_number.like(f"{_ENTRY_PREFIX}-%"),
        )
        .count()
    )
    return f"{_ENTRY_PREFIX}-{1001 + n}"


def post_invoice(db: Session, *, company_id: str, invoice, user_id: str | None):
    """Book ``Dr AR / Cr revenue`` for an issued invoice. Returns the entry, or
    ``None`` when it could not post — NEVER raises for a configuration gap or a
    closed period.

    ⚠️ THE SUBJECT IS FLUSHED BEFORE THE ENTRY IS WRITTEN, and the entry rides
    the CALLER'S transaction. `_try_claim`'s rule is flush-the-outer-work-first
    so an inner failure cannot undo it; the sibling `post_payment` applies it by
    posting pre-commit, so the payment and its entry land together or not at
    all. Same here: the invoice is flushed (it has an id and its columns are
    durable in-transaction), then the entry is written, then
    `invoice.journal_entry_id` points at it. No commit — the caller owns the
    transaction.

    A NOTE ON THE DISPATCH'S WORDING, flagged rather than silently reinterpreted:
    INV-1 A-2 said "the JE writes AFTER the invoice commits." Posting after a
    commit would leave a window where the invoice is durable and the entry is
    not, with nothing recording that an attempt was owed — a WIDER orphan window
    than the one it set out to avoid. Writing both inside one transaction after
    a flush makes an orphan impossible in either direction, satisfies the cited
    `_try_claim` rule (which is pre-FLUSH, not pre-commit), and matches
    `post_payment`. If the intent really was post-commit, this is the line to
    change and the tests to revisit.

    ⚠️ THE FULL INVOICE TOTAL POSTS, tax included, because no tax leg exists
    yet. Measured on production 2026-08-19: `tax_amount` is 0.00 on every issued
    invoice on every tenant, so total == subtotal today and splitting a tax leg
    would be building against zero evidence. The moment a nonzero tax amount
    appears this becomes wrong — which is why a test pins the equality rather
    than leaving it as an assumption nobody stated.
    """
    from app.services.agents.period_lock import PeriodLockedError
    from app.services.journal_entry_service import JournalLineSpec, create_journal_entry

    ar, revenue, reason = resolve_invoice_legs(db, company_id)
    if reason is not None:
        return _refuse(db, company_id, invoice, reason)

    amount = Decimal(str(invoice.total or 0))
    if amount <= 0:
        # A zero-total invoice has nothing to book. Not a refusal — there is no
        # gap to report and nothing an operator could configure to fix it.
        logger.info(
            "INV-1: invoice %s has a non-positive total (%s) — nothing to post",
            invoice.id, amount,
        )
        return None

    # ⚠️ FLUSH FIRST. The entry is about to reference this invoice's id and the
    # invoice is about to reference the entry's; the subject has to be real in
    # the session before either link is made.
    db.flush()

    entry_date = invoice.invoice_date or datetime.now(timezone.utc)
    as_date = entry_date.date() if isinstance(entry_date, datetime) else entry_date

    def _line(mapping, **side) -> JournalLineSpec:
        return JournalLineSpec(
            gl_account_id=mapping.id,
            gl_account_number=mapping.account_number,
            gl_account_name=mapping.account_name,
            description=f"Invoice {invoice.number}",
            **side,
        )

    try:
        entry = create_journal_entry(
            db,
            tenant_id=company_id,
            entry_number=_next_entry_number(db, company_id),
            entry_type=_ENTRY_TYPE,
            entry_date=as_date,
            period_month=as_date.month,
            period_year=as_date.year,
            description=f"Invoice {invoice.number}",
            reference_number=invoice.number,
            created_by=user_id,
            lines=[
                # Dr AR — the debit that has never existed. Production's
                # `1200 ACCOUNTS RECEIVABLE-TRADE` reads Dr 0.00 / Cr 33,845.00
                # precisely because this line was missing while payments
                # credited the same account.
                _line(ar, debit_amount=amount),
                _line(revenue, credit_amount=amount),
            ],
        )
    except PeriodLockedError:
        # Fail-open on the RECORD. The invoice is issued; the books are shut.
        # Reported rather than raised, so issuance is not blocked by a period
        # the operator closed after the fact.
        return _refuse(db, company_id, invoice, BLOCK_PERIOD_LOCKED)

    # ⚠️ FLUSH THE LINES. `create_journal_entry` flushes the ENTRY (it needs the
    # id to attach lines to) and then `db.add()`s the lines WITHOUT flushing —
    # and `SessionLocal` is `autoflush=False` platform-wide
    # (`app/database.py:7`). So on return the entry exists in the session and
    # its lines do not, and anything that queries `journal_entry_lines` before
    # the caller's commit sees an entry with no legs.
    #
    # Found by a test asserting the two legs and getting zero rows. `post_payment`
    # has the same shape and its docstring's "Flushes" is true of the entry only.
    # Flushed here rather than in `create_journal_entry` because changing a
    # primitive three other callers depend on is a separate change with its own
    # blast radius — recorded, not folded in.
    db.flush()

    invoice.journal_entry_id = entry.id
    return entry


def _refuse(db: Session, company_id: str, invoice, reason: str):
    """Log, report, return None. The single exit for every refusal so a new
    block reason cannot be added with the reporting forgotten."""
    logger.warning(
        "INV-1: invoice %s issued but NOT posted (%s) — tenant=%s total=%s",
        invoice.id, reason, company_id, invoice.total,
    )
    report_unposted_invoice(db, company_id=company_id, invoice=invoice, reason=reason)
    return None


def report_unposted_invoice(db: Session, *, company_id: str, invoice, reason: str):
    """Surface an unposted invoice as operator-visible work.

    Fail-open is only safe if the gap is VISIBLE — otherwise it is just a
    silently incomplete ledger, which is the failure this arc exists to remove.
    Same container `report_unposted_payment` uses (`AgentJob` + one
    `AgentAnomaly`), for the same reason: it is the surface migrated agents
    already stage into, and triage is where the operator works.

    Best-effort by design: an invoice must issue even if REPORTING the gap
    fails. That is the one place in this path a broad catch is correct, and it
    is narrow — it wraps only the reporting, never the invoice.
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
                "pipeline": "ar_invoice_posting",
                "invoice_id": invoice.id,
                "invoice_number": invoice.number,
                "amount": str(invoice.total),
                "reason": reason,
            },
        )
        db.add(job)
        db.flush()
        db.add(AgentAnomaly(
            id=str(uuid.uuid4()), agent_job_id=job.id,
            severity=AnomalySeverity.WARNING.value,
            anomaly_type=_UNPOSTED_ANOMALY_TYPE,
            entity_type="invoice", entity_id=invoice.id,
            description=(
                f"Invoice {invoice.number} for ${invoice.total} was issued but "
                f"did not post to the ledger — {_BLOCK_FIX[reason]}. The invoice "
                "itself is correct and the customer's balance has moved; only "
                "the journal entry is missing. Configure the account and the "
                "entry can be written."
            ),
        ))
        db.flush()
    except Exception:
        logger.exception(
            "INV-1: could not report unposted invoice %s (tenant=%s) — the "
            "invoice stands; only the reporting failed",
            invoice.id, company_id,
        )
