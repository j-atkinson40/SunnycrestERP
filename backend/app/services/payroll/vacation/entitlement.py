"""How many vacation hours somebody is allowed this year.

Two sources, in order:

  1. a per-person OVERRIDE with a source — "because some people's allowance is
     set by agreement" (James, 2026-11-23);
  2. the effective-dated years-of-service TIERS in the rulebook.

⚠️ **AND A THIRD STATE THAT IS NOT A NUMBER: NOT ESTABLISHED.** Years of
service come from `hire_date`, which is NULL for every payroll employee today
— the column was added by `r239` and nobody has measured a hire date for
anyone. A missing hire date is reported, naming the person; it is never read as
"hired today", which would hand a twenty-year employee the first tier.

⚠️ **THE TIERS ARE PLACEHOLDERS AND SAY SO.** Status `assumed` — "the example
tiers until I supply Sunnycrest's real list." A rule set created before 5c has
NULL tiers, which is a different thing again from zero hours: nobody chose,
so nothing is derivable from service for that rule set.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollReportEmployee,
    PayrollVacationEntitlement,
)
from app.services.payroll.rules import PayrollRules

BY_OVERRIDE = "override"
BY_TIERS = "service_tiers"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Entitlement:
    """The allowance, and why it is that number."""

    year: int
    hours: Decimal | None
    basis: str
    source: str | None
    years_of_service: int | None
    #: Said on screen when `hours` is None, naming what is missing.
    why_not: str | None = None

    @property
    def known(self) -> bool:
        return self.hours is not None


def completed_years(hire_date: date, *, on: date) -> int:
    """Completed years of service on a date.

    ⚠️ **COMPLETED, NOT ELAPSED-AND-ROUNDED.** Somebody hired on 1 March has
    not completed a year on the following 28 February, and a tier boundary is
    exactly where that distinction pays somebody differently.
    """
    years = on.year - hire_date.year
    if (on.month, on.day) < (hire_date.month, hire_date.day):
        years -= 1
    return max(0, years)


def hours_for_service(years: int, rules: PayrollRules) -> Decimal | None:
    """Tier lookup: the first tier whose `through_years` covers `years`.

    Service beyond the last tier earns the LAST tier's hours — the tiers run
    out rather than dropping to nothing, which is the opposite of the bonus
    day-tiers and is why the two are separate rules.
    """
    tiers = rules.vacation_entitlement_tiers
    if not tiers:
        return None
    for tier in tiers:
        if years <= int(tier["through_years"]):
            return Decimal(str(tier["hours"]))
    return Decimal(str(tiers[-1]["hours"]))


def override_for(db: Session, *, tenant_id: str, employee_id: str,
                 year: int) -> PayrollVacationEntitlement | None:
    return (
        db.query(PayrollVacationEntitlement)
        .filter(PayrollVacationEntitlement.tenant_id == tenant_id,
                PayrollVacationEntitlement.employee_id == employee_id,
                PayrollVacationEntitlement.year == year)
        .first()
    )


def entitlement_for(db: Session, *, tenant_id: str,
                    employee: PayrollReportEmployee, year: int,
                    rules: PayrollRules, on: date | None = None) -> Entitlement:
    """The allowance for `year`, by override if there is one, else by service."""
    at = on or date(year, 1, 1)

    override = override_for(db, tenant_id=tenant_id, employee_id=employee.id,
                            year=year)
    years = (completed_years(employee.hire_date, on=at)
             if employee.hire_date else None)

    if override is not None:
        # ⚠️ The override WINS and still reports years of service, because a
        # reader comparing the two is exactly who the source note is for.
        return Entitlement(year, Decimal(str(override.hours)), BY_OVERRIDE,
                           override.source, years)

    if employee.hire_date is None:
        return Entitlement(
            year, None, UNAVAILABLE, None, None,
            why_not=(
                f"{employee.display_name or employee.payentry_file_number} has "
                "no hire date, so years of service cannot be worked out. Enter "
                "a hire date, or set this year's allowance directly with its "
                "source."
            ),
        )

    hours = hours_for_service(years or 0, rules)
    if hours is None:
        return Entitlement(
            year, None, UNAVAILABLE, None, years,
            why_not=(
                "The rule set in force has no vacation entitlement tiers, so an "
                "allowance cannot be worked out from service. Set this year's "
                "allowance directly with its source."
            ),
        )
    return Entitlement(year, hours, BY_TIERS, None, years)
