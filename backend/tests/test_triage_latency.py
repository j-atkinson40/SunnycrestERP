"""BLOCKING CI gate — Triage engine latency.

Phase 5 targets:
  next_item      p50 < 100 ms, p99 < 300 ms
  apply_action   p50 < 200 ms, p99 < 500 ms

These are the numbers the user feels per triage interaction. Drift
here is immediately visible — the user perceives the workspace as
sluggish.

Methodology:
  1. Seed a tenant + 20 pending tasks (mid-sized real-world queue).
  2. Warm up the connection pool + query cache.
  3. Run N=30 sequential next_item calls + N=30 apply_action calls,
     measuring each.
  4. Compute p50 / p99 per operation.
  5. Fail the gate if any budget is exceeded.

Sequential, not concurrent — measures single-call latency the user
actually feels per keystroke-equivalent.

Environment opt-outs:
  - `TRIAGE_LATENCY_DISABLE=1` skips the test (underpowered CI
    runners only).
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import datetime, timezone

import pytest


_TARGET_NEXT_P50_MS: float = 100.0
_TARGET_NEXT_P99_MS: float = 300.0
_TARGET_ACTION_P50_MS: float = 200.0
_TARGET_ACTION_P99_MS: float = 500.0
_WARMUP_COUNT: int = 3
_SAMPLE_COUNT: int = 30
_SEED_TASK_COUNT: int = 20


if os.environ.get("TRIAGE_LATENCY_DISABLE") == "1":
    pytest.skip(
        "TRIAGE_LATENCY_DISABLE=1 — skipping triage latency gate",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _seed_tenant_with_tasks():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.task import Task
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"LAT-{suffix}",
            slug=f"lat-{suffix}",
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
            email=f"lat-{suffix}@t.co",
            first_name="Lat",
            last_name="Gate",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        priorities = ["urgent", "high", "normal", "low"]
        for i in range(_SEED_TASK_COUNT):
            db.add(
                Task(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    title=f"Task #{i:03d}",
                    description=f"Seed task {i}",
                    assignee_user_id=user.id,
                    created_by_user_id=user.id,
                    priority=priorities[i % len(priorities)],
                    status="open",
                    is_active=True,
                )
            )
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
        }
    finally:
        db.close()


@pytest.fixture(scope="module")
def seeded_tenant():
    return _seed_tenant_with_tasks()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


# ── Gate ─────────────────────────────────────────────────────────────


def test_triage_next_item_latency_gate(client, headers):
    """BLOCKING: next_item p50 < 100 ms, p99 < 300 ms."""
    # Start a session once
    r = client.post("/api/v1/triage/queues/task_triage/sessions", headers=headers)
    assert r.status_code == 201
    session_id = r.json()["session_id"]

    # Warm-up
    for _ in range(_WARMUP_COUNT):
        client.post(f"/api/v1/triage/sessions/{session_id}/next", headers=headers)

    durations_ms: list[float] = []
    for _ in range(_SAMPLE_COUNT):
        t0 = time.perf_counter()
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/next", headers=headers
        )
        t1 = time.perf_counter()
        # 200 when item exists, 204 when exhausted — both acceptable
        # for latency purposes (the engine still did its scan).
        assert r.status_code in (200, 204), (
            f"next_item → {r.status_code} {r.text[:120]}"
        )
        durations_ms.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations_ms):.1f}ms "
        f"max={max(durations_ms):.1f}ms)"
    )
    print(f"\n[triage-next-item-latency] {diag}")

    assert p50 <= _TARGET_NEXT_P50_MS, (
        f"triage next_item p50 {p50:.1f}ms > target "
        f"{_TARGET_NEXT_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_NEXT_P99_MS, (
        f"triage next_item p99 {p99:.1f}ms > target "
        f"{_TARGET_NEXT_P99_MS}ms — {diag}"
    )


def test_triage_apply_action_latency_gate(client, headers, seeded_tenant):
    """BLOCKING: apply_action p50 < 200 ms, p99 < 500 ms.

    Seeds more tasks for this test — each apply_action consumes a
    task, so we need enough inventory for sample + warmup.
    """
    from app.database import SessionLocal
    from app.models.task import Task

    extra_count = _SAMPLE_COUNT + _WARMUP_COUNT + 5
    db = SessionLocal()
    try:
        task_ids: list[str] = []
        for i in range(extra_count):
            t = Task(
                id=str(uuid.uuid4()),
                company_id=seeded_tenant["company_id"],
                title=f"ApplyAction seed {i}",
                description=f"action-latency-seed-{i}",
                assignee_user_id=seeded_tenant["user_id"],
                created_by_user_id=seeded_tenant["user_id"],
                priority="normal",
                status="open",
                is_active=True,
            )
            db.add(t)
            task_ids.append(t.id)
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/api/v1/triage/queues/task_triage/sessions", headers=headers
    )
    session_id = r.json()["session_id"]

    # Warm up — also consumes some tasks
    for i in range(_WARMUP_COUNT):
        tid = task_ids[i]
        client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{tid}/action",
            json={"action_id": "complete"},
            headers=headers,
        )

    durations_ms: list[float] = []
    for i in range(_SAMPLE_COUNT):
        tid = task_ids[_WARMUP_COUNT + i]
        t0 = time.perf_counter()
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{tid}/action",
            json={"action_id": "complete"},
            headers=headers,
        )
        t1 = time.perf_counter()
        assert r.status_code == 200, (
            f"apply_action → {r.status_code} {r.text[:120]}"
        )
        durations_ms.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations_ms):.1f}ms "
        f"max={max(durations_ms):.1f}ms)"
    )
    print(f"\n[triage-apply-action-latency] {diag}")

    assert p50 <= _TARGET_ACTION_P50_MS, (
        f"triage apply_action p50 {p50:.1f}ms > target "
        f"{_TARGET_ACTION_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_ACTION_P99_MS, (
        f"triage apply_action p99 {p99:.1f}ms > target "
        f"{_TARGET_ACTION_P99_MS}ms — {diag}"
    )
