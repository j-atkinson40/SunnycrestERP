"""Role writes leave an audit row, with the permission set before and after.

⚠️ **A CORRECTION TO THE 2026-11-03 FINDINGS, AND IT IS MINE.** That
investigation reported "roles.py has zero log_action calls, so changing what a
role may do is NOT audited". The first half is true — `app/api/routes/roles.py`
has none. The conclusion is false: `app/services/role_service.py` has FOUR, and
`set_role_permissions` already recorded old and new permission sets
(role_service.py:389). I measured the route file and made a claim about role
WRITES, which is a different population — the same constructed-scope error the
canon names, committed inside an investigation about measurement.

So role writes were already audited. What was actually missing, and is what this
file now pins:

  - `delete_role` recorded only name and slug — not the permission set it held,
    and after a delete there is nothing left to read;
  - a permission change and a rename both logged as action "updated", so the one
    change that moves a security boundary was indistinguishable in the list;
  - `limited_to_areas` (r221) was recorded nowhere, and for an area-limited role
    that field is MORE decisive than the permission list.

The enrichment is in the service, where the existing calls are. Adding a second
set in the route would have double-logged every write — which is how this was
caught: the first draft of this test found two "created" rows.

For an area-limited role the permission set IS the security boundary, so a change
to it is exactly the change that needs a record (James, 2026-11-03).

Full sets are stored alongside `granted`/`revoked` deltas rather than instead of
them: a reader wants to know what was granted without diffing two 200-item
lists, and wants the full set to be able to reconstruct the boundary as it stood.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
ADMIN_UID = "roleaudit-admin"
SLUG = "roleaudit-probe"


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
        # ⚠️ AUDIT ROWS BEFORE THE USER, AT BOTH ENDS. A previous run's audit
        # rows reference this actor, and `audit_logs.user_id` -> `users.id`
        # carries no ON DELETE — so the pre-delete raises on residue from a
        # failed run, turning every test in the file into a SETUP ERROR. An
        # erroring test asserts nothing, which is why this is ordered rather
        # than hoped about.
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": ADMIN_UID})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": ADMIN_UID})
        db.add(User(id=ADMIN_UID, email="roleaudit-admin@testco.example.com",
                    hashed_password="not-a-credential", first_name="Role",
                    last_name="Audit", role_id=rid, company_id=TESTCO_ID))
        db.commit()
        yield create_access_token({"sub": ADMIN_UID, "company_id": TESTCO_ID})
    finally:
        # ⚠️ AUDIT ROWS FIRST. `audit_logs.user_id` -> `users.id` carries no
        # ON DELETE, so deleting the actor raises while its audit rows exist —
        # which is the constraint doing its job: an audit row whose actor had
        # been deleted from under it would name nobody. Same shape as
        # `payroll_weeks.approved_by`.
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": ADMIN_UID})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": ADMIN_UID})
        db.commit()
        db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_probe_rows():
    """Remove the probe role and its audit rows around every test."""
    from app.database import SessionLocal

    def purge():
        db = SessionLocal()
        try:
            ids = [r[0] for r in db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug=:s"
            ), {"c": TESTCO_ID, "s": SLUG}).fetchall()]
            for rid in ids:
                db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": rid})
                db.execute(text("DELETE FROM audit_logs WHERE entity_type='role' AND entity_id=:r"),
                           {"r": rid})
                db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": rid})
            db.commit()
        finally:
            db.close()

    purge()
    yield
    purge()


def _audit_rows(role_id: str, action: str | None = None) -> list[dict]:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        sql = ("SELECT action, changes, user_id FROM audit_logs "
               "WHERE entity_type='role' AND entity_id=:r")
        params = {"r": role_id}
        if action:
            sql += " AND action=:a"
            params["a"] = action
        rows = db.execute(text(sql + " ORDER BY created_at"), params).fetchall()
    finally:
        db.close()
    return [{"action": r[0],
             "changes": json.loads(r[1]) if isinstance(r[1], str) else r[1],
             "user_id": r[2]} for r in rows]


def _create(client, token, perms=("payroll.view",)):
    r = client.post("/api/v1/roles",
                    headers={"Authorization": f"Bearer {token}", **HEADERS},
                    json={"name": "Role Audit Probe", "slug": SLUG,
                          "description": "probe", "permission_keys": list(perms)})
    assert r.status_code == 201, f"{r.status_code}: {r.text[:300]}"
    return r.json()["id"]


def test_creating_a_role_is_recorded_with_its_starting_permissions(client, admin_token):
    rid = _create(client, admin_token, perms=("payroll.view", "payroll.approve"))
    rows = _audit_rows(rid, "created")
    assert len(rows) == 1, f"expected one 'created' row, got {len(rows)}"
    ch = rows[0]["changes"]
    assert ch["slug"] == SLUG
    assert ch["permission_keys"]["before"] == []
    assert set(ch["permission_keys"]["after"]) == {"payroll.view", "payroll.approve"}
    assert ch["limited_to_areas"] == {"before": None, "after": None}
    assert rows[0]["user_id"] == ADMIN_UID, "the actor must be named"


def test_changing_a_roles_permissions_records_both_sets_and_the_delta(client, admin_token):
    """⚠️ THE ONE THAT MATTERS. This is the change that moves a security
    boundary, and before today it left no trace at all."""
    rid = _create(client, admin_token, perms=("payroll.view",))
    r = client.put(f"/api/v1/roles/{rid}/permissions",
                   headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                   json={"permission_keys": ["payroll.view", "payroll.approve",
                                             "financials.view"]})
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"

    rows = _audit_rows(rid, "permissions_changed")
    assert len(rows) == 1, (
        f"expected exactly one 'permissions_changed' row, got {len(rows)} — two "
        f"means the route and the service are both logging"
    )
    ch = rows[0]["changes"]
    assert ch["permission_keys"]["before"] == ["payroll.view"]
    assert ch["permission_keys"]["after"] == sorted(
        ["payroll.view", "payroll.approve", "financials.view"])
    assert ch["granted"] == sorted(["payroll.approve", "financials.view"])
    assert ch["revoked"] == []


def test_revoking_is_recorded_as_revoked(client, admin_token):
    rid = _create(client, admin_token, perms=("payroll.view", "payroll.approve"))
    r = client.put(f"/api/v1/roles/{rid}/permissions",
                   headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                   json={"permission_keys": ["payroll.view"]})
    assert r.status_code == 200
    ch = _audit_rows(rid, "permissions_changed")[0]["changes"]
    assert ch["revoked"] == ["payroll.approve"]
    assert ch["granted"] == []


def test_a_no_op_permission_write_records_nothing(client, admin_token):
    """⚠️ SILENCE ON A NO-OP IS DELIBERATE. An audit trail where every save
    writes a row, changed or not, is one a reader learns to skim."""
    rid = _create(client, admin_token, perms=("payroll.view",))
    r = client.put(f"/api/v1/roles/{rid}/permissions",
                   headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                   json={"permission_keys": ["payroll.view"]})
    assert r.status_code == 200
    assert _audit_rows(rid, "permissions_changed") == []


def test_updating_a_role_records_only_what_changed(client, admin_token):
    rid = _create(client, admin_token)
    r = client.patch(f"/api/v1/roles/{rid}",
                     headers={"Authorization": f"Bearer {admin_token}", **HEADERS},
                     json={"name": "Renamed Probe"})
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    rows = _audit_rows(rid, "updated")
    assert len(rows) == 1, f"expected one 'updated' row, got {len(rows)}"
    ch = rows[0]["changes"]
    # compute_changes shapes each entry as {"old": ..., "new": ...}
    name = ch["name"]
    assert set(name.values()) == {"Role Audit Probe", "Renamed Probe"}, ch
    assert "description" not in ch, "unchanged fields must not be recorded"
    assert "limited_to_areas" not in ch, "areas did not change, so must not appear"


def test_deleting_a_role_records_what_it_held_before_it_vanished(client, admin_token):
    """⚠️ SNAPSHOT BEFORE, NOT AFTER. Once deleted there is nothing to read, and
    'a role called payroll was deleted' without its permission set is a note that
    something happened, not an audit trail."""
    rid = _create(client, admin_token, perms=("payroll.view", "payroll.approve"))
    r = client.delete(f"/api/v1/roles/{rid}",
                      headers={"Authorization": f"Bearer {admin_token}", **HEADERS})
    assert r.status_code == 204, f"{r.status_code}: {r.text[:300]}"
    rows = _audit_rows(rid, "deleted")
    assert len(rows) == 1
    ch = rows[0]["changes"]
    assert set(ch["permission_keys"]["before"]) == {"payroll.view", "payroll.approve"}
    assert ch["slug"]["before"] == SLUG
    assert ch["permission_keys"]["after"] == []


def test_the_audit_row_survives_the_same_transaction_as_the_write(client, admin_token):
    """`log_action` flushes rather than commits, so the row must land with the
    write it describes — not in a second transaction that could fail alone."""
    rid = _create(client, admin_token)
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        role_exists = db.execute(text("SELECT 1 FROM roles WHERE id=:r"), {"r": rid}).scalar()
        audit_exists = db.execute(text(
            "SELECT 1 FROM audit_logs WHERE entity_type='role' AND entity_id=:r"
        ), {"r": rid}).scalar()
    finally:
        db.close()
    assert role_exists == 1 and audit_exists == 1, (
        f"role={role_exists} audit={audit_exists} — they must land together"
    )
