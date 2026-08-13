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


def lock_span_for_month(month: int, year: int) -> tuple[date, date]:
    """The lock a Close click should write — the whole month, inclusive.

    The natural inverse of `project_month`: closing writes a span the projection
    reads back as `CLOSED`, so the round trip is lossless for the common case.
    """
    return month_bounds(month, year)
