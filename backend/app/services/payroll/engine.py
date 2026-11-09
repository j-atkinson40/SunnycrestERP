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
from app.services.payroll.rules import PayrollRules

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
