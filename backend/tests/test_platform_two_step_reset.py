"""The sole-admin lockout: the platform realm can clear tenant two-step.

Payroll 2, ruling 3. This is the LAST of four recovery steps — recovery codes,
then another tenant admin, then (nothing, because impersonation acting as her
hits the self-clear refusal), then this.

⚠️ **THE CROSS-REALM TESTS ARE THE LOAD-BEARING ONES.** An endpoint that can
clear any tenant user's second factor is the single most attractive thing in
this slice to reach from the wrong realm. Phase 8e.2 established four such tests
for the portal realm; the same shape applies here.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import two_step
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

EP = "/api/platform/admin/tenants/{c}/users/{u}/two-step/reset"
SUBJECT_UID = "pf-reset-subject"
TENANT_ADMIN_UID = "pf-reset-tenant-admin"
PLATFORM_UID = "pf-reset-platform-admin"


@pytest.fixture(scope="module")
def world():
    from app.database import SessionLocal
    from app.models.platform_user import PlatformUser
    from app.core.security import hash_password
    from app.services.role_service import seed_default_roles

    db = SessionLocal()
    try:
        seed_default_roles(db, TESTCO_ID)
        db.commit()
        for slug, uid in (("payroll", SUBJECT_UID), ("admin", TENANT_ADMIN_UID)):
            rid = db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug=:s LIMIT 1"
            ), {"c": TESTCO_ID, "s": slug}).scalar()
            if rid is None:
                pytest.skip(f"testco has no '{slug}' role")
            db.execute(text("DELETE FROM user_recovery_codes WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM user_two_step WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u OR entity_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.add(User(id=uid, email=f"{uid}@testco.example.com",
                        hashed_password="not-a-credential", first_name="Reset",
                        last_name=slug.title(), role_id=rid, company_id=TESTCO_ID))
        db.execute(text("DELETE FROM platform_users WHERE id=:u"), {"u": PLATFORM_UID})
        db.add(PlatformUser(id=PLATFORM_UID, email="pf-reset@bridgeable.internal",
                            hashed_password=hash_password("not-a-credential"),
                            first_name="Platform", last_name="Admin",
                            role="support", is_active=True))
        db.commit()
        yield
    finally:
        for uid in (SUBJECT_UID, TENANT_ADMIN_UID):
            db.execute(text("DELETE FROM user_recovery_codes WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM user_two_step WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u OR entity_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.execute(text("DELETE FROM audit_logs WHERE entity_id=:u"), {"u": SUBJECT_UID})
        db.execute(text("DELETE FROM platform_users WHERE id=:u"), {"u": PLATFORM_UID})
        db.commit()
        db.close()


@pytest.fixture(autouse=True)
def enrolled(world, monkeypatch):
    """Each test starts with the subject enrolled, so a clear is observable."""
    from app.database import SessionLocal
    monkeypatch.setenv("ENVIRONMENT", "dev")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == SUBJECT_UID).first()
        two_step.enrol_for_non_production(db, user)
        db.commit()
        assert two_step.is_enrolled(db, SUBJECT_UID), "fixture failed to enrol"
    finally:
        db.close()
    yield


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _platform_token():
    return create_access_token({"sub": PLATFORM_UID}, realm="platform")


def _ep(uid=SUBJECT_UID, company=TESTCO_ID):
    return EP.format(c=company, u=uid)


def test_a_platform_admin_can_clear_it(world, client):
    from app.database import SessionLocal

    r = client.post(_ep(), headers={"Authorization": f"Bearer {_platform_token()}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"user_id": SUBJECT_UID, "had_enrolment": True, "enrolled": False}

    db = SessionLocal()
    try:
        assert not two_step.is_enrolled(db, SUBJECT_UID)
    finally:
        db.close()


def test_it_is_idempotent(world, client):
    h = {"Authorization": f"Bearer {_platform_token()}"}
    client.post(_ep(), headers=h)
    again = client.post(_ep(), headers=h)
    assert again.status_code == 200, again.text
    assert again.json()["had_enrolment"] is False


# ── cross-realm isolation ────────────────────────────────────────────────

def test_a_tenant_token_is_refused(world, client):
    """⚠️ Even a tenant ADMIN's token, and even with the mfa claim."""
    r = client.post(_ep(), headers={
        "Authorization": f"Bearer {tenant_token(TENANT_ADMIN_UID, TESTCO_ID)}",
        "X-Company-Slug": "testco"})
    assert r.status_code == 401, r.text


def test_an_unauthenticated_request_is_refused(world, client):
    r = client.post(_ep())
    assert r.status_code in (401, 403), r.text


def test_the_subject_cannot_clear_her_own(world, client):
    """The whole reason this endpoint is in the platform realm."""
    r = client.post(_ep(), headers={
        "Authorization": f"Bearer {tenant_token(SUBJECT_UID, TESTCO_ID)}",
        "X-Company-Slug": "testco"})
    assert r.status_code == 401, r.text


def test_a_user_in_another_tenant_is_not_reachable(world, client):
    """`company_id` in the path means a mistyped user id cannot cross tenants."""
    r = client.post(_ep(company="some-other-company"),
                    headers={"Authorization": f"Bearer {_platform_token()}"})
    assert r.status_code == 404, r.text
    # and she is still enrolled
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        assert two_step.is_enrolled(db, SUBJECT_UID), "a 404 still cleared her"
    finally:
        db.close()


# ── the audit row ────────────────────────────────────────────────────────

def test_the_platform_actor_is_recorded_even_though_the_column_cannot_hold_it(
    world, client
):
    """`audit_logs.user_id` is FK'd to `users.id`, so it is NULL here.

    The actor lives in `changes`. This pins that the limitation is handled
    rather than silently dropping the attribution.
    """
    from app.database import SessionLocal

    client.post(_ep(), headers={"Authorization": f"Bearer {_platform_token()}"})
    db = SessionLocal()
    try:
        row = db.execute(text(
            "SELECT user_id, changes::text FROM audit_logs "
            "WHERE action='two_step_reset_by_platform' AND entity_id=:u "
            "ORDER BY created_at DESC LIMIT 1"), {"u": SUBJECT_UID}).first()
        assert row is not None, "the reset was not audited"
        assert row[0] is None, "the FK cannot hold a PlatformUser id"
        assert PLATFORM_UID in row[1], row[1]
        assert "pf-reset@bridgeable.internal" in row[1], row[1]
    finally:
        db.close()


def test_clearing_does_not_let_her_past_the_guard(world, client):
    """A reset is permission to enrol again, not an exemption."""
    client.post(_ep(), headers={"Authorization": f"Bearer {_platform_token()}"})
    r = client.get("/api/v1/payroll-reports/formats", headers={
        "Authorization": f"Bearer {tenant_token(SUBJECT_UID, TESTCO_ID, mfa=False)}",
        "X-Company-Slug": "testco"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "two_step_required", r.text
