"""BLOCKING CI gate — Workflow Arc Phase 8a endpoint latency.

Targets per Phase 8a scope decision:
  GET /workflows?scope=core|vertical|tenant     p50 < 100 ms, p99 < 300 ms
  POST /workflows/{id}/fork                     p50 < 200 ms, p99 < 500 ms
  GET /spaces (with system spaces resolved)     identical to UI/UX Arc budget
                                                  (p50 < 100 ms, p99 < 300 ms)

Phase 8a adds scope-filter SQL + used_by_count aggregate. The existing
`workflows` table is tiny (~40 rows on a seeded tenant) so measuring
the tab filter in isolation mostly measures ORM + FastAPI overhead.
Fork is bounded by step-count of the source + step-param copy. System
space resolution is one extra permission check per user; Phase 3
baseline was p50=15ms / p99=20ms against the same fixture set.

20 samples sequential per endpoint, mixed shapes where relevant.

Opt-out: WORKFLOW_ARC_LATENCY_DISABLE=1 skips.
"""

from __future__ import annotations

import os
import statistics
import time
import uuid

import pytest


_TARGET_P50_MS: float = 100.0
_TARGET_P99_MS: float = 300.0
_TARGET_FORK_P50_MS: float = 200.0
_TARGET_FORK_P99_MS: float = 500.0
_WARMUP_COUNT: int = 3
_SAMPLE_COUNT: int = 20


if os.environ.get("WORKFLOW_ARC_LATENCY_DISABLE") == "1":
    pytest.skip(
        "WORKFLOW_ARC_LATENCY_DISABLE=1 — skipping Phase 8a latency gate",
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

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"WFLAT-{suffix}",
            slug=f"wflat-{suffix}",
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
            email=f"lat-{suffix}@wflat.co",
            first_name="Lat",
            last_name="Gate",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "token": token,
            "slug": co.slug,
            "company_id": co.id,
            "user_id": user.id,
        }
    finally:
        db.close()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


def _sample(client, headers, path: str) -> list[float]:
    # Warm up.
    for _ in range(_WARMUP_COUNT):
        r = client.get(path, headers=headers)
        assert r.status_code == 200, r.text
    durations = []
    for _ in range(_SAMPLE_COUNT):
        t0 = time.perf_counter()
        r = client.get(path, headers=headers)
        t1 = time.perf_counter()
        assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:120]}"
        durations.append((t1 - t0) * 1000.0)
    return durations


def _assert_budget(
    durations: list[float], *, p50_budget: float, p99_budget: float, label: str
):
    p50 = statistics.median(durations)
    p99 = statistics.quantiles(durations, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations):.1f}ms "
        f"max={max(durations):.1f}ms)"
    )
    print(f"\n[{label}-latency] {diag}")
    assert p50 <= p50_budget, (
        f"{label} p50 {p50:.1f}ms > {p50_budget}ms — {diag}"
    )
    assert p99 <= p99_budget, (
        f"{label} p99 {p99:.1f}ms > {p99_budget}ms — {diag}"
    )


def test_workflow_scope_core_latency(client, headers):
    durations = _sample(client, headers, "/api/v1/workflows?scope=core")
    _assert_budget(
        durations,
        p50_budget=_TARGET_P50_MS,
        p99_budget=_TARGET_P99_MS,
        label="workflow-scope-core",
    )


def test_workflow_scope_core_with_used_by_latency(client, headers):
    """With include_used_by=true, each row fires an aggregate —
    should still stay within budget for Phase 8a data sizes."""
    durations = _sample(
        client,
        headers,
        "/api/v1/workflows?scope=core&include_used_by=true",
    )
    _assert_budget(
        durations,
        p50_budget=_TARGET_P50_MS,
        p99_budget=_TARGET_P99_MS,
        label="workflow-scope-core-used-by",
    )


def test_workflow_scope_vertical_latency(client, headers):
    durations = _sample(
        client, headers, "/api/v1/workflows?scope=vertical"
    )
    _assert_budget(
        durations,
        p50_budget=_TARGET_P50_MS,
        p99_budget=_TARGET_P99_MS,
        label="workflow-scope-vertical",
    )


def test_spaces_list_with_system_space_latency(
    client, headers, seeded_tenant
):
    """Settings system space adds one extra space + one permission
    check to the resolve path. Budget unchanged from UI/UX arc."""
    # Seed so system space is in preferences.
    from app.database import SessionLocal
    from app.models.user import User
    from app.services.spaces import seed_for_user

    db = SessionLocal()
    try:
        user = (
            db.query(User).filter(User.id == seeded_tenant["user_id"]).one()
        )
        seed_for_user(db, user=user)
    finally:
        db.close()

    durations = _sample(client, headers, "/api/v1/spaces")
    _assert_budget(
        durations,
        p50_budget=_TARGET_P50_MS,
        p99_budget=_TARGET_P99_MS,
        label="spaces-with-system",
    )


def test_workflow_fork_latency(client, headers, seeded_tenant):
    """Fork copies a workflow + its steps + its platform-default
    params. Budget wider (200ms/500ms) because it's a multi-table
    write path. The test uses a freshly-created source workflow for
    each sample so the AlreadyForked check doesn't kick in; we
    delete the fork after measurement."""
    from app.database import SessionLocal
    from app.models.workflow import Workflow, WorkflowStep

    db = SessionLocal()
    try:
        # One source workflow per sample; create them upfront so the
        # measurement excludes source setup time.
        source_ids = []
        for i in range(_SAMPLE_COUNT + _WARMUP_COUNT):
            src_id = str(uuid.uuid4())
            src = Workflow(
                id=src_id,
                company_id=None,
                name=f"ForkSrc-{i}",
                description="fork latency source",
                tier=1,
                scope="core",
                vertical=None,
                trigger_type="manual",
                is_active=True,
                is_system=True,
            )
            db.add(src)
            db.flush()
            for step_n in range(3):
                db.add(
                    WorkflowStep(
                        id=str(uuid.uuid4()),
                        workflow_id=src_id,
                        step_order=step_n + 1,
                        step_key=f"step_{step_n}",
                        step_type="action",
                        config={"n": step_n},
                    )
                )
            source_ids.append(src_id)
        db.commit()
    finally:
        db.close()

    # Warm up with the first _WARMUP_COUNT sources.
    for i in range(_WARMUP_COUNT):
        r = client.post(
            f"/api/v1/workflows/{source_ids[i]}/fork",
            json={},
            headers=headers,
        )
        assert r.status_code == 200, r.text

    # Measured samples use the remaining sources.
    durations = []
    for i in range(_WARMUP_COUNT, _WARMUP_COUNT + _SAMPLE_COUNT):
        t0 = time.perf_counter()
        r = client.post(
            f"/api/v1/workflows/{source_ids[i]}/fork",
            json={},
            headers=headers,
        )
        t1 = time.perf_counter()
        assert r.status_code == 200, r.text
        durations.append((t1 - t0) * 1000.0)

    _assert_budget(
        durations,
        p50_budget=_TARGET_FORK_P50_MS,
        p99_budget=_TARGET_FORK_P99_MS,
        label="workflow-fork",
    )
