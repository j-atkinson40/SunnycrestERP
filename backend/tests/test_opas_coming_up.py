"""Two bugs in the door's first real answer. No database, no network, no model call.

On 2026-10-23 the model door worked on production for the first time and was asked
"anything going to st marys coming up?". It read the phrase correctly — cemetery
St. Mary's, going_out — and the ENGINE then answered wrongly, twice:

    SO-2026-0001   dated 2026-10-16, a week gone, and it came back anyway
    SO-2026-0001   labelled "Scheduled", and it is a DRAFT

One row, two independent defects, and they share a cause: both the filter and the
label were inferring a schedule from something that is not one. `going_out` meant
"not yet delivered", and a draft has never been delivered. `stage_of` returned the
rung `scheduled` for anything carrying a service date, and a draft can carry one.

⚠️ EVERY FIXTURE HERE IS BUILT FROM PRODUCTION'S OWN SHAPE rather than from a round
number: a draft with a past service date, a confirmed order dated today, a confirmed
order dated five days out. That is the three rows James was shown, and the expected
answer — two, not three — is his.
"""
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone
from decimal import Decimal

from app.services.order_list import detail
from app.services.order_list.question import OrderQuestion, interpret
from app.services.order_list.stage import (
    DOTS_FILLED,
    STATUS_LABEL,
    DeliveryFact,
    OrderFacts,
    ProofFact,
    dots_for,
    flag_of,
    matches,
    row_dict,
    select_flat,
    stands_at,
    stage_of,
    status_label,
    status_of,
)

#: Friday. SO-2026-0001's service date (2026-10-16) is a week behind it, SO-2026-0003's
#: is today, SO-2026-0004's (2026-10-28) is five days out — production's spacing.
TODAY = date(2026, 10, 23)

GONE = date(2026, 10, 16)
SOON = date(2026, 10, 28)


def _order(**kwargs) -> OrderFacts:
    base = dict(
        id=kwargs.pop("id", "o1"),
        number=kwargs.pop("number", "SO-2026-0001"),
        deceased_name=kwargs.pop("deceased_name", "smith"),
        funeral_home=kwargs.pop("funeral_home", "Hopkins Funeral Home"),
        cemetery=kwargs.pop("cemetery", "St. Mary's Cemetery"),
        total=kwargs.pop("total", Decimal("1000")),
    )
    base.update(kwargs)
    return OrderFacts(**base)


def _draft_past() -> OrderFacts:
    """SO-2026-0001 as production holds it: a draft, dated a week ago, undelivered."""
    return _order(id="gone", number="SO-2026-0001", status="draft", service_date=GONE)


def _coming_up_today() -> OrderFacts:
    return _order(id="today", number="SO-2026-0003", status="confirmed", service_date=TODAY)


def _coming_up_soon() -> OrderFacts:
    return _order(
        id="soon", number="SO-2026-0004", deceased_name="hart",
        status="confirmed", service_date=SOON,
    )


def _coming_up() -> OrderQuestion:
    """The question the door produced for James's phrase, verbatim from the probe."""
    return OrderQuestion(
        cemetery="St. Mary's Cemetery",
        going_out=True,
        title="Orders going to St. Mary's Cemetery",
    )


# ── bug 1: "coming up" is a date ───────────────────────────────────────────────


def test_james_walk_phrase_returns_two_orders_not_three():
    """The whole bug report in one assertion. Expected: SO-0003 and SO-0004."""
    rows = select_flat(
        [_draft_past(), _coming_up_today(), _coming_up_soon()], _coming_up(), TODAY,
    )
    assert [row.number for row in rows] == ["SO-2026-0003", "SO-2026-0004"]


def test_a_past_dated_order_is_never_coming_up_whatever_its_status():
    """"Past-dated orders never appear in a 'coming up' answer, whatever their status."

    Four statuses, one date. Before the fix the draft and the confirmed one both came
    back — the filter asked whether a delivery had completed, and for neither had one.
    """
    question = _coming_up()
    for status in ("draft", "confirmed", "in_production", "ready"):
        order = _order(status=status, service_date=GONE)
        assert matches(order, question, TODAY) is False, status


def test_an_order_with_no_service_date_is_not_coming_up():
    """Nothing is known about when it goes out, so it cannot be known to be ahead."""
    assert matches(_order(status="confirmed"), _coming_up(), TODAY) is False


def test_today_counts_as_coming_up():
    """"Service date today or later." Today is in, and the boundary is the ruling's."""
    assert matches(_coming_up_today(), _coming_up(), TODAY) is True
    assert matches(_order(status="confirmed", service_date=TODAY), _coming_up(), TODAY) is True


def test_coming_up_no_longer_keys_off_delivery_at_all():
    """⚠️ A REAL BEHAVIOUR CHANGE, AND IT IS THE RULING AS WRITTEN.

    "going_out means service date today or later … not 'not yet delivered'." So a
    future-dated order delivered early IS coming up. This test exists to make that
    deliberate rather than incidental: it is the one case where the old filter and the
    new one disagree in the OTHER direction, and if a later session decides the old
    reading was right, this is the assertion it has to argue with.

    Nothing is lost on the rules path — `_going` sets `delivered=False` alongside
    `going_out=True`, which the next test pins.
    """
    early = _order(
        status="confirmed",
        service_date=SOON,
        delivered_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )
    assert early.delivered is True
    assert matches(early, _coming_up(), TODAY) is True


def test_the_rules_path_still_excludes_delivered_through_its_own_flag():
    """"going out friday" is a rules phrase, and it carries `delivered=False` itself."""
    question = interpret("going out friday", today=TODAY).question
    assert question is not None
    assert question.going_out is True
    assert question.delivered is False
    delivered = _order(
        status="confirmed",
        service_date=question.service_from,
        delivered_at=datetime(2026, 10, 24, tzinfo=timezone.utc),
    )
    assert matches(delivered, question, TODAY) is False


def test_matches_has_no_default_today_so_a_caller_cannot_use_the_container_clock():
    """⚠️ A SIGNATURE ASSERTION, AND IT IS LOAD-BEARING FOR TENANT-LOCAL TIME.

    `today_for(company)` exists because "a UTC date near midnight is the wrong Friday".
    A default of `date.today()` on this parameter would put the container's date inside
    a tenant-local filter and nothing would ever go red — the answer would simply be
    one day wrong for part of each day, in whichever tenants are not on UTC.
    """
    today_param = inspect.signature(matches).parameters["today"]
    assert today_param.default is inspect.Parameter.empty


def test_matches_still_refuses_a_cancelled_order_by_default():
    """⚠️ A DUPLICATE OF AN ASSERTION IN `test_sales_order_pane.py`, ON PURPOSE.

    That file skips at module level when `DATABASE_URL` is unset, so all 44 of its
    tests — including this pure one, which touches no database — did not run on my
    machine while I read the gate as green. CI sets `DATABASE_URL`, ran them, and the
    `today` parameter added above broke this call. A gate whose environment cannot hold
    the defect is not evidence about it (CLAUDE.md §11).

    `matches` is a pure function and its default must be checked somewhere unguarded.
    This file has no skip. The copy in the pane's file stays — it is read there beside
    the pane behaviour that depends on it.
    """
    cancelled = _order(status="cancelled", service_date=SOON)
    question = OrderQuestion(decedent="smith", title="t")
    assert matches(cancelled, question, TODAY) is False
    assert matches(cancelled, question, TODAY, include_cancelled=True) is True


# ── bug 2: a label is the order's real status ─────────────────────────────────


def test_a_draft_is_labelled_draft_everywhere_it_is_labelled():
    """The row, the reply line, and the Sales Order Pane. Three surfaces, one word.

    ⚠️ DATED BEYOND THE DRIVER HORIZON ON PURPOSE. My first version of this test used
    `_draft_past()` and failed on `stands_at` with "No driver yet" — a FLAG, which wins
    over the status label by design on both the row and the reply line. That is not the
    bug and was not changed; it is pinned separately below. A draft far enough out to
    carry no flag is what isolates the label.
    """
    draft = _order(status="draft", service_date=date(2026, 12, 1))
    assert status_of(draft) == "draft"
    assert status_label(draft) == "Draft"
    assert row_dict(draft, TODAY)["stage_label"] == "Draft"
    assert stands_at(draft, TODAY) == "Draft"
    assert detail.steps_for(draft) == {"kind": "draft", "label": "Draft"}


def test_a_flag_wins_over_the_status_label_and_that_is_unchanged():
    """⚠️ PINNED BECAUSE IT SURPRISED ME, NOT BECAUSE IT CHANGED.

    `OrderListPane` renders `flag_label ?? stage_label`, and `stands_at` returns the
    flag's words when there is one. So fixing `stage_label` alone does not decide what
    the office reads — and the word "Scheduled" James was shown came from a PROBE SCRIPT
    printing `stage_label` raw, not from the pane. The label was wrong either way, and it
    is still the dots' accessible name; this pins which field each surface takes.
    """
    confirmed = _coming_up_soon()
    row = row_dict(confirmed, TODAY)
    assert confirmed.has_driver is False
    assert row["flag_label"] == "No driver yet"
    assert row["stage_label"] == "Confirmed"
    assert row["status"] == "confirmed"
    assert stands_at(confirmed, TODAY) == "No driver yet"


def test_a_draft_carries_no_driver_flag_so_the_pane_can_say_draft():
    """⚠️ NOT JAMES'S WORDS. MINE, AND THE REPORT SAYS SO.

    Measured on production after the label fix: all three St. Mary's rows read "No driver
    yet", the draft included — because the flag wins. "If the office reads that, they'll
    think it's on the schedule" is just as true of an order that merely needs a driver
    assigning, so "draft shows Draft" was still not reaching the surface the complaint
    was about.

    Only `nodriver` is suppressed. A legacy proof can be genuinely in progress on a
    draft, which the next assertion keeps.
    """
    draft = _draft_past()
    assert flag_of(draft, TODAY) is None
    assert row_dict(draft, TODAY).get("flag_label") is None
    assert row_dict(draft, TODAY)["stage_label"] == "Draft"
    assert stands_at(draft, TODAY) == "Draft"

    # A confirmed order in the same position still gets the flag — this is a draft rule.
    confirmed = _order(status="confirmed", service_date=GONE)
    assert flag_of(confirmed, TODAY) == "nodriver"


def test_a_draft_with_a_proof_problem_still_says_so():
    """The proof flags are about work in progress, not about a schedule, and a draft can
    carry them. Suppressing every flag on a draft would have hidden real work.
    """
    draft = _order(
        status="draft", service_date=GONE,
        proofs=[ProofFact(status="changes_requested")],
    )
    assert flag_of(draft, TODAY) == "change"
    assert row_dict(draft, TODAY)["flag_label"] == "Legacy change requested"
    # ⚠️ AND THE STATUS IS STILL DRAFT UNDERNEATH IT, so the Sales Order Pane — which
    # reads `steps_for`, not the flag — is unaffected.
    assert status_label(draft) == "Draft"
    assert detail.steps_for(draft)["kind"] == "draft"


def test_the_word_scheduled_is_not_a_label_this_module_can_produce():
    """⚠️ THE DELETION IS THE FIX. "Scheduled only if something actually schedules it
    (nothing does yet, so probably never)" — so there is no entry to reach for.

    Checked against the VALUES, not against the source, so a re-introduction under any
    key fails. The companion ratchet below watches the source.
    """
    assert "Scheduled" not in STATUS_LABEL.values()
    assert "scheduled" not in DOTS_FILLED


def test_no_surface_can_say_scheduled_about_an_order():
    """Every status, through every labelling function. None of them says it."""
    cases = [
        _order(status="draft", service_date=SOON),
        _order(status="confirmed", service_date=SOON),
        _order(status="confirmed", service_date=SOON,
               deliveries=[DeliveryFact(primary_assignee_id="driver-1")]),
        _order(status="cancelled", service_date=SOON),
        _order(status="confirmed", delivered_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
               completed_at=datetime(2026, 10, 20, tzinfo=timezone.utc)),
        _order(status="confirmed", invoice_statuses=["sent"],
               delivered_at=datetime(2026, 10, 20, tzinfo=timezone.utc)),
    ]
    said = {status_label(order) for order in cases}
    said |= {row_dict(order, TODAY)["stage_label"] for order in cases}
    said |= {stands_at(order, TODAY) for order in cases}
    assert "Scheduled" not in said
    # ⚠️ AND THE SET IS NON-EMPTY AND VARIED, so the assertion above is not satisfied by
    # a labeller that returned nothing. CLAUDE.md §11, a control that cannot distinguish
    # itself from a failure.
    assert len(said) >= 4


def test_each_status_reads_as_itself():
    assert status_label(_order(status="cancelled", service_date=SOON)) == "Cancelled"
    assert status_label(_coming_up_soon()) == "Confirmed"
    assert status_label(
        _order(status="confirmed", delivered_at=datetime(2026, 10, 20, tzinfo=timezone.utc))
    ) == "Delivered"
    assert status_label(
        _order(status="confirmed", invoice_statuses=["sent"],
               delivered_at=datetime(2026, 10, 20, tzinfo=timezone.utc))
    ) == "Invoiced"


def test_cancelled_wins_over_a_completed_delivery():
    """A cancelled order that had been delivered is cancelled, not Delivered."""
    order = _order(
        status="cancelled",
        delivered_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
        invoice_statuses=["sent"],
    )
    assert order.delivered is True and order.invoiced is True
    assert status_label(order) == "Cancelled"


def test_a_confirmed_order_with_a_driver_is_still_only_confirmed():
    """⚠️ THE TEMPTATION THIS CLOSES. A driver on the delivery is the nearest thing the
    platform has to a schedule, and it is still not a status on the order.
    """
    order = _order(
        status="confirmed", service_date=SOON,
        deliveries=[DeliveryFact(primary_assignee_id="driver-1")],
    )
    assert order.has_driver is True
    assert stage_of(order) == "confirmed"
    assert status_label(order) == "Confirmed"


def test_a_draft_and_a_cancelled_order_fill_no_dots():
    """The dots carry `aria-label={row.stage_label}`, so they are the label's other half."""
    draft = _draft_past()
    cancelled = _order(status="cancelled", service_date=SOON)
    assert dots_for(draft) == 0
    assert dots_for(cancelled) == 0
    assert row_dict(draft, TODAY)["dots_filled"] == 0
    assert row_dict(cancelled, TODAY)["dots_filled"] == 0
    # The live ladder is untouched — this is a draft rule, not a new ladder.
    assert dots_for(_coming_up_soon()) == 1


def test_the_row_carries_the_status_as_well_as_its_words():
    row = row_dict(_draft_past(), TODAY)
    assert row["status"] == "draft"
    assert row["stage_label"] == "Draft"


# ── the two paths agree ───────────────────────────────────────────────────────


def test_the_door_prompt_does_not_teach_the_meaning_the_code_rejects():
    """⚠️ "The rules path and door path must agree" (James, 2026-10-23).

    v1 of the prompt told the model `going_out  true — the person means orders not yet
    delivered`, which is the same wrong definition the matcher held. Fixing only the
    matcher would leave the model being asked for one thing and the engine filtering by
    another, and the disagreement would be invisible: both produce a plausible list.

    ⚠️ AND THE OBVIOUS ASSERTION IS WRONG, WHICH IS WHY THIS NOTE IS HERE. My first
    version read `assert "not yet delivered" not in SYSTEM_PROMPT` and failed: the new
    text contains that phrase deliberately, as `Not 'not yet delivered'`. A substring
    ban on the words would forbid the prompt from naming the misreading it corrects.
    What must be absent is the DEFINITION.
    """
    from scripts import seed_opas_order_list_prompt as seed

    assert "means orders not yet delivered" not in seed.SYSTEM_PROMPT
    going_out_line = next(
        line for line in seed.SYSTEM_PROMPT.splitlines() if "going_out " in line
    )
    assert "today or later" in going_out_line
    assert "Not 'not yet delivered'" in seed.SYSTEM_PROMPT


# ── the fourth group: a passed service day is named, not hidden ───────────────


def test_an_overdue_order_is_named_rather_than_hidden_or_mislabelled():
    """⚠️ JAMES ACCEPTED THE PROBLEM AND RULED THE FIX: "a fourth group for 'Going out'
    instead of hiding rows" (2026-10-23).

    "Going out this week" bucketed by calendar week, so the SAME stale order read
    "Going out this week" on a Friday (its Monday service date is inside this week) and
    vanished on the following Monday (the date is now last week, and nothing else
    claimed it). Two wrong answers from one rule. The row now has a group of its own.
    """
    from app.services.order_list.stage import GROUP_LABEL, OFFICE_GROUP_ORDER, group_of

    # Monday of this week, driver assigned so no flag claims it first, not delivered.
    monday = date(2026, 10, 19)
    stale = _order(
        status="confirmed", service_date=monday,
        deliveries=[DeliveryFact(primary_assignee_id="driver-1")],
    )
    assert flag_of(stale, TODAY) is None, "a flag would hide which group is being tested"
    assert group_of(stale, TODAY) == "overdue"
    assert GROUP_LABEL["overdue"] == "Service day passed, not delivered"

    # ⚠️ AND THE SAME ORDER A WEEK LATER IS STILL VISIBLE, which is the half that was
    # broken in the other direction. Before the fourth group this returned None.
    next_monday = date(2026, 10, 26)
    assert group_of(stale, next_monday) == "overdue"

    # Second in the office's reading order — more urgent than this week's schedule.
    assert OFFICE_GROUP_ORDER.index("overdue") == 1
    assert OFFICE_GROUP_ORDER.index("overdue") < OFFICE_GROUP_ORDER.index("going_out_this_week")


def test_going_out_this_week_no_longer_holds_a_passed_date():
    """The positive control for the test above: the group still works for its own rows."""
    from app.services.order_list.stage import group_of

    coming = _order(
        status="confirmed", service_date=date(2026, 10, 25),
        deliveries=[DeliveryFact(primary_assignee_id="driver-1")],
    )
    assert group_of(coming, TODAY) == "going_out_this_week"
    today_row = _order(
        status="confirmed", service_date=TODAY,
        deliveries=[DeliveryFact(primary_assignee_id="driver-1")],
    )
    assert group_of(today_row, TODAY) == "going_out_this_week"


def test_every_group_has_a_label_and_appears_in_both_reading_orders():
    """A new GroupId with no label raises a KeyError in `_pack`; one missing from an
    order tuple is silently never rendered. Both are easy to half-do.
    """
    from app.services.order_list.stage import (
        ACCOUNTING_GROUP_ORDER,
        GROUP_LABEL,
        OFFICE_GROUP_ORDER,
    )

    assert set(GROUP_LABEL) == set(OFFICE_GROUP_ORDER) == set(ACCOUNTING_GROUP_ORDER)
    assert len(OFFICE_GROUP_ORDER) == len(ACCOUNTING_GROUP_ORDER) == len(GROUP_LABEL) == 4
