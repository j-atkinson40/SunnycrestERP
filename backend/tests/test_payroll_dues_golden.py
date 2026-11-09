"""Week 44 union dues golden tests — w/e 2026-10-31, check date 2026-11-05.

⚠️ EVERY EXPECTED FIGURE BELOW IS A LITERAL, DERIVED FROM THE SPEC BEFORE THE
ENGINE EXISTED. None was produced by running the code under test (CLAUDE.md §11
"Money math is hand-proven — including aggregates", "Figures in dispatches are
never inherited"). The derivation is shown per row in `GOLDEN`, and the two
worked examples below show the full arithmetic.

Anonymized ids. Real employee names are deliberately absent from fixtures.

⚠️ THE DISPATCH'S STATED TOTAL HOURS (479.24) WAS WRONG AND IS NOT ASSERTED HERE.
It is the running total through E12 and omits E13's 41.20. Ruled 2026-11-03 in
favour of 520.44 — all 13 rows, consistent with the dues and wage totals, which
are both 13-row. See docs/specs/payroll-reports.md §7.1. This is the first known
defect the module corrects relative to the workbook it replaces.

Rates are the workbook's own typed-in OT rates, which are frequently NOT 1.5x:
9 of these 13 members carry an OT rate that is not 1.5 * reg_rate.

No database. Pure engine. Bare-database safe — creates no rows at all.

    E01 worked: dues_wage = 40*30 + 7*45 = 1200 + 315      = 1515.00
                dues_hours                = 40 + 7          = 47
                a = 1515.00 * 0.0145                        = 21.9675  -> 21.97
                b = (1515.00/47) * 0.6461
                  = 32.2340425531914893617... * 0.6461      = 20.82641... -> 20.83
                c = 47 * 0.02                               = 0.94
                dues = min(21.97, 20.83) + 0.94 = 20.83 + 0.94 = 21.77   (b binds)

    E04 worked: dues_wage = 40*24.39 + 2*36.585 = 975.60 + 73.17 = 1048.77
                dues_hours                       = 40 + 2         = 42
                a = 1048.77 * 0.0145                              = 15.207165 -> 15.21
                b = (1048.77/42) * 0.6461
                  = 24.97071428571...* 0.6461                     = 16.13337... -> 16.13
                c = 42 * 0.02                                     = 0.84
                dues = min(15.21, 16.13) + 0.84 = 15.21 + 0.84    = 16.05   (a binds)
"""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.services.payroll import DEFAULT_RULES, LineInputs, compute_dues, compute_vacation_pay

# id, reg, personal, ot, reg_rate, typed_ot_rate,
#     expect_wage, expect_hours, expect_a, expect_b, expect_c, expect_dues, binds
GOLDEN = [
    ("E01", "40",    "0", "7",    "30",    "45",     "1515.00",    "47",    "21.97", "20.83", "0.94", "21.77", "b"),
    ("E02", "40",    "0", "12.8", "24.54", "35.835", "1440.288",   "52.8",  "20.88", "17.62", "1.06", "18.68", "b"),
    ("E03", "40",    "0", "7.9",  "24.39", "36.585", "1264.6215",  "47.9",  "18.34", "17.06", "0.96", "18.02", "b"),
    ("E04", "40",    "0", "2",    "24.39", "36.585", "1048.77",    "42",    "15.21", "16.13", "0.84", "16.05", "a"),
    ("E05", "36",    "4", "7.68", "24.44", "35.685", "1251.6608",  "47.68", "18.15", "16.96", "0.95", "17.91", "b"),
    ("E06", "40",    "0", "7.43", "24.39", "36.585", "1247.42655", "47.43", "18.09", "16.99", "0.95", "17.94", "b"),
    ("E07", "32",    "0", "6.68", "22.34", "32.535", "932.2138",   "38.68", "13.52", "15.57", "0.77", "14.29", "a"),
    ("E08", "40",    "0", "5.83", "22.34", "32.535", "1083.27905", "45.83", "15.71", "15.27", "0.92", "16.19", "b"),
    ("E09", "0",     "0", "0",    "22.34", "32.535", "0",          "0",     None,    None,    None,   "0.00", "zero"),
    ("E10", "31.57", "0", "0.08", "22.34", "32.535", "707.8766",   "31.65", "10.26", "14.45", "0.63", "10.89", "a"),
    ("E11", "32",    "0", "4.9",  "22.34", "32.535", "874.3015",   "36.9",  "12.68", "15.31", "0.74", "13.42", "a"),
    ("E12", "40",    "0", "1.37", "22.34", "32.535", "938.17295",  "41.37", "13.60", "14.65", "0.83", "14.43", "a"),
    ("E13", "40",    "0", "1.2",  "22.34", "32.535", "932.642",    "41.2",  "13.52", "14.63", "0.82", "14.34", "a"),
]

# Totals over all 13 rows. The wage total is the sum of UNROUNDED wages; the
# report rounds it for presentation, and both values are asserted so a change to
# where rounding happens cannot pass.
TOTAL_DUES = D("193.93")
TOTAL_WAGE_EXACT = D("13236.25275")
TOTAL_WAGE_ROUNDED = D("13236.25")
TOTAL_HOURS = D("520.44")


def _line(reg, personal, ot):
    return LineInputs(reg_hrs=D(reg), personal_hrs=D(personal), ot_hrs=D(ot))


@pytest.mark.parametrize(
    "emp,reg,personal,ot,reg_rate,ot_rate,e_wage,e_hours,e_a,e_b,e_c,e_dues,e_binds",
    GOLDEN,
    ids=[g[0] for g in GOLDEN],
)
def test_week44_member_dues_typed_ot_rates(
    emp, reg, personal, ot, reg_rate, ot_rate, e_wage, e_hours, e_a, e_b, e_c, e_dues, e_binds
):
    r = compute_dues(_line(reg, personal, ot), D(reg_rate), D(ot_rate), DEFAULT_RULES)

    assert r.dues_wage == D(e_wage), f"{emp} dues_wage"
    assert r.dues_hours == D(e_hours), f"{emp} dues_hours"
    assert r.dues == D(e_dues), f"{emp} dues"
    assert r.binds == e_binds, f"{emp} which component binds"

    if e_a is None:
        # E09 — the zero-hours short circuit. No components, and critically no
        # division: component b would be a ZeroDivisionError without the guard.
        assert (r.component_a, r.component_b, r.component_c) == (None, None, None)
    else:
        assert r.component_a == D(e_a), f"{emp} component a"
        assert r.component_b == D(e_b), f"{emp} component b"
        assert r.component_c == D(e_c), f"{emp} component c"
        assert r.dues == min(D(e_a), D(e_b)) + D(e_c), f"{emp} dues recomposition"

    # The typed OT rate was used as given, never derived.
    assert r.ot_rate_derived is False
    assert r.ot_rate_used == D(ot_rate)


def test_week44_totals_cover_all_thirteen_rows():
    """⚠️ Asserts the POPULATION, not just the sums.

    The dispatch's three stated totals had two different populations — dues and
    wage over 13 rows, hours over 12. A test that only checked the sums would
    have passed on two of them and told nobody the third was a different
    denominator (CLAUDE.md §11 "a gate reports its denominator").
    """
    results = [
        compute_dues(_line(g[1], g[2], g[3]), D(g[4]), D(g[5]), DEFAULT_RULES)
        for g in GOLDEN
    ]
    assert len(results) == 13, "all 13 members must be in every total"

    assert sum(r.dues for r in results) == TOTAL_DUES
    assert sum(r.dues_wage for r in results) == TOTAL_WAGE_EXACT
    assert sum(r.dues_hours for r in results) == TOTAL_HOURS

    from app.services.payroll import round2
    assert round2(sum(r.dues_wage for r in results)) == TOTAL_WAGE_ROUNDED


def test_the_dispatch_hours_total_was_the_twelve_row_figure():
    """Pins the defect this module corrects, so it cannot silently come back.

    479.24 is not a rounding artefact and not a rule — it is the running total
    through E12. Asserting the arithmetic of the mistake means a future change
    that reintroduces a short SUM range fails here with a named reason, rather
    than quietly producing the workbook's old number again.
    """
    results = [
        compute_dues(_line(g[1], g[2], g[3]), D(g[4]), D(g[5]), DEFAULT_RULES)
        for g in GOLDEN
    ]
    twelve = sum(r.dues_hours for r in results[:12])
    thirteen = sum(r.dues_hours for r in results)

    assert twelve == D("479.24"), "the workbook's stated total"
    assert thirteen == TOTAL_HOURS, "all 13 rows — the correct total"
    assert thirteen - twelve == D("41.20") == results[12].dues_hours


def test_both_branches_of_the_cap_are_exercised():
    """The min(a, b) cap must be discriminated in BOTH directions.

    A fixture where the cap always binds would pass identically against
    `dues = b + c`, and one where it never binds would pass against
    `dues = a + c`. Neither would be evidence about `min` (CLAUDE.md §11
    green-without-evidence shape 7 — which wrong answers also satisfy this?).
    """
    binds = [
        compute_dues(_line(g[1], g[2], g[3]), D(g[4]), D(g[5]), DEFAULT_RULES).binds
        for g in GOLDEN
    ]
    assert binds.count("b") == 6, "cap binds on 6 rows"
    assert binds.count("a") == 6, "percentage binds on 6 rows"
    assert binds.count("zero") == 1, "E09 exercises the zero-hours short circuit"


# ------------------------------------------------- null OT rate (second golden)

# id -> (dues with typed ot, dues with ot_rate NULL, delta)
# Members whose typed OT rate already equals 1.5 * reg_rate are unchanged:
#   E01 30 -> 45, E03/E04/E06 24.39 -> 36.585. E09 is zero either way.
NULL_OT = [
    ("E01", "21.77", "21.77", "0.00"),
    ("E02", "18.68", "18.84", "0.16"),
    ("E03", "18.02", "18.02", "0.00"),
    ("E04", "16.05", "16.05", "0.00"),
    ("E05", "17.91", "18.01", "0.10"),
    ("E06", "17.94", "17.94", "0.00"),
    ("E07", "14.29", "14.38", "0.09"),
    ("E08", "16.19", "16.27", "0.08"),
    ("E09", "0.00",  "0.00",  "0.00"),
    ("E10", "10.89", "10.90", "0.01"),
    ("E11", "13.42", "13.49", "0.07"),
    ("E12", "14.43", "14.45", "0.02"),
    ("E13", "14.34", "14.36", "0.02"),
]
CHANGED_UNDER_NULL_OT = ["E02", "E05", "E07", "E08", "E10", "E11", "E12", "E13"]
TOTAL_DUES_NULL_OT = D("194.48")


@pytest.mark.parametrize("emp,e_typed,e_derived,e_delta", NULL_OT, ids=[n[0] for n in NULL_OT])
def test_week44_member_dues_with_null_ot_rate(emp, e_typed, e_derived, e_delta):
    g = next(g for g in GOLDEN if g[0] == emp)
    line = _line(g[1], g[2], g[3])

    typed = compute_dues(line, D(g[4]), D(g[5]), DEFAULT_RULES)
    derived = compute_dues(line, D(g[4]), None, DEFAULT_RULES)

    assert typed.dues == D(e_typed), f"{emp} dues on the typed OT rate"
    assert derived.dues == D(e_derived), f"{emp} dues on a derived 1.5x OT rate"
    assert derived.dues - typed.dues == D(e_delta), f"{emp} delta"

    assert derived.ot_rate_derived is True
    assert derived.ot_rate_used == D(g[4]) * D("1.5")


def test_null_ot_rate_raises_dues_for_exactly_eight_members():
    changed, unchanged = [], []
    for g in GOLDEN:
        line = _line(g[1], g[2], g[3])
        typed = compute_dues(line, D(g[4]), D(g[5]), DEFAULT_RULES)
        derived = compute_dues(line, D(g[4]), None, DEFAULT_RULES)
        (changed if derived.dues != typed.dues else unchanged).append(g[0])

    assert changed == CHANGED_UNDER_NULL_OT
    assert unchanged == ["E01", "E03", "E04", "E06", "E09"]

    # Direction matters as much as the set — a 1.5x rate is never lower than the
    # workbook's typed rate in this fixture, so dues can only rise.
    for emp in changed:
        row = next(n for n in NULL_OT if n[0] == emp)
        assert D(row[3]) > 0, f"{emp} delta must be positive"

    total = sum(
        compute_dues(_line(g[1], g[2], g[3]), D(g[4]), None, DEFAULT_RULES).dues
        for g in GOLDEN
    )
    assert total == TOTAL_DUES_NULL_OT
    assert total - TOTAL_DUES == D("0.55")


def test_the_five_unchanged_members_are_unchanged_for_two_different_reasons():
    """The control for the test above — and the reasons do NOT coincide.

    ⚠️ TWO CAUSES, ONE SYMPTOM. Four members are unchanged because their typed
    OT rate ALREADY equals 1.5 * reg_rate, so deriving it changes nothing. E09
    is unchanged because its hours are ZERO, and its rate is not 1.5x at all
    (22.34 * 1.5 = 33.51, against a typed 32.535) — deriving the rate does move
    its dues_wage, and the zero-hours short circuit is what holds its dues at
    0.00 regardless.

    Asserting one list of five would have been a true statement built on a false
    reason, and it would have certified an engine that short-circuited the wrong
    row (CLAUDE.md §11 "a CAUSE is inherited more easily than a count" — the
    specific trap is a shared symptom). This test was written as the single list
    and failed, which is how the conflation was found.
    """
    exact_rate = [g[0] for g in GOLDEN if D(g[5]) == D(g[4]) * D("1.5")]
    assert exact_rate == ["E01", "E03", "E04", "E06"]

    # E09 is NOT in that set, and its rate is genuinely not 1.5x.
    e09 = next(g for g in GOLDEN if g[0] == "E09")
    assert D(e09[5]) != D(e09[4]) * D("1.5")
    assert D(e09[5]) == D("32.535") and D(e09[4]) * D("1.5") == D("33.510")

    # Its dues_wage DOES move when the rate is derived... except that with zero
    # OT hours there is nothing for either rate to multiply, so the wage is 0.00
    # either way and the hours guard is the operative rule. Both are asserted so
    # neither can be the accidental explanation.
    line = _line(e09[1], e09[2], e09[3])
    typed = compute_dues(line, D(e09[4]), D(e09[5]), DEFAULT_RULES)
    derived = compute_dues(line, D(e09[4]), None, DEFAULT_RULES)
    assert typed.dues_hours == 0 and derived.dues_hours == 0
    assert typed.component_a is None and derived.component_a is None
    assert typed.dues == derived.dues == D("0.00")
    assert derived.ot_rate_used == D("33.510"), "the derived rate was computed"
    assert derived.ot_rate_derived is True


# ------------------------------------------------------------------ vacation


#: Hunt's first vacation week, as the register prints it. James, 2026-11-09.
#: Hand-derived; `test_hunts_first_vacation_week_is_two_lines` shows the work.
HUNT_PRIOR_GROSS = "33062.74"
HUNT_PRIOR_HOURS = "1512.36"
HUNT_RATE = D("22.5116")
HUNT_VAC_PAY = D("900.46")
HUNT_VAC_BONUS = D("75.00")


def test_week44_vacation_pay_is_the_SUPERSEDED_combined_computation():
    """⚠️ A CHARACTERIZATION TEST, NOT A TARGET.

    `compute_vacation_pay` folds the bonus inside one `round2(...)` and leaves
    the hourly rate unrounded. The register does neither: it prints `Vac` and
    `VacBonus` as separate lines and its rates carry four decimals. This figure
    is therefore WRONG against the register and is pinned only because payroll
    weeks already calculated under this function must still re-derive their
    stored figures. New work uses `compute_vacation_pay_only` plus
    `vacation_bonus_for_year` — see the test below.

      33062.74 / 1512.36 = 21.86168637096987489751117459
                  + 0.65 = 22.51168637096987489751117459
                    * 40 = 900.4674548387949959004469836
                    + 75 = 975.4674548387949959004469836
                  round2 = 975.47        <- 975.46 per the register
    """
    r = compute_vacation_pay(HUNT_PRIOR_GROSS, HUNT_PRIOR_HOURS, "40", DEFAULT_RULES)
    assert r.vacation_pay == D("975.47")
    assert r.average_hourly == D(HUNT_PRIOR_GROSS) / D(HUNT_PRIOR_HOURS)
    assert r.periods == ()


def test_hunts_first_vacation_week_is_two_lines(): 
    """The replacement golden: Vac 900.46 + VacBonus 75.00 = 975.46.

      rate  = 33062.74 / 1512.36 + 0.65 = 22.51168637096987489751117459
      TRUNCATED to 4dp (not rounded)    = 22.5116
      Vac   = round2(22.5116 * 40)      = round2(900.4640) = 900.46
      Bonus = 5 entitlement days x 15.00                   =  75.00
      total = 900.46 + 75.00                               = 975.46

    ⚠️ Truncation is what moves this figure, NOT the two-line split. Rounding
    the rate to 4dp gives 22.5117 and 900.47; leaving it unrounded also gives
    900.47. Only truncation gives James's stated 22.5116. And the split cannot
    change a total at all — `round2(x + c) == round2(x) + c` for any whole
    number of cents `c`, which every bonus part is. See `engine.vacation_rate`.
    """
    from app.services.payroll.engine import (
        compute_vacation_pay_only, vacation_bonus_for_year, vacation_rate)

    assert vacation_rate(HUNT_PRIOR_GROSS, HUNT_PRIOR_HOURS, DEFAULT_RULES) == HUNT_RATE
    pay = compute_vacation_pay_only(HUNT_PRIOR_GROSS, HUNT_PRIOR_HOURS, "40",
                                    DEFAULT_RULES)
    bonus = vacation_bonus_for_year(D("40"), DEFAULT_RULES)
    assert pay == HUNT_VAC_PAY
    assert bonus == HUNT_VAC_BONUS
    assert pay + bonus == D("975.46")
    # ⚠️ And the superseded path really does disagree, or this test is
    # asserting a difference that is not there.
    assert compute_vacation_pay(HUNT_PRIOR_GROSS, HUNT_PRIOR_HOURS, "40",
                                DEFAULT_RULES).vacation_pay == D("975.47")
