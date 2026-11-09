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

from app.api.deps import get_db, require_admin, require_permission
from app.models.company import Company
from app.services import audit_service
from app.services.payroll.data_gate import (
    PAYROLL_DATA_ENABLED,
    assert_payroll_data_enabled,
    is_payroll_data_enabled,
)
from app.models.payroll_report import PayrollWeek
from app.models.user import User
from app.services.payroll import service as payroll_service
from app.services.payroll.column_mapping import UnverifiedMapping, available_mappings
from app.services.payroll.parsers import ExportParseError, ExportPayload
from app.services.payroll.register_import import import_register
from app.services.payroll.register_parser import RegisterParseError
from app.services.payroll.reports import to_csv
from app.services.payroll.validation import summarize

router = APIRouter()

#: Upload cap. A weekly payroll export for a single licensee is kilobytes; a
#: 10 MB file is a wrong file, and reading it into memory to discover that is
#: the avoidable part.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


#: ─────────────────────────────────────────────────────────────────────────────
#: THREE DIFFERENT ANSWERS TO "WHO MAY DO THIS", split 2026-11-03 on James's
#: ruling. One permission previously meant both "can look" and "can change";
#: those separate the moment somebody needs to look without approving.
#:
#:   READ  = payroll.view     — look at reports, and recompute them.
#:   WRITE = payroll.approve  — approve a week, which freezes its figures.
#:   LOAD  = require_admin    — import an export. Later this becomes the
#:                              payroll job's own system actor; the accountant
#:                              never needs to load data herself.
#:
#: Her role holds both permissions, so none of this changes anything for her.
PAYROLL_READ = "payroll.view"
PAYROLL_WRITE = "payroll.approve"


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
    current_user: User = Depends(require_permission(PAYROLL_READ)),
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
    current_user: User = Depends(require_permission(PAYROLL_READ)),
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
    # ⚠️ ADMIN ONLY, NOT payroll.view. Loading hours is the act that brings pay
    # data into existence, and the payroll reviewer never needs to do it: in the
    # finished shape it is the background payroll job running under its own
    # system actor (James, 2026-11-03). Until that actor exists, an admin does
    # it by hand.
    #
    # The data switch below is a SECOND, independent gate on the same endpoint:
    # this one asks "are you allowed to load", the switch asks "may this tenant
    # hold payroll data at all". The future job actor will pass the first and
    # still have to satisfy the second.
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Upload a payroll export and create (or replace) the week's lines.

    Admin only. Idempotent on (tenant, week_end_date); an approved week refuses
    with 409, and a tenant whose payroll data switch is off refuses with 403.
    """

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Export exceeds {MAX_UPLOAD_BYTES} bytes")
    if not content:
        raise HTTPException(422, "Export is empty")

    # ⚠️ THE DATA SWITCH, CHECKED BEFORE THE BYTES ARE INTERPRETED. Off by
    # default per tenant. This is the enforced half of "no payroll data until
    # two-step sign-in exists" — before 2026-11-03 that was an agreement between
    # people, and anyone holding payroll.view could import an export.
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)

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
    # ⚠️ `payroll.view`, AND HERE IS THE SHOWING. The ruling is that calculate
    # may be a read permission if and only if it is a deterministic recompute
    # from already-loaded data with no other side effect.
    #
    # Measured against `app/services/payroll/service.py::calculate_week`, its
    # complete set of writes is:
    #   :270  deletes ITS OWN prior results for this week
    #   :319  inserts the recomputed result rows
    #   :341  week.status = "calculated"
    #   :342  week.calculated_at = now()
    #
    # Nothing else. No other table, no money, nothing outside this payroll week.
    # Same lines + same rule set -> identical `values` JSON, so running it twice
    # produces the same figures; `status` is already "calculated" by the second
    # run, and `calculated_at` is the only field that differs — a timestamp
    # recording the recompute itself.
    #
    # ⚠️ THE ONE ARGUMENT FOR `payroll.approve` INSTEAD: `status` advancing
    # imported -> calculated is what makes a week eligible for approval
    # (`approve_week` refuses anything not "calculated"), so calculate is a
    # prerequisite step and not purely an observation. It is left on read
    # because a look-only reviewer who could not recompute could not see
    # figures for a week nobody had calculated — and reports read STORED
    # results, so she still cannot change an approved week's numbers. Flip this
    # one constant to PAYROLL_WRITE if that reading is wrong.
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """Recompute dues for the week from loaded data. Refuses on an approved
    week. Deterministic — see the note on the dependency above."""
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
    current_user: User = Depends(require_permission(PAYROLL_READ)),
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
    current_user: User = Depends(require_permission(PAYROLL_READ)),
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
    # ⚠️ `payroll.approve`, NOT `payroll.view`. Approval is the irreversible
    # step — it freezes the figures and refuses further recalculation — so it is
    # the one action in this module that a look-only reviewer must not be able
    # to take.
    current_user: User = Depends(require_permission(PAYROLL_WRITE)),
    db: Session = Depends(get_db),
):
    """Approve the week, locking it against recalculation. Requires
    `payroll.approve`."""
    week = _get_week(db, week_id, current_user.company_id)

    try:
        payroll_service.approve_week(db, week, user_id=current_user.id)
    except payroll_service.WeekLocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except payroll_service.WeekNotCalculated as exc:
        raise HTTPException(409, str(exc)) from exc

    db.commit()
    return {"week": _week_payload(week), "locked": True}


# ─────────────────────────────────────────────────────────────────────────────
# The payroll data switch. Admin only — NOT payroll.view.
#
# ⚠️ GATED ON `require_admin`, DELIBERATELY NARROWER THAN THE REST OF THIS
# MODULE. Everything above answers to `payroll.view` so the payroll role can use
# it; this decides whether payroll data may exist at all, which is a tenant-level
# decision and not the payroll reviewer's to make. A payroll-limited user passes
# the area check on this router and is then refused here, which is the correct
# order of refusals.


@router.get("/settings/data-enabled")
def get_data_enabled(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Is payroll data loading enabled for this company?"""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    return {
        "setting": PAYROLL_DATA_ENABLED,
        "enabled": is_payroll_data_enabled(company),
    }


@router.put("/settings/data-enabled")
def set_data_enabled(
    enabled: bool = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Turn payroll data loading on or off. Audited.

    ⚠️ AUDITED BECAUSE THIS IS THE DECISION, NOT A PREFERENCE. Turning it on is
    the moment a tenant accepts that pay rates and hours may be stored, and the
    record should say who did that and when. A no-op write records nothing, so
    the trail stays readable.
    """
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    before = is_payroll_data_enabled(company)
    if before == enabled:
        return {"setting": PAYROLL_DATA_ENABLED, "enabled": before, "changed": False}

    company.set_setting(PAYROLL_DATA_ENABLED, bool(enabled))
    audit_service.log_action(
        db,
        current_user.company_id,
        "payroll_data_enabled_changed",
        "company",
        current_user.company_id,
        user_id=current_user.id,
        changes={PAYROLL_DATA_ENABLED: {"before": before, "after": bool(enabled)}},
    )
    db.commit()
    return {"setting": PAYROLL_DATA_ENABLED, "enabled": bool(enabled), "changed": True}


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 4 Phase 1 — the register upload.
#
# ⚠️ **UPLOAD ONLY. NOTHING HERE READS PAYENTRY.** James's ruling: the register
# arrives as a file a person downloaded and chose to upload. There is no
# Payentry credential in this process, no scheduled pull, and no outbound call
# of any kind — so there is nothing here to be given a credential later by
# accident.
# ─────────────────────────────────────────────────────────────────────────────

#: A year of registers for one licensee is ~2 MB of PDF. 25 allows several
#: years in one file without allowing a wrong file to be read into memory.
MAX_REGISTER_BYTES = 25 * 1024 * 1024


@router.post("/register/upload")
async def upload_register(
    file: UploadFile = File(...),
    # ⚠️ ADMIN ONLY, NOT payroll.view — the same reasoning as the hours
    # upload above. Importing a register is the act that brings paid-wage data
    # into existence, and the payroll reviewer never needs to do it.
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Import a Payentry Payroll Register PDF.

    Admin only, and refused outright for a tenant whose payroll data switch is
    off. Idempotent on (check number, check date, employee id): re-uploading an
    overlapping range counts the duplicates and changes nothing.

    The response carries the import report — unknown codes, employee ids with
    more than one candidate name, checks carrying both salary and union dues,
    and any check that did not add up. All of it is also stored on the import
    row, because a finding that lives only in a response body is a finding
    nobody can audit later.
    """
    content = await file.read()
    if len(content) > MAX_REGISTER_BYTES:
        raise HTTPException(413, f"Register exceeds {MAX_REGISTER_BYTES} bytes")
    if not content:
        raise HTTPException(422, "Register is empty")

    # ⚠️ THE DATA SWITCH, CHECKED BEFORE THE BYTES ARE INTERPRETED. Off by
    # default per tenant. A register is the most sensitive payroll file there
    # is — names, pay rates, child support, garnishments — so the switch gates
    # it for the same reason it gates the hours export, and first.
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)

    try:
        result = import_register(
            db,
            tenant_id=current_user.company_id,
            content=content,
            filename=file.filename or "register.pdf",
            uploaded_by_user_id=current_user.id,
        )
    except RegisterParseError as exc:
        # 422, not 500: the request is well-formed and the refusal is a stated
        # one — this file is not a readable Payroll Register.
        raise HTTPException(422, str(exc)) from exc

    audit_service.log_action(
        db,
        current_user.company_id,
        "payroll_register_imported",
        "payroll_register_import",
        result.import_id,
        user_id=current_user.id,
        changes={
            "filename": file.filename,
            "pages": result.pages,
            "checks_inserted": result.checks_inserted,
            "checks_duplicate": result.checks_duplicate,
            "checks_failed": result.checks_failed,
        },
    )
    db.commit()

    return {
        "import_id": result.import_id,
        "pages": result.pages,
        "checks_parsed": result.checks_parsed,
        "checks_inserted": result.checks_inserted,
        "checks_duplicate": result.checks_duplicate,
        "checks_failed": result.checks_failed,
        "summary_blocks_skipped": result.summary_blocks_skipped,
        "report": result.report,
    }
