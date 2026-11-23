"""Recording vacations, and the pane that reads them back.

⚠️ **ALLOWANCE, USED, SCHEDULED AND LEFT ARE FOUR DIFFERENT NUMBERS AND THE
PANE SHOWS ALL FOUR.** Collapsing "used" and "scheduled" into one "taken"
figure is the obvious simplification and it is wrong: a vacation on the
calendar for December has not been paid, and somebody deciding whether to
approve another week needs to see both.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollReportEmployee,
    PayrollVacation,
    PayrollVacationPayment,
)
from app.services.payroll.rules import PayrollRules
from app.services.payroll.vacation import entitlement as ent_service
from app.services.payroll.vacation import prior_year as py_service


class VacationError(ValueError):
    """A vacation could not be recorded as asked."""


@dataclass(frozen=True)
class YearView:
    """One person's vacation year, as the pane shows it."""

    year: int
    entitlement: ent_service.Entitlement
    used_hours: Decimal
    scheduled_hours: Decimal
    vacations: list[PayrollVacation]
    payments: list[PayrollVacationPayment]
    prior: py_service.PriorYear

    @property
    def remaining_hours(self) -> Decimal | None:
        """⚠️ `None` WHEN THE ALLOWANCE IS NOT KNOWN — never a bare number.
        "0 left" and "we do not know the allowance" are different facts, and
        the second one is the state every employee is in today."""
        if self.entitlement.hours is None:
            return None
        return self.entitlement.hours - self.used_hours - self.scheduled_hours


def record_vacation(db: Session, *, tenant_id: str,
                    employee: PayrollReportEmployee, start: date, end: date,
                    hours: Decimal, source: str,
                    user_id: str | None) -> PayrollVacation:
    """Put a vacation on the calendar — a union pick, or an approved request."""
    if end < start:
        raise VacationError(
            f"The vacation ends {end}, before it starts {start}.")
    if hours is None or Decimal(str(hours)) <= 0:
        raise VacationError("A vacation needs hours.")
    if not (source or "").strip():
        raise VacationError(
            "A recorded vacation needs a source — a union pick or an approved "
            "request. It is what somebody reads when they ask why this week is "
            "on the calendar."
        )
    # ⚠️ **OVERLAP IS REFUSED, BECAUSE TWO ROWS FOR ONE WEEK PAY IT TWICE.**
    # The bonus is split by the NUMBER of payments in the year, so a duplicate
    # does not merely double one week — it moves every other part's cents.
    clash = (
        db.query(PayrollVacation)
        .filter(PayrollVacation.tenant_id == tenant_id,
                PayrollVacation.employee_id == employee.id,
                PayrollVacation.status != "cancelled",
                PayrollVacation.start_date <= end,
                PayrollVacation.end_date >= start)
        .first()
    )
    if clash is not None:
        raise VacationError(
            f"This overlaps a vacation already recorded for "
            f"{clash.start_date} – {clash.end_date}. Cancel that one first if "
            "it is being replaced."
        )

    row = PayrollVacation(
        tenant_id=tenant_id, employee_id=employee.id, start_date=start,
        end_date=end, hours=Decimal(str(hours)), status="scheduled",
        source=source.strip(), created_by_user_id=user_id)
    db.add(row)
    db.flush()
    return row


def year_view(db: Session, *, tenant_id: str, employee: PayrollReportEmployee,
              year: int, rules: PayrollRules) -> YearView:
    """Everything the vacation pane shows for one person in one year."""
    vacations = (
        db.query(PayrollVacation)
        .filter(PayrollVacation.tenant_id == tenant_id,
                PayrollVacation.employee_id == employee.id,
                PayrollVacation.start_date >= date(year, 1, 1),
                PayrollVacation.start_date <= date(year, 12, 31))
        .order_by(PayrollVacation.start_date)
        .all()
    )
    payments = (
        db.query(PayrollVacationPayment)
        .join(PayrollVacation,
              PayrollVacation.id == PayrollVacationPayment.vacation_id)
        .filter(PayrollVacationPayment.tenant_id == tenant_id,
                PayrollVacation.employee_id == employee.id,
                PayrollVacationPayment.week_end_date >= date(year, 1, 1),
                PayrollVacationPayment.week_end_date <= date(year, 12, 31))
        .order_by(PayrollVacationPayment.week_end_date)
        .all()
    )
    used = sum((Decimal(str(v.hours)) for v in vacations if v.status == "paid"),
               Decimal("0"))
    scheduled = sum(
        (Decimal(str(v.hours)) for v in vacations if v.status == "scheduled"),
        Decimal("0"))

    return YearView(
        year=year,
        entitlement=ent_service.entitlement_for(
            db, tenant_id=tenant_id, employee=employee, year=year, rules=rules),
        used_hours=used,
        scheduled_hours=scheduled,
        vacations=vacations,
        payments=payments,
        prior=py_service.prior_year_for(
            db, tenant_id=tenant_id, employee=employee, year=year - 1),
    )


def payments_in_year(db: Session, *, tenant_id: str, employee_id: str,
                     year: int) -> int:
    """How many vacation payments this person has had in `year`.

    ⚠️ **THIS IS THE BONUS DIVISOR AND IT IS THE YEAR'S COUNT, NOT ONE
    VACATION'S.** §11.11: a yearly total "paid in equal parts, one with each
    vacation payment".
    """
    return int(db.execute(
        select(func.count())
        .select_from(PayrollVacationPayment)
        .join(PayrollVacation,
              PayrollVacation.id == PayrollVacationPayment.vacation_id)
        .where(PayrollVacationPayment.tenant_id == tenant_id)
        .where(PayrollVacation.employee_id == employee_id)
        .where(PayrollVacationPayment.week_end_date >= date(year, 1, 1))
        .where(PayrollVacationPayment.week_end_date <= date(year, 12, 31))
    ).scalar() or 0)
