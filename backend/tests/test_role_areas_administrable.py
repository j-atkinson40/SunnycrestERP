"""Areas can be ADMINISTERED, not only seeded.

⚠️ **THE BLOCKER THIS CLOSES, AND IT WAS A DANGEROUS ONE.** `limited_to_areas`
shipped in r221 with no way to set it through the API: `RoleCreate` and
`RoleUpdate` carried no such field, and `seed_default_roles` was its only writer.
So a "Payroll" role built in the admin screen got `limited_to_areas = NULL` —
NOT area-limited — and its holder reached all 1063 endpoints with no per-user
gate. It would have looked correct in the UI. Measured on production: zero roles
with slug `payroll` existed, so building one by hand was the only route available
to an admin.

Two halves, and the second is why an unsettable column was worse than no column:
areas you can seed but never manage mean James cannot hand an area to anyone.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.areas import KNOWN_AREAS
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
ADMIN_UID = "areaadmin-admin"
SUBJECT_UID = "areaadmin-subject"
SUBJECT_SLUG = "areaadmin-subject-role"
ROLES = "/api/v1/roles"

#: A representative slice of the 20-call probe. Short on purpose — the full
#: 20 are covered in test_area_limited_roles; what matters here is that an
#: ADMIN-DRIVEN change flips them.
PROBE = [
    "/api/v1/journal-entries/entries",
    "/api/v1/price-management/versions",
    "/api/v1/companies",
    "/api/v1/fh/cases",
    "/api/v1/email/threads",
]


@pytest.fixture(scope="module")
def admin_token():
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        rid = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='admin' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        if rid is None:
            pytest.skip("testco has no admin role")
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": ADMIN_UID})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": ADMIN_UID})
        db.add(User(id=ADMIN_UID, email="areaadmin-admin@testco.example.com",
                    hashed_password="not-a-credential", first_name="Area",
                    last_name="Admin", role_id=rid, company_id=TESTCO_ID))
        db.commit()
        yield create_access_token({"sub": ADMIN_UID, "company_id": TESTCO_ID})
    finally:
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": ADMIN_UID})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": ADMIN_UID})
        db.commit()
        db.close()


@pytest.fixture
def subject(admin_token):
    """An UNLIMITED role with a user on it, created through the API."""
    from app.database import SessionLocal

    db = SessionLocal()

    def purge():
        ids = [r[0] for r in db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug=:s"
        ), {"c": TESTCO_ID, "s": SUBJECT_SLUG}).fetchall()]
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": SUBJECT_UID})
        for rid in ids:
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": rid})
            db.execute(text("DELETE FROM audit_logs WHERE entity_type='role' AND entity_id=:r"),
                       {"r": rid})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": rid})
        db.commit()

    try:
        purge()
        c = TestClient(app)
        r = c.post(ROLES, headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                   json={"name": "Area Subject", "slug": SUBJECT_SLUG,
                         "permission_keys": ["payroll.view"]})
        assert r.status_code == 201, r.text[:300]
        role_id = r.json()["id"]
        db.add(User(id=SUBJECT_UID, email="areaadmin-subject@testco.example.com",
                    hashed_password="not-a-credential", first_name="Area",
                    last_name="Subject", role_id=role_id, company_id=TESTCO_ID))
        db.commit()
        yield {"role_id": role_id,
               "token": create_access_token({"sub": SUBJECT_UID, "company_id": TESTCO_ID})}
    finally:
        purge()
        db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _probe(client, token):
    return {p: client.get(p, headers={"Authorization": f"Bearer {token}", **HEADERS}).status_code
            for p in PROBE}


# ------------------------------------------------------ validation


def test_an_unknown_area_key_is_rejected_with_422(client, admin_token):
    """⚠️ BREAK TEST. A typo'd key would produce a role limited to an area
    nothing is tagged with — locked out of everything, and looking deliberate."""
    r = client.post(ROLES, headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                    json={"name": "Typo", "slug": "areaadmin-typo",
                          "limited_to_areas": ["payrol"]})
    assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"
    assert "payrol" in r.text and "payroll" in r.text, "the error must name both"


def test_a_known_area_is_accepted(client, admin_token):
    from app.database import SessionLocal
    r = client.post(ROLES, headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                    json={"name": "Known", "slug": "areaadmin-known",
                          "limited_to_areas": sorted(KNOWN_AREAS)})
    assert r.status_code == 201, r.text[:300]
    assert r.json()["limited_to_areas"] == sorted(KNOWN_AREAS)
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": r.json()["id"]})
        db.execute(text("DELETE FROM audit_logs WHERE entity_type='role' AND entity_id=:r"),
                   {"r": r.json()["id"]})
        db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": r.json()["id"]})
        db.commit()
    finally:
        db.close()


def test_the_admin_role_cannot_be_area_limited(client, admin_token):
    """It holds a permission wildcard; limiting it yields a role that passes
    every permission check and is refused by the area guard — and is a fast way
    to lock a tenant out of its own settings."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        rid = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='admin' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
    finally:
        db.close()
    r = client.patch(f"{ROLES}/{rid}",
                     headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                     json={"limited_to_areas": ["payroll"]})
    assert r.status_code == 400, f"{r.status_code}: {r.text[:200]}"
    assert "admin role cannot be limited" in r.text


# ------------------------------- the admin change actually takes effect


def test_an_admin_limiting_a_role_sends_its_user_to_403(client, admin_token, subject):
    """⚠️ THE WHOLE POINT, END TO END. Before: her probe calls succeed. After an
    ADMIN sets areas through the API: every one is refused by the area guard."""
    before = _probe(client, subject["token"])
    assert any(s == 200 for s in before.values()), (
        f"the subject must start with real reach or this proves nothing: {before}"
    )

    r = client.patch(f"{ROLES}/{subject['role_id']}",
                     headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                     json={"limited_to_areas": ["payroll"]})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["limited_to_areas"] == ["payroll"]

    after = _probe(client, subject["token"])
    assert all(s == 403 for s in after.values()), f"not all refused: {after}"


def test_clearing_the_limit_restores_her_reach(client, admin_token, subject):
    """⚠️ EXPLICIT `null` MEANS UNLIMITED; OMITTING THE FIELD MEANS LEAVE IT.
    A limit you can set but never lift is a trap, not a control — which is why
    the service reads `model_fields_set` rather than testing for None."""
    client.patch(f"{ROLES}/{subject['role_id']}",
                 headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                 json={"limited_to_areas": ["payroll"]})
    assert all(s == 403 for s in _probe(client, subject["token"]).values())

    r = client.patch(f"{ROLES}/{subject['role_id']}",
                     headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                     json={"limited_to_areas": None})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["limited_to_areas"] is None
    after = _probe(client, subject["token"])
    assert any(s == 200 for s in after.values()), f"reach not restored: {after}"


def test_omitting_the_field_leaves_the_areas_alone(client, admin_token, subject):
    client.patch(f"{ROLES}/{subject['role_id']}",
                 headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                 json={"limited_to_areas": ["payroll"]})
    r = client.patch(f"{ROLES}/{subject['role_id']}",
                     headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                     json={"name": "Renamed Only"})
    assert r.status_code == 200
    assert r.json()["limited_to_areas"] == ["payroll"], "a rename cleared the limit"


# ------------------------------------- a limited role never looks unlimited


def test_the_role_list_shows_which_roles_are_limited(client, admin_token, subject):
    client.patch(f"{ROLES}/{subject['role_id']}",
                 headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                 json={"limited_to_areas": ["payroll"]})
    r = client.get(ROLES, headers={"Authorization": f"Bearer {admin_token}", **HEADERS})
    assert r.status_code == 200
    by_slug = {x["slug"]: x for x in r.json()}
    assert "limited_to_areas" in by_slug[SUBJECT_SLUG], (
        "the list omits limited_to_areas, so a limited role and an unlimited one "
        "look the same to an admin"
    )
    assert by_slug[SUBJECT_SLUG]["limited_to_areas"] == ["payroll"]
    assert by_slug["admin"]["limited_to_areas"] is None
    # The seeded payroll role must advertise its limit too.
    if "payroll" in by_slug:
        assert by_slug["payroll"]["limited_to_areas"] == ["payroll"]


def test_the_area_change_is_audited_with_before_and_after(client, admin_token, subject):
    import json as _json
    from app.database import SessionLocal

    client.patch(f"{ROLES}/{subject['role_id']}",
                 headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                 json={"limited_to_areas": ["payroll"]})
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT changes FROM audit_logs WHERE entity_type='role' AND entity_id=:r "
            "AND action='updated' ORDER BY created_at DESC LIMIT 1"
        ), {"r": subject["role_id"]}).fetchall()
    finally:
        db.close()
    assert rows, "limiting a role left no audit row"
    ch = rows[0][0]
    if isinstance(ch, str):
        ch = _json.loads(ch)
    assert "limited_to_areas" in ch, f"areas not in the audit changes: {ch}"
    assert ["payroll"] in ch["limited_to_areas"].values()
