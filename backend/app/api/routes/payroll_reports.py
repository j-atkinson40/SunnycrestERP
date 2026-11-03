"""Weekly payroll reports API — upload, calculate, report, approve.

Accountant/admin only. Reporting only: nothing here runs payroll, pays anyone,
or touches the planned Check integration.

⚠️ **GATED ON A PERMISSION, NOT ON A ROLE NAME — CHANGED 2026-11-03.** These
endpoints originally imported `ACCOUNTING_ROLES` from `completeness.py` —
`("admin", "accountant")` — and refused every other slug. That was right while
those were the only two candidates and WRONG the moment a third role existed:
a user on the new `payroll` role holds `payroll.view` but her slug is
`payroll`, so the slug gate would have refused her from the very endpoints this
module exists to serve.

Gating on `require_permission("payroll.view")` also means per-user overrides
(`UserPermissionOverride`) work here for free, which a slug comparison could
never honour.

Existing access is preserved rather than widened: `payroll.view` was added to
`ACCOUNTANT_DEFAULT_PERMISSIONS`, because an accountant already reached these
endpoints through the old slug gate and must keep doing so. Admin is unaffected —
`get_user_permissions` returns every key for the admin role.

⚠️ **APPROVAL REFUSES, IT DOES NOT WARN.** Recalculating or re-importing an
approved week returns 409. Enforced in the service layer; the route only
translates. A UI-only restriction is not a restriction.

Spec: docs/specs/payroll-reports.md
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.payroll_report import PayrollWeek
from app.models.user import User
from app.services.payroll import service as payroll_service
from app.services.payroll.column_mapping import UnverifiedMapping, available_mappings
from app.services.payroll.parsers import ExportParseError, ExportPayload
from app.services.payroll.reports import to_csv
from app.services.payroll.validation import summarize

router = APIRouter()

#: Upload cap. A weekly payroll export for a single licensee is kilobytes; a
#: 10 MB file is a wrong file, and reading it into memory to discover that is
#: the avoidable part.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


#: The permission every endpoint in this module requires. One name, read by all
#: seven routes, so they cannot drift apart. `payroll.approve` exists in the
#: catalogue and is deliberately unused until the approve flow is designed in
#: slice 2 — approving is gated on `payroll.view` today, which is what the
#: 2026-11-03 dispatch specified.
PAYROLL_PERMISSION = "payroll.view"


def _get_week(db: Session, week_id: str, tenant_id: str) -> PayrollWeek:
    week = db.execute(
        select(PayrollWeek)
        .where(PayrollWeek.id == week_id)
        .where(PayrollWeek.tenant_id == tenant_id)
    ).scalars().first()
    if week is None:
        # 404 on a cross-tenant id as well as a missing one — the two must be
        # indistinguishable, or the response discloses which ids exist.
        raise HTTPException(404, "Payroll week not found")
    return week


def _flag_payload(flags) -> dict:
    return {
        "summary": summarize(flags),
        "flags": [
            {
                "code": f.code,
                "severity": f.severity,
                "message": f.message,
                "file_number": f.file_number,
                "employee_id": f.employee_id,
                "detail": f.detail,
            }
            for f in flags
        ],
    }


def _week_payload(week: PayrollWeek) -> dict:
    return {
        "id": week.id,
        "week_number": week.week_number,
        "week_end_date": week.week_end_date.isoformat(),
        "check_date": week.check_date.isoformat(),
        "status": week.status,
        "source_file_hash": week.source_file_hash,
        "imported_at": week.imported_at.isoformat() if week.imported_at else None,
        "calculated_at": week.calculated_at.isoformat() if week.calculated_at else None,
        "approved_by": week.approved_by,
        "approved_at": week.approved_at.isoformat() if week.approved_at else None,
    }


@router.get("/formats")
def list_formats(
    current_user: User = Depends(require_permission(PAYROLL_PERMISSION)),
    db: Session = Depends(get_db),
):
    """Available column mappings and whether each is verified.

    Surfaced so the unverified state of the Payentry mapping is visible before
    someone tries an upload, rather than only in the 422 they get back.
    """
    from app.services.payroll.column_mapping import load_mapping

    out = []
    for key in available_mappings():
        m = load_mapping(key)
        out.append({
            "format_key": key,
            "verified": m.verified,
            "mapped_fields": len(m.columns),
            "notes": m.notes,
        })
    return {"formats": out}


@router.get("/weeks")
def list_weeks(
    current_user: User = Depends(require_permission(PAYROLL_PERMISSION)),
    db: Session = Depends(get_db),
):
    weeks = db.execute(
        select(PayrollWeek)
        .where(PayrollWeek.tenant_id == current_user.company_id)
        .order_by(PayrollWeek.week_end_date.desc())
    ).scalars().all()
    return {"weeks": [_week_payload(w) for w in weeks], "count": len(weeks)}


@router.post("/weeks/upload", status_code=201)
async def upload_export(
    file: UploadFile = File(...),
    week_number: int = Form(...),
    week_end_date: date = Form(...),
    format_key: str = Form("payentry"),
    current_user: User = Depends(require_permission(PAYROLL_PERMISSION)),
    db: Session = Depends(get_db),
):
    """Upload a payroll export and create (or replace) the week's lines.

    Idempotent on (tenant, week_end_date). An approved week refuses with 409.
    """

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Export exceeds {MAX_UPLOAD_BYTES} bytes")
    if not content:
        raise HTTPException(422, "Export is empty")

    payload = ExportPayload(
        filename=file.filename or "upload",
        content=content,
        content_type=file.content_type,
    )

    try:
        result = payroll_service.import_week(
            db,
            tenant_id=current_user.company_id,
            payload=payload,
            week_number=week_number,
            week_end_date=week_end_date,
            format_key=format_key,
        )
    except payroll_service.WeekLocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except UnverifiedMapping as exc:
        # 422, not 500: the request is well-formed and the refusal is a stated
        # rule about the mapping, with the remedy in the message.
        raise HTTPException(422, str(exc)) from exc
    except (ExportParseError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc)) from exc

    db.commit()
    return {
        "week": _week_payload(result.week),
        "import": result.summary,
        **_flag_payload(result.flags),
    }


@router.post("/weeks/{week_id}/calculate")
def calculate(
    week_id: str,
    current_user: User = Depends(require_permission(PAYROLL_PERMISSION)),
    db: Session = Depends(get_db),
):
    """Compute dues for the week. Refuses on an approved week."""
    week = _get_week(db, week_id, current_user.company_id)

    try:
        result = payroll_service.calculate_week(db, week)
    except payroll_service.WeekLocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except payroll_service.PayrollError as exc:
        raise HTTPException(422, str(exc)) from exc

    db.commit()
    table = payroll_service.build_report(db, week, "weekly_dues_detail")
    return {
        "week": _week_payload(week),
        "rule_set_id": result.rule_set_id,
        "members_calculated": len(result.rows),
        "totals": table.totals,
        **_flag_payload(result.flags),
    }


@router.get("/weeks/{week_id}/reports/{report_key}")
def get_week_report(
    week_id: str,
    report_key: str,
    fmt: str = Query("json", pattern="^(json|csv)$"),
    current_user: User = Depends(require_permission(PAYROLL_PERMISSION)),
    db: Session = Depends(get_db),
):
    week = _get_week(db, week_id, current_user.company_id)

    try:
        table = payroll_service.build_report(db, week, report_key)
    except payroll_service.PayrollError as exc:
        raise HTTPException(404, str(exc)) from exc

    if fmt == "csv":
        return Response(
            content=to_csv(table),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{report_key}_'
                    f'{week.week_end_date.isoformat()}.csv"'
                )
            },
        )
    return {
        "report_key": table.report_key,
        "week": _week_payload(week),
        "columns": [{"key": k, "label": v} for k, v in table.columns],
        "rows": list(table.rows),
        "totals": table.totals,
        "meta": table.meta,
    }


@router.get("/reports/monthly-dues-remittance")
def monthly_remittance(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    fmt: str = Query("json", pattern="^(json|csv)$"),
    current_user: User = Depends(require_permission(PAYROLL_PERMISSION)),
    db: Session = Depends(get_db),
):
    """Per-member dues for a calendar month.

    Grouped by whichever key the tenant's rule set declares. The response echoes
    `meta.group_by` so a stored or exported report states the rule that produced
    it instead of leaving a reader to assume today's default.
    """
    try:
        table = payroll_service.monthly_remittance(
            db, tenant_id=current_user.company_id, year=year, month=month
        )
    except payroll_service.PayrollError as exc:
        raise HTTPException(422, str(exc)) from exc

    if fmt == "csv":
        return Response(
            content=to_csv(table),
            media_type="text/csv",
            headers={"Content-Disposition":
                     f'attachment; filename="monthly_dues_{year}_{month:02d}.csv"'},
        )
    return {
        "report_key": table.report_key,
        "columns": [{"key": k, "label": v} for k, v in table.columns],
        "rows": list(table.rows),
        "totals": table.totals,
        "meta": table.meta,
    }


@router.post("/weeks/{week_id}/approve")
def approve(
    week_id: str,
    current_user: User = Depends(require_permission(PAYROLL_PERMISSION)),
    db: Session = Depends(get_db),
):
    """Approve the week, locking it against recalculation."""
    week = _get_week(db, week_id, current_user.company_id)

    try:
        payroll_service.approve_week(db, week, user_id=current_user.id)
    except payroll_service.WeekLocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except payroll_service.WeekNotCalculated as exc:
        raise HTTPException(409, str(exc)) from exc

    db.commit()
    return {"week": _week_payload(week), "locked": True}
