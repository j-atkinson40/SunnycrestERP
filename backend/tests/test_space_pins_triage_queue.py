"""Spaces — triage_queue pin tests (Phase 3 follow-up 1).

Covers the new `triage_queue` pin type end-to-end:

  - Unit: seed template produces a triage pin for FH director +
    manufacturing production roles
  - Unit: _resolve_pin resolves icon/label/href/count from the Phase 5
    TriageQueueConfig registry + queue_count engine call
  - Unit: pin renders `unavailable=True` with count=None when the user
    lacks queue access (e.g. FH director for ss_cert_triage which is
    mfg-vertical + invoice.approve gated) or the queue_id is unknown
  - Unit: `_accessible_queue_ids_for_user` is called ONCE per space
    resolution regardless of triage-pin count (batched perf)
  - Unit: add_pin validation accepts "triage_queue"
  - API: create + list round-trip exposes `queue_item_count` on the
    response shape; POST /spaces/{id}/pins accepts pin_type=triage_queue
  - API: cross-user isolation — mfg admin can't see FH director's pins
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant_user(
    *,
    role_slug: str = "admin",
    vertical: str = "manufacturing",
    super_admin: bool = False,
):
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"SP-{suffix}",
            slug=f"sp-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@sp.co",
            first_name="SP",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=super_admin,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return user.id, co.id, co.slug, role.slug
    finally:
        db.close()


@pytest.fixture
def fh_director(db_session):
    """Funeral home director — sees task_triage (unrestricted) but
    NOT ss_cert_triage (requires manufacturing vertical)."""
    user_id, _, _, _ = _make_tenant_user(
        role_slug="director", vertical="funeral_home"
    )
    from app.models.user import User

    return db_session.query(User).filter(User.id == user_id).one()


@pytest.fixture
def mfg_admin(db_session):
    """Manufacturing admin — sees both task_triage AND ss_cert_triage
    (admin bypasses permission gates in user_has_permission)."""
    user_id, _, _, _ = _make_tenant_user(
        role_slug="admin", vertical="manufacturing"
    )
    from app.models.user import User

    return db_session.query(User).filter(User.id == user_id).one()


@pytest.fixture
def mfg_production(db_session):
    """Manufacturing production role — seeded Production space should
    ship with a task_triage pin as its first entry (follow-up 1)."""
    user_id, _, _, _ = _make_tenant_user(
        role_slug="production", vertical="manufacturing"
    )
    from app.models.user import User

    return db_session.query(User).filter(User.id == user_id).one()


# ── Unit tests — registry / seed ─────────────────────────────────────


class TestRegistryIcon:
    def test_triage_queue_config_has_icon_field(self):
        from app.services.triage.registry import _PLATFORM_CONFIGS

        task = _PLATFORM_CONFIGS["task_triage"]
        ss_cert = _PLATFORM_CONFIGS["ss_cert_triage"]
        # Every queue MUST have an icon or the frontend ICON_MAP
        # fallback kicks in (silent visual regression).
        assert task.icon == "CheckSquare"
        assert ss_cert.icon == "FileCheck"


class TestSeedTemplatesIncludeTriagePin:
    def test_fh_director_arrangement_template_has_task_triage_pin(self):
        from app.services.spaces import registry as reg

        templates = reg.get_templates("funeral_home", "director")
        arrangement = next(t for t in templates if t.name == "Arrangement")
        triage_pins = [p for p in arrangement.pins if p.pin_type == "triage_queue"]
        assert len(triage_pins) == 1
        assert triage_pins[0].target == "task_triage"

    def test_mfg_production_template_has_task_triage_pin(self):
        from app.services.spaces import registry as reg

        templates = reg.get_templates("manufacturing", "production")
        production = next(t for t in templates if t.name == "Production")
        triage_pins = [p for p in production.pins if p.pin_type == "triage_queue"]
        assert len(triage_pins) == 1
        assert triage_pins[0].target == "task_triage"


class TestSeededTriagePin:
    def test_fh_director_seed_produces_resolved_triage_pin(
        self, db_session, fh_director
    ):
        from app.services.spaces import get_spaces_for_user, seed_for_user

        seed_for_user(db_session, user=fh_director)
        spaces = get_spaces_for_user(db_session, user=fh_director)
        arrangement = next(s for s in spaces if s.name == "Arrangement")
        triage_pins = [p for p in arrangement.pins if p.pin_type == "triage_queue"]
        assert len(triage_pins) == 1
        pin = triage_pins[0]
        # Available — user can see task_triage (no gate)
        assert pin.unavailable is False
        assert pin.target_id == "task_triage"
        assert pin.icon == "CheckSquare"
        assert pin.label == "Task Triage"
        assert pin.href == "/triage/task_triage"
        # count should be an int (may be 0 if no tasks seeded)
        assert isinstance(pin.queue_item_count, int)
        assert pin.queue_item_count >= 0

    def test_mfg_production_seed_produces_triage_pin(
        self, db_session, mfg_production
    ):
        from app.services.spaces import get_spaces_for_user, seed_for_user

        seed_for_user(db_session, user=mfg_production)
        spaces = get_spaces_for_user(db_session, user=mfg_production)
        production = next(s for s in spaces if s.name == "Production")
        triage_pins = [p for p in production.pins if p.pin_type == "triage_queue"]
        assert len(triage_pins) == 1
        assert triage_pins[0].target_id == "task_triage"
        # production role doesn't have "admin" slug so permission path
        # still runs through user_has_permission — task_triage has no
        # permission requirements, so this should resolve.
        assert triage_pins[0].unavailable is False


# ── Unit tests — resolver behavior ───────────────────────────────────


class TestResolveTriageQueuePin:
    def test_resolves_to_config_icon_and_name(self, db_session, mfg_admin):
        from app.services.spaces import add_pin, create_space, get_spaces_for_user

        sp = create_space(db_session, user=mfg_admin, name="Ops")
        add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="task_triage",
        )
        spaces = get_spaces_for_user(db_session, user=mfg_admin)
        space = next(s for s in spaces if s.space_id == sp.space_id)
        pin = next(p for p in space.pins if p.pin_type == "triage_queue")
        assert pin.icon == "CheckSquare"
        assert pin.label == "Task Triage"
        assert pin.href == "/triage/task_triage"
        assert pin.unavailable is False

    def test_label_override_wins_over_config_name(
        self, db_session, mfg_admin
    ):
        from app.services.spaces import add_pin, create_space, get_spaces_for_user

        sp = create_space(db_session, user=mfg_admin, name="Ops")
        add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="task_triage",
            label_override="My Queue",
        )
        spaces = get_spaces_for_user(db_session, user=mfg_admin)
        space = next(s for s in spaces if s.space_id == sp.space_id)
        pin = next(p for p in space.pins if p.pin_type == "triage_queue")
        assert pin.label == "My Queue"

    def test_fh_director_cannot_access_ss_cert_triage(
        self, db_session, fh_director
    ):
        """ss_cert_triage requires manufacturing vertical — FH director
        on a funeral_home tenant should see the pin as unavailable.
        Manually pin since seed won't auto-include it."""
        from app.services.spaces import add_pin, create_space, get_spaces_for_user

        sp = create_space(db_session, user=fh_director, name="Try")
        add_pin(
            db_session,
            user=fh_director,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="ss_cert_triage",
        )
        spaces = get_spaces_for_user(db_session, user=fh_director)
        space = next(s for s in spaces if s.space_id == sp.space_id)
        pin = next(p for p in space.pins if p.pin_type == "triage_queue")
        assert pin.unavailable is True
        assert pin.href is None
        assert pin.queue_item_count is None
        # Still renders a readable label even when unavailable
        assert pin.label

    def test_unknown_queue_id_is_unavailable(self, db_session, mfg_admin):
        from app.services.spaces import add_pin, create_space, get_spaces_for_user

        sp = create_space(db_session, user=mfg_admin, name="Try")
        add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="nonexistent_queue",
        )
        spaces = get_spaces_for_user(db_session, user=mfg_admin)
        space = next(s for s in spaces if s.space_id == sp.space_id)
        pin = next(p for p in space.pins if p.pin_type == "triage_queue")
        assert pin.unavailable is True
        assert pin.href is None
        assert pin.queue_item_count is None


class TestBatchedAccessCheck:
    def test_list_queues_for_user_called_once_per_space_with_triage_pins(
        self, db_session, mfg_admin
    ):
        """Pinning N triage queues in one space should still trigger
        only ONE `list_queues_for_user` call during resolution."""
        from app.services.spaces import add_pin, create_space, get_spaces_for_user

        sp = create_space(db_session, user=mfg_admin, name="Ops")
        add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="task_triage",
        )
        add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="ss_cert_triage",
        )
        with patch(
            "app.services.spaces.crud._accessible_queue_ids_for_user",
            wraps=__import__(
                "app.services.spaces.crud", fromlist=["_accessible_queue_ids_for_user"]
            )._accessible_queue_ids_for_user,
        ) as spy:
            get_spaces_for_user(db_session, user=mfg_admin)
        # Space with ANY triage pin → one call per space in get_spaces_for_user.
        # For this single space, that means exactly 1 call — NOT 2 (one per pin).
        # Other spaces in the list won't contribute a call because they have
        # no triage pins.
        assert spy.call_count == 1

    def test_no_triage_pins_no_access_lookup(self, db_session, mfg_admin):
        from app.services.spaces import add_pin, create_space, get_spaces_for_user

        sp = create_space(db_session, user=mfg_admin, name="NoTriage")
        add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="nav_item",
            target_id="/cases",
        )
        with patch(
            "app.services.spaces.crud._accessible_queue_ids_for_user",
        ) as spy:
            get_spaces_for_user(db_session, user=mfg_admin)
        # Zero triage pins → zero access lookups. Protects the
        # 99% non-triage-pinned case from paying a perms query.
        assert spy.call_count == 0


# ── Unit tests — validation ──────────────────────────────────────────


class TestAddPinValidation:
    def test_accepts_triage_queue_pin_type(self, db_session, mfg_admin):
        from app.services.spaces import add_pin, create_space

        sp = create_space(db_session, user=mfg_admin, name="S")
        pin = add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="task_triage",
        )
        assert pin.pin_type == "triage_queue"
        assert pin.target_id == "task_triage"

    def test_triage_queue_pin_is_idempotent(self, db_session, mfg_admin):
        from app.services.spaces import add_pin, create_space, get_spaces_for_user

        sp = create_space(db_session, user=mfg_admin, name="S")
        p1 = add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="task_triage",
        )
        p2 = add_pin(
            db_session,
            user=mfg_admin,
            space_id=sp.space_id,
            pin_type="triage_queue",
            target_id="task_triage",
        )
        assert p1.pin_id == p2.pin_id
        spaces = get_spaces_for_user(db_session, user=mfg_admin)
        space = next(s for s in spaces if s.space_id == sp.space_id)
        assert len([p for p in space.pins if p.pin_type == "triage_queue"]) == 1


# ── API tests ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _ctx(
    *, role_slug: str = "admin", vertical: str = "manufacturing",
    super_admin: bool = False,
):
    from app.core.security import create_access_token

    user_id, company_id, slug, _ = _make_tenant_user(
        role_slug=role_slug, vertical=vertical, super_admin=super_admin,
    )
    token = create_access_token({"sub": user_id, "company_id": company_id})
    return {
        "user_id": user_id,
        "company_id": company_id,
        "token": token,
        "slug": slug,
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Company-Slug": slug,
        },
    }


class TestSpacesAPITriageQueue:
    def test_create_space_and_pin_triage_queue_roundtrip(self, client):
        ctx = _ctx(role_slug="admin", vertical="manufacturing")
        r = client.post(
            "/api/v1/spaces",
            json={"name": "Ops Space"},
            headers=ctx["headers"],
        )
        assert r.status_code == 201, r.text
        space_id = r.json()["space_id"]

        r = client.post(
            f"/api/v1/spaces/{space_id}/pins",
            json={
                "pin_type": "triage_queue",
                "target_id": "task_triage",
            },
            headers=ctx["headers"],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["pin_type"] == "triage_queue"
        assert body["target_id"] == "task_triage"
        assert body["icon"] == "CheckSquare"
        assert body["href"] == "/triage/task_triage"
        assert body["unavailable"] is False
        # queue_item_count is serialized even when 0
        assert "queue_item_count" in body
        assert isinstance(body["queue_item_count"], int)

    def test_list_spaces_includes_queue_item_count(self, client):
        ctx = _ctx(role_slug="admin", vertical="manufacturing")
        # Create + pin
        sp = client.post(
            "/api/v1/spaces",
            json={"name": "Ops"},
            headers=ctx["headers"],
        ).json()
        client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "triage_queue", "target_id": "task_triage"},
            headers=ctx["headers"],
        )
        r = client.get("/api/v1/spaces", headers=ctx["headers"])
        assert r.status_code == 200
        body = r.json()
        space = next(s for s in body["spaces"] if s["space_id"] == sp["space_id"])
        pin = next(p for p in space["pins"] if p["pin_type"] == "triage_queue")
        assert "queue_item_count" in pin
        assert isinstance(pin["queue_item_count"], int)

    def test_unavailable_triage_pin_serializes_null_count(self, client):
        """FH director pinning ss_cert_triage (mfg-only) → unavailable
        with queue_item_count=null in the API response."""
        ctx = _ctx(role_slug="director", vertical="funeral_home")
        sp = client.post(
            "/api/v1/spaces",
            json={"name": "Try"},
            headers=ctx["headers"],
        ).json()
        r = client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "triage_queue", "target_id": "ss_cert_triage"},
            headers=ctx["headers"],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["unavailable"] is True
        assert body["href"] is None
        assert body["queue_item_count"] is None

    def test_cross_user_isolation(self, client):
        ctx_a = _ctx(role_slug="admin", vertical="manufacturing")
        ctx_b = _ctx(role_slug="admin", vertical="manufacturing")
        # A creates + pins
        sp = client.post(
            "/api/v1/spaces", json={"name": "A"}, headers=ctx_a["headers"],
        ).json()
        client.post(
            f"/api/v1/spaces/{sp['space_id']}/pins",
            json={"pin_type": "triage_queue", "target_id": "task_triage"},
            headers=ctx_a["headers"],
        )
        # B requests A's space → 404
        r = client.get(
            f"/api/v1/spaces/{sp['space_id']}", headers=ctx_b["headers"],
        )
        assert r.status_code == 404
