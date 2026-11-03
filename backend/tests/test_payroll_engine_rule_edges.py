"""The rules the week-44 golden fixture cannot test.

⚠️ THIS FILE EXISTS BECAUSE OF A BREAK-TEST RESULT, NOT A HUNCH. The week-44
goldens were break-tested against eight deliberate engine defects. Five turned
them red correctly. THREE DID NOT FIRE AT ALL:

    ROUND_HALF_EVEN instead of ROUND_HALF_UP   ->  0 red  (32/32 still passed)
    vac_hrs dropped from dues_hours            ->  0 red
    sick hours never added to dues_hours       ->  0 red

The first was not predicted. The dispatch names ROUND_HALF_UP explicitly, and no
value in the week-44 fixture lands on an exact half-cent, so the rounding mode
could have been wrong in production with every golden test green. The other two
were predicted (spec §6.2) because `vac_hrs` and `sick_hrs` are zero on all 13
golden rows — but a prediction is not evidence, and the break test is.

Eight of the thirteen line inputs are identically zero in every golden row:
ny_covid_hrs, sick_hrs, bereavement_hrs, ot2_hrs, vac_hrs, stonebucks_amt,
misc_amt, vac_amt. Each gets a case here with a nonzero value and a hand-computed
expectation, so each term in the formula has real contact with a check.

Every expected figure is hand-derived from the spec, with the arithmetic shown.
No database. Bare-database safe.

BASELINE used throughout: reg_hrs 10 @ reg_rate 20.00, ot_rate 30.00
    dues_wage  = 10 * 20.00                      = 200.00
    dues_hours = 10                              = 10
    a = 200.00 * 0.0145                          = 2.90
    b = (200.00 / 10) * 0.6461 = 20 * 0.6461     = 12.922   -> 12.92
    c = 10 * 0.02                                = 0.20
    dues = min(2.90, 12.92) + 0.20               = 3.10
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal as D

import pytest

from app.services.payroll import (
    DEFAULT_RULES,
    LineInputs,
    PayrollRules,
    compute_dues,
    compute_stonebucks_per_day,
    compute_vacation_pay,
    round2,
    to_decimal,
)

REG_RATE = D("20.00")
OT_RATE = D("30.00")
BASELINE = LineInputs(reg_hrs=D("10"))
BASELINE_DUES = D("3.10")


def _dues(line, rules=DEFAULT_RULES, **kw):
    return compute_dues(line, REG_RATE, OT_RATE, rules, **kw)


def test_baseline_is_what_the_docstring_says():
    """Positive control. Every case below is a delta against this row, so if the
    baseline drifts the deltas stop meaning what they say."""
    r = _dues(BASELINE)
    assert (r.dues_wage, r.dues_hours) == (D("200.00"), D("10"))
    assert (r.component_a, r.component_b, r.component_c) == (D("2.90"), D("12.92"), D("0.20"))
    assert r.dues == BASELINE_DUES


# --------------------------------------------- the eight zero-contact inputs

# field, value, expect_wage, expect_hours, expect_dues, derivation
ZERO_CONTACT = [
    ("ny_covid_hrs", "5", "300.00", "15", "4.65",
     "wage (10+5)*20=300; a=300*.0145=4.35; b=(300/15)*.6461=12.922->12.92; c=.30; 4.35+.30"),
    ("bereavement_hrs", "5", "300.00", "15", "4.65",
     "same shape as ny_covid — straight-time hours at reg_rate"),
    ("personal_hrs", "5", "300.00", "15", "4.65",
     "same shape; personal is exercised once in the goldens (E05) but pinned here too"),
    ("ot2_hrs", "5", "350.00", "15", "5.38",
     "wage 10*20 + 5*30 = 350; a=350*.0145=5.075->5.08; b=(350/15)*.6461=15.0757->15.08; c=.30; 5.08+.30"),
    ("vac_hrs", "5", "200.00", "15", "3.20",
     "vac_hrs is in dues_HOURS only, never in wage; a=2.90; b=(200/15)*.6461=8.6147->8.61; c=.30; 2.90+.30"),
    ("sick_hrs", "5", "200.00", "15", "3.20",
     "defaults: excluded from wage, included in hours — identical arithmetic to vac_hrs"),
    ("stonebucks_amt", "50", "250.00", "10", "3.83",
     "wage 200+50=250; a=250*.0145=3.625->3.63 (HALF-UP; half-even gives 3.62); b=25*.6461=16.1525->16.15; c=.20"),
    ("misc_amt", "50", "250.00", "10", "3.83", "flat addition to wage, same as stonebucks"),
    ("vac_amt", "50", "250.00", "10", "3.83", "flat addition to wage, same as stonebucks"),
]


@pytest.mark.parametrize(
    "field,value,e_wage,e_hours,e_dues,derivation",
    ZERO_CONTACT,
    ids=[z[0] for z in ZERO_CONTACT],
)
def test_each_input_moves_dues(field, value, e_wage, e_hours, e_dues, derivation):
    r = _dues(replace(BASELINE, **{field: D(value)}))
    assert r.dues_wage == D(e_wage), f"{field} -> dues_wage ({derivation})"
    assert r.dues_hours == D(e_hours), f"{field} -> dues_hours ({derivation})"
    assert r.dues == D(e_dues), f"{field} -> dues ({derivation})"
    assert r.dues != BASELINE_DUES, f"{field} must move dues off the baseline"


def test_every_line_field_is_either_exercised_or_declared_inert():
    """⚠️ A RATCHET OVER THE FIELD LIST, so a NEW line field cannot be added
    without someone deciding whether it affects dues.

    Without this, adding a column to `payroll_week_line` and to `LineInputs`
    produces a field that silently contributes nothing, and no test anywhere
    says so — the read-site/write-site gap CLAUDE.md §11 calls "complete
    machinery behind an unprovisioned entrance".
    """
    exercised = {z[0] for z in ZERO_CONTACT} | {"reg_hrs", "ot_hrs"}
    declared_inert = {"winter_hrs", "weeks_pay"}   # see the characterization below
    assert exercised | declared_inert == set(LineInputs.__dataclass_fields__), (
        "a LineInputs field is neither exercised by a test nor declared inert; "
        "decide which it is"
    )
    assert not (exercised & declared_inert)


def test_winter_hours_and_weeks_pay_do_not_move_dues():
    """CHARACTERIZATION — pins an OPEN QUESTION, not a settled rule.

    # WRONGNESS (possibly): `winter_hrs` is an HOUR column that is excluded from
    # dues_hours while every other hour column is included, and `weeks_pay` is a
    # money column excluded from dues_wage. Neither appears in either formula as
    # specified. Whether that is intentional is unresolved — spec §7.5, alongside
    # the sick-time asymmetry in §7.2.
    #
    # This test asserts the CURRENT specified behaviour so that the question
    # cannot be closed by accident. If the accountant rules that winter_hrs
    # belongs in dues_hours, this test fails and names the ruling, rather than
    # the behaviour changing with nothing to notice.
    """
    for field, value in (("winter_hrs", "5"), ("weeks_pay", "50")):
        r = _dues(replace(BASELINE, **{field: D(value)}))
        assert r.dues_wage == D("200.00"), f"{field} is not a dues_wage term"
        assert r.dues_hours == D("10"), f"{field} is not a dues_hours term"
        assert r.dues == BASELINE_DUES, f"{field} does not move dues today"


# ------------------------------------------------------- ROUND_HALF_UP

def test_round2_is_half_up_not_half_even():
    """⚠️ THE GOLDENS CANNOT SEE THIS. Swapping the rounding mode left all 32
    week-44 assertions green, because no value in that fixture lands on an exact
    half-cent. These do.

    Python's Decimal default is ROUND_HALF_EVEN; Excel's ROUND is half-up. The
    two disagree only when the discarded part is EXACTLY half and the kept digit
    is even, which is why a realistic fixture can miss it entirely.
    """
    # value      half-up   half-even
    cases = [("0.125", "0.13", "0.12"),
             ("0.145", "0.15", "0.14"),
             ("3.625", "3.63", "3.62"),
             ("2.005", "2.01", "2.00")]
    for raw, half_up, half_even in cases:
        assert round2(D(raw)) == D(half_up), f"round2({raw}) must be half-up"
        assert D(half_up) != D(half_even), f"{raw} must actually discriminate the two modes"


def test_half_cent_propagates_through_a_whole_dues_calculation():
    """End-to-end half-cent, so the mode is guarded in the dues path too and not
    only in the helper.

        reg_hrs 1.275 @ reg_rate 1.00
        wage  = 1.275 ; hours = 1.275
        a = 1.275 * 0.0145   = 0.0184875            -> 0.02
        b = (1.275/1.275) * 0.6461 = 0.6461         -> 0.65
        c = 1.275 * 0.02     = 0.0255  <- EXACT HALF -> 0.03 half-up
                                                       (0.02 half-even)
        dues = min(0.02, 0.65) + 0.03               = 0.05
                                   half-even would give 0.02 + 0.02 = 0.04
    """
    r = compute_dues(LineInputs(reg_hrs=D("1.275")), D("1.00"), D("1.50"), DEFAULT_RULES)
    assert r.component_c == D("0.03"), "c rounds half-up"
    assert r.dues == D("0.05")
    assert r.dues != D("0.04"), "0.04 is the half-even answer"


# ---------------------------------------------------------- the sick flags

# sick_in_dues_wage, sick_in_dues_hours, expect_wage, expect_hours, expect_dues
SICK_MATRIX = [
    (False, True, "200.00", "15", "3.20",
     "DEFAULT — the workbook: excluded from wage, included in hours"),
    (True, True, "300.00", "15", "4.65",
     "both: wage (10+5)*20=300; a=4.35; b=(300/15)*.6461=12.92; c=.30"),
    (False, False, "200.00", "10", "3.10",
     "neither: identical to the baseline row"),
    (True, False, "300.00", "10", "4.55",
     "wage only: a=300*.0145=4.35; b=(300/10)*.6461=19.383->19.38; c=.20; 4.35+.20"),
]


@pytest.mark.parametrize("in_wage,in_hours,e_wage,e_hours,e_dues,why", SICK_MATRIX)
def test_sick_flags_all_four_combinations(in_wage, in_hours, e_wage, e_hours, e_dues, why):
    """⚠️ ALL FOUR, AND ALL FOUR ANSWERS ARE DISTINCT.

    The golden fixture has sick_hrs = 0 on every row, so it cannot distinguish
    any of these from any other — flipping either flag left all 32 assertions
    green (break-tested). Four distinct expected values is what makes this a real
    check rather than a restatement of the default.
    """
    rules = PayrollRules(sick_in_dues_wage=in_wage, sick_in_dues_hours=in_hours)
    r = _dues(replace(BASELINE, sick_hrs=D("5")), rules=rules)
    assert r.dues_wage == D(e_wage), why
    assert r.dues_hours == D(e_hours), why
    assert r.dues == D(e_dues), why


def test_the_four_sick_combinations_are_mutually_distinct():
    """The control: if two combinations gave the same dues, the test above would
    pass against an engine that honoured only one of the two flags."""
    seen = {}
    for in_wage, in_hours, _, _, e_dues, _ in SICK_MATRIX:
        assert e_dues not in seen, f"{(in_wage, in_hours)} collides with {seen.get(e_dues)}"
        seen[e_dues] = (in_wage, in_hours)
    assert len(seen) == 4


def test_default_rules_reproduce_the_workbook_asymmetry():
    assert DEFAULT_RULES.sick_in_dues_wage is False
    assert DEFAULT_RULES.sick_in_dues_hours is True


# -------------------------------------------------------- initiation fee

def test_initiation_fee_is_added_on_the_first_dues_week():
    """dues = min(a,b) + c + fee = 2.90 + 0.20 + 10.00 = 13.10"""
    r = _dues(BASELINE, apply_initiation_fee=True)
    assert r.initiation_fee == D("10.00")
    assert r.dues == D("13.10")
    assert r.dues - BASELINE_DUES == D("10.00")


def test_initiation_fee_is_not_added_on_a_zero_hours_week():
    """The zero-hours rule says dues = 0, and it wins over the fee.

    # WRONGNESS (reading, not measured): the dispatch states "if dues_hours == 0
    # -> dues = 0" before the fee clause, and "first dues week" reads as a week
    # in which dues actually arise. So a member with no hours is not charged the
    # initiation fee and remains due it next week. Flagged in spec §7.6 — if the
    # accountant rules the fee is owed regardless, this test fails and says so.
    """
    r = _dues(LineInputs(), apply_initiation_fee=True)
    assert r.dues_hours == 0
    assert r.initiation_fee == D("0.00")
    assert r.dues == D("0.00")


# ------------------------------------------------------------ vacation

def test_vacation_split_parts_sum_exactly_to_the_total():
    """975.47 split 0.5 / 0.25 / 0.25.

        raw    : 487.735 , 243.8675 , 243.8675
        floors : 487.73  , 243.86   , 243.86    = 975.45  (2 cents short)
        remainders: 0.005 , 0.0075  , 0.0075    -> the two 0.0075 parts get a cent
        final  : 487.73  , 243.87   , 243.87    = 975.47  exactly

    A naive per-part round would give 487.74 + 243.87 + 243.87 = 975.48 and a
    report whose parts do not reconcile to its own total.
    """
    r = compute_vacation_pay("33062.74", "1512.36", "40", DEFAULT_RULES,
                             split_fractions=["0.5", "0.25", "0.25"])
    assert r.vacation_pay == D("975.47")
    assert r.periods == (D("487.73"), D("243.87"), D("243.87"))
    assert sum(r.periods) == r.vacation_pay


def test_vacation_split_fractions_must_sum_to_one():
    with pytest.raises(ValueError, match="sum to exactly 1"):
        compute_vacation_pay("33062.74", "1512.36", "40", DEFAULT_RULES,
                             split_fractions=["0.5", "0.25"])


def test_vacation_allows_at_most_three_periods():
    with pytest.raises(ValueError, match="at most 3"):
        compute_vacation_pay("33062.74", "1512.36", "40", DEFAULT_RULES,
                             split_fractions=["0.25", "0.25", "0.25", "0.25"])


def test_vacation_refuses_zero_prior_year_hours():
    """Named refusal, not a ZeroDivisionError and not a plausible default."""
    with pytest.raises(ValueError, match="prior_year_hours is zero"):
        compute_vacation_pay("33062.74", "0", "40", DEFAULT_RULES)


# ---------------------------------------------------------- stonebucks

def test_stonebucks_per_day():
    """10 tons * 11.00 / 4 CSRs = 110.00 / 4 = 27.50"""
    assert compute_stonebucks_per_day("10", "4", DEFAULT_RULES) == D("27.50")


def test_stonebucks_rounds_half_up():
    """3 tons * 11.00 / 8 = 33.00 / 8 = 4.125 -> 4.13 half-up (4.12 half-even)"""
    assert compute_stonebucks_per_day("3", "8", DEFAULT_RULES) == D("4.13")


def test_stonebucks_is_zero_when_there_are_no_csrs():
    """A stated rule, not a crash guard: tons with nobody to credit pays nothing."""
    assert compute_stonebucks_per_day("10", "0", DEFAULT_RULES) == D("0.00")
    assert compute_stonebucks_per_day("0", "0", DEFAULT_RULES) == D("0.00")


# -------------------------------------------------------- float rejection

def test_float_is_refused_at_every_boundary():
    """⚠️ REFUSED, NOT CONVERTED. Decimal(0.1) is
    0.1000000000000000055511151231257827021181583404541015625, and dues built
    from it would round correctly almost always — which cannot be caught by a
    test. So float is made unexpressible rather than discouraged.
    """
    with pytest.raises(TypeError, match="float is not accepted"):
        to_decimal(0.1, "rate")
    with pytest.raises(TypeError, match="float is not accepted"):
        LineInputs(reg_hrs=40.0)
    with pytest.raises(TypeError, match="float is not accepted"):
        PayrollRules(dues_pct=0.0145)
    with pytest.raises(TypeError, match="bool"):
        to_decimal(True, "rate")

    # Exact inputs are accepted.
    assert to_decimal("24.54") == D("24.54")
    assert to_decimal(40) == D("40")


def test_remittance_grouping_setting_is_validated():
    assert DEFAULT_RULES.remittance_group_by == "week_end_date"
    PayrollRules(remittance_group_by="check_date")
    with pytest.raises(ValueError, match="remittance_group_by"):
        PayrollRules(remittance_group_by="invoice_date")


# ------------------------------------------------- report number formatting

def test_fmt_exact_never_emits_exponent_notation():
    """⚠️ REGRESSION. `Decimal.normalize()` alone turns 40.0000 into `4E+1`.

    Hours and wages come back from Numeric columns carrying the column's scale
    as trailing zeros (`47.0000`, `13236.25275000`). Stripping them with bare
    `normalize()` is correct for 52.8000 and WRONG for every whole number that
    is a multiple of ten — so a 40-hour week rendered as "4E+1" on the report,
    and a 100-hour total as "1E+2".

    Found end-to-end, not by reading: the member rows read `47` while the total
    read `520.4400`, because rows and totals were formatted by different code.
    They now share one function, and this pins both halves.
    """
    from app.services.payroll.reports import fmt_exact, fmt_hours

    assert fmt_hours is fmt_exact, "rows and totals must share one formatter"

    cases = {
        "47.0000": "47",
        "40.0000": "40",            # bare normalize() -> 4E+1
        "100.0000": "100",          # bare normalize() -> 1E+2
        "0.0000": "0",
        "52.8000": "52.8",
        "31.6500": "31.65",
        "520.4400": "520.44",
        "1.2750": "1.275",
        "13236.25275000": "13236.25275",
    }
    for raw, expected in cases.items():
        got = fmt_exact(D(raw))
        assert got == expected, f"fmt_exact({raw}) == {got!r}, expected {expected!r}"
        assert "E" not in got and "e" not in got, f"{raw} rendered in exponent form"

    assert fmt_exact(None) is None


def test_fmt_exact_preserves_value_not_just_appearance():
    """The formatter must not round. It strips zeros; it does not lose digits."""
    from app.services.payroll.reports import fmt_exact

    for raw in ("13236.25275000", "707.87660000", "1.2750", "0.0100"):
        assert D(fmt_exact(D(raw))) == D(raw), f"{raw} changed value"
