"""Setting an employee's payroll status, as a record rather than an edit.

⚠️ **THE FIELD EXISTED FOR ELEVEN DAYS WITH NO WAY TO SET IT.** `r234` added
`payroll_status` and `payroll_status_since`; measured on production
2026-11-21, **0 of 30** employees carried a value, while two readers depended
on them:

  * the R-115's line 1, which fell back to counting checks and warned that it
    had;
  * `roster_coverage`, whose `if status in EXCUSED_STATUSES: continue` had
    therefore **never once been taken** — so the one member it was built to
    stop flagging was flagged every week.

This module is the entrance that was missing.

### Why a change is a record

A status decides whether somebody is counted on a form filed with a union.
"Who said they left, and when did they say it" has to survive the next edit,
so every change appends a `PayrollEmployeeStatusChange` carrying the state it
replaced, and the two denormalised columns are updated in the same
transaction. Readers keep reading the columns; the history is behind them.

⚠️ **`since` AND `changed_at` ARE DIFFERENT DATES AND ARE ROUTINELY MONTHS
APART.** `since` is the day the status began — the day somebody actually
stopped working. `changed_at` is the day a person typed it in. James is
looking up June leaving dates in November. The R-115's line-1 rule compares
`since` against the month, so conflating the two would quietly put a leaver
back into a month they had already left.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PAYROLL_EMPLOYEE_STATUSES,
    PayrollEmployeeStatusChange,
    PayrollReportEmployee,
)


class EmployeeStatusError(ValueError):
    """The status could not be set as asked."""


@dataclass(frozen=True)
class StatusView:
    """What a pane shows: the current status and how it got there."""

    status: str | None
    since: date | None
    history: list[dict]


def current(employee: PayrollReportEmployee) -> tuple[str | None, date | None]:
    """The status as every existing reader sees it.

    ⚠️ `None` IS NOT `"active"`. NULL means nobody has said; `active` means
    somebody looked and said they are working. The R-115's line-1 fallback
    turns on that difference — a tenant with no statuses recorded counts by
    checks and SAYS SO, where a tenant that has recorded them counts
    membership.
    """
    return employee.payroll_status, employee.payroll_status_since


def set_status(
    db: Session,
    *,
    employee: PayrollReportEmployee,
    status: str,
    since: date,
    reason: str,
    user_id: str | None,
) -> PayrollEmployeeStatusChange:
    """Record a change and move the current value with it."""
    if status not in PAYROLL_EMPLOYEE_STATUSES:
        raise EmployeeStatusError(
            f"{status!r} is not a payroll status; expected one of "
            f"{list(PAYROLL_EMPLOYEE_STATUSES)}"
        )
    if not (reason or "").strip():
        raise EmployeeStatusError(
            "a status change needs a reason — this is the field somebody "
            "reads a year later when the union asks why a member was not on "
            "a form, and 'left' with no reason cannot answer them"
        )
    # ⚠️ A FUTURE `since` IS REFUSED. "Left as of next March" would drop the
    # member from every month until then — including months already filed —
    # because the line-1 rule only asks whether the status began before the
    # month. A future-dated status is a different feature (a scheduled
    # change) and is not this one.
    today = datetime.now(timezone.utc).date()
    if since > today:
        raise EmployeeStatusError(
            f"{since} is in the future. A status takes effect from the day it "
            "began, and a future date would remove this member from months "
            "that have already been filed. Record it on the day it happens."
        )

    prev_status, prev_since = current(employee)
    if prev_status == status and prev_since == since:
        raise EmployeeStatusError(
            f"this employee is already {status!r} since {since}. Nothing was "
            "recorded — a no-op change in the history is noise in the one "
            "place that has to stay readable."
        )

    change = PayrollEmployeeStatusChange(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        status=status,
        since=since,
        previous_status=prev_status,
        previous_since=prev_since,
        reason=reason.strip(),
        changed_by_user_id=user_id,
    )
    db.add(change)
    # The denormalised current value, moved in the SAME transaction. If this
    # and the history row could diverge, every reader would be reading a
    # value the history does not explain.
    employee.payroll_status = status
    employee.payroll_status_since = since
    db.flush()
    return change


def history(db: Session, *, employee_id: str) -> list[PayrollEmployeeStatusChange]:
    """Every recorded change for one employee, newest first."""
    return (
        db.query(PayrollEmployeeStatusChange)
        .filter(PayrollEmployeeStatusChange.employee_id == employee_id)
        .order_by(PayrollEmployeeStatusChange.changed_at.desc())
        .all()
    )


def shape_change(change: PayrollEmployeeStatusChange,
                 *, by_name: str | None = None) -> dict:
    """One history row, as a pane needs it."""
    return {
        "id": change.id,
        "status": change.status,
        "since": change.since.isoformat() if change.since else None,
        "previous_status": change.previous_status,
        "previous_since": (change.previous_since.isoformat()
                           if change.previous_since else None),
        "reason": change.reason,
        "changed_at": change.changed_at.isoformat() if change.changed_at else None,
        "changed_by_user_id": change.changed_by_user_id,
        "changed_by_name": by_name,
    }
