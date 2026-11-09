"""Dues computed from the pay lines a check actually carries.

Payroll 4, Phase 2. The existing path (`engine.compute_dues`) derives a dues
wage from hours times a typed rate in the weekly HOURS export — what we are
about to pay. This path reads the REGISTER: the amounts Payentry actually paid.
Same formula, different way of arriving at its two inputs; `engine.
dues_from_wage_and_hours` is the single copy of the formula, so the two cannot
drift apart by a cent.

⚠️ **THE CODE MAP BELOW WAS MEASURED, NOT ASSUMED.** It was found by scoring
candidate maps against the 629 `Union` deduction lines in a full year of real
registers — the deduction Payentry actually took is the answer key. The map
that matches is:

    dues wage    Reg  OT  PTO  Ber  Vac  VacBonus  Hol
    dues hours   Reg  OT  PTO  Ber  Vac            Hol
    neither      Sal  Sick  Comm  Bonus  HealthInsS  Winter

Each exclusion is a measurement, not a preference. Adding `Comm`, `Bonus`,
`HealthInsS` and `Winter` LOWERS the match count from 553 to 552 — so they are
out because the register says so. `VacBonus` is in the wage and not in the
hours because it is a flat amount with no hours on the line (29 lines, all
hourless). Including `Vac` alone changes nothing (535); `Vac` and `VacBonus`
together take it from 535 to 552, and `Hol` to 553.

⚠️ **`Sal` AND `Sick` ARE RULINGS, AND THEY AGREE WITH THE MEASUREMENT.**
`Sal` is salaried pay and union members are hourly (James, 2026-11-09); `Sick`
is out of both dues wage and dues hours (the accountant, 2026-11-03). Measured
on the year, NO missing check carries a `Sick` line at all, so including sick
hours could not turn a single miss into a match — the flag is not what the
remaining misses are about.

⚠️ **THE INITIATION FEE IS NOT INFERRED HERE.** Six checks in the year show an
actual dues figure exactly 10.00 above the computed one, which is the fee. Only
2 of those 6 are that member's first `Union` check in the register's window, so
"first check seen" is a wrong rule that would charge the fee to four
established members and miss it for others whose membership began before the
window. Whether a member has paid an initiation fee is a fact about that
member, and it belongs in the people facts of Phase 4 — not in a heuristic
over whatever range of registers happens to have been uploaded.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.services.payroll.engine import DuesResult, dues_from_wage_and_hours
from app.services.payroll.register_parser import DUES_DEDUCTION_CODE
from app.services.payroll.rules import PayrollRules

ZERO = Decimal("0")

#: Earning codes that contribute their AMOUNT to the dues wage.
DUES_WAGE_CODES = frozenset({"Reg", "OT", "PTO", "Ber", "Vac", "VacBonus", "Hol"})

#: Earning codes that contribute their HOURS to the dues hours. `VacBonus` is
#: deliberately absent: it is a flat amount and its lines carry no hours.
DUES_HOURS_CODES = frozenset({"Reg", "OT", "PTO", "Ber", "Vac", "Hol"})

#: Named so the exclusions are readable as a set rather than inferred from two
#: inclusions. Asserted against the parser's full code list, so a new earning
#: code cannot land in neither list unnoticed.
DUES_EXCLUDED_CODES = frozenset({"Sal", "Sick", "Comm", "Bonus", "HealthInsS", "Winter"})


@dataclass
class CheckDues:
    """What one check's own lines say its dues should be, and what they were."""

    emp_id: str
    check_number: str
    check_date: object
    dues_wage: Decimal
    dues_hours: Decimal
    computed: DuesResult
    #: The `Union` deduction the register actually carries. The answer key.
    actual: Decimal

    @property
    def difference(self) -> Decimal:
        return self.computed.dues - self.actual

    @property
    def matches(self) -> bool:
        return self.computed.dues == self.actual


def dues_wage_and_hours(check) -> tuple[Decimal, Decimal]:
    """The two dues inputs, from a check's earning lines.

    Takes anything with a `.lines` sequence of objects carrying `kind`, `code`,
    `hours` and `amount` — a parsed `RegisterCheck` or a stored
    `PayrollCheck`, so the same reading serves the import and the reports.
    """
    wage = sum(
        (l.amount for l in check.lines
         if l.kind == "earning" and l.code in DUES_WAGE_CODES),
        ZERO,
    )
    hours = sum(
        ((l.hours or ZERO) for l in check.lines
         if l.kind == "earning" and l.code in DUES_HOURS_CODES),
        ZERO,
    )
    return wage, hours


def actual_dues(check) -> Decimal:
    """The `Union` deduction on the check. Negative lines would subtract."""
    return sum(
        (l.amount for l in check.lines
         if l.kind == "deduction" and l.code == DUES_DEDUCTION_CODE),
        ZERO,
    )


def dues_for_check(check, rules: PayrollRules, *,
                   apply_initiation_fee: bool = False) -> CheckDues:
    """Dues for one check, beside the dues it was actually charged.

    `apply_initiation_fee` is the caller's decision — see the module docstring
    for why it cannot be inferred from a register.
    """
    wage, hours = dues_wage_and_hours(check)
    return CheckDues(
        emp_id=check.emp_id,
        check_number=check.check_number or "",
        check_date=check.check_date,
        dues_wage=wage,
        dues_hours=hours,
        computed=dues_from_wage_and_hours(
            wage, hours, rules, apply_initiation_fee=apply_initiation_fee),
        actual=actual_dues(check),
    )


def classify_difference(row: CheckDues) -> str:
    """Why a computed figure disagrees with the charged one.

    ⚠️ **A CLASSIFICATION, NOT AN EXCUSE.** Every bucket here is a disagreement
    that a person still has to settle; naming the shape is how the 76 become
    reviewable instead of a single unhelpful count. Measured over the year:

        34  off by up to 1.00
        22  off by 1.00 to 5.00
        10  within 2 cents
         6  actual exactly 10.00 higher — an initiation fee
         2  no dues-bearing earnings on the check at all
         2  off by more than 5.00

    The two largest buckets are small, signed both ways and spread across 17 of
    the 18 members, which is the shape of dues computed from a DIFFERENT week's
    figures — the accountant works from the hours export and types the result
    into Payentry, so a timing offset would look exactly like this. Stated as
    the leading hypothesis and nothing more: it has not been tested against an
    hours export for the same weeks.
    """
    diff = row.difference
    if row.actual - row.computed.dues == Decimal("10.00"):
        return "initiation_fee"
    if abs(diff) <= Decimal("0.02"):
        return "rounding"
    if row.actual == 0:
        return "charged_nothing"
    if row.computed.dues == 0:
        return "no_dues_bearing_earnings"
    if abs(diff) <= Decimal("1.00"):
        return "off_by_under_1"
    if abs(diff) <= Decimal("5.00"):
        return "off_by_1_to_5"
    return "off_by_over_5"
