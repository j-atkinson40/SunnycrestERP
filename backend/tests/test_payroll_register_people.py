"""People facts the register establishes — Payroll 4 Phase 4.

⚠️ **THE RULE THIS FILE EXISTS TO HOLD: PROPOSE, NEVER OVERWRITE.** Every fact
here is one somebody may have curated by hand. An importer that wrote its
findings straight onto the roster would quietly undo that work, and the only
record of what was lost would be whichever register it happened to read last.
"""
from __future__ import annotations

import io
from datetime import date
from decimal import Decimal as D

import pdfplumber
import pytest

from app.services.payroll.register_parser import parse_register
from app.services.payroll.register_people import (
    Proposal,
    _is_unset,
    observed_facts,
)
from app.services.payroll.rules import DEFAULT_RULES
from tests.fixtures.payroll import register_fixture


@pytest.fixture(scope="module")
def checks():
    with pdfplumber.open(io.BytesIO(register_fixture.build())) as pdf:
        return parse_register(pdf).checks


@pytest.fixture(scope="module")
def facts(checks):
    return observed_facts(checks, lambda when: DEFAULT_RULES)


# ── what the register establishes ────────────────────────────────────────────

def test_every_paid_employee_is_seen(facts):
    assert set(facts) == register_fixture.EXPECTED_PEOPLE


def test_union_membership_is_proved_by_a_dues_line(facts):
    proved = {e for e, f in facts.items() if f["is_union_member"]}
    assert proved == register_fixture.EXPECTED_UNION_PEOPLE
    # E02 has no Union line, so membership is not proved — which is NOT the
    # same as proved false. See the upward-only test below.
    assert "E02" not in proved


def test_one_display_name_per_employee(facts):
    for emp_id, expected in register_fixture.EXPECTED_DISPLAY_NAMES.items():
        assert facts[emp_id]["display_name"] == expected
    assert all(len(f["name_candidates"]) == 1 for f in facts.values())


def test_the_initiation_fee_date_is_the_check_that_shows_the_gap(facts):
    """E03 was charged exactly 10.00 more than its pay lines imply."""
    assert facts["E03"]["initiation_fee_paid_date"] == date(2025, 11, 13)
    assert facts["E03"]["fee_dates_seen"] == [date(2025, 11, 13)]


def test_no_fee_is_invented_for_a_member_who_shows_none(facts):
    """⚠️ A positive control on the test above.

    If the detector fired on any dues gap rather than on exactly the fee, E01
    (which matches to the cent) and E04 (whose gap is 45.00) would both get a
    date, and the field would be meaningless.
    """
    assert facts["E01"]["initiation_fee_paid_date"] is None
    assert facts["E04"]["initiation_fee_paid_date"] is None


class _Line:
    def __init__(self, kind, code, amount, hours=None):
        self.kind, self.code, self.amount, self.hours = kind, code, amount, hours
        self.rate, self.description = None, ""


class _Check:
    """The smallest thing `observed_facts` can read. Two DIFFERENT dates."""

    def __init__(self, emp_id, when, dues):
        self.emp_id, self.check_date, self.person = emp_id, when, "Alpha, Ann A"
        self.check_number = "1"
        self.lines = [
            _Line("earning", "Reg", D("1000.00"), D("40.00")),
            _Line("deduction", "Union", dues),
        ]


def test_the_rules_are_resolved_per_check_date():
    """⚠️ The rulebook is effective-dated and a register spans a year.

    Asking "is this gap the fee" with one rule set would use the wrong fee for
    every check on the other side of a rule change.

    ⚠️ **THIS USES PURPOSE-BUILT CHECKS, NOT THE FIXTURE, AND THAT IS THE
    POINT.** Every check in the fixture falls on one date, so against it a
    resolver called once with `min(dates)` is indistinguishable from one called
    per check — the first version of this test passed with the per-date lookup
    deliberately broken. Two different dates are the minimum that can tell them
    apart.
    """
    seen: list[date] = []

    def resolver(when):
        seen.append(when)
        return DEFAULT_RULES

    early, late = date(2026, 1, 5), date(2026, 9, 7)
    observed_facts([_Check("E01", early, D("14.40")),
                    _Check("E01", late, D("14.40"))], resolver)
    assert seen, "the resolver was never called — the rules are not per-date"
    assert set(seen) == {early, late}, (
        f"the resolver saw {sorted(set(seen))}, not both check dates — the "
        "rules are being resolved once rather than per check"
    )


# ── the unset rule, which has bitten this codebase before ───────────────────

@pytest.mark.parametrize("value, expected", [
    (None, True),
    ("", True),
    ("   ", True),
    # ⚠️ EVERY ONE OF THESE IS A REAL ANSWER, NOT AN ABSENCE. Deciding by
    # truthiness would treat them as unset and let the register overwrite a
    # deliberate `False` — the null-versus-empty inversion again.
    (False, False),
    (0, False),
    (D("0.00"), False),
    ([], False),
    ("Alpha, Ann A", False),
    (True, False),
])
def test_unset_is_decided_by_identity_not_truthiness(value, expected):
    assert _is_unset(value) is expected


# ── propose, never overwrite ────────────────────────────────────────────────

def test_a_fill_is_applicable_and_a_conflict_is_not():
    fill = Proposal("E01", "display_name", "A", None, "fill", "nothing recorded")
    agree = Proposal("E01", "display_name", "A", "A", "agree", "already says so")
    clash = Proposal("E01", "display_name", "A", "B", "conflict", "disagree")
    assert fill.applicable
    assert not agree.applicable
    assert not clash.applicable


def test_union_membership_only_ever_fills_upward():
    """⚠️ A dues line PROVES membership; its absence disproves nothing.

    A member on leave, between vacation entitlements, or simply not paid inside
    the uploaded range has no dues line to show. If absence were treated as
    evidence, re-importing a short register would un-member half the roster —
    and the reconciliation would look like it had tidied something up.

    Asserted on the reconciliation logic's own shape: the register never
    produces `is_union_member = False` as a thing to write.
    """
    from app.services.payroll.register_people import reconcile
    import inspect

    source = inspect.getsource(reconcile)
    assert 'field == "is_union_member" and register_says is True' in source, (
        "the upward-only guard is gone from reconcile(); absence of a dues "
        "line must never be written as non-membership"
    )


def test_nothing_derivable_from_the_checks_is_copied_onto_the_roster():
    """⚠️ No second copy of any fact (James, 2026-11-09).

    First check date, check count and total dues paid are all one query away
    from `payroll_checks`. Copying them to the roster would create two answers
    to the same question, and the stale one would win whenever the import did
    not run.
    """
    from app.models.payroll_report import PayrollReportEmployee

    columns = set(PayrollReportEmployee.__table__.columns.keys())
    forbidden = {"first_check_date", "last_check_date", "check_count",
                 "total_dues_paid", "total_wage", "ytd_dues"}
    assert not (columns & forbidden), (
        f"these are derivable from payroll_checks and must not be stored: "
        f"{sorted(columns & forbidden)}"
    )


def test_the_fee_paid_date_is_distinct_from_the_fee_due_flag():
    """Two different facts, deliberately. Not a duplicate pair.

    `initiation_fee_due` is forward-looking — charge a fee next time dues
    arise. `initiation_fee_paid_date` is historical. Phase 2 needed the second
    and had only the first, which is why it could not decide the fee at all.
    """
    from app.models.payroll_report import PayrollReportEmployee

    columns = PayrollReportEmployee.__table__.columns
    assert "initiation_fee_due" in columns
    assert "initiation_fee_paid_date" in columns
    # NULL means "not established", not "never paid one".
    assert columns["initiation_fee_paid_date"].nullable
