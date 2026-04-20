"""BLOCKING CI gate — Phase 6 briefing generation latency.

Phase 6 targets:
  POST /briefings/v2/generate  p50 < 2000 ms, p99 < 5000 ms

Budget is intentionally wider than Phases 1-5 because briefings are
Haiku-generation-dominated. The typical user-perceived flow is the
every-15-min scheduler sweep (user never blocks on it); the API
endpoint is on-demand for "generate now" requests.

Methodology (matches Phase 5 gate structure):
  1. Seed a tenant + user + a small legacy context payload (empty
     builders return fast; the budget covers Intelligence call overhead).
  2. Monkey-patch `intelligence_service.execute` to return immediately
     with a canned response — we measure our OWN overhead, not the
     Anthropic API. This keeps the gate hermetic + CI-stable.
  3. Run 10 samples sequentially and compute p50/p99.
  4. Fail the gate if the budget is exceeded.

Opt-out:
  - `BRIEFING_LATENCY_DISABLE=1` skips (underpowered CI only).
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from decimal import Decimal

import pytest


_TARGET_P50_MS: float = 2000.0
_TARGET_P99_MS: float = 5000.0
_WARMUP_COUNT: int = 2
_SAMPLE_COUNT: int = 10


if os.environ.get("BRIEFING_LATENCY_DISABLE") == "1":
    pytest.skip(
        "BRIEFING_LATENCY_DISABLE=1 — skipping briefing latency gate",
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
            name=f"BRIEF-{suffix}",
            slug=f"brief-{suffix}",
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
            email=f"brief-{suffix}@t.co",
            first_name="Brief",
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
            "company_id": co.id,
            "user_id": user.id,
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


def test_briefing_generate_latency_gate(client, headers, monkeypatch):
    """BLOCKING: POST /briefings/v2/generate p50 < 2000ms, p99 < 5000ms."""

    class _FastResult:
        status = "success"
        response_parsed = {
            "narrative_text": "Good morning. All systems nominal.",
            "structured_sections": {"greeting": "Good morning."},
        }
        response_text = None
        input_tokens = 500
        output_tokens = 100
        cost_usd = Decimal("0.001")
        latency_ms = 50

    # Replace Intelligence call — measure our orchestration overhead only.
    monkeypatch.setattr(
        "app.services.intelligence.intelligence_service.execute",
        lambda *a, **k: _FastResult(),
    )

    # Warm up
    for _ in range(_WARMUP_COUNT):
        r = client.post(
            "/api/v1/briefings/v2/generate",
            json={"briefing_type": "morning"},
            headers=headers,
        )
        assert r.status_code == 200, r.text

    durations_ms: list[float] = []
    for _ in range(_SAMPLE_COUNT):
        t0 = time.perf_counter()
        r = client.post(
            "/api/v1/briefings/v2/generate",
            json={"briefing_type": "morning"},
            headers=headers,
        )
        t1 = time.perf_counter()
        assert r.status_code == 200, (
            f"briefing generate → {r.status_code} {r.text[:120]}"
        )
        durations_ms.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations_ms):.1f}ms "
        f"max={max(durations_ms):.1f}ms)"
    )
    print(f"\n[briefing-generate-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, (
        f"briefing generate p50 {p50:.1f}ms > target "
        f"{_TARGET_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_P99_MS, (
        f"briefing generate p99 {p99:.1f}ms > target "
        f"{_TARGET_P99_MS}ms — {diag}"
    )
