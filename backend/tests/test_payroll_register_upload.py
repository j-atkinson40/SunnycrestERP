"""`POST /payroll-reports/register/upload` — the register import, end to end.

Three things are asserted, and the first is the one that would hurt most if it
were wrong:

1. **IDEMPOTENCE.** Uploading the same register twice inserts nothing the
   second time. The natural way to use this is to pull a fresh year from
   Payentry and upload it, so overlapping uploads are the NORMAL case — and a
   dues figure that doubled because a register was uploaded twice is the
   failure that matters.
2. **THE DATA SWITCH REFUSES FIRST.** A register is the most sensitive payroll
   file a tenant has. The switch is checked before the bytes are interpreted.
3. **THE REPORT IS STORED, NOT JUST RETURNED.** The anomalies that need a
   person outlive the request that found them.

⚠️ Uploads go as an ADMIN. The endpoint is admin-only for the same reason the
hours upload is, so uploading as anyone else would be refused by the admin gate
(or, on a tenant with area limits seeded, by the area guard) and this file
would be asserting the wrong refusal.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.company import Company
from app.models.payroll_report import PayrollCheck, PayrollCheckLine, PayrollRegisterImport
from app.models.user import User
from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token
from tests.fixtures.payroll import register_fixture

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
ADMIN_UID = "register-admin"
UPLOAD = "/api/v1/payroll-reports/register/upload"


@pytest.fixture(scope="module")
def token():
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        rid = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='admin' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        if rid is None:
            pytest.skip("testco has no 'admin' role")
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": ADMIN_UID})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": ADMIN_UID})
        db.add(User(id=ADMIN_UID, email=f"{ADMIN_UID}@testco.example.com",
                    hashed_password="not-a-credential", first_name="Register",
                    last_name="Admin", role_id=rid, company_id=TESTCO_ID))
        db.commit()
        yield tenant_token(ADMIN_UID, TESTCO_ID)
    finally:
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": ADMIN_UID})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": ADMIN_UID})
        db.commit()
        db.close()


@pytest.fixture(autouse=True)
def clean_register_rows():
    """No check rows before or after. The idempotence test needs a known start."""
    from app.database import SessionLocal

    def wipe():
        db = SessionLocal()
        try:
            db.query(PayrollCheckLine).filter(
                PayrollCheckLine.tenant_id == TESTCO_ID).delete()
            db.query(PayrollCheck).filter(
                PayrollCheck.tenant_id == TESTCO_ID).delete()
            db.query(PayrollRegisterImport).filter(
                PayrollRegisterImport.tenant_id == TESTCO_ID).delete()
            db.commit()
        finally:
            db.close()

    wipe()
    yield
    wipe()


@pytest.fixture
def switch():
    """Turn the payroll data switch on for a test, and off again after."""
    from app.database import SessionLocal

    def put(value):
        db = SessionLocal()
        try:
            co = db.query(Company).filter(Company.id == TESTCO_ID).first()
            if value is None:
                s = co.settings
                s.pop(PAYROLL_DATA_ENABLED, None)
                co.settings_json = json.dumps(s)
            else:
                co.set_setting(PAYROLL_DATA_ENABLED, value)
            db.commit()
        finally:
            db.close()

    put(True)
    yield
    put(None)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def register_bytes():
    return register_fixture.build()


def _upload(client, token, content, filename="register.pdf"):
    return client.post(
        UPLOAD,
        headers={"Authorization": f"Bearer {token}", **HEADERS},
        files={"file": (filename, content, "application/pdf")},
    )


# ── the switch refuses first ─────────────────────────────────────────────────

def test_upload_is_refused_while_the_data_switch_is_off(client, token, register_bytes):
    r = _upload(client, token, register_bytes)
    assert r.status_code == 403, f"{r.status_code}: {r.text[:300]}"
    assert r.json()["detail"]["code"] == "payroll_data_disabled"


def test_nothing_is_stored_when_the_switch_refuses(client, token, register_bytes):
    """⚠️ The refusal is before the bytes are interpreted, not after."""
    from app.database import SessionLocal

    _upload(client, token, register_bytes)
    db = SessionLocal()
    try:
        assert db.query(PayrollCheck).filter(
            PayrollCheck.tenant_id == TESTCO_ID).count() == 0
        assert db.query(PayrollRegisterImport).filter(
            PayrollRegisterImport.tenant_id == TESTCO_ID).count() == 0
    finally:
        db.close()


# ── the happy path ───────────────────────────────────────────────────────────

def test_a_register_imports_its_checks_and_lines(client, token, register_bytes, switch):
    from app.database import SessionLocal

    r = _upload(client, token, register_bytes)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
    body = r.json()
    assert body["checks_parsed"] == register_fixture.EXPECTED_CHECKS
    assert body["checks_inserted"] == register_fixture.EXPECTED_CHECKS
    assert body["checks_duplicate"] == 0
    assert body["checks_failed"] == 0
    # ⚠️ Counted, not merely absent — a block-detection change that started
    # swallowing real checks would show up here as a number, not as silence.
    assert body["summary_blocks_skipped"] == register_fixture.EXPECTED_SUMMARY_BLOCKS

    db = SessionLocal()
    try:
        checks = db.query(PayrollCheck).filter(
            PayrollCheck.tenant_id == TESTCO_ID).all()
        assert {c.emp_id for c in checks} == register_fixture.EXPECTED_PEOPLE
        assert {c.person for c in checks} == set(
            register_fixture.EXPECTED_DISPLAY_NAMES.values())
        assert all(c.lines for c in checks), "a check with no lines is a parse fault"
    finally:
        db.close()


def test_a_negative_deduction_survives_the_round_trip(client, token, register_bytes, switch):
    """⚠️ Stored negative, read back negative.

    A reimbursement is printed as a NEGATIVE deduction. `abs()` anywhere on the
    way in or out would overstate total deductions by twice the amount and
    break the agreement with the printed total that validates the parse.
    """
    from app.database import SessionLocal
    from decimal import Decimal

    assert _upload(client, token, register_bytes).status_code == 200
    db = SessionLocal()
    try:
        line = (db.query(PayrollCheckLine)
                .filter(PayrollCheckLine.tenant_id == TESTCO_ID,
                        PayrollCheckLine.code == "CellReimb")
                .one())
        assert line.amount == Decimal("-20.00")
    finally:
        db.close()


def test_the_import_report_is_stored_and_not_only_returned(client, token,
                                                           register_bytes, switch):
    """The anomalies that need a person outlive the request that found them."""
    from app.database import SessionLocal

    body = _upload(client, token, register_bytes).json()
    assert [a["emp_id"] for a in body["report"]["union_salary_anomalies"]] == ["E04"]

    db = SessionLocal()
    try:
        record = db.query(PayrollRegisterImport).filter(
            PayrollRegisterImport.id == body["import_id"]).one()
        assert record.report == body["report"], "the stored report drifted from the response"
        assert [a["emp_id"] for a in record.report["union_salary_anomalies"]] == ["E04"]
        assert record.filename == "register.pdf"
        assert record.uploaded_by_user_id == ADMIN_UID
    finally:
        db.close()


# ── idempotence ──────────────────────────────────────────────────────────────

def test_uploading_the_same_register_twice_inserts_nothing_the_second_time(
        client, token, register_bytes, switch):
    """⚠️ THE ONE THAT MATTERS.

    Pulling a fresh year and uploading it is the intended workflow, so an
    overlapping upload is normal. If this were wrong every dues figure for the
    overlap would double, and the report would look entirely plausible.
    """
    from app.database import SessionLocal

    first = _upload(client, token, register_bytes).json()
    second = _upload(client, token, register_bytes).json()

    assert first["checks_inserted"] == register_fixture.EXPECTED_CHECKS
    assert second["checks_inserted"] == 0
    assert second["checks_duplicate"] == register_fixture.EXPECTED_CHECKS

    db = SessionLocal()
    try:
        assert db.query(PayrollCheck).filter(
            PayrollCheck.tenant_id == TESTCO_ID
        ).count() == register_fixture.EXPECTED_CHECKS
        # And no orphaned lines from a half-written second pass.
        assert db.query(PayrollCheckLine).filter(
            PayrollCheckLine.tenant_id == TESTCO_ID,
            PayrollCheckLine.code == "CellReimb",
        ).count() == 1
    finally:
        db.close()


def test_the_duplicate_count_is_not_simply_always_zero(client, token,
                                                       register_bytes, switch):
    """⚠️ A positive control on the test above.

    `checks_inserted == 0` on a second upload would also be true if the import
    silently did nothing at all — if the parse broke, or the switch flipped, or
    the file were unreadable. This pins the FIRST upload to a non-zero insert
    and the SECOND to a non-zero duplicate count, so "nothing happened twice"
    cannot pass as idempotence.
    """
    first = _upload(client, token, register_bytes).json()
    second = _upload(client, token, register_bytes).json()
    assert first["checks_inserted"] > 0
    assert second["checks_duplicate"] > 0
    assert first["checks_inserted"] == second["checks_duplicate"]


# ── refusals ─────────────────────────────────────────────────────────────────

def test_a_file_that_is_not_a_register_is_refused_with_422(client, token, switch):
    """Well-formed request, stated refusal — not a 500."""
    r = _upload(client, token, b"%PDF-1.4\nnot a register\n", filename="wrong.pdf")
    assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"


def test_an_empty_file_is_refused(client, token, switch):
    r = _upload(client, token, b"", filename="empty.pdf")
    assert r.status_code == 422


def test_an_unauthenticated_upload_is_refused(client, register_bytes):
    r = client.post(UPLOAD, headers=HEADERS,
                    files={"file": ("r.pdf", register_bytes, "application/pdf")})
    assert r.status_code in (401, 403), f"{r.status_code}: {r.text[:200]}"
