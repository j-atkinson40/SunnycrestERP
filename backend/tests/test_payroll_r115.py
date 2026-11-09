"""The R-115 union remittance form — Payroll 4 Phase 6.

⚠️ **TWO REMITTANCE REPORTS EXIST ON PURPOSE** (James, 2026-11-09: keep both,
named distinctly):

    monthly_dues_remittance   from the HOURS export: dues the rules IMPLY
    union_remittance_r115     from the REGISTER: dues actually DEDUCTED

They disagree on 76 of 629 checks in a measured year. The form sent to the
union must state what was taken; the other report is how you learn whether
what was taken was right. Collapsing them would lose exactly that.

⚠️ **AND THE FILED TABLE IS A RECORD, NOT A CACHE.** Recomputing a filed
month from `payroll_checks` gives a different answer as soon as an overlapping
register is imported or a check is corrected. A form that cannot reproduce its
own filing is not evidence of a filing.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.models.payroll_report import R115_STATUSES, R115_TRANSITIONS
from app.services.payroll.reports import (
    R115Row,
    monthly_dues_remittance,
    to_csv,
    union_remittance_r115,
)

#: Hand-built from the shape the real October 2026 register has: weekly checks
#: dated the 1st, 8th, 15th, 22nd and 29th. Anonymised ids and invented money.
OCTOBER = [date(2026, 10, d) for d in (1, 8, 15, 22, 29)]


def rows(*specs):
    out = []
    for emp_id, name, dates, dues, hours in specs:
        for i, when in enumerate(dates):
            out.append(R115Row(emp_id=emp_id, display_name=name, check_date=when,
                               check_number=f"{emp_id}-{i}",
                               dues_deducted=D(dues), dues_hours=D(hours)))
    return out


@pytest.fixture
def october():
    return rows(
        ("2",  "Bravo, Ben B",   OCTOBER,          "18.00", "42.00"),
        ("10", "Juliet, Jo J",   OCTOBER,          "17.50", "40.00"),
        # A member paid only once in the month — joined, left, or on leave.
        ("7",  "Golf, Gus G",    OCTOBER[:1],      "16.25", "40.00"),
        # A check in the NEXT month must not be counted.
        ("2",  "Bravo, Ben B",   [date(2026, 11, 5)], "18.00", "42.00"),
    )


# ── the figures ──────────────────────────────────────────────────────────────

def test_the_month_totals_are_the_sum_of_what_was_deducted(october):
    table = union_remittance_r115(october, year=2026, month=10)
    # 5*18.00 + 5*17.50 + 1*16.25 = 90.00 + 87.50 + 16.25 = 193.75
    assert table.totals["dues_deducted"] == "193.75"
    assert table.totals["row_count"] == 3


def test_a_check_in_another_month_is_excluded(october):
    """⚠️ And the excluded row is visible in meta, not silently dropped."""
    table = union_remittance_r115(october, year=2026, month=10)
    assert table.meta["check_rows_considered"] == 11
    assert table.meta["check_rows_available"] == 12
    assert table.meta["check_dates_included"] == [d.isoformat() for d in OCTOBER]


def test_a_member_paid_once_appears_once(october):
    table = union_remittance_r115(october, year=2026, month=10)
    by_emp = {r["emp_id"]: r for r in table.rows}
    assert by_emp["7"]["checks"] == 1
    assert by_emp["7"]["dues_deducted"] == "16.25"
    assert by_emp["2"]["checks"] == 5


def test_employee_ids_sort_numerically(october):
    """⚠️ 10 must not come before 2 on a form somebody reads down a column."""
    table = union_remittance_r115(october, year=2026, month=10)
    assert [r["emp_id"] for r in table.rows] == ["2", "7", "10"]


def test_grouping_is_always_check_date_and_is_not_a_setting():
    """A register has a check date and no week-end date, so there is no choice.

    ⚠️ `monthly_dues_remittance` keeps the setting because its source carries
    both dates. This one states the grouping in `meta` so a stored report says
    which rule produced it.
    """
    import inspect
    assert "group_by" not in inspect.signature(union_remittance_r115).parameters
    table = union_remittance_r115([], year=2026, month=10)
    assert table.meta["group_by"] == "check_date"
    # The other report still has the setting, and still defaults as shipped.
    assert "group_by" in inspect.signature(monthly_dues_remittance).parameters


def test_a_row_with_no_check_date_is_refused_not_dropped():
    """A row that cannot be placed in a month must not vanish from a total."""
    bad = [R115Row("2", "Bravo, Ben B", None, "1", D("18.00"), D("42.00"))]
    with pytest.raises(ValueError, match="no check date"):
        union_remittance_r115(bad, year=2026, month=10)


def test_the_two_reports_are_named_distinctly(october):
    """⚠️ The ruling, asserted. One report key cannot serve both sources."""
    assert union_remittance_r115(october, year=2026, month=10).report_key == \
        "union_remittance_r115"
    assert monthly_dues_remittance([], year=2026, month=10).report_key == \
        "monthly_dues_remittance"


def test_the_report_says_where_its_figures_came_from(october):
    """A reader must not have to know which report they are holding."""
    table = union_remittance_r115(october, year=2026, month=10)
    assert "deducted" in table.meta["source"]


def test_it_exports_as_csv(october):
    csv = to_csv(union_remittance_r115(october, year=2026, month=10))
    assert "Dues deducted" in csv
    assert "193.75" in csv


# ── the status flow ──────────────────────────────────────────────────────────

def test_filed_is_terminal_by_having_no_transitions():
    """⚠️ Terminal by a MISSING MAP ENTRY, not by a branch in a function.

    A terminal state enforced by an `if` can be bypassed by whoever adds the
    next `elif`. One enforced by absence from the transition map cannot.
    """
    assert "filed" not in R115_TRANSITIONS
    assert "filed" in R115_STATUSES


def test_the_flow_goes_forward_and_allows_one_step_back_from_submitted():
    assert R115_TRANSITIONS["draft"] == ("submitted",)
    assert set(R115_TRANSITIONS["submitted"]) == {"filed", "draft"}
    # draft cannot jump straight to filed
    assert "filed" not in R115_TRANSITIONS["draft"]


def test_every_transition_target_is_a_real_status():
    """A transition to a status that does not exist would pass a check and
    then violate the database's own constraint."""
    for source, targets in R115_TRANSITIONS.items():
        assert source in R115_STATUSES, source
        for target in targets:
            assert target in R115_STATUSES, target


def test_the_advance_function_refuses_an_unknown_status():
    from app.services.payroll.r115 import R115Error, advance

    class _Form:
        status = "draft"
    with pytest.raises(R115Error, match="is not a status"):
        advance(None, _Form(), "approved")


def test_the_advance_function_refuses_a_disallowed_step():
    from app.services.payroll.r115 import R115Error, advance

    class _Form:
        status = "draft"
    with pytest.raises(R115Error, match="cannot become filed"):
        advance(None, _Form(), "filed")


def test_a_filed_form_says_it_is_terminal_rather_than_listing_nothing():
    """⚠️ The refusal has to be readable, or somebody retries it all day."""
    from app.services.payroll.r115 import R115Error, advance

    class _Form:
        status = "filed"
    with pytest.raises(R115Error, match="terminal"):
        advance(None, _Form(), "submitted")
