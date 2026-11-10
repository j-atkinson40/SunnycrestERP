"""Salaried or hourly, decided once — Payroll 3 follow-up.

James's rule, 2026-11-10: *"Salaried = any `Sal` line in their last 4 checks;
hourly = a `Reg` line with a printed rate in their last 4 checks. Hours-only
$0.00 lines never make anyone hourly."*

⚠️ **ONE PLACE, BECAUSE TWO CHECKS GOT IT WRONG IN THE SAME WAY.** Roster
coverage flagged Thurston for having no hours, and the rate resolver flagged
Reilley as `missing_rate` — both because each had its own idea of "hourly" and
both read an hours-bearing line as evidence of it. Measured in Payroll 4: 36
earning lines across 29 checks carry HOURS WITH NO MONEY, every one of them on
a salaried person's check, because the salary already covers the pay. So any
salaried person who takes a day off looks hourly to a code filter.

⚠️ **AND THE EVIDENCE IS ASYMMETRIC, WHICH IS WHY THE RULE IS NOT A TEST ON
ONE FIELD.** A `Sal` line is positive proof of how somebody is paid. Hours on a
`PTO` line are not proof of the opposite — they are proof that a day was taken.
The only positive evidence of hourly pay is a `Reg` line with a rate printed
beside it, because that is Payentry stating the rate it multiplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

SALARIED = "salaried"
HOURLY = "hourly"
UNKNOWN = "unknown"

#: Positive evidence of salary.
SALARY_CODE = "Sal"

#: Positive evidence of hourly pay: this code, WITH a printed rate.
HOURLY_RATE_CODE = "Reg"

#: How far back to look. Four checks is about a month.
LOOKBACK_CHECKS = 4


@dataclass(frozen=True)
class Employment:
    emp_id: str
    kind: str
    #: Why, in a few words, so a finding can say it.
    because: str

    @property
    def is_salaried(self) -> bool:
        return self.kind == SALARIED

    @property
    def is_hourly(self) -> bool:
        return self.kind == HOURLY


def recent_check_dates(checks, *, before: date,
                       count: int = LOOKBACK_CHECKS) -> list[date]:
    dates = sorted({c.check_date for c in checks
                    if c.check_date is not None and c.check_date <= before},
                   reverse=True)
    return dates[:count]


def classify_employment(checks, *, before: date,
                        count: int = LOOKBACK_CHECKS) -> dict[str, Employment]:
    """How each employee was paid, over their last `count` check dates.

    ⚠️ **THE WINDOW IS PER EMPLOYEE, NOT GLOBAL.** Somebody who stopped being
    paid a month ago has no checks inside a global window, and a global window
    would classify them `unknown` and then exempt them from everything. Their
    last four checks are their last four, whenever they were.
    """
    per_emp: dict[str, list] = {}
    for chk in checks:
        if chk.emp_id and chk.check_date is not None:
            per_emp.setdefault(chk.emp_id, []).append(chk)

    out: dict[str, Employment] = {}
    for emp_id, their in per_emp.items():
        window = set(recent_check_dates(their, before=before, count=count))
        if not window:
            out[emp_id] = Employment(emp_id, UNKNOWN,
                                     f"no checks on or before {before}")
            continue
        has_salary = False
        has_rated_reg = False
        for chk in their:
            if chk.check_date not in window:
                continue
            for line in chk.lines:
                if line.kind != "earning":
                    continue
                if line.code == SALARY_CODE:
                    has_salary = True
                elif (line.code == HOURLY_RATE_CODE
                        and getattr(line, "rate", None) is not None):
                    has_rated_reg = True
        if has_salary:
            # ⚠️ Salary wins even when a rated Reg line is also present: a
            # salaried person can be paid some hourly work, and the thing that
            # matters downstream is that no hourly RATE is expected of them.
            out[emp_id] = Employment(emp_id, SALARIED,
                                     f"a {SALARY_CODE} line in the last "
                                     f"{count} checks")
        elif has_rated_reg:
            out[emp_id] = Employment(emp_id, HOURLY,
                                     f"a {HOURLY_RATE_CODE} line with a printed "
                                     f"rate in the last {count} checks")
        else:
            # ⚠️ NOT "hourly by default". Somebody paid only PTO at $0.00, or
            # only a bonus, is neither — and `unknown` is a question rather
            # than an assumption either way.
            out[emp_id] = Employment(emp_id, UNKNOWN,
                                     f"no {SALARY_CODE} line and no rated "
                                     f"{HOURLY_RATE_CODE} line in the last "
                                     f"{count} checks")
    return out
