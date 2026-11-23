"""What a vacation pays, and the working behind it.

Two shapes, and the difference is not a detail:

  UNION       rate = trunc_dp((prior gross / prior hours) + increment)
              Vac      = round2(rate x hours)
              VacBonus = this payment's part of the YEARLY bonus total
  NON-UNION   Vac      = round2(regular rate x hours)
              no bonus

⚠️ **TWO SEPARATELY-ROUNDED LINES, BECAUSE THAT IS WHAT THE REGISTER PAYS**
(spec §3.1). The superseded form folded the bonus inside one `round2(...)`.
That fold cannot change a total — `round2(x + c) == round2(x) + c` for whole
cents — but it makes a payment unreconcilable against the register line by
line, which is the point of splitting it.

⚠️ **THE BONUS IS YEARLY AND ITS PARTS ARE SPREAD ACROSS THE YEAR'S VACATION
PAYMENTS**, not across one vacation's checks. A 160-hour entitlement earns
155.00 and is normally taken as four weeks, so the parts are 38.75 x4. I first
modelled the part count as the 1/2/3 check split the Focus offers and the
`160 h -> 38.75 x4` golden refused it.

⚠️ **THE CENT PLACEMENT IS CUMULATIVE, AND THE EVIDENCE IS ONE CASE DEEP.**
`round2(total*i/n) - round2(total*(i-1)/n)`. 12 of the 13 entitlement groups in
the measured year divide into exactly equal cents and cannot tell cumulative
from largest-remainder apart; exactly one discriminates (§11.11). Worth
carrying forward rather than re-discovering.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.services.payroll.engine import (
    allocate_cumulative,
    round2,
    vacation_bonus_for_year,
    vacation_rate,
)
from app.services.payroll.money import to_decimal
from app.services.payroll.rules import PayrollRules


class VacationPayUnavailable(ValueError):
    """The pay cannot be worked out, and the message says what is missing."""


@dataclass(frozen=True)
class PayPart:
    """One check's worth: a `Vac` line and, for a union member, a `VacBonus`."""

    index: int
    count: int
    hours: Decimal
    vac_pay: Decimal
    vac_bonus: Decimal

    @property
    def total(self) -> Decimal:
        return self.vac_pay + self.vac_bonus


@dataclass(frozen=True)
class VacationPay:
    """The whole working, in the order a person reads it."""

    union: bool
    hours: Decimal
    rate: Decimal | None
    #: Union only — where the rate came from.
    prior_year_gross: Decimal | None
    prior_year_hours: Decimal | None
    rate_truncate_dp: int | None
    #: Union only — the yearly bonus and this vacation's share of it.
    entitlement_hours: Decimal | None
    bonus_year_total: Decimal | None
    parts: tuple[PayPart, ...]

    @property
    def vac_total(self) -> Decimal:
        return sum((p.vac_pay for p in self.parts), Decimal("0.00"))

    @property
    def bonus_total(self) -> Decimal:
        return sum((p.vac_bonus for p in self.parts), Decimal("0.00"))


def union_pay(*, hours: object, prior_year_gross: object,
              prior_year_hours: object, entitlement_hours: object,
              rules: PayrollRules, checks: int = 1,
              bonus_part_start: int = 1,
              bonus_part_count: int = 1) -> VacationPay:
    """A union member's vacation pay.

    `checks` splits THIS vacation's hours across 1, 2 or 3 checks — the Focus's
    first question. `bonus_part_start` / `bonus_part_count` place those checks
    among the YEAR's vacation payments, which is what the bonus is divided by.

    ⚠️ **THE HOURS SPLIT IS EQUAL AND THE REMAINDER GOES TO THE LAST CHECK**,
    so the parts sum to the hours exactly. Splitting the PAY instead would
    round twice and could miss the total by a cent.
    """
    hrs = to_decimal(hours, "hours")
    if hrs <= 0:
        raise VacationPayUnavailable("A vacation with no hours has no pay.")
    if not 1 <= checks <= 3:
        raise VacationPayUnavailable(
            f"A vacation is paid in 1, 2 or 3 checks; got {checks}.")

    gross = to_decimal(prior_year_gross, "prior_year_gross")
    prior_hours = to_decimal(prior_year_hours, "prior_year_hours")
    if prior_hours <= 0:
        raise VacationPayUnavailable(
            "The prior year's hours are not known, so the average hourly rate "
            "cannot be worked out. Enter the prior-year figures with their "
            "source."
        )

    rate = vacation_rate(gross, prior_hours, rules)
    ent = to_decimal(entitlement_hours, "entitlement_hours")
    year_total = vacation_bonus_for_year(ent, rules)
    year_parts = allocate_cumulative(year_total, bonus_part_count)

    per_check = (hrs / checks).quantize(Decimal("0.0001"))
    parts: list[PayPart] = []
    for i in range(checks):
        # ⚠️ The LAST check carries the rounding remainder, so the hours add up.
        this_hours = (hrs - per_check * (checks - 1)) if i == checks - 1 else per_check
        bonus_idx = bonus_part_start - 1 + i
        bonus = (year_parts[bonus_idx]
                 if 0 <= bonus_idx < len(year_parts) else Decimal("0.00"))
        parts.append(PayPart(
            index=bonus_idx + 1, count=bonus_part_count, hours=this_hours,
            vac_pay=round2(rate * this_hours), vac_bonus=bonus))

    return VacationPay(
        union=True, hours=hrs, rate=rate, prior_year_gross=gross,
        prior_year_hours=prior_hours,
        rate_truncate_dp=int(rules.vacation_rate_truncate_dp),
        entitlement_hours=ent, bonus_year_total=year_total,
        parts=tuple(parts))


def non_union_pay(*, hours: object, regular_rate: object,
                  checks: int = 1) -> VacationPay:
    """A non-union employee's vacation pay: regular rate x hours, NO bonus.

    ⚠️ **NO BONUS, AND THAT IS A RULE RATHER THAN AN OVERSIGHT.** The vacation
    bonus comes from the union agreement's day tiers. Paying it to somebody not
    covered by that agreement would be inventing an entitlement.
    """
    hrs = to_decimal(hours, "hours")
    if hrs <= 0:
        raise VacationPayUnavailable("A vacation with no hours has no pay.")
    rate = to_decimal(regular_rate, "regular_rate")
    if rate <= 0:
        raise VacationPayUnavailable(
            "No regular pay rate is on file for this person, so vacation pay "
            "cannot be worked out."
        )
    if not 1 <= checks <= 3:
        raise VacationPayUnavailable(
            f"A vacation is paid in 1, 2 or 3 checks; got {checks}.")

    per_check = (hrs / checks).quantize(Decimal("0.0001"))
    parts = []
    for i in range(checks):
        this_hours = (hrs - per_check * (checks - 1)) if i == checks - 1 else per_check
        parts.append(PayPart(index=i + 1, count=checks, hours=this_hours,
                             vac_pay=round2(rate * this_hours),
                             vac_bonus=Decimal("0.00")))

    return VacationPay(
        union=False, hours=hrs, rate=rate, prior_year_gross=None,
        prior_year_hours=None, rate_truncate_dp=None, entitlement_hours=None,
        bonus_year_total=None, parts=tuple(parts))
