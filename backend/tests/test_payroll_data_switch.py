"""The payroll data switch: off by default, and it refuses rather than warns.

⚠️ **WHAT THIS REPLACES.** Payroll 1 loaded no payroll data because we AGREED not
to. All seven payroll endpoints gate on `payroll.view` and three of them WRITE, so
anyone holding that permission could import a Payentry export before tenant
invites and two-step sign-in existed. An agreement only a person can keep is the
shape CLAUDE.md names over and over: a rule that holds until the day it matters.

So the empty state is now structural. Absent/NULL and `false` both mean DISABLED
— the one place in this arc where absent means something rather than nothing,
because the safe reading of "nobody has said" is "not allowed".
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.main import app
from app.models.company import Company
from app.models.user import User
from app.services.payroll.data_gate import (
    PAYROLL_DATA_ENABLED,
    is_payroll_data_enabled,
)
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
ADMIN_UID = "switch-admin"
ACCT_UID = "switch-accountant"
UPLOAD = "/api/v1/payroll-reports/weeks/upload"
SETTING = "/api/v1/payroll-reports/settings/data-enabled"


def _csv() -> bytes:
    buf = io.StringIO()
    buf.write("file_number,display_name,dept,reg_hrs,personal_hrs,ot_hrs\n")
    buf.write("E01,Member E01,PRECAST,40,0,7\n")
    return buf.getvalue().encode()


@pytest.fixture(scope="module")
def tokens():
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ids = {}
        for slug, uid in (("admin", ADMIN_UID), ("accountant", ACCT_UID)):
            rid = db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug=:s LIMIT 1"
            ), {"c": TESTCO_ID, "s": slug}).scalar()
            if rid is None:
                pytest.skip(f"testco has no '{slug}' role")
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.add(User(id=uid, email=f"{uid}@testco.example.com",
                        hashed_password="not-a-credential", first_name="Switch",
                        last_name=slug.title(), role_id=rid, company_id=TESTCO_ID))
            ids[slug] = create_access_token({"sub": uid, "company_id": TESTCO_ID})
        db.commit()
        yield ids
    finally:
        for uid in (ADMIN_UID, ACCT_UID):
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()


@pytest.fixture(autouse=True)
def _switch_off():
    """Every test starts from the default-off state and restores it."""
    from app.database import SessionLocal

    def put(value):
        db = SessionLocal()
        try:
            co = db.query(Company).filter(Company.id == TESTCO_ID).first()
            if value is None:
                s = co.settings
                s.pop(PAYROLL_DATA_ENABLED, None)
                import json
                co.settings_json = json.dumps(s)
            else:
                co.set_setting(PAYROLL_DATA_ENABLED, value)
            db.commit()
        finally:
            db.close()

    put(None)
    yield put
    put(None)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


#: ⚠️ UPLOADS GO AS AN **ADMIN**, SINCE THE 2026-11-03 SPLIT. `POST /weeks/upload`
#: is admin-only now, so uploading as the accountant would be refused by the ADMIN
#: gate and this file would be asserting the wrong refusal — green for a reason
#: unrelated to the switch it exists to test. The accountant's own refusal is
#: asserted once, below, precisely so the two are told apart.
def _upload(client, token):
    return client.post(UPLOAD, headers={"Authorization": f"Bearer {token}", **HEADERS},
                       files={"file": ("w.csv", _csv(), "text/csv")},
                       data={"week_number": 44, "week_end_date": "2026-10-31",
                             "format_key": "bridgeable_csv"})


# ------------------------------------------------------------- default off


def test_absent_setting_means_disabled(tokens):
    """NULL is not "unknown" here — it is "no"."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.id == TESTCO_ID).first()
        assert PAYROLL_DATA_ENABLED not in co.settings
        assert is_payroll_data_enabled(co) is False
    finally:
        db.close()


def test_upload_is_refused_while_the_switch_is_off(client, tokens):
    """⚠️ THE BREAK TEST. Before the switch this returned 201 and created a week.
    Measured: adding the gate turned 24 of the 26 payroll e2e tests red until
    that suite enabled the switch deliberately."""
    r = _upload(client, tokens["admin"])
    assert r.status_code == 403, f"{r.status_code}: {r.text[:200]}"
    detail = r.json()["detail"]
    assert detail["code"] == "payroll_data_disabled", (
        f"refused, but not by the SWITCH: {detail}"
    )
    assert detail["setting"] == PAYROLL_DATA_ENABLED
    assert "two-step" in detail["message"], "the message must say what unblocks it"


def test_no_week_was_created_by_the_refused_upload(client, tokens):
    """A refusal that still wrote a row would be worse than no refusal."""
    from app.database import SessionLocal
    _upload(client, tokens["admin"])
    db = SessionLocal()
    try:
        n = db.execute(text(
            "SELECT count(*) FROM payroll_weeks WHERE tenant_id=:c"
        ), {"c": TESTCO_ID}).scalar()
    finally:
        db.close()
    assert n == 0, f"{n} payroll week(s) exist after a refused upload"


def test_only_true_enables_it(_switch_off, tokens):
    """`is True`, not truthiness. A stray "false" string or a 1 must not arm it."""
    from app.database import SessionLocal

    for value, expected in ((True, True), (False, False), ("true", False), (1, False)):
        _switch_off(value)
        db = SessionLocal()
        try:
            co = db.query(Company).filter(Company.id == TESTCO_ID).first()
            assert is_payroll_data_enabled(co) is expected, f"value={value!r}"
        finally:
            db.close()


def test_upload_is_allowed_once_the_switch_is_on(client, tokens, _switch_off):
    """⚠️ THE ALLOW PATH. Without it the gate could be a blanket refusal and every
    test above would still pass — which is an outage, not a feature."""
    _switch_off(True)
    r = _upload(client, tokens["admin"])
    assert r.status_code != 403, f"still refused with the switch on: {r.text[:200]}"
    assert r.status_code == 201, f"{r.status_code}: {r.text[:300]}"

    # clean the week this created
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text(
            "DELETE FROM payroll_week_results WHERE week_id IN "
            "(SELECT id FROM payroll_weeks WHERE tenant_id=:c)"), {"c": TESTCO_ID})
        db.execute(text(
            "DELETE FROM payroll_week_lines WHERE week_id IN "
            "(SELECT id FROM payroll_weeks WHERE tenant_id=:c)"), {"c": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_weeks WHERE tenant_id=:c"), {"c": TESTCO_ID})
        db.commit()
    finally:
        db.close()


# ------------------------------------------------------- who may change it


def test_reading_the_switch_requires_admin_not_payroll_view(client, tokens):
    """⚠️ NARROWER THAN THE REST OF THE MODULE, ON PURPOSE. Whether payroll data
    may exist at all is a tenant decision, not the payroll reviewer's."""
    r = client.get(SETTING, headers={"Authorization": f"Bearer {tokens['accountant']}",
                                     **HEADERS})
    assert r.status_code == 403, f"accountant could read the switch: {r.status_code}"

    r2 = client.get(SETTING, headers={"Authorization": f"Bearer {tokens['admin']}",
                                      **HEADERS})
    assert r2.status_code == 200, r2.text[:200]
    assert r2.json() == {"setting": PAYROLL_DATA_ENABLED, "enabled": False}


def test_an_accountant_cannot_turn_it_on(client, tokens):
    r = client.put(SETTING, headers={"Authorization": f"Bearer {tokens['accountant']}",
                                     **HEADERS}, data={"enabled": "true"})
    assert r.status_code == 403


def test_an_admin_turning_it_on_is_audited_with_before_and_after(client, tokens):
    from app.database import SessionLocal
    import json as _json

    r = client.put(SETTING, headers={"Authorization": f"Bearer {tokens['admin']}",
                                     **HEADERS}, data={"enabled": "true"})
    assert r.status_code == 200, r.text[:200]
    assert r.json() == {"setting": PAYROLL_DATA_ENABLED, "enabled": True, "changed": True}

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT changes, user_id FROM audit_logs "
            "WHERE action='payroll_data_enabled_changed' AND company_id=:c "
            "ORDER BY created_at DESC LIMIT 1"
        ), {"c": TESTCO_ID}).fetchall()
    finally:
        db.close()
    assert rows, "turning the switch on left no audit row"
    changes = rows[0][0]
    if isinstance(changes, str):
        changes = _json.loads(changes)
    assert changes[PAYROLL_DATA_ENABLED] == {"before": False, "after": True}
    assert rows[0][1] == ADMIN_UID, "the actor must be named"


def test_a_no_op_write_changes_nothing_and_records_nothing(client, tokens, _switch_off):
    """An audit trail where every save writes a row is one a reader skims."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        before = db.execute(text(
            "SELECT count(*) FROM audit_logs WHERE action='payroll_data_enabled_changed' "
            "AND company_id=:c"), {"c": TESTCO_ID}).scalar()
    finally:
        db.close()

    r = client.put(SETTING, headers={"Authorization": f"Bearer {tokens['admin']}",
                                     **HEADERS}, data={"enabled": "false"})
    assert r.status_code == 200
    assert r.json()["changed"] is False

    db = SessionLocal()
    try:
        after = db.execute(text(
            "SELECT count(*) FROM audit_logs WHERE action='payroll_data_enabled_changed' "
            "AND company_id=:c"), {"c": TESTCO_ID}).scalar()
    finally:
        db.close()
    assert after == before


def test_the_switch_is_per_company():
    """Turning it on for one tenant must not arm another."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        others = db.execute(text(
            "SELECT count(*) FROM companies "
            "WHERE id <> :c AND settings_json IS NOT NULL "
            "AND settings_json::jsonb->>'payroll_data_enabled' = 'true'"
        ), {"c": TESTCO_ID}).scalar()
    finally:
        db.close()
    assert others == 0, f"{others} other tenant(s) have payroll data enabled"


def test_the_accountant_is_refused_upload_by_the_ADMIN_gate_not_the_switch(
    client, tokens, _switch_off
):
    """⚠️ TWO REFUSALS ON ONE ENDPOINT, AND WHICH ONE FIRED MATTERS.

    With the switch ON, an accountant is still refused — by `require_admin`,
    because loading hours is not the payroll reviewer's job (2026-11-03 ruling).
    Asserting the DISTINCTION is what keeps this file honest: without it, the
    switch tests could pass while the switch did nothing, simply because every
    caller happened to be admin-refused.
    """
    _switch_off(True)
    r = _upload(client, tokens["accountant"])
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail == "Admin access required", (
        f"expected the admin refusal, got {detail!r}"
    )
    assert not (isinstance(detail, dict) and detail.get("code") == "payroll_data_disabled")
