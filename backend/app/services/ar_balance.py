"""AR membership — one definition of "is this a live receivable document".

THE SEAM (AR-1 C-3). Balance, aging, statements, collections, the dashboards
and the nightly drift sweeper all need the same two answers:

    WHICH invoices are receivable   ← this module
    HOW MUCH each one owes          ← Invoice.balance_remaining (a hybrid)

Before this they each answered both, differently. Five distinct status filters
were in use across the codebase:

    ("sent", "partial", "overdue")                     aging, statements, ...
    ("sent", "overdue", "partial")                     same set, reordered
    ("sent", "open", "partial", "overdue")             the financials board
    ("sent", "partial", "overdue", "open")             briefings
    NOT IN ("paid","void","draft","write_off")         the drift sweeper

An invoice at `open` was counted by the board and by the sweeper and was
INVISIBLE TO AGING. An invoice at `posted` — every finance charge — was
invisible to all of them except the sweeper. Both statuses are written by
production code paths (`draft_invoice_service.py:651,706` and
`finance_charge_service.py:384`).

WHY AN EXCLUSION AND NOT AN INCLUSION. An inclusion list is exactly how `open`
and `posted` dropped out: each was added to the platform later, and no one
revisited five separate tuples. An exclusion list fails the other way — a new
status is receivable until someone says otherwise, which is the safe direction
for money. `open` and `posted` would both have been correct from the day they
were introduced.

WHY ONLY TWO ENTRIES. Because the VALUE expression carries the rest, and this
is the part worth not eroding:

    draft       excluded — not issued; the balance moves at draft→issued
    void        excluded — reversed (sales_service.py:1023)
    paid        included, contributes 0.00 (total − paid is zero by definition)
    write_off   included, contributes 0.00 (− written_off_amount zeroes it)
    everything else — sent / open / partial / overdue / posted — receivable

A PARTIALLY written-off invoice keeps its ordinary status, so no status filter
can correct it; only the four-term value expression can. If a future number
looks wrong, the fix is almost certainly in the terms, NOT in adding a status
here. Reaching for this list to fix an amount is how the drift starts again.
"""
from __future__ import annotations

from app.models.invoice import Invoice

# Not receivable documents. See the module docstring before adding to this.
RECEIVABLE_EXCLUDED_STATUSES: tuple[str, ...] = ("draft", "void")


def is_receivable():
    """The membership clause, for `.filter(...)`.

    Composable rather than a query-builder because the callers scope
    differently — by company, by customer, joined to Customer, grouped, or with
    an extra date predicate. What they must share is WHICH rows count, not how
    they are reached.
    """
    return Invoice.status.notin_(RECEIVABLE_EXCLUDED_STATUSES)
