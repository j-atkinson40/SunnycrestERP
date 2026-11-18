"""Which payroll week it is, computed from today.

⚠️ **THIS EXISTS BECAUSE THERE WAS NO PATH TO THE FIRST UPLOAD.** Until now a
week descriptor came only from a `PayrollWeek` row, and that row is created BY
the upload — so with nothing uploaded the Focus could not open, the note had
nothing to say, and the Payroll page offered no link. The upload card lived
inside the surface the upload had to create. Measured 2026-11-17 on a live
tenant with the switch on, a register loaded and a reconciled roster: still no
way in.

So the week is derived from the calendar instead, and the row is created by the
upload rather than before it.

⚠️ **"THE CURRENT WEEK" IS THE WEEK BEING PROCESSED, NOT THE CALENDAR WEEK, AND
THE TWO DIFFER ON MOST DAYS.** On Tuesday 2026-11-17 the calendar week is
Nov 15–21; the week Susan works is **Nov 8–14**, which ended on Saturday and
whose checks are dated the 19th. James's own example — "Week 46 (Nov 8–14)",
written on the 17th — is the week that ENDED, and payroll is always worked in
arrears: you cannot pay hours that have not been worked yet.

So `current_payroll_week(today)` returns the week whose end is **the last
Saturday on or before today**. On a Saturday that is the day itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.services.payroll.hours_validation import WEEK_START_WEEKDAY
from app.services.payroll.service import CHECK_DATE_OFFSET

#: Saturday, in Python's weekday() where Monday is 0. The week runs
#: `WEEK_START_WEEKDAY` (Sunday) through here.
WEEK_END_WEEKDAY = (WEEK_START_WEEKDAY + 6) % 7


def week_end_for(on: date) -> date:
    """The Saturday that ends the payroll week containing `on`."""
    forward = (WEEK_END_WEEKDAY - on.weekday()) % 7
    return on + timedelta(days=forward)


def week_number_for(week_end: date) -> int:
    """Payentry's week number.

    ⚠️ **DERIVED FROM PRODUCTION, NOT CHOSEN.** The live week 44 ends
    2026-10-31, and `date(2026,10,31).isocalendar().week` is 44. Cross-checked
    a second way: counting Saturdays forward from that known pair gives 46 for
    2026-11-14, which is independently what James called that week. Two
    derivations that share no step agreeing is the reason this is a one-liner
    rather than an anchor table.
    """
    return week_end.isocalendar()[1]


@dataclass(frozen=True)
class PayrollWeekDescriptor:
    """A week that may or may not exist as a row yet."""

    week_number: int
    week_start_date: date
    week_end_date: date
    check_date: date
    #: When Payentry must have it. See `PayrollRules.payentry_cutoff_*`.
    cutoff_at: datetime

    def as_dict(self) -> dict:
        return {
            "week_number": self.week_number,
            "week_start_date": self.week_start_date.isoformat(),
            "week_end_date": self.week_end_date.isoformat(),
            "check_date": self.check_date.isoformat(),
            "cutoff_at": self.cutoff_at.isoformat(),
        }


def describe_week(week_end: date, *, cutoff_weekday: int, cutoff_time: time
                  ) -> PayrollWeekDescriptor:
    """Everything derivable about a week from its end date.

    `check_date = week_end + CHECK_DATE_OFFSET` — read from `service`, which is
    where that 5 is named once for the model, the importer and the tests.
    """
    start = week_end - timedelta(days=6)
    check = week_end + CHECK_DATE_OFFSET
    # The cutoff is the named weekday in the week the CHECKS fall in, which is
    # the week after the one being paid. Checks land Thursday; the cutoff is
    # the Wednesday before them.
    back = (check.weekday() - cutoff_weekday) % 7
    cutoff_day = check - timedelta(days=back)
    return PayrollWeekDescriptor(
        week_number=week_number_for(week_end),
        week_start_date=start,
        week_end_date=week_end,
        check_date=check,
        cutoff_at=datetime.combine(cutoff_day, cutoff_time),
    )


def current_week_end(today: date) -> date:
    """The END of the week being worked today — the last Saturday on or before.

    ⚠️ **SPLIT OUT 2026-11-18 SO A CALLER CAN ASK WHICH WEEK WITHOUT INVENTING A
    CUTOFF.** `current_payroll_week` needs the cutoff to describe the DEADLINE,
    and the cutoff has no bearing on which week ended. Opas's capability list
    needs only the date, and passing it a cutoff it does not use would be two
    arguments whose irrelevance the next reader has to re-derive — or, worse,
    would invite someone to pass the wrong ones and not notice.
    """
    return today - timedelta(days=(today.weekday() - WEEK_END_WEEKDAY) % 7)


def current_payroll_week(today: date, *, cutoff_weekday: int, cutoff_time: time
                         ) -> PayrollWeekDescriptor:
    """The week Susan is working today — the one that ended most recently."""
    return describe_week(current_week_end(today),
                         cutoff_weekday=cutoff_weekday, cutoff_time=cutoff_time)
