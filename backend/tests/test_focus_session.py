"""Phase A Session 4 — Focus persistence tests.

Covers:
- Service layer: 3-tier resolve, create-or-resume idempotency, layout
  roundtrip, close semantics, recent-closed window.
- API layer: endpoint happy paths, ownership 404 for cross-user,
  auth required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _make_ctx(*, vertical: str = "manufacturing"):
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"Focus-{suffix}",
            slug=f"focus-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@focus.co",
            first_name="Focus",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=False,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "token": token,
            "slug": co.slug,
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx()


@pytest.fixture
def ctx_other():
    return _make_ctx()


def _auth_headers(ctx):
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _get_user(user_id: str):
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


# ── Service-layer tests ─────────────────────────────────────────────


class TestServiceLayer:
    def test_get_active_returns_none_when_no_session(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            result = fss.get_active_session(db, user, "kanban")
            assert result is None
        finally:
            db.close()

    def test_create_session_fresh(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            session = fss.create_or_resume_session(db, user, "kanban")
            db.commit()
            assert session is not None
            assert session.is_active is True
            assert session.focus_type == "kanban"
            assert session.user_id == user.id
            assert session.company_id == user.company_id
        finally:
            db.close()

    def test_resume_returns_same_session(self, ctx):
        """create_or_resume is idempotent — second call resumes, not duplicates."""
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            s1 = fss.create_or_resume_session(db, user, "kanban")
            db.commit()
            s2 = fss.create_or_resume_session(db, user, "kanban")
            db.commit()
            assert s1.id == s2.id
            # last_interacted_at should bump on resume.
            assert s2.last_interacted_at >= s1.last_interacted_at
        finally:
            db.close()

    def test_different_focus_types_get_separate_sessions(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            s_kanban = fss.create_or_resume_session(db, user, "kanban")
            s_single = fss.create_or_resume_session(
                db, user, "single_record"
            )
            db.commit()
            assert s_kanban.id != s_single.id
            assert s_kanban.focus_type == "kanban"
            assert s_single.focus_type == "single_record"
        finally:
            db.close()

    def test_update_layout_state_roundtrip(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            session = fss.create_or_resume_session(db, user, "kanban")
            layout = {
                "widgets": {
                    "w1": {
                        "position": {
                            "anchor": "top-left",
                            "offsetX": 32,
                            "offsetY": 96,
                            "width": 320,
                            "height": 240,
                        }
                    }
                }
            }
            updated = fss.update_layout_state(db, session, layout)
            db.commit()
            assert updated.layout_state == layout

            # Re-fetch to verify persistence.
            fresh = fss.get_active_session(db, user, "kanban")
            assert fresh is not None
            assert fresh.layout_state == layout
        finally:
            db.close()

    def test_close_session_stamps_closed_at(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            session = fss.create_or_resume_session(db, user, "kanban")
            closed = fss.close_session(db, session)
            db.commit()
            assert closed.is_active is False
            assert closed.closed_at is not None
        finally:
            db.close()

    def test_close_session_idempotent(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            session = fss.create_or_resume_session(db, user, "kanban")
            fss.close_session(db, session)
            first_closed_at = session.closed_at
            db.commit()
            # Second close should be no-op.
            fss.close_session(db, session)
            db.commit()
            assert session.closed_at == first_closed_at
        finally:
            db.close()

    def test_recent_closed_within_window(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            session = fss.create_or_resume_session(db, user, "kanban")
            fss.update_layout_state(
                db, session, {"widgets": {"w": {"position": {"a": 1}}}}
            )
            fss.close_session(db, session)
            db.commit()
            recent = fss.get_recent_closed_session(db, user, "kanban")
            assert recent is not None
            assert recent.id == session.id
            assert recent.layout_state == {
                "widgets": {"w": {"position": {"a": 1}}}
            }
        finally:
            db.close()

    def test_recent_closed_outside_window_returns_none(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            session = fss.create_or_resume_session(db, user, "kanban")
            fss.close_session(db, session)
            # Backdate closed_at beyond the window.
            session.closed_at = datetime.now(timezone.utc) - timedelta(
                days=2
            )
            db.add(session)
            db.commit()
            recent = fss.get_recent_closed_session(
                db, user, "kanban", within_seconds=3600
            )
            assert recent is None
        finally:
            db.close()

    def test_tenant_default_upsert(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            layout = {"widgets": {"seeded": {"position": {"x": 0}}}}
            row = fss.set_layout_default(
                db, ctx["company_id"], "kanban", layout
            )
            db.commit()
            assert row.layout_state == layout
            # Upsert with new layout — row.id stays same, state replaces.
            new_layout = {"widgets": {"updated": {}}}
            row2 = fss.set_layout_default(
                db, ctx["company_id"], "kanban", new_layout
            )
            db.commit()
            assert row2.id == row.id
            assert row2.layout_state == new_layout
        finally:
            db.close()

    def test_resolve_3_tier_active_wins(self, ctx):
        """Active session layout takes priority over recent + default."""
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            fss.set_layout_default(
                db, ctx["company_id"], "kanban", {"source": "default"}
            )
            # Simulate a prior closed session.
            prior = fss.create_or_resume_session(db, user, "kanban")
            fss.update_layout_state(db, prior, {"source": "recent"})
            fss.close_session(db, prior)
            # Open a fresh one with its own layout.
            active = fss.create_or_resume_session(db, user, "kanban")
            fss.update_layout_state(db, active, {"source": "active"})
            db.commit()
            resolved = fss.resolve_layout_state(db, user, "kanban")
            assert resolved == {"source": "active"}
        finally:
            db.close()

    def test_resolve_3_tier_falls_through_to_recent(self, ctx):
        """No active, recent exists → returns recent."""
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            fss.set_layout_default(
                db, ctx["company_id"], "kanban", {"source": "default"}
            )
            prior = fss.create_or_resume_session(db, user, "kanban")
            fss.update_layout_state(db, prior, {"source": "recent"})
            fss.close_session(db, prior)
            db.commit()
            resolved = fss.resolve_layout_state(db, user, "kanban")
            assert resolved == {"source": "recent"}
        finally:
            db.close()

    def test_resolve_3_tier_falls_through_to_default(self, ctx):
        """No active, no recent, default exists → returns default."""
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            fss.set_layout_default(
                db, ctx["company_id"], "kanban", {"source": "default"}
            )
            db.commit()
            resolved = fss.resolve_layout_state(db, user, "kanban")
            assert resolved == {"source": "default"}
        finally:
            db.close()

    def test_resolve_returns_none_when_nothing_exists(self, ctx):
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            user = _get_user(ctx["user_id"])
            resolved = fss.resolve_layout_state(db, user, "kanban")
            assert resolved is None
        finally:
            db.close()

    def test_tenant_isolation_service_level(self, ctx, ctx_other):
        """User A's active session is invisible to user B's queries."""
        from app.database import SessionLocal
        from app.services.focus import focus_session_service as fss

        db = SessionLocal()
        try:
            a_user = _get_user(ctx["user_id"])
            b_user = _get_user(ctx_other["user_id"])
            a_session = fss.create_or_resume_session(db, a_user, "kanban")
            fss.update_layout_state(db, a_session, {"owner": "A"})
            db.commit()
            b_sees = fss.get_active_session(db, b_user, "kanban")
            assert b_sees is None
            b_resolved = fss.resolve_layout_state(db, b_user, "kanban")
            assert b_resolved is None
        finally:
            db.close()


# ── API-layer tests ─────────────────────────────────────────────────


class TestAPILayer:
    def test_auth_required_for_get_layout(self, client):
        res = client.get("/api/v1/focus/kanban/layout")
        assert res.status_code in (401, 403)

    def test_get_layout_empty_returns_null(self, ctx, client):
        res = client.get(
            "/api/v1/focus/kanban/layout",
            headers=_auth_headers(ctx),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["layout_state"] is None
        assert body["source"] is None

    def test_open_creates_session_and_returns_layout(self, ctx, client):
        res = client.post(
            "/api/v1/focus/kanban/open",
            headers=_auth_headers(ctx),
        )
        assert res.status_code == 200
        body = res.json()
        assert "session" in body
        assert body["session"]["focus_type"] == "kanban"
        assert body["session"]["is_active"] is True
        # No prior state → layout is null.
        assert body["layout_state"] is None or body["layout_state"] == {}

    def test_open_then_update_layout(self, ctx, client):
        open_res = client.post(
            "/api/v1/focus/kanban/open",
            headers=_auth_headers(ctx),
        )
        session_id = open_res.json()["session"]["id"]
        layout = {
            "widgets": {
                "w1": {
                    "position": {
                        "anchor": "top-left",
                        "offsetX": 0,
                        "offsetY": 0,
                        "width": 100,
                        "height": 100,
                    }
                }
            }
        }
        patch_res = client.patch(
            f"/api/v1/focus/sessions/{session_id}/layout",
            headers=_auth_headers(ctx),
            json={"layout_state": layout},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["layout_state"] == layout

        # GET /layout should now return it via the active tier.
        get_res = client.get(
            "/api/v1/focus/kanban/layout",
            headers=_auth_headers(ctx),
        )
        body = get_res.json()
        assert body["layout_state"] == layout
        assert body["source"] == "active"

    def test_close_session(self, ctx, client):
        open_res = client.post(
            "/api/v1/focus/kanban/open",
            headers=_auth_headers(ctx),
        )
        session_id = open_res.json()["session"]["id"]
        close_res = client.post(
            f"/api/v1/focus/sessions/{session_id}/close",
            headers=_auth_headers(ctx),
        )
        assert close_res.status_code == 200
        body = close_res.json()
        assert body["is_active"] is False
        assert body["closed_at"] is not None

    def test_cross_user_access_returns_404(self, ctx, ctx_other, client):
        # User A opens a session.
        open_res = client.post(
            "/api/v1/focus/kanban/open",
            headers=_auth_headers(ctx),
        )
        session_id = open_res.json()["session"]["id"]
        # User B attempts to update it.
        patch_res = client.patch(
            f"/api/v1/focus/sessions/{session_id}/layout",
            headers=_auth_headers(ctx_other),
            json={"layout_state": {"hostile": True}},
        )
        assert patch_res.status_code == 404
        # User B attempts to close it.
        close_res = client.post(
            f"/api/v1/focus/sessions/{session_id}/close",
            headers=_auth_headers(ctx_other),
        )
        assert close_res.status_code == 404

    def test_recent_history_lists_closed_sessions(self, ctx, client):
        # Open + close several focuses.
        for focus_type in ("kanban", "single_record", "triage_queue"):
            open_res = client.post(
                f"/api/v1/focus/{focus_type}/open",
                headers=_auth_headers(ctx),
            )
            sid = open_res.json()["session"]["id"]
            client.post(
                f"/api/v1/focus/sessions/{sid}/close",
                headers=_auth_headers(ctx),
            )
        # Recent list.
        recent_res = client.get(
            "/api/v1/focus/recent",
            headers=_auth_headers(ctx),
        )
        assert recent_res.status_code == 200
        items = recent_res.json()
        types = {item["focus_type"] for item in items}
        assert {"kanban", "single_record", "triage_queue"}.issubset(types)

    def test_recent_history_cross_user_isolation(
        self, ctx, ctx_other, client
    ):
        # User A closes a focus.
        open_res = client.post(
            "/api/v1/focus/kanban/open",
            headers=_auth_headers(ctx),
        )
        sid = open_res.json()["session"]["id"]
        client.post(
            f"/api/v1/focus/sessions/{sid}/close",
            headers=_auth_headers(ctx),
        )
        # User B's recent list should not see it.
        b_recent = client.get(
            "/api/v1/focus/recent",
            headers=_auth_headers(ctx_other),
        )
        assert all(
            item["id"] != sid for item in b_recent.json()
        ), "User B saw user A's session"
