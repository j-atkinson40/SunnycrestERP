"""Prior-year gross and hours — computed from registers, or entered with a source.

⚠️ **COVERAGE DECIDES WHETHER THE COMPUTED FIGURE MAY BE USED, AND THAT IS THE
WHOLE DESIGN.** James, 2026-11-23:

> If the registers cover the whole prior year, compute it. If not, show the
> coverage ("registers cover Nov 13 – Dec 31 2025 only") and take an entered
> figure with a required source note.

The alternative — summing whatever checks happen to be imported and calling it
the prior year — produces a figure that is *plausible, wrong, and silent*. A
person with seven weeks of imported register would get a vacation rate built
from seven weeks of earnings, and nothing on the screen would say so. That is
the `is_manufactured` shape from CLAUDE.md §5: a defensible-looking value
nobody measured.

⚠️ **THE DEFINITION ITSELF IS `assumed`, NOT CONFIRMED.** Gross is the printed
total earnings on every check dated in the year — all earnings codes, VacBonus
included, off-cycle checks included — and hours is the printed total hours.
James gave it with the status and the source: "registers, definition
unconfirmed against the workbook". It has never been compared against the
accountant's Vac Calc tab, because 2025's registers cover seven weeks. **The
comparison becomes possible for 2027 vacations**, once the 2026 weekly uploads
run through December; that is recorded as an open check in STATE.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollCheck,
    PayrollPriorYearFigures,
    PayrollReportEmployee,
)

#: How much of a year the registers must cover before a computed figure is
#: offered as usable.
#:
#: ⚠️ **THE WHOLE YEAR, AND THE BAR IS DELIBERATELY NOT A PERCENTAGE.** "95% of
#: the year" sounds more forgiving and is worse: the missing 5% is a fortnight
#: of earnings missing from a divisor, which moves a rate without moving
#: anything a reader would notice. Either the year is covered or the figure is
#: entered by somebody who knows what is missing.
FULL_YEAR = "full_year"
PARTIAL = "partial"
NONE = "none"


@dataclass(frozen=True)
class Coverage:
    """What the imported registers actually span for one year."""

    year: int
    first_check: date | None
    last_check: date | None
    check_count: int
    kind: str

    @property
    def covers_year(self) -> bool:
        return self.kind == FULL_YEAR

    def sentence(self) -> str:
        """Said on screen, naming the dates rather than a verdict."""
        if self.kind == NONE:
            return f"No registers are imported for {self.year}."
        span = f"{self.first_check} – {self.last_check}"
        if self.kind == FULL_YEAR:
            return f"Registers cover {self.year} ({span})."
        return (
            f"Registers cover {span} only, not the whole of {self.year}. "
            "A prior-year figure must be entered, with its source."
        )


@dataclass(frozen=True)
class PriorYear:
    """The figures to use, and where they came from."""

    year: int
    gross: Decimal | None
    hours: Decimal | None
    #: "registers" | "entered" | "unavailable"
    basis: str
    #: For an entered figure, what the person typed as its origin.
    source: str | None
    coverage: Coverage
    #: Present when the registers were summed as well — so a screen can show
    #: the entered figure BESIDE what the partial registers say, which is the
    #: only way the definition question ever gets looked at.
    register_gross: Decimal | None = None
    register_hours: Decimal | None = None

    @property
    def usable(self) -> bool:
        return self.gross is not None and self.hours is not None and self.hours > 0


def coverage_for(db: Session, *, tenant_id: str, year: int) -> Coverage:
    """What the imported registers span for `year`.

    ⚠️ Measured from the CHECKS, not from the register-import rows: an import
    may be recorded whose checks were all for another year.
    """
    row = db.execute(
        select(func.min(PayrollCheck.check_date),
               func.max(PayrollCheck.check_date),
               func.count())
        .where(PayrollCheck.tenant_id == tenant_id)
        .where(PayrollCheck.check_date >= date(year, 1, 1))
        .where(PayrollCheck.check_date <= date(year, 12, 31))
    ).one()
    first, last, count = row[0], row[1], int(row[2] or 0)
    if count == 0:
        return Coverage(year, None, None, 0, NONE)

    # ⚠️ **A WEEK OF SLACK AT EACH END, AND HERE IS WHY IT IS NOT CHEATING.**
    # Payroll weeks do not align to January 1st: the first check of a year is
    # dated several days in, and the last may fall in the first days of the
    # next. Demanding a check ON the 1st would call every complete year partial.
    # Seven days is one pay cycle — the gap a full year can legitimately leave
    # — and anything wider is a real hole.
    covers = (first - date(year, 1, 1)).days <= 7 and \
             (date(year, 12, 31) - last).days <= 7
    return Coverage(year, first, last, count, FULL_YEAR if covers else PARTIAL)


def register_totals(db: Session, *, tenant_id: str, emp_id: str,
                    year: int) -> tuple[Decimal, Decimal]:
    """Gross and hours summed off the checks dated in `year`.

    ⚠️ **EVERY CHECK, EVERY EARNINGS CODE.** The definition James gave is the
    PRINTED totals — which already include VacBonus and off-cycle checks —
    rather than a sum of selected line codes. Selecting codes would be a second
    definition of "gross" living beside the register's own.
    """
    row = db.execute(
        select(func.coalesce(func.sum(PayrollCheck.printed_total_earnings), 0),
               func.coalesce(func.sum(PayrollCheck.printed_total_hours), 0))
        .where(PayrollCheck.tenant_id == tenant_id)
        .where(PayrollCheck.emp_id == emp_id)
        .where(PayrollCheck.check_date >= date(year, 1, 1))
        .where(PayrollCheck.check_date <= date(year, 12, 31))
    ).one()
    return Decimal(str(row[0] or 0)), Decimal(str(row[1] or 0))


def entered_figures(db: Session, *, tenant_id: str, employee_id: str,
                    year: int) -> PayrollPriorYearFigures | None:
    return (
        db.query(PayrollPriorYearFigures)
        .filter(PayrollPriorYearFigures.tenant_id == tenant_id,
                PayrollPriorYearFigures.employee_id == employee_id,
                PayrollPriorYearFigures.year == year)
        .first()
    )


def prior_year_for(db: Session, *, tenant_id: str,
                   employee: PayrollReportEmployee, year: int) -> PriorYear:
    """The figures to use for a vacation in `year + 1`, and their basis.

    ⚠️ **AN ENTERED FIGURE WINS OVER A COMPUTED ONE, ALWAYS.** Somebody typed
    it knowing what the registers were missing; the computation does not know
    that. The register totals are still returned alongside so the two can be
    looked at together — which is how the definition question eventually gets
    answered rather than deferred forever.
    """
    cov = coverage_for(db, tenant_id=tenant_id, year=year)
    reg_gross, reg_hours = (
        register_totals(db, tenant_id=tenant_id,
                        emp_id=employee.payentry_file_number, year=year)
        if cov.kind != NONE else (None, None)
    )

    entered = entered_figures(db, tenant_id=tenant_id,
                              employee_id=employee.id, year=year)
    if entered is not None:
        return PriorYear(year, Decimal(str(entered.gross)),
                         Decimal(str(entered.hours)), "entered", entered.source,
                         cov, reg_gross, reg_hours)

    if cov.covers_year and reg_hours and reg_hours > 0:
        return PriorYear(year, reg_gross, reg_hours, "registers", None, cov,
                         reg_gross, reg_hours)

    # ⚠️ **"UNAVAILABLE" IS A STATE, NOT AN ERROR AND NOT A ZERO.** The screen
    # shows the coverage sentence and asks for a figure. Returning 0/0 here
    # would divide by zero one layer down; returning the partial sum would be
    # the silent wrong answer this module exists to prevent.
    return PriorYear(year, None, None, "unavailable", None, cov,
                     reg_gross, reg_hours)
