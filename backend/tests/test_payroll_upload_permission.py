"""Who may upload payroll data — the 2026-11-13 ruling.

Until 2026-11-13 the uploads were admin-only, ruled so on 2026-11-03 because
"the payroll reviewer never needs to do it: in the finished shape it is the
background payroll job running under its own system actor". The premise was
that Opas would pull the hours. The Monday pull is designed and NOT built, so
until it exists Susan runs her own week from uploads.

⚠️ **THE "BRINGS PAY DATA INTO EXISTENCE" GATE DID NOT GO AWAY — IT MOVED TO
THE CONTROL THAT ACTUALLY IS ONE.** The payroll data switch stays admin-only,
is tenant-wide, and refuses every upload while it is off, admin included. That
is `test_no_upload_works_while_the_switch_is_off`, and it is the test that
makes the rest of this change safe.
"""
from __future__ import annotations

import io
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.permissions import (
    ACCOUNTANT_PAYROLL_PERMISSIONS,
    PAYROLL_DEFAULT_PERMISSIONS,
    get_all_permission_keys,
)
from app.main import app
from app.models.company import Company
from app.models.user import User
from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token
from tests.fixtures.payroll import register_fixture

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
UPLOAD = "/api/v1/payroll-reports/weeks/upload"
REGISTER = "/api/v1/payroll-reports/register/upload"
RECONCILE = "/api/v1/payroll-reports/register/people/reconcile"
SWITCH = "/api/v1/payroll-reports/settings/data-enabled"
RULES = "/api/v1/payroll-reports/rules"

#: slug -> user id
ACTORS = {"payroll": "perm-payroll", "admin": "perm-admin", "office": "perm-office"}


@pytest.fixture(scope="module")
def tokens():
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        out = {}
        for slug, uid in ACTORS.items():
            rid = db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug=:s LIMIT 1"
            ), {"c": TESTCO_ID, "s": slug}).scalar()
            if rid is None:
                pytest.skip(f"testco has no '{slug}' role")
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.add(User(id=uid, email=f"{uid}@testco.example.com",
                        hashed_password="not-a-credential", first_name="Perm",
                        last_name=slug.title(), role_id=rid, company_id=TESTCO_ID))
            out[slug] = uid
        db.commit()
        yield {slug: tenant_token(uid, TESTCO_ID) for slug, uid in out.items()}
    finally:
        for uid in ACTORS.values():
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()


@pytest.fixture
def switch_on():
    """Payroll data on for the test, and off again afterwards."""
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


@pytest.fixture(autouse=True)
def no_litter():
    """⚠️ These tests really upload, so they really write rows.

    The suite has a session-level litter check, and a test that leaves payroll
    checks behind makes the NEXT test's "0 rows" assertion meaningless. Cleared
    before and after.
    """
    from app.database import SessionLocal
    from app.models.payroll_report import (
        PayrollCheck,
        PayrollCheckLine,
        PayrollRegisterImport,
        PayrollWeek,
        PayrollWeekLine,
    )

    def wipe():
        db = SessionLocal()
        try:
            db.query(PayrollCheckLine).filter(
                PayrollCheckLine.tenant_id == TESTCO_ID).delete()
            db.query(PayrollCheck).filter(
                PayrollCheck.tenant_id == TESTCO_ID).delete()
            db.query(PayrollRegisterImport).filter(
                PayrollRegisterImport.tenant_id == TESTCO_ID).delete()
            for week in db.query(PayrollWeek).filter(
                    PayrollWeek.tenant_id == TESTCO_ID,
                    PayrollWeek.week_end_date == date(2026, 10, 31)).all():
                db.query(PayrollWeekLine).filter(
                    PayrollWeekLine.week_id == week.id).delete()
                db.delete(week)
            db.commit()
        finally:
            db.close()

    wipe()
    yield
    wipe()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def H(token):
    return {"Authorization": f"Bearer {token}", **HEADERS}


def _hours_csv() -> bytes:
    return (b"file_number,display_name,dept,reg_hrs,personal_hrs,ot_hrs\n"
            b"E01,Member E01,PRECAST,40,0,7\n")


def _post_hours(client, token):
    return client.post(UPLOAD, headers=H(token),
                       files={"file": ("w.csv", _hours_csv(), "text/csv")},
                       data={"week_number": 44, "week_end_date": "2026-10-31",
                             "format_key": "bridgeable_csv"})


def _post_register(client, token):
    return client.post(REGISTER, headers=H(token),
                       files={"file": ("r.pdf", register_fixture.build(),
                                       "application/pdf")})


# ── the permission itself ────────────────────────────────────────────────────

def test_the_key_is_in_the_catalogue_and_on_the_payroll_role():
    assert "payroll.upload" in get_all_permission_keys()
    assert "payroll.upload" in PAYROLL_DEFAULT_PERMISSIONS


def test_the_accountant_is_not_widened():
    """⚠️ r222 exists to PRESERVE what the old slug gate gave the accountant,
    and that gate never reached the uploads — they were admin-only. Granting
    upload here would widen the role, which is the mistake r222's own comment
    records for the `accounting` alias."""
    assert "payroll.upload" not in ACCOUNTANT_PAYROLL_PERMISSIONS


# ── Susan can now do her job ─────────────────────────────────────────────────

def test_the_payroll_user_can_upload_hours(client, tokens, switch_on):
    r = _post_hours(client, tokens["payroll"])
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:300]}"


def test_the_payroll_user_can_upload_the_register(client, tokens, switch_on):
    r = _post_register(client, tokens["payroll"])
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"


def test_the_payroll_user_can_read_the_rulebook(client, tokens):
    """She needs to see which rules produced a figure she is approving."""
    r = client.get(RULES, headers=H(tokens["payroll"]))
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"


def test_there_is_no_rule_write_endpoint_at_all():
    """⚠️ "Rule edits stay admin-only" is satisfied structurally: there is no
    write endpoint to gate. Rule sets are seeded by script. If one is ever
    added, this fails and whoever adds it has to decide the gate deliberately.
    """
    from app.api.routes.payroll_reports import router

    writes = [r for r in router.routes
              if getattr(r, "path", "") == "/rules"
              and set(getattr(r, "methods", set())) - {"GET", "HEAD", "OPTIONS"}]
    assert writes == [], writes


# ── what stays admin-only ────────────────────────────────────────────────────

@pytest.mark.parametrize("path, verb", [
    (RECONCILE, "post"),
    (SWITCH, "get"),
    (SWITCH, "put"),
])
def test_the_payroll_user_is_refused_the_admin_controls(client, tokens, path, verb):
    call = getattr(client, verb)
    kwargs = {"headers": H(tokens["payroll"])}
    if verb in ("post", "put"):
        kwargs["data"] = {"enabled": "true", "apply": "false"}
    r = call(path, **kwargs)
    assert r.status_code == 403, f"{path} {verb}: {r.status_code} {r.text[:200]}"
    assert "Admin" in r.text or "admin" in r.text


# ── ⚠️ the gate that makes the whole change safe ─────────────────────────────

def test_no_upload_works_while_the_switch_is_off(client, tokens):
    """⚠️ THE LOAD-BEARING TEST.

    The data switch is now the control carrying "may this tenant hold payroll
    data at all". It is admin-only, tenant-wide, and off by default — and while
    it is off NOTHING uploads, for anyone. If this ever passed only for the
    payroll role, widening the upload permission would have given away the
    gate rather than moved it.
    """
    for who in ("payroll", "admin"):
        for post in (_post_hours, _post_register):
            r = post(client, tokens[who])
            assert r.status_code == 403, f"{who}: {r.status_code} {r.text[:160]}"
            assert r.json()["detail"]["code"] == "payroll_data_disabled"


def test_the_admin_can_still_upload_when_the_switch_is_on(client, tokens, switch_on):
    """A positive control: the switch-off test above must be about the SWITCH,
    not about uploads being broken for everyone."""
    assert _post_register(client, tokens["admin"]).status_code == 200


# ── a user outside the payroll area ──────────────────────────────────────────
#
# ⚠️ These tests build their OWN area-limited role rather than borrowing a
# seeded one. The first version used the `office` role and passed on my machine
# because this dev database carries the parked Phase B branch's hand-run area
# seed. On a clean database `office` is NULL-areas — `test_area_limited_roles`
# asserts that it is — so the test was reading a local accident as the regime
# and CI was right to fail it. The `area-probe-` id prefix is the exemption
# `test_no_undeclared_role_carries_areas` already allows for exactly this.

PROBE_ROLE_ID = "area-probe-perm-upload"
PROBE_USER_ID = "area-probe-perm-user"


@pytest.fixture
def out_of_area_token():
    """A role limited to `scheduling` that HOLDS every payroll permission.

    Granting the permissions is the point. If the probe held none of them it
    would be refused either way and the test could not tell the area guard from
    the permission guard — which is the one thing it exists to show.
    """
    from app.database import SessionLocal
    from app.models.role import Role
    from app.models.role_permission import RolePermission

    db = SessionLocal()

    def wipe():
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": PROBE_USER_ID})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": PROBE_USER_ID})
        db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": PROBE_ROLE_ID})
        db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": PROBE_ROLE_ID})

    try:
        wipe()
        db.add(Role(id=PROBE_ROLE_ID, company_id=TESTCO_ID,
                    name="Area Probe Scheduling", slug="area-probe-upload",
                    is_system=False, is_active=True,
                    limited_to_areas=["scheduling"]))
        db.flush()
        # ⚠️ via the ORM: `role_permissions.id` is a primary key with a
        # PYTHON-side default, so a raw INSERT leaves it null.
        for key in PAYROLL_DEFAULT_PERMISSIONS:
            db.add(RolePermission(role_id=PROBE_ROLE_ID, permission_key=key))
        db.add(User(id=PROBE_USER_ID, email="area-probe-upload@testco.example.com",
                    hashed_password="not-a-credential", first_name="Area",
                    last_name="Probe", role_id=PROBE_ROLE_ID, company_id=TESTCO_ID))
        db.commit()

        # Control: the probe must really be limited, and really hold the upload
        # permission. Either one silently missing turns the assertions below
        # into a test of nothing.
        assert db.execute(text(
            "SELECT limited_to_areas IS NOT NULL FROM roles WHERE id=:r"
        ), {"r": PROBE_ROLE_ID}).scalar() is True, "probe role is not area-limited"
        assert db.execute(text(
            "SELECT count(*) FROM role_permissions "
            "WHERE role_id=:r AND permission_key='payroll.upload'"
        ), {"r": PROBE_ROLE_ID}).scalar() == 1, "probe role lacks payroll.upload"

        yield tenant_token(PROBE_USER_ID, TESTCO_ID)
    finally:
        wipe()
        db.commit()
        db.close()


@pytest.mark.parametrize("path", [UPLOAD, REGISTER, RULES, RECONCILE])
def test_a_user_outside_the_payroll_area_is_refused_before_any_permission(
        client, out_of_area_token, switch_on, path):
    """⚠️ The AREA guard answers first, and says so.

    The probe holds `payroll.upload`, `payroll.view` and `payroll.approve`, so a
    permission refusal here would be wrong on the merits. What refuses it is the
    area limit, and the guard names it — `area_restricted`, requested area
    `payroll` — which is also what makes a support call one request long.
    """
    r = (client.get(path, headers=H(out_of_area_token)) if path == RULES
         else client.post(path, headers=H(out_of_area_token),
                          data={"week_number": 44, "week_end_date": "2026-10-31"},
                          files={"file": ("x.pdf", b"%PDF-1.4\n", "application/pdf")}))
    assert r.status_code == 403, f"{path}: {r.status_code}"
    detail = r.json().get("detail")
    assert isinstance(detail, dict) and detail.get("code") == "area_restricted", detail
    assert detail.get("requested_area") == "payroll"
    assert detail.get("allowed_areas") == ["scheduling"]
