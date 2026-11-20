"""Line 1 — who is in the bargaining unit for a month.

⚠️ **THE ROSTER FLAG IS NOT THE ANSWER, AND THE FIRST VERSION USED IT.**
`is_union_member` is set by the reconcile for anyone who had dues at any point
in the year, so Sunnycrest's roster carries **18** while October's unit was
**13**. The difference is four people who had already left and one member on
workers' comp.

⚠️ **AND THE RULE AS FIRST WORDED MISSED THE GOLDEN BY ONE.** "Union members
with a payroll status active during the month (not left before it started)"
keeps a member on comp and gives 14. Measured against the shape below, then
ruled 2026-11-18: workers' comp and leave are outside the unit for the month.
Both numbers are asserted here, so the ruling cannot be reversed silently.

The shape reproduces the live October: 18 union members, 13 paying dues on
every check date, 4 who left in August, and Staring on workers' comp with
October checks and no dues line.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from app.services.payroll import r115_form
from app.services.payroll.r115_schedule import check_dates_in
from app.services.payroll.rules import DEFAULT_RULES
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

YEAR, MONTH = 2026, 10
OCTOBER = check_dates_in(YEAR, MONTH)


@pytest.fixture
def sunnycrest_shape():
    """18 union members as the reconcile leaves them, with real statuses."""
    from app.database import SessionLocal
    from app.models.payroll_report import (
        PayrollCheck,
        PayrollCheckLine,
        PayrollReportEmployee,
    )

    db = SessionLocal()
    emps: list[str] = []
    chks: list[str] = []

    def member(fn, name, status=None, since=None):
        e = PayrollReportEmployee(
            id=str(uuid.uuid4()), tenant_id=TESTCO_ID,
            payentry_file_number=fn, display_name=name, is_union_member=True,
            payroll_status=status, payroll_status_since=since)
        db.add(e)
        emps.append(e.id)

    def paid(fn, dates, dues="15.30"):
        for i, when in enumerate(dates):
            cid = str(uuid.uuid4())
            chks.append(cid)
            db.add(PayrollCheck(id=cid, tenant_id=TESTCO_ID, emp_id=fn,
                                person=fn, check_number=f"L1-{fn}-{i}",
                                check_date=when, source_page=0))
            db.add(PayrollCheckLine(
                id=str(uuid.uuid4()), tenant_id=TESTCO_ID, check_id=cid,
                kind="earning", code="Reg", hours=D("40.00"),
                amount=D("1000.00")))
            if dues:
                db.add(PayrollCheckLine(
                    id=str(uuid.uuid4()), tenant_id=TESTCO_ID, check_id=cid,
                    kind="deduction", code="Union", amount=D(dues)))

    try:
        # ⚠️ **THIS MONTH IS OWNED BY THIS FIXTURE, NOT INHERITED.** The
        # walk-through seed writes register checks into the same tenant and
        # the same derived month, so a total asserted here was silently the
        # sum of both — 394.25 where the arithmetic said 180.00. A test that
        # asserts on a month's figures must establish that month's contents.
        # The walk re-seeds its own rows before it runs.
        db.execute(text("DELETE FROM payroll_check_lines WHERE check_id IN "
                        "(SELECT id FROM payroll_checks WHERE tenant_id=:t "
                        " AND extract(year from check_date)=:y "
                        " AND extract(month from check_date)=:m)"),
                   {"t": TESTCO_ID, "y": YEAR, "m": MONTH})
        db.execute(text("DELETE FROM payroll_checks WHERE tenant_id=:t "
                        "AND extract(year from check_date)=:y "
                        "AND extract(month from check_date)=:m"),
                   {"t": TESTCO_ID, "y": YEAR, "m": MONTH})
        # ⚠️ And the ROSTER, for the same reason: line 1 counts union
        # members for the tenant, so the walk seed's four would be added to
        # this fixture's eighteen.
        db.execute(text("DELETE FROM payroll_rates WHERE employee_id IN "
                        "(SELECT id FROM payroll_report_employees WHERE tenant_id=:t)"),
                   {"t": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_report_employees WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        for n in range(1, 14):
            member(f"L1-{n:02d}", f"Member {n}")
            paid(f"L1-{n:02d}", OCTOBER)
        for n in range(14, 18):
            member(f"L1-{n:02d}", f"Leaver {n}", "left", date(2026, 8, 15))
        # ⚠️ Checks but NO dues line — paid while on comp, nothing remitted.
        # This is what makes him invisible to line 2 and visible to line 1.
        member("L1-18", "Staring", "workers_comp", date(2026, 10, 8))
        paid("L1-18", OCTOBER[1:], dues=None)
        db.commit()
        yield db
    finally:
        if chks:
            db.execute(text("DELETE FROM payroll_check_lines "
                            "WHERE check_id = ANY(:i)"), {"i": chks})
            db.execute(text("DELETE FROM payroll_checks WHERE id = ANY(:i)"),
                       {"i": chks})
        if emps:
            db.execute(text("DELETE FROM payroll_report_employees "
                            "WHERE id = ANY(:i)"), {"i": emps})
        db.commit()
        db.close()


def _lines(db):
    return r115_form.build_lines(db, tenant_id=TESTCO_ID, year=YEAR,
                                 month=MONTH, rules=DEFAULT_RULES)


def test_LINE_1_EXCLUDES_ONLY_THOSE_WHOSE_STATUS_PREDATES_THE_MONTH(
        sunnycrest_shape):
    """⚠️ **THIS FIXTURE ANSWERS 14, AND THAT IS NOT A REGRESSION.**

    It asserted 13 under the FIRST ruling, which put `workers_comp` outside
    the unit outright. That reached the golden and was wrong about the
    reason — Staring was paid with dues taken on the October 1 and 8 checks,
    so the union WAS paid for him that month. Under the revised rule he is
    in, and this shape yields the 13 payers plus him.

    ⚠️ **AND SO THE FIXTURE IS NO LONGER THE GOLDEN.** 13 came from the real
    October register; a made-up shape agreeing with it was an artefact of how
    the shape was built, and treating that agreement as confirmation is how
    the first ruling survived. What this file pins is the RULE —
    before / during / absent — against data whose shape is known. The
    production figures are verified separately and recorded in the PR body.
    """
    out = _lines(sunnycrest_shape)
    by_num = {ln["number"]: ln["value"] for ln in out["lines"]}
    assert out["unit"]["roster_union_members"] == 18, "the fixture's premise"
    assert by_num[1] == "14", out["unit"]
    assert out["unit"]["basis"] == "payroll_status"
    assert len(out["unit"]["excluded"]) == 4, "only the four who left in August"


def test_the_four_who_LEFT_BEFORE_the_month_are_excluded_by_name(
        sunnycrest_shape):
    out = _lines(sunnycrest_shape)
    excluded = {e["emp_id"] for e in out["unit"]["excluded"]}
    assert {"L1-14", "L1-15", "L1-16", "L1-17"} <= excluded, excluded
    for entry in out["unit"]["excluded"]:
        assert entry["reason"], "an exclusion with no reason cannot be audited"


def test_the_member_on_COMP_FROM_MID_MONTH_IS_IN_for_that_month(
        sunnycrest_shape):
    """⚠️ **THE SECOND RULING, WHICH REVERSED THE FIRST.** James, 2026-11-18:
    a status that began DURING the month keeps the member in, because dues
    were taken and the union was paid for them — the treatment leavers
    already had, and nothing separated the two cases."""
    out = _lines(sunnycrest_shape)
    excluded = {e["emp_id"] for e in out["unit"]["excluded"]}
    assert "L1-18" not in excluded, out["unit"]["excluded"]


def test_the_member_on_comp_is_OUT_the_following_month(sunnycrest_shape):
    """The other half. Without it, "comp is in" would be satisfied by a rule
    that never excludes anybody for comp at all."""
    out = r115_form.build_lines(sunnycrest_shape, tenant_id=TESTCO_ID,
                                year=2026, month=11, rules=DEFAULT_RULES)
    excluded = {e["emp_id"]: e for e in out["unit"]["excluded"]}
    assert "L1-18" in excluded, out["unit"]["excluded"]
    assert "workers_comp" in excluded["L1-18"]["reason"]


def test_a_status_predating_the_month_AND_no_dues_is_out(sunnycrest_shape):
    """⚠️ The same member, the same status, an earlier start date — out,
    BECAUSE he also paid no dues that month. Without this, "comp is in" could
    be implemented as "comp is always in", which is the first ruling's
    mistake wearing the opposite sign."""
    db = sunnycrest_shape
    db.execute(text("UPDATE payroll_report_employees "
                    "SET payroll_status_since='2026-09-02' "
                    "WHERE tenant_id=:t AND payentry_file_number='L1-18'"),
               {"t": TESTCO_ID})
    db.commit()
    out = _lines(db)
    assert "L1-18" in {e["emp_id"] for e in out["unit"]["excluded"]}, \
        "comp beginning in September is outside October"


def test_line_2_is_13_and_line_1_does_not_fall_below_it(sunnycrest_shape):
    """Line 2 counts members who actually paid; Staring paid nothing."""
    out = _lines(sunnycrest_shape)
    by_num = {ln["number"]: ln["value"] for ln in out["lines"]}
    assert by_num[2] == "13"
    assert int(by_num[1]) >= int(by_num[2])
    assert out["unit"]["paying_but_not_counted"] == []
    assert out["warnings"] == [], out["warnings"]


def test_the_fallback_counts_CHECKS_and_warns_that_it_did(sunnycrest_shape):
    """⚠️ **THE FALLBACK READS HIGH, AND SAYS SO.** With no statuses recorded
    there is nothing to distinguish a member on comp from a working one, so
    Staring's October checks put him in the unit and line 1 reads 14. James
    ruled the fix is to set the statuses, not to change the fallback — so the
    number carries a warning naming that remedy rather than being quietly
    corrected."""
    db = sunnycrest_shape
    db.execute(text("UPDATE payroll_report_employees SET payroll_status=NULL, "
                    "payroll_status_since=NULL WHERE tenant_id=:t "
                    "AND payentry_file_number LIKE 'L1-%'"), {"t": TESTCO_ID})
    db.commit()
    out = _lines(db)
    by_num = {ln["number"]: ln["value"] for ln in out["lines"]}
    assert out["unit"]["basis"] == "checks_in_month"
    assert by_num[1] == "14", "every member with an October check"
    assert any("payroll_status" in w for w in out["warnings"]), out["warnings"]


def test_a_LEFT_member_with_no_date_is_still_excluded(sunnycrest_shape):
    """"Left, we did not record when" cannot be read as "left this month" —
    that would quietly put every undated leaver back into the unit."""
    db = sunnycrest_shape
    db.execute(text("UPDATE payroll_report_employees SET payroll_status_since=NULL "
                    "WHERE tenant_id=:t AND payentry_file_number='L1-14'"),
               {"t": TESTCO_ID})
    db.commit()
    out = _lines(db)
    excluded = {e["emp_id"] for e in out["unit"]["excluded"]}
    assert "L1-14" in excluded
    assert [e for e in out["unit"]["excluded"]
            if e["emp_id"] == "L1-14"][0]["reason"].endswith("no date recorded")


def test_someone_who_left_DURING_the_month_is_still_in_the_unit(
        sunnycrest_shape):
    """They were in the unit for part of it and had dues taken. Excluding
    them would drop a member the union was paid for."""
    db = sunnycrest_shape
    db.execute(text("UPDATE payroll_report_employees "
                    "SET payroll_status='left', payroll_status_since='2026-10-20' "
                    "WHERE tenant_id=:t AND payentry_file_number='L1-01'"),
               {"t": TESTCO_ID})
    db.commit()
    out = _lines(db)
    by_num = {ln["number"]: ln["value"] for ln in out["lines"]}
    assert by_num[1] == "14", "unchanged — he left during October, not before"


def test_the_other_golden_figures_are_unchanged_by_the_line_1_work(
        sunnycrest_shape):
    """⚠️ A CONTROL. Line 1 is computed from the roster and the rest from the
    register; a change to one must not move the other.

        13 members x 5 checks x $15.30 = $994.50 remitted
        13 x 5 x 40.00                 = 2,600.00 hours
        13 x 5 x $1,000.00             = $65,000.00 earnings
    """
    out = _lines(sunnycrest_shape)
    by_num = {ln["number"]: ln["value"] for ln in out["lines"]}
    assert by_num[3] == "2600.00"
    assert by_num[4] == "65000.00"
    assert [ln for ln in out["lines"] if ln["number"] is None][0]["value"] \
        == "994.50"


# ── the keep-in: dues taken means the union was paid for them ────────────


@pytest.fixture
def staring_with_october_dues(sunnycrest_shape):
    """Staring's REAL shape: comp dated in September, dues on an October check.

    ⚠️ **THE BASE FIXTURE CANNOT TEST THE KEEP-IN, AND DID NOT.** Its Staring
    is paid with `dues=None`, so he has no October dues and is excluded by
    the date alone — the keep-in never fires and every assertion about it
    would pass against a build that did not have one. Measured on production
    2026-11-18: his only October check is the 8th, carrying $5.46 of dues,
    and it pays for work done Sep 27 to Oct 3, so his true comp date may fall
    in September.
    """
    import uuid as _uuid
    from decimal import Decimal as _D

    from app.models.payroll_report import PayrollCheck, PayrollCheckLine

    db = sunnycrest_shape
    db.execute(text("UPDATE payroll_report_employees "
                    "SET payroll_status='workers_comp', "
                    "    payroll_status_since='2026-09-28' "
                    "WHERE tenant_id=:t AND payentry_file_number='L1-18'"),
               {"t": TESTCO_ID})
    cid = str(_uuid.uuid4())
    db.add(PayrollCheck(id=cid, tenant_id=TESTCO_ID, emp_id="L1-18",
                        person="Staring", check_number="L1-STARING-OCT8",
                        check_date=date(2026, 10, 8), source_page=0))
    db.add(PayrollCheckLine(id=str(_uuid.uuid4()), tenant_id=TESTCO_ID,
                            check_id=cid, kind="earning", code="Reg",
                            hours=_D("16.22"), amount=_D("354.20")))
    db.add(PayrollCheckLine(id=str(_uuid.uuid4()), tenant_id=TESTCO_ID,
                            check_id=cid, kind="deduction", code="Union",
                            amount=_D("5.46")))
    db.commit()
    yield db
    db.execute(text("DELETE FROM payroll_check_lines WHERE check_id=:c"), {"c": cid})
    db.execute(text("DELETE FROM payroll_checks WHERE id=:c"), {"c": cid})
    db.commit()


def test_STARING_IS_IN_FOR_OCTOBER_despite_a_september_comp_date(
        staring_with_october_dues):
    """⚠️ **THE CASE THE DATE RULE GOT WRONG.** Comp from 2026-09-28 — before
    October — so the date test alone excludes him and line 1 files as 12.
    But $5.46 of dues was taken from his October 8 check: the union was paid
    for him that month, so he is in the unit for it."""
    out = _lines(staring_with_october_dues)
    excluded = {e["emp_id"] for e in out["unit"]["excluded"]}
    assert "L1-18" not in excluded, out["unit"]["excluded"]
    by_num = {ln["number"]: ln["value"] for ln in out["lines"]}
    assert by_num[1] == "14", "13 payers plus Staring, who also paid"
    assert by_num[2] == "14", "he is a payer too, now that he has a dues line"


def test_and_he_is_OUT_in_november_when_no_dues_were_taken(
        staring_with_october_dues):
    """The other half. His comp predates November and nothing was deducted
    in it, so both halves of "outside" hold."""
    out = r115_form.build_lines(staring_with_october_dues, tenant_id=TESTCO_ID,
                                year=2026, month=11, rules=DEFAULT_RULES)
    excluded = {e["emp_id"]: e for e in out["unit"]["excluded"]}
    assert "L1-18" in excluded, out["unit"]["excluded"]
    assert "workers_comp" in excluded["L1-18"]["reason"]


def test_the_keep_in_beats_a_LEFT_status_with_no_date_too(sunnycrest_shape):
    """⚠️ The undated-`left` exclusion is the harshest branch, so it is the
    one most likely to drop somebody wrongly. Dues outrank it: a person the
    union was paid for is in the unit however little the roster records."""
    import uuid as _uuid
    from decimal import Decimal as _D

    from app.models.payroll_report import PayrollCheck, PayrollCheckLine

    db = sunnycrest_shape
    db.execute(text("UPDATE payroll_report_employees "
                    "SET payroll_status='left', payroll_status_since=NULL "
                    "WHERE tenant_id=:t AND payentry_file_number='L1-14'"),
               {"t": TESTCO_ID})
    cid = str(_uuid.uuid4())
    db.add(PayrollCheck(id=cid, tenant_id=TESTCO_ID, emp_id="L1-14",
                        person="Leaver 14", check_number="L1-14-OCT",
                        check_date=OCTOBER[0], source_page=0))
    db.add(PayrollCheckLine(id=str(_uuid.uuid4()), tenant_id=TESTCO_ID,
                            check_id=cid, kind="earning", code="Reg",
                            hours=_D("8.00"), amount=_D("200.00")))
    db.add(PayrollCheckLine(id=str(_uuid.uuid4()), tenant_id=TESTCO_ID,
                            check_id=cid, kind="deduction", code="Union",
                            amount=_D("3.10")))
    db.commit()
    try:
        out = _lines(db)
        assert "L1-14" not in {e["emp_id"] for e in out["unit"]["excluded"]}
    finally:
        db.execute(text("DELETE FROM payroll_check_lines WHERE check_id=:c"), {"c": cid})
        db.execute(text("DELETE FROM payroll_checks WHERE id=:c"), {"c": cid})
        db.commit()


@pytest.mark.parametrize("month", [9, 10, 11, 12])
def test_LINE_1_IS_NEVER_SMALLER_THAN_LINE_2(sunnycrest_shape, month):
    """⚠️ **STRUCTURAL NOW, NOT A WARNING AFTER THE FACT.** Every member who
    paid dues is counted in the unit by construction, so a form that
    contradicts itself has stopped being expressible. The warning for it
    stays, because the fallback tier and a future change could still produce
    one — but it should now be unreachable through this path."""
    out = r115_form.build_lines(sunnycrest_shape, tenant_id=TESTCO_ID,
                                year=2026, month=month, rules=DEFAULT_RULES)
    by_num = {ln["number"]: ln["value"] for ln in out["lines"]}
    assert int(by_num[1]) >= int(by_num[2]), (month, out["unit"])
    assert out["unit"]["paying_but_not_counted"] == [], out["unit"]


def test_removing_the_keep_in_would_break_that_property(sunnycrest_shape):
    """⚠️ **THE BREAK TEST, AS A TEST.** The property above is worth nothing
    unless something could violate it. Staring on comp from September with
    October dues is exactly the shape that does — and the only reason it does
    not is the keep-in clause."""
    import uuid as _uuid
    from decimal import Decimal as _D

    from app.models.payroll_report import PayrollCheck, PayrollCheckLine

    db = sunnycrest_shape
    db.execute(text("UPDATE payroll_report_employees "
                    "SET payroll_status='workers_comp', "
                    "    payroll_status_since='2026-09-28' "
                    "WHERE tenant_id=:t AND payentry_file_number='L1-18'"),
               {"t": TESTCO_ID})
    cid = str(_uuid.uuid4())
    db.add(PayrollCheck(id=cid, tenant_id=TESTCO_ID, emp_id="L1-18",
                        person="Staring", check_number="L1-BREAK",
                        check_date=date(2026, 10, 8), source_page=0))
    db.add(PayrollCheckLine(id=str(_uuid.uuid4()), tenant_id=TESTCO_ID,
                            check_id=cid, kind="earning", code="Reg",
                            hours=_D("16.22"), amount=_D("354.20")))
    db.add(PayrollCheckLine(id=str(_uuid.uuid4()), tenant_id=TESTCO_ID,
                            check_id=cid, kind="deduction", code="Union",
                            amount=_D("5.46")))
    db.commit()
    try:
        with_keep_in = _lines(db)
        assert int(with_keep_in["lines"][0]["value"]) >= int(
            with_keep_in["lines"][1]["value"])

        # Now ask the same question WITHOUT the keep-in, by the date rule
        # alone — the arithmetic the clause exists to prevent.
        from app.models.payroll_report import PayrollReportEmployee as E
        members = (db.query(E)
                   .filter(E.tenant_id == TESTCO_ID, E.is_union_member.is_(True))
                   .all())
        by_date_only = sum(
            1 for m in members
            if not (m.payroll_status
                    and m.payroll_status_since
                    and m.payroll_status_since < date(2026, 10, 1))
        )
        paying = int(with_keep_in["lines"][1]["value"])
        assert by_date_only < paying, (
            "the break did not reproduce the violation it claims to prevent; "
            f"date-only gives {by_date_only}, payers {paying}")
    finally:
        db.execute(text("DELETE FROM payroll_check_lines WHERE check_id=:c"), {"c": cid})
        db.execute(text("DELETE FROM payroll_checks WHERE id=:c"), {"c": cid})
        db.commit()
