"""Saturday, hourly-vs-salaried, and the week's findings — Payroll 3 follow-up.

Three fixes, each for a defect that was shipped and then found:

  * the clustered-departure detector called a short SATURDAY a finding;
  * two different checks each had their own idea of "hourly" and both read an
    hours-bearing line as evidence of it;
  * the rate resolver reported a salaried person as `missing_rate`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal as D

import pytest

from app.services.payroll.employment import (
    HOURLY,
    LOOKBACK_CHECKS,
    SALARIED,
    UNKNOWN,
    classify_employment,
)
from app.services.payroll.punch_findings import (
    SHIFT_WEEKDAYS,
    all_findings,
    find_clustered_early_departures,
    find_early_clock_ins,
    find_saturday_work,
    has_regular_shift,
)
from app.services.payroll.punch_parser import DayPunches, Punch
from app.services.payroll.register_rates import rate_history, rates_for_week
from app.services.payroll.roster_coverage import (
    check_roster_coverage,
    hourly_people_recently_paid,
)
from app.services.payroll.week_findings import (
    dues_difference_findings,
    dues_without_earnings_findings,
    lunch_deduction_findings,
)


class _Line:
    def __init__(self, code, hours=None, rate=None, amount="0.00", kind="earning"):
        self.kind, self.code, self.hours, self.rate = kind, code, hours, rate
        self.amount, self.description = D(amount), ""


class _Check:
    def __init__(self, emp_id, when, lines):
        self.emp_id, self.check_date, self.lines = emp_id, when, lines
        self.check_number, self.person = "1", f"Person, {emp_id}"


def _punch(name, when, hhmm, dept="[103] Production"):
    h, m = (int(x) for x in hhmm.split(":"))
    return Punch(name=name, dept=dept, punch_at=datetime.combine(when, datetime.min.time())
                 .replace(hour=h, minute=m), has_location=False, origin="Kiosk")


def _day(name, when, in_at, out_at, dept="[103] Production"):
    d = DayPunches(name=name, on_date=when)
    d.pairs.append((_punch(name, when, in_at, dept), _punch(name, when, out_at, dept)))
    return d


SAT = date(2026, 10, 31)      # Saturday
THU = date(2026, 10, 29)      # Thursday
SUN = date(2026, 10, 25)      # Sunday


# ── Saturday ─────────────────────────────────────────────────────────────────

def test_the_shift_rule_describes_monday_to_friday_only():
    assert SHIFT_WEEKDAYS == {0, 1, 2, 3, 4}
    assert has_regular_shift(THU)
    assert not has_regular_shift(SAT)
    assert not has_regular_shift(SUN)


def test_a_short_saturday_is_not_an_early_departure():
    """⚠️ THE FIX. Four people left from 10:53 on the real Saturday 2026-10-31
    and the detector called it a finding. Every Saturday hour is overtime and a
    short Saturday is what a short Saturday looks like."""
    days = [_day("Alpha, Ann", SAT, "06:00", "10:53"),
            _day("Bravo, Ben", SAT, "06:00", "10:58")]
    assert find_clustered_early_departures(days) == []
    assert not [f for f in all_findings(days)
                if f.kind == "clustered_early_departure"]


def test_clocking_in_early_on_a_saturday_is_not_a_finding():
    days = [_day("Alpha, Ann", SAT, "05:30", "10:00")]
    assert find_early_clock_ins(days) == []


def test_the_same_pattern_on_a_thursday_still_is_a_finding():
    """⚠️ A positive control. The Saturday exemption must not switch the
    detectors off altogether."""
    days = [_day("Alpha, Ann", THU, "06:00", "14:00"),
            _day("Bravo, Ben", THU, "06:00", "14:06")]
    assert len(find_clustered_early_departures(days)) == 1
    assert len(find_early_clock_ins(days)) == 2


def test_saturday_hours_are_reported_as_overtime_worked():
    days = [_day("Alpha, Ann", SAT, "06:00", "10:12")]
    found = find_saturday_work(days)
    assert len(found) == 1
    assert found[0].kind == "saturday_overtime_worked"
    assert "4.20 hours" in found[0].detail
    assert "overtime" in found[0].detail


def test_a_weekday_produces_no_saturday_finding():
    assert find_saturday_work([_day("Alpha, Ann", THU, "06:00", "15:30")]) == []


def test_saturday_work_is_reported_for_a_department_with_no_shift_rule():
    """Hours worked are a fact and need no rule to interpret."""
    days = [_day("Golf, Gus", SAT, "08:00", "12:00", dept="[107] Office")]
    assert len(find_saturday_work(days)) == 1


# ── hourly or salaried ───────────────────────────────────────────────────────

def test_a_sal_line_means_salaried():
    checks = [_Check("15", date(2026, 10, 29), [_Line("Sal", amount="1918.25")])]
    got = classify_employment(checks, before=date(2026, 11, 5))
    assert got["15"].kind == SALARIED


def test_a_reg_line_with_a_printed_rate_means_hourly():
    checks = [_Check("1", date(2026, 10, 29),
                     [_Line("Reg", D("40"), D("30.0000"), "1200.00")])]
    got = classify_employment(checks, before=date(2026, 11, 5))
    assert got["1"].kind == HOURLY


def test_hours_only_zero_dollar_lines_never_make_anyone_hourly():
    """⚠️ THE RULE JAMES STATED, AND THE DEFECT IT CLOSES.

    Thurston's real 2026-10-22 check carries `PTO 8.00` at $0.00 beside his
    salary. Payroll 4 measured 36 such hours-with-no-money lines across 29
    checks, every one on a salaried person's check. A filter that read the
    CODES called him hourly and the coverage check flagged him.
    """
    checks = [_Check("15", date(2026, 10, 22),
                     [_Line("Sal", amount="1918.25"), _Line("PTO", D("8.00"))])]
    got = classify_employment(checks, before=date(2026, 11, 5))
    assert got["15"].kind == SALARIED
    # and without the salary line it is still not hourly: no rated Reg line
    only_pto = [_Check("99", date(2026, 10, 22), [_Line("PTO", D("8.00"))])]
    assert classify_employment(only_pto, before=date(2026, 11, 5))["99"].kind == UNKNOWN


def test_a_reg_line_with_no_printed_rate_is_not_enough():
    checks = [_Check("99", date(2026, 10, 29), [_Line("Reg", D("40"))])]
    assert classify_employment(checks, before=date(2026, 11, 5))["99"].kind == UNKNOWN


def test_salary_wins_when_both_appear():
    checks = [_Check("15", date(2026, 10, 29),
                     [_Line("Sal", amount="1900.00"),
                      _Line("Reg", D("4"), D("20.0000"), "80.00")])]
    assert classify_employment(checks, before=date(2026, 11, 5))["15"].kind == SALARIED


def test_the_window_is_the_employees_own_last_four_checks():
    """⚠️ Per employee, not global.

    Staring's last check is months old. A global window would classify him
    `unknown` and then exempt him from everything.
    """
    old = [_Check("29", date(2026, 7, 1) + timedelta(days=7 * i),
                  [_Line("Reg", D("40"), D("21.0000"), "840.00")])
           for i in range(4)]
    got = classify_employment(old, before=date(2026, 11, 5))
    assert got["29"].kind == HOURLY
    assert LOOKBACK_CHECKS == 4


# ── the coverage regression this follow-up nearly shipped ────────────────────

def test_coverage_needs_recently_paid_AND_hourly():
    """⚠️ THE REGRESSION I CAUGHT BEFORE COMMITTING.

    Delegating wholesale to `classify_employment` made coverage flag 8 people
    instead of 1 — including Staring, whom James said must NEVER be flagged —
    because a permanently-hourly person who has not been paid for a month is
    still hourly. The two windows answer different questions and are composed,
    not conflated.
    """
    # ⚠️ FOUR recent check dates, because the window IS the last four. My
    # first version gave the fixture only two dates in total, so "the last
    # four" included the stale one and the test failed for its own reasons
    # rather than the code's.
    recent = [date(2026, 10, 15), date(2026, 10, 22),
              date(2026, 10, 29), date(2026, 11, 5)]
    stale = date(2026, 7, 1)
    checks = [_Check("25", d, [_Line("Reg", D("40"), D("24.0000"), "960.00")])
              for d in recent]
    checks.append(
        _Check("29", stale, [_Line("Reg", D("40"), D("21.0000"), "840.00")]))
    paid = hourly_people_recently_paid(checks, before=date(2026, 11, 5))
    assert paid == {"25"}, paid
    assert "29" not in paid, "Staring must not be in the recent window"

    class _H:
        lines = []
        listed_without_hours = {}
        def hours_by_emp(self):  # noqa: D102
            return {}
    flagged = [f.emp_id for f in check_roster_coverage(
        _H(), checks, week_check_date=date(2026, 11, 5))]
    assert flagged == ["25"], flagged


# ── a salaried person is not missing_rate ────────────────────────────────────

def test_a_salaried_person_is_not_reported_as_missing_a_rate():
    """⚠️ Employee 22 was the only "missing" rate in week 44, and he is
    salaried. Reporting it as missing data sends somebody looking for a number
    that does not exist."""
    checks = [_Check("22", date(2026, 10, 29), [_Line("Sal", amount="1200.00")])]
    employment = classify_employment(checks, before=date(2026, 11, 5))
    res = rates_for_week({"22"}, check_date=date(2026, 11, 5),
                         history=rate_history(checks), employment=employment)
    assert res.missing == []
    assert res.salaried == ["22"]
    assert res.missing_count == 0


def test_an_hourly_person_with_no_rate_is_still_missing():
    """⚠️ A positive control: the exemption must not swallow a real gap."""
    checks = [_Check("99", date(2026, 10, 29), [_Line("Reg", D("40"))])]
    employment = classify_employment(checks, before=date(2026, 11, 5))
    res = rates_for_week({"99"}, check_date=date(2026, 11, 5),
                         history=rate_history(checks), employment=employment)
    assert res.missing == ["99"]


def test_without_an_employment_map_the_old_behaviour_holds():
    """Additive argument: omitting it must not silently change anything."""
    checks = [_Check("22", date(2026, 10, 29), [_Line("Sal", amount="1200.00")])]
    res = rates_for_week({"22"}, check_date=date(2026, 11, 5),
                         history=rate_history(checks))
    assert res.missing == ["22"] and res.salaried == []


# ── the findings list ────────────────────────────────────────────────────────

def test_the_lunch_finding_names_both_people_and_asks():
    class _F:
        def __init__(self, emp_id):
            self.emp_id, self.on_date, self.day_hours = emp_id, date(2026,10,30), D("9.50")
            self.dept, self.detail = "108", ""
    out = lunch_deduction_findings([_F("21"), _F("31")],
                                   names={"21": "Levine", "31": "McAuliffe"})
    assert len(out) == 1
    assert "Levine (21)" in out[0].line and "McAuliffe (31)" in out[0].line
    assert out[0].line.rstrip().endswith("?"), "a finding is a question"
    assert "0.50" in out[0].line


def test_dues_without_earnings_finds_the_stevenson_shape():
    checks = [_Check("25", date(2026, 11, 5),
                     [_Line("Union", amount="16.05", kind="deduction")])]
    out = dues_without_earnings_findings(checks, week_check_date=date(2026, 11, 5),
                                         hours_emp_ids=set(), names={"25": "Stevenson"})
    assert len(out) == 1
    assert "16.05" in out[0].line and "no earnings" in out[0].line
    assert out[0].line.rstrip().endswith("?")


def test_a_check_with_earnings_is_not_that_finding():
    checks = [_Check("1", date(2026, 11, 5),
                     [_Line("Reg", D("40"), D("30"), "1200.00"),
                      _Line("Union", amount="21.77", kind="deduction")])]
    assert dues_without_earnings_findings(
        checks, week_check_date=date(2026, 11, 5),
        hours_emp_ids={"1"}, names={}) == []


def test_a_dues_difference_line_carries_both_figures():
    out = dues_difference_findings([("3", D("18.84"), D("18.68"), None)],
                                   names={"3": "Skutt"})
    assert "18.84" in out[0].line and "18.68" in out[0].line and "0.16" in out[0].line


def test_an_untested_cause_is_called_unexplained():
    """⚠️ A cause is named only when it has been tested.

    Two were tested against week 44 and disproved; the line says so rather
    than offering the most plausible-sounding story.
    """
    out = dues_difference_findings([("3", D("18.84"), D("18.68"), None)], names={})
    assert "Unexplained" in out[0].line
    assert "pre-raise" in out[0].line
    assert out[0].cause is None


def test_a_tested_cause_is_stated():
    out = dues_difference_findings(
        [("5", D("13.39"), D("23.39"), "an initiation fee")], names={})
    assert "Most likely an initiation fee" in out[0].line
    assert out[0].cause == "an initiation fee"


# ── why the dues differ: settled 2026-11-10 ──────────────────────────────────
#
# ⚠️ **PAYENTRY DOES NOT CALCULATE DUES. IT DEDUCTS WHAT THE ACCOUNTANT TYPES
# IN FROM HER WORKBOOK.** That one fact explains all eight differences, and it
# is why the first two hypotheses failed: both assumed Payentry was computing
# something. The tests below need no real file, because the workbook's week-44
# figures are already in the repository as the spec's golden table.


def test_the_workbook_golden_explains_skutts_dues():
    """⚠️ THE WHOLE MECHANISM, FROM COMMITTED DATA ONLY.

    Golden row E02 is Skutt: 40 regular and 12.8 overtime hours, his CURRENT
    rate of 24.54, and a typed overtime rate of 35.835 — which is 1.5 x 23.89,
    his rate BEFORE the October raise. 1.5 x his current rate would be 36.81.

    So the workbook pays his regular hours at the new rate and his overtime at
    the old one, and its dues figure is 18.68. Payentry deducted 18.68. We
    calculate 18.84. The difference is the stale rate and nothing else.
    """
    from app.services.payroll.engine import LineInputs, compute_dues
    from app.services.payroll.rules import DEFAULT_RULES
    from app.services.payroll.week_findings import (
        TYPED_FROM_WORKBOOK,
        explain_dues_difference,
    )
    from tests.test_payroll_dues_golden import GOLDEN

    row = next(r for r in GOLDEN if r[0] == "E02")
    reg_h, ot_h, reg_rate, typed_ot, workbook_dues = (
        D(row[1]), D(row[3]), D(row[4]), D(row[5]), D(row[11]))
    assert typed_ot == (D("23.89") * D("1.5")).quantize(D("0.001")), (
        "E02's typed overtime rate should be 1.5x the PRE-raise 23.89")
    current_ot = (reg_rate * D("1.5")).quantize(D("0.0001"))
    assert current_ot == D("36.8100")

    line = LineInputs(reg_hrs=reg_h, ot_hrs=ot_h)

    def recompute(ot_rate):
        return compute_dues(line, reg_rate, ot_rate, DEFAULT_RULES).dues

    ours = recompute(current_ot)
    assert ours == D("18.84")
    assert recompute(typed_ot) == workbook_dues == D("18.68")

    cause = explain_dues_difference(
        emp_id="3", ours=ours, payentry=workbook_dues, recompute=recompute,
        current_ot_rate=current_ot, stale_ot_rate=typed_ot)
    assert cause.explained
    assert cause.cause == TYPED_FROM_WORKBOOK
    assert cause.workbook_ot_rate == typed_ot


def test_the_three_that_agree_have_an_updated_workbook_rate():
    """⚠️ The other half of the explanation, and it is what makes it credible.

    Twelve people were raised. Three had their workbook overtime rate updated
    to 1.5x the NEW rate, and those three are exactly the three whose dues
    agree with ours. If the workbook's rates were uniformly stale, every member
    would differ — and they do not.
    """
    from tests.test_payroll_dues_golden import GOLDEN

    for gid, reg_rate, typed_ot in (("E01", "30", "45"),
                                    ("E03", "24.39", "36.585"),
                                    ("E06", "24.39", "36.585")):
        row = next(r for r in GOLDEN if r[0] == gid)
        assert row[4] == reg_rate and row[5] == typed_ot, row
        assert D(row[5]) == (D(row[4]) * D("1.5")).quantize(D("0.001")), (
            f"{gid}'s typed overtime rate is 1.5x its CURRENT rate")


def test_a_cause_is_not_claimed_unless_the_recomputation_lands_exactly():
    """⚠️ "Close enough" would send Susan to fix a rate that was not the
    problem."""
    from app.services.payroll.week_findings import explain_dues_difference

    cause = explain_dues_difference(
        emp_id="9", ours=D("20.00"), payentry=D("19.00"),
        recompute=lambda ot: D("19.50"),          # never reaches 19.00
        current_ot_rate=D("30.0000"), stale_ot_rate=D("28.0000"))
    assert not cause.explained and cause.cause is None


def test_no_difference_means_no_cause_and_no_finding():
    from app.services.payroll.week_findings import (
        dues_cause_findings,
        explain_dues_difference,
    )

    same = explain_dues_difference(
        emp_id="1", ours=D("21.77"), payentry=D("21.77"),
        recompute=lambda ot: D("21.77"),
        current_ot_rate=D("45.0000"), stale_ot_rate=D("39.0600"))
    assert not same.explained
    assert dues_cause_findings([same]) == []


def test_an_identical_stale_rate_cannot_explain_anything():
    """If the workbook's rate equals the current one, it is not the cause."""
    from app.services.payroll.week_findings import explain_dues_difference

    cause = explain_dues_difference(
        emp_id="9", ours=D("20.00"), payentry=D("19.00"),
        recompute=lambda ot: D("19.00"),
        current_ot_rate=D("30.0000"), stale_ot_rate=D("30.0000"))
    assert not cause.explained


def test_the_finding_names_the_remedy():
    from app.services.payroll.week_findings import (
        dues_cause_findings,
        explain_dues_difference,
    )

    cause = explain_dues_difference(
        emp_id="3", ours=D("18.84"), payentry=D("18.68"),
        recompute=lambda ot: D("18.68") if ot == D("35.8350") else D("18.84"),
        current_ot_rate=D("36.8100"), stale_ot_rate=D("35.8350"))
    line = dues_cause_findings([cause], names={"3": "Skutt"})[0].line
    assert "35.8350" in line and "36.8100" in line
    assert "workbook" in line
    assert "Updating that rate would close it" in line
