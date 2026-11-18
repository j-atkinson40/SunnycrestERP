"""The week line's WORDING, and what it offers past a deadline.

⚠️ **EVERY DEFECT FIXED HERE WAS VISIBLE ON THE SCREEN AND INVISIBLE TO THE
SUITE.** `test_payroll_week_calendar.py` asserts the line is PRESENT, carries
the week number and addresses the week by its end — all true of
"Week 46 (Nov 8–Nov 14) has no hours yet. Payentry needs it by Wednesday
5:00pm." rendered on a Friday, two days after that Wednesday, under a link
reading "Open Weekly payroll" beside an offer to see it again next month.

So these tests assert on the WORDS, and on all seven days the line can render
rather than on whichever one the suite happens to run.

⚠️ The two phrasings are PURE FUNCTIONS at module level for exactly that
reason. Inlined in the condition, the past-tense branch — the one that was
wrong — was reachable only by monkeypatching `date.today` out from under a
module that reads it elsewhere.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from app.services.fragments.platform_defaults import cutoff_words, week_range_words
from app.services.note.deferral import allowed_presets, resolve_preset
from app.services.payroll.week_calendar import current_payroll_week

WED, FIVE_PM = 2, time(17, 0)

#: Saturday 2026-11-14 ends week 46 — James's own example week, and the one
#: whose wording he quoted. Every day below is a real day of that cycle.
WEEK_46_END = date(2026, 11, 14)


def _desc(d: date):
    return current_payroll_week(d, cutoff_weekday=WED, cutoff_time=FIVE_PM)


# ── the date range ───────────────────────────────────────────────────────


def test_a_week_inside_one_month_names_that_month_ONCE():
    """"Nov 8–14", which is what James asked for by name."""
    assert week_range_words(date(2026, 11, 8), date(2026, 11, 14)) == "Nov 8–14"


def test_the_live_week_46_range_is_the_one_from_the_brief():
    """⚠️ DERIVED, NOT TYPED. The range is read off the week calendar rather
    than written out, so this fails if the week's boundaries move rather than
    only if the formatting does."""
    w = _desc(WEEK_46_END)
    assert week_range_words(w.week_start_date, w.week_end_date) == "Nov 8–14"


def test_a_week_crossing_a_month_names_BOTH():
    """The collapse is not unconditional — "Oct 25–1" would be unreadable."""
    assert week_range_words(date(2026, 10, 25), date(2026, 11, 1)) == "Oct 25–Nov 1"


def test_a_week_crossing_a_YEAR_names_both_months():
    """⚠️ THE YEAR IS COMPARED, NOT ONLY THE MONTH. December 2026 and
    December 2027 share a month number; collapsing on the month alone would
    render a 53-week span as "Dec 28–3"."""
    assert week_range_words(date(2026, 12, 28), date(2027, 1, 3)) == "Dec 28–Jan 3"
    assert week_range_words(date(2026, 12, 6), date(2027, 12, 12)) == "Dec 6–Dec 12"


def test_an_en_dash_not_a_hyphen():
    """The typographic dash, as every other range on the surface uses."""
    assert "–" in week_range_words(date(2026, 11, 8), date(2026, 11, 14))
    assert "-" not in week_range_words(date(2026, 11, 8), date(2026, 11, 14))


# ── the deadline, in all three tenses ────────────────────────────────────


def test_the_cutoff_day_says_TODAY():
    """James asked for "by 5:00pm today" on the cutoff day, by name."""
    w = _desc(WEEK_46_END)
    assert cutoff_words(w.cutoff_at, w.cutoff_at.date()) == (
        "Payentry needs it by 5:00pm today."
    )


def test_before_the_cutoff_the_WEEKDAY_is_named():
    w = _desc(WEEK_46_END)
    two_days_out = w.cutoff_at.date() - timedelta(days=2)
    assert cutoff_words(w.cutoff_at, two_days_out) == (
        "Payentry needs it by Wednesday 5:00pm."
    )


def test_past_the_cutoff_it_does_not_claim_a_FUTURE_deadline():
    """⚠️ **THE DEFECT, STATED AS THE THING THAT WAS ON THE SCREEN.** On the
    Thursday and Friday of the cycle the old line read "Payentry needs it by
    Wednesday 5:00pm" — a deadline five days out, naming one that had gone."""
    w = _desc(WEEK_46_END)
    for d in (w.cutoff_at.date() + timedelta(days=1),
              w.cutoff_at.date() + timedelta(days=2)):
        words = cutoff_words(w.cutoff_at, d)
        assert words == "Payentry's Wednesday 5:00pm cutoff has passed.", (d, words)
        assert "needs it by" not in words, (d, words)


def test_every_day_of_the_cycle_renders_exactly_one_true_tense():
    """⚠️ **ALL SEVEN DAYS, NOT THE ONE THE SUITE RUNS ON.** The line renders
    on each of the seven days between one Saturday and the next Friday, and
    the suite only ever sees today's. Each day is checked against which tense
    is TRUE of it rather than against a transcript, so the test states the
    rule rather than restating the implementation."""
    seen = set()
    for i in range(7):
        today = WEEK_46_END + timedelta(days=i)
        w = _desc(today)
        words = cutoff_words(w.cutoff_at, today)
        day = w.cutoff_at.date()
        if day > today:
            assert words.startswith("Payentry needs it by "), (today, words)
            assert "today" not in words, (today, words)
            seen.add("future")
        elif day == today:
            assert words.endswith("today."), (today, words)
            seen.add("today")
        else:
            assert "has passed" in words, (today, words)
            assert "needs it" not in words, (today, words)
            seen.add("past")
    # ⚠️ A POSITIVE CONTROL ON THE LOOP. Without this, a `_desc` that returned
    # the same week every day would satisfy every branch above by only ever
    # entering one of them, and the test would pass having checked a third of
    # what it claims.
    assert seen == {"future", "today", "past"}, seen


def test_no_tense_reads_as_a_demand():
    """⚠️ `compose` REFUSES PROSE THAT DEMANDS, and the past tense is where a
    rewrite would reach for one. "The cutoff has passed" reports; "You need to
    upload this immediately" would be a badge's work done through language."""
    from app.services.fragments.synthesis import BANNED_IMPERATIVES

    w = _desc(WEEK_46_END)
    for i in range(7):
        words = cutoff_words(w.cutoff_at, WEEK_46_END + timedelta(days=i)).lower()
        assert not [b for b in BANNED_IMPERATIVES if b in words], words


# ── which deferrals are still honest ─────────────────────────────────────


def test_no_deadline_leaves_every_affordance_standing():
    """The common case. A prompt with no cutoff is unchanged by this PR."""
    assert allowed_presets(today=date(2026, 11, 10), not_after=None) == (
        "tomorrow", "next_week", "next_month", "date",
    )


def test_a_cutoff_four_days_out_drops_the_two_that_overshoot():
    today = date(2026, 11, 14)
    assert allowed_presets(today=today, not_after=date(2026, 11, 18)) == (
        "tomorrow", "date",
    )


def test_on_the_cutoff_day_NOTHING_is_honest():
    """⚠️ **THE EMPTY TUPLE IS THE POINT.** The note draws no "See again" row
    at all here — not three disabled buttons, and not "Tomorrow" landing the
    reader a day past Payentry's deadline."""
    day = date(2026, 11, 18)
    assert allowed_presets(today=day, not_after=day) == ()


def test_past_the_cutoff_nothing_is_honest_either():
    assert allowed_presets(today=date(2026, 11, 20),
                           not_after=date(2026, 11, 18)) == ()


def test_the_picker_is_offered_only_while_the_deadline_is_AHEAD():
    """⚠️ Suppressing the presets and leaving the picker free would move the
    same dishonest choice one control to the right."""
    assert "date" in allowed_presets(today=date(2026, 11, 17),
                                     not_after=date(2026, 11, 18))
    assert "date" not in allowed_presets(today=date(2026, 11, 18),
                                         not_after=date(2026, 11, 18))


@pytest.mark.parametrize("preset", ["tomorrow", "next_week", "next_month"])
def test_an_allowed_preset_RESOLVES_to_a_date_within_the_deadline(preset):
    """⚠️ **THE AGREEMENT THAT MATTERS, AND THE REASON THIS LIVES IN PYTHON.**

    The obvious design served the deadline and let the client decide which of
    its three buttons overshoot — which would have put `_add_months` in
    TypeScript, free to disagree with the Python that actually records the
    deferral. This asserts the filter and the resolver agree by construction:
    every preset offered resolves to a date the deadline permits, for a whole
    year of days, which is a claim a second implementation cannot make.
    """
    for i in range(365):
        today = date(2026, 1, 1) + timedelta(days=i)
        for horizon in (1, 3, 8, 32, 400):
            not_after = today + timedelta(days=horizon)
            offered = allowed_presets(today=today, not_after=not_after)
            if preset in offered:
                assert resolve_preset(preset, today=today) <= not_after
            else:
                assert resolve_preset(preset, today=today) > not_after


def test_next_month_on_the_31st_is_the_servers_arithmetic_not_thirty_days():
    """⚠️ THE CASE A SECOND IMPLEMENTATION GETS WRONG. "Next month" from
    October 31st is November 30th — clamped to the month's last valid day, not
    `+30 days` and not the 31st of a 30-day month. A client doing its own
    filtering would have had to reproduce this."""
    assert resolve_preset("next_month", today=date(2026, 10, 31)) == date(2026, 11, 30)
