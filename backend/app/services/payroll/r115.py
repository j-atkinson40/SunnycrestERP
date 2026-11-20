"""Build and advance the R-115 union remittance form — Payroll 4 Phase 6.

⚠️ **THE FORM IS BUILT FROM WHAT WAS DEDUCTED, NOT FROM WHAT THE RULES IMPLY.**
The union is being told how much was taken from its members' pay. That figure
is the register's `Union` deduction, not a recomputation — and the two disagree
on 76 checks in a measured year. `monthly_dues_remittance` is kept beside this
precisely so the disagreement stays visible rather than being resolved by
whichever report happened to be run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.payroll_report import (
    R115_STATUSES,
    R115_TRANSITIONS,
    PayrollCheck,
    PayrollUnionFormR115,
)
from app.services.payroll.register_dues import actual_dues, dues_wage_and_hours
from app.services.payroll.register_parser import DUES_DEDUCTION_CODE
from app.services.payroll.reports import R115Row, ReportTable, union_remittance_r115

ZERO = Decimal("0")


class R115Error(ValueError):
    """The form cannot be built or cannot move where it was asked to move."""


#: ⚠️ **[CORRECTED 2026-11-18 — THE FIRST VERSION HAD LINE 4 WRONG, AND THE
#: WAY IT GOT THERE IS THE POINT.]** This block read:
#:
#:     line 4 is the total dues remitted — the money being sent, which for
#:     the live October 2026 month is $979.73
#:
#: **Line 4 is "Total Earnings (excl. lump sum)"** — the month's dues WAGE.
#: The money remitted is its own un-numbered field at the foot of the form,
#: **Total Remittance**, and $979.73 is that. The two were conflated.
#:
#: ⚠️ The session that built it searched for `"line 4"`, found nothing, and
#: reported the field map as absent from the repository. That was a
#: CONSTRUCTED PATTERN — the map is written in the form's own vocabulary
#: ("Total Earnings", "bargaining unit", "lump sum"), which that grep cannot
#: match. The absence was a failed lookup reported as a finding, and the
#: answer given in its place was built without the map being read.
#:
#: The full line set now lives in `r115_form.py` and in
#: `docs/specs/payroll-reports.md` §11.8a, so the next reader finds it instead
#: of asking. This module keeps only the mapping the ENDPOINTS need.
R115_LINES: dict[int, str] = {
    1: "members_in_unit",
    2: "members_paying_dues",
    3: "hours_in_earnings",
    4: "total_earnings",
    5: "percentage_dues",
    6: "per_hour_dues",
    7: "initiation_fees",
    8: "lump_sum",
    9: "misc",
}

#: The un-numbered field at the foot. Named separately BECAUSE conflating it
#: with a numbered line is the error this file records.
TOTAL_REMITTANCE_KEY = "total_remittance"

#: The report-table totals key holding the money actually deducted.
#: `union_remittance_r115` names it `dues_deducted` — deducted, not implied,
#: which is why this form exists beside `monthly_dues_remittance`.
REMITTANCE_TOTALS_KEY = "dues_deducted"


def total_remittance(totals: dict) -> str:
    """The money remitted, as a string, from a report table's totals.

    ⚠️ **THIS IS NOT LINE 4.** It is the Total Remittance field. The name says
    so because the previous name (`line_4_amount`) said the opposite and was
    believed.

    Takes the TOTALS rather than the form so a preview and a stored form give
    the same answer through the same code.
    """
    value = totals.get(REMITTANCE_TOTALS_KEY)
    if value is None:
        raise R115Error(
            f"the report totals carry no {REMITTANCE_TOTALS_KEY!r}, so the "
            f"remittance cannot be stated. Totals present: {sorted(totals)}"
        )
    return str(value)


def rows_for_month(db: Session, *, tenant_id: str, year: int, month: int) -> list[R115Row]:
    """Every check in the month that carried a union deduction.

    ⚠️ Filtered in the DATABASE on the check date, not in Python over every
    check the tenant has. A year of registers is 1,275 rows for one small
    licensee; a form for one month must not get slower every time a register is
    uploaded.
    """
    from sqlalchemy import extract

    checks = (
        db.query(PayrollCheck)
        .filter(PayrollCheck.tenant_id == tenant_id)
        .filter(extract("year", PayrollCheck.check_date) == year)
        .filter(extract("month", PayrollCheck.check_date) == month)
        .all()
    )
    rows: list[R115Row] = []
    for check in checks:
        dues = actual_dues(check)
        if dues == 0:
            # No dues line: nothing to remit for this check. See
            # `union_remittance_r115` on why that is an absence, not a zero row.
            continue
        _wage, hours = dues_wage_and_hours(check)
        rows.append(R115Row(
            emp_id=check.emp_id,
            display_name=check.person,
            check_date=check.check_date,
            check_number=check.check_number,
            dues_deducted=dues,
            dues_hours=hours,
        ))
    return rows


def preview(db: Session, *, tenant_id: str, year: int, month: int) -> ReportTable:
    """The form as it would be, computing and storing nothing."""
    return union_remittance_r115(
        rows_for_month(db, tenant_id=tenant_id, year=year, month=month),
        year=year, month=month,
    )


def live_form(db: Session, *, tenant_id: str, year: int, month: int):
    """The one form for this month that has not been superseded."""
    return (
        db.query(PayrollUnionFormR115)
        .filter(PayrollUnionFormR115.tenant_id == tenant_id,
                PayrollUnionFormR115.year == year,
                PayrollUnionFormR115.month == month,
                PayrollUnionFormR115.superseded_by_id.is_(None))
        .first()
    )


def build(db: Session, *, tenant_id: str, year: int, month: int) -> PayrollUnionFormR115:
    """Create or refresh this month's DRAFT form from the register.

    ⚠️ **A SUBMITTED OR FILED FORM IS NEVER REBUILT.** It refuses, the same way
    an approved payroll week refuses recalculation and for the same reason: the
    stored table is the record of what was sent, and rebuilding it in place
    would quietly replace that record with today's answer. A correction is a
    NEW form — see `supersede`.
    """
    table = preview(db, tenant_id=tenant_id, year=year, month=month)
    if not table.rows:
        raise R115Error(
            f"no union deductions found for {year}-{month:02d}. Either no "
            "register covering that month has been imported, or no member had "
            "dues taken — and those are different situations, so the form is "
            "not created empty."
        )

    form = live_form(db, tenant_id=tenant_id, year=year, month=month)
    if form is not None and form.status != "draft":
        raise R115Error(
            f"the {year}-{month:02d} form is {form.status}, not draft. A "
            "submitted or filed form records what was sent and is not rebuilt "
            "in place; supersede it with a correction instead."
        )
    if form is None:
        form = PayrollUnionFormR115(tenant_id=tenant_id, year=year, month=month)
        db.add(form)

    form.status = "draft"
    form.member_count = len(table.rows)
    form.total_dues = Decimal(table.totals["dues_deducted"])
    form.total_hours = Decimal(table.totals["dues_hours"])
    form.rows = {"columns": list(table.columns), "rows": list(table.rows),
                 "totals": table.totals, "meta": table.meta}
    db.flush()
    return form


def advance(db: Session, form: PayrollUnionFormR115, to_status: str) -> PayrollUnionFormR115:
    """Move the form forward through its flow, or refuse and say why.

    ⚠️ `filed` is terminal by having NO entry in `R115_TRANSITIONS`, rather
    than by a special case in this function. A terminal state enforced by a
    missing map entry cannot be bypassed by someone adding a branch here.
    """
    if to_status not in R115_STATUSES:
        raise R115Error(f"{to_status!r} is not a status; expected one of {R115_STATUSES}")
    allowed = R115_TRANSITIONS.get(form.status, ())
    if to_status not in allowed:
        raise R115Error(
            f"a {form.status} form cannot become {to_status}. "
            + (f"From {form.status} it may become: {', '.join(allowed)}."
               if allowed else
               f"{form.status} is terminal — a correction is a new form, not "
               "a change to this one.")
        )
    now = datetime.now(timezone.utc)
    form.status = to_status
    if to_status == "submitted":
        form.submitted_at = now
    elif to_status == "filed":
        form.filed_at = now
    db.flush()
    return form


def supersede(db: Session, form: PayrollUnionFormR115) -> PayrollUnionFormR115:
    """Replace a submitted or filed form with a fresh draft correction.

    The old form keeps its own stored table and gains `superseded_by_id`, so
    the record of what was sent survives the correction. That is the whole
    point: a filed figure that can be overwritten is not evidence of anything.
    """
    if form.status == "draft":
        raise R115Error(
            "a draft form is rebuilt, not superseded — there is nothing filed "
            "to preserve."
        )
    replacement = PayrollUnionFormR115(
        tenant_id=form.tenant_id, year=form.year, month=form.month, status="draft")
    db.add(replacement)
    db.flush()
    form.superseded_by_id = replacement.id
    db.flush()
    return build(db, tenant_id=form.tenant_id, year=form.year, month=form.month)
