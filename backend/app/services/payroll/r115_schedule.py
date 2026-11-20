"""When the R-115 is ready, and when it is due — Payroll 5b.

Two facts the stored form does not carry, because neither is an act anybody
performs:

  * **READY** is a fact about the CALENDAR. A month's form is still being
    filled while checks can still land in it, and ready once the month's last
    check has been issued. Nobody decides that; the date arrives.
  * **DUE** is a fact about the TENANT's agreement with its local. It is a
    standing setting an admin edits, not a property of any one month.

⚠️ **NEITHER IS A STORED STATUS, AND THAT IS THE DESIGN.** The obvious shape
was a fourth value in `R115_STATUSES` — `draft -> ready -> submitted -> filed`.
A stored `ready` would have to be WRITTEN by something when a date passes: a
nightly sweep, or a lazy write on read. Both can fail to run, and a form that
says `draft` because the sweep did not fire is wrong in a way nothing reports.
Derived, it cannot drift: the answer is recomputed from today's date every time
anybody looks.

It also keeps the migrated CHECK constraint and `R115_TRANSITIONS` untouched —
`filed` stays terminal by having no map entry, which is the property that
stops the next person adding an `elif` past it.

### The vocabulary, and where it comes from

James's brief, 2026-11-18: *"filling → ready after the month's last check →
approve → print view → mark sent"*. The spec (§11.8) names the stored flow
`draft -> submitted -> filed`. These are the same machine under two names, and
this module is the ONE place the two are mapped, so a screen cannot invent a
third spelling:

    stored      shown        the act that reaches it
    ─────────────────────────────────────────────────
    draft       Filling      the register is imported     (before the last check)
    draft       Ready        the month's last check lands (nobody acts)
    submitted   Approved     Approve
    filed       Sent         Mark sent

`print view` is a VIEW of a form, not a stage — a reader can print a Ready form
and print it again after it is Sent, and neither printing moves it.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from app.services.payroll import r115_settings as _settings
from app.services.payroll.service import CHECK_DATE_OFFSET
from app.services.payroll.week_calendar import WEEK_END_WEEKDAY

#: The weekday checks fall on, in Python's Monday=0. **DERIVED, NOT TYPED.**
#: A payroll week ends on `WEEK_END_WEEKDAY` and its checks are dated
#: `CHECK_DATE_OFFSET` later, so writing `3` here would be a third producer of
#: a fact those two already settle — and it would go on saying Thursday on the
#: day somebody moves the check offset.
#:
#: Verified against the live October 2026 month: this yields Oct 1, 8, 15, 22,
#: 29, which is exactly the set the production R-115 covered.
CHECK_WEEKDAY: int = (WEEK_END_WEEKDAY + CHECK_DATE_OFFSET.days) % 7

#: Re-exported from `r115_settings`, which owns every R-115 settings key.
#: ⚠️ DEFINED THERE AND IMPORTED HERE, not spelled twice: this module briefly
#: carried its own copy of the literal, which is exactly the two-producers
#: shape that lets one move without the other.
R115_DUE_DAY = _settings.R115_DUE_DAY

#: What the reader is shown, keyed by the stage ids this module returns.
STAGE_LABELS: dict[str, str] = {
    "filling": "Filling",
    "ready": "Ready",
    "approved": "Approved",
    "sent": "Sent",
}


def check_dates_in(year: int, month: int) -> list[date]:
    """Every date in the month that a payroll check falls on.

    ⚠️ **THE CALENDAR'S ANSWER, NOT THE REGISTER'S.** Asking the register which
    check dates a month has can only report the ones already IMPORTED, so a
    month with one register loaded would look complete. The question "can more
    checks still land in this month" is a question about the calendar, and the
    calendar can answer it before any file arrives.
    """
    last = calendar.monthrange(year, month)[1]
    return [d for d in (date(year, month, n) for n in range(1, last + 1))
            if d.weekday() == CHECK_WEEKDAY]


def last_check_date_in(year: int, month: int) -> date:
    """The month's final check date — the day after which it can gain no more.

    Every month contains at least four of any weekday, so this cannot be
    empty; `check_dates_in` returning nothing would mean the weekday derivation
    is broken, and raising is better than returning a date nobody can explain.
    """
    dates = check_dates_in(year, month)
    if not dates:
        raise ValueError(
            f"no check dates derived for {year}-{month:02d} — CHECK_WEEKDAY "
            f"is {CHECK_WEEKDAY}, which cannot be right: every month holds at "
            "least four of every weekday."
        )
    return dates[-1]


def current_form_period(today: date) -> tuple[int, int]:
    """The month whose R-115 is the one to act on today.

    The latest month whose last check has already been issued — so through
    November, the form in play is October's, and it becomes November's only
    once November's final check has landed.

    ⚠️ **NOT "LAST MONTH".** On the 30th of a month whose last check fell on
    the 26th, this month's form is the actionable one and a naive "today minus
    one month" would send the reader back to a month they already sent. The
    question is about the payroll calendar, not about the calendar.
    """
    y, m = today.year, today.month
    if today > last_check_date_in(y, m):
        return y, m
    return (y - 1, 12) if m == 1 else (y, m - 1)


def due_day(company) -> int | None:
    """The configured day of the following month, or `None` if unset.

    ⚠️ **ABSENT MEANS ABSENT HERE, UNLIKE THE DATA SWITCH.** `data_gate`
    collapses a missing value to `False` on purpose, because the safe reading
    of "nobody has said" is "not allowed". There is no safe default for a
    deadline: inventing the 15th would print a date on a form that nobody
    agreed to, and a wrong deadline is worse than a visible absence. The screen
    says "No due date set", which is the honest thing and is also the thing
    that gets somebody to go and set it.

    A stored value outside 1..31 is treated as unset rather than clamped. It
    can only arrive by someone writing the setting directly, and silently
    turning a 45 into the 31st would be this module inventing the deadline it
    just refused to invent.
    """
    raw = company.get_setting(R115_DUE_DAY, None)
    if isinstance(raw, bool) or not isinstance(raw, int):
        # ⚠️ `bool` first: `True` is an `int` in Python and would pass as day 1.
        return None
    return raw if 1 <= raw <= 31 else None


def due_date_for(company, year: int, month: int) -> date | None:
    """The date this month's form is due, or `None` when no day is set.

    The form for a month is filed in the month AFTER it — the last check has
    to have been issued before there is anything to remit — so the configured
    day is read in the following month.

    ⚠️ **CLAMPED TO THE MONTH'S LAST DAY, NEVER ROLLED FORWARD.** A tenant
    whose local wants the 31st has a February deadline of the 28th or 29th;
    rolling into March would move the deadline past the month it belongs to.
    Same rule as `deferral._add_months`, for the same reason.
    """
    day = due_day(company)
    if day is None:
        return None
    y, m = (year + 1, 1) if month == 12 else (year, month + 1)
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def stage_of(form, *, year: int, month: int, today: date) -> str:
    """Which of the four stages the reader should be shown.

    `form` may be `None` — a month whose form has not been built yet is still
    `filling` or `ready`, and the screen offering to build it needs to say
    which.

    ⚠️ **A SUBMITTED OR FILED FORM IS NEVER "FILLING" AGAIN, WHATEVER THE DATE
    SAYS.** The calendar question only decides between the two DRAFT stages.
    Letting the date reach a form that has been approved would mean a form
    going backwards on screen because somebody re-ran it in a new month.
    """
    status = getattr(form, "status", None) if form is not None else None
    if status == "submitted":
        return "approved"
    if status == "filed":
        return "sent"
    return "ready" if today > last_check_date_in(year, month) else "filling"


def schedule_for(company, *, form, year: int, month: int, today: date) -> dict:
    """Everything a screen needs to say where this month stands.

    One call, so the stage and the dates behind it cannot be fetched from two
    places and disagree. `last_check_date` is served alongside the stage
    because "Filling" without "until Oct 29" tells the reader a state and not
    a reason.
    """
    last_check = last_check_date_in(year, month)
    due = due_date_for(company, year, month)
    return {
        "stage": stage_of(form, year=year, month=month, today=today),
        "stage_label": STAGE_LABELS[stage_of(form, year=year, month=month,
                                             today=today)],
        "last_check_date": last_check.isoformat(),
        "check_dates": [d.isoformat() for d in check_dates_in(year, month)],
        "due_date": due.isoformat() if due else None,
        #: ⚠️ SERVED AS A FACT, NOT AS A RENDERED STRING. "No due date set" is
        #: the client's wording for `due_date == null`; a server that sent the
        #: sentence would be deciding copy, and a second surface would then
        #: have to match it by hand.
        "due_day_setting": due_day(company),
        "overdue": bool(due and today > due and
                        stage_of(form, year=year, month=month,
                                 today=today) != "sent"),
    }
