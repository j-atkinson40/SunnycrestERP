"""Journal-entry creation — the single persistence primitive.

S-2 extraction. Three sites construct JournalEntry + JournalEntryLine rows
today: the `journal_entries` route's `create_entry` + `reverse_entry`, and
the inline JE in `early_payment_discount_service`. This module is the ONE
place that does the construction, so future guards (S-3's period lock)
land here once and cover every path.

DELIBERATELY a persistence primitive, NOT a unifier. The three callers
keep their divergent behaviors — different entry-number schemes
(`JE-####` vs `DISC-`), different statuses (draft vs posted), different
period derivations (entry_date vs today vs payment_date). Those
divergences may encode a real document-type distinction and this
extraction has no standing to collapse them. The caller computes
entry_number, status, period, and fully-resolved line specs; this module
constructs the rows, sets the totals FROM the lines (which reproduces all
three callers' current totals bit-for-bit), flushes, and returns the
entry. It does NOT commit — the caller owns the transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.services.agents.period_lock import PeriodLockService, PeriodLockedError


@dataclass
class JournalLineSpec:
    """A fully-resolved journal line. The caller is responsible for any
    GL-account resolution / denormalization (e.g. create_entry's
    tenant-scoped lookup) before handing specs here — this module does no
    lookups."""

    gl_account_id: str
    debit_amount: Decimal | float | str = 0
    credit_amount: Decimal | float | str = 0
    gl_account_number: str | None = None
    gl_account_name: str | None = None
    description: str | None = None


def create_journal_entry(
    db: Session,
    *,
    tenant_id: str,
    entry_number: str,
    entry_type: str,
    entry_date: date,
    period_month: int,
    period_year: int,
    description: str,
    lines: list[JournalLineSpec],
    status: str | None = None,
    reference_number: str | None = None,
    created_by: str | None = None,
    posted_by: str | None = None,
    posted_at: datetime | None = None,
    is_reversal: bool = False,
    reversal_of_entry_id: str | None = None,
    reversal_scheduled: bool = False,
    reversal_date: date | None = None,
    entry_id: str | None = None,
) -> JournalEntry:
    """Construct + persist a JournalEntry and its lines. Flushes; does NOT
    commit. Totals are computed from `lines` (matches every current
    caller). `status` is applied only when provided so the model's
    server_default ("draft") governs the create path exactly as before;
    `entry_id` is applied only when provided so the model's default UUID
    governs otherwise.
    """
    # S-3 period-lock guard. PeriodLock is the authoritative closed-period
    # source across the platform (month-end close writes it on approval;
    # every AR write — invoices, payments — already honors it). Guarding in
    # this ONE primitive covers all three JE-creation callers at once
    # (manual create_entry, reverse_entry, EPD discount). It reads
    # entry_date: reversal carries `today` (open), and EPD carries the
    # payment's date (already lock-checked at payment creation), so in the
    # normal flow only a manual create into a locked period is actually
    # blocked. Fail-closed (409). `datetime` is a subclass of `date`, so a
    # datetime entry_date (EPD passes payment_date) is narrowed to a date.
    lock_date = entry_date.date() if isinstance(entry_date, datetime) else entry_date
    lock = PeriodLockService.check_date_in_locked_period(db, tenant_id, lock_date)
    if lock:
        raise PeriodLockedError(lock)

    # sum(...) over the specs mirrors the route's original computation,
    # including the empty-lines edge (int 0, coerced by the Numeric column).
    total_debits = sum(Decimal(str(line.debit_amount)) for line in lines)
    total_credits = sum(Decimal(str(line.credit_amount)) for line in lines)

    # AR-0c GUARDS. Both land HERE rather than at `post_entry` because a bad
    # entry should never exist, not merely never post — L-2/L-3 drafts are the
    # books' record of a cleared row and are read long before anyone posts them.
    #
    # The service computed both totals and never compared them (S-2 pinned this
    # as `test_permits_unbalanced_draft`, and the S-2 header listed it among the
    # things "almost certainly WRONG" that the extraction deliberately did not
    # fix). `post_entry` catches it at posting time; nothing caught it at rest.
    if total_debits != total_credits:
        raise HTTPException(
            400,
            f"Entry is not balanced. Debits: ${total_debits}, "
            f"Credits: ${total_credits}",
        )

    # A two-legged entry whose legs are the SAME account is meaningless
    # whatever produced it — debit 10 and credit 10 on one account nets to
    # nothing while passing every balance check. This is the shape the EPD
    # AR-account fallback produced (`ar_account_id or gl_account_id`), and the
    # reason it survived is that a balanced nothing looks exactly like a
    # balanced something. Single-line entries are untouched: S-2 pinned those
    # as creatable (`test_permits_fewer_than_two_lines`) and the >=2-line rule
    # lives in `post_entry`.
    if len(lines) >= 2 and len({line.gl_account_id for line in lines}) == 1:
        raise HTTPException(
            400,
            "Every line of this entry is on the same GL account, so it records "
            "nothing. Check the account configuration behind it.",
        )

    kwargs = dict(
        tenant_id=tenant_id,
        entry_number=entry_number,
        entry_type=entry_type,
        entry_date=entry_date,
        period_month=period_month,
        period_year=period_year,
        description=description,
        reference_number=reference_number,
        total_debits=total_debits,
        total_credits=total_credits,
        created_by=created_by,
        posted_by=posted_by,
        posted_at=posted_at,
        is_reversal=is_reversal,
        reversal_of_entry_id=reversal_of_entry_id,
        reversal_scheduled=reversal_scheduled,
        reversal_date=reversal_date,
    )
    if status is not None:
        kwargs["status"] = status
    if entry_id is not None:
        kwargs["id"] = entry_id

    entry = JournalEntry(**kwargs)
    db.add(entry)
    db.flush()

    for i, line in enumerate(lines):
        db.add(JournalEntryLine(
            tenant_id=tenant_id,
            journal_entry_id=entry.id,
            line_number=i + 1,
            gl_account_id=line.gl_account_id,
            gl_account_number=line.gl_account_number,
            gl_account_name=line.gl_account_name,
            description=line.description,
            debit_amount=Decimal(str(line.debit_amount)),
            credit_amount=Decimal(str(line.credit_amount)),
        ))

    return entry
