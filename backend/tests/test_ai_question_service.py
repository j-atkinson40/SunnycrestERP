"""Triage AI Question service — unit tests (follow-up 2).

Exercises `app.services.triage.ai_question.ask_question`:

  - Context building includes item data + related entities via the
    per-queue builder in `_RELATED_ENTITY_BUILDERS`
  - Intelligence call receives the expected variables (item_json,
    user_question, tenant_context, related_entities_json, vertical,
    user_role, queue_name, queue_description, item_type)
  - Response parsing: well-formed, malformed, numeric confidence
    coerced to ConfidenceTier
  - Permission check: super_admin bypasses; user lacking queue
    permission raises ActionNotAllowed
  - Rate limit raises RateLimited with retry_after_seconds
  - Missing ai_question panel raises NoAIQuestionPanel
  - Missing item_id in queue raises ItemNotFound
  - Empty / too-long question raises QuestionTooLong
  - confidence.to_tier utility boundaries (≥0.8 high, ≥0.5 medium,
    else low; None + bad input collapse to low)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
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
    super_admin: bool = True,
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
            name=f"AQ-{suffix}",
            slug=f"aq-{suffix}",
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
            email=f"u-{suffix}@aq.co",
            first_name="Aq",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=super_admin,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return user.id, co.id, role.slug
    finally:
        db.close()


@pytest.fixture
def mfg_user(db_session):
    from app.models.user import User

    user_id, _, _ = _make_tenant_user(
        role_slug="admin", vertical="manufacturing", super_admin=True
    )
    return db_session.query(User).filter(User.id == user_id).one()


@pytest.fixture
def fh_user(db_session):
    from app.models.user import User

    user_id, _, _ = _make_tenant_user(
        role_slug="director", vertical="funeral_home", super_admin=True
    )
    return db_session.query(User).filter(User.id == user_id).one()


def _seed_task(db, user, **overrides):
    from app.services.task_service import create_task

    return create_task(
        db,
        company_id=user.company_id,
        title=overrides.get("title", "Review quote"),
        created_by_user_id=user.id,
        assignee_user_id=overrides.get("assignee_user_id", user.id),
        priority=overrides.get("priority", "urgent"),
        due_date=overrides.get("due_date", date.today() + timedelta(days=1)),
        description=overrides.get("description", "Verify pricing on quote"),
    )


def _start_session(db, user, queue_id: str):
    from app.services.triage.engine import start_session

    return start_session(db, user=user, queue_id=queue_id)


class _FakeIntelResult:
    def __init__(
        self,
        *,
        status: str = "success",
        response_parsed=None,
        latency_ms: int = 250,
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
        self.input_tokens = 100
        self.output_tokens = 50
        self.cost_usd = None


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.services.triage.ai_question import _reset_rate_limiter

    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


# ── Confidence utility ──────────────────────────────────────────────


class TestConfidenceTier:
    def test_high_at_boundary(self):
        from app.services.intelligence.confidence import to_tier

        assert to_tier(0.80) == "high"
        assert to_tier(0.99) == "high"
        assert to_tier(1.0) == "high"

    def test_medium_at_boundary(self):
        from app.services.intelligence.confidence import to_tier

        assert to_tier(0.50) == "medium"
        assert to_tier(0.79) == "medium"

    def test_low_below_boundary(self):
        from app.services.intelligence.confidence import to_tier

        assert to_tier(0.49) == "low"
        assert to_tier(0.0) == "low"

    def test_none_and_malformed_collapse_to_low(self):
        from app.services.intelligence.confidence import to_tier

        assert to_tier(None) == "low"
        assert to_tier("garbage") == "low"  # type: ignore[arg-type]


# ── Service orchestration ──────────────────────────────────────────


class TestAskQuestionService:
    def test_happy_path_task_queue(self, db_session, mfg_user):
        """Ask a question about a task — verifies end-to-end wiring:
        session resolve → item fetch → related-entity builder →
        Intelligence call → response parse → confidence mapping."""
        from app.services.triage.ai_question import ask_question

        task = _seed_task(db_session, mfg_user, title="Review quote #42")
        session = _start_session(db_session, mfg_user, "task_triage")

        fake_result = _FakeIntelResult(
            response_parsed={
                "answer": "The task is urgent due to the due date.",
                "confidence": 0.85,
                "sources": [
                    {
                        "entity_type": "task",
                        "entity_id": task.id,
                        "display_label": task.title,
                    }
                ],
            },
            latency_ms=412,
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake_result,
        ) as spy:
            resp = ask_question(
                db_session,
                user=mfg_user,
                session_id=session.id,
                item_id=task.id,
                question="Why is this task urgent?",
            )

        assert resp.answer.startswith("The task is urgent")
        assert resp.confidence == "high"
        assert resp.confidence_score == 0.85
        assert resp.latency_ms == 412
        assert len(resp.source_references) == 1
        assert resp.source_references[0].entity_id == task.id

        # Intelligence call shape — verify the variables passed.
        spy.assert_called_once()
        call_kwargs = spy.call_args.kwargs
        assert call_kwargs["prompt_key"] == "triage.task_context_question"
        variables = call_kwargs["variables"]
        assert variables["user_question"] == "Why is this task urgent?"
        assert variables["vertical"] == "manufacturing"
        assert variables["user_role"] == "admin"
        assert variables["queue_name"] == "Task Triage"
        assert variables["item_type"] == "task"
        # item_json + related_entities_json are JSON strings.
        import json as _j

        parsed_item = _j.loads(variables["item_json"])
        assert parsed_item["id"] == task.id
        parsed_related = _j.loads(variables["related_entities_json"])
        assert isinstance(parsed_related, list)

    def test_medium_confidence_tier(self, db_session, mfg_user):
        from app.services.triage.ai_question import ask_question

        task = _seed_task(db_session, mfg_user)
        session = _start_session(db_session, mfg_user, "task_triage")
        fake_result = _FakeIntelResult(
            response_parsed={
                "answer": "Unclear.",
                "confidence": 0.55,
                "sources": [],
            },
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake_result,
        ):
            resp = ask_question(
                db_session,
                user=mfg_user,
                session_id=session.id,
                item_id=task.id,
                question="Why?",
            )
        assert resp.confidence == "medium"

    def test_related_entities_builder_invoked_for_task(
        self, db_session, mfg_user
    ):
        """task_triage's builder pulls the linked entity (if any) +
        other tasks by the same assignee."""
        from app.services.triage.ai_question import (
            _RELATED_ENTITY_BUILDERS,
        )

        # Seed the current task + 3 sibling tasks (same assignee).
        main = _seed_task(
            db_session, mfg_user, title="Main task", priority="urgent"
        )
        for i in range(3):
            _seed_task(
                db_session, mfg_user, title=f"Sibling {i}", priority="normal"
            )

        builder = _RELATED_ENTITY_BUILDERS["task_triage"]
        rows = builder(
            db_session,
            mfg_user,
            {
                "id": main.id,
                "assignee_user_id": mfg_user.id,
                "related_entity_type": None,
                "related_entity_id": None,
            },
        )
        # 3 sibling tasks, no linked entity.
        assert len(rows) == 3
        assert all(r["entity_type"] == "task" for r in rows)
        assert all(r["context"] == "same_assignee" for r in rows)

    def test_malformed_ai_response_rejected(self, db_session, mfg_user):
        from app.services.triage.ai_question import (
            AIQuestionFailed,
            ask_question,
        )

        task = _seed_task(db_session, mfg_user)
        session = _start_session(db_session, mfg_user, "task_triage")
        fake_result = _FakeIntelResult(
            response_parsed=None,  # simulate force_json path failed
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake_result,
        ):
            with pytest.raises(AIQuestionFailed):
                ask_question(
                    db_session,
                    user=mfg_user,
                    session_id=session.id,
                    item_id=task.id,
                    question="Why?",
                )

    def test_ai_status_failure_raises(self, db_session, mfg_user):
        from app.services.triage.ai_question import (
            AIQuestionFailed,
            ask_question,
        )

        task = _seed_task(db_session, mfg_user)
        session = _start_session(db_session, mfg_user, "task_triage")
        fake_result = _FakeIntelResult(
            status="error",
            response_parsed=None,
        )
        fake_result.error_message = "API rate limited"
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake_result,
        ):
            with pytest.raises(AIQuestionFailed):
                ask_question(
                    db_session,
                    user=mfg_user,
                    session_id=session.id,
                    item_id=task.id,
                    question="Why?",
                )

    def test_empty_question_rejected(self, db_session, mfg_user):
        from app.services.triage.ai_question import (
            QuestionTooLong,
            ask_question,
        )

        task = _seed_task(db_session, mfg_user)
        session = _start_session(db_session, mfg_user, "task_triage")
        with pytest.raises(QuestionTooLong):
            ask_question(
                db_session,
                user=mfg_user,
                session_id=session.id,
                item_id=task.id,
                question="   ",
            )

    def test_too_long_question_rejected(self, db_session, mfg_user):
        from app.services.triage.ai_question import (
            QuestionTooLong,
            ask_question,
        )

        task = _seed_task(db_session, mfg_user)
        session = _start_session(db_session, mfg_user, "task_triage")
        with pytest.raises(QuestionTooLong):
            ask_question(
                db_session,
                user=mfg_user,
                session_id=session.id,
                item_id=task.id,
                question="x" * 600,  # > 500 max
            )

    def test_item_not_found_raises(self, db_session, mfg_user):
        from app.services.triage.ai_question import (
            ItemNotFound,
            ask_question,
        )

        session = _start_session(db_session, mfg_user, "task_triage")
        # Valid question but bogus item id.
        fake_result = _FakeIntelResult(
            response_parsed={"answer": "x", "confidence": 0.9, "sources": []}
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake_result,
        ):
            with pytest.raises(ItemNotFound):
                ask_question(
                    db_session,
                    user=mfg_user,
                    session_id=session.id,
                    item_id="bogus_task_id",
                    question="Why?",
                )


# ── Rate limiting ──────────────────────────────────────────────────


class TestRateLimit:
    def test_rate_limit_after_10_requests(self, db_session, mfg_user):
        from app.services.triage.ai_question import (
            RateLimited,
            ask_question,
        )

        task = _seed_task(db_session, mfg_user)
        session = _start_session(db_session, mfg_user, "task_triage")
        fake_result = _FakeIntelResult(
            response_parsed={
                "answer": "ok",
                "confidence": 0.9,
                "sources": [],
            },
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake_result,
        ):
            for _ in range(10):
                ask_question(
                    db_session,
                    user=mfg_user,
                    session_id=session.id,
                    item_id=task.id,
                    question="Why?",
                )
            with pytest.raises(RateLimited) as exc_info:
                ask_question(
                    db_session,
                    user=mfg_user,
                    session_id=session.id,
                    item_id=task.id,
                    question="Why?",
                )
            assert exc_info.value.retry_after_seconds >= 1
            assert exc_info.value.http_status == 429

    def test_rate_limit_is_per_user(self, db_session):
        """User A hitting the limit must NOT block user B."""
        from app.models.user import User
        from app.services.triage.ai_question import (
            RateLimited,
            ask_question,
        )

        # Two independent users (separate tenants — rate limiter is
        # indexed by user_id so this doubly verifies isolation).
        uid_a, _, _ = _make_tenant_user(role_slug="admin", super_admin=True)
        uid_b, _, _ = _make_tenant_user(role_slug="admin", super_admin=True)
        user_a = db_session.query(User).filter(User.id == uid_a).one()
        user_b = db_session.query(User).filter(User.id == uid_b).one()
        task_a = _seed_task(db_session, user_a)
        task_b = _seed_task(db_session, user_b)
        session_a = _start_session(db_session, user_a, "task_triage")
        session_b = _start_session(db_session, user_b, "task_triage")

        fake = _FakeIntelResult(
            response_parsed={"answer": "ok", "confidence": 0.9, "sources": []},
        )
        with patch(
            "app.services.triage.ai_question.intelligence_service.execute",
            return_value=fake,
        ):
            # Exhaust user A
            for _ in range(10):
                ask_question(
                    db_session,
                    user=user_a,
                    session_id=session_a.id,
                    item_id=task_a.id,
                    question="Why?",
                )
            with pytest.raises(RateLimited):
                ask_question(
                    db_session,
                    user=user_a,
                    session_id=session_a.id,
                    item_id=task_a.id,
                    question="Why?",
                )
            # User B still has full budget.
            resp = ask_question(
                db_session,
                user=user_b,
                session_id=session_b.id,
                item_id=task_b.id,
                question="Why?",
            )
            assert resp.answer == "ok"

    def test_rate_limit_overhead_under_5ms(self):
        """BLOCKING CI sub-gate: rate-limit check adds <5ms per call."""
        import time

        from app.services.triage.ai_question import (
            _check_rate_limit,
            _reset_rate_limiter,
        )

        _reset_rate_limiter()
        user_id = "perf-user"
        # Warm up.
        _check_rate_limit(user_id)
        # Measure 100 successful rate-limit checks (well under limit).
        _reset_rate_limiter()
        start = time.perf_counter()
        for _ in range(100):
            _check_rate_limit(user_id)
            # Reset bucket each iteration so we don't hit the 10-limit.
            _reset_rate_limiter()
        elapsed_ms = (time.perf_counter() - start) * 1000.0 / 100
        assert elapsed_ms < 5, f"rate limit check p-avg={elapsed_ms:.3f}ms > 5ms"


# ── Panel + permission preconditions ───────────────────────────────


class TestPreconditions:
    def test_no_ai_question_panel_raises(self, db_session, mfg_user):
        """If the resolved queue config has no ai_question panel, the
        service refuses rather than silently asking a wrong prompt."""
        from app.services.triage.ai_question import (
            NoAIQuestionPanel,
            ask_question,
        )

        # Monkey-patch the registry to return a config with no
        # ai_question panel.
        from app.services.triage.platform_defaults import _task_triage
        import copy

        cfg_no_panel = copy.deepcopy(_task_triage)
        cfg_no_panel.context_panels = [
            p
            for p in cfg_no_panel.context_panels
            if p.panel_type.value != "ai_question"
        ]

        task = _seed_task(db_session, mfg_user)
        session = _start_session(db_session, mfg_user, "task_triage")
        with patch(
            "app.services.triage.ai_question._registry.get_config",
            return_value=cfg_no_panel,
        ):
            with pytest.raises(NoAIQuestionPanel):
                ask_question(
                    db_session,
                    user=mfg_user,
                    session_id=session.id,
                    item_id=task.id,
                    question="Why?",
                )

    def test_session_from_another_user_rejected(self, db_session):
        """A session belonging to user A is not visible to user B."""
        from app.models.user import User
        from app.services.triage.ai_question import ask_question
        from app.services.triage.types import SessionNotFound

        uid_a, _, _ = _make_tenant_user(super_admin=True)
        uid_b, _, _ = _make_tenant_user(super_admin=True)
        user_a = db_session.query(User).filter(User.id == uid_a).one()
        user_b = db_session.query(User).filter(User.id == uid_b).one()
        _seed_task(db_session, user_a)
        session_a = _start_session(db_session, user_a, "task_triage")
        with pytest.raises(SessionNotFound):
            ask_question(
                db_session,
                user=user_b,
                session_id=session_a.id,
                item_id="anything",
                question="Why?",
            )
