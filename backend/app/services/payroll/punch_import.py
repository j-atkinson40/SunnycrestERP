"""Storing Punch Location clock events — the writer `PayrollPunch` never had.

⚠️ **THE TABLE SHIPPED WITH NO WRITER.** `PayrollPunch` and
`parse_punch_location` were both built in Payroll 3; measured 2026-11-23, the
parser was called only by tests and the table had **no write site anywhere in
`app/` or `scripts/`**. So `punch_data_present` in the timecard pane was
permanently false, and the three weekly questions that need clock times —
early release, early clock-in, missed punches — could not run at all.

⚠️ **AN UNRESOLVED PUNCH IS STORED WITH A NULL `emp_id`, NOT DROPPED.** The
model's own comment says so: "an unresolved punch is a finding, not a guess".
Dropping it would make the finding disappear along with the evidence for it,
and the next upload would re-raise it from nothing. Stored, it can be attached
the moment somebody confirms the name.

⚠️ **AND THE WHOLE FILE IS NOT REFUSED FOR AN UNRESOLVED NAME.** That is the
opposite choice from `import_hours`, which refuses a file whose employee ids
are unknown — and the difference is real: an unknown id in the HOURS file
means somebody's pay is filed against a person who does not exist, where an
unmatched punch name means one person's clock times are unattached and
everybody else's are fine. Refusing the file would throw away twenty-nine good
people's punches over one spelling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollCheck,
    PayrollNameAlias,
    PayrollPunch,
)
from app.services.payroll.punch_names import NameFinding, normalise, resolve
from app.services.payroll.punch_parser import (
    PunchParseError,
    parse_punch_location,
)


@dataclass
class PunchImportResult:
    stored: int = 0
    unattached: int = 0
    people_matched: int = 0
    findings: list[NameFinding] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            # ⚠️ **`punches_stored`, NOT `stored`.** The endpoint's reply also
            # carries a BOOLEAN `stored` meaning "was the punch file stored at
            # all", which the upload card reads — and spreading this dict over
            # it silently replaced the boolean with the count. One name for two
            # meanings, decided by which spread won.
            "punches_stored": self.stored,
            "unattached": self.unattached,
            "people_matched": self.people_matched,
            "findings": [
                {"kind": f.kind, "raw_name": f.raw_name,
                 "candidates": list(f.candidates), "detail": f.detail}
                for f in self.findings
            ],
        }


def aliases_for(db: Session, tenant_id: str) -> dict[str, str]:
    """Confirmed name → employee number, normalised.

    ⚠️ Re-normalised on read rather than trusted as stored, so a change to the
    normaliser cannot silently orphan every alias somebody confirmed.
    """
    rows = (db.query(PayrollNameAlias)
            .filter(PayrollNameAlias.tenant_id == tenant_id).all())
    return {normalise(r.raw_name or r.normalised_name): r.emp_id for r in rows}


def register_names(db: Session, tenant_id: str) -> dict[str, set[str]]:
    """Every name the register has spelled for each employee number."""
    out: dict[str, set[str]] = {}
    for emp_id, person in db.query(PayrollCheck.emp_id, PayrollCheck.person) \
            .filter(PayrollCheck.tenant_id == tenant_id).distinct().all():
        if emp_id and person:
            out.setdefault(emp_id, set()).add(person)
    return out


def import_punches(
    db: Session, *, tenant_id: str, content: bytes, import_id: str,
    week_end_date: date, hours_names_by_emp: dict[str, set[str]],
) -> PunchImportResult:
    """Parse, resolve names, and store every clock event for the week.

    `hours_names_by_emp` comes from THIS week's Employee Hours parse, which is
    the first source the ruling names and the better one: a register spanning
    a year may hold somebody who left in March.
    """
    parsed = parse_punch_location(content)

    names = {p.name for p in parsed.punches if p.name}
    res = resolve(
        names,
        hours_names_by_emp=hours_names_by_emp,
        register_names_by_emp=register_names(db, tenant_id),
        aliases=aliases_for(db, tenant_id),
    )

    # ⚠️ REPLACE THIS WEEK'S PUNCHES FOR THIS IMPORT RATHER THAN APPEND. A
    # second upload of the same week is a correction, not twice the clock
    # events — and doubled punches would make every missed-punch finding
    # disappear, because every in would have an out.
    db.query(PayrollPunch).filter(
        PayrollPunch.tenant_id == tenant_id,
        PayrollPunch.week_end_date == week_end_date,
    ).delete(synchronize_session=False)

    result = PunchImportResult(findings=list(res.findings))
    for p in parsed.punches:
        emp_id = res.by_raw_name.get(p.name)
        db.add(PayrollPunch(
            tenant_id=tenant_id, import_id=import_id,
            week_end_date=week_end_date, emp_id=emp_id,
            person_name=p.name, dept=p.dept, punch_at=p.punch_at,
            has_location=bool(p.has_location), origin=p.origin))
        result.stored += 1
        if emp_id is None:
            result.unattached += 1
    result.people_matched = len(set(res.by_raw_name.values()))
    db.flush()
    return result


__all__ = ["PunchImportResult", "PunchParseError", "import_punches"]


def stored_days(db: Session, *, tenant_id: str, week_end_date: date):
    """Stored punches, paired into days through the ONE pairing implementation.

    ⚠️ **IT REBUILDS A `PunchParseResult` RATHER THAN RE-PAIRING.** Writing a
    second pairing loop over DB rows would be a second answer to "which in
    goes with which out", and the two would disagree the first time either
    changed — on a question whose wrong answer is somebody's paid hours.
    `pair_punches` already refuses to invent a missing half; this hands it the
    same shape it reads from a file.

    ⚠️ **ONLY ATTACHED PUNCHES.** A punch whose name nobody has confirmed has
    no `emp_id`, and attributing its hours to a person would be the silent
    fuzzy match the ruling forbids. It is stored, it is a finding, and it is
    not paired into anybody's day.
    """
    from app.services.payroll.punch_parser import (
        Punch,
        PunchParseResult,
        pair_punches,
    )

    rows = (
        db.query(PayrollPunch)
        .filter(PayrollPunch.tenant_id == tenant_id,
                PayrollPunch.week_end_date == week_end_date,
                PayrollPunch.emp_id.isnot(None))
        .order_by(PayrollPunch.punch_at)
        .all()
    )
    punches = [
        Punch(name=r.person_name, dept=r.dept, punch_at=r.punch_at,
              has_location=bool(r.has_location), origin=r.origin)
        for r in rows
    ]
    return pair_punches(PunchParseResult(
        punches=punches, blocks=0, departments={r.dept for r in rows if r.dept}))


def punch_data_present(db: Session, *, tenant_id: str,
                       week_end_date: date) -> bool:
    """⚠️ ANY stored punch, attached or not — the timecard pane's sentence is
    about whether a file was loaded, not about whether it resolved."""
    return db.query(PayrollPunch).filter(
        PayrollPunch.tenant_id == tenant_id,
        PayrollPunch.week_end_date == week_end_date).first() is not None
