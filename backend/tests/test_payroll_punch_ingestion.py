"""Storing punches, and the three questions that needed them.

⚠️ **`PayrollPunch` SHIPPED WITH NO WRITER AND `all_findings` WITH NO CALLER.**
Measured 2026-11-23: `parse_punch_location` was called only by tests, the
table had no write site anywhere in `app/` or `scripts/`, and
`punch_findings.all_findings` — which has had unpaired punches, early
clock-ins, clustered early departures and the Saturday rule since Payroll 3 —
was called by nothing. Two halves of a feature, each complete, with no wire
between them.

⚠️ **THE NAME RULING IS THE SUBJECT, NOT THE STORAGE.** The punch file carries
names and no employee numbers, so attaching a punch means deciding two
spellings are one person. James, Payroll 3 item 4: match via this week's
Employee Hours names, then register names, after normalising case, spacing,
Sr./Jr. and punctuation; unmatched or ambiguous is a finding; a confirmed
mapping becomes an alias; **never fuzzy-match silently.**
"""
from __future__ import annotations

import os
import pathlib
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text

from app.services.payroll import punch_names as pn
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

WEEK_END = date(2026, 10, 31)


# ── normalisation ────────────────────────────────────────────────────────


@pytest.mark.parametrize("a, b, why", [
    ("Hunt, Michael", "Michael Hunt", "the two exports disagree about order"),
    ("HUNT, MICHAEL", "michael hunt", "case"),
    ("Hunt,  Michael", "Michael   Hunt", "spacing"),
    ("Smith Jr., John", "John Smith", "generational suffix"),
    ("Smith Sr, John", "John Smith", "suffix without a period"),
    ("O'Brien, Sean", "Sean OBrien", "punctuation"),
    ("Peña, Ana", "Ana Pena", "accents, because the exports disagree"),
    ("Smith-Jones, Ann", "Ann Smith Jones", "hyphen as a separator"),
])
def test_the_two_exports_spell_one_person_the_same_way_after_normalising(a, b, why):
    assert pn.normalise(a) == pn.normalise(b), why


def test_normalising_does_NOT_merge_two_different_people():
    """⚠️ The control. A normaliser that collapses everything matches
    everybody, and the refusal tests below would pass for the wrong reason."""
    assert pn.normalise("Hunt, Michael") != pn.normalise("Hunt, Michelle")
    assert pn.normalise("Smith, John") != pn.normalise("Smith, Jon")
    # ⚠️ AND IT DOES NOT MERGE "Micheal" WITH "Michael" — one character apart,
    # and the first real alias. An edit-distance match would join them without
    # anybody deciding, and would join two real brothers on the same rule.
    assert pn.normalise("Micheal Jones") != pn.normalise("Michael Jones")


# ── resolution ───────────────────────────────────────────────────────────


def test_THIS_WEEKS_HOURS_WIN_over_the_register():
    """⚠️ A register spanning a year may hold somebody who left in March, and
    a punch in November is not theirs. The week's own file is the better
    evidence, so it answers first and the register does not widen it into an
    ambiguity."""
    r = pn.resolve(
        {"Michael Hunt"},
        hours_names_by_emp={"22": {"Hunt, Michael"}},
        register_names_by_emp={"7": {"Hunt, Michael"}},
        aliases={})
    assert r.by_raw_name == {"Michael Hunt": "22"}
    assert r.findings == []


def test_a_CONFIRMED_ALIAS_outranks_both_exports():
    """That is what makes confirming one worth doing: the same name never
    comes back as a finding."""
    r = pn.resolve(
        {"Micheal Jones"},
        hours_names_by_emp={"9": {"Jones, Michael"}},
        register_names_by_emp={},
        aliases={pn.normalise("Micheal Jones"): "22"})
    assert r.by_raw_name == {"Micheal Jones": "22"}
    assert r.findings == []


def test_AMBIGUOUS_is_a_finding_and_names_the_candidates():
    """⚠️ NOT "pick the first". Two people whose names normalise the same is
    exactly when a guess attaches somebody's hours to their brother."""
    r = pn.resolve(
        {"Pat Taylor"},
        hours_names_by_emp={"3": {"Taylor, Pat"}, "4": {"Taylor, Pat"}},
        register_names_by_emp={}, aliases={})
    assert r.by_raw_name == {}
    assert len(r.findings) == 1
    f = r.findings[0]
    assert f.kind == pn.AMBIGUOUS
    assert f.candidates == ("3", "4")
    assert "3, 4" in f.detail


def test_UNMATCHED_is_a_finding_that_says_what_to_do():
    r = pn.resolve({"Nobody Here"}, hours_names_by_emp={},
                   register_names_by_emp={}, aliases={})
    assert r.by_raw_name == {}
    assert r.findings[0].kind == pn.UNMATCHED
    assert "Confirm who it is" in r.findings[0].detail


# ── storage ──────────────────────────────────────────────────────────────


@pytest.fixture
def week_rows():
    """A hours-import row to hang punches off, removed afterwards."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollHoursImport

    db = SessionLocal()
    iid = str(uuid.uuid4())
    try:
        db.add(PayrollHoursImport(
            id=iid, tenant_id=TESTCO_ID, filename="t.pdf",
            file_sha256=uuid.uuid4().hex, week_end_date=WEEK_END,
            rows_parsed=0, source_kind="employee_hours"))
        db.commit()
        yield iid
    finally:
        db.execute(text("DELETE FROM payroll_punches WHERE import_id=:i"),
                   {"i": iid})
        db.execute(text("DELETE FROM payroll_hours_imports WHERE id=:i"), {"i": iid})
        db.commit()
        db.close()


def test_an_UNATTACHED_punch_is_STORED_not_dropped(week_rows):
    """⚠️ The model says so: "an unresolved punch is a finding, not a guess".
    Dropping it would delete the evidence along with the finding, and the next
    upload would re-raise it from nothing."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollPunch
    from app.services.payroll import punch_import

    db = SessionLocal()
    try:
        # Two people: one the hours file knows, one it does not.
        content = _real_or_skip()
        res = punch_import.import_punches(
            db, tenant_id=TESTCO_ID, content=content, import_id=week_rows,
            week_end_date=WEEK_END, hours_names_by_emp={})
        db.commit()
        # ⚠️ **NOT `unattached == stored`, WHICH IS WHAT I FIRST WROTE.** It
        # assumed the register source was empty; it is not — `register_names`
        # reads the tenant's own checks, and the seeded fixture shares a
        # surname with the real file, so one person matched. The code was
        # right and the assumption was mine. The invariant that actually
        # matters is that NOTHING IS DROPPED: every punch in the file is a row,
        # attached or not.
        assert res.stored > 0
        assert res.unattached > 0, "no unmatched names, so this proves nothing"
        assert res.unattached <= res.stored
        assert len(res.findings) > 0
        # Every unmatched name produced a finding rather than vanishing.
        assert all(f.kind in (pn.UNMATCHED, pn.AMBIGUOUS) for f in res.findings)
        n = db.query(PayrollPunch).filter(
            PayrollPunch.import_id == week_rows).count()
        assert n == res.stored
    finally:
        db.close()


def _real_or_skip() -> bytes:
    raw = os.environ.get("PAYROLL_PUNCH_LOCATION")
    if not raw:
        pytest.skip(
            "PAYROLL_PUNCH_LOCATION must point at the real Punch Location "
            ".xls, outside the repo. Skipped rather than faked — a synthesised "
            "workbook would test my idea of the format, which is the mistake "
            "the guessed CSV mapping already made. The golden path is also "
            "covered by the walk-through."
        )
    return pathlib.Path(raw).expanduser().read_bytes()


def test_RE_UPLOADING_a_week_REPLACES_rather_than_doubling(week_rows):
    """⚠️ Doubled punches would make every missed-punch finding DISAPPEAR,
    because every in would have an out. A second upload is a correction."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollPunch
    from app.services.payroll import punch_import

    content = _real_or_skip()
    db = SessionLocal()
    try:
        first = punch_import.import_punches(
            db, tenant_id=TESTCO_ID, content=content, import_id=week_rows,
            week_end_date=WEEK_END, hours_names_by_emp={})
        db.commit()
        second = punch_import.import_punches(
            db, tenant_id=TESTCO_ID, content=content, import_id=week_rows,
            week_end_date=WEEK_END, hours_names_by_emp={})
        db.commit()
        assert first.stored == second.stored
        assert db.query(PayrollPunch).filter(
            PayrollPunch.week_end_date == WEEK_END,
            PayrollPunch.tenant_id == TESTCO_ID).count() == second.stored
    finally:
        db.close()


# ── the real files ───────────────────────────────────────────────────────


def test_the_REAL_punch_file_resolves_against_the_REAL_hours_file():
    """⚠️ **THE MEASUREMENT THAT SAYS THE RULING IS SUFFICIENT.** Week 44:
    17 punch names, and the same week's Employee Hours names alone match all
    17 — no register, no aliases, no ambiguity. If this ever drops, the
    normaliser or one of the two exports has changed and somebody has to look
    before any punch is attached."""
    import pdfplumber

    hours_path = os.environ.get("PAYROLL_EMPLOYEE_HOURS_PDF")
    if not hours_path:
        pytest.skip("PAYROLL_EMPLOYEE_HOURS_PDF must point at the real export")
    from app.services.payroll.hours_parser import parse_employee_hours
    from app.services.payroll.punch_parser import parse_punch_location

    with pdfplumber.open(pathlib.Path(hours_path).expanduser()) as f:
        hours = parse_employee_hours(f)
    parsed = parse_punch_location(_real_or_skip())
    names = {p.name for p in parsed.punches if p.name}

    res = pn.resolve(names, hours_names_by_emp=hours.names_by_emp,
                     register_names_by_emp={}, aliases={})
    assert res.matched == len(names), (
        f"{len(names) - res.matched} punch names no longer match this week's "
        f"hours: {[f.raw_name for f in res.findings]}")
    assert res.findings == []


def test_the_hours_report_CARRIES_names_by_emp():
    """⚠️ It did not, and the resolver would have received `{}` and reported
    every name unmatched. The parser has had `names_by_emp` all along; it was
    simply never shaped into the report the endpoint passes on."""
    import pdfplumber

    hours_path = os.environ.get("PAYROLL_EMPLOYEE_HOURS_PDF")
    if not hours_path:
        pytest.skip("PAYROLL_EMPLOYEE_HOURS_PDF must point at the real export")
    from app.services.payroll.hours_parser import parse_employee_hours

    with pdfplumber.open(pathlib.Path(hours_path).expanduser()) as f:
        parsed = parse_employee_hours(f)
    assert parsed.names_by_emp, "the parser itself lost them"


# ── end to end, through the endpoint ─────────────────────────────────────


def test_BOTH_real_files_through_the_endpoint_store_and_turn_the_findings_on():
    """⚠️ **THE TEST THAT CAUGHT MY OWN DEFECT, AND IT ONLY CAUGHT IT BECAUSE
    IT READS THE DATABASE.**

    The first version of the endpoint wiring ran the punch import BELOW
    `db.commit()`. The rows were flushed, never committed, and vanished when
    the session closed — while the reply said `stored: 168`, because the
    service counted what it had ADDED rather than what persisted. A test
    asserting the response would have passed over an empty table. That is the
    same lesson as the hours upload four days earlier, reproduced by the
    person who wrote it up.

    So this asserts the reply AND the row count AND the findings, and the
    middle one is the load-bearing assertion.
    """
    import pdfplumber
    from fastapi.testclient import TestClient

    from app.database import SessionLocal
    from app.main import app
    from app.models.payroll_report import PayrollPunch, PayrollWeek
    from app.services.payroll.hours_parser import parse_employee_hours
    from app.services.payroll.week_focus import week_focus
    from tests._payroll_switch import payroll_switch
    from tests._two_step import tenant_token

    hours_path = os.environ.get("PAYROLL_EMPLOYEE_HOURS_PDF")
    if not hours_path:
        pytest.skip("PAYROLL_EMPLOYEE_HOURS_PDF must point at the real export")
    punch_bytes = _real_or_skip()
    hours_bytes = pathlib.Path(hours_path).expanduser().read_bytes()

    with pdfplumber.open(pathlib.Path(hours_path).expanduser()) as f:
        ids = sorted(parse_employee_hours(f).emp_ids)

    from app.models.payroll_report import PayrollReportEmployee
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    made, uid, made_rule = [], "punch-e2e-admin", None
    try:
        role = (db.query(Role)
                .filter(Role.company_id == TESTCO_ID, Role.slug == "admin").first())
        if role is None:
            pytest.skip("testco has no admin role")
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.add(User(id=uid, email=f"{uid}@testco.com", hashed_password="x",
                    first_name="Punch", last_name="E2E", company_id=TESTCO_ID,
                    role_id=role.id, is_active=True))
        # ⚠️ The roster is a precondition `import_hours` ENFORCES — ids only,
        # never names, so no real employee's name is written anywhere.
        for e in ids:
            if not db.query(PayrollReportEmployee).filter(
                    PayrollReportEmployee.tenant_id == TESTCO_ID,
                    PayrollReportEmployee.payentry_file_number == e).first():
                rid = str(uuid.uuid4()); made.append(rid)
                db.add(PayrollReportEmployee(
                    id=rid, tenant_id=TESTCO_ID, payentry_file_number=e,
                    display_name=f"Roster {e}", is_union_member=False))
        # ⚠️ **THIS TEST OWNS ITS RULE SET.** `week_focus` recomputes through
        # `calculate_week`, which REFUSES without one — "seed a rule set rather
        # than falling back to defaults, so the result records which rules
        # produced it", which is right. Other suites clear
        # `payroll_rule_sets`, so run alone this passed and run in the slice it
        # failed with a message about a date five days after the week. A test
        # that depends on a table's contents either creates that state or says
        # it assumes it; this one creates it.
        from app.models.payroll_report import PayrollRuleSet

        rule_row = (db.query(PayrollRuleSet)
                    .filter(PayrollRuleSet.tenant_id == TESTCO_ID)
                    .order_by(PayrollRuleSet.effective_date.desc()).first())
        made_rule = None
        if rule_row is None or rule_row.effective_date > date(2026, 1, 1):
            made_rule = str(uuid.uuid4())
            db.add(PayrollRuleSet(id=made_rule, tenant_id=TESTCO_ID,
                                  effective_date=date(2026, 1, 1)))

        db.execute(text("DELETE FROM payroll_hours_imports WHERE tenant_id=:c "
                        "AND week_end_date=:w"), {"c": TESTCO_ID, "w": WEEK_END})
        db.execute(text("DELETE FROM payroll_weeks WHERE tenant_id=:c "
                        "AND week_end_date=:w"), {"c": TESTCO_ID, "w": WEEK_END})
        db.commit()

        with payroll_switch(TESTCO_ID, True):
            r = TestClient(app).post(
                "/api/v1/payroll-reports/weeks/upload",
                files={"file": ("hours.pdf", hours_bytes, "application/pdf"),
                       "punch_file": ("punch.xls", punch_bytes,
                                      "application/vnd.ms-excel")},
                data={"week_number": 44, "week_end_date": WEEK_END.isoformat()},
                headers={"Authorization": f"Bearer {tenant_token(uid, TESTCO_ID)}",
                         "X-Company-Slug": "testco"})
        assert r.status_code == 201, r.text[:400]
        punch = r.json()["punch_file"]
        assert punch["stored"] is True
        # ⚠️ EVERY NAME RESOLVED against this week's hours alone. If this ever
        # fails, the normaliser or an export changed and somebody looks before
        # a punch is attached.
        assert punch["unattached"] == 0, punch["findings"]
        assert punch["findings"] == []

        # ⚠️ THE ASSERTION THAT CAUGHT THE BUG: what the DATABASE holds.
        stored = db.query(PayrollPunch).filter(
            PayrollPunch.tenant_id == TESTCO_ID,
            PayrollPunch.week_end_date == WEEK_END).count()
        assert stored == punch["punches_stored"], (
            f"the reply said {punch['punches_stored']} and the database holds "
            f"{stored} — the rows were flushed and not committed")

        week = db.query(PayrollWeek).filter(
            PayrollWeek.tenant_id == TESTCO_ID,
            PayrollWeek.week_end_date == WEEK_END).first()
        kinds = {f["code"] for f in week_focus(db, week)["findings"]}
        # ⚠️ **THE THREE QUESTIONS, NOW ANSWERABLE.** They could not run at all
        # before: `all_findings` had no caller and `PayrollPunch` no writer.
        assert "early_clock_in" in kinds, kinds
        assert "clustered_early_departure" in kinds, kinds
        # ⚠️ AND THE SATURDAY RULE: the early detectors run Monday-to-Friday,
        # so Saturday produces its own finding rather than a false early
        # release. Week 44 has both, which is what makes it the right week.
        assert "saturday_overtime_worked" in kinds, kinds
    finally:
        db.execute(text("DELETE FROM payroll_hours_imports WHERE tenant_id=:c "
                        "AND week_end_date=:w"), {"c": TESTCO_ID, "w": WEEK_END})
        db.execute(text("DELETE FROM payroll_weeks WHERE tenant_id=:c "
                        "AND week_end_date=:w"), {"c": TESTCO_ID, "w": WEEK_END})
        if made:
            db.execute(text("DELETE FROM payroll_report_employees "
                            "WHERE id = ANY(:i)"), {"i": made})
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        if made_rule:
            db.execute(text("DELETE FROM payroll_rule_sets WHERE id=:r"),
                       {"r": made_rule})
        db.commit()
        db.close()


def test_the_WRONG_FILE_in_the_punch_field_is_refused_by_content():
    """A PDF in the punch field is the mistake somebody will make, and the
    sentence names which export goes where."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.models.role import Role
    from app.models.user import User
    from app.database import SessionLocal
    from tests._payroll_switch import payroll_switch
    from tests._two_step import tenant_token

    db = SessionLocal()
    uid = "punch-wrongfile"
    try:
        role = (db.query(Role)
                .filter(Role.company_id == TESTCO_ID, Role.slug == "admin").first())
        if role is None:
            pytest.skip("testco has no admin role")
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.add(User(id=uid, email=f"{uid}@testco.com", hashed_password="x",
                    first_name="Wrong", last_name="File", company_id=TESTCO_ID,
                    role_id=role.id, is_active=True))
        db.commit()
        with payroll_switch(TESTCO_ID, True):
            r = TestClient(app).post(
                "/api/v1/payroll-reports/weeks/upload",
                files={"file": ("hours.pdf", b"%PDF-1.4 not really",
                                "application/pdf"),
                       "punch_file": ("oops.pdf", b"%PDF-1.4 also a pdf",
                                      "application/pdf")},
                data={"week_number": 44, "week_end_date": WEEK_END.isoformat()},
                headers={"Authorization": f"Bearer {tenant_token(uid, TESTCO_ID)}",
                         "X-Company-Slug": "testco"})
        assert r.status_code == 422, r.text[:300]
        detail = r.json()["detail"]
        assert detail["code"] == "punch_file_not_recognised"
        assert "Punch Location" in detail["message"]
        assert "spreadsheet" in detail["message"]
    finally:
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()
