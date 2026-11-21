"""When the R-115 is ready, and when it is due.

⚠️ **THE STAGE IS DERIVED, SO THE TESTS DRIVE THE CLOCK RATHER THAN THE DATA.**
Every case below names the day it is asking about. The alternative — asserting
whatever stage today produces — would pass every day and mean something
different on each of them, which is the shape that let the week line claim a
past deadline was five days out.

The October figures are the live production month (STATE 2026-11-17, and
`docs/specs/payroll-reports.md:564`): 13 members, 2,731.14 hours, $979.73,
check dates Oct 1/8/15/22/29.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.payroll import r115_schedule as S


class _Company:
    """Just enough Company to answer `get_setting`."""

    def __init__(self, value=None):
        self._value = value

    def get_setting(self, key, default=None):
        assert key == S.R115_DUE_DAY, f"unexpected setting read: {key!r}"
        return self._value if self._value is not None else default


# ── the calendar ─────────────────────────────────────────────────────────


def test_october_2026_check_dates_are_the_FIVE_production_saw():
    """⚠️ **THE GOLDEN, AND IT IS DERIVED RATHER THAN TYPED INTO THE SOURCE.**
    The live October R-115 covered Oct 1, 8, 15, 22 and 29. `CHECK_WEEKDAY`
    comes from `WEEK_END_WEEKDAY + CHECK_DATE_OFFSET`, so this fails if either
    constant moves — which is the point: the form's month boundaries would
    move with them."""
    assert [d.isoformat() for d in S.check_dates_in(2026, 10)] == [
        "2026-10-01", "2026-10-08", "2026-10-15", "2026-10-22", "2026-10-29",
    ]


def test_the_check_weekday_is_derived_from_the_week_end_and_the_offset(monkeypatch):
    """A third producer of "Thursday" is a third thing to update.

    ⚠️ **THIS RE-IMPORTS THE MODULE WITH THE CONSTANTS MOVED, BECAUSE THE
    OBVIOUS VERSION COULD NOT FAIL.** It first read:

        assert S.CHECK_WEEKDAY == (WEEK_END_WEEKDAY + CHECK_DATE_OFFSET.days) % 7

    — which is green whether `CHECK_WEEKDAY` is derived or typed as `3`,
    since Thursday IS 3 today. Break-tested: replacing the derivation with the
    literal left all 43 tests passing. An assertion that compares a value to
    itself-by-another-name cannot see the difference it exists to see.

    Moving the offset by a day and reloading makes the two answers diverge, so
    a literal fails and a derivation follows. CLAUDE.md §11 shape 9 — a check
    with full contact that asserts the wrong thing.
    """
    import importlib

    from app.services.payroll import service as payroll_service

    monkeypatch.setattr(payroll_service, "CHECK_DATE_OFFSET", timedelta(days=6))
    reloaded = importlib.reload(S)
    try:
        # Saturday + 6 = Friday. A hardcoded Thursday does not move.
        assert reloaded.CHECK_WEEKDAY == 4, (
            "CHECK_WEEKDAY did not follow CHECK_DATE_OFFSET — it is a literal, "
            "not a derivation"
        )
        assert reloaded.last_check_date_in(2026, 10) == date(2026, 10, 30), (
            "the month's last check did not move with the weekday"
        )
    finally:
        # ⚠️ RELOADED BACK UNDER THE REAL CONSTANT, in a `finally`. The module
        # object is shared; leaving it patched would hand every later test in
        # this process a Friday payroll calendar.
        monkeypatch.undo()
        importlib.reload(S)
    assert S.CHECK_WEEKDAY == 3, "the module was left patched"


def test_the_last_check_of_october_2026_is_the_29th():
    assert S.last_check_date_in(2026, 10) == date(2026, 10, 29)


@pytest.mark.parametrize("year,month", [(2026, m) for m in range(1, 13)]
                                       + [(2027, 2), (2028, 2)])
def test_every_month_has_four_or_five_check_dates(year, month):
    """⚠️ A POSITIVE CONTROL ON THE DERIVATION ITSELF. Every month contains at
    least four of any weekday; a derivation producing 0, 1 or 6 would be
    broken in a way the October golden alone could not see."""
    n = len(S.check_dates_in(year, month))
    assert 4 <= n <= 5, f"{year}-{month:02d} produced {n} check dates"


def test_the_check_dates_are_all_inside_the_month_asked_for():
    for y, m in ((2026, 1), (2026, 10), (2026, 12), (2028, 2)):
        for d in S.check_dates_in(y, m):
            assert (d.year, d.month) == (y, m), d


# ── filling vs ready ─────────────────────────────────────────────────────


def test_it_is_FILLING_while_a_check_can_still_land_in_the_month():
    for day in (1, 15, 28):
        assert S.stage_of(None, year=2026, month=10,
                          today=date(2026, 10, day)) == "filling", day


def test_it_is_still_FILLING_ON_the_last_check_day():
    """⚠️ "Ready AFTER the month's last check" — the checks are issued that
    day, so a form called ready that morning is ready before the money it
    reports has moved."""
    assert S.stage_of(None, year=2026, month=10,
                      today=date(2026, 10, 29)) == "filling"


def test_it_is_READY_the_day_after_the_last_check():
    assert S.stage_of(None, year=2026, month=10,
                      today=date(2026, 10, 30)) == "ready"
    assert S.stage_of(None, year=2026, month=10,
                      today=date(2026, 11, 18)) == "ready"


def test_a_month_with_no_form_yet_still_has_a_stage():
    """The screen that offers to BUILD the form has to say whether the month
    is finished. `None` is a real input here, not a missing one."""
    assert S.stage_of(None, year=2026, month=10, today=date(2026, 10, 2)) == "filling"
    assert S.stage_of(None, year=2026, month=10, today=date(2026, 11, 2)) == "ready"


# ── the stored statuses win over the calendar ────────────────────────────


class _Form:
    def __init__(self, status):
        self.status = status


def test_submitted_shows_as_APPROVED_and_filed_as_SENT():
    assert S.stage_of(_Form("submitted"), year=2026, month=10,
                      today=date(2026, 11, 2)) == "approved"
    assert S.stage_of(_Form("filed"), year=2026, month=10,
                      today=date(2026, 11, 2)) == "sent"


def test_an_approved_form_does_not_go_BACKWARDS_when_the_date_is_early():
    """⚠️ **THE CALENDAR ONLY DECIDES BETWEEN THE TWO DRAFT STAGES.** A form
    approved early — the month's checks all landed and somebody approved on
    the 20th — must not read "Filling" because the 29th has not arrived. A
    stage that can go backwards is a stage nobody trusts."""
    for status, expected in (("submitted", "approved"), ("filed", "sent")):
        assert S.stage_of(_Form(status), year=2026, month=10,
                          today=date(2026, 10, 20)) == expected


def test_every_stage_id_has_a_label():
    """A stage with no label renders as a `KeyError` on the one screen it
    exists for."""
    seen = set()
    for status in (None, "draft", "submitted", "filed"):
        form = _Form(status) if status else None
        for today in (date(2026, 10, 1), date(2026, 11, 1)):
            seen.add(S.stage_of(form, year=2026, month=10, today=today))
    assert seen <= set(S.STAGE_LABELS), seen - set(S.STAGE_LABELS)
    assert seen == {"filling", "ready", "approved", "sent"}, seen


# ── the due date ─────────────────────────────────────────────────────────


def test_no_setting_means_NO_DUE_DATE_rather_than_a_guessed_one():
    """⚠️ **UNLIKE THE DATA SWITCH, ABSENT STAYS ABSENT.** `data_gate` folds a
    missing value into `False` because the safe reading of "nobody said" is
    "not allowed". There is no safe default for a deadline — a printed date
    nobody agreed to is worse than a visible blank."""
    assert S.due_day(_Company(None)) is None
    assert S.due_date_for(_Company(None), 2026, 10) is None


def test_the_due_date_falls_in_the_month_AFTER_the_period():
    """The last check has to be issued before there is anything to remit."""
    assert S.due_date_for(_Company(15), 2026, 10) == date(2026, 11, 15)


def test_december_rolls_into_the_next_year():
    assert S.due_date_for(_Company(10), 2026, 12) == date(2027, 1, 10)


def test_a_31st_deadline_clamps_to_februarys_last_day_rather_than_rolling():
    """Rolling into March would move the deadline past the month it belongs
    to. Same rule as the deferral presets' `_add_months`."""
    assert S.due_date_for(_Company(31), 2027, 1) == date(2027, 2, 28)
    assert S.due_date_for(_Company(31), 2028, 1) == date(2028, 2, 29)
    assert S.due_date_for(_Company(31), 2026, 3) == date(2026, 4, 30)


@pytest.mark.parametrize("bad", [0, 32, 45, -1, True, False, "15", 15.0, None])
def test_a_value_that_is_not_a_day_reads_as_UNSET_rather_than_being_clamped(bad):
    """⚠️ `True` IS AN `int` IN PYTHON AND WOULD PASS AS DAY 1. Silently
    turning a 45 into the 31st would be this module inventing the deadline it
    refuses to invent two tests up."""
    assert S.due_day(_Company(bad)) is None


def test_a_real_day_survives_the_validation():
    """The positive control: without it, a `due_day` that returned `None` for
    everything would satisfy every case above."""
    for day in (1, 15, 28, 31):
        assert S.due_day(_Company(day)) == day


# ── the whole payload ────────────────────────────────────────────────────


def test_the_schedule_payload_carries_the_stage_AND_the_reason_for_it():
    """"Filling" without "until Oct 29" states a condition and withholds the
    thing that explains it."""
    s = S.schedule_for(_Company(15), form=None, year=2026, month=10,
                       today=date(2026, 10, 20))
    assert s["stage"] == "filling"
    assert s["stage_label"] == "Filling"
    assert s["last_check_date"] == "2026-10-29"
    assert s["check_dates"][-1] == "2026-10-29"
    assert len(s["check_dates"]) == 5
    assert s["due_date"] == "2026-11-15"
    assert s["due_day_setting"] == 15
    assert s["overdue"] is False


def test_the_payload_says_due_date_is_null_rather_than_wording_it():
    """⚠️ "No due date set" is the CLIENT's wording. A server that sent the
    sentence would be deciding copy, and the second surface would then have to
    match it by hand."""
    s = S.schedule_for(_Company(None), form=None, year=2026, month=10,
                       today=date(2026, 11, 2))
    assert s["due_date"] is None
    assert s["due_day_setting"] is None
    assert "No due date" not in repr(s)


def test_overdue_is_true_past_the_due_date_and_FALSE_once_sent():
    """A form filed late is not still overdue — the thing the flag asks for
    has happened."""
    late = date(2026, 11, 16)
    assert S.schedule_for(_Company(15), form=None, year=2026, month=10,
                          today=late)["overdue"] is True
    assert S.schedule_for(_Company(15), form=_Form("submitted"), year=2026,
                          month=10, today=late)["overdue"] is True
    assert S.schedule_for(_Company(15), form=_Form("filed"), year=2026,
                          month=10, today=late)["overdue"] is False


def test_overdue_is_false_when_no_due_date_is_configured():
    """Nothing can be late against a deadline nobody set."""
    assert S.schedule_for(_Company(None), form=None, year=2026, month=10,
                          today=date(2027, 6, 1))["overdue"] is False
