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


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.company import Company
from app.models.payroll_report import PayrollCheck, PayrollCheckLine, PayrollRegisterImport
from app.models.user import User
from tests._payroll_switch import payroll_switch
from tests._tenant import (
    TESTCO_ID,
    drop_company,
    ensure_company,
    make_canonical_tenant_fixture,
)
from tests._two_step import tenant_token
from tests.fixtures.payroll import register_fixture

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
ADMIN_UID = "register-admin"
UPLOAD = "/api/v1/payroll-reports/register/upload"
IMPORTS = "/api/v1/payroll-reports/register/imports"
PEOPLE_STATUS = "/api/v1/payroll-reports/register/people/status"


def H(token):
    """Auth + tenant headers, as `_upload` builds them inline."""
    return {"Authorization": f"Bearer {token}", **HEADERS}


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

    # ⚠️ ON FOR THE BODY, AS FOUND AFTERWARDS. This used to REMOVE the key on
    # the way out whatever the tenant held, which left every tenant's switch
    # off and blanked a live note mid-walk-through. See
    # `tests/_payroll_switch.py`.
    with payroll_switch(TESTCO_ID, True):
        yield


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


def test_the_report_counts_DISTINCT_PEOPLE_not_checks(client, token,
                                                      register_bytes, switch):
    """The figure the payroll setup page reports as "N checks for M people".

    ⚠️ **IT IS NOT A SECOND NAME FOR THE CHECK COUNT, AND THE FIXTURE CANNOT
    PROVE THAT ON ITS OWN.** Five checks for five people here, so `employees`
    and `checks_inserted` are the same number and an implementation returning
    either would pass this assertion alone. The duplicate test below is the
    discriminator: on a re-upload `checks_inserted` falls to 0 while the file
    still accounts for the same five people.
    """
    body = _upload(client, token, register_bytes).json()
    assert body["report"]["employees"] == len(register_fixture.EXPECTED_PEOPLE)


def test_the_people_count_survives_a_re_upload_that_inserts_nothing(
        client, token, register_bytes, switch):
    """⚠️ THE ONE THAT MAKES THE FIGURE ABOVE MEAN ANYTHING.

    An administrator re-running step 2 of the setup page must not be told the
    register covers "0 people" — it covers the whole roster whether or not it
    wrote a row. Counting only the inserted side would say zero, and zero would
    read as "this file was empty".
    """
    _upload(client, token, register_bytes)
    second = _upload(client, token, register_bytes).json()

    assert second["checks_inserted"] == 0
    assert second["checks_duplicate"] == register_fixture.EXPECTED_CHECKS
    assert second["report"]["employees"] == len(register_fixture.EXPECTED_PEOPLE)


# ── the import log: so a client that lost the response can CHECK ────────────
#
# ⚠️ ADDED 2026-11-17 BECAUSE A PAGE WAS GUESSING. The payroll setup page told
# an administrator "nothing has been changed" after an upload whose response it
# never received — a claim it could not make. There was no endpoint that could
# answer "did my import land?", so there was nothing for it to ask.


def test_the_import_log_is_empty_before_anything_is_uploaded(client, token):
    """⚠️ A POSITIVE CONTROL ON THE EMPTY CASE, and it is the case that matters.

    The page uses an ABSENCE from this log to tell James "nothing was saved, it
    is safe to try again". If this endpoint answered emptily for some unrelated
    reason — wrong tenant filter, a 403 swallowed by a client — that advice
    would be wrong in the dangerous direction.
    """
    r = client.get(IMPORTS, headers=H(token))
    assert r.status_code == 200, r.text[:200]
    assert r.json() == {"imports": [], "count": 0}


def test_an_upload_appears_in_the_log_with_its_counts(client, token,
                                                     register_bytes, switch):
    posted = _upload(client, token, register_bytes).json()
    r = client.get(IMPORTS, headers=H(token))
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    row = body["imports"][0]
    assert row["import_id"] == posted["import_id"]
    assert row["filename"] == "register.pdf"
    assert row["checks_inserted"] == register_fixture.EXPECTED_CHECKS
    assert row["pages"] == posted["pages"]
    # The stored report travels too, so a client that lost the upload response
    # can still show the findings rather than only the counts.
    assert row["report"]["employees"] == len(register_fixture.EXPECTED_PEOPLE)


def test_the_log_is_newest_first(client, token, register_bytes, switch):
    _upload(client, token, register_bytes, filename="first.pdf")
    _upload(client, token, register_bytes, filename="second.pdf")
    names = [i["filename"] for i in client.get(IMPORTS, headers=H(token)).json()["imports"]]
    assert names[:2] == ["second.pdf", "first.pdf"], names


def test_the_log_requires_the_payroll_read_permission(client, register_bytes):
    """Unauthenticated is refused. The log names files and counts, and an
    unauthenticated reader has no business with either."""
    r = client.get(IMPORTS, headers=HEADERS)
    assert r.status_code in (401, 403), r.status_code


def test_the_log_NEVER_shows_another_tenant_s_imports(client, token):
    """⚠️ **THE CROSS-TENANT GUARD, AND IT WAS MISSING UNTIL BREAK-TESTED.**

    When this endpoint was first written the three tests above all passed with
    the `tenant_id` filter DELETED — so there was no guard at all on a read
    that names payroll files and their check counts. The ordering test fired on
    its break; this one had no break to fire on, because the local database's
    other tenants hold no imports.

    A second tenant with a register import of its own is therefore CREATED
    here, which is the only way the assertion can discriminate. Without it the
    test would be the shape CLAUDE.md §11 names: green, in contact with
    nothing.
    """
    from app.database import SessionLocal

    other_id = "register-isolation-co"
    created = False
    db = SessionLocal()
    try:
        created = ensure_company(db, company_id=other_id,
                                 slug="register-isolation-co",
                                 name="Register Isolation Co")
        if not created:
            pytest.skip("could not create an isolated second tenant")
        db.add(PayrollRegisterImport(
            tenant_id=other_id, uploaded_by_user_id=None,
            filename="SOMEBODY_ELSES_REGISTER.pdf", pages=1,
            checks_parsed=1, checks_inserted=1, checks_failed=0,
            summary_blocks_skipped=0, report={}))
        db.commit()

        # POSITIVE CONTROL: the row really is there, so an empty answer below
        # cannot be an empty table masquerading as isolation.
        assert db.query(PayrollRegisterImport).filter(
            PayrollRegisterImport.tenant_id == other_id).count() == 1

        body = client.get(IMPORTS, headers=H(token)).json()
        names = [i["filename"] for i in body["imports"]]
        assert "SOMEBODY_ELSES_REGISTER.pdf" not in names, names
        assert body["count"] == 0, body
    finally:
        if created:
            db.query(PayrollRegisterImport).filter(
                PayrollRegisterImport.tenant_id == other_id).delete()
            db.commit()
            drop_company(db, company_id=other_id,
                         child_tables=("payroll_register_imports",))
        db.close()


# ── the roster status: a check that costs less than what it checks ──────────
#
# ⚠️ ADDED 2026-11-17. The reconcile answered **499 after 125 s** in a browser
# and committed 19 s later; the page promised to check what was saved and had
# nothing cheap enough to ask. The first fix proposed was "re-run the dry run
# and see whether `fill` proposals remain" — the SAME call, measured at 153 s.


def test_the_roster_status_is_four_counts_and_a_timestamp(client, token):
    r = client.get(PEOPLE_STATUS, headers=H(token))
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert set(body) == {"employees", "with_display_name", "union_members",
                         "last_reconciled_at"}
    # Shapes, not values — the counts depend on whatever this tenant holds.
    assert isinstance(body["employees"], int)
    assert isinstance(body["with_display_name"], int)
    assert isinstance(body["union_members"], int)


def test_the_roster_status_requires_a_signed_in_caller(client):
    r = client.get(PEOPLE_STATUS, headers=HEADERS)
    assert r.status_code in (401, 403), r.status_code


def test_the_roster_status_is_cheap(client, token):
    """⚠️ **THE POINT OF THE ENDPOINT, ASSERTED AS A QUERY COUNT.**

    It exists only because the obvious check was the thing that timed out. An
    implementation that grew a per-check loop would be useless for its one job
    and would look fine in every other test, so the cost is pinned here.

    Four counts and one audit lookup. The ceiling is deliberately loose — this
    guards against an N+1, not against one extra index scan.
    """
    from app.database import engine
    from sqlalchemy import event

    seen = []

    def before(conn, cur, stmt, params, ctx, many):
        seen.append(stmt)

    event.listen(engine, "before_cursor_execute", before)
    try:
        r = client.get(PEOPLE_STATUS, headers=H(token))
    finally:
        event.remove(engine, "before_cursor_execute", before)
    assert r.status_code == 200
    # POSITIVE CONTROL: the instrument saw something, so a low count below is
    # not an instrument that never fired.
    assert len(seen) > 0, "the query counter captured nothing"
    assert len(seen) <= 12, f"{len(seen)} statements for four counts:\n" + "\n".join(
        s.split(chr(10))[0][:80] for s in seen)


def test_the_reconcile_does_not_load_lines_one_check_at_a_time(client, token,
                                                               register_bytes,
                                                               switch):
    """⚠️ **THE N+1 THAT MADE THE RECONCILE TAKE TWO MINUTES.**

    Measured against production 2026-11-17, instrumented at the cursor:
    1,275 `payroll_check_lines` SELECTs — one per check — accounting for
    105 s of a 111 s run. Every fact the reconcile derives comes from a
    check's lines, so a lazy relationship means a round trip per check.

    `selectinload` makes it a fixed handful. Asserted as a count rather than a
    duration, because a duration on this hardware would be a flake.
    """
    from sqlalchemy import event

    from app.database import SessionLocal, engine
    from app.services.payroll.register_people import reconcile
    from tests.test_payroll_register_people import DEFAULT_RULES

    _upload(client, token, register_bytes)

    line_queries = []

    def before(conn, cur, stmt, params, ctx, many):
        if "payroll_check_lines" in stmt:
            line_queries.append(stmt)

    db = SessionLocal()
    event.listen(engine, "before_cursor_execute", before)
    try:
        proposals, facts = reconcile(
            db, tenant_id=TESTCO_ID, rules_for_date=lambda when: DEFAULT_RULES)
    finally:
        event.remove(engine, "before_cursor_execute", before)
        db.close()

    # POSITIVE CONTROL FIRST: the reconcile really did read the lines, so a low
    # count is eager loading rather than a reconcile that read nothing.
    assert facts, "the reconcile saw no employees — the count below proves nothing"
    assert len(line_queries) >= 1, "no line query at all; the instrument is blind"
    # One eager load, not one per check.
    assert len(line_queries) <= 3, (
        f"{len(line_queries)} line queries for "
        f"{register_fixture.EXPECTED_CHECKS} checks — the N+1 is back"
    )


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
