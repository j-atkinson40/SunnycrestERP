"""Rates, overtime checks, roster coverage and the week feed — Payroll 3 P3.

⚠️ Three of the four modules here exist to ASK QUESTIONS, not to compute
answers Bridgeable then uses. Payentry runs the payroll; its REG/OT1 split is
what people were paid. Computing the split only to COMPARE turns the same
arithmetic from an assertion into a question a person can settle.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.services.payroll.hours_parser import PAY_TYPE_TO_BUCKET
from app.services.payroll.overtime_rules import (
    AUTO_LUNCH_DEPTS,
    DAILY_OT_DEPTS,
    RULE_SOURCE,
    RULE_STATUS,
    WEEKLY_OT_DEPTS,
    check_auto_lunch,
    check_overtime_split,
)
from app.services.payroll.register_rates import (
    OT_MULTIPLIER,
    RateAt,
    rate_conflicts,
    rate_for,
    rate_history,
    rates_for_week,
)
from app.services.payroll.roster_coverage import (
    EXCUSED_STATUSES,
    REGISTERS_LOOKBACK,
    SALARY_EARNING_CODE,
    check_roster_coverage,
    hourly_people_recently_paid,
    recent_check_dates,
)


# ── small stand-ins, so these tests need no database ─────────────────────────

class _RLine:
    def __init__(self, code, hours=None, rate=None, kind="earning"):
        self.kind, self.code, self.hours, self.rate = kind, code, hours, rate
        self.amount, self.description = D("0.00"), ""


class _Check:
    def __init__(self, emp_id, when, lines):
        self.emp_id, self.check_date, self.lines = emp_id, when, lines
        self.check_number = "1"


class _HLine:
    def __init__(self, emp_id, when, pay_type, hours, home="103"):
        self.emp_id, self.work_date, self.pay_type = emp_id, when, pay_type
        self.hours, self.home_dept, self.worked_dept = D(hours), home, home
        self.name = f"Person {emp_id}"


class _Hours:
    def __init__(self, lines, listed=None):
        self.lines = lines
        self.listed_without_hours = listed or {}

    def hours_by_emp(self):
        out = {}
        for l in self.lines:
            out.setdefault(l.emp_id, {}).setdefault(l.pay_type, D(0))
            out[l.emp_id][l.pay_type] += l.hours
        return out


# ── rates from the register ──────────────────────────────────────────────────

def test_the_rate_is_the_most_recent_printed_reg_rate():
    checks = [_Check("1", date(2026, 10, 22), [_RLine("Reg", D("40"), D("26.0400"))]),
              _Check("1", date(2026, 10, 29), [_RLine("Reg", D("40"), D("30.0000"))])]
    hist = rate_history(checks)
    assert rate_for("1", date(2026, 10, 28), hist).reg_rate == D("26.0400")
    assert rate_for("1", date(2026, 11, 5), hist).reg_rate == D("30.0000")


def test_a_raise_arrives_without_anybody_typing_it():
    """⚠️ The reason rates come from the register at all.

    Twelve employees' Reg rate changed on the real 2026-10-29 check. Week 44's
    check is dated Nov 5, so the post-raise rate applies — and a
    hand-maintained table would have been wrong for twelve people that week,
    silently.
    """
    checks = [_Check("1", date(2026, 10, 22), [_RLine("Reg", D("40"), D("26.0400"))]),
              _Check("1", date(2026, 10, 29), [_RLine("Reg", D("40"), D("30.0000"))])]
    res = rates_for_week({"1"}, check_date=date(2026, 11, 5),
                         history=rate_history(checks))
    assert res.rates["1"].reg_rate == D("30.0000")
    assert res.missing == []


def test_the_rule_looks_further_back_than_the_weeks_own_check():
    """⚠️ Employee 25's real Nov 5 check prints no Reg rate — he was on
    vacation. Reading only the week's own check would make him missing_rate
    for a week he was paid at a known rate."""
    checks = [_Check("25", date(2026, 10, 29), [_RLine("Reg", D("22"), D("24.3900"))]),
              _Check("25", date(2026, 11, 5), [_RLine("Vac", D("40"))])]
    res = rates_for_week({"25"}, check_date=date(2026, 11, 5),
                         history=rate_history(checks))
    assert res.rates["25"].reg_rate == D("24.3900")


def test_the_ot_rate_is_one_and_a_half_times_and_quantized():
    assert OT_MULTIPLIER == D("1.5")
    assert RateAt(date(2026, 11, 5), D("30.0000")).ot_rate == D("45.0000")
    # ⚠️ Four decimals, not five: a Numeric(12,4) column must not be handed a
    # 5-decimal value and left to decide the rounding.
    assert RateAt(date(2026, 11, 5), D("22.3400")).ot_rate == D("33.5100")


def test_a_missing_rate_is_counted_and_never_inferred():
    """⚠️ James: "don't infer one from amount / hours without telling me how
    many." Five of thirty real employees are salaried and have no printed
    rate; amount over hours would give each of them a plausible wrong number.
    """
    checks = [_Check("15", date(2026, 11, 5), [_RLine("Sal")])]
    res = rates_for_week({"15"}, check_date=date(2026, 11, 5),
                         history=rate_history(checks))
    assert res.rates == {}
    assert res.missing == ["15"]
    assert res.missing_count == 1


def test_an_ot_line_rate_is_not_used_as_the_rate_source():
    """The register prints an OT rate too, and it is not always 1.5x."""
    checks = [_Check("1", date(2026, 11, 5),
                     [_RLine("OT", D("5"), D("99.0000"))])]
    assert rate_history(checks) == {}


def test_two_reg_rates_on_one_check_are_reported():
    checks = [_Check("1", date(2026, 11, 5),
                     [_RLine("Reg", D("20"), D("26.0400")),
                      _RLine("Reg", D("20"), D("30.0000"))])]
    conflicts = rate_conflicts(checks)
    assert conflicts == [("1", date(2026, 11, 5), [D("26.0400"), D("30.0000")])]


# ── overtime: compare, never recompute ───────────────────────────────────────

def test_the_departments_are_split_between_the_two_rules():
    assert DAILY_OT_DEPTS == {"101", "103"}
    assert WEEKLY_OT_DEPTS == {"106", "107", "108"}
    assert AUTO_LUNCH_DEPTS == {"106", "107", "108"}
    assert not (DAILY_OT_DEPTS & WEEKLY_OT_DEPTS), "a department needs one rule"


def test_a_plant_day_over_eight_hours_agrees_with_payentry():
    """9.0 worked on a Tuesday: the rule implies 1.0 OT and Payentry gave 1.0."""
    lines = [_HLine("1", date(2026, 10, 27), "REG", "8.00"),
             _HLine("1", date(2026, 10, 27), "OT1", "1.00")]
    assert check_overtime_split(_Hours(lines)) == []


def test_a_plant_day_where_payentry_disagrees_is_flagged():
    lines = [_HLine("1", date(2026, 10, 27), "REG", "9.00")]
    found = check_overtime_split(_Hours(lines))
    assert len(found) == 1
    assert found[0].rule_ot == D("1.00") and found[0].payentry_ot == D("0")
    assert found[0].status == RULE_STATUS == "from_registers"
    assert found[0].source == RULE_SOURCE


def test_every_saturday_hour_is_overtime():
    """⚠️ EVERY hour, not the hours beyond eight. 2026-10-31 is a Saturday."""
    ok = [_HLine("1", date(2026, 10, 31), "OT1", "4.00")]
    assert check_overtime_split(_Hours(ok)) == []
    bad = [_HLine("1", date(2026, 10, 31), "REG", "4.00")]
    found = check_overtime_split(_Hours(bad))
    assert len(found) == 1 and found[0].rule_ot == D("4.00")
    assert "Saturday" in found[0].rule


def test_an_office_week_over_forty_agrees_with_payentry():
    lines = [_HLine("21", date(2026, 10, 26 + i), "REG", "8.00", home="108")
             for i in range(5)]
    lines.append(_HLine("21", date(2026, 10, 30), "OT1", "2.00", home="108"))
    assert check_overtime_split(_Hours(lines)) == []


def test_pto_and_sick_do_not_earn_overtime():
    """Paid, but not worked. 40 REG + 8 Sick is not 8 hours of overtime."""
    lines = [_HLine("14", date(2026, 10, 26 + i), "REG", "8.00", home="106")
             for i in range(5)]
    lines.append(_HLine("14", date(2026, 10, 27), "Sick", "8.00", home="106"))
    assert check_overtime_split(_Hours(lines)) == []


def test_a_department_with_no_overtime_rule_is_not_checked():
    lines = [_HLine("99", date(2026, 10, 27), "REG", "14.00", home="104")]
    assert check_overtime_split(_Hours(lines)) == []


# ── the automatic lunch deduction ────────────────────────────────────────────

def test_a_nine_and_a_half_hour_office_day_without_the_deduction_is_flagged():
    """⚠️ The real case: employees 21 and 31 on 2026-10-30, both 9.50 hours
    with no -0.50 line, and both exactly 0.50 OT above the register."""
    lines = [_HLine("21", date(2026, 10, 30), "OT1", "5.50", home="108"),
             _HLine("21", date(2026, 10, 30), "REG", "4.00", home="108")]
    found = check_auto_lunch(_Hours(lines))
    assert len(found) == 1
    assert found[0].day_hours == D("9.50")


def test_a_day_that_has_the_deduction_is_not_flagged():
    """⚠️ PRESENCE, not reapplication. Payentry already printed it; applying
    another half hour would disagree with Payentry on every 9.5-hour day."""
    lines = [_HLine("21", date(2026, 10, 26), "REG", "9.50", home="108"),
             _HLine("21", date(2026, 10, 26), "REG", "-0.50", home="108")]
    assert check_auto_lunch(_Hours(lines)) == []


def test_a_plant_day_is_not_checked_for_the_lunch_deduction():
    lines = [_HLine("1", date(2026, 10, 26), "REG", "9.50", home="103")]
    assert check_auto_lunch(_Hours(lines)) == []


# ── roster coverage ──────────────────────────────────────────────────────────

def test_the_lookback_is_four_check_dates():
    # ⚠️ timedelta, not `10, 1 + 7*i` — that produced date(2026, 10, 36).
    from datetime import timedelta
    checks = [_Check("1", date(2026, 10, 1) + timedelta(days=7 * i),
                     [_RLine("Reg", D("40"), D("20"))])
              for i in range(6)]
    got = recent_check_dates(checks, before=date(2026, 11, 5))
    assert len(got) == REGISTERS_LOOKBACK == 4
    assert got[0] > got[-1], "newest first"


def test_someone_recently_paid_with_no_hours_is_flagged():
    checks = [_Check("25", date(2026, 10, 29), [_RLine("Reg", D("40"), D("24"))])]
    found = check_roster_coverage(_Hours([]), checks,
                                  week_check_date=date(2026, 11, 5))
    assert [f.emp_id for f in found] == ["25"]
    assert found[0].kind == "no_hours"


@pytest.mark.parametrize("status", sorted(EXCUSED_STATUSES))
def test_a_recorded_reason_excuses_them(status):
    checks = [_Check("29", date(2026, 10, 29), [_RLine("Reg", D("40"), D("24"))])]
    assert check_roster_coverage(_Hours([]), checks,
                                 week_check_date=date(2026, 11, 5),
                                 statuses={"29": status}) == []


def test_no_recorded_reason_is_a_question_not_an_exemption():
    """⚠️ NULL is not "working normally"."""
    checks = [_Check("29", date(2026, 10, 29), [_RLine("Reg", D("40"), D("24"))])]
    assert check_roster_coverage(_Hours([]), checks,
                                 week_check_date=date(2026, 11, 5),
                                 statuses={"29": None})


def test_a_salaried_person_is_never_expected_to_have_hours():
    """⚠️ THE FALSE POSITIVE I SHIPPED AND THEN FOUND.

    Thurston is salaried at 1,918.25 a week, and his real 2026-10-22 check
    carries a `PTO 8.00` line at $0.00. A filter that read only the earning
    CODES called him hourly and flagged him — and Payroll 4 measured 36 such
    hours-with-no-money lines across 29 checks, all salaried. So any salaried
    person who takes a day off would be flagged every week for ever.
    """
    checks = [_Check("15", date(2026, 10, 22),
                     [_RLine("Sal"), _RLine("PTO", D("8.00"))])]
    assert SALARY_EARNING_CODE == "Sal"
    assert hourly_people_recently_paid(checks, before=date(2026, 11, 5)) == set()
    assert check_roster_coverage(_Hours([]), checks,
                                 week_check_date=date(2026, 11, 5)) == []


def test_a_genuinely_hourly_person_is_still_expected():
    """A positive control: the salary exclusion must not excuse everyone."""
    checks = [_Check("25", date(2026, 10, 29), [_RLine("Reg", D("40"), D("24"))]),
              _Check("15", date(2026, 10, 29), [_RLine("Sal")])]
    assert hourly_people_recently_paid(checks, before=date(2026, 11, 5)) == {"25"}


# ── the bucket mapping ───────────────────────────────────────────────────────

def test_the_buckets_are_the_ones_calculate_week_reads():
    assert PAY_TYPE_TO_BUCKET == {"REG": "reg_hrs", "OT1": "ot_hrs",
                                  "PTO": "personal_hrs", "Sick": "sick_hrs"}
