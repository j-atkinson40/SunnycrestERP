"""Store an hours week and feed it to the calculation — Payroll 3 Phase 3.

Two layers, and the separation is the point:

  `payroll_hours_lines`  what the file said, per line, immutable
  `payroll_week_lines`   the interpretation a calculation reads: buckets

⚠️ **THE RAW LINES ARE KEPT AND LINKED, SO EVERY BUCKET CAN BE TAKEN APART
AGAIN.** A week's dues have to be defensible to a union auditor, and "this is
what Payentry's report printed" is the only thing that settles a disagreement
about which bucket an hour landed in. `PayrollWeekLine.raw` carries the
contributing line ids and the per-day detail.

⚠️ **A CORRECTION IS A NEW IMPORT, NEVER AN EDIT.** The import batch is keyed
by the sha256 of the bytes, so re-uploading the same file is detectable and a
changed file is a new batch beside the first.

⚠️ **ONE PARSER SERVES BOTH THE UPLOAD AND THE FUTURE MONDAY PULL** (the
brief). `import_hours` takes bytes, not a request, so the scheduled job in
Phase 4 hands it the same thing an upload does and no second code path exists
to drift.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pdfplumber
from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollHoursImport,
    PayrollHoursLine,
    PayrollReportEmployee,
    PayrollWeek,
    PayrollWeekLine,
)
from app.services.payroll.hours_parser import (
    PAY_TYPE_TO_BUCKET,
    HoursParseError,
    parse_employee_hours,
)
from app.services.payroll.hours_validation import (
    ValidationReport,
    check_date_for_week,
    validate_import,
)

ZERO = Decimal("0")


class HoursImportRefused(ValueError):
    """The import was refused. `report` says why."""

    def __init__(self, message: str, report: ValidationReport | None = None):
        super().__init__(message)
        self.report = report


@dataclass
class HoursImportResult:
    import_id: str
    week_id: str | None
    week_end_date: date
    rows_stored: int
    week_lines_written: int
    duplicate_of: str | None = None
    report: dict = field(default_factory=dict)


def file_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _bucket_totals(lines) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for line in lines:
        bucket = PAY_TYPE_TO_BUCKET.get(line.pay_type)
        if bucket is None:
            continue                       # unknown type: reported, not bucketed
        out[bucket] = out.get(bucket, ZERO) + line.hours
    return out


def import_hours(db: Session, *, tenant_id: str, content: bytes, filename: str,
                 week_end_date: date, uploaded_by_user_id: str | None,
                 known_emp_ids: set[str], checks=None,
                 write_week: bool = True) -> HoursImportResult:
    """Parse, validate, store the raw lines, and feed `payroll_week_lines`.

    ⚠️ **VALIDATION RUNS BEFORE ANYTHING IS WRITTEN AND A BLOCKING FINDING
    REFUSES THE WHOLE FILE.** Not "import what parsed and warn about the
    rest": a week filed against an employee id that does not exist has wrong
    dues for somebody, and a partial week's totals look entirely plausible.
    """
    digest = file_sha256(content)
    existing = (
        db.query(PayrollHoursImport)
        .filter(PayrollHoursImport.tenant_id == tenant_id,
                PayrollHoursImport.file_sha256 == digest)
        .order_by(PayrollHoursImport.created_at)
        .first()
    )

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            parsed = parse_employee_hours(pdf)
    except HoursParseError:
        raise
    except Exception as exc:                       # pdfplumber raises broadly
        raise HoursParseError(f"could not read the report: {exc}") from exc

    report = validate_import(parsed, expected_week_end=week_end_date,
                             known_emp_ids=known_emp_ids, checks=checks)
    shaped = {
        "findings": [{"kind": f.kind, "detail": f.detail, "blocking": f.blocking}
                     for f in report.findings],
        "by_kind": report.by_kind(),
        "hours_by_pay_type": {k: str(v) for k, v in
                              parsed.hours_by_pay_type().items()},
        "emp_ids": sorted(parsed.emp_ids, key=lambda e: (len(e), e)),
        "listed_without_hours": parsed.listed_without_hours,
    }
    if not report.ok:
        raise HoursImportRefused(
            "the hours file was refused: "
            + "; ".join(f.detail for f in report.blocking), report)

    # ⚠️ The SAME bytes again is not an error and not a second import. The
    # batch is reported so the caller can say "already imported" rather than
    # silently writing a duplicate week.
    if existing is not None:
        return HoursImportResult(
            import_id=existing.id, week_id=None, week_end_date=week_end_date,
            rows_stored=0, week_lines_written=0, duplicate_of=existing.id,
            report=shaped)

    batch = PayrollHoursImport(
        tenant_id=tenant_id, source_kind="employee_hours", file_sha256=digest,
        filename=filename, week_end_date=week_end_date,
        uploaded_by_user_id=uploaded_by_user_id,
        rows_parsed=len(parsed.lines), report=shaped)
    db.add(batch)
    db.flush()

    raw_ids: dict[str, list[str]] = {}
    for line in parsed.lines:
        row = PayrollHoursLine(
            tenant_id=tenant_id, import_id=batch.id, week_end_date=week_end_date,
            emp_id=line.emp_id, name=line.name, home_dept=line.home_dept,
            worked_dept=line.worked_dept, work_date=line.work_date,
            pay_type=line.pay_type, hours=line.hours)
        db.add(row)
        db.flush()
        raw_ids.setdefault(line.emp_id, []).append(row.id)

    week_id = None
    written = 0
    if write_week:
        week_id, written = _write_week(db, tenant_id=tenant_id, parsed=parsed,
                                       week_end_date=week_end_date,
                                       raw_ids=raw_ids, file_hash=digest)
    db.flush()
    return HoursImportResult(import_id=batch.id, week_id=week_id,
                             week_end_date=week_end_date,
                             rows_stored=len(parsed.lines),
                             week_lines_written=written, report=shaped)


def _write_week(db: Session, *, tenant_id: str, parsed, week_end_date: date,
                raw_ids: dict[str, list[str]],
                file_hash: str | None = None) -> tuple[str | None, int]:
    """Create or replace the `payroll_weeks` row and its bucket lines.

    ⚠️ **AN APPROVED WEEK IS NOT TOUCHED.** Payroll 1's discipline: approval is
    terminal for calculation, and re-importing hours over an approved week
    would change figures somebody has signed off.
    """
    week = (db.query(PayrollWeek)
            .filter(PayrollWeek.tenant_id == tenant_id,
                    PayrollWeek.week_end_date == week_end_date).first())
    if week is not None and week.status == "approved":
        raise HoursImportRefused(
            f"the week ending {week_end_date} is approved; re-importing hours "
            f"over it would change figures that have been signed off")

    roster = {e.payentry_file_number: e
              for e in db.query(PayrollReportEmployee)
              .filter(PayrollReportEmployee.tenant_id == tenant_id).all()}

    if week is None:
        # ⚠️ `check_date` is NOT NULL with no default, and `source_file_hash`
        # exists for exactly this. I omitted both in the first draft and the
        # insert would have failed on a constraint — the same schema-guessing
        # mistake this project has hit before. Read the model, do not assume it.
        week = PayrollWeek(tenant_id=tenant_id, week_end_date=week_end_date,
                           week_number=week_end_date.isocalendar().week,
                           check_date=check_date_for_week(week_end_date),
                           source_file_hash=file_hash,
                           status="imported")
        db.add(week)
        db.flush()
    else:
        db.query(PayrollWeekLine).filter(PayrollWeekLine.week_id == week.id).delete()
        week.status = "imported"
        week.source_file_hash = file_hash
        db.flush()

    per_emp: dict[str, list] = {}
    for line in parsed.lines:
        per_emp.setdefault(line.emp_id, []).append(line)

    written = 0
    for emp_id, lines in sorted(per_emp.items(), key=lambda kv: (len(kv[0]), kv[0])):
        employee = roster.get(emp_id)
        if employee is None:
            # Unreachable in practice: `validate_identity` blocks an unknown id
            # before this runs. Kept because "unreachable" is a claim about
            # today's callers, not about the function.
            continue
        buckets = _bucket_totals(lines)
        db.add(PayrollWeekLine(
            week_id=week.id, employee_id=employee.id,
            reg_hrs=buckets.get("reg_hrs", ZERO),
            ot_hrs=buckets.get("ot_hrs", ZERO),
            personal_hrs=buckets.get("personal_hrs", ZERO),
            sick_hrs=buckets.get("sick_hrs", ZERO),
            # ⚠️ The evidence, linked. Every bucket above can be taken apart
            # into the printed lines that made it.
            raw={"source": "employee_hours",
                 "hours_line_ids": raw_ids.get(emp_id, []),
                 "by_day": [{"date": l.work_date.isoformat(),
                             "pay_type": l.pay_type, "hours": str(l.hours)}
                            for l in sorted(lines, key=lambda l: (l.work_date,
                                                                  l.pay_type))]}))
        written += 1
    db.flush()
    return week.id, written
