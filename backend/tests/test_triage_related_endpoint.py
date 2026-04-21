"""Triage `/related` endpoint — follow-up 4 wires the Phase 5
related_entities context panel using follow-up 2's
`_RELATED_ENTITY_BUILDERS` infrastructure.

Covers GET /api/v1/triage/sessions/{id}/items/{item_id}/related:

  - task_triage queue returns sibling tasks (assignee scope)
  - Empty list when no builder registered for the queue (graceful
    degradation, NOT an error)
  - Session not found → 404
  - Item not found → 404
  - Cross-user session isolation
  - Auth required
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest


# ── Fixtures (mirror test_triage_ai_question_api.py) ────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_ctx():
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
            name=f"REL-{suffix}",
            slug=f"rel-{suffix}",
            is_active=True,
            vertical="manufacturing",
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
            email=f"u-{suffix}@rel.co",
            first_name="Rel",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
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
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-Company-Slug": co.slug,
            },
        }
    finally:
        db.close()


def _seed_task_and_session(db_session, ctx, *, n_siblings: int = 3):
    from app.models.user import User
    from app.services.task_service import create_task
    from app.services.triage.engine import next_item, start_session

    user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
    main = create_task(
        db_session,
        company_id=ctx["company_id"],
        title="Main task",
        created_by_user_id=ctx["user_id"],
        assignee_user_id=ctx["user_id"],
        priority="urgent",
        due_date=date.today() + timedelta(days=1),
    )
    for i in range(n_siblings):
        create_task(
            db_session,
            company_id=ctx["company_id"],
            title=f"Sibling {i}",
            created_by_user_id=ctx["user_id"],
            assignee_user_id=ctx["user_id"],
            priority="normal",
            due_date=date.today() + timedelta(days=2 + i),
        )
    session = start_session(db_session, user=user, queue_id="task_triage")
    try:
        next_item(db_session, session_id=session.id, user=user)
    except Exception:
        pass
    return main.id, session.id


# ── Happy path ────────────────────────────────────────────────────


class TestRelatedHappy:
    def test_returns_sibling_tasks(self, client, db_session):
        ctx = _make_ctx()
        task_id, session_id = _seed_task_and_session(
            db_session, ctx, n_siblings=3
        )
        r = client.get(
            f"/api/v1/triage/sessions/{session_id}/items/{task_id}/related",
            headers=ctx["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # 3 sibling tasks expected (linked entity is None for these,
        # so total is just the siblings).
        assert len(body) == 3
        for row in body:
            assert row["entity_type"] == "task"
            assert row["context"] == "same_assignee"
            assert "display_label" in row
            # extras carries status/priority/due_date pass-through.
            assert "extras" in row

    def test_no_siblings_returns_empty_list(self, client, db_session):
        ctx = _make_ctx()
        task_id, session_id = _seed_task_and_session(
            db_session, ctx, n_siblings=0
        )
        r = client.get(
            f"/api/v1/triage/sessions/{session_id}/items/{task_id}/related",
            headers=ctx["headers"],
        )
        assert r.status_code == 200
        assert r.json() == []


# ── Error paths ───────────────────────────────────────────────────


class TestRelatedErrors:
    def test_session_not_found(self, client):
        ctx = _make_ctx()
        r = client.get(
            "/api/v1/triage/sessions/nope/items/abc/related",
            headers=ctx["headers"],
        )
        assert r.status_code == 404

    def test_item_not_found(self, client, db_session):
        ctx = _make_ctx()
        _, session_id = _seed_task_and_session(db_session, ctx)
        r = client.get(
            f"/api/v1/triage/sessions/{session_id}/items/bogus/related",
            headers=ctx["headers"],
        )
        assert r.status_code == 404

    def test_cross_user_session_404(self, client, db_session):
        ctx_a = _make_ctx()
        ctx_b = _make_ctx()
        task_id, session_id = _seed_task_and_session(db_session, ctx_a)
        r = client.get(
            f"/api/v1/triage/sessions/{session_id}/items/{task_id}/related",
            headers=ctx_b["headers"],
        )
        assert r.status_code == 404

    def test_auth_required(self, client):
        r = client.get(
            "/api/v1/triage/sessions/abc/items/def/related",
        )
        assert r.status_code in (401, 403)
