"""Who should have hours this week, and who has a reason not to — Payroll 3.

James's ruling, 2026-11-10: *"roster coverage: every hourly person paid in the
last 4 registers either has hours or a payroll status (workers_comp, leave,
left), otherwise flag 'no hours'. Staring (workers_comp since the Oct 8 check)
must not be flagged."*

⚠️ **THE POINT IS THE PERSON WHO IS MISSING, NOT THE PERSON WHO IS THERE.** An
hours file is complete-looking by nature: it lists who it lists, and nothing in
it says somebody is absent. The only way to notice that a person who was paid
for the last four weeks has vanished is to ask the registers who was being
paid and compare.

⚠️ **AND A CHECK THAT FLAGS THE SAME PEOPLE EVERY WEEK GETS SWITCHED OFF.**
Staring has been on workers_comp since the 2026-10-08 check and will appear in
the last four registers for a month after he stops being paid. `payroll_status`
is what keeps him out of the flag list — and a NULL status is a question, not
an exemption.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

#: Reasons a person legitimately has no hours. Anything else — including
#: nothing at all — is flagged.
EXCUSED_STATUSES = frozenset({"workers_comp", "leave", "left"})

#: How far back to look for "who is being paid". Four checks is about a month.
REGISTERS_LOOKBACK = 4

#: Earning codes that mean somebody was paid for TIME rather than salary.
HOURLY_EARNING_CODES = frozenset({"Reg", "OT", "PTO", "Sick", "Hol", "Ber", "Vac"})

#: ⚠️ **A `Sal` LINE ANYWHERE IN THE WINDOW MEANS SALARIED, WHATEVER ELSE THE
#: CHECK CARRIES.** My first version decided "hourly" from the codes above
#: alone and flagged Thurston, who is salaried at 1,918.25 a week — because
#: his 2026-10-22 check carries a `PTO 8.00` line at $0.00. Payroll 4 measured
#: that exact shape: 36 earning lines across 29 checks carry HOURS WITH NO
#: MONEY, all of them for salaried staff whose pay the salary already covers.
#: So any salaried person who takes a day off looks hourly to a code filter,
#: and the coverage check flags them every week for the rest of time.
SALARY_EARNING_CODE = "Sal"


@dataclass
class CoverageFinding:
    emp_id: str
    kind: str
    detail: str


def recent_check_dates(checks, *, before: date,
                       count: int = REGISTERS_LOOKBACK) -> list[date]:
    """The `count` most recent distinct check dates on or before `before`."""
    dates = sorted({c.check_date for c in checks
                    if c.check_date is not None and c.check_date <= before},
                   reverse=True)
    return dates[:count]


def hourly_people_recently_paid(checks, *, before: date,
                                count: int = REGISTERS_LOOKBACK) -> set[str]:
    """Employee ids paid for HOURS in the recent registers.

    ⚠️ Hourly, not everyone. A salaried person has no line in the Employee
    Hours report at all, so counting them here would flag every one of them
    every week — and there are five in the real register.
    """
    window = set(recent_check_dates(checks, before=before, count=count))
    hourly: set[str] = set()
    salaried: set[str] = set()
    for chk in checks:
        if chk.check_date not in window or not chk.emp_id:
            continue
        for line in chk.lines:
            if line.kind != "earning":
                continue
            if line.code == SALARY_EARNING_CODE:
                salaried.add(chk.emp_id)
            elif (line.code in HOURLY_EARNING_CODES
                    and (line.hours or Decimal("0")) != 0):
                hourly.add(chk.emp_id)
    # ⚠️ Salaried wins. A `Sal` line is positive evidence of how somebody is
    # paid; hours on a PTO line are not evidence of the opposite.
    return hourly - salaried


def check_roster_coverage(result, checks, *, week_check_date: date,
                          statuses: dict[str, str | None] | None = None
                          ) -> list[CoverageFinding]:
    """People recently paid for hours who have none this week and no reason."""
    statuses = statuses or {}
    expected = hourly_people_recently_paid(checks, before=week_check_date)
    present = set(result.hours_by_emp())
    out: list[CoverageFinding] = []
    for emp_id in sorted(expected - present, key=lambda e: (len(e), e)):
        status = statuses.get(emp_id)
        if status in EXCUSED_STATUSES:
            continue
        listed = emp_id in result.listed_without_hours
        out.append(CoverageFinding(
            emp_id=emp_id, kind="no_hours",
            detail=(f"employee {emp_id} was paid for hours in the last "
                    f"{REGISTERS_LOOKBACK} registers but has no hours this "
                    f"week and no payroll status"
                    + (" (listed in the file with no hours)" if listed
                       else " (not in the hours file at all)"))))
    return out
