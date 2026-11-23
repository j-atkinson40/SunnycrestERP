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
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin, require_permission
from app.models.company import Company
from app.services import audit_service
from app.services.payroll.rules import DEFAULT_RULES, DEFAULT_RULE_PROVENANCE
from app.services.payroll.week_calendar import current_payroll_week
from app.services.payroll.data_gate import (
    PAYROLL_DATA_ENABLED,
    assert_payroll_data_enabled,
    is_payroll_data_enabled,
)
from app.models.payroll_report import (
    R115_STATUSES,
    PayrollCheck,
    PayrollRegisterImport,
    PayrollReportEmployee,
    PayrollRuleSet,
    PayrollUnionFormR115,
    PayrollWeek,
)
from app.models.user import User
from app.services.payroll import service as payroll_service
from app.services.payroll import week_focus
from app.services.payroll.column_mapping import UnverifiedMapping, available_mappings
from app.services.payroll.parsers import ExportParseError, ExportPayload
from app.services.payroll.hours_import import (
    HoursImportRefused,
    import_hours,
)
from app.services.payroll.hours_parser import HoursParseError
from app.services.payroll.register_import import import_register
from app.services.payroll.register_people import apply_fills, reconcile
from app.services.payroll import r115 as r115_service
from app.services.payroll import r115_form
from app.services.payroll import r115_schedule
from app.services.payroll import r115_settings
from app.services.payroll.register_parser import RegisterParseError
from app.services.payroll.reports import to_csv
from app.services.payroll.rules import RULE_FIELDS, RULE_STATUSES
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

#: ⚠️ **ADDED 2026-11-13, REVERSING PART OF THE 2026-11-03 RULING.** That
#: ruling made the uploads admin-only because "the payroll reviewer never needs
#: to do it: in the finished shape it is the background payroll job running
#: under its own system actor". The premise was that Opas would pull the hours.
#: The Monday pull is designed and NOT built, and until it exists Susan runs her
#: own week from uploads — which is what she was asked to do.
#:
#: ⚠️ The "brings pay data into existence" gate did not go away; it moved to the
#: control that actually is one. The payroll DATA SWITCH stays admin-only, is
#: tenant-wide, and while it is off NO upload works for anyone, admin included.
#: Uploading a week against a tenant whose switch is already on is routine work.
PAYROLL_UPLOAD = "payroll.upload"


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


@router.get("/weeks/current")
def current_week(
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """The week Susan is working today, whether or not it exists as a row.

    ⚠️ **THE POINT IS THAT IT ANSWERS BEFORE ANY UPLOAD.** Every other payroll
    read needs a `week_id`, and that row is created BY the upload — so with
    nothing uploaded the note had nothing to say, the Payroll page offered no
    link, and the Focus (which carries the upload card) could not open. The
    upload card lived inside the surface the upload had to create.

    `exists` is the whole distinction. When false, the descriptor is derived
    from the calendar and the caller may still open the Focus on it; the row
    appears when the hours are uploaded.
    """
    rules = payroll_service.rules_from_row(
        payroll_service.resolve_rule_set(db, current_user.company_id, date.today())
    ) if _has_rule_set(db, current_user.company_id) else DEFAULT_RULES

    desc = current_payroll_week(
        date.today(),
        cutoff_weekday=rules.payentry_cutoff_weekday,
        cutoff_time=rules.payentry_cutoff_time,
    )
    row = (
        db.query(PayrollWeek)
        .filter(PayrollWeek.tenant_id == current_user.company_id,
                PayrollWeek.week_end_date == desc.week_end_date)
        .first()
    )
    payload = desc.as_dict()
    payload["exists"] = row is not None
    payload["week_id"] = row.id if row else None
    payload["status"] = row.status if row else "no_hours_yet"
    # The provenance of the cutoff travels with it: it is an ASSUMED default,
    # and a screen that states a deadline should be able to say who said so.
    payload["cutoff_provenance"] = DEFAULT_RULE_PROVENANCE["payentry_cutoff"]
    return payload


def _has_rule_set(db: Session, tenant_id: str) -> bool:
    """⚠️ `resolve_rule_set` RAISES when no set covers the date — deliberately,
    so a dues figure can always name its rules. This endpoint states a
    DEADLINE, not a dues figure, and must still answer for a tenant that has
    not been given a rulebook yet. So the absence is checked rather than
    caught: catching would also swallow a real resolution failure."""
    return db.query(PayrollRuleSet).filter(
        PayrollRuleSet.tenant_id == tenant_id).first() is not None


@router.post("/weeks/upload", status_code=201)
async def upload_export(
    file: UploadFile = File(...),
    week_number: int = Form(...),
    week_end_date: date = Form(...),
    format_key: str = Form("payentry"),
    # ⚠️ `payroll.upload`, NOT admin — changed 2026-11-13. The 2026-11-03
    # ruling made this admin-only because "the payroll reviewer never needs to
    # do it: in the finished shape it is the background payroll job running
    # under its own system actor". That premise was Opas pulling the hours, and
    # the Monday pull is designed but NOT built — so until it exists Susan runs
    # her own week from uploads, which is the job she was given.
    #
    # The data switch below is a SECOND, independent gate on the same endpoint,
    # and it is now the one carrying the "brings pay data into existence"
    # weight: this one asks "are you allowed to load", the switch asks "may this
    # tenant hold payroll data at all". The switch stays ADMIN-ONLY and refuses
    # every upload while it is off, admin included. The future job actor will
    # pass the first and still have to satisfy the second.
    current_user: User = Depends(require_permission(PAYROLL_UPLOAD)),
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

    # ─────────────────────────────────────────────────────────────────────────
    # Payroll 3: Payentry's own Employee Hours PDF.
    #
    # ⚠️ **THE SAME ENDPOINT AND THE SAME PARSER AS THE FUTURE MONDAY PULL.**
    # A new format key rather than a new route, and `import_hours` takes BYTES
    # rather than a request — so the scheduled job of Phase 4 hands it exactly
    # what an upload does and there is no second code path to drift.
    #
    # ⚠️ **IDENTITY IS CHECKED AGAINST THE REGISTER AND THE ROSTER, AND A
    # BLOCKING FINDING REFUSES THE WHOLE FILE.** A naive read of the real
    # export reproduces every hour total while turning one employee number
    # into 12008; the only thing that can reject that is a roster.
    if format_key == HOURS_FORMAT_KEY:
        known = _known_emp_ids(db, current_user.company_id)
        checks = db.query(PayrollCheck).filter(
            PayrollCheck.tenant_id == current_user.company_id).all()
        try:
            result = import_hours(
                db, tenant_id=current_user.company_id, content=content,
                filename=file.filename or "employee_hours.pdf",
                week_end_date=week_end_date,
                uploaded_by_user_id=current_user.id,
                known_emp_ids=known, checks=checks)
        except HoursImportRefused as exc:
            # 422: the request is well-formed and the refusal is a stated one.
            raise HTTPException(422, {"code": "hours_import_refused",
                                      "message": str(exc),
                                      "findings": [
                                          {"kind": f.kind, "detail": f.detail}
                                          for f in (exc.report.findings
                                                    if exc.report else [])]}) from exc
        except HoursParseError as exc:
            raise HTTPException(422, {"code": "hours_unreadable",
                                      "message": str(exc)}) from exc
        audit_service.log_action(
            db, current_user.company_id, "payroll_hours_imported",
            "payroll_hours_import", result.import_id, user_id=current_user.id,
            changes={"filename": file.filename, "week_end_date": str(week_end_date),
                     "rows": result.rows_stored,
                     "duplicate_of": result.duplicate_of})
        db.commit()
        return {"import_id": result.import_id, "week_id": result.week_id,
                "week_end_date": str(result.week_end_date),
                "rows_stored": result.rows_stored,
                "week_lines_written": result.week_lines_written,
                "duplicate_of": result.duplicate_of,
                "report": result.report}

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


@router.get("/settings/union-form")
def get_union_form_settings(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """The tenant's R-115 settings: the deadline and the header's own facts.

    ⚠️ **ONE ENDPOINT FOR FOUR SETTINGS, NOT FOUR ENDPOINTS.** They are edited
    together on one screen and read together by one form header; splitting
    them would make a half-saved header possible and would make the admin
    screen issue four requests to show one panel.
    """
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    return r115_settings.all_settings(company)


@router.put("/settings/union-form")
def set_union_form_settings(
    # ⚠️ **A STRING, NOT AN `int`, SO IT CAN BE CLEARED.** Declared
    # `int | None` first, which made `due_day=""` a 422 — and that is the
    # exact body a form sends when somebody empties the field, so the setting
    # could be set and never unset. Parsed below: omitted is unchanged, empty
    # clears, anything else must be a day. The three text fields already
    # worked this way; the number was the odd one out.
    due_day: str | None = Form(None),
    local: str | None = Form(None),
    plant: str | None = Form(None),
    completed_by: str | None = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Set or clear the R-115 settings. Audited, and partial by omission.

    ⚠️ **AN OMITTED FIELD IS UNCHANGED; AN EMPTY ONE IS CLEARED.** A PUT that
    treated every absent field as a clear would wipe the local the moment
    somebody saved only the due date. The distinction is carried by the form
    body: a field not sent is absent, a field sent empty is `""`, and only the
    second clears.

    Clearing is a real operation — a tenant whose local changed its deadline,
    or who got a new plant name, must be able to return to "we do not know"
    rather than leave a stale value standing. The screens then say "Not set".
    """
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    before = r115_settings.all_settings(company)
    sent = {k: v for k, v in (
        (r115_settings.R115_LOCAL, local),
        (r115_settings.R115_PLANT, plant),
        (r115_settings.R115_COMPLETED_BY, completed_by),
    ) if v is not None}

    parsed_day: int | None = None
    clear_day = False
    if due_day is not None:
        if due_day.strip() == "":
            clear_day = True
        else:
            try:
                parsed_day = int(due_day)
            except ValueError:
                raise HTTPException(
                    400,
                    detail={
                        "code": "due_day_not_a_number",
                        "message": (
                            f"{due_day!r} is not a day of the month. Send a "
                            "number from 1 to 31, or an empty value to clear "
                            "the deadline."
                        ),
                    },
                ) from None

    if parsed_day is not None and not (1 <= parsed_day <= 31):
        raise HTTPException(
            400,
            detail={
                "code": "due_day_out_of_range",
                "message": (
                    f"{parsed_day} is not a day of the month. The R-115 due day "
                    "is 1 to 31; it is read in the month after the period, and "
                    "a day past the end of that month falls back to its last "
                    "day."
                ),
            },
        )
    for key, value in sent.items():
        if len(value) > r115_settings.MAX_TEXT:
            raise HTTPException(
                400,
                detail={
                    "code": "setting_too_long",
                    "message": (
                        f"{key} is {len(value)} characters; the limit is "
                        f"{r115_settings.MAX_TEXT}. These are header fields on "
                        "a form, not a notes field."
                    ),
                },
            )

    if clear_day:
        company.set_setting(r115_settings.R115_DUE_DAY, None)
    elif parsed_day is not None:
        company.set_setting(r115_settings.R115_DUE_DAY, parsed_day)
    for key, value in sent.items():
        # ⚠️ An empty string CLEARS rather than storing "". `_text` already
        # reads "" back as unset, so storing it would leave a value the code
        # believes is absent — two states that look the same and are not.
        company.set_setting(key, value.strip() or None)

    after = r115_settings.all_settings(company)
    changed = {k: {"before": before[k], "after": after[k]}
               for k in after if before[k] != after[k]}
    if not changed:
        return {**after, "changed": False}

    audit_service.log_action(
        db, current_user.company_id, "payroll_union_form_settings_changed",
        "company", current_user.company_id, user_id=current_user.id,
        changes=changed,
    )
    db.commit()
    return {**after, "changed": True}


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 4 Phase 1 — the register upload.
#
# ⚠️ **UPLOAD ONLY. NOTHING HERE READS PAYENTRY.** James's ruling: the register
# arrives as a file a person downloaded and chose to upload. There is no
# Payentry credential in this process, no scheduled pull, and no outbound call
# of any kind — so there is nothing here to be given a credential later by
# accident.
# ─────────────────────────────────────────────────────────────────────────────

#: Payroll 3. Payentry's own Employee Hours report, as a PDF.
HOURS_FORMAT_KEY = "payentry_employee_hours"


def _known_emp_ids(db: Session, tenant_id: str) -> set[str]:
    """Every employee id the tenant can account for.

    ⚠️ **THE REGISTER *OR* THE ROSTER** (James, 2026-11-10). The register
    alone is not enough: employee 38 is listed in the real hours file with no
    hours and appears nowhere in a YEAR of registers, so she has to be put on
    the roster before her week will import. That refusal is the check working.
    """
    from_checks = {e for (e,) in db.query(PayrollCheck.emp_id)
                   .filter(PayrollCheck.tenant_id == tenant_id).distinct().all() if e}
    from_roster = {e for (e,) in db.query(PayrollReportEmployee.payentry_file_number)
                   .filter(PayrollReportEmployee.tenant_id == tenant_id).all() if e}
    return from_checks | from_roster


#: A year of registers for one licensee is ~2 MB of PDF. 25 allows several
#: years in one file without allowing a wrong file to be read into memory.
MAX_REGISTER_BYTES = 25 * 1024 * 1024


@router.post("/register/upload")
async def upload_register(
    file: UploadFile = File(...),
    # ⚠️ `payroll.upload`, NOT admin — changed 2026-11-13, same reasoning as
    # the hours upload. Susan pulls the Check Register from Payentry today;
    # importing it here is the same act. The data switch below still refuses
    # it outright while payroll data is off for the tenant.
    current_user: User = Depends(require_permission(PAYROLL_UPLOAD)),
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


@router.get("/register/imports")
def list_register_imports(
    limit: int = 20,
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """Recent register imports, newest first.

    ⚠️ **THIS EXISTS SO A PAGE CAN STOP GUESSING WHETHER AN UPLOAD LANDED.**
    Added 2026-11-17. Until now nothing could answer "did my import go
    through?" from outside the upload's own response — so a client that got no
    response had no way to find out, and the payroll setup page said "nothing
    has been changed", which it could not know.

    A failed request is the case this is for, and it is the one where the
    client's own account is worth least: a CORS rejection, a timeout or a reset
    on the RETURN leg produces a client-side error for work the server may have
    completed. The only trustworthy account of whether a request arrived comes
    from the thing it arrived at.

    ⚠️ **NOT GATED ON THE DATA SWITCH, matching every other read on this
    router.** The switch gates WRITES — `assert_payroll_data_enabled` is called
    on the uploads and the reconcile, not on the reads. That asymmetry is
    deliberate and documented in `data_gate.py`; this endpoint follows it
    rather than introducing a third rule. It returns counts and filenames, not
    pay data.
    """
    limit = max(1, min(limit, 100))
    rows = (
        db.query(PayrollRegisterImport)
        .filter(PayrollRegisterImport.tenant_id == current_user.company_id)
        .order_by(PayrollRegisterImport.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "imports": [
            {
                "import_id": r.id,
                "filename": r.filename,
                "pages": r.pages,
                "checks_parsed": r.checks_parsed,
                "checks_inserted": r.checks_inserted,
                "checks_duplicate": r.checks_duplicate,
                "checks_failed": r.checks_failed,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                # The stored report, so a client that lost the upload response
                # can still show the findings rather than only the counts.
                "report": r.report or {},
            }
            for r in rows
        ],
        "count": len(rows),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 4 Phase 3 — the rulebook, readable.
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/rules")
def get_rule_sets(
    # ⚠️ READ-ONLY for the payroll area, changed 2026-11-13. Susan needs to see
    # which rules produced a figure she is about to approve — a dues result
    # carries its `rule_set_id` and that is meaningless if she cannot read the
    # set. EDITING the rulebook remains an administration act and there is no
    # write endpoint here at all; rule sets are seeded by script.
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """Every effective-dated rule set for this tenant, newest first.

    ⚠️ **EACH VALUE COMES WITH WHO SETTLED IT.** Payroll 1 shipped ten
    constants of which seven faithfully reproduced the accountant's workbook
    and three were open questions, and nothing in the data told them apart — a
    reader seeing `sick_in_dues_hours = True` could not know whether that was a
    decision or a placeholder. `provenance` answers that per key:
    `confirmed` (a person with the authority said so), `measured` (derived from
    real data), `assumed` (reproduces the workbook, nobody confirmed it), or
    `disputed` (two sources disagree and it is NOT settled).

    A `disputed` key is the important one: it means the stored value is being
    used because something has to be, not because it is agreed.
    """
    rows = (
        db.query(PayrollRuleSet)
        .filter(PayrollRuleSet.tenant_id == current_user.company_id)
        .order_by(PayrollRuleSet.effective_date.desc())
        .all()
    )
    out = []
    for row in rows:
        provenance = row.rule_provenance or {}
        out.append({
            "id": row.id,
            "effective_date": row.effective_date.isoformat(),
            "values": {field: str(getattr(row, field)) for field in RULE_FIELDS},
            "provenance": {
                field: provenance.get(field, {"status": "assumed", "source": ""})
                for field in RULE_FIELDS
            },
            "disputed_keys": sorted(
                k for k, v in provenance.items()
                if isinstance(v, dict) and v.get("status") == "disputed"
            ),
        })
    return {"rule_sets": out, "statuses": list(RULE_STATUSES)}


@router.get("/register/people/status")
def register_people_status(
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """What the payroll roster holds, and when it was last reconciled.

    ⚠️ **THIS EXISTS BECAUSE THE OBVIOUS FOLLOW-UP CHECK WAS THE THING THAT
    TIMED OUT.** Measured on production 2026-11-17: the reconcile answered
    **499 after 125 s** — the browser hung up and the server committed 19 s
    later. The first fix proposed for that was "re-run the dry run and see
    whether any `fill` proposals remain", which is the SAME call: a dry run
    took 153 s against the same data. A check that costs what the thing it
    checks cost is not a check.

    So this is four counts and a timestamp — O(1) queries, no rule
    resolution, no per-check arithmetic.

    ⚠️ `last_reconciled_at` COMES FROM THE AUDIT LOG, not from a column on the
    roster, because the audit row is written only on the APPLY path. A roster
    row can be created by other means; "somebody ran the reconcile and it
    committed" is a fact only the audit trail holds.

    Not gated on the data switch, matching every other read on this router.
    """
    tid = current_user.company_id
    total = (
        db.query(PayrollReportEmployee)
        .filter(PayrollReportEmployee.tenant_id == tid)
        .count()
    )
    named = (
        db.query(PayrollReportEmployee)
        .filter(PayrollReportEmployee.tenant_id == tid,
                PayrollReportEmployee.display_name.isnot(None))
        .count()
    )
    members = (
        db.query(PayrollReportEmployee)
        .filter(PayrollReportEmployee.tenant_id == tid,
                PayrollReportEmployee.is_union_member.is_(True))
        .count()
    )
    last = db.execute(text(
        "SELECT created_at FROM audit_logs "
        "WHERE company_id = :c AND action = 'payroll_register_people_reconciled' "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"c": tid}).scalar()
    return {
        "employees": total,
        "with_display_name": named,
        "union_members": members,
        "last_reconciled_at": last.isoformat() if last else None,
    }


@router.post("/register/people/reconcile")
def reconcile_register_people(
    apply: bool = Form(False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Compare the imported register against the payroll roster.

    Admin only, behind the payroll data switch. **Dry run unless `apply` is
    true**, and even then only `fill` proposals are written.

    ⚠️ **IT NEVER OVERWRITES A CURATED FACT.** Every fact the register
    establishes is one somebody may have corrected by hand — a fixed display
    name, a membership flag set for a member between vacation entitlements. So
    a proposal is `fill` (the roster has nothing, nothing to lose), `agree`
    (already says this), or `conflict` (they disagree and a person decides).
    `conflict` is returned and never written.

    ⚠️ **AND `is_union_member` ONLY EVER FILLS UPWARD.** A dues deduction
    PROVES membership; its absence disproves nothing, because a member on
    leave, between entitlements, or simply not paid in the uploaded range has
    no dues line to show.
    """
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)

    # ⚠️ RESOLVED PER CHECK DATE, AND IT REFUSES RATHER THAN FALLING BACK.
    # `resolve_rule_set` deliberately raises when a tenant has no rule set
    # effective on a date, because a dues figure computed from code defaults is
    # a figure that cannot say which rules produced it. A register spans a year,
    # so the rules are resolved per check rather than once.
    # ⚠️ **MEMOISED PER CHECK DATE, AND THE COMMENT BELOW USED TO EXPLAIN WHY
    # IT WAS NOT.** "A register spans a year, so the rules are resolved per
    # check rather than once" is correct about the REQUIREMENT and was being
    # satisfied by re-querying for every check.
    #
    # Measured on production 2026-11-17: `resolve_rule_set` was called **629
    # times across 52 distinct check dates**. The rule set in force on a given
    # date cannot change between two checks that share that date, so 577 of
    # those 629 calls asked a question already answered.
    #
    # ⚠️ **AND THIS IS A CANDIDATE, NOT A DIAGNOSIS.** The reconcile took ~145 s
    # in production and 153 s in a local dry run, and the phase split was never
    # attributed. A 12× cut in rule resolution is worth having on its own; it is
    # NOT a claim that the request now fits inside a browser's patience. The
    # status endpoint above is what makes a slow run survivable, and the two
    # fixes are deliberately independent.
    _rules_by_date: dict = {}

    def rules_for_date(when):
        if when not in _rules_by_date:
            row = payroll_service.resolve_rule_set(db, current_user.company_id, when)
            # Resolution RAISES for a date no rule set covers — deliberately,
            # so a dues figure can always name the rules that produced it.
            #
            # ⚠️ **CACHING AFTER THE CALL IS DEFENSIVE, NOT LOAD-BEARING, AND
            # THE FIRST VERSION OF THIS COMMENT CLAIMED OTHERWISE.** It said a
            # refusal "is never memoised as an answer", which reads as a
            # protection. Break-tested by caching BEFORE resolution: every test
            # stayed green, because this memo is per-REQUEST and the raise
            # aborts that request — so a poisoned entry has no second reader.
            # The protection comes from the memo's lifetime, not from this
            # ordering. Kept anyway: it survives someone later lifting the memo
            # to a wider scope, which is exactly when it would start to matter.
            # CLAUDE.md §11, "a guard whose protection is supplied by a layer
            # beneath it".
            _rules_by_date[when] = payroll_service.rules_from_row(row)
        return _rules_by_date[when]

    try:
        proposals, facts = reconcile(
            db, tenant_id=current_user.company_id, rules_for_date=rules_for_date)
    except payroll_service.PayrollError as exc:
        # 409, not 500: the request is fine and the refusal is a stated one —
        # this tenant has no rulebook covering the checks it has imported.
        raise HTTPException(409, str(exc)) from exc

    applied = []
    if apply:
        applied = apply_fills(db, tenant_id=current_user.company_id,
                              proposals=proposals)
        audit_service.log_action(
            db,
            current_user.company_id,
            "payroll_register_people_reconciled",
            "payroll_report_employee",
            None,
            user_id=current_user.id,
            changes={"applied": [
                {"emp_id": p.emp_id, "field": p.field, "value": str(p.register_says)}
                for p in applied
            ]},
        )
        db.commit()

    def shape(p):
        return {"emp_id": p.emp_id, "field": p.field,
                "register_says": str(p.register_says),
                "roster_says": None if p.roster_says is None else str(p.roster_says),
                "verdict": p.verdict, "why": p.why}

    return {
        "employees_seen": len(facts),
        "union_members_proved": sum(1 for f in facts.values() if f["is_union_member"]),
        "applied": [shape(p) for p in applied],
        "proposals": [shape(p) for p in proposals],
        "conflicts": [shape(p) for p in proposals if p.verdict == "conflict"],
        # ⚠️ Reported, never merged: an id with two printed names is either a
        # parse fault or a real name change, and only a person can tell.
        "ambiguous_names": {
            emp_id: f["name_candidates"] for emp_id, f in facts.items()
            if len(f["name_candidates"]) > 1
        },
        "dry_run": not apply,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 4 Phase 6 — the R-115 union remittance form.
#
# ⚠️ Two remittance reports exist on purpose and are named distinctly:
#   `monthly_dues_remittance`  — from the HOURS export: dues the rules IMPLY
#   `union_remittance_r115`    — from the REGISTER: dues actually DEDUCTED
# They disagree on 76 checks in a measured year. The form sent to the union
# must state what was taken; the other report is how you learn whether what
# was taken was right. Collapsing them would lose that.
# ─────────────────────────────────────────────────────────────────────────────


def _form_shape(form: PayrollUnionFormR115) -> dict:
    return {
        "id": form.id,
        "year": form.year,
        "month": form.month,
        "status": form.status,
        "member_count": form.member_count,
        "total_dues": str(form.total_dues),
        "total_hours": str(form.total_hours),
        "submitted_at": form.submitted_at.isoformat() if form.submitted_at else None,
        "filed_at": form.filed_at.isoformat() if form.filed_at else None,
        "superseded_by_id": form.superseded_by_id,
        "table": form.rows,
        # ⚠️ **THE REMITTANCE, AND IT IS NOT LINE 4.** This field was built
        # as `line_4` on 2026-11-18 and corrected the same day: line 4 is
        # Total Earnings, and the money is the un-numbered Total Remittance.
        # Served rather than derived client-side so one mapping exists.
        "total_remittance": r115_service.total_remittance(
            (form.rows or {}).get("totals") or {"dues_deducted": str(form.total_dues)}
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Payroll employee status — the entrance r234 never had.
#
# ⚠️ `r234` added `payroll_status` / `payroll_status_since` and NOTHING COULD
# WRITE THEM. Measured on production 2026-11-21: 0 of 30 employees carried a
# value, while the R-115's line 1 and `roster_coverage`'s excused branch both
# read them — so line 1 fell back to counting checks and the excused branch
# had never once been taken.
# ─────────────────────────────────────────────────────────────────────────────


def _employee_or_404(db: Session, tenant_id: str, employee_id: str):
    from app.models.payroll_report import PayrollReportEmployee

    emp = (db.query(PayrollReportEmployee)
           .filter(PayrollReportEmployee.tenant_id == tenant_id,
                   PayrollReportEmployee.id == employee_id)
           .first())
    if emp is None:
        # ⚠️ Filtered on tenant FIRST, so another tenant's employee is a 404
        # and not a 403 — a 403 would confirm the id exists.
        raise HTTPException(404, "no such employee for this company")
    return emp


@router.get("/employees/{employee_id}/status")
def get_employee_status(
    employee_id: str,
    current_user: User = Depends(require_permission("payroll.view")),
    db: Session = Depends(get_db),
):
    """One employee's current payroll status, and how it got there."""
    from app.services.payroll import employee_status as status_service

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    emp = _employee_or_404(db, current_user.company_id, employee_id)
    rows = status_service.history(db, employee_id=emp.id)

    names: dict[str, str] = {}
    ids = {r.changed_by_user_id for r in rows if r.changed_by_user_id}
    if ids:
        for u in db.query(User).filter(User.id.in_(ids)).all():
            names[u.id] = f"{u.first_name} {u.last_name}".strip() or u.email

    status, since = status_service.current(emp)
    return {
        "employee_id": emp.id,
        "display_name": emp.display_name,
        # ⚠️ `null` MEANS NOBODY HAS SAID, and is not the same as "active".
        # The client words the difference; the server does not collapse it.
        "status": status,
        "since": since.isoformat() if since else None,
        "history": [status_service.shape_change(r, by_name=names.get(
            r.changed_by_user_id)) for r in rows],
    }


@router.put("/employees/{employee_id}/status", status_code=201)
def set_employee_status(
    employee_id: str,
    status: str = Form(...),
    since: date = Form(...),
    reason: str = Form(...),
    current_user: User = Depends(require_permission(PAYROLL_WRITE)),
    db: Session = Depends(get_db),
):
    """Record a status change. Appends history; never an overwrite.

    ⚠️ **`payroll.approve`, NOT ADMIN.** Susan is the person who knows that
    somebody left — she reconciles the roster against the register every
    week. Requiring an admin would mean the fact is known by one person and
    recordable only by another, which is how it stays unrecorded.
    """
    from app.services.payroll import employee_status as status_service

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    emp = _employee_or_404(db, current_user.company_id, employee_id)
    before = status_service.current(emp)
    try:
        change = status_service.set_status(
            db, employee=emp, status=status, since=since, reason=reason,
            user_id=current_user.id)
    except status_service.EmployeeStatusError as exc:
        raise HTTPException(400, str(exc)) from exc

    audit_service.log_action(
        db, current_user.company_id, "payroll_employee_status_changed",
        "payroll_report_employee", emp.id, user_id=current_user.id,
        changes={"status": {"before": before[0], "after": change.status},
                 "since": {"before": before[1].isoformat() if before[1] else None,
                           "after": change.since.isoformat()},
                 "reason": change.reason},
    )
    db.commit()
    return status_service.shape_change(
        change,
        by_name=f"{current_user.first_name} {current_user.last_name}".strip())


def _r115_subject(year: int, month: int) -> str:
    """What an R-115 copy is ABOUT. One producer — the writer and every
    reader derive the subject here, so a copy cannot be filed under
    "2026-10" and looked up under "2026-10-01"."""
    return f"{year}-{month:02d}"


def _r115_copies(db: Session, user: User, *, year: int, month: int,
                 current: dict | None) -> list[dict]:
    """This month's copies, newest first, with names resolved."""
    from app.core.areas import allowed_area_grants
    from app.services.outgoing_copies import registry as copy_registry
    from app.services.outgoing_copies import service as copy_service

    grants = allowed_area_grants(_limited_to_areas(db, user))
    if "r115" not in copy_registry.readable_kinds(grants):
        return []

    rows = copy_service.copies_for(db, tenant_id=user.company_id,
                                   document_kind="r115",
                                   subject=_r115_subject(year, month))
    names: dict[str, str] = {}
    ids = {r.made_by_user_id for r in rows if r.made_by_user_id}
    if ids:
        for u in db.query(User).filter(User.id.in_(ids)).all():
            names[u.id] = f"{u.first_name} {u.last_name}".strip() or u.email
    return [copy_service.shape(r, current=current, made_by_name=names.get(
        r.made_by_user_id)) for r in rows]


def _limited_to_areas(db: Session, user: User):
    """The caller's role's area limit, read from the ROLE — never a request."""
    from app.models.role import Role

    role = db.query(Role).filter(Role.id == user.role_id).first()
    return getattr(role, "limited_to_areas", None) if role else None


@router.post("/r115/copies", status_code=201)
def record_r115_copy(
    year: int = Form(...),
    month: int = Form(..., ge=1, le=12),
    left_as: str = Form(...),
    sent_how: str | None = Form(None),
    current_user: User = Depends(require_permission("payroll.view")),
    db: Session = Depends(get_db),
):
    """Freeze a copy of this month's R-115 as it leaves.

    ⚠️ **THE SERVER REBUILDS THE FIGURES RATHER THAN TRUSTING THE PAGE.** A
    client posting its own content could freeze anything, and a copy is
    evidence. The cost is a window: if a register is imported between the
    page rendering and the print being taken, the copy records the newer
    figures. That window is small, and the drift it could hide is exactly
    what `differs_from_today` surfaces on every later read.

    ⚠️ **MARKING SENT NEEDS `payroll.approve`; PRINTING NEEDS ONLY `view`.**
    Printing is reading. Saying a form was sent to the union is an assertion
    about the outside world, and it is checked separately below rather than
    by a second route — one place builds the copy, so one place freezes the
    content.
    """
    from app.services.outgoing_copies import service as copy_service
    from app.services.payroll.service import (
        PayrollError,
        resolve_rule_set,
        rules_from_row,
    )

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)

    if left_as == "marked_sent":
        from app.services.permission_service import user_has_permission

        if not user_has_permission(current_user, db, PAYROLL_WRITE):
            raise HTTPException(
                403,
                detail={
                    "code": "insufficient_permission",
                    "message": (
                        "Marking the union form sent is an assertion that it "
                        f"left the building; it needs {PAYROLL_WRITE}. "
                        "Printing it does not."
                    ),
                },
            )

    try:
        rules = rules_from_row(resolve_rule_set(db, current_user.company_id,
                                                date(year, month, 1)))
        built = r115_form.build_lines(db, tenant_id=current_user.company_id,
                                      year=year, month=month, rules=rules)
    except PayrollError as exc:
        raise HTTPException(409, str(exc)) from exc

    content = {
        "lines": built["lines"],
        "header": r115_form.header_for(company, year=year, month=month,
                                       check_dates=built["check_dates"]),
        "check_dates": built["check_dates"],
        "percentage_dues_computed": built["percentage_dues_computed"],
        "percentage_dues_variance": built["percentage_dues_variance"],
    }
    try:
        copy = copy_service.record_copy(
            db, tenant_id=current_user.company_id, document_kind="r115",
            subject=_r115_subject(year, month), content=content,
            left_as=left_as, made_by_user_id=current_user.id,
            sent_how=sent_how,
        )
    except copy_service.OutgoingCopyError as exc:
        raise HTTPException(400, str(exc)) from exc

    audit_service.log_action(
        db, current_user.company_id, "outgoing_copy_recorded",
        "outgoing_copy", copy.id, user_id=current_user.id,
        changes={"document_kind": "r115",
                 "subject": _r115_subject(year, month),
                 "left_as": left_as, "sent_how": sent_how},
    )
    db.commit()
    return copy_service.shape(copy, current=built,
                              made_by_name=f"{current_user.first_name} "
                                           f"{current_user.last_name}".strip())


@router.get("/r115")
def get_r115(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(require_permission("payroll.view")),
    db: Session = Depends(get_db),
):
    """One month's union form, its stage, and what it would say if built.

    ⚠️ **ONE CALL, BECAUSE THE STAGE AND THE FIGURES MUST NOT BE FETCHED
    SEPARATELY.** A screen that read the form from here and the stage from
    somewhere else could render "Sent" above a table from a later rebuild. The
    Focus asks one question — "where does October stand?" — and gets one
    answer.

    `form` is null for a month nobody has built yet; `preview` then carries
    what it WOULD say, so the screen can show the figures beside the button
    that creates it rather than an empty frame. For a month that HAS a form,
    `preview` is null: the stored table is the record, and showing today's
    recomputation beside it would invite reading the wrong one.
    """
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    form = r115_service.live_form(
        db, tenant_id=current_user.company_id, year=year, month=month)

    preview = None
    if form is None:
        try:
            table = r115_service.preview(
                db, tenant_id=current_user.company_id, year=year, month=month)
            preview = {
                "columns": list(table.columns),
                "rows": list(table.rows),
                "totals": table.totals,
                "meta": table.meta,
                "total_remittance": r115_service.total_remittance(table.totals),
            }
        except r115_service.R115Error:
            # ⚠️ NOT AN ERROR TO THE CALLER. "No register covers this month
            # yet" is a true and useful answer to "where does October stand",
            # and a 409 here would make the Focus unable to render the stage
            # it was opened to show. The absence is reported as `preview:
            # null` with the stage still present.
            preview = None

    # ⚠️ THE NUMBERED LINES ARE COMPUTED FOR EVERY MONTH, BUILT OR NOT. The
    # print view lays out the whole form in order, and a month whose form has
    # not been created yet still has to show what it would say — that is what
    # the reader approves. `r115_form` reads the register either way, so the
    # two paths cannot produce different lines.
    from app.services.payroll.service import (
        PayrollError,
        resolve_rule_set,
        rules_from_row,
    )

    # ⚠️ **NO RULE SET IS A REPORTED ABSENCE, NOT A 500 AND NOT A FALLBACK.**
    # `resolve_rule_set` refuses to default on purpose — "seed a rule set
    # rather than falling back to defaults, so the result records which rules
    # produced it" — and lines 5, 6 and 7 are dues components that cannot be
    # computed without one. But the STAGE can: a Focus opened on a tenant
    # whose rules were never seeded must still say where the month stands and
    # why its lines are missing, rather than failing to render at all.
    lines = None
    lines_unavailable = None
    try:
        rules = rules_from_row(resolve_rule_set(db, current_user.company_id,
                                                date(year, month, 1)))
        lines = r115_form.build_lines(db, tenant_id=current_user.company_id,
                                      year=year, month=month, rules=rules)
    except PayrollError as exc:
        lines_unavailable = str(exc)

    return {
        "year": year,
        "month": month,
        "form": _form_shape(form) if form is not None else None,
        "preview": preview,
        "schedule": r115_schedule.schedule_for(
            company, form=form, year=year, month=month, today=date.today()),
        "lines": lines["lines"] if lines else None,
        #: Why the lines are absent, in the words the service used. `null`
        #: when they are present — the two are never both set, so a screen
        #: cannot render a reason beside a table.
        "lines_unavailable": lines_unavailable,
        "warnings": lines["warnings"] if lines else [],
        "adds_up": lines["adds_up"] if lines else None,
        "percentage_dues_computed": (lines["percentage_dues_computed"]
                                     if lines else None),
        "percentage_dues_variance": (lines["percentage_dues_variance"]
                                     if lines else None),
        "initiation_fee_count": lines["initiation_fee_count"] if lines else None,
        "header": r115_form.header_for(
            company, year=year, month=month,
            check_dates=lines["check_dates"] if lines else []),
        # ⚠️ **AREA-FILTERED EVEN HERE, WHERE IT CANNOT CURRENTLY FAIL.**
        # Reaching this route already means passing the payroll area guard,
        # so `readable_kinds` can only say yes today. It is applied anyway
        # because the rule is "copies are visible only to callers who can see
        # that kind's area", and a rule enforced by the route it happens to
        # sit behind is a rule that stops being enforced when the next route
        # serves copies. `tests/test_outgoing_copies.py` holds it.
        "copies": _r115_copies(db, current_user, year=year, month=month,
                               current=lines),
    }


@router.get("/r115/preview")
def preview_r115(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    # Reading the form is the payroll reviewer's job, so `payroll.view` —
    # unlike the register upload, which brings the data into existence.
    current_user: User = Depends(require_permission("payroll.view")),
    db: Session = Depends(get_db),
):
    """The R-115 as it would be for one month. Stores nothing.

    Always grouped by CHECK DATE, and not by a setting: a register has a check
    date and carries no week-end date at all, so the alternative is not a
    choice here, it is unavailable.
    """
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    table = r115_service.preview(
        db, tenant_id=current_user.company_id, year=year, month=month)
    return {
        "report_key": table.report_key,
        "columns": list(table.columns),
        "rows": list(table.rows),
        "totals": table.totals,
        "meta": table.meta,
    }


@router.post("/r115")
def build_r115(
    year: int = Form(...),
    month: int = Form(..., ge=1, le=12),
    current_user: User = Depends(require_permission(PAYROLL_WRITE)),
    db: Session = Depends(get_db),
):
    """Create or refresh this month's DRAFT form from the register.

    A submitted or filed form is never rebuilt in place — it refuses with 409,
    the same way an approved payroll week refuses recalculation. The stored
    table is the record of what was sent; rebuilding it would replace that
    record with today's answer.
    """
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    try:
        form = r115_service.build(
            db, tenant_id=current_user.company_id, year=year, month=month)
    except r115_service.R115Error as exc:
        raise HTTPException(409, str(exc)) from exc
    audit_service.log_action(
        db, current_user.company_id, "payroll_r115_built",
        "payroll_union_form_r115", form.id, user_id=current_user.id,
        changes={"year": year, "month": month,
                 "member_count": form.member_count,
                 "total_dues": str(form.total_dues)},
    )
    db.commit()
    return _form_shape(form)


@router.post("/r115/{form_id}/status")
def advance_r115(
    form_id: str,
    to_status: str = Form(...),
    current_user: User = Depends(require_permission(PAYROLL_WRITE)),
    db: Session = Depends(get_db),
):
    """Move the form through draft -> submitted -> filed.

    `filed` is terminal. A correction is a NEW form that supersedes this one,
    never a change to it: a filed figure that can be overwritten is not
    evidence of anything.
    """
    form = (
        db.query(PayrollUnionFormR115)
        .filter(PayrollUnionFormR115.id == form_id,
                PayrollUnionFormR115.tenant_id == current_user.company_id)
        .first()
    )
    if form is None:
        raise HTTPException(404, "no such R-115 form")
    before = form.status
    try:
        r115_service.advance(db, form, to_status)
    except r115_service.R115Error as exc:
        raise HTTPException(409, str(exc)) from exc
    audit_service.log_action(
        db, current_user.company_id, "payroll_r115_status_changed",
        "payroll_union_form_r115", form.id, user_id=current_user.id,
        changes={"status": {"before": before, "after": form.status}},
    )
    db.commit()
    return _form_shape(form)


@router.post("/r115/{form_id}/supersede")
def supersede_r115(
    form_id: str,
    current_user: User = Depends(require_permission(PAYROLL_WRITE)),
    db: Session = Depends(get_db),
):
    """Replace a submitted or filed form with a fresh draft correction.

    The old form keeps its stored table and gains `superseded_by_id`, so the
    record of what was sent survives the correction.
    """
    form = (
        db.query(PayrollUnionFormR115)
        .filter(PayrollUnionFormR115.id == form_id,
                PayrollUnionFormR115.tenant_id == current_user.company_id)
        .first()
    )
    if form is None:
        raise HTTPException(404, "no such R-115 form")
    try:
        replacement = r115_service.supersede(db, form)
    except r115_service.R115Error as exc:
        raise HTTPException(409, str(exc)) from exc
    audit_service.log_action(
        db, current_user.company_id, "payroll_r115_superseded",
        "payroll_union_form_r115", form.id, user_id=current_user.id,
        changes={"superseded_by": replacement.id},
    )
    db.commit()
    return {"superseded": _form_shape(form), "replacement": _form_shape(replacement),
            "statuses": list(R115_STATUSES)}


# ─────────────────────────────────────────── Payroll 5a: the weekly Focus
#
# ⚠️ **THE READS TAKE `payroll.view`, THE TWO WRITES TAKE `payroll.approve`,
# AND EVERY ONE OF THEM IS BEHIND THE DATA SWITCH.** James's ruling of
# 2026-11-13. Reading a week's dues is the job Susan was given; deciding a
# finding and correcting somebody's hours change what payroll pays, and they
# sit at the change level with the week approval they feed.
#
# ⚠️ The switch is checked on the READS too, not only the writes. A tenant
# whose switch is off holds no payroll data, so a Focus there can only report
# on rows that should not exist — and answering 200 with an empty Focus would
# make "the switch is off" look like "there is nothing this week".


@router.get("/weeks/{week_id}/focus")
def get_week_focus(
    week_id: str,
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """The weekly payroll Focus: the dues summary, decisions and corrections."""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    week = _get_week(db, week_id, current_user.company_id)
    return week_focus.week_focus(db, week)


@router.get("/weeks/{week_id}/panes/union-dues")
def get_union_dues_pane(
    week_id: str,
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """Pane: every member's hours and dues for the week, and the total."""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    week = _get_week(db, week_id, current_user.company_id)
    try:
        return week_focus.union_dues_pane(db, week)
    except payroll_service.PayrollError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/weeks/{week_id}/panes/member/{employee_id}")
def get_member_pane(
    week_id: str,
    employee_id: str,
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """Pane: the working behind one member's dues — the figures and the rate."""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    week = _get_week(db, week_id, current_user.company_id)
    pane = week_focus.member_pane(db, week, employee_id)
    if pane is None:
        raise HTTPException(404, "No dues result for that employee on this week")
    return pane


@router.get("/weeks/{week_id}/panes/timecard/{employee_id}")
def get_timecard_pane(
    week_id: str,
    employee_id: str,
    current_user: User = Depends(require_permission(PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    """Pane: the week's days for one person, with corrections and punch counts.

    ⚠️ Never coordinates. `any_punch_has_location` is a boolean and the only
    thing stored — James's ruling of 2026-11-10.
    """
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    week = _get_week(db, week_id, current_user.company_id)
    return week_focus.timecard_pane(db, week, employee_id)


@router.post("/weeks/{week_id}/corrections", status_code=201)
def post_hour_correction(
    week_id: str,
    emp_id: str = Form(...),
    work_date: date = Form(...),
    pay_type: str = Form(...),
    hours: Decimal = Form(...),
    reason: str = Form(...),
    current_user: User = Depends(require_permission(PAYROLL_WRITE)),
    db: Session = Depends(get_db),
):
    """A hand-entered hours correction. Appended, never written over the import."""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    week = _get_week(db, week_id, current_user.company_id)
    try:
        row = week_focus.record_correction(
            db, week, emp_id=emp_id, work_date=work_date, pay_type=pay_type,
            hours=hours, reason=reason, user_id=current_user.id,
        )
    except week_focus.FocusWriteError as exc:
        raise HTTPException(422, str(exc)) from exc

    audit_service.log_action(
        db, current_user.company_id, "payroll_hours_corrected",
        "payroll_week", week.id, user_id=current_user.id,
        changes={"emp_id": emp_id, "work_date": work_date.isoformat(),
                 "pay_type": pay_type, "hours": str(hours),
                 "correction_id": row.id})
    db.commit()
    return {"id": row.id, "emp_id": row.emp_id,
            "work_date": row.work_date.isoformat(), "pay_type": row.pay_type,
            "hours": str(row.hours), "reason": row.reason}


@router.post("/weeks/{week_id}/decisions", status_code=201)
def post_week_decision(
    week_id: str,
    finding_key: str = Form(...),
    outcome: str = Form(...),
    note: str = Form(""),
    current_user: User = Depends(require_permission(PAYROLL_WRITE)),
    db: Session = Depends(get_db),
):
    """Record what was decided about one finding. Supersedes, never overwrites."""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    assert_payroll_data_enabled(company)
    week = _get_week(db, week_id, current_user.company_id)
    try:
        row = week_focus.record_decision(
            db, week, key=finding_key, outcome=outcome, note=note,
            user_id=current_user.id,
        )
    except week_focus.FocusWriteError as exc:
        raise HTTPException(422, str(exc)) from exc

    audit_service.log_action(
        db, current_user.company_id, "payroll_week_decided",
        "payroll_week", week.id, user_id=current_user.id,
        changes={"finding_key": row.finding_key, "outcome": row.outcome,
                 "decision_id": row.id})
    db.commit()
    return {"id": row.id, "finding_key": row.finding_key,
            "outcome": row.outcome, "note": row.note}
