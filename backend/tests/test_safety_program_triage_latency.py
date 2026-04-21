"""BLOCKING CI gates — Phase 8d.1 safety_program triage latency.

Two gates:
  safety_program_triage:
    next_item     p50 < 100 ms, p99 < 300 ms
    apply_action  p50 < 200 ms, p99 < 500 ms
      (apply = safety_program.approve which delegates to
       svc.approve_generation which does: SafetyProgramGeneration
       status transition + SafetyProgram upsert. No AI call, no R2,
       no email. Fast.)

Methodology identical to Phase 5/8b/8c/8d:
  - Seed one tenant + admin + N pending_review generations.
  - 3 warmups + 30 samples sequential.
  - Each generation gets its own distinct osha_standard_code to
    avoid version-increment convergence across samples (each approve
    creates a fresh SafetyProgram row).

Opt-out: TRIAGE_LATENCY_DISABLE=1.
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
_SEED_ITEM_COUNT: int = 40


if os.environ.get("TRIAGE_LATENCY_DISABLE") == "1":
    pytest.skip(
        "TRIAGE_LATENCY_DISABLE=1 — skipping Phase 8d.1 latency gates",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _seed_safety_program_tenant() -> dict:
    """Seed a MFG tenant + admin + N pending_review SafetyProgramGeneration
    rows, each with a distinct osha_standard_code so each approve_line
    action creates a fresh SafetyProgram row (no version-increment
    collision across samples)."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.safety_program_generation import (
        SafetyProgramGeneration,
    )
    from app.models.safety_training_topic import SafetyTrainingTopic
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"SPLAT-{suffix}",
            slug=f"splat-{suffix}",
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
            email=f"lat-{suffix}@sp.co",
            first_name="SP",
            last_name="Lat",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        now = datetime.now(timezone.utc)
        generation_ids: list[str] = []
        for i in range(_SEED_ITEM_COUNT):
            topic = SafetyTrainingTopic(
                id=str(uuid.uuid4()),
                month_number=((i % 12) + 1),
                topic_key=f"lat_topic_{suffix}_{i:03d}",
                title=f"Topic {i:03d}",
                description=f"Topic {i:03d} description.",
                osha_standard=f"TEST.{i:04d}",
                osha_standard_label=f"Test standard {i:04d}",
                key_points=["a", "b"],
                is_high_risk=False,
            )
            db.add(topic)
            db.flush()

            gen = SafetyProgramGeneration(
                id=str(uuid.uuid4()),
                tenant_id=co.id,
                topic_id=topic.id,
                year=2026,
                month_number=((i % 12) + 1),
                osha_standard_code=f"TEST.{i:04d}",
                osha_scrape_status="success",
                osha_scraped_text="Scrape snippet.",
                osha_scraped_at=now,
                generated_content=f"<h2>Program {i}</h2>",
                generated_html=f"<html><body>Program {i}</body></html>",
                generation_status="complete",
                generation_model="claude-sonnet-4-20250514",
                generation_token_usage={"input_tokens": 100, "output_tokens": 1000},
                generated_at=now,
                status="pending_review",
            )
            db.add(gen)
            generation_ids.append(gen.id)
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
            "generation_ids": generation_ids,
        }
    finally:
        db.close()


def _run_next_item_gate(
    client, tenant_ctx: dict, queue_id: str, label: str
) -> None:
    headers = {
        "Authorization": f"Bearer {tenant_ctx['token']}",
        "X-Company-Slug": tenant_ctx["slug"],
    }
    r = client.post(
        f"/api/v1/triage/queues/{queue_id}/sessions", headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["session_id"]

    for _ in range(_WARMUP_COUNT):
        client.post(
            f"/api/v1/triage/sessions/{session_id}/next", headers=headers,
        )

    durations: list[float] = []
    for _ in range(_SAMPLE_COUNT):
        t0 = time.perf_counter()
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/next", headers=headers,
        )
        t1 = time.perf_counter()
        assert r.status_code in (200, 204), (
            f"next_item → {r.status_code} {r.text[:120]}"
        )
        durations.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations)
    p99 = statistics.quantiles(durations, n=100)[-1]
    print(
        f"\n[{label}-next-item-latency] "
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations):.1f}ms "
        f"max={max(durations):.1f}ms)"
    )
    assert p50 <= _TARGET_NEXT_P50_MS, (
        f"{label} next_item p50 {p50:.1f}ms > {_TARGET_NEXT_P50_MS}ms"
    )
    assert p99 <= _TARGET_NEXT_P99_MS, (
        f"{label} next_item p99 {p99:.1f}ms > {_TARGET_NEXT_P99_MS}ms"
    )


def _run_apply_action_gate(
    client,
    tenant_ctx: dict,
    queue_id: str,
    label: str,
    *,
    item_ids: list[str],
    action_id: str,
) -> None:
    headers = {
        "Authorization": f"Bearer {tenant_ctx['token']}",
        "X-Company-Slug": tenant_ctx["slug"],
    }
    r = client.post(
        f"/api/v1/triage/queues/{queue_id}/sessions", headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["session_id"]

    for i in range(_WARMUP_COUNT):
        client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{item_ids[i]}/action",
            json={"action_id": action_id},
            headers=headers,
        )

    durations: list[float] = []
    for i in range(_SAMPLE_COUNT):
        idx = _WARMUP_COUNT + i
        t0 = time.perf_counter()
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{item_ids[idx]}/action",
            json={"action_id": action_id},
            headers=headers,
        )
        t1 = time.perf_counter()
        assert r.status_code == 200, (
            f"apply_action → {r.status_code} {r.text[:200]}"
        )
        durations.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations)
    p99 = statistics.quantiles(durations, n=100)[-1]
    print(
        f"\n[{label}-apply-action-latency] "
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations):.1f}ms "
        f"max={max(durations):.1f}ms)"
    )
    assert p50 <= _TARGET_ACTION_P50_MS, (
        f"{label} apply_action p50 {p50:.1f}ms > "
        f"{_TARGET_ACTION_P50_MS}ms"
    )
    assert p99 <= _TARGET_ACTION_P99_MS, (
        f"{label} apply_action p99 {p99:.1f}ms > "
        f"{_TARGET_ACTION_P99_MS}ms"
    )


@pytest.fixture(scope="module")
def safety_program_tenant():
    return _seed_safety_program_tenant()


def test_safety_program_next_item_latency(client, safety_program_tenant):
    _run_next_item_gate(
        client,
        safety_program_tenant,
        "safety_program_triage",
        "safety-program",
    )


def test_safety_program_apply_action_latency(
    client, safety_program_tenant
):
    """Approve orchestration overhead: status transition +
    SafetyProgram upsert. No AI, no R2, no email — should be fast."""
    _run_apply_action_gate(
        client,
        safety_program_tenant,
        "safety_program_triage",
        "safety-program",
        item_ids=safety_program_tenant["generation_ids"],
        action_id="approve",
    )
