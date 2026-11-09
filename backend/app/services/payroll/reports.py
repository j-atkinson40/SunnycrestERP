"""Weekly payroll reports — structured data plus CSV.

Pure functions over already-computed rows. No DB; the service layer loads rows
and hands them in, which keeps every report testable against literal figures.

⚠️ **EVERY TABLE CARRIES ITS OWN DENOMINATOR.** `totals["row_count"]` is emitted
on every report, always, next to the money. This is not decoration: the defect
that prompted it was a stated hours total computed over twelve of thirteen rows
while the dues and wage totals on the SAME report covered all thirteen, and
nothing in the three numbers said they had different populations (spec §7.1,
CLAUDE.md §11 "a gate reports its denominator"). A total printed beside its row
count cannot do that silently.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.services.payroll.engine import DuesResult
from app.services.payroll.money import round2

ZERO = Decimal("0")


@dataclass(frozen=True)
class MemberDuesRow:
    """One member's computed dues for one week, with the identity to report it."""

    employee_id: str
    file_number: str
    display_name: str
    result: DuesResult
    dept: str | None = None
    week_end_date: date | None = None
    check_date: date | None = None


@dataclass(frozen=True)
class ReportTable:
    report_key: str
    columns: tuple[tuple[str, str], ...]     # (key, label)
    rows: tuple[dict, ...]
    totals: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.rows)


def _money(v: Decimal | None) -> str | None:
    return None if v is None else str(round2(v))


def fmt_exact(v: Decimal | None) -> str | None:
    """Canonical exact-decimal string: trailing zeros stripped, never exponent notation.

    ⚠️ `Decimal.normalize()` ALONE IS WRONG HERE AND THE BUG IS INVISIBLE ON
    MOST VALUES. `Decimal("52.8000").normalize()` is `52.8`, which is what you
    want — but `Decimal("40.0000").normalize()` is `4E+1`, so a 40-hour week
    would render as "4E+1" on the report. Every whole-number hours value that is
    a multiple of ten hits it, which is most full weeks.

    It also has to be the SAME formatter for rows and for totals. Using
    `normalize()` for rows and bare `str()` for totals is what produced a report
    whose member rows read `47` beside a total reading `520.4400` — the same
    quantity in two notations, found by an end-to-end assertion rather than by
    reading the code.
    """
    if v is None:
        return None
    q = v.normalize()
    if q == q.to_integral_value():
        q = q.quantize(Decimal(1))
    return str(q)


#: Hours and full-precision wage totals are the same formatting problem: strip
#: the trailing zeros a Numeric column's scale adds, without ever emitting
#: exponent notation. One function, so rows and totals cannot diverge.
fmt_hours = fmt_exact
_hours = fmt_exact


def weekly_dues_detail(rows: list[MemberDuesRow]) -> ReportTable:
    """Per member: wage, hours, a, b, c, dues — plus totals over ALL rows."""
    columns = (
        ("file_number", "File #"),
        ("display_name", "Name"),
        ("dept", "Dept"),
        ("dues_wage", "Dues wage"),
        ("dues_hours", "Dues hours"),
        ("component_a", "a (pct)"),
        ("component_b", "b (cap)"),
        ("component_c", "c (per hr)"),
        ("binds", "Binds"),
        ("initiation_fee", "Initiation"),
        ("dues", "Dues"),
    )
    out = []
    for r in rows:
        d = r.result
        out.append({
            "employee_id": r.employee_id,
            "file_number": r.file_number,
            "display_name": r.display_name,
            "dept": r.dept,
            "dues_wage": _money(d.dues_wage),
            "dues_hours": _hours(d.dues_hours),
            "component_a": _money(d.component_a),
            "component_b": _money(d.component_b),
            "component_c": _money(d.component_c),
            "binds": d.binds,
            "initiation_fee": _money(d.initiation_fee),
            "dues": _money(d.dues),
            "ot_rate_used": str(r.result.ot_rate_used),
            "ot_rate_derived": d.ot_rate_derived,
        })

    # ⚠️ EVERY ROW IS IN EVERY TOTAL. No filter, no slice, no skip-if-zero.
    # `row_count` states the population so the three totals can be checked
    # against each other by a reader.
    # ⚠️ TOTALS USE THE SAME FORMATTERS AS THE ROWS. See fmt_hours.
    totals = {
        "row_count": len(rows),
        "dues_wage": fmt_exact(sum((r.result.dues_wage for r in rows), ZERO)),
        "dues_wage_rounded": _money(sum((r.result.dues_wage for r in rows), ZERO)),
        "dues_hours": fmt_exact(sum((r.result.dues_hours for r in rows), ZERO)),
        "initiation_fee": _money(sum((r.result.initiation_fee for r in rows), ZERO)),
        "dues": _money(sum((r.result.dues for r in rows), ZERO)),
    }
    return ReportTable("weekly_dues_detail", columns, tuple(out), totals)


def employee_dues_deduction(rows: list[MemberDuesRow]) -> ReportTable:
    """What goes on the deduction register: name and dues, and the total."""
    columns = (
        ("file_number", "File #"),
        ("display_name", "Name"),
        ("dues", "Dues"),
    )
    out = [
        {
            "employee_id": r.employee_id,
            "file_number": r.file_number,
            "display_name": r.display_name,
            "dues": _money(r.result.dues),
        }
        for r in rows
    ]
    totals = {
        "row_count": len(rows),
        "dues": _money(sum((r.result.dues for r in rows), ZERO)),
    }
    return ReportTable("employee_dues_deduction", columns, tuple(out), totals)


def monthly_dues_remittance(
    rows: list[MemberDuesRow],
    *,
    year: int,
    month: int,
    group_by: str = "week_end_date",
) -> ReportTable:
    """Per member sum for one calendar month.

    ⚠️ `group_by` DECIDES WHICH MONTH A WEEK BELONGS TO, and the two settings
    disagree for any week straddling a month boundary — week 44 (w/e 2026-10-31,
    check date 2026-11-05) lands in OCTOBER under `week_end_date` and NOVEMBER
    under `check_date`. Default is `week_end_date`, pending the accountant's
    confirmation (spec §7.3). The setting in force is echoed in `meta` so a
    stored report says which rule produced it rather than leaving a reader to
    assume the current default was the one used.
    """
    if group_by not in ("week_end_date", "check_date"):
        raise ValueError(f"group_by must be week_end_date or check_date, got {group_by!r}")

    per_member: dict[str, dict] = {}
    weeks_seen: set = set()
    considered = 0

    for r in rows:
        key_date = r.week_end_date if group_by == "week_end_date" else r.check_date
        if key_date is None:
            raise ValueError(
                f"row for {r.file_number} has no {group_by}; a remittance row "
                f"cannot be grouped without its grouping key"
            )
        if (key_date.year, key_date.month) != (year, month):
            continue
        considered += 1
        weeks_seen.add(key_date)
        slot = per_member.setdefault(
            r.employee_id,
            {
                "employee_id": r.employee_id,
                "file_number": r.file_number,
                "display_name": r.display_name,
                "weeks": 0,
                "_dues": ZERO,
                "_hours": ZERO,
            },
        )
        slot["weeks"] += 1
        slot["_dues"] += r.result.dues
        slot["_hours"] += r.result.dues_hours

    out = []
    for slot in sorted(per_member.values(), key=lambda s: s["file_number"]):
        out.append({
            "employee_id": slot["employee_id"],
            "file_number": slot["file_number"],
            "display_name": slot["display_name"],
            "weeks": slot["weeks"],
            "dues_hours": fmt_exact(slot["_hours"]),
            "dues": _money(slot["_dues"]),
        })

    columns = (
        ("file_number", "File #"),
        ("display_name", "Name"),
        ("weeks", "Weeks"),
        ("dues_hours", "Dues hours"),
        ("dues", "Dues"),
    )
    totals = {
        "row_count": len(out),
        "dues": _money(sum((Decimal(r["dues"]) for r in out), ZERO)),
        "dues_hours": fmt_exact(sum((Decimal(r["dues_hours"]) for r in out), ZERO)),
    }
    meta = {
        "year": year,
        "month": month,
        "group_by": group_by,
        "weeks_included": sorted(d.isoformat() for d in weeks_seen),
        "member_week_rows_considered": considered,
        "member_week_rows_available": len(rows),
    }
    return ReportTable("monthly_dues_remittance", columns, tuple(out), totals, meta)


@dataclass(frozen=True)
class VacationRow:
    employee_id: str
    file_number: str
    display_name: str
    prior_year_gross: Decimal
    prior_year_hours: Decimal
    vac_hours: Decimal
    average_hourly: Decimal
    vacation_pay: Decimal
    periods: tuple = ()


def vacation_pay_report(rows: list[VacationRow], *, year: int) -> ReportTable:
    columns = (
        ("file_number", "File #"),
        ("display_name", "Name"),
        ("prior_year_gross", "Prior yr gross"),
        ("prior_year_hours", "Prior yr hours"),
        ("average_hourly", "Avg hourly"),
        ("vac_hours", "Vac hours"),
        ("vacation_pay", "Vacation pay"),
    )
    out = [
        {
            "employee_id": r.employee_id,
            "file_number": r.file_number,
            "display_name": r.display_name,
            "prior_year_gross": str(round2(r.prior_year_gross)),
            "prior_year_hours": fmt_exact(r.prior_year_hours),
            # Four places: the average hourly rate feeds a multiplication by up
            # to 40 hours, so rounding it to cents first would move the answer.
            "average_hourly": str(r.average_hourly.quantize(Decimal("0.0001"))),
            "vac_hours": fmt_exact(r.vac_hours),
            "vacation_pay": str(round2(r.vacation_pay)),
            "periods": [str(p) for p in r.periods],
        }
        for r in sorted(rows, key=lambda r: r.file_number)
    ]
    totals = {
        "row_count": len(rows),
        "vacation_pay": _money(sum((r.vacation_pay for r in rows), ZERO)),
        "vac_hours": fmt_exact(sum((r.vac_hours for r in rows), ZERO)),
    }
    return ReportTable("vacation_pay", columns, tuple(out), totals, {"year": year})


def to_csv(table: ReportTable) -> str:
    """CSV with a TOTAL row, and the row count written next to it.

    The total row says `TOTAL (n=13)` rather than `TOTAL`, so a spreadsheet
    opened six months from now still states the population of its own sums.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    keys = [k for k, _ in table.columns]
    writer.writerow([label for _, label in table.columns])
    for row in table.rows:
        writer.writerow(["" if row.get(k) is None else row.get(k) for k in keys])

    if table.totals:
        total_row = []
        for i, k in enumerate(keys):
            if i == 0:
                total_row.append(f"TOTAL (n={table.totals.get('row_count', len(table.rows))})")
            else:
                v = table.totals.get(k)
                total_row.append("" if v is None else v)
        writer.writerow(total_row)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 4 Phase 6 — the R-115 union remittance form.
#
# ⚠️ **THIS IS A SECOND REPORT, NOT A REPLACEMENT.** James's ruling: keep both,
# named distinctly. `monthly_dues_remittance` above is built from the HOURS
# export and reports dues the rules IMPLY — it is the figure to check a
# deduction against. `union_remittance_r115` is built from the REGISTER and
# reports dues that were actually DEDUCTED. They answer different questions and
# they disagree on 76 checks in a year, which is precisely why both are needed:
# the form filed with the union must say what was taken, and the other report
# is how you find out whether what was taken was right.
#
# ⚠️ **ALWAYS GROUPED BY CHECK DATE, AND NOT BY A SETTING.** A register has a
# check date and carries no week-end date at all, so `week_end_date` is not a
# choice here — it is unavailable. `monthly_dues_remittance` keeps the setting
# because its source has both.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class R115Row:
    """One check's union deduction, as the register recorded it."""

    emp_id: str
    display_name: str
    check_date: date
    check_number: str
    dues_deducted: Decimal
    dues_hours: Decimal


def union_remittance_r115(
    rows: list[R115Row], *, year: int, month: int
) -> ReportTable:
    """Per member, the union dues actually deducted in one calendar month.

    ⚠️ **A MEMBER WITH NO DEDUCTION IN THE MONTH DOES NOT APPEAR.** The form
    reports money taken; a member who was not paid, or was paid with no dues
    line, has nothing to remit. Their absence is visible in `meta` as a
    `check_dates_included` list a reader can compare against the payroll
    calendar, rather than as a silently shorter table.
    """
    per_member: dict[str, dict] = {}
    dates_seen: set = set()
    considered = 0

    for row in rows:
        if row.check_date is None:
            raise ValueError(
                f"check {row.check_number or '?'} for employee {row.emp_id} has "
                "no check date; an R-115 row cannot be placed in a month "
                "without one"
            )
        if (row.check_date.year, row.check_date.month) != (year, month):
            continue
        considered += 1
        dates_seen.add(row.check_date)
        slot = per_member.setdefault(row.emp_id, {
            "emp_id": row.emp_id,
            "display_name": row.display_name,
            "checks": 0,
            "_dues": ZERO,
            "_hours": ZERO,
        })
        slot["checks"] += 1
        slot["_dues"] += row.dues_deducted
        slot["_hours"] += row.dues_hours

    out = []
    # Sorted by employee id NUMERICALLY where it is a number, so 10 does not
    # sort before 2 on a form somebody reads down a column.
    def sort_key(slot):
        eid = slot["emp_id"]
        return (0, int(eid), "") if eid.isdigit() else (1, 0, eid)

    for slot in sorted(per_member.values(), key=sort_key):
        out.append({
            "emp_id": slot["emp_id"],
            "display_name": slot["display_name"],
            "checks": slot["checks"],
            "dues_hours": fmt_exact(slot["_hours"]),
            "dues_deducted": _money(slot["_dues"]),
        })

    columns = (
        ("emp_id", "Emp #"),
        ("display_name", "Name"),
        ("checks", "Checks"),
        ("dues_hours", "Hours"),
        ("dues_deducted", "Dues deducted"),
    )
    totals = {
        "row_count": len(out),
        "dues_deducted": _money(sum((Decimal(r["dues_deducted"]) for r in out), ZERO)),
        "dues_hours": fmt_exact(sum((Decimal(r["dues_hours"]) for r in out), ZERO)),
    }
    meta = {
        "year": year,
        "month": month,
        # Stated rather than configurable: see the section comment above.
        "group_by": "check_date",
        "check_dates_included": sorted(d.isoformat() for d in dates_seen),
        "check_rows_considered": considered,
        "check_rows_available": len(rows),
        "source": "payroll register — dues actually deducted",
    }
    return ReportTable("union_remittance_r115", columns, tuple(out), totals, meta)
