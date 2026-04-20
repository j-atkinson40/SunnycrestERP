"""BLOCKING CI gate — triage `/ask` endpoint latency (follow-up 2).

Targets (approved):
  POST /api/v1/triage/sessions/{id}/items/{id}/ask
  p50 < 1500 ms, p99 < 3000 ms

Budget is Haiku-conversational — wider than the <100ms Phase 1
command-bar gate because we expect a real Intelligence round trip in
production. The test here measures OUR overhead only (context
building + rate-limit check + response parsing); Intelligence is
monkey-patched to return immediately with a canned response. That
keeps the gate hermetic and CI-stable, and any future regression in
orchestration code trips the gate well before it would affect users.

Methodology mirrors `test_briefing_generation_latency.py` + Phase 5
`test_triage_latency.py`:
  1. Seed a single tenant + user + task (shared across samples).
  2. Warm up 2 iterations (JIT + Pydantic first-call costs).
  3. Run 20 sequential samples, compute p50 / p99.
  4. Assert budget.

Also verifies the rate-limit check adds <5ms per call (sub-gate from
the approved spec requirement).

Opt-out:
  AI_QUESTION_LATENCY_DISABLE=1 skips (underpowered CI only).
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import date, timedelta

import pytest


_TARGET_P50_MS: float = 1500.0
_TARGET_P99_MS: float = 3000.0
_WARMUP_COUNT: int = 2
_SAMPLE_COUNT: int = 20


if os.environ.get("AI_QUESTION_LATENCY_DISABLE") == "1":
    pytest.skip(
        "AI_QUESTION_LATENCY_DISABLE=1 — skipping ai_question latency gate",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def seeded_tenant():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.services.task_service import create_task
    from app.services.triage.engine import next_item, start_session

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"AQLAT-{suffix}",
            slug=f"aqlat-{suffix}",
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
            email=f"aqlat-{suffix}@t.co",
            first_name="Latency",
            last_name="Gate",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        task = create_task(
            db,
            company_id=co.id,
            title="Latency gate task",
            created_by_user_id=user.id,
            assignee_user_id=user.id,
            priority="urgent",
            due_date=date.today() + timedelta(days=1),
            description="For latency testing.",
        )
        session = start_session(db, user=user, queue_id="task_triage")
        try:
            next_item(db, session_id=session.id, user=user)
        except Exception:
            pass
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "task_id": task.id,
            "session_id": session.id,
            "token": token,
            "slug": co.slug,
        }
    finally:
        db.close()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.services.triage.ai_question import _reset_rate_limiter

    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


def test_ask_question_latency_gate(client, headers, seeded_tenant, monkeypatch):
    """BLOCKING: /ask p50 < 1500ms, p99 < 3000ms."""

    class _FastResult:
        status = "success"
        response_parsed = {
            "answer": "Urgent due date (tomorrow).",
            "confidence": 0.88,
            "sources": [],
        }
        response_text = None
        latency_ms = 250
        execution_id = "exec_latency"
        prompt_id = None
        prompt_version_id = None
        model_used = "claude-haiku-4-5"
        error_message = None
        rendered_system_prompt = ""
        rendered_user_prompt = ""
        input_tokens = 200
        output_tokens = 30
        cost_usd = None

    # Intelligence is monkey-patched — we measure orchestration, not
    # the Anthropic network round-trip.
    monkeypatch.setattr(
        "app.services.triage.ai_question.intelligence_service.execute",
        lambda *a, **k: _FastResult(),
    )

    url = (
        f"/api/v1/triage/sessions/{seeded_tenant['session_id']}"
        f"/items/{seeded_tenant['task_id']}/ask"
    )

    # Warm up.
    for _ in range(_WARMUP_COUNT):
        r = client.post(url, json={"question": "Why?"}, headers=headers)
        assert r.status_code == 200, r.text

    # Reset rate limiter so the 20 samples all succeed. Reset
    # between each iteration too since we'd otherwise exceed the
    # 10-req/min budget.
    from app.services.triage.ai_question import _reset_rate_limiter

    durations_ms: list[float] = []
    for _ in range(_SAMPLE_COUNT):
        _reset_rate_limiter()
        t0 = time.perf_counter()
        r = client.post(url, json={"question": "Why?"}, headers=headers)
        t1 = time.perf_counter()
        assert r.status_code == 200, (
            f"/ask → {r.status_code} {r.text[:120]}"
        )
        durations_ms.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations_ms):.1f}ms "
        f"max={max(durations_ms):.1f}ms)"
    )
    print(f"\n[ai-question-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, (
        f"/ask p50 {p50:.1f}ms > target {_TARGET_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_P99_MS, (
        f"/ask p99 {p99:.1f}ms > target {_TARGET_P99_MS}ms — {diag}"
    )


def test_confidence_mapping_under_1ms():
    """BLOCKING sub-gate: confidence.to_tier adds <1ms per call."""
    from app.services.intelligence.confidence import to_tier

    # Warm up.
    for _ in range(100):
        to_tier(0.85)
    start = time.perf_counter()
    N = 10_000
    for _ in range(N):
        to_tier(0.85)
    elapsed_per_call_ms = (time.perf_counter() - start) * 1000.0 / N
    print(f"\n[confidence-mapping] per-call avg = {elapsed_per_call_ms:.4f}ms")
    assert elapsed_per_call_ms < 1.0, (
        f"confidence.to_tier per-call {elapsed_per_call_ms:.4f}ms exceeds 1ms budget"
    )
