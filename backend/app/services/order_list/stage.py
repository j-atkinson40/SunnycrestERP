"""Stage, flags, groups, totals, and the lens line. No database and no model.

Every number in here is counted from `OrderFacts`. A fact is something the
order row, its delivery, its proof, or its invoice already says.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Literal

from app.services.order_list.question import OrderQuestion

# A service with no driver is "needs something" only when it is soon. Further
# out is hidden from the default view, which is what the footer says.
DRIVER_HORIZON_DAYS = 14

StageName = Literal["proof", "scheduled", "delivered", "invoiced"]
FlagName = Literal["change", "proof", "nodriver", "close"]
GroupId = Literal["needs_something", "going_out_this_week", "delivered_not_invoiced"]

# The prototype's fill counts: the current step is empty, and Invoiced fills all four.
DOTS_FILLED: dict[StageName, int] = {
    "proof": 0,
    "scheduled": 1,
    "delivered": 2,
    "invoiced": 4,
}

STAGE_LABEL: dict[StageName, str] = {
    "proof": "Proof",
    "scheduled": "Scheduled",
    "delivered": "Delivered",
    "invoiced": "Invoiced",
}

FLAG_COPY: dict[FlagName, tuple[str, str, str]] = {
    # flag → (row text, action id, button)
    "change": ("Legacy change requested", "proof", "Open the proof"),
    "proof": ("Proof not approved", "proof", "Open the proof"),
    "nodriver": ("No driver yet", "scheduling", "Open scheduling"),
    "close": ("Delivered, not closed out", "close", "Close it out"),
}

GROUP_LABEL: dict[GroupId, str] = {
    "needs_something": "Needs something",
    "going_out_this_week": "Going out this week",
    "delivered_not_invoiced": "Delivered, not invoiced yet",
}

OFFICE_GROUP_ORDER: tuple[GroupId, ...] = (
    "needs_something",
    "going_out_this_week",
    "delivered_not_invoiced",
)
# Accounting's default leads with the money that has not been billed.
# Same rows, different order. Nothing is hidden.
ACCOUNTING_GROUP_ORDER: tuple[GroupId, ...] = (
    "delivered_not_invoiced",
    "needs_something",
    "going_out_this_week",
)

DEFAULT_FOOTER = (
    'Invoiced orders and orders further out don\'t show here. '
    'Ask for them: "Hopkins orders this month".'
)
FILTER_FOOTER = "Times and drivers are changed in scheduling, not from a list."

ProofState = Literal["none", "pending", "approved", "change_requested"]

_CHANGE_STATUSES = frozenset({
    "changes_requested", "change_requested", "revision_requested", "needs_changes",
})
_APPROVED_STATUSES = frozenset({"approved", "complete", "completed", "printed"})
_INVOICED_SKIP = frozenset({"draft", "void", "write_off"})
_CANCELLED = frozenset({"cancelled", "canceled"})


@dataclass
class ProofFact:
    status: str | None = None
    family_approved: bool = False
    approved_at: object | None = None
    latest_version_at: object | None = None


@dataclass
class TaskFact:
    task_type: str | None = None
    status: str | None = None
    approved_at: object | None = None


@dataclass
class DeliveryFact:
    status: str | None = None
    primary_assignee_id: str | None = None
    requested_date: date | None = None


@dataclass
class OrderFacts:
    """One order, as the tables already record it. Derived fields are not stored."""

    id: str
    number: str
    deceased_name: str | None
    funeral_home: str
    cemetery: str | None = None
    cemetery_city: str | None = None
    vault: str | None = None
    service_date: date | None = None
    service_time: time | None = None
    total: Decimal = Decimal("0")
    status: str = "confirmed"
    delivered_at: object | None = None
    completed_at: object | None = None
    delivered_by_driver_name: str | None = None
    proofs: list[ProofFact] = field(default_factory=list)
    tasks: list[TaskFact] = field(default_factory=list)
    deliveries: list[DeliveryFact] = field(default_factory=list)
    invoice_statuses: list[str] = field(default_factory=list)

    @property
    def cancelled(self) -> bool:
        return (self.status or "").lower() in _CANCELLED

    @property
    def invoiced(self) -> bool:
        return any(status not in _INVOICED_SKIP for status in self.invoice_statuses)

    @property
    def delivered(self) -> bool:
        if self.delivered_at is not None or (self.status or "").lower() in {"delivered", "completed"}:
            return True
        return any((d.status or "").lower() == "completed" for d in self.deliveries)

    @property
    def completed(self) -> bool:
        """Closed out. `completed_at` is the completion column the order already has."""
        return self.completed_at is not None or (self.status or "").lower() == "completed"

    @property
    def assignee_ids(self) -> set[str]:
        return {
            d.primary_assignee_id
            for d in self.deliveries
            if d.primary_assignee_id and (d.status or "").lower() not in _CANCELLED
        }

    @property
    def has_driver(self) -> bool:
        if self.delivered_by_driver_name:
            return True
        return bool(self.assignee_ids)

    @property
    def proof(self) -> ProofState:
        change = False
        pending = False
        saw_legacy = False
        for proof in self.proofs:
            saw_legacy = True
            status = (proof.status or "").lower()
            if status in _CHANGE_STATUSES:
                change = True
                continue
            if (
                proof.approved_at is not None
                and proof.latest_version_at is not None
                and proof.latest_version_at > proof.approved_at
            ):
                change = True
                continue
            approved = (
                status in _APPROVED_STATUSES
                or proof.family_approved
                or proof.approved_at is not None
            )
            if not approved:
                pending = True
        for task in self.tasks:
            if "legacy" not in (task.task_type or ""):
                continue
            saw_legacy = True
            status = (task.status or "").lower()
            if status in _CHANGE_STATUSES:
                change = True
            elif task.approved_at is not None or status in _APPROVED_STATUSES:
                continue
            else:
                pending = True
        if change:
            return "change_requested"
        if pending:
            return "pending"
        if saw_legacy:
            return "approved"
        return "none"


def proof_state_of(
    proofs: list[ProofFact], tasks: list[TaskFact],
) -> ProofState:
    """Test seam. The row uses `OrderFacts.proof`, which calls the same rules."""
    return OrderFacts(id="", number="", deceased_name=None, funeral_home="", proofs=proofs, tasks=tasks).proof


def stage_of(facts: OrderFacts) -> StageName:
    if facts.invoiced:
        return "invoiced"
    if facts.delivered:
        return "delivered"
    # An open proof with nobody assigned is still the proof step. Once a driver
    # is assigned, or there is a service date and nothing is owed on the proof,
    # the step is scheduled — a missing driver is the flag, not the step.
    if facts.proof in {"pending", "change_requested"} and not facts.has_driver:
        return "proof"
    if facts.has_driver or facts.service_date is not None:
        return "scheduled"
    return "proof"


def flag_of(facts: OrderFacts, today: date) -> FlagName | None:
    if facts.invoiced:
        return None
    if facts.delivered and not facts.completed:
        return "close"
    if facts.proof == "change_requested":
        return "change"
    if facts.proof == "pending":
        return "proof"
    if (
        not facts.delivered
        and not facts.has_driver
        and facts.service_date is not None
        and facts.service_date <= today + timedelta(days=DRIVER_HORIZON_DAYS)
    ):
        return "nodriver"
    return None


def week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def group_of(facts: OrderFacts, today: date) -> GroupId | None:
    """Which default-view group this order belongs in. None means it stays hidden.

    The three groups are mutually exclusive. A flag wins over "going out", and
    a close-out flag wins over "delivered, not invoiced" — that row is waiting
    on a person, not on an invoice.
    """
    if facts.cancelled or facts.invoiced:
        return None
    flag = flag_of(facts, today)
    if flag is not None:
        return "needs_something"
    if facts.delivered:
        return "delivered_not_invoiced"
    start, end = week_bounds(today)
    if facts.service_date is not None and start <= facts.service_date <= end:
        return "going_out_this_week"
    return None


def group_order_for(role_slug: str | None) -> tuple[GroupId, ...]:
    if role_slug and "account" in role_slug.lower():
        return ACCOUNTING_GROUP_ORDER
    return OFFICE_GROUP_ORDER


def is_driver(role_slug: str | None) -> bool:
    return bool(role_slug) and "driver" in role_slug.lower()


def matches(
    facts: OrderFacts, question: OrderQuestion, *, include_cancelled: bool = False,
) -> bool:
    """True when this order is inside the question. Default-view membership is separate.

    ⚠️ `include_cancelled` IS A PARAMETER RATHER THAN A SECOND MATCHER, added 2026-10-19.
    The Sales Order Pane opens one named order and must be able to reach a cancelled one
    — "Draft and cancelled show as such" — while every LIST question still excludes them.
    Writing a cancelled-tolerant copy of the five field comparisons below would have been
    two sets of matching rules free to drift, which is the defect this codebase keeps
    recording. Every list caller leaves the default alone.
    """
    if facts.cancelled and not include_cancelled:
        return False
    if question.funeral_home and not _contains(facts.funeral_home, question.funeral_home):
        return False
    if question.cemetery and not (
        _contains(facts.cemetery, question.cemetery) or _contains(facts.cemetery_city, question.cemetery)
    ):
        return False
    if question.vault and not _contains(facts.vault, question.vault):
        return False
    if question.decedent and not _contains(facts.deceased_name, question.decedent):
        return False
    if question.service_from is not None or question.service_to is not None:
        if facts.service_date is None:
            return False
        if question.service_from is not None and facts.service_date < question.service_from:
            return False
        if question.service_to is not None and facts.service_date > question.service_to:
            return False
    if question.delivered is True and not facts.delivered:
        return False
    if question.delivered is False and facts.delivered:
        return False
    if question.invoiced is True and not facts.invoiced:
        return False
    if question.invoiced is False and facts.invoiced:
        return False
    if question.going_out and facts.delivered:
        return False
    return True


def _contains(haystack: str | None, needle: str) -> bool:
    if not haystack or not needle:
        return False
    hay = haystack.casefold()
    pin = needle.casefold()
    if pin in hay:
        return True
    # "monticello" matches a line that says "Monticellos" and the reverse.
    if pin.endswith("s") and pin[:-1] in hay:
        return True
    if not pin.endswith("s") and f"{pin}s" in hay:
        return True
    return False


def sort_key(facts: OrderFacts) -> tuple:
    return (
        facts.service_date or date.max,
        facts.service_time or time.max,
        (facts.deceased_name or "").casefold(),
        facts.id,
    )


def select_default(facts: list[OrderFacts], today: date) -> dict[GroupId, list[OrderFacts]]:
    grouped: dict[GroupId, list[OrderFacts]] = {key: [] for key in OFFICE_GROUP_ORDER}
    for item in facts:
        group = group_of(item, today)
        if group is not None:
            grouped[group].append(item)
    for rows in grouped.values():
        rows.sort(key=sort_key)
    return grouped


def select_flat(facts: list[OrderFacts], question: OrderQuestion) -> list[OrderFacts]:
    chosen = [item for item in facts if matches(item, question)]
    chosen.sort(key=sort_key)
    return chosen


def sum_totals(rows: list[OrderFacts], question: OrderQuestion) -> dict | None:
    """The money line. None on the default view — that view has a footer, not a total.

    ⚠️ THE SUM IS `Decimal` ADDED HERE. Nothing upstream is allowed to hand this
    function a number it computed. `show_not_invoiced` is suppressed on the
    not-invoiced question itself, where the count would repeat the title.
    """
    if question.is_default:
        return None
    not_invoiced = sum(1 for row in rows if not row.invoiced)
    show_money = question.about_money
    total = sum((row.total for row in rows), Decimal("0")) if show_money else None
    return {
        "count": len(rows),
        "not_invoiced": not_invoiced,
        "show_money": show_money,
        "total": f"{total:.2f}" if total is not None else None,
        "show_not_invoiced": bool(show_money and not_invoiced > 0 and question.invoiced is not False),
    }


def format_money(amount: str | None) -> str | None:
    if amount is None:
        return None
    quantized = Decimal(amount)
    if quantized == quantized.to_integral():
        return f"${int(quantized):,}"
    return f"${quantized:,.2f}"


def total_sentence(rows: list[OrderFacts]) -> str:
    """What "how much is that?" says. Count and dollars, both counted here."""
    count = len(rows)
    total = sum((row.total for row in rows), Decimal("0"))
    noun = "order" if count == 1 else "orders"
    return f"{count} {noun} · {format_money(f'{total:.2f}')}"


_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def format_when(service_date: date | None, service_time: time | None, today: date) -> dict:
    """Date lines for a row. Keys are omitted when the order has no such fact."""
    out: dict[str, str | bool] = {}
    if service_date is not None:
        start, end = week_bounds(today)
        in_week = start <= service_date <= end
        weekday = _DOW[service_date.weekday()]
        month = _MON[service_date.month - 1]
        out["date_in_week"] = in_week
        if in_week:
            out["date_primary"] = weekday
        else:
            out["date_primary"] = f"{weekday} {month} {service_date.day}"
            out["date_head"] = f"{weekday} {month}"
            out["date_day"] = str(service_date.day)
    if service_time is not None:
        hour = service_time.hour % 12 or 12
        out["time_label"] = f"{hour}:{service_time.minute:02d}"
    return out


def meta_line(facts: OrderFacts) -> str:
    place = facts.cemetery or ""
    if facts.cemetery_city:
        place = f"{place}, {facts.cemetery_city}" if place else facts.cemetery_city
    parts = [part for part in (facts.funeral_home, place, facts.vault) if part]
    return " · ".join(parts)


def row_dict(facts: OrderFacts, today: date) -> dict:
    """One list row. Absent facts are omitted — the pane renders no blank cells."""
    stage = stage_of(facts)
    flag = flag_of(facts, today)
    row: dict = {
        "id": facts.id,
        "number": facts.number,
        "deceased_name": facts.deceased_name or "Unnamed",
        "meta": meta_line(facts),
        "stage": stage,
        "stage_label": STAGE_LABEL[stage],
        "dots_filled": DOTS_FILLED[stage],
        "invoiced": facts.invoiced,
        "service_date": facts.service_date.isoformat() if facts.service_date else None,
    }
    if row["service_date"] is None:
        del row["service_date"]
    row.update(format_when(facts.service_date, facts.service_time, today))
    if flag is not None:
        label, action, action_label = FLAG_COPY[flag]
        row["flag"] = flag
        row["flag_label"] = label
        row["action"] = action
        row["action_label"] = action_label
    if not row["meta"]:
        del row["meta"]
    return row


def stands_at(facts: OrderFacts, today: date) -> str:
    flag = flag_of(facts, today)
    if flag is not None:
        return FLAG_COPY[flag][0]
    return STAGE_LABEL[stage_of(facts)]


def _lens_bit(facts: OrderFacts, today: date, *, flagged: bool) -> str:
    name = (facts.deceased_name or "Unnamed").split()[-1]
    if flagged:
        flag = flag_of(facts, today)
        text = FLAG_COPY[flag][0] if flag is not None else STAGE_LABEL[stage_of(facts)]
        return f"{name}: {text.casefold()}"
    when = format_when(facts.service_date, facts.service_time, today)
    clock = when.get("time_label")
    return f"{name} {clock}" if clock else name


def lens_for(
    *,
    title: str,
    rows: list[OrderFacts],
    today: date,
    group_label: str | None = None,
    flagged: bool = False,
) -> dict:
    """The glasses line: a count, then three at a time.

    More than three says how many remain and that the rest is on the iPad.
    Three or fewer offer the first one.
    """
    heading = (group_label or title).upper()
    pages: list[dict] = []
    chunk: list[str] = []
    for index, facts in enumerate(rows):
        chunk.append(_lens_bit(facts, today, flagged=flagged))
        if len(chunk) == 3:
            pages.append({"items": chunk, "more": len(rows) - (index + 1)})
            chunk = []
    if chunk:
        pages.append({"items": chunk, "more": 0})
    count = len(rows)
    return {
        "heading": f"{heading} · {count}",
        "pages": pages,
        "cue": "tap: open the first" if count <= 3 else "tap: next three · double tap: on the iPad",
        "first_order_id": rows[0].id if rows else None,
    }
