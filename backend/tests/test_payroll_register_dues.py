"""Dues from a check's own pay lines — Payroll 4 Phase 2.

⚠️ **THE EXPECTED FIGURES ARE HAND-DERIVED FROM THE RULES, NOT PRODUCED BY THE
ENGINE.** `register_fixture.EXPECTED_DUES` shows the full arithmetic per check.
A fixture whose answer key came from the code under test would agree with any
formula, including a wrong one.

⚠️ **AND THE CODE MAP ITSELF WAS MEASURED, NOT CHOSEN.** It was found by
scoring candidate maps against 629 real `Union` deduction lines — the
deduction Payentry actually took is the answer key. The full-year check lives
in `scripts/check_register_dues.py`, because it needs a real export and a real
export never enters the repository. What CI holds is the map, the formula, and
the classifier.
"""
from __future__ import annotations

import io
from decimal import Decimal as D

import pdfplumber
import pytest

from app.services.payroll.engine import LineInputs, compute_dues, dues_from_wage_and_hours
from app.services.payroll.register_dues import (
    DUES_EXCLUDED_CODES,
    DUES_HOURS_CODES,
    DUES_WAGE_CODES,
    actual_dues,
    classify_difference,
    dues_for_check,
    dues_wage_and_hours,
)
from app.services.payroll.register_parser import (
    DUES_EXCLUDED_EARNING_CODES,
    KNOWN_EARNING_CODES,
    parse_register,
)
from app.services.payroll.rules import DEFAULT_RULES
from tests.fixtures.payroll import register_fixture


@pytest.fixture(scope="module")
def by_emp():
    with pdfplumber.open(io.BytesIO(register_fixture.build())) as pdf:
        return {c.emp_id: c for c in parse_register(pdf).checks}


# ── the map ──────────────────────────────────────────────────────────────────

def test_every_known_earning_code_is_classified():
    """⚠️ A new earning code cannot land in neither list unnoticed.

    This is the real risk with a map like this: Payentry adds a pay type, it is
    silently in nothing, and every dues figure for whoever receives it is
    quietly low. The parser's own code list is the population.
    """
    covered = DUES_WAGE_CODES | DUES_HOURS_CODES | DUES_EXCLUDED_CODES
    missing = sorted(KNOWN_EARNING_CODES - covered)
    assert not missing, (
        f"these earning codes are in no dues list: {missing}. Decide for each "
        "whether it is dues wage, dues hours, both or neither — measured "
        "against real Union deductions, not guessed."
    )


def test_the_map_names_no_code_that_does_not_exist():
    """⚠️ A positive control on the test above.

    A map full of invented codes would satisfy the coverage assertion while
    describing nothing real.
    """
    covered = DUES_WAGE_CODES | DUES_HOURS_CODES | DUES_EXCLUDED_CODES
    unreal = sorted(covered - KNOWN_EARNING_CODES)
    assert not unreal, f"these are in a dues list but are not register codes: {unreal}"


def test_sal_and_sick_are_excluded_and_the_two_modules_agree():
    """Both are rulings, and both are stated in two places.

    `register_parser.DUES_EXCLUDED_EARNING_CODES` holds the rulings; this
    module holds the full map. They must not disagree.
    """
    assert DUES_EXCLUDED_EARNING_CODES <= DUES_EXCLUDED_CODES
    for code in ("Sal", "Sick"):
        assert code not in DUES_WAGE_CODES
        assert code not in DUES_HOURS_CODES


def test_vacbonus_is_in_the_wage_but_not_the_hours():
    """Measured: 29 `VacBonus` lines in the year, every one with no hours."""
    assert "VacBonus" in DUES_WAGE_CODES
    assert "VacBonus" not in DUES_HOURS_CODES


# ── the figures ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("emp_id", sorted(register_fixture.EXPECTED_DUES))
def test_dues_match_the_hand_derived_figures(by_emp, emp_id):
    expected = register_fixture.EXPECTED_DUES[emp_id]
    row = dues_for_check(by_emp[emp_id], DEFAULT_RULES)
    assert row.dues_wage == D(expected["wage"])
    assert row.dues_hours == D(expected["hours"])
    assert row.computed.dues == D(expected["dues"])
    assert row.actual == D(expected["charged"])
    assert row.matches is expected["matches"]
    assert row.computed.binds == expected["binds"]


def test_the_sick_line_is_in_neither_wage_nor_hours(by_emp):
    """E01 carries 8.00 sick hours worth 200.00. Neither may appear.

    ⚠️ Asserted as an arithmetic consequence, not by reading the code map, so
    a map that said the right thing while the summation ignored it would fail.
    """
    wage, hours = dues_wage_and_hours(by_emp["E01"])
    assert wage == D("1375.00"), "the Sick amount (200.00) leaked into the dues wage"
    assert hours == D("50.00"), "the Sick hours (8.00) leaked into the dues hours"
    # and the check really does carry one, or this proves nothing
    assert any(l.code == "Sick" for l in by_emp["E01"].lines)


def test_a_salary_only_check_has_no_dues_wage_and_no_dues_hours(by_emp):
    wage, hours = dues_wage_and_hours(by_emp["E04"])
    assert (wage, hours) == (D("0"), D("0"))
    assert any(l.code == "Sal" for l in by_emp["E04"].lines)
    # The zero guard, which is the only thing making component b safe.
    assert dues_for_check(by_emp["E04"], DEFAULT_RULES).computed.dues == D("0.00")


def test_a_check_with_no_union_line_has_no_actual_dues(by_emp):
    assert actual_dues(by_emp["E02"]) == D("0")


# ── the classifier ───────────────────────────────────────────────────────────

def test_an_initiation_fee_is_classified_as_one(by_emp):
    """E03 was charged exactly 10.00 more than its lines imply."""
    row = dues_for_check(by_emp["E03"], DEFAULT_RULES)
    assert row.actual - row.computed.dues == D("10.00")
    assert classify_difference(row) == "initiation_fee"


def test_a_check_with_nothing_dues_bearing_is_classified_as_such(by_emp):
    row = dues_for_check(by_emp["E04"], DEFAULT_RULES)
    assert classify_difference(row) == "no_dues_bearing_earnings"


def test_the_initiation_fee_is_applied_only_when_the_caller_says_so(by_emp):
    """⚠️ It is NOT inferred from the register, and this pins that.

    Six checks in the measured year are exactly 10.00 high, but only 2 of the 6
    are that member's first `Union` check in the register's window — so "first
    check seen" would charge four established members a fee they already paid.
    Membership history is a people fact (Phase 4), not something a range of
    uploaded registers can be asked.
    """
    without = dues_for_check(by_emp["E03"], DEFAULT_RULES)
    with_fee = dues_for_check(by_emp["E03"], DEFAULT_RULES, apply_initiation_fee=True)
    assert with_fee.computed.dues - without.computed.dues == D("10.00")
    assert with_fee.matches, "with the fee, E03's charged figure is explained exactly"
    assert not without.matches


# ── one formula, two paths ───────────────────────────────────────────────────

def test_the_register_path_and_the_hours_path_use_the_same_formula():
    """⚠️ The thing that would be invisible for a year if it were wrong.

    Payroll 1's path derives a dues wage from hours times a typed rate; this
    one reads the amounts actually paid. Those are two ways of arriving at the
    inputs, NOT two formulas. Given the same wage and hours they must produce
    the identical DuesResult, to the cent and to the binding component.
    """
    # 40 hours at 30.00 and 7 at 45.00 — the goldens' E01 row.
    line = LineInputs(reg_hrs=D("40"), ot_hrs=D("7"))
    via_hours = compute_dues(line, D("30"), D("45"), DEFAULT_RULES)
    via_register = dues_from_wage_and_hours(
        via_hours.dues_wage, via_hours.dues_hours, DEFAULT_RULES)
    assert via_register.dues == via_hours.dues == D("21.77")
    assert via_register.component_a == via_hours.component_a
    assert via_register.component_b == via_hours.component_b
    assert via_register.component_c == via_hours.component_c
    assert via_register.binds == via_hours.binds == "b"
