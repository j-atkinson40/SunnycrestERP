"""MoC Planning items (r123) — the personal build-backlog.

Pins: OWNER SCOPING (user A's items invisible to user B — solo today,
correct forever); scope/vertical routing (manufacturing items only on
manufacturing's read); CRUD + loud-reject validation; owner-check on
patch/delete (another user's item reads as not-found — existence isn't
leaked); the API round-trip through the authenticated identity.

State-immunity: fixture users + fixture-scoped teardown.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models.moc_planning_item import MoCPlanningItem
from app.models.platform_user import PlatformUser
from app.services.maps_of_content import planning

MOC = "/api/platform/admin/moc"


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def users(db):
    suffix = uuid.uuid4().hex[:6]
    a = PlatformUser(id=str(uuid.uuid4()), email=f"plan-a-{suffix}@bridgeable.test",
                     hashed_password="x", first_name="A", last_name="P",
                     role="super_admin", is_active=True)
    b = PlatformUser(id=str(uuid.uuid4()), email=f"plan-b-{suffix}@bridgeable.test",
                     hashed_password="x", first_name="B", last_name="P",
                     role="super_admin", is_active=True)
    db.add_all([a, b])
    db.commit()
    yield {"a": a, "b": b}
    s = SessionLocal()
    try:
        s.query(MoCPlanningItem).filter(
            MoCPlanningItem.owner_user_id.in_([a.id, b.id])
        ).delete(synchronize_session=False)
        for u in (a, b):
            s.query(PlatformUser).filter(PlatformUser.id == u.id).delete(
                synchronize_session=False
            )
        s.commit()
    finally:
        s.close()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _headers(user: PlatformUser) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id}, realm='platform')}"}


# ── owner scoping: the pin that stays correct forever ────────────────


def test_owner_scoping_a_invisible_to_b(db, users):
    a, b = users["a"], users["b"]
    planning.create_item(db, owner_user_id=a.id, scope="vertical_default",
                         vertical="manufacturing", kind="feature",
                         title="A's private plan")
    mine = planning.list_items(db, owner_user_id=a.id,
                               scope="vertical_default", vertical="manufacturing")
    theirs = planning.list_items(db, owner_user_id=b.id,
                                 scope="vertical_default", vertical="manufacturing")
    assert [i.title for i in mine] == ["A's private plan"]
    assert theirs == []                                   # NEVER renders


def test_owner_check_on_patch_and_delete(db, users):
    a, b = users["a"], users["b"]
    item = planning.create_item(db, owner_user_id=a.id, scope="vertical_default",
                                vertical="manufacturing", kind="workflow",
                                title="A's workflow plan")
    # B can't patch or delete A's item — and can't learn it exists.
    with pytest.raises(planning.PlanningValidationError, match="not found"):
        planning.patch_item(db, item_id=item.id, owner_user_id=b.id,
                            status="done")
    with pytest.raises(planning.PlanningValidationError, match="not found"):
        planning.delete_item(db, item_id=item.id, owner_user_id=b.id)
    # A can.
    updated = planning.patch_item(db, item_id=item.id, owner_user_id=a.id,
                                  status="done")
    assert updated.status == "done"
    planning.delete_item(db, item_id=item.id, owner_user_id=a.id)


# ── scope/vertical routing ───────────────────────────────────────────


def test_scope_vertical_routing(db, users):
    a = users["a"]
    planning.create_item(db, owner_user_id=a.id, scope="vertical_default",
                         vertical="manufacturing", kind="focus", title="mfg plan")
    planning.create_item(db, owner_user_id=a.id, scope="vertical_default",
                         vertical="funeral_home", kind="focus", title="fh plan")
    planning.create_item(db, owner_user_id=a.id, scope="platform_default",
                         vertical=None, kind="feature", title="platform plan")

    mfg = planning.list_items(db, owner_user_id=a.id,
                              scope="vertical_default", vertical="manufacturing")
    fh = planning.list_items(db, owner_user_id=a.id,
                             scope="vertical_default", vertical="funeral_home")
    plat = planning.list_items(db, owner_user_id=a.id,
                               scope="platform_default", vertical=None)
    assert [i.title for i in mfg] == ["mfg plan"]
    assert [i.title for i in fh] == ["fh plan"]
    assert [i.title for i in plat] == ["platform plan"]


# ── validation, loud ─────────────────────────────────────────────────


def test_validation_loud_rejects(db, users):
    a = users["a"]
    with pytest.raises(planning.PlanningValidationError, match="kind"):
        planning.create_item(db, owner_user_id=a.id, scope="platform_default",
                             vertical=None, kind="epic", title="x")
    with pytest.raises(planning.PlanningValidationError, match="status"):
        planning.create_item(db, owner_user_id=a.id, scope="platform_default",
                             vertical=None, kind="feature", title="x",
                             status="someday")
    with pytest.raises(planning.PlanningValidationError, match="vertical-less"):
        planning.create_item(db, owner_user_id=a.id, scope="platform_default",
                             vertical="manufacturing", kind="feature", title="x")
    with pytest.raises(planning.PlanningValidationError, match="requires"):
        planning.create_item(db, owner_user_id=a.id, scope="vertical_default",
                             vertical=None, kind="feature", title="x")
    with pytest.raises(planning.PlanningValidationError, match="title"):
        planning.create_item(db, owner_user_id=a.id, scope="platform_default",
                             vertical=None, kind="feature", title="   ")


# ── the API round-trip through the authenticated identity ────────────


def test_api_round_trip_owner_stamped(client, db, users):
    a, b = users["a"], users["b"]
    r = client.post(f"{MOC}/planning", headers=_headers(a), json={
        "scope": "vertical_default", "vertical": "manufacturing",
        "kind": "document", "title": "Aftercare letter template",
        "description": "Warm-tone letter; merges family names from the case.",
    })
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["status"] == "planned"

    # A sees it on the manufacturing read; B does not.
    ra = client.get(f"{MOC}/planning", headers=_headers(a),
                    params={"scope": "vertical_default", "vertical": "manufacturing"})
    rb = client.get(f"{MOC}/planning", headers=_headers(b),
                    params={"scope": "vertical_default", "vertical": "manufacturing"})
    assert any(i["id"] == item["id"] for i in ra.json())
    assert all(i["id"] != item["id"] for i in rb.json())

    # Inline status pick; then delete.
    rp = client.patch(f"{MOC}/planning/{item['id']}", headers=_headers(a),
                      json={"status": "in_progress"})
    assert rp.status_code == 200 and rp.json()["status"] == "in_progress"
    rb2 = client.patch(f"{MOC}/planning/{item['id']}", headers=_headers(b),
                       json={"status": "done"})
    assert rb2.status_code == 404                        # not-yours = not-found
    rd = client.delete(f"{MOC}/planning/{item['id']}", headers=_headers(a))
    assert rd.status_code == 200
