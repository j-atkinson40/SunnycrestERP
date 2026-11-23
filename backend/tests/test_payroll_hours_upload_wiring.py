"""The Focus's hours upload reaches the Employee Hours parser.

⚠️ **IT NEVER DID, AND NOTHING IN THIS REPO COULD HAVE TOLD YOU.** Measured
2026-11-23:

  * `POST /weeks/upload` chose its parser from `format_key`, defaulting to
    `"payentry"` — the key of `column_mappings/payentry.json`, an old GUESSED
    layout for a CSV nobody exports, carrying `verified: false`.
  * The Focus never sent `format_key` at all, so every upload took that
    default and was refused by the unverified-mapping guard. **In every
    environment.**
  * Payroll 3's PDF reader sat behind `format_key == "payentry_employee_hours"`
    — a string that appeared **exactly once in the whole tree, at its own
    definition.** Not the client, not a test, not a script. The parser was
    built, golden-tested against the real export (25 people, 708.61 hours) and
    unreachable from the product.

Phase 3's own suite tests the PARSER and the RULES. Nothing posted a PDF to the
endpoint, so the branch that would have failed had never executed. CLAUDE.md
§11: complete machinery behind an unprovisioned entrance.

⚠️ **THESE TESTS DRIVE THE ENDPOINT, NOT THE SERVICE.** A service-level test
would have passed throughout the entire period the product was broken — that is
not a hypothetical, it is what happened.
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.user import User
from app.services.payroll import export_sniff
from tests._payroll_switch import payroll_switch
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

BASE = "/api/v1/payroll-reports"
HEADERS = {"X-Company-Slug": "testco"}

#: ⚠️ READ IN PLACE, NEVER COPIED INTO THE REPOSITORY — real names, real rates.
HOURS_ENV = "PAYROLL_EMPLOYEE_HOURS_PDF"
WEEK_END = date(2026, 10, 31)

#: James's goldens, from Payentry's own export. Stated here as literals rather
#: than computed from the parser, so this file cannot agree with a wrong parser.
#:
#: ⚠️ **"25 PEOPLE" AND "18 PEOPLE" ARE BOTH RIGHT AND THEY COUNT DIFFERENT
#: THINGS.** 25 are LISTED on the export; 18 of them have hours and 7 are
#: listed with none. My first assertion read `count(DISTINCT emp_id)` from the
#: stored lines — which is 18, because somebody with no hours has no line —
#: and compared it to 25. The number was not wrong; the POPULATION was, and a
#: count whose population is ambiguous is CLAUDE.md §11's denominator problem.
#: Both are asserted, so neither can drift into standing for the other.
GOLDEN_LISTED = 25
GOLDEN_WITH_HOURS = 18
GOLDEN_WITHOUT_HOURS = 7
GOLDEN_HOURS = D("708.61")


def _real_pdf() -> Path:
    raw = os.environ.get(HOURS_ENV)
    if not raw:
        # ⚠️ **A SKIP, AND IT SAYS WHERE THE COVERAGE ACTUALLY LIVES.** A skip
        # with a stated reason reads as deliberate and is still a channel that
        # reports nothing — the two upload tests retired on 2026-11-23 had been
        # skipping on exactly this variable since the day they landed, and
        # nobody noticed for weeks. The refusal and sniffer tests in this file
        # DO run in CI; the golden path is held by the walk-through, which is
        # stamped in `frontend/tests/local/WALKS.md` so it cannot go stale
        # unnoticed.
        pytest.skip(
            f"{HOURS_ENV} must point at the real Payentry Employee Hours PDF, "
            "outside the repo (try ~/Downloads/). Skipped rather than faked — "
            "a synthesised PDF would test my idea of the format, which is "
            "precisely what the guessed CSV mapping already was. The golden "
            "path is covered by payroll-week44-walkthrough.spec.ts."
        )
    p = Path(raw).expanduser()
    assert p.exists(), f"{HOURS_ENV} points at {p}, which does not exist"
    return p


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def token():
    from app.database import SessionLocal
    from app.models.role import Role

    db = SessionLocal()
    uid = "hours-upload-admin"
    try:
        role = (db.query(Role)
                .filter(Role.company_id == TESTCO_ID, Role.slug == "admin").first())
        if role is None:
            pytest.skip("testco has no admin role")
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.add(User(id=uid, email=f"{uid}@testco.com", hashed_password="x",
                    first_name="Hours", last_name="Admin",
                    company_id=TESTCO_ID, role_id=role.id, is_active=True))
        db.commit()
        yield tenant_token(uid, TESTCO_ID)
    finally:
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}", **HEADERS}


@pytest.fixture
def switch_on():
    with payroll_switch(TESTCO_ID, True):
        yield


@pytest.fixture
def roster_knows_the_file():
    """The 25 employee ids in the real export, present on testco's roster.

    ⚠️ **THIS IS A PRECONDITION THE IMPORTER ENFORCES, NOT A WORKAROUND.**
    `import_hours` refuses a whole file whose ids are not in the register or
    the roster — "correct hours against a person who does not exist" is what a
    mis-read employee number looks like, and that guard is the reason the
    parser can be trusted. Without this fixture the test fails on identity and
    never reaches the wiring, which is what it is actually about.

    ⚠️ **IDS ONLY, AND THE IDS COME FROM THE FILE WHILE THE GOLDENS DO NOT.**
    Deriving a fixture from the input is fine; deriving the ASSERTIONS from it
    would not be, so `GOLDEN_PEOPLE` and `GOLDEN_HOURS` stay literals James
    stated. No names are copied — the display name here is a placeholder, so
    nothing in this repository carries a real employee's name.
    """
    import pdfplumber

    from app.database import SessionLocal
    from app.models.payroll_report import PayrollReportEmployee
    from app.services.payroll.hours_parser import parse_employee_hours

    with pdfplumber.open(_real_pdf()) as pdf:
        emp_ids = sorted(parse_employee_hours(pdf).emp_ids)

    db = SessionLocal()
    made: list[str] = []
    try:
        for emp_id in emp_ids:
            exists = db.query(PayrollReportEmployee).filter(
                PayrollReportEmployee.tenant_id == TESTCO_ID,
                PayrollReportEmployee.payentry_file_number == emp_id).first()
            if exists:
                continue
            rid = str(uuid.uuid4())
            db.add(PayrollReportEmployee(
                id=rid, tenant_id=TESTCO_ID, payentry_file_number=emp_id,
                display_name=f"Roster {emp_id}", is_union_member=False))
            made.append(rid)
        db.commit()
        yield emp_ids
    finally:
        if made:
            db.execute(text("DELETE FROM payroll_report_employees WHERE id = ANY(:ids)"),
                       {"ids": made})
            db.commit()
        db.close()


@pytest.fixture
def clean_week():
    """This week's rows, before and after — the upload WRITES."""
    from app.database import SessionLocal

    def wipe():
        db = SessionLocal()
        try:
            db.execute(text(
                "DELETE FROM payroll_hours_imports WHERE tenant_id=:c "
                "AND week_end_date=:w"), {"c": TESTCO_ID, "w": WEEK_END})
            db.execute(text(
                "DELETE FROM payroll_weeks WHERE tenant_id=:c AND week_end_date=:w"),
                {"c": TESTCO_ID, "w": WEEK_END})
            db.commit()
        finally:
            db.close()

    wipe()
    yield
    wipe()


# ── the wiring, which is the whole subject ───────────────────────────────


def test_the_REAL_export_reaches_the_PDF_parser_and_the_goldens_come_back(
        client, token, switch_on, clean_week, roster_knows_the_file):
    """⚠️ **THE TEST THE PRODUCT NEEDED AND DID NOT HAVE.** It sends the file
    Susan downloads, through the endpoint the Focus posts to, with the form
    fields the Focus actually sends — which notably do NOT include
    `format_key`. Before this fix it answered 422."""
    pdf = _real_pdf()
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
        # ⚠️ EXACTLY WHAT `uploadWeekHours` SENDS. No `format_key` — that
        # absence is the defect, so supplying one here would hide it.
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text[:600]
    body = r.json()

    # ⚠️ READ THE ROWS, NOT THE STATUS. A 201 says the request was accepted.
    assert body["rows_stored"] > 0, body
    assert body["week_id"], body

    # What the SERVER says it read: everyone the export lists.
    report = body["report"]
    assert len(report["emp_ids"]) == GOLDEN_LISTED, report["emp_ids"]
    assert len(report["listed_without_hours"]) == GOLDEN_WITHOUT_HOURS

    # And what it STORED, read from the rows rather than from the reply.
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        with_hours = db.execute(text(
            "SELECT count(DISTINCT emp_id) FROM payroll_hours_lines "
            "WHERE import_id=:i"), {"i": body["import_id"]}).scalar()
        hours = db.execute(text(
            "SELECT coalesce(sum(hours), 0) FROM payroll_hours_lines "
            "WHERE import_id=:i"), {"i": body["import_id"]}).scalar()
    finally:
        db.close()

    assert with_hours == GOLDEN_WITH_HOURS, (
        f"{with_hours} people have hour lines, expected {GOLDEN_WITH_HOURS}")

    # ⚠️ **THE SENTENCE THE SCREEN WILL ACTUALLY RENDER.** The upload card says
    # `Week N loaded: {summary.people} people, {summary.hours} hours.` — so
    # these two fields ARE the user-visible result, and before this fix the
    # PDF branch returned neither and the sentence read "— people, — hours."
    summary = body["summary"]
    assert summary["people"] == GOLDEN_LISTED, summary
    assert summary["hours"] == str(GOLDEN_HOURS), summary
    assert summary["listed_without_hours"] == GOLDEN_WITHOUT_HOURS, summary
    # ⚠️ ASSERTED BECAUSE IT WAS NULL ON EVERY UPLOAD and no test noticed —
    # it read a `rows` key the report does not have. A field that is always
    # null is worse than an absent one: null reads as measured-and-empty.
    assert summary["with_hours"] == GOLDEN_WITH_HOURS, summary
    assert D(str(hours)) == GOLDEN_HOURS, f"{hours} hours, expected {GOLDEN_HOURS}"
    # ⚠️ The arithmetic tying the two populations together, so a future change
    # cannot quietly move somebody from one to the other.
    assert GOLDEN_WITH_HOURS + GOLDEN_WITHOUT_HOURS == GOLDEN_LISTED


def test_the_endpoint_IGNORES_format_key_for_a_PDF(client, token, switch_on,
                                                   clean_week, roster_knows_the_file):
    """⚠️ **CONTENT WINS OVER THE FLAG, WHICH IS THE RULING.** A caller that
    says "payentry" — the old CSV mapping — while sending a PDF gets the PDF
    parser, because the bytes cannot be wrong about themselves and the flag
    can. James, 2026-11-23: chosen by file content, not by a client flag."""
    pdf = _real_pdf()
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat(),
              "format_key": "payentry"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text[:400]
    assert "verified=false" not in r.text


def test_a_FILENAME_cannot_route_a_file(client, token, switch_on, clean_week):
    """⚠️ `.pdf` IS A CLAIM BY WHOEVER NAMED THE FILE. The case that matters is
    the one where it is wrong, so the extension decides nothing."""
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": ("Employee_Hours.pdf", b"\x01\x02\x00\x03not a pdf",
                        "application/pdf")},
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 422, r.text[:300]
    assert "Employee Hours" in r.text


# ── what a refusal has to say ────────────────────────────────────────────


def test_an_unreadable_file_NAMES_WHAT_IT_EXPECTED(client, token, switch_on):
    """"Unsupported file type" tells somebody nothing they can act on. The
    whole value of a refusal is the next step it hands them."""
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": ("mystery.bin", b"\x01\x02\x00\x03\x04", "application/x-thing")},
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 422, r.text[:300]
    detail = r.json()["detail"]
    assert detail["code"] == "hours_file_not_recognised"
    assert "Employee Hours" in detail["message"]
    assert "PDF" in detail["message"]
    assert "mystery.bin" in detail["message"]


def test_the_PUNCH_workbook_is_refused_as_the_HOURS_file_and_says_why(
        client, token, switch_on):
    """⚠️ THE MISTAKE SOMEBODY WILL ACTUALLY MAKE: there are two files in the
    Payentry download and one is a spreadsheet. The refusal names both so she
    knows which one to pick, instead of saying "unsupported"."""
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": ("Punch_Location.xls",
                        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64,
                        "application/vnd.ms-excel")},
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 422, r.text[:300]
    msg = r.json()["detail"]["message"]
    assert "Employee Hours" in msg
    assert "Punch Location" in msg


def test_the_legacy_CSV_path_still_works_and_still_refuses_the_guessed_mapping(
        client, token, switch_on, clean_week):
    """⚠️ CONTENT ROUTING MUST NOT QUIETLY RETIRE THE OTHER PATH. Two CSVs with
    different column layouts are both CSVs, which is the one case bytes cannot
    settle — so `format_key` survives as the chooser among TEXT mappings and
    nothing else."""
    csv = (b"file_number,display_name,dept,reg_hrs,personal_hrs,ot_hrs\n"
           b"E01,Member E01,PRECAST,40,0,7\n")
    refused = client.post(
        f"{BASE}/weeks/upload",
        files={"file": ("export.csv", csv, "text/csv")},
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat(),
              "format_key": "payentry"},
        headers=_auth(token),
    )
    assert refused.status_code == 422, refused.text[:300]
    assert "verified=false" in refused.text

    ok = client.post(
        f"{BASE}/weeks/upload",
        files={"file": ("export.csv", csv, "text/csv")},
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat(),
              "format_key": "bridgeable_csv"},
        headers=_auth(token),
    )
    assert ok.status_code == 201, ok.text[:300]


# ── the punch file, which was being thrown away in silence ───────────────


def test_an_attached_PUNCH_file_is_reported_rather_than_silently_dropped(
        client, token, switch_on, clean_week, roster_knows_the_file):
    """⚠️ **THE FOCUS HAS BEEN SENDING THIS SINCE PAYROLL 5a AND THE ENDPOINT
    HAD NO SUCH PARAMETER**, so FastAPI dropped it and the response said
    nothing. A success with no mention of the file is how somebody comes to
    believe punches were loaded. `PayrollPunch` has no writer anywhere in
    `app/` — ingestion is unbuilt, and that is now stated in the reply."""
    pdf = _real_pdf()
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": (pdf.name, pdf.read_bytes(), "application/pdf"),
               "punch_file": ("Punch_Location.xls",
                              b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64,
                              "application/vnd.ms-excel")},
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text[:400]
    punch = r.json()["punch_file"]
    assert punch is not None, "the punch file was dropped in silence again"
    assert punch["stored"] is False
    assert punch["filename"] == "Punch_Location.xls"
    assert "not stored yet" in punch["reason"]


def test_no_punch_file_reports_nothing_rather_than_a_false_negative(
        client, token, switch_on, clean_week, roster_knows_the_file):
    """The control: absent and not-stored are different facts."""
    pdf = _real_pdf()
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
        data={"week_number": 44, "week_end_date": WEEK_END.isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text[:300]
    assert r.json()["punch_file"] is None


# ── the sniffer, on its own ──────────────────────────────────────────────


def test_the_sniffer_reads_the_REAL_export_as_a_PDF():
    assert export_sniff.detect(
        _real_pdf().read_bytes(), filename="x.pdf").kind == export_sniff.EMPLOYEE_HOURS_PDF


def test_a_PDF_mentioned_INSIDE_a_csv_does_not_route_it(_=None):
    """⚠️ FALSE PRESENCE FROM A SUBSTRING. Searching the whole file for `%PDF-`
    would route a CSV that happens to mention one. The magic is bounded to the
    first few bytes, where a real header lives."""
    csv = b"name,note\nSmith,see %PDF- in the attachment\n"
    assert export_sniff.detect(csv, filename="x.csv").kind == export_sniff.DELIMITED_TEXT
