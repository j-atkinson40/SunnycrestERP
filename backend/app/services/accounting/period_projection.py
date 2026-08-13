"""A month's close status, projected from `period_locks`. CR-1 prerequisite.

⚠️ THE CONTROL THAT REPORTED SUCCESS AND ONLY HALF-CONTROLLED.
Two substrates modelled period closure and did not know about each other:

    period_locks         date RANGES. Written by month-end close. Honoured by
                         every AR write path — invoices, payments, statements.
    accounting_periods   month/year rows with a `status`. Written by the
                         operator-facing Accounting Periods tab. Honoured by
                         exactly ONE path: the journal-entry post.

So clicking Close stopped journal entries and did nothing to the money. An
operator would see JE posting refuse and reasonably conclude the close worked.
**A partially-working control is harder to notice than a broken one.**

THE FIX IS A PROJECTION, NOT A RE-POINT. `accounting_periods` is not vestigial —
it has a live tab with a list view. Re-pointing only the button would leave that
tab reading a status nothing writes. So the READER survives and the SOURCE moves:
`period_locks` is authoritative, and the month/year view is derived from it.

⚠️ THREE STATES, NOT TWO — and the third is the honest one.
The tab's period is a MONTH; "8/2026 is closed" is a claim about every day in it.
A lock covering 1–15 August makes that claim false — but rendering the month OPEN
is equally false, because writes to the first half will be refused. Both binary
answers mislead someone about what happens when they try to post.

Same shape as `deliberately unmapped` and MAP-5's `runs_dry`: the honest state is
the one that refuses to collapse into a neighbour.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date

#: Every day in the month is covered by some lock.
CLOSED = "closed"
#: Some days are covered. Neither "closed" nor "open" is true of the month.
PARTIALLY_CLOSED = "partially_closed"
#: No day is covered.
OPEN = "open"

PERIOD_STATES = (CLOSED, PARTIALLY_CLOSED, OPEN)


def active_locks(db, tenant_id: str) -> list:
    """Every live lock for the tenant. The ONLY read both period UIs may use.

    ⚠️ ONE DEFINITION ON PURPOSE. `is_active` is the same flag
    `PeriodLockService.check_date_in_locked_period` filters on. Two period
    surfaces exist (`/journal-entries/periods` and `/vault/accounting/periods`)
    and they got out of step once already — that is the whole defect. A copy of
    this filter per route is how they drift apart again.
    """
    from app.models.period_lock import PeriodLock

    return (
        db.query(PeriodLock)
        .filter(PeriodLock.tenant_id == tenant_id, PeriodLock.is_active == True)  # noqa: E712
        .all()
    )


def month_bounds(month: int, year: int) -> tuple[date, date]:
    """First and last day of the month, inclusive.

    `monthrange` rather than arithmetic: a hand-rolled last-day is where February
    and leap years go wrong, and this feeds a claim about whether money can move.
    """
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def project_month(
    locks: list[tuple[date, date]], *, month: int, year: int
) -> str:
    """Derive one month's status from date-range locks. Pure.

    `locks` is `(period_start, period_end)` pairs, inclusive at both ends, in any
    order and possibly overlapping — the union is what matters, not the pieces.

    Day-by-day rather than interval arithmetic: a month is at most 31 days, and
    interval merging is where off-by-one errors live. The cost is irrelevant and
    the correctness is obvious by inspection, which matters more for a function
    whose answer decides whether an operator is told they can post.
    """
    first, last = month_bounds(month, year)
    total = (last - first).days + 1
    covered = sum(
        1
        for i in range(total)
        if any(s <= (d := date.fromordinal(first.toordinal() + i)) <= e for s, e in locks)
    )
    if covered == 0:
        return OPEN
    if covered == total:
        return CLOSED
    return PARTIALLY_CLOSED


def covered_ranges(
    locks: list[tuple[date, date]], *, month: int, year: int
) -> list[tuple[date, date]]:
    """The locked spans within the month, merged and clipped to it.

    ⚠️ THIS IS WHAT MAKES THE THIRD STATE USABLE. "Partially closed" tells an
    operator nothing about whether their invoice will post; "closed 1–15 August"
    predicts the behaviour. A state name that can't be acted on is only a
    slightly better lie than the binary it replaced.

    Merged, because two adjacent locks are one span to a reader. Clipped, because
    a lock running into September is not a fact about August.
    """
    first, last = month_bounds(month, year)
    out: list[tuple[date, date]] = []
    for i in range((last - first).days + 1):
        day = date.fromordinal(first.toordinal() + i)
        if not any(s <= day <= e for s, e in locks):
            continue
        # Extend the open span if this day continues it, else start a new one.
        if out and (day - out[-1][1]).days == 1:
            out[-1] = (out[-1][0], day)
        else:
            out.append((day, day))
    return out


def lock_span_for_month(month: int, year: int) -> tuple[date, date]:
    """The lock a Close click should write — the whole month, inclusive.

    The natural inverse of `project_month`: closing writes a span the projection
    reads back as `CLOSED`, so the round trip is lossless for the common case.
    """
    return month_bounds(month, year)
