"""Which sales-order status transitions are allowed.

James's ruling, 2026-10-16 (step 2, item 4): an explicit allowed set. A PATCH that skips
or reverses a step is rejected. `draft -> delivered` must fail.

⚠️ BEFORE THIS THERE WAS NO STATE MACHINE AT ALL. `SalesOrderUpdate.status` is an
unconstrained `str` (`app/schemas/sales.py:147`) and `update_sales_order` assigned
whatever arrived (`sales_service.py:640-642`). The only refusal was on the STARTING state
— `completed` and cancelled orders could not be modified. So `PATCH {"status":
"delivered"}` on a draft was accepted, which skipped `confirmed` entirely and dropped the
order straight into the end-of-day batch's net with `delivered_at` still NULL. The
draft→confirmed→delivered sequence existed only as the order of buttons in
`frontend/src/pages/sales-order-detail.tsx:193-236`.

⚠️ THE GRAPH IS WIDER THAN JAMES'S FOUR, AND THE DEVIATION IS DELIBERATE — flagged
rather than taken silently. The dispatch names `draft -> confirmed -> delivered ->
invoiced, plus cancel`. Two things make a literal reading unshippable:

  * **`processing` and `shipped` are real and reachable from the UI.** The order detail
    page ships "Move to Production" (`confirmed -> processing`) and a `processing ->
    delivered` button. A four-status allow-list would reject both and break buttons that
    work today.
  * **`invoiced` IS NOT A SALES-ORDER STATUS AND IS NOT INVENTED HERE.** Invoicing is an
    `invoices` row with its own lifecycle; the order's own terminal states are
    `delivered` and `completed`. Adding an `invoiced` status would create a second,
    disagreeing answer to "is this invoiced?" — the first being `invoices.sales_order_id`,
    which is what every consumer already reads and what the one-invoice-per-order guard
    enforces (`sales_service.py:744-762`).

So the spine James named is enforced exactly — `draft -> confirmed` and nothing skipping
it, `delivered` unreachable from `draft`, cancel available throughout, no reversals — and
the two intermediate statuses the product already uses are permitted on the path.

⚠️ EVERY STATUS IN PRODUCTION USE IS COVERED. Measured 2026-10-16, unbounded across all
tenants: `confirmed` 24, `delivered` 7, `completed` 4, `draft` 3. No CHECK constraint on
the column. The other statuses named below (`processing`, `shipped`, `spring_burial`) have
zero rows today but live code paths, so they are in the graph rather than discovered by an
outage later.
"""

from __future__ import annotations

from app.models.sales_order import CANCEL_SPELLINGS, STATUS_CANCELLED

#: Terminal states — nothing leaves them.
#:
#: ⚠️ `completed` BEING TERMINAL IS PRE-EXISTING BEHAVIOUR, not a new rule:
#: `update_sales_order` already refused to modify a `completed` or cancelled order
#: (`sales_service.py:626-630`). This records it in the graph so there is one place to
#: read the lifecycle rather than two half-statements.
TERMINAL = frozenset({"completed", *CANCEL_SPELLINGS})

#: The spine, plus the intermediates the product already uses.
#:
#: ⚠️ READ THE ABSENCES. `draft` does NOT reach `delivered`; nothing reaches `draft`
#: (no un-confirming — see `REOPEN_IS_NOT_A_TRANSITION` below); `delivered` does not
#: reach `shipped` (no reversals).
ALLOWED: dict[str, frozenset[str]] = {
    # The order is not real yet. Confirming is the assertion that it is.
    "draft": frozenset({"confirmed", STATUS_CANCELLED, "spring_burial"}),
    # Real and scheduled. `delivered` is reachable directly because a small shop does
    # not run a production stage for every order.
    "confirmed": frozenset(
        {"processing", "shipped", "delivered", STATUS_CANCELLED, "spring_burial"}
    ),
    "processing": frozenset({"shipped", "delivered", STATUS_CANCELLED}),
    "shipped": frozenset({"delivered", STATUS_CANCELLED}),
    # Delivered is where the end-of-day batch leaves an order. `completed` is set by
    # full payment or by hand.
    "delivered": frozenset({"completed", STATUS_CANCELLED}),
    # ⚠️ SPRING BURIAL IS A HOLD, NOT A STEP. A winter order is parked here and comes
    # back to `confirmed` when it is scheduled in the spring
    # (`spring_burial_service.py:173`, `:224`). It is the one place the graph goes
    # "backwards" by wall-clock order, and it is a real workflow rather than a reversal.
    "spring_burial": frozenset({"confirmed", STATUS_CANCELLED}),
    "completed": frozenset(),
    STATUS_CANCELLED: frozenset(),
}

#: Recorded so the absence is a decision rather than an oversight: there is no
#: `confirmed -> draft`. Un-confirming an order that the batch may already have acted on
#: would mean reversing a delivery and an invoice, and nothing in the system knows how to
#: do that. An order confirmed in error is cancelled, not demoted.
REOPEN_IS_NOT_A_TRANSITION = True


class TransitionError(ValueError):
    """A status change that the graph does not permit."""


def is_allowed(current: str | None, target: str | None) -> bool:
    """Whether `current -> target` is permitted.

    ⚠️ A NO-OP IS ALLOWED. `confirmed -> confirmed` arrives whenever a PATCH carries other
    fields plus the status it already has, which the UI does on every edit. Rejecting it
    would turn "change the notes" into an error.

    ⚠️ AN UNKNOWN CURRENT STATUS IS PERMISSIVE, DELIBERATELY. Legacy rows carry values
    this graph does not name (`pending`, `scheduled`, `in_production` appear in other
    services), and refusing to touch them would strand them permanently — the exact
    shape the `completed` net had to be widened for in audit #2 D-3. Unknown TARGETS are
    still refused, so the graph cannot be widened by accident.
    """
    if target is None:
        return True  # not a status change
    cur = _canonical(current)
    tgt = _canonical(target)
    if cur == tgt:
        return True
    if cur not in ALLOWED:
        return tgt in _ALL_KNOWN_TARGETS
    return tgt in ALLOWED[cur]


def check(current: str | None, target: str | None, *, order_number: str = "") -> None:
    """Raise `TransitionError` if the transition is not permitted.

    The message names the current state and what IS reachable, because a bare refusal
    sends the reader to this file to find out; the reachable set is the thing they came
    for.
    """
    if is_allowed(current, target):
        return
    cur = _canonical(current)
    reachable = sorted(ALLOWED.get(cur, frozenset()))
    where = f"Order {order_number} " if order_number else "This order "
    if cur in TERMINAL:
        raise TransitionError(
            f"{where}is {cur}, which is final. No further status change is possible."
        )
    raise TransitionError(
        f"{where}is {cur}; it cannot go straight to {_canonical(target)}. "
        f"From {cur} it can become: {', '.join(reachable) or '(nothing)'}."
    )


def _canonical(status: str | None) -> str:
    """Normalise the cancel spellings; everything else passes through.

    `canceled` and `cancelled` both appear in legacy rows
    (`app/models/sales_order.py:28-29`), and a graph keyed on one of them would refuse
    transitions out of the other.
    """
    if status in CANCEL_SPELLINGS:
        return STATUS_CANCELLED
    return status or ""


#: Every status any rule mentions as a destination. Used to bound the permissive branch
#: for unknown current states, so that branch cannot be used to write an arbitrary string.
_ALL_KNOWN_TARGETS = frozenset(
    {t for targets in ALLOWED.values() for t in targets} | set(ALLOWED)
)
