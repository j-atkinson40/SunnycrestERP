"""The overtime rules, used to CHECK Payentry rather than to recompute — P3.

James's ruling, 2026-11-10: *"Bridgeable doesn't recalculate overtime.
Payentry already splits REG and OT1. Flag only the days where Payentry's split
disagrees with these rules."*

⚠️ **THAT DIRECTION IS THE WHOLE DESIGN.** Payentry runs the payroll and its
split is what people were paid. If Bridgeable computed its own split and used
it, every rounding difference would become a pay dispute and Bridgeable would
be quietly asserting authority it does not have. Computing the split only to
COMPARE turns the same arithmetic into a question — "Payentry gave this day 1.5
OT and the rule implies 2.0; which is right?" — that a person can answer.

The rules, confirmed by Payentry's own split (James, 2026-11-10):

    depts 101 (Delivery) and 103 (Production)
        overtime after 8 hours in a DAY, and EVERY Saturday hour is overtime
    depts 106 (Supervisor), 107 (Office), 108 (Sales)
        overtime after 40 hours in the WEEK
        and 30 minutes deducted automatically on a 9.5-hour day

⚠️ **THE LUNCH DEDUCTION IS ALREADY IN THE FILE AND MUST NOT BE APPLIED
AGAIN.** Payentry prints it as a `-0.50` REG line — measured: employee 20 has
four of them in week 44. Summing the REG lines already nets it out, so a rule
that subtracted another half hour would disagree with Payentry on every
9.5-hour day and the flag would fire for everyone. The deduction is checked
for PRESENCE, not reapplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")

#: Daily-overtime departments: after 8 hours a day, and all of Saturday.
DAILY_OT_DEPTS = frozenset({"101", "103"})

#: Weekly-overtime departments: after 40 hours in the week.
WEEKLY_OT_DEPTS = frozenset({"106", "107", "108"})

#: Departments whose 9.5-hour days carry an automatic 30-minute deduction.
AUTO_LUNCH_DEPTS = frozenset({"106", "107", "108"})

DAILY_OT_THRESHOLD = Decimal("8")
WEEKLY_OT_THRESHOLD = Decimal("40")
AUTO_LUNCH_HOURS = Decimal("-0.50")
AUTO_LUNCH_TRIGGER_DAY = Decimal("9.5")

SATURDAY = 5                    # Python weekday(): Monday=0

#: Pay types that count as time worked. PTO and Sick are paid but not worked,
#: so they do not earn overtime under either rule.
WORKED_PAY_TYPES = ("REG", "OT1")

#: Provenance for every figure this module produces, per the brief.
RULE_STATUS = "from_registers"
RULE_SOURCE = "Employee Hours wk44 + registers"


@dataclass
class OvertimeDisagreement:
    emp_id: str
    dept: str | None
    scope: str                  # "day" or "week"
    on_date: date | None
    worked: Decimal
    payentry_ot: Decimal
    rule_ot: Decimal
    rule: str
    status: str = RULE_STATUS
    source: str = RULE_SOURCE

    @property
    def difference(self) -> Decimal:
        return self.payentry_ot - self.rule_ot


def _worked(lines) -> Decimal:
    return sum((l.hours for l in lines if l.pay_type in WORKED_PAY_TYPES), ZERO)


def _ot(lines) -> Decimal:
    return sum((l.hours for l in lines if l.pay_type == "OT1"), ZERO)


def check_overtime_split(result, *, dept_of=None) -> list[OvertimeDisagreement]:
    """Compare Payentry's REG/OT1 split against the rules. Reports only.

    `dept_of` maps an emp_id to its department code; by default the home
    department on the employee's own lines is used.
    """
    out: list[OvertimeDisagreement] = []
    per_emp: dict[str, list] = {}
    for line in result.lines:
        per_emp.setdefault(line.emp_id, []).append(line)

    for emp_id, lines in sorted(per_emp.items(), key=lambda kv: (len(kv[0]), kv[0])):
        dept = (dept_of or {}).get(emp_id) or next(
            (l.home_dept for l in lines if l.home_dept), None)

        if dept in DAILY_OT_DEPTS:
            by_day: dict[date, list] = {}
            for line in lines:
                by_day.setdefault(line.work_date, []).append(line)
            for when, todays in sorted(by_day.items()):
                worked = _worked(todays)
                payentry = _ot(todays)
                if when.weekday() == SATURDAY:
                    # ⚠️ EVERY Saturday hour, not the hours beyond eight.
                    rule_ot, rule = worked, "every Saturday hour is overtime"
                else:
                    rule_ot = max(ZERO, worked - DAILY_OT_THRESHOLD)
                    rule = f"overtime after {DAILY_OT_THRESHOLD} hours in a day"
                if rule_ot != payentry:
                    out.append(OvertimeDisagreement(
                        emp_id=emp_id, dept=dept, scope="day", on_date=when,
                        worked=worked, payentry_ot=payentry, rule_ot=rule_ot,
                        rule=rule))

        elif dept in WEEKLY_OT_DEPTS:
            worked = _worked(lines)
            payentry = _ot(lines)
            rule_ot = max(ZERO, worked - WEEKLY_OT_THRESHOLD)
            if rule_ot != payentry:
                out.append(OvertimeDisagreement(
                    emp_id=emp_id, dept=dept, scope="week", on_date=None,
                    worked=worked, payentry_ot=payentry, rule_ot=rule_ot,
                    rule=f"overtime after {WEEKLY_OT_THRESHOLD} hours in the week"))
    return out


@dataclass
class LunchFinding:
    emp_id: str
    dept: str | None
    on_date: date
    day_hours: Decimal
    detail: str
    status: str = RULE_STATUS
    source: str = RULE_SOURCE


def check_auto_lunch(result, *, dept_of=None) -> list[LunchFinding]:
    """Days in 106/107/108 that should carry the 30-minute deduction and don't.

    ⚠️ **PRESENCE, NOT REAPPLICATION.** Payentry already prints the deduction
    as a `-0.50` REG line. This looks for a 9.5-hour day with no such line —
    the shape of a day where the deduction was missed — and says nothing about
    days that have it.
    """
    out: list[LunchFinding] = []
    per: dict[tuple[str, date], list] = {}
    for line in result.lines:
        per.setdefault((line.emp_id, line.work_date), []).append(line)

    for (emp_id, when), lines in sorted(per.items(), key=lambda kv: (len(kv[0][0]),
                                                                    kv[0][0], kv[0][1])):
        dept = (dept_of or {}).get(emp_id) or next(
            (l.home_dept for l in lines if l.home_dept), None)
        if dept not in AUTO_LUNCH_DEPTS:
            continue
        has_deduction = any(l.hours == AUTO_LUNCH_HOURS for l in lines)
        gross = sum((l.hours for l in lines
                     if l.pay_type in WORKED_PAY_TYPES and l.hours > 0), ZERO)
        if gross >= AUTO_LUNCH_TRIGGER_DAY and not has_deduction:
            out.append(LunchFinding(
                emp_id=emp_id, dept=dept, on_date=when, day_hours=gross,
                detail=(f"{gross} hours recorded with no {AUTO_LUNCH_HOURS} "
                        f"lunch line, in a department where the deduction is "
                        f"automatic on a {AUTO_LUNCH_TRIGGER_DAY}-hour day")))
    return out
