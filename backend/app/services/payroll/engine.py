"""Pure payroll dues / vacation / stonebucks arithmetic.

⚠️ NO DATABASE. No session, no ORM import, no query. The engine takes line
values, a rule set and resolved rates, and returns results. Persistence is the
caller's job (`app.services.payroll.service`).

That boundary is what makes the golden tests hand-provable: they assert literal
figures derived from the spec against a function that cannot reach a database,
so a passing test cannot be an artefact of fixture state (CLAUDE.md §11 "a test
can pass because data is MISSING").

Rounding: intermediates are NOT rounded. `dues_wage` carries full precision into
`a` and `b`; only `a`, `b` and `c` round, and they round before `min()` and
before the sum. Rounding earlier changes answers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from app.services.payroll.money import round2, to_decimal
from app.services.payroll.rules import VACATION_HOURS_PER_DAY, PayrollRules

ZERO = Decimal("0")


@dataclass(frozen=True)
class LineInputs:
    """One employee's hours and amounts for one week.

    Mirrors `payroll_week_line`. Every field is coerced through `to_decimal`, so
    a float anywhere in an import row fails loudly here rather than quietly
    later.

    ⚠️ `winter_hrs` AND `weeks_pay` ARE CARRIED BUT ARE NOT INPUTS TO DUES.
    Neither appears in the `dues_wage` or `dues_hours` formula. They are stored
    on the line and available to reports. This is the workbook's behaviour as
    specified, and it is an OPEN QUESTION whether `winter_hrs` ought to be in
    `dues_hours` alongside the other hour columns — see
    docs/specs/payroll-reports.md §7.5. It is pinned by a characterization test
    (`test_payroll_engine_rule_edges.py::test_winter_hours_and_weeks_pay_do_not_move_dues`)
    so that if the ruling changes the test fails and says so, rather than the
    behaviour drifting silently.
    """

    reg_hrs: Decimal = ZERO
    ny_covid_hrs: Decimal = ZERO
    ot_hrs: Decimal = ZERO
    ot2_hrs: Decimal = ZERO
    personal_hrs: Decimal = ZERO
    sick_hrs: Decimal = ZERO
    bereavement_hrs: Decimal = ZERO
    winter_hrs: Decimal = ZERO          # carried, not a dues input — see docstring
    vac_hrs: Decimal = ZERO
    stonebucks_amt: Decimal = ZERO
    misc_amt: Decimal = ZERO
    vac_amt: Decimal = ZERO
    weeks_pay: Decimal = ZERO           # carried, not a dues input — see docstring

    def __post_init__(self) -> None:
        for f in self.__dataclass_fields__:
            object.__setattr__(self, f, to_decimal(getattr(self, f), f))


@dataclass(frozen=True)
class DuesResult:
    dues_wage: Decimal
    dues_hours: Decimal
    component_a: Decimal | None     # round2(wage * dues_pct)
    component_b: Decimal | None     # round2((wage / hours) * cap_multiplier)
    component_c: Decimal | None     # round2(hours * dues_per_hour)
    capped: Decimal | None          # min(a, b)
    initiation_fee: Decimal
    dues: Decimal
    ot_rate_used: Decimal
    ot_rate_derived: bool           # True when ot_rate was NULL and 1.5x applied

    @property
    def binds(self) -> str:
        """Which component the cap resolved to — for the detail report."""
        if self.component_a is None:
            return "zero"
        if self.component_b < self.component_a:
            return "b"
        if self.component_a < self.component_b:
            return "a"
        return "tie"


def resolve_ot_rate(reg_rate: object, ot_rate: object | None) -> tuple[Decimal, bool]:
    """NULL ot_rate means reg_rate * 1.5, derived at calculation time.

    Returns (rate, was_derived). The flag is carried into the result so a report
    can say which rate it used — the workbook's typed-in OT rates are frequently
    NOT 1.5x (9 of 13 week-44 members), so "derived" is the exception, not the
    norm, and conflating them would hide a data-entry error.
    """
    reg = to_decimal(reg_rate, "reg_rate")
    if ot_rate is None:
        return reg * Decimal("1.5"), True
    return to_decimal(ot_rate, "ot_rate"), False


def compute_dues_wage(line: LineInputs, reg_rate: Decimal, ot_rate: Decimal,
                      rules: PayrollRules) -> Decimal:
    """Sick pay excluded by default — see rules.sick_in_dues_wage."""
    straight = line.reg_hrs + line.personal_hrs + line.ny_covid_hrs + line.bereavement_hrs
    if rules.sick_in_dues_wage:
        straight += line.sick_hrs
    overtime = line.ot_hrs + line.ot2_hrs
    return (
        straight * reg_rate
        + overtime * ot_rate
        + line.stonebucks_amt
        + line.misc_amt
        + line.vac_amt
    )


def compute_dues_hours(line: LineInputs, rules: PayrollRules) -> Decimal:
    """Sick hours included by default — see rules.sick_in_dues_hours."""
    hours = (
        line.reg_hrs
        + line.personal_hrs
        + line.ny_covid_hrs
        + line.bereavement_hrs
        + line.ot_hrs
        + line.ot2_hrs
        + line.vac_hrs
    )
    if rules.sick_in_dues_hours:
        hours += line.sick_hrs
    return hours


def compute_dues(
    line: LineInputs,
    reg_rate: object,
    ot_rate: object | None,
    rules: PayrollRules,
    *,
    apply_initiation_fee: bool = False,
) -> DuesResult:
    """Dues for one member for one week.

    `apply_initiation_fee` is decided by the caller, not here — "the employee's
    first dues week" is a fact about other weeks, which the engine cannot see.
    The service layer resolves it and passes the answer in.
    """
    rate, derived = resolve_ot_rate(reg_rate, ot_rate)
    wage = compute_dues_wage(line, reg_rate=to_decimal(reg_rate, "reg_rate"),
                             ot_rate=rate, rules=rules)
    hours = compute_dues_hours(line, rules)

    return dues_from_wage_and_hours(
        wage, hours, rules,
        apply_initiation_fee=apply_initiation_fee,
        ot_rate_used=rate, ot_rate_derived=derived,
    )


def dues_from_wage_and_hours(
    wage: Decimal,
    hours: Decimal,
    rules: PayrollRules,
    *,
    apply_initiation_fee: bool = False,
    ot_rate_used: Decimal = ZERO,
    ot_rate_derived: bool = False,
) -> DuesResult:
    """The dues formula itself, given a wage and an hour count.

    ⚠️ **EXTRACTED SO THERE IS EXACTLY ONE COPY OF THE FORMULA.** Payroll 4
    computes dues from the REGISTER — the amounts actually paid on a check —
    rather than from hours times a typed rate. That is a different way of
    arriving at `wage` and `hours`, not a different formula, and the two paths
    disagreeing by a cent on the same inputs is the sort of thing nobody would
    find for a year. `compute_dues` now calls this, so the goldens cover both.

    `ot_rate_used` / `ot_rate_derived` are carried for the hours-export path's
    detail report; the register path has no typed OT rate to report, because
    the register prints the rate it actually used.
    """
    # ⚠️ The zero guard runs BEFORE any division and is the only thing making
    # component b safe. There is no other division in the dues path.
    if hours == 0:
        return DuesResult(
            dues_wage=wage, dues_hours=hours,
            component_a=None, component_b=None, component_c=None, capped=None,
            initiation_fee=Decimal("0.00"), dues=Decimal("0.00"),
            ot_rate_used=ot_rate_used, ot_rate_derived=ot_rate_derived,
        )

    a = round2(wage * rules.dues_pct)
    b = round2((wage / hours) * rules.dues_cap_multiplier)
    c = round2(hours * rules.dues_per_hour)
    capped = min(a, b)

    fee = rules.initiation_fee if apply_initiation_fee else Decimal("0.00")
    return DuesResult(
        dues_wage=wage, dues_hours=hours,
        component_a=a, component_b=b, component_c=c, capped=capped,
        initiation_fee=fee, dues=capped + c + fee,
        ot_rate_used=ot_rate_used, ot_rate_derived=ot_rate_derived,
    )


# ---------------------------------------------------------------- vacation


@dataclass(frozen=True)
class VacationResult:
    average_hourly: Decimal     # prior_year_gross / prior_year_hours, unrounded
    vacation_pay: Decimal       # the rounded total
    periods: tuple[Decimal, ...] = field(default_factory=tuple)


def compute_vacation_pay(
    prior_year_gross: object,
    prior_year_hours: object,
    vac_hours: object,
    rules: PayrollRules,
    *,
    split_fractions: list | tuple | None = None,
) -> VacationResult:
    """((prior_gross / prior_hours) + increment) * vac_hours + bonus, rounded once.

    `split_fractions` optionally divides the TOTAL across up to 3 periods. The
    split is applied to the rounded total, not by running the formula per
    period, and the parts are allocated so that they sum to the total EXACTLY —
    a naive per-part round can lose or gain a cent, and a vacation report whose
    parts do not reconcile to its own total is worse than no split at all.
    """
    gross = to_decimal(prior_year_gross, "prior_year_gross")
    hours = to_decimal(prior_year_hours, "prior_year_hours")
    vac = to_decimal(vac_hours, "vac_hours")

    if hours == 0:
        raise ValueError(
            "prior_year_hours is zero; the average hourly rate is undefined. "
            "An employee with no prior-year hours needs a rule, not a division."
        )

    avg = gross / hours
    total = round2((avg + rules.vacation_increment) * vac + rules.vacation_bonus)

    if not split_fractions:
        return VacationResult(average_hourly=avg, vacation_pay=total)

    fractions = [to_decimal(f, "split_fraction") for f in split_fractions]
    if len(fractions) > 3:
        raise ValueError(f"at most 3 vacation periods, got {len(fractions)}")
    if sum(fractions) != Decimal("1"):
        raise ValueError(
            f"vacation split fractions must sum to exactly 1, got {sum(fractions)}"
        )

    return VacationResult(
        average_hourly=avg,
        vacation_pay=total,
        periods=_allocate_exact(total, fractions),
    )


def _allocate_exact(total: Decimal, fractions: list[Decimal]) -> tuple[Decimal, ...]:
    """Split `total` by `fractions` so the parts sum to `total` to the cent.

    Largest-remainder: round each part down, then hand the leftover cents to the
    parts with the biggest discarded remainder. Guarantees sum(parts) == total.
    """
    raw = [total * f for f in fractions]
    floors = [r.quantize(Decimal("0.01"), rounding=ROUND_DOWN) for r in raw]
    shortfall = total - sum(floors)
    cents = int((shortfall / Decimal("0.01")).to_integral_value())
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:cents]:
        floors[i] += Decimal("0.01")
    return tuple(floors)


# ------------------------------------------------------------- stonebucks


def compute_stonebucks_per_day(tons: object, csr_count: object,
                               rules: PayrollRules) -> Decimal:
    """round2(tons * per_ton / csr_count), and 0 when there are no CSRs.

    The csr_count==0 branch is a stated rule, not a guard against a crash: a day
    with tons recorded and nobody to credit them to pays nothing, rather than
    erroring or crediting a phantom.
    """
    t = to_decimal(tons, "tons")
    n = to_decimal(csr_count, "csr_count")
    if n == 0:
        return Decimal("0.00")
    return round2(t * rules.stonebucks_per_ton / n)


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 4 Phase 5 — the vacation bonus, as the register actually pays it.
# ─────────────────────────────────────────────────────────────────────────────


def vacation_bonus_for_year(entitlement_hours: object, rules: PayrollRules) -> Decimal:
    """The YEARLY vacation bonus for an entitlement, from the day tiers.

    ⚠️ **A YEARLY TOTAL FROM THE YEAR'S ENTITLEMENT — NOT A PER-VACATION
    CHARGE.** This is the correction of 2026-11-09. The tiers pay per day of
    entitlement, cumulatively: 15.00 for days 1-5, 10.00 for 6-10, 6.00 for
    11-15, nothing after. Measured against a year of registers:

        40 h   5 days   5x15                 =  75.00
        48 h   6 days   75 + 1x10            =  85.00
        80 h  10 days   75 + 5x10            = 125.00
       120 h  15 days   125 + 5x6            = 155.00
       160 h  20 days   155 + 0              = 155.00

    ⚠️ **155.00 IS A CEILING BECAUSE THE TIERS RUN OUT, NOT BECAUSE OF A CAP
    RULE.** Writing it as `min(total, 155)` would be the same number today and
    a different number the moment a tier changed — and nothing would say which
    rule produced the old figures.

    A rule set with no tiers falls back to the flat `vacation_bonus`, so a week
    already calculated under an older set still re-derives its own figure.
    """
    hours = to_decimal(entitlement_hours, "entitlement_hours")
    if hours <= 0:
        return Decimal("0.00")
    if not rules.vacation_bonus_day_tiers:
        return rules.vacation_bonus

    days = hours / VACATION_HOURS_PER_DAY
    total = Decimal("0")
    previous = 0
    for tier in rules.vacation_bonus_day_tiers:
        through = Decimal(tier["through_day"])
        # Days falling inside this tier, never negative once the tier is past.
        in_tier = min(days, through) - Decimal(previous)
        if in_tier <= 0:
            break
        total += in_tier * tier["per_day"]
        previous = tier["through_day"]
    return round2(total)


def allocate_cumulative(total: Decimal, parts: int) -> tuple[Decimal, ...]:
    """Split `total` into `parts` equal payments summing to it exactly.

    ⚠️ **CUMULATIVE ROUNDING, AND THE REGISTER CHOSE IT — I DID NOT.** Part i
    is `round2(total * i / n) - round2(total * (i-1) / n)`: each running total
    is rounded, so the parts absorb the cents wherever the rounding falls.

    The existing `_allocate_exact` uses largest-remainder, which is a different
    answer. Measured against every `VacBonus` line in a year of registers —
    17 entitlement groups, 29 lines:

      * 16 groups cannot tell the two rules apart. Their totals divide into
        exactly equal cents (38.75 x4, 62.50 x2, a single payment), so both
        rules give the same parts and agreeing with them proves nothing.
      * EXACTLY ONE group discriminates: 155.00 over three payments. The
        register pays 51.67 / 51.66 / 51.67 in date order. Cumulative gives
        51.67 / 51.66 / 51.67. Largest-remainder gives 51.67 / 51.67 / 51.66
        — right total, wrong payments.

    So the evidence is one case deep, and that is worth stating plainly rather
    than reporting "17 of 17 matched". `_allocate_exact` is left alone: it
    splits vacation PAY by caller-chosen fractions, which is a different
    problem from splitting a bonus into equal payments.
    """
    if parts < 1:
        raise ValueError(f"a bonus is paid in at least one part, got {parts}")
    out: list[Decimal] = []
    previous = Decimal("0")
    for i in range(1, parts + 1):
        cumulative = round2(total * Decimal(i) / Decimal(parts))
        out.append(cumulative - previous)
        previous = cumulative
    # The identity the whole function exists for. Cheap, and it would have
    # caught a `parts` of the wrong type before the figures reached a report.
    if sum(out) != round2(total):
        raise AssertionError(
            f"parts {out} sum to {sum(out)}, not {total} — the split lost money"
        )
    return tuple(out)


@dataclass(frozen=True)
class VacationBonusResult:
    entitlement_hours: Decimal
    entitlement_days: Decimal
    yearly_total: Decimal
    parts: tuple[Decimal, ...]


def compute_vacation_bonus(
    entitlement_hours: object, parts: int, rules: PayrollRules
) -> VacationBonusResult:
    """The yearly bonus and the equal payments it is paid in."""
    hours = to_decimal(entitlement_hours, "entitlement_hours")
    total = vacation_bonus_for_year(hours, rules)
    return VacationBonusResult(
        entitlement_hours=hours,
        entitlement_days=hours / VACATION_HOURS_PER_DAY,
        yearly_total=total,
        parts=allocate_cumulative(total, parts),
    )


#: Payentry prints and stores pay rates to four decimals. See
#: `vacation_rate` for why the fourth is TRUNCATED and not rounded.
RATE_PLACES = Decimal("0.0001")


def vacation_rate(prior_year_gross: object, prior_year_hours: object,
                  rules: PayrollRules) -> Decimal:
    """The vacation hourly rate: (prior gross / prior hours) + increment, to 4dp.

    ⚠️ **TRUNCATED TO FOUR DECIMALS, NOT ROUNDED, AND THIS IS THE CENT.** The
    register prints rates to 4dp and this is where the spec's 975.47 was wrong.
    On the week-44 figures (gross 33,062.74 over 1,512.36 hours) the rate is
    22.51168637…:

        truncated to 4dp  ->  22.5116   x 40 = 900.4640  ->  900.46
        rounded   to 4dp  ->  22.5117   x 40 = 900.4680  ->  900.47
        left unrounded                  x 40 = 900.46745 ->  900.47

    James gives the rate as **22.5116** and the pay as **900.46**, which only
    truncation produces. Rounding and leaving it unrounded both give 900.47.

    ⚠️ **AND IT IS TRUNCATION — NOT "ROUNDING TWICE" — THAT MOVES THE FIGURE.**
    I checked the other explanation before writing this: splitting `Vac` and
    `VacBonus` into separately-rounded lines CANNOT change any total, because
    `round2(x + c) == round2(x) + c` whenever `c` is a whole number of cents,
    and every bonus part is (75.00, 85.00, 62.50, 51.67, 38.75…). Verified over
    200,000 random pairs: zero differ. So the two-line split is a structural
    correction that makes the model match what Payentry prints; the 975.47 ->
    975.46 correction is this truncation, and conflating them would leave the
    real cause unfixed while a passing test said otherwise.

    ⚠️ **THE EVIDENCE IS ONE CASE DEEP.** Hunt's is the only vacation line in
    the year whose rate is not already exact to 4dp, so it is the only one that
    can tell truncation from rounding. Every other `Vac` line has a rate like
    27.1900 or 22.3000 and agrees with either rule. Worth confirming against
    Payentry's own rate field before this is treated as settled.
    """
    gross = to_decimal(prior_year_gross, "prior_year_gross")
    hours = to_decimal(prior_year_hours, "prior_year_hours")
    if hours == 0:
        raise ValueError(
            "prior_year_hours is zero; the average hourly rate is undefined. "
            "An employee with no prior-year hours needs a rule, not a division."
        )
    return (gross / hours + rules.vacation_increment).quantize(
        RATE_PLACES, rounding=ROUND_DOWN)


def compute_vacation_pay_only(
    prior_year_gross: object, prior_year_hours: object, vac_hours: object,
    rules: PayrollRules,
) -> Decimal:
    """Vacation PAY for one payment, rounded on its own, with NO bonus in it.

    ⚠️ **TWO LINES, BECAUSE THE REGISTER PAYS TWO LINES.** `Vac` and
    `VacBonus` are separate earning lines, each rounded to the cent. The old
    `compute_vacation_pay` folds the bonus inside one `round2(...)`, which
    makes a vacation payment impossible to reconcile against the register line
    by line even though — see `vacation_rate` — it produces the same total.

    `compute_vacation_pay` is NOT deleted: weeks already calculated under it
    must still re-derive their stored figures.
    """
    vac = to_decimal(vac_hours, "vac_hours")
    return round2(vacation_rate(prior_year_gross, prior_year_hours, rules) * vac)
