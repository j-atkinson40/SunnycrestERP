"""The vacation bonus — Payroll 4 Phase 5.

⚠️ **THE DISPATCH'S GOLDENS WERE WRONG AND THE REGISTER WAS RIGHT** (James,
2026-11-09). The bonus is not a flat amount charged per vacation. It is a
YEARLY total built from the year's entitlement in days — 15.00 a day for days
1-5, 10.00 for 6-10, 6.00 for 11-15, nothing after — then paid in equal parts,
one with each vacation payment.

The two goldens that were dropped, recorded so nobody re-derives them:

    "second week, days 6-8 -> 30.00"       — the registers pay a two-week
                                             entitlement 125.00, not 105.00
    "three weeks -> 155.00 as one figure"  — 155.00 is the YEARLY total, paid
                                             51.67 / 51.66 / 51.67

Every expected figure below is hand-derived from the tiers. None came from
running the code under test.
"""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.services.payroll.engine import (
    allocate_cumulative,
    compute_vacation_bonus,
    compute_vacation_pay_only,
    vacation_bonus_for_year,
    vacation_rate,
)
from app.services.payroll.rules import DEFAULT_RULES, PayrollRules

#: entitlement hours, days, yearly total, and the derivation.
TIERS = [
    ("40",  "5",  "75.00",  "5 x 15.00"),
    ("48",  "6",  "85.00",  "75.00 + 1 x 10.00"),
    ("80",  "10", "125.00", "75.00 + 5 x 10.00"),
    ("120", "15", "155.00", "125.00 + 5 x 6.00"),
    ("160", "20", "155.00", "155.00 + 5 x 0 — the tiers have run out"),
]

#: total, parts, and the payments the REGISTER actually made.
SPLITS = [
    ("75.00",  1, ["75.00"]),
    ("85.00",  1, ["85.00"]),
    ("125.00", 1, ["125.00"]),                          # two weeks on one check
    ("125.00", 2, ["62.50", "62.50"]),
    ("155.00", 3, ["51.67", "51.66", "51.67"]),
    ("155.00", 4, ["38.75", "38.75", "38.75", "38.75"]),
]


# ── the tiers ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours, days, total, derivation", TIERS)
def test_the_yearly_total_comes_from_the_entitlement_in_days(hours, days, total,
                                                             derivation):
    assert vacation_bonus_for_year(D(hours), DEFAULT_RULES) == D(total), derivation
    result = compute_vacation_bonus(D(hours), 1, DEFAULT_RULES)
    assert result.entitlement_days == D(days)


def test_the_ceiling_is_the_tiers_running_out_not_a_cap():
    """⚠️ 155.00 is not stored anywhere, and that is deliberate.

    A stored `max 155.00` would give the same number today and a different
    number the moment a tier changed, with nothing to say which rule produced
    the old figures. This asserts the ceiling emerges: a huge entitlement earns
    exactly what fifteen days earn.
    """
    fifteen_days = vacation_bonus_for_year(D("120"), DEFAULT_RULES)
    assert fifteen_days == D("155.00")
    for hours in ("160", "200", "400", "4000"):
        assert vacation_bonus_for_year(D(hours), DEFAULT_RULES) == fifteen_days
    # And no rule field holds 155.
    assert not any(t["per_day"] == D("155.00")
                   for t in DEFAULT_RULES.vacation_bonus_day_tiers)


def test_a_fourth_tier_would_pay_more_than_155():
    """⚠️ THE CONTROL THAT MAKES THE TEST ABOVE MEAN SOMETHING.

    Everything above is equally true of an implementation that computes the
    tiers AND THEN clamps to 155.00 — I checked, by adding
    `min(total, Decimal("155.00"))` to the function: all 33 tests still passed.
    A redundant clamp is not harmless, because it would silently swallow a tier
    change and the old figures would be indistinguishable from the new ones.

    So this extends the tier table and requires the total to EXCEED 155.00. A
    clamped implementation fails here and nowhere else.
    """
    extended = PayrollRules(vacation_bonus_day_tiers=(
        {"through_day": 5, "per_day": "15.00"},
        {"through_day": 10, "per_day": "10.00"},
        {"through_day": 15, "per_day": "6.00"},
        {"through_day": 20, "per_day": "4.00"},      # a tier that did not exist
    ))
    # 155.00 + 5 days x 4.00 = 175.00
    assert vacation_bonus_for_year(D("160"), extended) == D("175.00")
    assert vacation_bonus_for_year(D("160"), extended) > D("155.00"), (
        "the total is clamped at 155.00, so a tier change would be swallowed"
    )
    # The shipped tiers are unaffected by the experiment.
    assert vacation_bonus_for_year(D("160"), DEFAULT_RULES) == D("155.00")


def test_a_partial_day_earns_a_partial_tier_rate():
    """4 hours is half a day at 15.00 — 7.50. Measured entitlements are whole
    days, so this is the behaviour at an untested edge, pinned deliberately so
    a change to it fails rather than drifting."""
    assert vacation_bonus_for_year(D("4"), DEFAULT_RULES) == D("7.50")


def test_no_entitlement_earns_nothing():
    for hours in ("0", "-8"):
        assert vacation_bonus_for_year(D(hours), DEFAULT_RULES) == D("0.00")


def test_a_rule_set_predating_the_tiers_falls_back_to_the_flat_bonus():
    """⚠️ A payroll week already calculated must still re-derive its figure.

    NULL tiers mean "this rule set predates them", which is a real state and
    not an empty table.
    """
    old = PayrollRules(vacation_bonus_day_tiers=())
    assert old.vacation_bonus_day_tiers == ()
    assert vacation_bonus_for_year(D("120"), old) == D("75.00")
    assert vacation_bonus_for_year(D("40"), old) == D("75.00")


def test_the_flat_bonus_and_the_tiers_agree_at_five_days():
    """⚠️ The two fields must not silently disagree.

    `vacation_bonus` is kept for old rule sets and is exactly what the tiers
    give for a five-day entitlement. If someone edits one, this fails.
    """
    assert DEFAULT_RULES.vacation_bonus == vacation_bonus_for_year(
        D("40"), DEFAULT_RULES)


# ── the split ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("total, parts, expected", SPLITS)
def test_the_parts_are_what_the_register_paid(total, parts, expected):
    assert list(allocate_cumulative(D(total), parts)) == [D(e) for e in expected]


def test_the_discriminating_case_is_155_over_three():
    """⚠️ THE ONE CASE THAT CHOSE THE RULE, AND THE ONLY ONE THAT COULD.

    16 of the 17 entitlement groups in a year of registers cannot tell
    cumulative rounding from largest-remainder: their totals divide into
    exactly equal cents, so both rules agree and agreeing proves nothing.
    155.00 over three payments is the single group that discriminates.

        register           51.67 / 51.66 / 51.67
        cumulative         51.67 / 51.66 / 51.67   <- adopted
        largest-remainder  51.67 / 51.67 / 51.66   <- right total, wrong parts

    This test asserts BOTH: that cumulative gives the register's answer, and
    that the existing `_allocate_exact` does not — so the two cannot be quietly
    swapped for each other.
    """
    from app.services.payroll.engine import _allocate_exact

    third = D(1) / D(3)
    assert list(allocate_cumulative(D("155.00"), 3)) == [D("51.67"), D("51.66"),
                                                         D("51.67")]
    largest_remainder = list(_allocate_exact(D("155.00"), [third, third, third]))
    assert largest_remainder == [D("51.67"), D("51.67"), D("51.66")]
    assert largest_remainder != list(allocate_cumulative(D("155.00"), 3)), (
        "the two allocators now agree on the discriminating case, so the "
        "evidence that chose cumulative no longer distinguishes them"
    )


@pytest.mark.parametrize("total, parts", [
    ("155.00", 3), ("155.00", 7), ("85.00", 6), ("125.00", 9), ("0.01", 3),
    ("75.00", 1), ("0.00", 4),
])
def test_the_parts_always_sum_to_the_total_exactly(total, parts):
    """The identity the splitter exists for. A vacation bonus whose parts do
    not reconcile to its own total is worse than no split at all."""
    assert sum(allocate_cumulative(D(total), parts)) == D(total)


def test_a_bonus_is_paid_in_at_least_one_part():
    for parts in (0, -1):
        with pytest.raises(ValueError, match="at least one part"):
            allocate_cumulative(D("75.00"), parts)


# ── the two lines ────────────────────────────────────────────────────────────

def test_vacation_pay_and_the_bonus_are_separate_lines():
    """⚠️ A STRUCTURAL correction that changes no total, stated as such.

    `round2(x + c) == round2(x) + c` for any whole number of cents `c`, and
    every bonus part is one. So splitting the lines cannot move a figure — it
    makes a vacation payment reconcilable against the register line by line,
    which the combined form never was. The figure that DID move (975.47 ->
    975.46) moved because the rate is truncated; see the rate test below.
    """
    pay = compute_vacation_pay_only("33062.74", "1512.36", "40", DEFAULT_RULES)
    bonus = vacation_bonus_for_year(D("40"), DEFAULT_RULES)
    assert pay == D("900.46")
    assert bonus == D("75.00")
    assert pay + bonus == D("975.46")


def test_the_rate_is_truncated_to_four_decimals_not_rounded():
    """⚠️ This, and not the two-line split, is what moves the cent.

        rate unrounded    22.51168637...
        truncated to 4dp  22.5116  x 40 = 900.4640 -> 900.46   <- the register
        rounded   to 4dp  22.5117  x 40 = 900.4680 -> 900.47
        left unrounded             x 40 = 900.46745 -> 900.47

    Only truncation gives James's stated 22.5116. The evidence is ONE case
    deep: Hunt's is the only vacation line in the year whose rate is not
    already exact to 4dp, so every other line agrees with either rule.
    """
    from decimal import ROUND_HALF_UP

    raw = D("33062.74") / D("1512.36") + D("0.65")
    assert vacation_rate("33062.74", "1512.36", DEFAULT_RULES) == D("22.5116")
    # The alternatives, asserted so the choice is visible rather than implied.
    assert raw.quantize(D("0.0001"), rounding=ROUND_HALF_UP) == D("22.5117")
    assert D("22.5117") * 40 > D("900.465"), "rounding would give 900.47"
    assert D("22.5116") * 40 < D("900.465"), "truncating gives 900.46"


def test_a_zero_prior_year_refuses_rather_than_dividing():
    with pytest.raises(ValueError, match="prior_year_hours is zero"):
        vacation_rate("33062.74", "0", DEFAULT_RULES)


# ── the whole thing ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours, parts, expected", [
    ("40",  1, ["75.00"]),
    ("48",  1, ["85.00"]),
    ("80",  2, ["62.50", "62.50"]),
    ("120", 3, ["51.67", "51.66", "51.67"]),
    ("160", 4, ["38.75", "38.75", "38.75", "38.75"]),
])
def test_the_replacement_goldens(hours, parts, expected):
    """Exactly the goldens James specified on 2026-11-09."""
    result = compute_vacation_bonus(D(hours), parts, DEFAULT_RULES)
    assert list(result.parts) == [D(e) for e in expected]
    assert sum(result.parts) == result.yearly_total
