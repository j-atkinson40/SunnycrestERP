"""DB orchestration for weekly payroll reports.

The arithmetic lives in `engine` (pure) and the shaping in `reports` (pure).
This module does the parts that need a session: resolving which rules and rates
were in force, persisting lines and results, and enforcing the approval lock.

⚠️ **APPROVAL IS A LOCK, ENFORCED HERE.** Recalculating an approved week raises
`WeekLocked`. The route maps it to 409. A UI-only restriction is not a
restriction — the service is the boundary (the precedent and the reasoning are
`completeness.py::_require_accounting_role`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollRate,
    PayrollReportEmployee,
    PayrollRuleSet,
    PayrollWeek,
    PayrollWeekLine,
    PayrollWeekResult,
)
from app.services.payroll import reports as report_builders
from app.services.payroll.column_mapping import load_mapping
from app.services.payroll.engine import LineInputs, compute_dues
from app.services.payroll.parsers import ExportPayload, get_parser
from app.services.payroll.reports import MemberDuesRow
from app.services.payroll.rules import RULE_FIELDS, PayrollRules
from app.services.payroll.validation import (
    ValidationFlag,
    flag_ot_rate,
    flag_unmapped_columns,
    flag_zero_hours_with_pay,
    reconcile_roster,
    summarize,
)

#: check_date = week_end_date + CHECK_DATE_OFFSET. Named once; the model, the
#: importer and the tests all read it here rather than each spelling "5 days".
CHECK_DATE_OFFSET = timedelta(days=5)

DETAIL_REPORT_KEY = "weekly_dues_detail"

LINE_FIELDS = tuple(LineInputs.__dataclass_fields__)


class PayrollError(RuntimeError):
    pass


class WeekLocked(PayrollError):
    """An approved week cannot be recalculated or re-imported."""


class WeekNotCalculated(PayrollError):
    pass


class MissingRate(PayrollError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------- rule / rate


def resolve_rule_set(db: Session, tenant_id: str, as_of: date) -> PayrollRuleSet:
    """The newest rule set effective on or before `as_of`."""
    row = db.execute(
        select(PayrollRuleSet)
        .where(PayrollRuleSet.tenant_id == tenant_id)
        .where(PayrollRuleSet.effective_date <= as_of)
        .order_by(PayrollRuleSet.effective_date.desc())
        .limit(1)
    ).scalars().first()
    if row is None:
        raise PayrollError(
            f"no payroll rule set effective on or before {as_of} for tenant "
            f"{tenant_id}. Dues cannot be computed without the rules that "
            f"define them — seed a rule set rather than falling back to "
            f"defaults, so the result records which rules produced it."
        )
    return row


def rules_from_row(row: PayrollRuleSet) -> PayrollRules:
    """Build the frozen engine rule set from a stored row.

    Reads `RULE_FIELDS` rather than listing the names again — two producers of
    one field list is two things waiting to drift apart.
    """
    kwargs = {f: getattr(row, f) for f in RULE_FIELDS}
    return PayrollRules(effective_date=row.effective_date, **kwargs)


def resolve_rate(db: Session, employee_id: str, as_of: date) -> PayrollRate | None:
    return db.execute(
        select(PayrollRate)
        .where(PayrollRate.employee_id == employee_id)
        .where(PayrollRate.effective_date <= as_of)
        .order_by(PayrollRate.effective_date.desc())
        .limit(1)
    ).scalars().first()


# ----------------------------------------------------------------- import


@dataclass
class ImportResult:
    week: PayrollWeek
    rows_parsed: int
    rows_persisted: int
    flags: list[ValidationFlag]

    @property
    def summary(self) -> dict:
        return {
            "rows_parsed": self.rows_parsed,
            "rows_persisted": self.rows_persisted,
            "rows_skipped": self.rows_parsed - self.rows_persisted,
            "flags": summarize(self.flags),
        }


def import_week(
    db: Session,
    *,
    tenant_id: str,
    payload: ExportPayload,
    week_number: int,
    week_end_date: date,
    format_key: str = "payentry",
    allow_unverified_mapping: bool = False,
) -> ImportResult:
    """Parse an export into a week of lines.

    Idempotent on `(tenant_id, week_end_date)`: re-importing replaces the lines
    of a non-approved week. An APPROVED week refuses.
    """
    mapping = load_mapping(format_key)
    mapping.require_verified(allow_unverified=allow_unverified_mapping)
    parsed = get_parser(format_key).parse(payload, mapping)

    week = db.execute(
        select(PayrollWeek)
        .where(PayrollWeek.tenant_id == tenant_id)
        .where(PayrollWeek.week_end_date == week_end_date)
    ).scalars().first()

    if week is not None and week.status == "approved":
        raise WeekLocked(
            f"week ending {week_end_date} is approved (by {week.approved_by} at "
            f"{week.approved_at}); it cannot be re-imported. Reopening an "
            f"approved week is a deliberate act, not a side effect of an upload."
        )

    if week is None:
        week = PayrollWeek(
            tenant_id=tenant_id,
            week_number=week_number,
            week_end_date=week_end_date,
            check_date=week_end_date + CHECK_DATE_OFFSET,
            source_file_hash=parsed.source_file_hash,
            status="imported",
        )
        db.add(week)
        db.flush()
    else:
        week.week_number = week_number
        week.check_date = week_end_date + CHECK_DATE_OFFSET
        week.source_file_hash = parsed.source_file_hash
        week.status = "imported"
        week.calculated_at = None
        # Replacing the lines, so the previous calculation's results are stale.
        for stale in list(week.results):
            db.delete(stale)
        for stale in list(week.lines):
            db.delete(stale)
        db.flush()

    configured = {
        e.payentry_file_number: e
        for e in db.execute(
            select(PayrollReportEmployee)
            .where(PayrollReportEmployee.tenant_id == tenant_id)
        ).scalars().all()
    }

    flags: list[ValidationFlag] = []
    unmapped = flag_unmapped_columns(parsed.unmapped_columns)
    if unmapped:
        flags.append(unmapped)

    persisted = 0
    for row in parsed.rows:
        emp = configured.get(row.payentry_file_number)
        if emp is None:
            # Flagged by reconcile_roster below; the line cannot be stored
            # because it has no employee to attach to.
            continue

        values = {f: row.hours_and_amounts.get(f, Decimal("0")) for f in LINE_FIELDS}
        zero_pay = flag_zero_hours_with_pay(
            values, file_number=row.payentry_file_number, employee_id=emp.id
        )
        if zero_pay:
            flags.append(zero_pay)

        db.add(PayrollWeekLine(week_id=week.id, employee_id=emp.id, raw=row.raw, **values))
        persisted += 1

    flags.extend(reconcile_roster({r.payentry_file_number for r in parsed.rows}, configured))
    db.flush()

    return ImportResult(week=week, rows_parsed=len(parsed.rows),
                        rows_persisted=persisted, flags=flags)


# -------------------------------------------------------------- calculate


@dataclass
class CalculationResult:
    week: PayrollWeek
    rows: list[MemberDuesRow]
    flags: list[ValidationFlag]
    rule_set_id: str


def calculate_week(db: Session, week: PayrollWeek, *, persist: bool = True) -> CalculationResult:
    """Compute dues for every line on the week.

    ⚠️ **THE INITIATION-FEE DECISIONS ARE ALL MADE BEFORE ANY RESULT IS
    WRITTEN.** "The employee's first dues week" is an aggregate over PRIOR
    results, and SQLAlchemy autoflush would insert this week's pending result
    rows before such a query runs — so a per-employee check interleaved with
    writes would see the row it is in the middle of creating and conclude this
    was not the first week. The failure is silent and costs exactly one
    initiation fee per member (CLAUDE.md §11 "Money math is hand-proven —
    including aggregates"). Resolved by computing the whole set up front, under
    `no_autoflush`, and by deleting prior results for this week first.
    """
    if week.status == "approved":
        raise WeekLocked(
            f"week ending {week.week_end_date} is approved and cannot be "
            f"recalculated. Approval is the point at which the numbers stop "
            f"moving; that is what makes them citable."
        )

    rule_row = resolve_rule_set(db, week.tenant_id, week.week_end_date)
    rules = rules_from_row(rule_row)

    lines = db.execute(
        select(PayrollWeekLine).where(PayrollWeekLine.week_id == week.id)
    ).scalars().all()

    # Clear this week's prior results BEFORE the first-week queries run, so a
    # recalculation cannot see its own previous output as prior history.
    db.execute(
        PayrollWeekResult.__table__.delete().where(PayrollWeekResult.week_id == week.id)
    )
    db.flush()

    with db.no_autoflush:
        fee_due = _resolve_initiation_fees(db, week, lines)

    flags: list[ValidationFlag] = []
    rows: list[MemberDuesRow] = []

    for line in lines:
        emp = db.get(PayrollReportEmployee, line.employee_id)
        rate = resolve_rate(db, line.employee_id, week.week_end_date)
        if rate is None:
            flags.append(ValidationFlag.of(
                "missing_rate",
                file_number=getattr(emp, "payentry_file_number", None),
                employee_id=line.employee_id,
                detail={"week_end_date": week.week_end_date.isoformat()},
            ))
            continue

        ot_flag = flag_ot_rate(
            rate.reg_rate, rate.ot_rate,
            file_number=getattr(emp, "payentry_file_number", None),
            employee_id=line.employee_id,
        )
        if ot_flag:
            flags.append(ot_flag)

        result = compute_dues(
            LineInputs(**{f: getattr(line, f) for f in LINE_FIELDS}),
            rate.reg_rate,
            rate.ot_rate,
            rules,
            apply_initiation_fee=fee_due.get(line.employee_id, False),
        )

        rows.append(MemberDuesRow(
            employee_id=line.employee_id,
            file_number=getattr(emp, "payentry_file_number", "?"),
            display_name=getattr(emp, "display_name", "?"),
            dept=getattr(emp, "dept", None),
            result=result,
            week_end_date=week.week_end_date,
            check_date=week.check_date,
        ))

        if persist:
            db.add(PayrollWeekResult(
                week_id=week.id,
                employee_id=line.employee_id,
                report_key=DETAIL_REPORT_KEY,
                values_json={
                    "dues_wage": str(result.dues_wage),
                    "dues_hours": str(result.dues_hours),
                    "component_a": None if result.component_a is None else str(result.component_a),
                    "component_b": None if result.component_b is None else str(result.component_b),
                    "component_c": None if result.component_c is None else str(result.component_c),
                    "capped": None if result.capped is None else str(result.capped),
                    "initiation_fee": str(result.initiation_fee),
                    "dues": str(result.dues),
                    "binds": result.binds,
                    "ot_rate_used": str(result.ot_rate_used),
                    "ot_rate_derived": result.ot_rate_derived,
                },
                rule_set_id=rule_row.id,
                rate_ids=[rate.id],
            ))

    if persist:
        week.status = "calculated"
        week.calculated_at = _now()
        db.flush()

    return CalculationResult(week=week, rows=rows, flags=flags, rule_set_id=rule_row.id)


def _resolve_initiation_fees(db: Session, week: PayrollWeek, lines) -> dict:
    """Which employees owe the initiation fee on THIS week.

    An employee owes it when `initiation_fee_due` is set AND they have no
    earlier week (strictly before this `week_end_date`) that produced non-zero
    dues. Computed for the whole set in one pass, before any write.
    """
    out: dict[str, bool] = {}
    for line in lines:
        emp = db.get(PayrollReportEmployee, line.employee_id)
        if emp is None or not emp.initiation_fee_due:
            out[line.employee_id] = False
            continue

        prior = db.execute(
            select(PayrollWeekResult.id)
            .join(PayrollWeek, PayrollWeek.id == PayrollWeekResult.week_id)
            .where(PayrollWeekResult.employee_id == line.employee_id)
            .where(PayrollWeekResult.report_key == DETAIL_REPORT_KEY)
            .where(PayrollWeek.tenant_id == week.tenant_id)
            .where(PayrollWeek.week_end_date < week.week_end_date)
            .limit(1)
        ).first()
        out[line.employee_id] = prior is None
    return out


# ----------------------------------------------------------------- approve


def approve_week(db: Session, week: PayrollWeek, *, user_id: str) -> PayrollWeek:
    if week.status == "approved":
        raise WeekLocked(f"week ending {week.week_end_date} is already approved")
    if week.status != "calculated":
        raise WeekNotCalculated(
            f"week ending {week.week_end_date} is {week.status!r}; it must be "
            f"calculated before it can be approved. Approving an uncalculated "
            f"week would lock a week that has no numbers in it."
        )
    week.status = "approved"
    week.approved_by = user_id
    week.approved_at = _now()
    db.flush()
    return week


# ----------------------------------------------------------------- reports


def build_report(db: Session, week: PayrollWeek, report_key: str):
    """Build one of the week-scoped reports from stored results."""
    rows = _rows_from_stored_results(db, week)
    if report_key == "weekly_dues_detail":
        return report_builders.weekly_dues_detail(rows)
    if report_key == "employee_dues_deduction":
        return report_builders.employee_dues_deduction(rows)
    raise PayrollError(
        f"unknown week-scoped report {report_key!r}; available: "
        f"weekly_dues_detail, employee_dues_deduction"
    )


def monthly_remittance(db: Session, *, tenant_id: str, year: int, month: int):
    """Per-member dues for a calendar month, grouped per the rule set in force.

    The grouping key comes from the rule set, not from a parameter default, so a
    tenant that switches to `check_date` gets it everywhere at once.
    """
    as_of = date(year, month, 1)
    rules = rules_from_row(resolve_rule_set(db, tenant_id, as_of))

    weeks = db.execute(
        select(PayrollWeek).where(PayrollWeek.tenant_id == tenant_id)
    ).scalars().all()

    rows: list[MemberDuesRow] = []
    for week in weeks:
        rows.extend(_rows_from_stored_results(db, week))

    return report_builders.monthly_dues_remittance(
        rows, year=year, month=month, group_by=rules.remittance_group_by
    )


def _rows_from_stored_results(db: Session, week: PayrollWeek) -> list[MemberDuesRow]:
    """Rebuild report rows from persisted results.

    Reports read STORED results, never recompute. A report that recalculated on
    read would silently change after an approved week if a rate or rule moved —
    which is the opposite of what approval is for.
    """
    from app.services.payroll.engine import DuesResult

    stored = db.execute(
        select(PayrollWeekResult)
        .where(PayrollWeekResult.week_id == week.id)
        .where(PayrollWeekResult.report_key == DETAIL_REPORT_KEY)
    ).scalars().all()

    rows: list[MemberDuesRow] = []
    for r in stored:
        v = r.values_json
        emp = db.get(PayrollReportEmployee, r.employee_id)
        rows.append(MemberDuesRow(
            employee_id=r.employee_id,
            file_number=getattr(emp, "payentry_file_number", "?"),
            display_name=getattr(emp, "display_name", "?"),
            dept=getattr(emp, "dept", None),
            week_end_date=week.week_end_date,
            check_date=week.check_date,
            result=DuesResult(
                dues_wage=Decimal(v["dues_wage"]),
                dues_hours=Decimal(v["dues_hours"]),
                component_a=None if v["component_a"] is None else Decimal(v["component_a"]),
                component_b=None if v["component_b"] is None else Decimal(v["component_b"]),
                component_c=None if v["component_c"] is None else Decimal(v["component_c"]),
                capped=None if v["capped"] is None else Decimal(v["capped"]),
                initiation_fee=Decimal(v["initiation_fee"]),
                dues=Decimal(v["dues"]),
                ot_rate_used=Decimal(v["ot_rate_used"]),
                ot_rate_derived=bool(v["ot_rate_derived"]),
            ),
        ))
    return sorted(rows, key=lambda r: r.file_number)
