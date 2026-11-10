"""Validating an hours import when the file validates nothing — Payroll 3.

⚠️ The identity check is the one that earns its keep. A mis-read employee
number arrives with correct hours, a correct date and a correct pay type; the
only thing wrong with it is that no such person exists. No arithmetic can see
that, which is why `test_the_identity_check_catches_a_mis_read_id` exists and
why it blocks rather than warns.
"""
from __future__ import annotations

import io
from datetime import date
from decimal import Decimal as D

import pdfplumber
import pytest

from app.services.payroll.hours_parser import parse_employee_hours
from app.services.payroll.hours_validation import (
    CHECK_LAG_DAYS,
    PAY_TYPE_TO_REGISTER_CODE,
    check_date_for_week,
    compare_with_register,
    validate_identity,
    validate_import,
    validate_week_window,
    week_bounds,
)
from tests.fixtures.payroll import build_hours_pdf as fixture

WEEK_END = date(2026, 10, 31)


@pytest.fixture(scope="module")
def parsed():
    with pdfplumber.open(io.BytesIO(fixture.build())) as pdf:
        return parse_employee_hours(pdf)


# ── the week window ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("day, start, end", [
    ("2026-10-25", "2026-10-25", "2026-10-31"),   # the Sunday itself
    ("2026-10-26", "2026-10-25", "2026-10-31"),
    ("2026-10-31", "2026-10-25", "2026-10-31"),   # the Saturday
    ("2026-11-01", "2026-11-01", "2026-11-07"),   # next Sunday starts a week
])
def test_weeks_run_sunday_to_saturday(day, start, end):
    got = week_bounds(date.fromisoformat(day))
    assert got == (date.fromisoformat(start), date.fromisoformat(end))


def test_the_check_lands_five_days_after_week_end():
    """Measured: week 44 ends Sat 2026-10-31, its checks are dated Thu Nov 5."""
    assert CHECK_LAG_DAYS == 5
    assert check_date_for_week(WEEK_END) == date(2026, 11, 5)


def test_the_right_week_passes(parsed):
    report = validate_week_window(parsed, expected_week_end=WEEK_END)
    assert report.ok, report.findings


def test_the_wrong_week_blocks(parsed):
    report = validate_week_window(parsed, expected_week_end=date(2026, 11, 7))
    assert not report.ok
    assert any(f.kind == "wrong_week" for f in report.blocking)


def test_a_sunday_with_no_hours_is_noted_and_not_blocking(parsed):
    """Normal: nobody works Sunday. A note, never a refusal."""
    report = validate_week_window(parsed, expected_week_end=WEEK_END)
    notes = [f for f in report.findings if f.kind == "days_with_no_hours"]
    assert notes and not notes[0].blocking
    assert "2026-10-25" in notes[0].detail


def test_dates_spanning_two_weeks_block(parsed):
    import copy
    from datetime import timedelta
    bad = copy.deepcopy(parsed)
    bad.lines[0].work_date = WEEK_END + timedelta(days=3)
    report = validate_week_window(bad, expected_week_end=WEEK_END)
    assert any(f.kind == "spans_more_than_one_week" for f in report.blocking)


# ── identity: the check that catches 12008 ───────────────────────────────────

def test_the_identity_check_catches_a_mis_read_id(parsed):
    """⚠️ THE POINT OF THE WHOLE MODULE.

    12008 is what a naive parse returns for employee 20. It arrives with
    correct hours on a correct date with a correct pay type. The ONLY thing
    that can reject it is a roster that has never heard of it.
    """
    import copy
    bad = copy.deepcopy(parsed)
    for line in bad.lines:
        if line.emp_id == "20":
            line.emp_id = "12008"
    bad.names_by_emp["12008"] = bad.names_by_emp.pop("20")

    known = fixture.EXPECTED_EMP_IDS                       # the real roster
    report = validate_identity(bad, known_emp_ids=known)
    assert not report.ok, "a non-existent employee id was accepted"
    blocked = report.blocking[0]
    assert blocked.kind == "unknown_emp_id"
    assert "12008" in blocked.detail

    # ⚠️ And the control: the same file with the id read correctly passes.
    assert validate_identity(parsed, known_emp_ids=known).ok


def test_an_unknown_id_blocks_rather_than_warns(parsed):
    report = validate_identity(parsed, known_emp_ids={"36"})
    assert not report.ok
    assert all(f.blocking for f in report.findings if f.kind == "unknown_emp_id")


def test_one_id_under_two_names_blocks(parsed):
    import copy
    bad = copy.deepcopy(parsed)
    bad.names_by_emp["36"] = {"Bravo, Ben", "Bravo, Benjamin"}
    report = validate_identity(bad, known_emp_ids=fixture.EXPECTED_EMP_IDS)
    assert any(f.kind == "one_id_two_names" for f in report.blocking)


def test_a_name_only_person_still_has_to_be_known(parsed):
    """⚠️ Being listed with no hours does not exempt an id.

    Measured on the real export: employee 38 is listed with no hours and does
    NOT appear anywhere in a year of registers, so the check blocks until
    somebody adds her to the roster. That is the intended behaviour — an id
    nobody can account for is exactly what this refuses.
    """
    assert "38" in parsed.emp_ids
    assert "38" in parsed.listed_without_hours
    report = validate_identity(parsed, known_emp_ids=fixture.EXPECTED_EMP_IDS - {"38"})
    assert any("38" in f.detail for f in report.blocking)


# ── against the register ─────────────────────────────────────────────────────

class _Line:
    def __init__(self, code, hours):
        self.kind, self.code, self.hours = "earning", code, D(hours)
        self.amount, self.rate, self.description = D("0.00"), None, ""


class _Check:
    def __init__(self, emp_id, when, lines):
        self.emp_id, self.check_date, self.lines = emp_id, when, lines
        self.check_number = "1"


def test_matching_hours_agree(parsed):
    checks = [_Check("36", date(2026, 11, 5),
                     [_Line("Reg", "24.00"), _Line("OT", "1.08")])]
    rows, report = compare_with_register(parsed, checks, week_end=WEEK_END)
    agree = {(r.emp_id, r.pay_type): r.agrees for r in rows}
    assert agree[("36", "REG")] and agree[("36", "OT1")]
    assert not [f for f in report.findings
                if f.kind == "hours_differ_from_register" and " 36 " in f.detail]


def test_a_difference_is_reported_with_both_figures(parsed):
    checks = [_Check("36", date(2026, 11, 5),
                     [_Line("Reg", "24.00"), _Line("OT", "1.07")])]
    _rows, report = compare_with_register(parsed, checks, week_end=WEEK_END)
    # ⚠️ Select the finding under test rather than taking the first one. The
    # fixture has other employees with no check at all, so they differ too —
    # my first version asserted on diffs[0] and read emp 14's REG row.
    diffs = [f for f in report.findings
             if f.kind == "hours_differ_from_register" and "emp 36 OT1" in f.detail]
    assert diffs, [f.detail for f in report.findings]
    assert "1.08" in diffs[0].detail and "1.07" in diffs[0].detail

def test_a_register_difference_never_blocks(parsed):
    """⚠️ Reported, not blocking, and deliberately.

    Payroll 4 measured 76 checks in a year where computed and charged dues
    differ for reasons nobody has settled. Blocking an import on an hours
    difference would block every import.
    """
    checks = [_Check("36", date(2026, 11, 5), [_Line("Reg", "0.00")])]
    _rows, report = compare_with_register(parsed, checks, week_end=WEEK_END)
    assert report.ok
    assert report.findings


def test_only_the_weeks_own_check_is_compared(parsed):
    """A check five days late belongs to this week; any other does not."""
    checks = [_Check("36", date(2026, 10, 29), [_Line("Reg", "24.00")])]
    rows, report = compare_with_register(parsed, checks, week_end=WEEK_END)
    assert rows == []
    assert any(f.kind == "no_check_for_week" for f in report.findings)


def test_the_pay_type_map_covers_every_known_type():
    from app.services.payroll.hours_parser import KNOWN_PAY_TYPES
    assert set(PAY_TYPE_TO_REGISTER_CODE) == KNOWN_PAY_TYPES


# ── the whole gate ───────────────────────────────────────────────────────────

def test_validate_import_blocks_before_it_compares(parsed):
    """⚠️ Order: a blocked import must not also emit a wall of hour
    differences nobody should act on yet."""
    checks = [_Check("36", date(2026, 11, 5), [_Line("Reg", "0.00")])]
    report = validate_import(parsed, expected_week_end=WEEK_END,
                             known_emp_ids={"36"}, checks=checks)
    assert not report.ok
    assert not [f for f in report.findings if f.kind == "hours_differ_from_register"]


def test_validate_import_passes_a_clean_week(parsed):
    report = validate_import(parsed, expected_week_end=WEEK_END,
                             known_emp_ids=fixture.EXPECTED_EMP_IDS)
    assert report.ok, [f.detail for f in report.blocking]


def test_unreadable_rows_block(parsed):
    import copy
    bad = copy.deepcopy(parsed)
    bad.unreadable_rows = [(2, "Someone, Unparseable [ ??]")]
    report = validate_import(bad, expected_week_end=WEEK_END,
                             known_emp_ids=fixture.EXPECTED_EMP_IDS)
    assert any(f.kind == "unreadable_row" for f in report.blocking)
