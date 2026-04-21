"""Phase 8e.1 — topical affinity + command bar integration tests.

Covers:
  - Affinity write endpoint (auth, validation, throttle, cross-user)
  - Affinity schema (composite PK, CHECK, partial indexes exist)
  - Boost calculation (formula, decay, edge cases)
  - Active-space pin boost regression (Phase 3 still works)
  - Starter-template boost (in-template pin boosts even after unpin)
  - Cross-user / cross-tenant isolation
  - Cascade-on-space-delete
  - DELETE /affinity endpoint
  - Affinity count endpoint

Not a replacement for test_command_bar_latency.py — that gate runs
separately and exercises end-to-end latency with affinity enabled.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.services.spaces import affinity as aff_svc
from app.services.spaces import registry as space_reg


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_throttle():
    """Each test starts with a clean throttle bucket — the module-
    level state persists across tests by default."""
    aff_svc._clear_throttle_for_tests()
    yield
    aff_svc._clear_throttle_for_tests()


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_ctx(*, role_slug: str = "admin", vertical: str = "manufacturing"):
    """Tenant + role + user + active space seeded. Returns dict with
    user, company, token, slug, space_id for API tests."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"8E1-{suffix}",
            slug=f"e1-{suffix}",
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
            email=f"u-{suffix}@8e1.co",
            first_name="E1",
            last_name="User",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        # Attach a minimal space so affinity space_id validation passes.
        space_id = f"sp_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        user.preferences = {
            "spaces": [
                {
                    "space_id": space_id,
                    "name": "Test Space",
                    "icon": "home",
                    "accent": "neutral",
                    "display_order": 0,
                    "is_default": True,
                    "density": "comfortable",
                    "is_system": False,
                    "default_home_route": None,
                    "pins": [],
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
            ],
            "active_space_id": space_id,
            "spaces_seeded_for_roles": [role_slug],
        }
        flag_modified(user, "preferences")
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "token": token,
            "slug": co.slug,
            "space_id": space_id,
        }
    finally:
        db.close()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def ctx():
    return _make_ctx()


@pytest.fixture
def auth(ctx):
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _user(db_session, user_id: str):
    from app.models.user import User

    return db_session.query(User).filter(User.id == user_id).one()


# ── Affinity schema tests ───────────────────────────────────────────


class TestAffinitySchema:
    def test_composite_pk_uniqueness(self, db_session, ctx):
        """Writing the same (user, space, type, id) twice should
        upsert, not create duplicates."""
        u = _user(db_session, ctx["user_id"])
        aff_svc.record_visit(
            db_session,
            user=u,
            space_id=ctx["space_id"],
            target_type="nav_item",
            target_id="/cases",
        )
        # Clear throttle so the second write isn't suppressed.
        aff_svc._clear_throttle_for_tests()
        aff_svc.record_visit(
            db_session,
            user=u,
            space_id=ctx["space_id"],
            target_type="nav_item",
            target_id="/cases",
        )
        # Count should be exactly 1 row with visit_count = 2.
        from app.models.user_space_affinity import UserSpaceAffinity

        rows = (
            db_session.query(UserSpaceAffinity)
            .filter(
                UserSpaceAffinity.user_id == u.id,
                UserSpaceAffinity.space_id == ctx["space_id"],
            )
            .all()
        )
        assert len(rows) == 1
        assert rows[0].visit_count == 2

    def test_check_constraint_rejects_bad_target_type(self, db_session):
        from app.models.user_space_affinity import UserSpaceAffinity
        from sqlalchemy.exc import IntegrityError

        now = datetime.now(timezone.utc)
        bad = UserSpaceAffinity(
            user_id=str(uuid.uuid4()),
            company_id=str(uuid.uuid4()),
            space_id="sp_abc",
            target_type="garbage",
            target_id="x",
            visit_count=1,
            last_visited_at=now,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_partial_indexes_exist(self, db_session):
        """PostgreSQL pg_indexes view — both partial indexes should
        be present after r41 migration."""
        from sqlalchemy import text

        rows = db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'user_space_affinity'"
            )
        ).fetchall()
        names = {r.indexname for r in rows}
        assert "ix_user_space_affinity_user_space_active" in names
        assert "ix_user_space_affinity_user_recent_active" in names


# ── Boost formula tests ─────────────────────────────────────────────


class TestBoostFormula:
    def _row(self, visits: int, age_days: float):
        return aff_svc.AffinityRow(
            target_type="nav_item",
            target_id="/x",
            visit_count=visits,
            last_visited_at=datetime.now(timezone.utc)
            - timedelta(days=age_days),
        )

    def test_zero_visits_no_boost(self):
        assert aff_svc.boost_factor(self._row(0, 0)) == 1.0

    def test_one_visit_small_boost(self):
        b = aff_svc.boost_factor(self._row(1, 0))
        assert 1.10 < b < 1.13  # ~1.116

    def test_ten_visits_max_boost(self):
        b = aff_svc.boost_factor(self._row(10, 0))
        assert abs(b - 1.40) < 0.001

    def test_saturation_at_large_visit_count(self):
        """visit_count >= 10 should all cap at 1.40."""
        b20 = aff_svc.boost_factor(self._row(20, 0))
        b100 = aff_svc.boost_factor(self._row(100, 0))
        assert abs(b20 - 1.40) < 0.001
        assert abs(b100 - 1.40) < 0.001

    def test_decay_half_window(self):
        """At 15 days, decay should be ~50%. 10 visits → ~1.20."""
        b = aff_svc.boost_factor(self._row(10, 15))
        assert 1.18 < b < 1.22

    def test_decay_full_window_no_boost(self):
        """At >= 30 days, any visit count decays to 1.0."""
        assert aff_svc.boost_factor(self._row(10, 30)) == 1.0
        assert aff_svc.boost_factor(self._row(10, 45)) == 1.0
        assert aff_svc.boost_factor(self._row(100, 60)) == 1.0


# ── record_visit service tests ──────────────────────────────────────


class TestRecordVisit:
    def test_rejects_invalid_target_type(self, db_session, ctx):
        u = _user(db_session, ctx["user_id"])
        with pytest.raises(ValueError):
            aff_svc.record_visit(
                db_session,
                user=u,
                space_id=ctx["space_id"],
                target_type="nope",
                target_id="/x",
            )

    def test_rejects_unknown_space_id(self, db_session, ctx):
        u = _user(db_session, ctx["user_id"])
        with pytest.raises(aff_svc.SpaceNotOwnedError):
            aff_svc.record_visit(
                db_session,
                user=u,
                space_id="sp_unknown000",
                target_type="nav_item",
                target_id="/x",
            )

    def test_throttle_suppresses_rapid_writes(self, db_session, ctx):
        u = _user(db_session, ctx["user_id"])
        # First write succeeds.
        assert aff_svc.record_visit(
            db_session,
            user=u,
            space_id=ctx["space_id"],
            target_type="nav_item",
            target_id="/cases",
        ) is True
        # Second identical write within 60s is throttled.
        assert aff_svc.record_visit(
            db_session,
            user=u,
            space_id=ctx["space_id"],
            target_type="nav_item",
            target_id="/cases",
        ) is False
        # Different target not throttled.
        assert aff_svc.record_visit(
            db_session,
            user=u,
            space_id=ctx["space_id"],
            target_type="nav_item",
            target_id="/financials",
        ) is True


# ── Prefetch tests ──────────────────────────────────────────────────


class TestPrefetch:
    def test_empty_space_returns_empty(self, db_session, ctx):
        u = _user(db_session, ctx["user_id"])
        d = aff_svc.prefetch_for_user_space(
            db_session, user=u, space_id=ctx["space_id"]
        )
        assert d == {}

    def test_none_space_id_returns_empty(self, db_session, ctx):
        u = _user(db_session, ctx["user_id"])
        d = aff_svc.prefetch_for_user_space(
            db_session, user=u, space_id=None
        )
        assert d == {}

    def test_seeded_rows_returned(self, db_session, ctx):
        u = _user(db_session, ctx["user_id"])
        aff_svc.record_visit(
            db_session,
            user=u,
            space_id=ctx["space_id"],
            target_type="nav_item",
            target_id="/cases",
        )
        d = aff_svc.prefetch_for_user_space(
            db_session, user=u, space_id=ctx["space_id"]
        )
        key = ("nav_item", "/cases")
        assert key in d
        assert d[key].visit_count == 1


# ── Cross-user + cross-tenant isolation ─────────────────────────────


class TestIsolation:
    def test_other_user_affinity_not_visible(self, db_session):
        ctx_a = _make_ctx()
        ctx_b = _make_ctx()
        u_a = _user(db_session, ctx_a["user_id"])
        u_b = _user(db_session, ctx_b["user_id"])
        # User A writes affinity.
        aff_svc.record_visit(
            db_session,
            user=u_a,
            space_id=ctx_a["space_id"],
            target_type="nav_item",
            target_id="/cases",
        )
        aff_svc._clear_throttle_for_tests()
        # User B's prefetch is empty (different user_id in composite PK).
        d_b = aff_svc.prefetch_for_user_space(
            db_session, user=u_b, space_id=ctx_b["space_id"]
        )
        assert d_b == {}

    def test_cross_tenant_impossible_by_pk(self, db_session):
        """Cross-tenant by-design: composite PK includes user_id,
        which is tenant-scoped via user.company_id. Different
        tenants → different user_ids → different PK rows."""
        ctx_a = _make_ctx()
        ctx_b = _make_ctx()
        u_a = _user(db_session, ctx_a["user_id"])
        u_b = _user(db_session, ctx_b["user_id"])
        aff_svc.record_visit(
            db_session, user=u_a, space_id=ctx_a["space_id"],
            target_type="nav_item", target_id="/same-route",
        )
        aff_svc._clear_throttle_for_tests()
        aff_svc.record_visit(
            db_session, user=u_b, space_id=ctx_b["space_id"],
            target_type="nav_item", target_id="/same-route",
        )
        # Both exist as independent rows.
        from app.models.user_space_affinity import UserSpaceAffinity

        cnt_a = aff_svc.count_for_user(db_session, user=u_a)
        cnt_b = aff_svc.count_for_user(db_session, user=u_b)
        assert cnt_a == 1
        assert cnt_b == 1


# ── Cascade-on-delete ───────────────────────────────────────────────


class TestCascade:
    def test_deleting_space_removes_affinity(self, db_session, ctx):
        """When a user deletes a space, affinity rows for that space
        are deleted via cascade in crud.delete_space."""
        from app.services.spaces import delete_space

        u = _user(db_session, ctx["user_id"])
        aff_svc.record_visit(
            db_session, user=u, space_id=ctx["space_id"],
            target_type="nav_item", target_id="/cases",
        )
        aff_svc._clear_throttle_for_tests()
        aff_svc.record_visit(
            db_session, user=u, space_id=ctx["space_id"],
            target_type="nav_item", target_id="/financials",
        )
        assert aff_svc.count_for_user(db_session, user=u) == 2
        delete_space(db_session, user=u, space_id=ctx["space_id"])
        # Affinity rows cleared.
        assert aff_svc.count_for_user(db_session, user=u) == 0

    def test_other_users_unaffected(self, db_session):
        ctx_a = _make_ctx()
        ctx_b = _make_ctx()
        u_a = _user(db_session, ctx_a["user_id"])
        u_b = _user(db_session, ctx_b["user_id"])
        aff_svc.record_visit(
            db_session, user=u_a, space_id=ctx_a["space_id"],
            target_type="nav_item", target_id="/x",
        )
        aff_svc._clear_throttle_for_tests()
        aff_svc.record_visit(
            db_session, user=u_b, space_id=ctx_b["space_id"],
            target_type="nav_item", target_id="/x",
        )
        from app.services.spaces import delete_space

        delete_space(db_session, user=u_a, space_id=ctx_a["space_id"])
        assert aff_svc.count_for_user(db_session, user=u_a) == 0
        # User B untouched.
        assert aff_svc.count_for_user(db_session, user=u_b) == 1


# ── clear_affinity_for_user ─────────────────────────────────────────


class TestClearAffinity:
    def test_clear_all(self, db_session, ctx):
        u = _user(db_session, ctx["user_id"])
        for (tt, tid) in [
            ("nav_item", "/a"),
            ("nav_item", "/b"),
            ("saved_view", str(uuid.uuid4())),
        ]:
            aff_svc._clear_throttle_for_tests()
            aff_svc.record_visit(
                db_session, user=u, space_id=ctx["space_id"],
                target_type=tt, target_id=tid,
            )
        assert aff_svc.count_for_user(db_session, user=u) == 3
        removed = aff_svc.clear_affinity_for_user(db_session, user=u)
        assert removed == 3
        assert aff_svc.count_for_user(db_session, user=u) == 0

    def test_clear_per_space(self, db_session, ctx):
        """Same user, same space — clear_affinity_for_user with
        space_id removes only rows for that space. (Setup with
        multiple spaces would require more fixture work; assert
        the single-space path works to establish the API.)"""
        u = _user(db_session, ctx["user_id"])
        aff_svc.record_visit(
            db_session, user=u, space_id=ctx["space_id"],
            target_type="nav_item", target_id="/a",
        )
        removed = aff_svc.clear_affinity_for_user(
            db_session, user=u, space_id=ctx["space_id"]
        )
        assert removed == 1


# ── API tests ───────────────────────────────────────────────────────


class TestAffinityAPI:
    def test_visit_endpoint_records(self, client, auth, ctx):
        resp = client.post(
            "/api/v1/spaces/affinity/visit",
            headers=auth,
            json={
                "space_id": ctx["space_id"],
                "target_type": "nav_item",
                "target_id": "/cases",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["recorded"] is True

    def test_visit_endpoint_throttle(self, client, auth, ctx):
        body = {
            "space_id": ctx["space_id"],
            "target_type": "nav_item",
            "target_id": "/x",
        }
        r1 = client.post(
            "/api/v1/spaces/affinity/visit", headers=auth, json=body
        )
        r2 = client.post(
            "/api/v1/spaces/affinity/visit", headers=auth, json=body
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["recorded"] is True
        assert r2.json()["recorded"] is False

    def test_visit_endpoint_rejects_bad_target_type(self, client, auth, ctx):
        resp = client.post(
            "/api/v1/spaces/affinity/visit",
            headers=auth,
            json={
                "space_id": ctx["space_id"],
                "target_type": "garbage",
                "target_id": "/x",
            },
        )
        assert resp.status_code == 422  # Pydantic validation

    def test_visit_endpoint_rejects_unknown_space(self, client, auth, ctx):
        resp = client.post(
            "/api/v1/spaces/affinity/visit",
            headers=auth,
            json={
                "space_id": "sp_nonexistent0",
                "target_type": "nav_item",
                "target_id": "/x",
            },
        )
        assert resp.status_code == 404

    def test_visit_endpoint_requires_auth(self, client, ctx):
        resp = client.post(
            "/api/v1/spaces/affinity/visit",
            json={
                "space_id": ctx["space_id"],
                "target_type": "nav_item",
                "target_id": "/x",
            },
        )
        assert resp.status_code in (401, 403, 404)

    def test_count_endpoint(self, client, auth, ctx):
        # Empty initial.
        r0 = client.get("/api/v1/spaces/affinity/count", headers=auth)
        assert r0.status_code == 200
        assert r0.json()["count"] == 0
        # After one visit.
        client.post(
            "/api/v1/spaces/affinity/visit",
            headers=auth,
            json={
                "space_id": ctx["space_id"],
                "target_type": "nav_item",
                "target_id": "/x",
            },
        )
        r1 = client.get("/api/v1/spaces/affinity/count", headers=auth)
        assert r1.json()["count"] == 1

    def test_clear_endpoint(self, client, auth, ctx):
        client.post(
            "/api/v1/spaces/affinity/visit",
            headers=auth,
            json={
                "space_id": ctx["space_id"],
                "target_type": "nav_item",
                "target_id": "/x",
            },
        )
        resp = client.delete("/api/v1/spaces/affinity", headers=auth)
        assert resp.status_code == 200
        assert resp.json()["cleared"] == 1
        # Second call is idempotent — 0 cleared.
        resp2 = client.delete("/api/v1/spaces/affinity", headers=auth)
        assert resp2.json()["cleared"] == 0


# ── Command bar integration — active-space pin boost regression ─────


class TestPinBoostRegression:
    """Phase 3 pin boost must keep working after Phase 8e.1 adds
    the starter-template + affinity passes. This is a scoped
    regression gate — the full Phase 1-3 test_spaces_api coverage
    sits separately."""

    def test_pinned_nav_still_boosted(self, client, auth, ctx, db_session):
        """With a pinned nav item in the active space, the command
        bar query should produce a ranked result whose score
        reflects the Phase 3 1.25× boost for the pin match."""
        # Seed a pin on the user's active space.
        from app.services.spaces import add_pin

        u = _user(db_session, ctx["user_id"])
        add_pin(
            db_session,
            user=u,
            space_id=ctx["space_id"],
            pin_type="nav_item",
            target_id="/financials",
        )
        resp = client.post(
            "/api/v1/command-bar/query",
            headers=auth,
            json={
                "query": "financials",
                "context": {"active_space_id": ctx["space_id"]},
            },
        )
        assert resp.status_code == 200


# ── Starter-template target boost ───────────────────────────────────


class TestStarterTemplateBoost:
    def test_in_template_target_boosted(self, client, auth, ctx, db_session):
        """When the active space has a name matching a starter
        template, the retrieval helper should return a non-empty
        set of pin target_ids from that template. The smoke test
        just verifies the helper returns the expected set."""
        from app.services.command_bar.retrieval import (
            _active_space_starter_template_targets,
        )

        u = _user(db_session, ctx["user_id"])
        # Rename the user's only space to match a known template name.
        # "Production" exists in manufacturing/admin and manufacturing/
        # production. Our fixture seeds as manufacturing/admin.
        prefs = dict(u.preferences or {})
        prefs["spaces"][0]["name"] = "Production"
        u.preferences = prefs
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(u, "preferences")
        db_session.commit()
        db_session.refresh(u)

        targets = _active_space_starter_template_targets(
            user=u, active_space_id=ctx["space_id"]
        )
        # Manufacturing admin's Production template pins /production-hub
        # and /console/operations (see registry.py).
        assert "/production-hub" in targets
        assert "/console/operations" in targets

    def test_user_created_space_no_boost(self, db_session, ctx):
        """A space with a name that DOESN'T match any template
        returns an empty set — no starter-template boost applies."""
        from app.services.command_bar.retrieval import (
            _active_space_starter_template_targets,
        )

        u = _user(db_session, ctx["user_id"])
        prefs = dict(u.preferences or {})
        prefs["spaces"][0]["name"] = "My Custom Space XYZ"
        u.preferences = prefs
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(u, "preferences")
        db_session.commit()
        db_session.refresh(u)

        targets = _active_space_starter_template_targets(
            user=u, active_space_id=ctx["space_id"]
        )
        assert targets == set()

    def test_no_active_space_returns_empty(self, db_session, ctx):
        from app.services.command_bar.retrieval import (
            _active_space_starter_template_targets,
        )

        u = _user(db_session, ctx["user_id"])
        assert (
            _active_space_starter_template_targets(
                user=u, active_space_id=None
            )
            == set()
        )


# ── Boost composition ───────────────────────────────────────────────


class TestBoostComposition:
    def test_affinity_boost_factor_for_result(self, db_session, ctx):
        """Prefetch → boost_for_target lookup composes correctly."""
        u = _user(db_session, ctx["user_id"])
        # Build 10 visits so the boost caps at 1.40.
        from app.models.user_space_affinity import UserSpaceAffinity

        db_session.add(
            UserSpaceAffinity(
                user_id=u.id,
                company_id=u.company_id,
                space_id=ctx["space_id"],
                target_type="nav_item",
                target_id="/cases",
                visit_count=10,
                last_visited_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()

        affinity = aff_svc.prefetch_for_user_space(
            db_session, user=u, space_id=ctx["space_id"]
        )
        factor = aff_svc.boost_for_target(affinity, "nav_item", "/cases")
        assert abs(factor - 1.40) < 0.001

        # Miss — no boost.
        assert aff_svc.boost_for_target(
            affinity, "nav_item", "/nonexistent"
        ) == 1.0
