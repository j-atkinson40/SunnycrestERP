"""GL-account resolution for reconciliation postings (Ledger Posting arc L-1).

Two resolvers + one shared validator. Every one resolves-at-use and fails by
returning ``None`` — never a guess, never a partial post:

  * ``resolve_keyword_gl_account`` — the per-tenant keyword→GL map for the
    ladder's classifications (``bank_fee`` / ``payroll`` / ``nsf``). Stored as a
    settings key on ``Company.settings`` (Option A, ratified 2026-08-04), the
    EPD precedent: a tenant's GL choice for a purpose lives in settings as a
    ``TenantGLMapping.id``, resolved + validated at use.
  * ``resolve_contra_gl_account`` — a bank account's own GL (cash) account
    (``FinancialAccount.gl_account_id``, FK'd to ``tenant_gl_mappings`` in r153).
    This is the offsetting leg of every reconciliation JE.
  * ``validate_gl_account`` — the shared gate: an id resolves ONLY to an ACTIVE
    ``TenantGLMapping`` owned by THIS tenant, else ``None``.

DISCIPLINE (the whole point of the Ledger Posting arc): a ``None`` from any
resolver means the caller MUST NOT book silently. The row is raised to an
exception (L-2 keyword auto-clear) or the accept is refused (L-3 coding) —
nothing clears unbooked. The three failure modes — unmapped (no settings entry),
dangling (id points at a deleted/inactive mapping), and foreign (id belongs to
another tenant) — all fail closed; they are logged distinctly because they call
for different operator actions (configure vs. re-map vs. investigate), but none
is ever a silent clear.

Settings shape::

    company.settings["reconciliation_keyword_gl"] = {
        "bank_fee": "<TenantGLMapping.id>",
        "payroll":  "<TenantGLMapping.id>",
        "nsf":      "<TenantGLMapping.id>",
    }

An absent map, an absent key, ``None``, or an id that fails validation each
resolve to ``None``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.financial_account import FinancialAccount
from app.models.journal_entry import JournalEntry
from app.services.agents.period_lock import PeriodLockService
from app.services.journal_entry_service import JournalLineSpec, create_journal_entry

logger = logging.getLogger(__name__)

# The settings key holding the keyword→GL map.
KEYWORD_GL_SETTINGS_KEY = "reconciliation_keyword_gl"

# The keyword ladder's classifications (reconciliation_service.py). Fixed in
# code — the settings map keys off these exact strings. The keyword vocabulary
# lives here, not in a table, precisely because it is code-fixed (that is why
# Option A over a table for three rows).
KEYWORD_CLASSIFICATIONS: tuple[str, ...] = ("bank_fee", "payroll", "nsf")

# Why a keyword row could not book (L-2). Persisted on the exception so the
# Books Review card can name the CONFIGURATION action rather than asking the
# operator to code a row the system already classified. All four fail closed;
# they differ only in who fixes what:
#   keyword_gl_unmapped  — no settings entry for this classification → configure the map
#   keyword_gl_dangling  — mapped, but the id no longer resolves    → re-map it
#   contra_gl_unset      — the bank account has no GL account        → set it on the account
#   contra_gl_dangling   — set, but the id no longer resolves        → re-map it
#   period_locked        — the accounting period is closed           → not a config problem
BLOCK_KEYWORD_GL_UNMAPPED = "keyword_gl_unmapped"
BLOCK_KEYWORD_GL_DANGLING = "keyword_gl_dangling"
BLOCK_CONTRA_GL_UNSET = "contra_gl_unset"
BLOCK_CONTRA_GL_DANGLING = "contra_gl_dangling"
BLOCK_PERIOD_LOCKED = "period_locked"

# Draft, never posted. L-2 books; a human posts. Nothing in this arc writes a
# `posted` journal entry — that is deliberate and is the reason `journal_entries`
# going non-zero is safe to ship.
RECON_ENTRY_TYPE = "reconciliation"
RECON_ENTRY_STATUS = "draft"


def validate_gl_account(
    db: Session, tenant_id: str, gl_account_id: str | None
) -> TenantGLMapping | None:
    """Return the ACTIVE ``TenantGLMapping`` for ``gl_account_id`` owned by
    ``tenant_id``, or ``None``. This is the single gate all resolution passes
    through — deleted, inactive, foreign-tenant, or empty all yield ``None``."""
    if not gl_account_id:
        return None
    return (
        db.query(TenantGLMapping)
        .filter(
            TenantGLMapping.id == gl_account_id,
            TenantGLMapping.tenant_id == tenant_id,
            TenantGLMapping.is_active.is_(True),
        )
        .first()
    )


def _keyword_gl_with_reason(
    db: Session, company: Company, classification: str
) -> tuple[str | None, str | None]:
    """``(gl_account_id, blocked_reason)`` — exactly one is non-``None``.

    The reason-carrying core of ``resolve_keyword_gl_account``. L-1 logged the
    unmapped/dangling distinction and threw it away; L-2 needs it as a VALUE,
    because the Books Review card must tell the operator which of the two
    configuration actions to take. The log lines are unchanged.
    """
    if classification not in KEYWORD_CLASSIFICATIONS:
        # A classification the map has no business answering for — treat as
        # unmapped rather than trusting an arbitrary settings key.
        return None, BLOCK_KEYWORD_GL_UNMAPPED
    mapping = (company.settings or {}).get(KEYWORD_GL_SETTINGS_KEY) or {}
    gl_id = mapping.get(classification)
    if not gl_id:
        logger.info(
            "recon keyword GL unmapped: tenant=%s classification=%s",
            company.id, classification,
        )
        return None, BLOCK_KEYWORD_GL_UNMAPPED
    validated = validate_gl_account(db, company.id, gl_id)
    if validated is None:
        logger.warning(
            "recon keyword GL DANGLING: tenant=%s classification=%s gl_id=%s "
            "(deleted/inactive/foreign mapping) — will exception, not clear",
            company.id, classification, gl_id,
        )
        return None, BLOCK_KEYWORD_GL_DANGLING
    return validated.id, None


def _contra_gl_with_reason(
    db: Session, financial_account: FinancialAccount
) -> tuple[str | None, str | None]:
    """``(gl_account_id, blocked_reason)`` — exactly one is non-``None``. The
    reason-carrying core of ``resolve_contra_gl_account``; see
    ``_keyword_gl_with_reason`` for why the distinction is now a value."""
    gl_id = financial_account.gl_account_id
    if not gl_id:
        logger.info(
            "recon contra GL unset: financial_account=%s tenant=%s",
            financial_account.id, financial_account.tenant_id,
        )
        return None, BLOCK_CONTRA_GL_UNSET
    validated = validate_gl_account(db, financial_account.tenant_id, gl_id)
    if validated is None:
        logger.warning(
            "recon contra GL DANGLING: financial_account=%s gl_id=%s "
            "(deleted/inactive/foreign mapping) — refusing booking",
            financial_account.id, gl_id,
        )
        return None, BLOCK_CONTRA_GL_DANGLING
    return validated.id, None


def resolve_keyword_gl_account(
    db: Session, company: Company, classification: str
) -> str | None:
    """The validated GL account id for a keyword ``classification``, or ``None``.

    ``None`` ⇒ the caller raises the row to an exception (never a silent clear).
    Distinguishes unmapped (no settings entry) from dangling (mapped but the id
    no longer resolves) in the log, because they need different operator action;
    both fail closed.
    """
    gl_id, _reason = _keyword_gl_with_reason(db, company, classification)
    return gl_id


def resolve_contra_gl_account(
    db: Session, financial_account: FinancialAccount
) -> str | None:
    """The validated GL (cash) account id for a bank account, or ``None``.

    ``None`` ⇒ the JE has no offsetting leg and MUST NOT be built — the caller
    refuses the booking (row → exception, or accept rejected), never a one-legged
    or silent post.
    """
    gl_id, _reason = _contra_gl_with_reason(db, financial_account)
    return gl_id


# ---------------------------------------------------------------------------
# L-2: the posting itself.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KeywordPosting:
    """Both legs of a keyword row's journal entry, resolved and validated.

    Its existence is the licence to clear the row. There is no partial value —
    a posting either has both legs or was never constructed.
    """

    classification: str
    keyword_gl_account_id: str
    contra_gl_account_id: str


def resolve_keyword_posting(
    db: Session,
    company: Company,
    financial_account: FinancialAccount,
    classification: str,
    entry_date: date,
) -> tuple[KeywordPosting | None, str | None]:
    """``(posting, blocked_reason)`` — exactly one is non-``None``.

    Resolves BOTH legs plus the period gate before anything is written. The
    caller books when it gets a posting and raises the row to an exception
    carrying ``blocked_reason`` when it does not. Order of checks is the order
    of the operator's likely fix: the keyword leg (the map they configure), then
    the contra leg (the bank account they configure), then the period (a policy
    gate, not a configuration problem).
    """
    keyword_gl, reason = _keyword_gl_with_reason(db, company, classification)
    if keyword_gl is None:
        return None, reason

    contra_gl, reason = _contra_gl_with_reason(db, financial_account)
    if contra_gl is None:
        return None, reason

    # Period lock is checked HERE rather than left to create_journal_entry's
    # raise, so a closed period produces the same fail-closed exception row as a
    # missing mapping instead of an exception escaping the matcher mid-run. This
    # mirrors the payment auto-commit path, which has always gated on the lock
    # before clearing.
    lock = PeriodLockService.check_date_in_locked_period(db, company.id, entry_date)
    if lock is not None:
        logger.info(
            "recon keyword posting blocked by period lock: tenant=%s "
            "classification=%s date=%s",
            company.id, classification, entry_date,
        )
        return None, BLOCK_PERIOD_LOCKED

    return KeywordPosting(
        classification=classification,
        keyword_gl_account_id=keyword_gl,
        contra_gl_account_id=contra_gl,
    ), None


def book_keyword_entry(
    db: Session,
    *,
    company_id: str,
    posting: KeywordPosting,
    amount,
    entry_date: date,
    description: str,
    reference_number: str | None = None,
) -> JournalEntry:
    """Book the two-legged DRAFT journal entry for a keyword row. Flushes; does
    NOT commit (the caller owns the transaction).

    DIRECTION follows the transaction's SIGN, which is the bank's point of view:
    a negative amount is money leaving the account. So a -15.00 bank fee credits
    cash 15.00 and debits the bank-fee account 15.00; a positive amount (a fee
    refund, an NSF credit-back) reverses both legs. Magnitudes are always the
    absolute value — a journal line never carries a negative amount, it carries
    a side. The entry is balanced by construction: one debit, one credit, one
    magnitude.
    """
    amount_dec = Decimal(str(amount))
    magnitude = abs(amount_dec)

    if amount_dec < 0:
        # Money out: the expense/liability side takes the debit, cash the credit.
        lines = [
            JournalLineSpec(
                gl_account_id=posting.keyword_gl_account_id,
                debit_amount=magnitude,
                description=description,
            ),
            JournalLineSpec(
                gl_account_id=posting.contra_gl_account_id,
                credit_amount=magnitude,
                description=description,
            ),
        ]
    else:
        # Money in: cash takes the debit, the keyword account the credit.
        lines = [
            JournalLineSpec(
                gl_account_id=posting.contra_gl_account_id,
                debit_amount=magnitude,
                description=description,
            ),
            JournalLineSpec(
                gl_account_id=posting.keyword_gl_account_id,
                credit_amount=magnitude,
                description=description,
            ),
        ]

    # Own numbering scheme, per journal_entry_service's stated discipline that
    # callers keep their own (`JE-` for manual, `DISC-` for EPD). `RECON-` makes
    # a reconciliation-born entry legible in the register at a glance.
    count = db.query(JournalEntry).filter(JournalEntry.tenant_id == company_id).count()

    return create_journal_entry(
        db,
        tenant_id=company_id,
        entry_number=f"RECON-{count + 1001}",
        entry_type=RECON_ENTRY_TYPE,
        status=RECON_ENTRY_STATUS,
        entry_date=entry_date,
        period_month=entry_date.month,
        period_year=entry_date.year,
        description=description,
        reference_number=reference_number,
        lines=lines,
    )
