"""Validating an Employee Hours import when the file validates nothing itself.

Payroll 3. The register parser could check every figure against the register's
own printed totals. This report prints NO totals, so there is nothing internal
to disagree with — and "the totals match" is worse than no check at all here,
because a naive parse of the real export reproduces every hour total exactly
while reading one employee number as 12008.

So validation comes from four places, and only one of them is arithmetic:

  1. THE WEEK WINDOW    — every date inside one Sunday-Saturday week, and that
                          week the one that was asked for.
  2. IDENTITY           — every employee id exists in the register or the
                          roster, and resolves to exactly one name. ⚠️ THIS IS
                          THE CHECK THAT CATCHES 12008, and no total can.
  3. THE PUNCH CLOCK    — daily hours against the clock times (Phase 2).
  4. THE REGISTER       — the week's hours against the check Payentry actually
                          issued for it, which lands five days after week end.

⚠️ **AN IMPORT WITH AN UNKNOWN EMPLOYEE ID STOPS.** It does not import the rows
it recognised and warn about the rest. A week filed against a person who does
not exist is a week whose dues are wrong for someone, and the only safe
default is to refuse the file and name the id.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

#: Payentry's payroll week. Sunday through Saturday.
WEEK_START_WEEKDAY = 6          # Python: Monday=0 … Sunday=6

#: The check for a week is dated five days after the week ends — measured on
#: the real data: week 44 ends Saturday 2026-10-31 and its checks are dated
#: Thursday 2026-11-05.
CHECK_LAG_DAYS = 5

#: Employee Hours pay type -> the register's earning code for the same thing.
PAY_TYPE_TO_REGISTER_CODE = {
    "REG": "Reg",
    "OT1": "OT",
    "PTO": "PTO",
    "Sick": "Sick",
}


@dataclass
class Finding:
    """Something a person has to look at. Never a number on its own."""

    kind: str
    detail: str
    #: True when this must stop the import rather than be noted beside it.
    blocking: bool = False


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)

    def add(self, kind: str, detail: str, *, blocking: bool = False) -> None:
        self.findings.append(Finding(kind, detail, blocking))

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.blocking]

    @property
    def ok(self) -> bool:
        return not self.blocking

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.kind] = out.get(f.kind, 0) + 1
        return out


def week_bounds(any_day: date) -> tuple[date, date]:
    """The Sunday-to-Saturday week containing `any_day`."""
    back = (any_day.weekday() - WEEK_START_WEEKDAY) % 7
    start = any_day - timedelta(days=back)
    return start, start + timedelta(days=6)


def check_date_for_week(week_end: date) -> date:
    return week_end + timedelta(days=CHECK_LAG_DAYS)


def validate_week_window(result, *, expected_week_end: date) -> ValidationReport:
    """Check 1 — every date in one week, and that week the expected one.

    ⚠️ **BLOCKING.** A file covering two weeks, or a different week from the one
    requested, would be imported against the wrong week and every figure
    downstream would be attributed to the wrong seven days.
    """
    report = ValidationReport()
    dates = sorted({l.work_date for l in result.lines})
    if not dates:
        report.add("no_dates", "the parse produced no dated lines at all",
                   blocking=True)
        return report

    start, end = week_bounds(dates[0])
    outside = [d for d in dates if not (start <= d <= end)]
    if outside:
        report.add("spans_more_than_one_week",
                   f"dates {[d.isoformat() for d in outside]} fall outside the "
                   f"Sun {start} - Sat {end} week of the first date",
                   blocking=True)
    if end != expected_week_end:
        report.add("wrong_week",
                   f"the file covers the week ending {end}, not the requested "
                   f"{expected_week_end}", blocking=True)
    # ⚠️ Reported, never blocking: a week with no Sunday hours is normal.
    missing = [ (start + timedelta(days=i)).isoformat()
                for i in range(7) if (start + timedelta(days=i)) not in dates ]
    if missing:
        report.add("days_with_no_hours", f"no hours recorded on {missing}")
    return report


def validate_identity(result, *, known_emp_ids: set[str],
                      source: str = "register or roster") -> ValidationReport:
    """Check 2 — every id is real and every id means one person.

    ⚠️ **THIS IS THE CHECK THAT WOULD HAVE CAUGHT 12008, AND IT IS THE ONLY
    ONE THAT COULD.** The corrupted id came with correct hours, a correct date
    and a correct pay type; the only thing wrong with it was that no such
    employee exists. Arithmetic cannot see that. A roster can.

    ⚠️ **BLOCKING, per James's ruling of 2026-11-10.** An unknown id stops the
    import. Importing the recognised rows and warning about the rest would
    file a partial week whose totals look plausible.
    """
    report = ValidationReport()
    unknown = sorted(result.emp_ids - known_emp_ids, key=lambda e: (len(e), e))
    if unknown:
        report.add("unknown_emp_id",
                   f"employee id(s) {unknown} are in the hours file but not in "
                   f"the {source}. This is what a mis-read id looks like: "
                   f"correct hours against a person who does not exist.",
                   blocking=True)
    for emp_id, names in sorted(result.ambiguous_names.items()):
        report.add("one_id_two_names",
                   f"employee id {emp_id} appears under {sorted(names)}; an id "
                   f"must mean one person", blocking=True)
    return report


@dataclass
class HoursVsRegisterRow:
    emp_id: str
    pay_type: str
    hours_file: Decimal
    register_hours: Decimal

    @property
    def difference(self) -> Decimal:
        return self.hours_file - self.register_hours

    @property
    def agrees(self) -> bool:
        return self.difference == 0


def compare_with_register(result, checks, *, week_end: date
                          ) -> tuple[list[HoursVsRegisterRow], ValidationReport]:
    """Check 4 — the week's hours against the check Payentry issued for it.

    `checks` is any iterable of parsed or stored register checks (anything with
    `emp_id`, `check_date` and `lines`). Only checks dated `week_end + 5` are
    considered; see `CHECK_LAG_DAYS`.

    ⚠️ **REPORTED, NOT BLOCKING.** A disagreement here can be the hours file,
    the register, or a genuine adjustment Payentry made between the two — and
    Payroll 4 already measured 76 checks where computed dues and charged dues
    differ for reasons nobody has settled. Stopping an import on it would stop
    every import.
    """
    want = check_date_for_week(week_end)
    report = ValidationReport()
    relevant = [c for c in checks if getattr(c, "check_date", None) == want]
    if not relevant:
        report.add("no_check_for_week",
                   f"no register check dated {want} ({CHECK_LAG_DAYS} days after "
                   f"week end {week_end}); the hours cannot be compared")
        return [], report

    reg_hours: dict[str, dict[str, Decimal]] = {}
    for chk in relevant:
        per = reg_hours.setdefault(chk.emp_id, {})
        for line in chk.lines:
            if line.kind != "earning":
                continue
            per[line.code] = per.get(line.code, Decimal("0")) + (
                line.hours or Decimal("0"))

    rows: list[HoursVsRegisterRow] = []
    file_hours = result.hours_by_emp()
    for emp_id in sorted(set(file_hours) | set(reg_hours), key=lambda e: (len(e), e)):
        for pay_type, code in PAY_TYPE_TO_REGISTER_CODE.items():
            a = file_hours.get(emp_id, {}).get(pay_type, Decimal("0"))
            b = reg_hours.get(emp_id, {}).get(code, Decimal("0"))
            if a == 0 and b == 0:
                continue
            rows.append(HoursVsRegisterRow(emp_id, pay_type, a, b))
    for row in rows:
        if not row.agrees:
            report.add("hours_differ_from_register",
                       f"emp {row.emp_id} {row.pay_type}: hours file "
                       f"{row.hours_file}, register {row.register_hours} "
                       f"(diff {row.difference})")
    return rows, report


def validate_import(result, *, expected_week_end: date, known_emp_ids: set[str],
                    checks=None) -> ValidationReport:
    """Every check that does not need the punch file, in one call.

    ⚠️ **ORDER MATTERS.** The week window and identity run first and can block;
    the register comparison is advisory and runs last, so a blocked import does
    not also emit a wall of hour differences that nobody should act on yet.
    """
    report = ValidationReport()
    report.findings += validate_week_window(
        result, expected_week_end=expected_week_end).findings
    report.findings += validate_identity(
        result, known_emp_ids=known_emp_ids).findings
    if result.unknown_pay_types:
        report.add("unknown_pay_type",
                   f"pay type(s) {sorted(result.unknown_pay_types)} are not in "
                   f"the known set; reported rather than dropped")
    if result.unreadable_rows:
        report.add("unreadable_row",
                   f"{len(result.unreadable_rows)} row(s) looked like data and "
                   f"could not be read: {result.unreadable_rows[:5]}",
                   blocking=True)
    if checks is not None and report.ok:
        report.findings += compare_with_register(
            result, checks, week_end=expected_week_end)[1].findings
    return report
