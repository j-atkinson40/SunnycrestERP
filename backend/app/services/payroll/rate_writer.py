"""Writing effective-dated pay rates from the register.

⚠️ **`PayrollRate` HAD NO WRITER IN `app/` AND THIS IS IT.** Measured in the
week-44 dress rehearsal, 2026-11-23: the table was written only by two seed
scripts, and `register_rates.rates_for_week` — which derives rates from the
register — was called only by tests. Uploading the real register inserted
**1,275 checks and zero rates**, so on a tenant whose rates were never seeded
every employee came back `missing_rate` and every dues figure was $0.00.

**The ruling** (James, Payroll 3; restated 2026-11-23): *a rate is read from
the register check that first prints it, and is effective from the start of
the pay period that check pays.* `week_end = check_date - 5`;
`effective_from = week_end - 6`. One resolver, by week end.

⚠️ **A CHANGED RATE STARTS A NEW EFFECTIVE ROW AND NEVER OVERWRITES ONE.**
Overwriting would silently restate what somebody was paid last March — and
`resolve_rate` reads "the most recent row on or before this week", so history
is the mechanism, not a nicety. Two rates for one effective date is the only
case that updates in place, and it is a correction to a row that was wrong.

⚠️ **EVERY IMPORT DERIVES FROM ALL THE TENANT'S CHECKS, NOT ONLY THE ONES
JUST INSERTED.** That is what makes a re-upload a backfill: James re-uploads
the register, every check is a duplicate, nothing is inserted — and the rates
still get written. A writer that only looked at new rows would do nothing on
exactly the upload that is meant to fix the gap.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollCheck,
    PayrollRate,
    PayrollReportEmployee,
)
from app.services.payroll.register_rates import rate_history


@dataclass
class RateWriteResult:
    written: int = 0
    corrected: int = 0
    unchanged: int = 0
    #: Employee numbers with a printed rate but no roster row — they cannot be
    #: stored, because `payroll_rates` hangs off the employee.
    no_roster_row: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "written": self.written,
            "corrected": self.corrected,
            "unchanged": self.unchanged,
            "no_roster_row": sorted(self.no_roster_row,
                                    key=lambda e: (len(e), e)),
        }


def write_rates(db: Session, *, tenant_id: str) -> RateWriteResult:
    """Derive effective-dated rates from every stored check and upsert them."""
    checks = db.execute(
        select(PayrollCheck).where(PayrollCheck.tenant_id == tenant_id)
    ).scalars().all()
    history = rate_history(checks)

    employees = {
        e.payentry_file_number: e
        for e in db.execute(
            select(PayrollReportEmployee)
            .where(PayrollReportEmployee.tenant_id == tenant_id)
        ).scalars().all()
        if e.payentry_file_number
    }

    out = RateWriteResult()
    for emp_id, entries in sorted(history.items()):
        employee = employees.get(emp_id)
        if employee is None:
            # ⚠️ REPORTED, NOT SKIPPED IN SILENCE. A rate for somebody absent
            # from the roster means the roster is incomplete, which is a thing
            # to look at rather than a row to drop.
            out.no_roster_row.append(emp_id)
            continue

        existing = {
            r.effective_date: r
            for r in db.execute(
                select(PayrollRate)
                .where(PayrollRate.employee_id == employee.id)
            ).scalars().all()
        }
        # ⚠️ **ONLY WHERE THE RATE CHANGES.** The register prints the same rate
        # on every check, so storing one row per check would be fifty rows a
        # year per person saying the same thing — and `resolve_rate` would
        # still answer identically. A row marks a CHANGE.
        previous: Decimal | None = None
        for entry in entries:
            if previous is not None and entry.reg_rate == previous:
                continue
            previous = entry.reg_rate

            row = existing.get(entry.effective_date)
            if row is None:
                db.add(PayrollRate(
                    id=str(uuid.uuid4()), employee_id=employee.id,
                    reg_rate=entry.reg_rate,
                    effective_date=entry.effective_date))
                out.written += 1
            elif row.reg_rate != entry.reg_rate:
                # Same effective date, different rate: the stored row was
                # wrong. A correction in place, not a second row — two rows
                # for one date would make "which rate" unanswerable.
                row.reg_rate = entry.reg_rate
                out.corrected += 1
            else:
                out.unchanged += 1
    db.flush()
    return out
