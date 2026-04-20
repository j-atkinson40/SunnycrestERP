"""Triage `/ask` API — integration tests (follow-up 2).

Covers the HTTP contract of
`POST /api/v1/triage/sessions/{session_id}/items/{item_id}/ask`:

  - Happy path: valid session + valid item + monkey-patched
    Intelligence returns 200 with `_AskResponse` shape
  - Invalid session id → 404
  - Invalid item id → 404
  - Question too long → 400
  - Empty question → Pydantic 422 (min_length=1)
  - Rate limit → 429 with structured body
    `{code: "rate_limited", retry_after_seconds, message}` +
    `Retry-After` header
  - Auth required (no token → 401/403)
  - Cross-user session isolation → 404
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest


# ── Fixtures (mirror test_task_and_triage.py pattern) ────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(
    *, role_slug: str = "admin", vertical: str = "manufacturing",
    super_admin: bool = True,
):
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
            name=f"AQAPI-{suffix}",
            slug=f"aqapi-{suffix}",
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
            email=f"u-{suffix}@aqapi.co",
            first_name="A",
            last_name="Q",
            hashed_password="x",
            is_active=True,
            is_super_admin=super_admin,
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


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.services.triage.ai_question import _reset_rate_limiter

    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


def _seed_task_and_session(db_session, ctx, *, title: str = "Task 1"):
    """Seed a task, open a triage session, refresh — return (task_id,
    session_id). Uses direct service calls so the session's
    `current_item_id` is populated before we `next_item` it."""
    from app.models.user import User
    from app.services.task_service import create_task
    from app.services.triage.engine import next_item, start_session

    user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
    task = create_task(
        db_session,
        company_id=ctx["company_id"],
        title=title,
        created_by_user_id=ctx["user_id"],
        assignee_user_id=ctx["user_id"],
        priority="urgent",
        due_date=date.today() + timedelta(days=1),
    )
    session = start_session(db_session, user=user, queue_id="task_triage")
    # Advance cursor so `current_item_id` is populated (not required
    # by the service but matches the real UX).
    try:
        next_item(db_session, session_id=session.id, user=user)
    except Exception:
        pass
    return task.id, session.id


class _FakeIntelResult:
    def __init__(
        self,
        *,
        status="success",
        response_parsed=None,
        latency_ms=250,
    ):
        self.status = status
        self.response_parsed = response_parsed
        self.response_text = None
        self.latency_ms = latency_ms
        self.execution_id = "exec_" + uuid.uuid4().hex[:8]
        self.prompt_id = None
        self.prompt_version_id = None
        self.model_used = "claude-haiku-4-5"
        self.error_message = None
        self.rendered_system_prompt = ""
        self.rendered_user_prompt = ""
        self.input_tokens = 80
        self.output_tokens = 40
        self.cost_usd = None


# ── Happy path ──────────────────────────────────────────────────────


class TestAskAPIHappy:
    def test_roundtrip(self, client, db_session):
        ctx = _make_ctx()
        task_id, session_id = _seed_task_and_session(db_session, ctx)

        fake = _FakeIntelResult(
            response_parsed={
                "answer": "Due tomorrow — urgent priority.",
                "confidence": 0.9,
                "sources": [
                    {
                        "entity_type": "task",
                        "entity_id": task_id,
                        "display_label": "Task 1",
                    }
                ],
            },
            latency_ms=390,
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake,
        ):
            r = client.post(
                f"/api/v1/triage/sessions/{session_id}/items/{task_id}/ask",
                json={"question": "Why is this urgent?"},
                headers=ctx["headers"],
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["question"] == "Why is this urgent?"
        assert body["answer"].startswith("Due tomorrow")
        assert body["confidence"] == "high"
        assert body["confidence_score"] == 0.9
        assert body["latency_ms"] == 390
        assert len(body["source_references"]) == 1
        assert body["source_references"][0]["entity_id"] == task_id
        assert "asked_at" in body
        assert "execution_id" in body


# ── Error paths ────────────────────────────────────────────────────


class TestAskAPIErrors:
    def test_session_not_found(self, client):
        ctx = _make_ctx()
        r = client.post(
            "/api/v1/triage/sessions/nope_session/items/anything/ask",
            json={"question": "Why?"},
            headers=ctx["headers"],
        )
        assert r.status_code == 404

    def test_item_not_found(self, client, db_session):
        ctx = _make_ctx()
        _, session_id = _seed_task_and_session(db_session, ctx)
        fake = _FakeIntelResult(
            response_parsed={"answer": "x", "confidence": 0.9, "sources": []}
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake,
        ):
            r = client.post(
                f"/api/v1/triage/sessions/{session_id}/items/bogus_id/ask",
                json={"question": "Why?"},
                headers=ctx["headers"],
            )
        assert r.status_code == 404

    def test_question_too_long(self, client, db_session):
        ctx = _make_ctx()
        task_id, session_id = _seed_task_and_session(db_session, ctx)
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{task_id}/ask",
            json={"question": "x" * 600},
            headers=ctx["headers"],
        )
        assert r.status_code == 400
        # Detail mentions the limit
        assert "500" in r.text or "characters" in r.text.lower()

    def test_empty_question_422(self, client, db_session):
        """Pydantic min_length=1 fires before our service layer."""
        ctx = _make_ctx()
        task_id, session_id = _seed_task_and_session(db_session, ctx)
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{task_id}/ask",
            json={"question": ""},
            headers=ctx["headers"],
        )
        assert r.status_code == 422

    def test_auth_required(self, client, db_session):
        ctx = _make_ctx()
        task_id, session_id = _seed_task_and_session(db_session, ctx)
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{task_id}/ask",
            json={"question": "Why?"},
        )
        # Either 401 (missing token) or 403 depending on dependency setup.
        assert r.status_code in (401, 403)

    def test_cross_user_isolation(self, client, db_session):
        ctx_a = _make_ctx()
        ctx_b = _make_ctx()
        task_id, session_id = _seed_task_and_session(db_session, ctx_a)
        fake = _FakeIntelResult(
            response_parsed={"answer": "x", "confidence": 0.9, "sources": []}
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake,
        ):
            # User B cannot query user A's session.
            r = client.post(
                f"/api/v1/triage/sessions/{session_id}/items/{task_id}/ask",
                json={"question": "Why?"},
                headers=ctx_b["headers"],
            )
        assert r.status_code == 404


# ── Rate limit structured 429 ──────────────────────────────────────


class TestRateLimit429:
    def test_structured_429_body_and_retry_after_header(
        self, client, db_session
    ):
        ctx = _make_ctx()
        task_id, session_id = _seed_task_and_session(db_session, ctx)
        fake = _FakeIntelResult(
            response_parsed={"answer": "ok", "confidence": 0.9, "sources": []}
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake,
        ):
            # Burn through the 10-req budget.
            for _ in range(10):
                r = client.post(
                    f"/api/v1/triage/sessions/{session_id}/items/{task_id}/ask",
                    json={"question": "Why?"},
                    headers=ctx["headers"],
                )
                assert r.status_code == 200, r.text
            # 11th is rate limited.
            r = client.post(
                f"/api/v1/triage/sessions/{session_id}/items/{task_id}/ask",
                json={"question": "Why?"},
                headers=ctx["headers"],
            )
        assert r.status_code == 429
        detail = r.json().get("detail")
        assert isinstance(detail, dict)
        assert detail["code"] == "rate_limited"
        assert detail["retry_after_seconds"] >= 1
        assert "Pausing AI questions" in detail["message"]
        # Retry-After header is set for clients that honor it.
        assert r.headers.get("Retry-After") == str(detail["retry_after_seconds"])
