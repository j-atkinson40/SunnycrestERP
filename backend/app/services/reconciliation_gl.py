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
        "bank_fee": "<TenantGLMapping.id>",   # mapped
        "payroll":  None,                      # DELIBERATELY unmapped
        # "nsf" absent                         # never configured
    }

THREE states, not two. Every non-mapped state still resolves to ``None`` and
still fails closed — the distinction is entirely in the REASON, because the
reason is what the operator reads:

  * an id            → mapped; validated at use, dangling if it no longer resolves
  * key present, null→ the operator decided this one does not post automatically
  * key absent       → nobody has decided yet

The middle state exists because the shape does not fit every classification. A
net payroll ACH draw is gross wages plus employer taxes across several
departments, and an NSF reverses against AR — neither is one GL account, so
"unmapped" is the correct answer rather than an unfinished one. A settings UI
that only offered "pick an account" would manufacture wrong answers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
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
# operator to code a row the system already classified. All SIX fail closed;
# they differ in who fixes what — and one of them is not a fix at all:
#   keyword_gl_unmapped   — no settings entry for this classification → configure the map
#   keyword_gl_intentional— mapped to null ON PURPOSE               → NOTHING TO FIX
#   keyword_gl_dangling   — mapped, but the id no longer resolves    → re-map it
#   contra_gl_unset       — the bank account has no GL account       → set it on the account
#   contra_gl_dangling    — set, but the id no longer resolves       → re-map it
#   period_locked         — the accounting period is closed          → not a config problem
#
# keyword_gl_intentional is the odd one and the copy must carry that. The
# production chart pull (STATE, 2026-08-04) found NO correct single account for
# payroll (a net ACH draw is gross wages plus employer taxes across departments)
# or for nsf (a bounced check reverses against AR, not an expense). Unmapped is
# the RIGHT answer for those, so the card says these don't post automatically and
# this one needs a person — never that something is missing. Telling an operator
# to fix what they deliberately chose is worse than saying nothing.
BLOCK_KEYWORD_GL_UNMAPPED = "keyword_gl_unmapped"
BLOCK_KEYWORD_GL_INTENTIONAL = "keyword_gl_intentional"
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


def require_gl_account(
    db: Session, tenant_id: str, gl_account_id: str | None
) -> TenantGLMapping:
    """``validate_gl_account`` with a legible 400 instead of a ``None``.

    THE ONE RAISER, so every write boundary that accepts a GL account agrees on
    what "usable" means AND says the same thing when it is not. L-2.1b added
    this check to the reconciliation account routes; L-2.2 routes the journal-
    entry route through it too — before that, `create_entry` filtered
    `tenant_id` but not `is_active`, so a soft-deleted mapping was writable on
    one path and refused on the other. Two definitions differing by one
    predicate is exactly the drift a shared function exists to prevent.

    Returns the mapping so the caller can denormalize from it (JE lines carry
    account number + name; see `JournalLineSpec`).

    THE MESSAGE NAMES INACTIVE but deliberately does NOT distinguish
    foreign-tenant from nonexistent. Inactive is the operator's own data and the
    fix is theirs; saying "that belongs to another tenant" would make any
    endpoint carrying this check a cross-tenant existence oracle. The two read
    identically, and tests on both routes assert byte-identity.
    """
    mapping = validate_gl_account(db, tenant_id, gl_account_id)
    if mapping is not None:
        return mapping
    same_tenant = (
        db.query(TenantGLMapping)
        .filter(
            TenantGLMapping.id == gl_account_id,
            TenantGLMapping.tenant_id == tenant_id,
        )
        .first()
    )
    if same_tenant is not None:
        raise HTTPException(
            400,
            f"GL account {same_tenant.account_number} ({same_tenant.account_name}) "
            "is inactive — reactivate it, or choose another.",
        )
    raise HTTPException(400, "That GL account is not in your chart of accounts.")


def keyword_gl_with_reason(
    db: Session, company: Company, classification: str
) -> tuple[TenantGLMapping | None, str | None]:
    """``(mapping, blocked_reason)`` — exactly one is non-``None``.

    The reason-carrying core of ``resolve_keyword_gl_account``. L-1 logged the
    unmapped/dangling distinction and threw it away; L-2 needs it as a VALUE,
    because the Books Review card must tell the operator which of the two
    configuration actions to take. The log lines are unchanged.

    PUBLIC as of L-2.1c because it now has consumers beyond the posting path —
    anything that reports config state (the configure script, and the settings
    panel's GET) must derive it HERE rather than re-deriving it, or two
    descriptions of the same settings dict drift apart. The script did drift:
    its report read a deliberate null as UNMAPPED.

    Returns the whole validated ``TenantGLMapping`` rather than its id because
    ``JournalLineSpec`` requires the caller to denormalize account number + name
    onto each line (that module does no lookups). ``validate_gl_account`` has
    already loaded the row, so carrying it costs nothing and passing only the id
    would force a second query — or, as it did before this was caught, produce
    lines with blank account columns.
    """
    if classification not in KEYWORD_CLASSIFICATIONS:
        # A classification the map has no business answering for — treat as
        # unmapped rather than trusting an arbitrary settings key.
        return None, BLOCK_KEYWORD_GL_UNMAPPED
    mapping = (company.settings or {}).get(KEYWORD_GL_SETTINGS_KEY) or {}
    # THREE settings states, and the order of these two checks is load-bearing.
    # `null` is FALSY, so the `if not gl_id` below would swallow a deliberate
    # unmapping and report it as a gap the operator still has to close. Key
    # PRESENT and null means they already decided; key ABSENT means they have
    # not. (Ledger Posting L-2.1c.)
    if classification in mapping and mapping[classification] is None:
        logger.info(
            "recon keyword GL deliberately unmapped: tenant=%s classification=%s",
            company.id, classification,
        )
        return None, BLOCK_KEYWORD_GL_INTENTIONAL
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
    return validated, None


def contra_gl_with_reason(
    db: Session, financial_account: FinancialAccount
) -> tuple[TenantGLMapping | None, str | None]:
    """``(mapping, blocked_reason)`` — exactly one is non-``None``. The
    reason-carrying core of ``resolve_contra_gl_account``; see
    ``keyword_gl_with_reason`` for why the distinction is now a value, and why
    the mapping travels rather than the id alone."""
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
    return validated, None


def resolve_keyword_gl_account(
    db: Session, company: Company, classification: str
) -> str | None:
    """The validated GL account id for a keyword ``classification``, or ``None``.

    ``None`` ⇒ the caller raises the row to an exception (never a silent clear).
    Distinguishes unmapped (no settings entry) from dangling (mapped but the id
    no longer resolves) in the log, because they need different operator action;
    both fail closed.
    """
    mapping, _reason = keyword_gl_with_reason(db, company, classification)
    return mapping.id if mapping is not None else None


def resolve_contra_gl_account(
    db: Session, financial_account: FinancialAccount
) -> str | None:
    """The validated GL (cash) account id for a bank account, or ``None``.

    ``None`` ⇒ the JE has no offsetting leg and MUST NOT be built — the caller
    refuses the booking (row → exception, or accept rejected), never a one-legged
    or silent post.
    """
    mapping, _reason = contra_gl_with_reason(db, financial_account)
    return mapping.id if mapping is not None else None


# ---------------------------------------------------------------------------
# L-2: the posting itself.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KeywordPosting:
    """Both legs of a keyword row's journal entry, resolved and validated.

    Its existence is the licence to clear the row. There is no partial value —
    a posting either has both legs or was never constructed.

    Each leg carries the GL account's number + name alongside its id because
    ``JournalLineSpec`` requires the caller to denormalize them onto the line
    (``journal_entry_service`` does no lookups). Those columns are what
    ``/journal-entries`` renders and what the year-end-close and estimated-tax
    agents match on; omitting them produces an entry that is arithmetically
    correct and humanly unreadable.
    """

    classification: str
    keyword_gl_account_id: str
    keyword_gl_account_number: str | None
    keyword_gl_account_name: str | None
    contra_gl_account_id: str
    contra_gl_account_number: str | None
    contra_gl_account_name: str | None


@dataclass(frozen=True)
class KeywordPostingContext:
    """Every input resolution needs, fetched once, for a set of bank accounts.

    THE ONE RESOLVER, and the reason it is a context object rather than a
    function with a batch flag. Two callers ask the same question in different
    shapes: the matcher asks per row while writing, the Books Review builder asks
    for a page of rows while reading. A single function that switched behavior on
    a `batch=` argument would be two implementations wearing one name — and if
    the two ever ordered their checks differently, the card would name a
    different reason than the matcher would have, which is precisely the class of
    divergence the membership seam and `_count_config` exist to prevent.

    So the SHAPE that differs (how many rows, when the inputs are fetched) lives
    in construction, and the DECISION lives in ``decide``, which touches no
    database at all. Both callers run identical logic because there is only one.
    """

    company_id: str
    # classification → (mapping, blocked_reason); exactly one is non-None.
    keyword_legs: dict[str, tuple[TenantGLMapping | None, str | None]]
    # financial_account_id → (mapping, blocked_reason); same invariant.
    contra_legs: dict[str, tuple[TenantGLMapping | None, str | None]]
    # Active locked periods as (start, end) inclusive. Tested in memory — a
    # per-row `check_date_in_locked_period` would be one query per row, which is
    # affordable in the matcher's write path and is NOT affordable in a queue
    # builder that renders a page at a time.
    locked_periods: tuple[tuple[date, date], ...]

    def is_locked(self, entry_date: date) -> bool:
        return any(s <= entry_date <= e for (s, e) in self.locked_periods)

    def decide(
        self, *, classification: str, financial_account_id: str, entry_date: date
    ) -> tuple[KeywordPosting | None, str | None]:
        """``(posting, blocked_reason)`` — exactly one is non-``None``. Pure.

        Order of checks is the order of the operator's likely fix: the keyword leg
        (the map they configure), then the contra leg (the bank account they
        configure), then the period (a policy gate, not a configuration problem).
        Changing this order changes which reason a blocked row reports, so it is
        part of the contract, not an implementation detail.
        """
        keyword_gl, reason = self.keyword_legs.get(
            classification, (None, BLOCK_KEYWORD_GL_UNMAPPED)
        )
        if keyword_gl is None:
            return None, reason

        contra_gl, reason = self.contra_legs.get(
            financial_account_id, (None, BLOCK_CONTRA_GL_UNSET)
        )
        if contra_gl is None:
            return None, reason

        # Checked HERE rather than left to create_journal_entry's raise, so a
        # closed period produces the same fail-closed exception row as a missing
        # mapping instead of an exception escaping the matcher mid-run.
        if self.is_locked(entry_date):
            logger.info(
                "recon keyword posting blocked by period lock: tenant=%s "
                "classification=%s date=%s",
                self.company_id, classification, entry_date,
            )
            return None, BLOCK_PERIOD_LOCKED

        return KeywordPosting(
            classification=classification,
            keyword_gl_account_id=keyword_gl.id,
            keyword_gl_account_number=keyword_gl.account_number,
            keyword_gl_account_name=keyword_gl.account_name,
            contra_gl_account_id=contra_gl.id,
            contra_gl_account_number=contra_gl.account_number,
            contra_gl_account_name=contra_gl.account_name,
        ), None


def build_keyword_posting_context(
    db: Session, company: Company, financial_accounts: list[FinancialAccount]
) -> KeywordPostingContext:
    """Resolve every input once, for however many accounts the caller has.

    Three queries regardless of row count: the keyword legs' mappings, the contra
    legs' mappings, and the tenant's active period locks. `keyword_gl_with_reason`
    and `contra_gl_with_reason` are reused per DISTINCT leg (at most three
    classifications, at most five bank accounts), not per row — so the cost is
    bounded by configuration, not by how many transactions are on screen.
    """
    from app.models.period_lock import PeriodLock

    keyword_legs = {
        c: keyword_gl_with_reason(db, company, c) for c in KEYWORD_CLASSIFICATIONS
    }
    contra_legs = {
        fa.id: contra_gl_with_reason(db, fa) for fa in financial_accounts
    }
    locks = (
        db.query(PeriodLock)
        .filter(PeriodLock.tenant_id == company.id, PeriodLock.is_active == True)  # noqa: E712
        .all()
    )
    return KeywordPostingContext(
        company_id=company.id,
        keyword_legs=keyword_legs,
        contra_legs=contra_legs,
        locked_periods=tuple((l.period_start, l.period_end) for l in locks),
    )


def resolve_keyword_posting(
    db: Session,
    company: Company,
    financial_account: FinancialAccount,
    classification: str,
    entry_date: date,
) -> tuple[KeywordPosting | None, str | None]:
    """One row's worth of ``KeywordPostingContext.decide``, context included.

    Kept because callers that resolve a single row read better this way. It is a
    WRAPPER, not a second implementation — build a context for the one account,
    then decide. A caller in a loop should build the context itself and call
    ``decide`` per row instead; the matcher does.
    """
    ctx = build_keyword_posting_context(db, company, [financial_account])
    return ctx.decide(
        classification=classification,
        financial_account_id=financial_account.id,
        entry_date=entry_date,
    )


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

    def _keyword_leg(**side) -> JournalLineSpec:
        return JournalLineSpec(
            gl_account_id=posting.keyword_gl_account_id,
            gl_account_number=posting.keyword_gl_account_number,
            gl_account_name=posting.keyword_gl_account_name,
            description=description,
            **side,
        )

    def _contra_leg(**side) -> JournalLineSpec:
        return JournalLineSpec(
            gl_account_id=posting.contra_gl_account_id,
            gl_account_number=posting.contra_gl_account_number,
            gl_account_name=posting.contra_gl_account_name,
            description=description,
            **side,
        )

    if amount_dec < 0:
        # Money out: the expense/liability side takes the debit, cash the credit.
        lines = [
            _keyword_leg(debit_amount=magnitude),
            _contra_leg(credit_amount=magnitude),
        ]
    else:
        # Money in: cash takes the debit, the keyword account the credit.
        lines = [
            _contra_leg(debit_amount=magnitude),
            _keyword_leg(credit_amount=magnitude),
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
