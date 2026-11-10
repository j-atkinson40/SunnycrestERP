"""Local-only checks against the real Payentry exports — Payroll 3.

⚠️ **SKIPPED UNLESS THE ENV VARS POINT AT REAL FILES, AND THAT IS THE POINT.**
A real export never enters the repository: it carries names, pay rates, clock
times and employee numbers. CI holds anonymised fixtures. These tests exist so
the real numbers can be re-checked on a developer machine after a parser
change, and so the figures in the report are reproducible rather than
remembered.

    PAYROLL_EMPLOYEE_HOURS_PDF=~/Downloads/Payentry_Employee_Hours_2026-10-25_to_10-31.pdf \
    PAYROLL_PUNCH_LOCATION=~/Downloads/Sunnycrest_2026-10-25_to_10-31_Punch_Location.xls \
    PAYROLL_REGISTER_PDF=~/Downloads/Sunnycrest_Payroll_Register_2025-11-09_to_2026-11-09.pdf \
    python -m pytest tests/test_payroll_real_files_local.py -q

⚠️ **A SKIP IS NOT A PASS.** `test_the_env_vars_are_named_correctly` always
runs, so a typo in a variable name shows up as a failure rather than as a
quietly skipped file that nobody notices has stopped running.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

HOURS_ENV = "PAYROLL_EMPLOYEE_HOURS_PDF"
PUNCH_ENV = "PAYROLL_PUNCH_LOCATION"
REGISTER_ENV = "PAYROLL_REGISTER_PDF"
WEEK_END = date(2026, 10, 31)


def _path(var: str) -> Path | None:
    raw = os.environ.get(var)
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.exists() else None


def _require(var: str) -> Path:
    p = _path(var)
    if p is None:
        pytest.skip(f"{var} is not set to an existing file")
    return p


def test_the_env_vars_are_named_correctly():
    """⚠️ Always runs. A renamed variable must fail, not silently skip."""
    assert HOURS_ENV == "PAYROLL_EMPLOYEE_HOURS_PDF"
    assert PUNCH_ENV == "PAYROLL_PUNCH_LOCATION"
    assert REGISTER_ENV == "PAYROLL_REGISTER_PDF"


# ── Employee Hours, week 44 ──────────────────────────────────────────────────

def test_week_44_hour_totals():
    """The goldens James stated, from Payentry's own export."""
    import pdfplumber

    from app.services.payroll.hours_parser import parse_employee_hours

    with pdfplumber.open(_require(HOURS_ENV)) as pdf:
        r = parse_employee_hours(pdf)
    totals = {k: str(v) for k, v in r.hours_by_pay_type().items()}
    assert totals == {"REG": "618.45", "OT1": "74.16",
                      "PTO": "4.00", "Sick": "12.00"}
    assert sum(r.hours_by_pay_type().values()) == D("708.61")
    assert len(r.emp_ids) == 25
    assert len(r.hours_by_emp()) == 18
    assert len(r.listed_without_hours) == 7
    assert r.unreadable_rows == []
    assert r.unknown_pay_types == {}
    assert r.ambiguous_names == {}


def test_week_44_per_person_goldens():
    import pdfplumber

    from app.services.payroll.hours_parser import parse_employee_hours

    with pdfplumber.open(_require(HOURS_ENV)) as pdf:
        r = parse_employee_hours(pdf)
    by = r.hours_by_emp()
    # Coyne: REG 36, OT1 7.68, PTO 4.  Edward Bell 47.44.  Hunt 31.65.
    assert by["7"] == {"REG": D("36.00"), "OT1": D("7.68"), "PTO": D("4.00")}
    assert sum(by["6"].values()) == D("47.44")
    assert sum(by["30"].values()) == D("31.65")


def test_the_interleaved_employee_numbers_are_right():
    """⚠️ The identity check the totals cannot make.

    DiGenova is employee 20, not 12008. Sanchez Jr is 14, not "14 1".
    Baran-Corgnell is 17, listed with no hours.
    """
    import pdfplumber

    from app.services.payroll.hours_parser import parse_employee_hours

    with pdfplumber.open(_require(HOURS_ENV)) as pdf:
        r = parse_employee_hours(pdf)
    assert "12008" not in r.emp_ids
    assert {"20", "14", "17"} <= r.emp_ids
    names = {e: sorted(n)[0] for e, n in r.names_by_emp.items()}
    assert names["20"].startswith("DiGenova")
    assert names["14"].startswith("Sanchez")
    assert names["17"].startswith("Baran")
    assert "17" in r.listed_without_hours
    homes = {l.emp_id: l.home_dept for l in r.lines}
    assert homes["20"] == "108" and homes["14"] == "106"


def test_every_date_is_inside_week_44():
    import pdfplumber

    from app.services.payroll.hours_parser import parse_employee_hours
    from app.services.payroll.hours_validation import validate_week_window

    with pdfplumber.open(_require(HOURS_ENV)) as pdf:
        r = parse_employee_hours(pdf)
    report = validate_week_window(r, expected_week_end=WEEK_END)
    assert report.ok, [f.detail for f in report.blocking]
    assert {d.isoformat() for d in {l.work_date for l in r.lines}} == {
        "2026-10-26", "2026-10-27", "2026-10-28",
        "2026-10-29", "2026-10-30", "2026-10-31"}


# ── Punch Location, week 44 ──────────────────────────────────────────────────

def test_week_44_punches():
    from app.services.payroll.punch_parser import pair_punches, parse_punch_location

    r = parse_punch_location(_require(PUNCH_ENV).read_bytes())
    assert len(r.punches) == 168
    assert r.blocks == 28
    assert len(r.people) == 17
    # ⚠️ 28 blocks for 17 people is the interleaving, measured.
    assert r.blocks > len(r.people)
    assert sum(1 for p in r.punches if p.has_location) == 19
    days = pair_punches(r)
    assert len(days) == 84
    assert not [d for d in days if d.unpaired], "week 44 has no missed punches"


def test_edward_bell_is_scattered_across_blocks_and_still_pairs():
    """The real case the fixture reproduces: 7 blocks, 12 punches."""
    from app.services.payroll.punch_parser import pair_punches, parse_punch_location

    r = parse_punch_location(_require(PUNCH_ENV).read_bytes())
    his = r.by_person()["Bell, Edward"]
    assert len(his) == 12
    oct26 = [p for p in his if p.on_date == date(2026, 10, 26)]
    assert [p.punch_at.strftime("%H:%M") for p in oct26] == ["06:00", "15:43"]
    day = next(d for d in pair_punches(r)
               if d.name == "Bell, Edward" and d.on_date == date(2026, 10, 26))
    assert len(day.pairs) == 1 and not day.unpaired


def test_week_44_punch_findings():
    """What the detectors find on the real week. Figures, not impressions."""
    from collections import Counter

    from app.services.payroll.punch_findings import all_findings
    from app.services.payroll.punch_parser import pair_punches, parse_punch_location

    r = parse_punch_location(_require(PUNCH_ENV).read_bytes())
    found = all_findings(pair_punches(r))
    kinds = Counter(f.kind for f in found)
    # ⚠️ AFTER THE SATURDAY RULE (James, 2026-11-10). Before it: 9 early
    # clock-ins and 2 clusters, three of the clock-ins and one cluster falling
    # on Saturday 2026-10-31 — four people out from 10:53, which is what a
    # short Saturday looks like, not a finding. The early detectors now run
    # Monday to Friday and Saturday hours are reported as overtime worked.
    assert kinds == {"early_clock_in": 6, "clustered_early_departure": 1,
                     "saturday_overtime_worked": 8}, kinds
    saturday = [f for f in found if f.on_date == date(2026, 10, 31)]
    assert {f.kind for f in saturday} == {"saturday_overtime_worked"}, saturday


# ── hours against the register ───────────────────────────────────────────────

def test_week_44_hours_against_the_november_5_checks():
    """⚠️ Pins the measured disagreements so a change to them is visible.

    10 of 36 comparisons differ, and every one is reported rather than
    blocking — see `compare_with_register`.
    """
    import pdfplumber

    from app.services.payroll.hours_parser import parse_employee_hours
    from app.services.payroll.hours_validation import compare_with_register
    from app.services.payroll.register_parser import parse_register

    with pdfplumber.open(_require(HOURS_ENV)) as pdf:
        hours = parse_employee_hours(pdf)
    with pdfplumber.open(_require(REGISTER_ENV)) as pdf:
        reg = parse_register(pdf)

    rows, report = compare_with_register(hours, reg.checks, week_end=WEEK_END)
    assert len(rows) == 36
    differ = {(r.emp_id, r.pay_type): str(r.difference)
              for r in rows if not r.agrees}
    assert differ == {
        ("1", "OT1"): "0.01", ("4", "OT1"): "0.01", ("6", "OT1"): "0.01",
        ("28", "OT1"): "0.01", ("32", "OT1"): "0.01", ("36", "OT1"): "-0.01",
        ("21", "OT1"): "0.50", ("31", "OT1"): "0.50",
        ("14", "REG"): "2.00", ("14", "OT1"): "-2.00",
    }, differ
    assert report.ok, "an hours difference must never block"


def test_the_hours_file_has_one_employee_the_register_has_never_paid():
    """⚠️ A real blocking finding, and correct behaviour.

    Employee 38 is listed in the hours file with no hours and appears nowhere
    in a YEAR of registers, so the identity check refuses the import until
    somebody puts her on the roster. That is what the check is for.
    """
    import pdfplumber

    from app.services.payroll.hours_parser import parse_employee_hours
    from app.services.payroll.hours_validation import validate_identity
    from app.services.payroll.register_parser import parse_register

    with pdfplumber.open(_require(HOURS_ENV)) as pdf:
        hours = parse_employee_hours(pdf)
    with pdfplumber.open(_require(REGISTER_ENV)) as pdf:
        reg = parse_register(pdf)

    known = {c.emp_id for c in reg.checks}
    assert hours.emp_ids - known == {"38"}
    report = validate_identity(hours, known_emp_ids=known)
    assert not report.ok
    assert any("38" in f.detail for f in report.blocking)


def test_payentrys_deductions_are_the_workbooks_figures():
    """⚠️ THE PROOF THAT SETTLED THE EIGHT DIFFERENCES.

    Payentry does not calculate dues; it deducts what the accountant types in
    from her workbook. The sum of Payentry's 2026-11-05 `Union` deductions is
    193.93 — exactly the workbook's week-44 golden total in spec §6, to the
    cent. A coincidence at that precision across twelve members is not
    available.
    """
    import pdfplumber

    from app.services.payroll.register_parser import parse_register
    from tests.test_payroll_dues_golden import TOTAL_DUES

    with pdfplumber.open(_require(REGISTER_ENV)) as pdf:
        reg = parse_register(pdf)
    total = sum(
        (line.amount for chk in reg.checks if chk.check_date == date(2026, 11, 5)
         for line in chk.lines
         if line.kind == "deduction" and line.code == "Union"),
        D("0"))
    assert total == TOTAL_DUES == D("193.93"), total
