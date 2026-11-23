"""Payroll 5a — the weekly payroll Focus and its three panes.

What Susan opens on a Tuesday: the week's union dues, what Opas flagged, and
the detail behind any one member. Read-only except for two writes the Focus
owns — a hand correction to someone's hours, and a decision about a finding.

⚠️ **THE FIGURES ARE NOT RECOMPUTED HERE.** Dues come from
`payroll_week_results` through `service.build_report`, which is the same source
the deduction register and the monthly remittance read. A second computation in
a presentation layer is a second answer, free to disagree with the one that was
approved — and the one on screen is the one Susan would trust.

⚠️ **A DECISION IS KEYED ON THE FINDING, NOT ON A ROW.** Findings are recomputed
from the imports every time the week is opened, so anything derived from the run
would lose the decision the moment the week was recalculated. `finding_key`
builds the key from what the finding is ABOUT.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollHourCorrection,
    PayrollHoursLine,
    PayrollPunch,
    PayrollReportEmployee,
    PayrollWeek,
    PayrollWeekDecision,
    PayrollWeekLine,
)
from app.services.payroll import service as payroll_service
from app.services.payroll.validation import reconcile_roster

logger = logging.getLogger(__name__)

ZERO = Decimal("0.0000")

#: The payroll week runs Sunday to Saturday; `week_end_date` is the Saturday.
_WEEK_SPAN = timedelta(days=6)

#: One week. Mirrors `ck_payroll_hour_correction_plausible`; see the model.
_MAX_CORRECTION_HOURS = Decimal("168")


def _now() -> datetime:
    return datetime.now(timezone.utc)

#: ⚠️ A DECLARED SET, VALIDATED AT THE EDGE. An unrecognised outcome renders as
#: nothing at all, so it is refused rather than stored. Kept here next to the
#: words they mean so the two cannot drift.
DECISION_OUTCOMES: dict[str, str] = {
    "settled": "Looked at and correct as it stands.",
    "corrected": "Hours were corrected; see the correction.",
    "asked": "Asked someone and waiting on an answer.",
    "not_an_issue": "Looked at and not a problem.",
}


def finding_key(kind: str, *, emp_id: str | None = None,
                on_date: date | None = None) -> str:
    """Stable identity for a finding: `kind:emp_id:date`, empty parts kept.

    ⚠️ The separator positions are FIXED even when a part is absent, so
    `("missed_punch", emp_id="12008")` can never collide with a different kind
    that happens to have a date where this one has none.
    """
    return ":".join((kind, emp_id or "", on_date.isoformat() if on_date else ""))


# ───────────────────────────────────────────────────── corrections as overlay


def live_corrections(db: Session, *, tenant_id: str, week_end_date: date,
                     emp_id: str | None = None) -> list[PayrollHourCorrection]:
    """Corrections not superseded by a later one, oldest first."""
    q = (
        select(PayrollHourCorrection)
        .where(PayrollHourCorrection.tenant_id == tenant_id)
        .where(PayrollHourCorrection.week_end_date == week_end_date)
        .where(PayrollHourCorrection.superseded_at.is_(None))
        .order_by(PayrollHourCorrection.entered_at)
    )
    if emp_id is not None:
        q = q.where(PayrollHourCorrection.emp_id == emp_id)
    return list(db.execute(q).scalars().all())


@dataclass(frozen=True)
class DayHours:
    """One day of one person's hours, parsed and corrected shown separately.

    ⚠️ **BOTH, NOT A MERGED TOTAL.** "Payentry said 6.5 and Susan added 1.5" is
    the fact a reviewer needs; a single 8.0 hides who decided it. The template
    shows the total and the correction as a note, which it can only do if the
    two arrive apart.
    """

    work_date: date
    pay_type: str
    parsed: Decimal
    corrected: Decimal

    @property
    def total(self) -> Decimal:
        return self.parsed + self.corrected


def day_hours(db: Session, *, tenant_id: str, week_end_date: date,
              emp_id: str) -> list[DayHours]:
    """Per (day, pay type) hours for one person: parsed plus any correction.

    A correction may stand alone. A punch that never reached Payentry's export
    is the commonest real case, and there is then no parsed line for that day —
    so the keys are the UNION of both sides, not the parsed side's.
    """
    parsed: dict[tuple[date, str], Decimal] = {}
    rows = db.execute(
        select(PayrollHoursLine)
        .where(PayrollHoursLine.tenant_id == tenant_id)
        .where(PayrollHoursLine.week_end_date == week_end_date)
        .where(PayrollHoursLine.emp_id == emp_id)
    ).scalars().all()
    for r in rows:
        k = (r.work_date, r.pay_type)
        parsed[k] = parsed.get(k, ZERO) + r.hours

    corrected: dict[tuple[date, str], Decimal] = {}
    for c in live_corrections(db, tenant_id=tenant_id,
                              week_end_date=week_end_date, emp_id=emp_id):
        k = (c.work_date, c.pay_type)
        corrected[k] = corrected.get(k, ZERO) + c.hours

    out = [
        DayHours(work_date=d, pay_type=p,
                 parsed=parsed.get((d, p), ZERO),
                 corrected=corrected.get((d, p), ZERO))
        for (d, p) in sorted(set(parsed) | set(corrected))
    ]
    return out


# ───────────────────────────────────────────────────────────────── the panes


def union_dues_pane(db: Session, week: PayrollWeek) -> dict:
    """Pane: every member's hours and dues for the week, and the total.

    Straight from the stored results. `members_paying` counts rows with dues
    above zero and is reported ALONGSIDE the row count rather than instead of
    it — "11 of 13" is the sentence Susan reads, and one number cannot say it.
    """
    report = payroll_service.build_report(db, week, "weekly_dues_detail")
    rows = list(report.rows or ())
    paying = sum(1 for r in rows if Decimal(r.get("dues") or "0.00") > 0)
    return {
        "week_number": week.week_number,
        "week_end_date": week.week_end_date.isoformat(),
        "check_date": week.check_date.isoformat(),
        "status": week.status,
        "members": rows,
        "members_total": len(rows),
        "members_paying": paying,
        "total_dues": report.totals.get("dues"),
        "total_dues_hours": report.totals.get("dues_hours"),
        # ⚠️ The formula in words, served with the numbers rather than written
        # into the template. The rule set is effective-dated, so a pane that
        # hard-coded "1.45%" would keep saying it after the rate changed.
        "basis": _dues_basis(db, week),
    }


def _dues_basis(db: Session, week: PayrollWeek) -> dict:
    """The rule set in force for this week's check date, in words."""
    rs = payroll_service.resolve_rule_set(db, week.tenant_id, week.check_date)
    rules = payroll_service.rules_from_row(rs)
    # ⚠️ DIRECT ATTRIBUTE ACCESS, NOT `getattr(..., default)`. A first draft
    # used `getattr(rules, "dues_percent", "")` and every one of those names
    # was wrong — the fields are `dues_pct` and `dues_cap_multiplier`. The
    # defaults turned three wrong names into three empty strings and the pane
    # would have rendered a blank formula with nothing failing anywhere.
    return {
        "percent": str(rules.dues_pct),
        "cap_multiplier": str(rules.dues_cap_multiplier),
        "per_hour": str(rules.dues_per_hour),
        "rule_set_effective": rs.effective_date.isoformat(),
        "sentence": (
            "Each member's dues: the lower of the percentage of dues wage and "
            "the cap, plus the per-hour amount."
        ),
    }


def member_pane(db: Session, week: PayrollWeek, emp_id: str) -> dict | None:
    """Pane: the working behind one member's dues for the week.

    Returns None when the member has no result on this week, which is a real
    answer rather than an error — somebody with no hours has no dues row.
    """
    report = payroll_service.build_report(db, week, "weekly_dues_detail")
    row = next((r for r in (report.rows or ())
                if r.get("employee_id") == emp_id), None)
    if row is None:
        return None

    line = db.execute(
        select(PayrollWeekLine)
        .where(PayrollWeekLine.week_id == week.id)
        .where(PayrollWeekLine.employee_id == emp_id)
    ).scalars().first()

    emp = db.get(PayrollReportEmployee, emp_id)
    return {
        "employee_id": emp_id,
        "display_name": row.get("display_name"),
        "file_number": row.get("file_number"),
        "dept": row.get("dept"),
        "week_number": week.week_number,
        "hours": {
            "reg": str(line.reg_hrs) if line else None,
            "ot": str(line.ot_hrs) if line else None,
            "personal": str(line.personal_hrs) if line else None,
            "sick": str(line.sick_hrs) if line else None,
            "vacation": str(line.vac_hrs) if line else None,
            "dues_hours": row.get("dues_hours"),
        },
        "dues_wage": row.get("dues_wage"),
        # ⚠️ WHICH OT RATE WAS USED, AND WHETHER IT WAS DERIVED. The week-44
        # investigation turned entirely on this: the workbook's typed OT rates
        # were stale, and the difference was invisible until the rate used was
        # shown next to the figure it produced.
        "ot_rate_used": row.get("ot_rate_used"),
        "ot_rate_derived": row.get("ot_rate_derived"),
        "working": {
            "component_a": row.get("component_a"),
            "component_b": row.get("component_b"),
            "component_c": row.get("component_c"),
            "binds": row.get("binds"),
            "initiation_fee": row.get("initiation_fee"),
        },
        "dues": row.get("dues"),
        "union_member": bool(emp.is_union_member) if emp else None,
    }


def timecard_pane(db: Session, week: PayrollWeek, emp_id: str) -> dict:
    """Pane: the week's days for one person, with corrections and punch flags.

    ⚠️ `has_location` only. GPS coordinates are never stored — James's ruling
    of 2026-11-10 — so this reports WHETHER a punch carried a location and
    never where.
    """
    days = day_hours(db, tenant_id=week.tenant_id,
                     week_end_date=week.week_end_date, emp_id=emp_id)

    punches = db.execute(
        select(PayrollPunch)
        .where(PayrollPunch.tenant_id == week.tenant_id)
        .where(PayrollPunch.week_end_date == week.week_end_date)
        .where(PayrollPunch.emp_id == emp_id)
        .order_by(PayrollPunch.punch_at)
    ).scalars().all()

    by_day: dict[date, list] = {}
    for p in punches:
        by_day.setdefault(p.punch_at.date(), []).append(p)

    return {
        "employee_id": emp_id,
        "week_number": week.week_number,
        "week_end_date": week.week_end_date.isoformat(),
        "days": [
            {
                "work_date": d.work_date.isoformat(),
                "pay_type": d.pay_type,
                "parsed_hours": str(d.parsed),
                "corrected_hours": str(d.corrected),
                "total_hours": str(d.total),
                # An odd number of punches is an unpaired punch — someone
                # clocked in and never out. Stated as a count rather than a
                # verdict; the finding is `punch_findings`' job, not a pane's.
                "punch_count": len(by_day.get(d.work_date, ())),
                "any_punch_has_location": any(
                    p.has_location for p in by_day.get(d.work_date, ())
                ),
            }
            for d in days
        ],
        "total_parsed": str(sum((d.parsed for d in days), ZERO)),
        "total_corrected": str(sum((d.corrected for d in days), ZERO)),
        # ⚠️ Said plainly rather than implied by an empty list: no punch file
        # for the week and a person who never punched look identical from
        # outside, and only one of them is worth asking about.
        "punch_data_present": bool(punches),
        "source": "Payentry Employee Hours; punches from Punch Location",
    }


# ───────────────────────────────────────────────────────────── the Focus itself


def week_focus(db: Session, week: PayrollWeek) -> dict:
    """The weekly payroll Focus: the dues summary and what is outstanding."""
    dues = union_dues_pane(db, week)
    decisions = {
        d.finding_key: d
        for d in db.execute(
            select(PayrollWeekDecision)
            .where(PayrollWeekDecision.tenant_id == week.tenant_id)
            .where(PayrollWeekDecision.week_end_date == week.week_end_date)
            .where(PayrollWeekDecision.superseded_at.is_(None))
        ).scalars().all()
    }
    corrections = live_corrections(db, tenant_id=week.tenant_id,
                                   week_end_date=week.week_end_date)

    # ⚠️ **FINDINGS ARE RECOMPUTED READ-ONLY, THROUGH THE ONE IMPLEMENTATION.**
    #
    # `calculate_week(..., persist=False)` is what the calculate endpoint runs,
    # minus the writing. Reusing it means the findings Susan answers in the
    # Focus are the same findings the import reported — a second set computed
    # here for display would be a second opinion, and the two would diverge the
    # first time either changed.
    #
    # It costs the calculation on every open. Accepted deliberately: the
    # alternative is storing flags, and a stored flag outlives the condition
    # that produced it — an answered finding would keep reappearing, or a new
    # one would never show until somebody re-imported.
    findings: list[dict] = []
    try:
        recomputed = payroll_service.calculate_week(db, week, persist=False)
        flags = list(recomputed.flags or ())

        # ⚠️ **THE ROSTER MISMATCH IS NOT IN `calculate_week`, AND IT IS THE
        # FINDING THAT MATTERS MOST.**
        #
        # `calculate_week` flags things about LINES it can see — zero hours with
        # pay, an odd OT rate, a missing rate. A union member who is absent from
        # the hours export has no line, so nothing in that pass can notice them.
        # The flag is raised at IMPORT, by comparing the export's file numbers
        # against the configured roster, and then it is gone: the week Susan
        # opens on Tuesday would have shown her nothing about Stevenson.
        #
        # That is exactly how he went unpaid. So the comparison is re-run here
        # from stored rows — the file numbers WITH a line this week against the
        # active union members — through `reconcile_roster`, the same function
        # the import uses, rather than a second implementation of "who is
        # missing".
        configured = {
            e.payentry_file_number: e
            for e in db.execute(
                select(PayrollReportEmployee)
                .where(PayrollReportEmployee.tenant_id == week.tenant_id)
            ).scalars().all()
            if e.payentry_file_number
        }
        with_lines = {
            configured_fn
            for configured_fn, emp in configured.items()
            if db.execute(
                select(PayrollWeekLine.id)
                .where(PayrollWeekLine.week_id == week.id)
                .where(PayrollWeekLine.employee_id == emp.id)
                .limit(1)
            ).first() is not None
        }
        flags.extend(reconcile_roster(with_lines, configured))

        # ⚠️ **THE CLOCK-TIME QUESTIONS, TURNED ON 2026-11-23.** `punch_findings`
        # has had all four since Payroll 3 — unpaired punches, early clock-ins,
        # clustered early departures and the Saturday rule — and **nothing had
        # ever called `all_findings`**, because `PayrollPunch` had no writer.
        # Complete machinery behind an unprovisioned entrance; the writer
        # landed with the punch import and this is the entrance.
        #
        # ⚠️ **SILENT WHEN NO PUNCH FILE WAS LOADED, WHICH IS NOT THE SAME AS
        # NOTHING TO REPORT.** A week with no punches yields no clock findings
        # — correctly — and the timecard pane already says a punch file was
        # not loaded, so the absence is stated somewhere a reader will see it
        # rather than read as "all clear".
        from app.services.payroll import punch_findings, punch_import

        punch_days = punch_import.stored_days(
            db, tenant_id=week.tenant_id, week_end_date=week.week_end_date)
        clock_findings = (punch_findings.all_findings(punch_days)
                          if punch_days else [])

        findings = [
            {
                "key": finding_key(f.code, emp_id=f.file_number or None),
                "code": f.code,
                "severity": f.severity,
                "message": f.message,
                "file_number": f.file_number,
                "employee_id": f.employee_id,
                "detail": f.detail,
            }
            for f in flags
        ]
        findings.extend({
            # ⚠️ KEYED ON THE DATE AS WELL AS THE KIND. A missed punch on
            # Tuesday and one on Thursday are two decisions; `finding_key`
            # keeps the separators so a kind with no date cannot collide with
            # the same kind that has one.
            "key": finding_key(f.kind, on_date=f.on_date),
            "code": f.kind,
            "severity": "warning",
            "message": f.detail,
            "file_number": None,
            "employee_id": None,
            # ⚠️ `shift_status` TRAVELS WITH IT so a reader can tell a
            # conclusion from a guess without looking up the rule — and the
            # Saturday rule is exactly where that matters, since Saturday has
            # no regular shift to be early or late against.
            "detail": {"on_date": f.on_date.isoformat(),
                       "people": list(f.people),
                       "shift_status": f.shift_status},
        } for f in clock_findings)
    except Exception:
        # A week that cannot be recalculated still has a Focus: its dues and
        # decisions are stored and readable. Reported as a flag of its own
        # rather than as an empty list, because "no findings" and "the findings
        # could not be computed" must not render identically.
        logger.exception("findings recompute failed for week %s", week.id)
        findings = [{
            "key": finding_key("findings_unavailable"),
            "code": "findings_unavailable",
            "severity": "error",
            "message": ("This week's checks could not be re-run, so what Opas "
                        "flagged is not shown. The dues below are the stored "
                        "figures and are unaffected."),
            "file_number": None, "employee_id": None, "detail": {},
        }]

    return {
        "week_id": week.id,
        "week_number": week.week_number,
        "week_end_date": week.week_end_date.isoformat(),
        "check_date": week.check_date.isoformat(),
        "status": week.status,
        "approved_at": week.approved_at.isoformat() if week.approved_at else None,
        "dues": {
            "total": dues["total_dues"],
            "members_paying": dues["members_paying"],
            "members_total": dues["members_total"],
        },
        "decisions": [
            {
                "finding_key": k,
                "outcome": d.outcome,
                "note": d.note,
                "decided_at": d.decided_at.isoformat() if d.decided_at else None,
            }
            for k, d in sorted(decisions.items())
        ],
        "corrections": [
            {
                "emp_id": c.emp_id,
                "work_date": c.work_date.isoformat(),
                "pay_type": c.pay_type,
                "hours": str(c.hours),
                "reason": c.reason,
                "entered_at": c.entered_at.isoformat() if c.entered_at else None,
            }
            for c in corrections
        ],
        "findings": findings,
        "decision_outcomes": DECISION_OUTCOMES,
    }


# ─────────────────────────────────────────────────────────────── the two writes


class FocusWriteError(ValueError):
    """A correction or decision the Focus refuses to store."""


def record_correction(db: Session, week: PayrollWeek, *, emp_id: str,
                      work_date: date, pay_type: str, hours: Decimal,
                      reason: str, user_id: str) -> PayrollHourCorrection:
    """Store a hand correction, superseding any live one for the same slot.

    ⚠️ Refuses a work date outside the week. A correction filed against the
    wrong week is invisible on both — it would not show on the week it was
    entered from and would silently alter a week nobody was looking at.
    """
    if not reason or not reason.strip():
        raise FocusWriteError(
            "a correction needs a reason — an unexplained correction is "
            "unreviewable six weeks later, which is when anybody asks"
        )
    span_start = week.week_end_date - _WEEK_SPAN
    if not (span_start <= work_date <= week.week_end_date):
        raise FocusWriteError(
            f"{work_date} is outside the week ending {week.week_end_date} "
            f"({span_start} to {week.week_end_date})"
        )
    # ⚠️ VALIDATED HERE SO THE DATABASE IS A BACKSTOP, NOT THE ERROR SURFACE.
    # The CHECK constraint is the same bound; reaching it produces an
    # IntegrityError and a 500, which tells the person at the screen nothing.
    # This produces a 422 that names the number and the bound.
    if not (-_MAX_CORRECTION_HOURS <= hours <= _MAX_CORRECTION_HOURS):
        raise FocusWriteError(
            f"{hours} hours is outside what a week's correction can describe "
            f"(±{_MAX_CORRECTION_HOURS}). If that is really the figure, it "
            "belongs on more than one week."
        )
    if week.status == "approved":
        raise FocusWriteError(
            f"week ending {week.week_end_date} is approved; correcting it now "
            "would change a week whose checks are already dated. Enter the "
            "adjustment on the next week, as the dues catch-up was."
        )

    row = PayrollHourCorrection(
        tenant_id=week.tenant_id, week_end_date=week.week_end_date,
        emp_id=emp_id, work_date=work_date, pay_type=pay_type,
        hours=hours, reason=reason.strip(), entered_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def record_decision(db: Session, week: PayrollWeek, *, key: str, outcome: str,
                    note: str, user_id: str) -> PayrollWeekDecision:
    """Store a decision about a finding, superseding the live one if any."""
    if outcome not in DECISION_OUTCOMES:
        raise FocusWriteError(
            f"unknown outcome {outcome!r}; one of {sorted(DECISION_OUTCOMES)}. "
            "An unrecognised outcome renders as nothing, so it is refused "
            "rather than stored."
        )
    if not key or not key.strip():
        raise FocusWriteError("a decision needs the finding it is about")

    prior = db.execute(
        select(PayrollWeekDecision)
        .where(PayrollWeekDecision.tenant_id == week.tenant_id)
        .where(PayrollWeekDecision.week_end_date == week.week_end_date)
        .where(PayrollWeekDecision.finding_key == key.strip())
        .where(PayrollWeekDecision.superseded_at.is_(None))
    ).scalars().first()

    # ⚠️ **ORDER: RETIRE THE OLD ROW, INSERT THE NEW, THEN POINT BACK.**
    #
    # My first version inserted first and it failed with a unique violation on
    # `uq_payroll_week_decision_live` — correctly. The index allows one LIVE
    # decision per finding, so the old one must stop being live before the new
    # one exists. `superseded_by` cannot do that job: it is a foreign key to
    # this table and has nothing to point at yet. So `superseded_at` carries
    # liveness and the pointer is filled in last, once there is a real id.
    if prior is not None:
        prior.superseded_at = _now()
        db.flush()

    row = PayrollWeekDecision(
        tenant_id=week.tenant_id, week_end_date=week.week_end_date,
        finding_key=key.strip(), outcome=outcome, note=(note or "").strip(),
        decided_by=user_id,
    )
    db.add(row)
    db.flush()

    if prior is not None:
        prior.superseded_by = row.id
        db.flush()
    return row
