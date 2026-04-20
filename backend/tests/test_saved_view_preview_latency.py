"""BLOCKING CI gate — Saved View PREVIEW latency (follow-up 3).

Fails CI if p99 > 500 ms or p50 > 150 ms for the
`/api/v1/saved-views/preview` endpoint. Preview is the hot path of
the builder live-preview pane: it fires on every 300ms-debounced
config change and backs the directional UX the arc promised.

Targets match the existing /execute gate — Phase 2 measured that
endpoint at p50=15.4ms / p99=18.5ms against a 1000-row fixture.
Preview adds the 100-row cap + telemetry wrap, neither of which
materially shifts the executor's hot-path cost. If preview drifts
past the execute budget, the executor itself regressed and both
gates should catch it.

Methodology mirrors test_saved_view_execute_latency.py with two
changes:
  1. No view is persisted — the preview endpoint takes the config
     directly in the body (no save-row lookup).
  2. Sample count = 20, not 50. Preview is debounced at 300ms
     client-side; the practical upper bound on calls/user/min is an
     order of magnitude lower than /execute. 20 samples keeps the
     gate runtime in line with the per-hop budget for CI.

Environment opt-out:
  SAVED_VIEW_PREVIEW_LATENCY_DISABLE=1 skips (underpowered CI only).
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest


_TARGET_P50_MS: float = 150.0
_TARGET_P99_MS: float = 500.0
_WARMUP_COUNT: int = 3
_SAMPLE_COUNT: int = 20
_SEED_ROW_COUNT: int = 1_000


if os.environ.get("SAVED_VIEW_PREVIEW_LATENCY_DISABLE") == "1":
    pytest.skip(
        "SAVED_VIEW_PREVIEW_LATENCY_DISABLE=1 — skipping preview latency gate",
        allow_module_level=True,
    )


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def seeded_tenant():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.customer import Customer
    from app.models.role import Role
    from app.models.sales_order import SalesOrder
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"SVPRE-{suffix}",
            slug=f"svpre-{suffix}",
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
            email=f"admin-{suffix}@svpre.co",
            first_name="Pre",
            last_name="View",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        customer = Customer(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Bulk Customer",
            is_active=True,
        )
        db.add(customer)
        db.flush()

        statuses = ["draft", "confirmed", "in_production", "delivered", "cancelled"]
        base_date = datetime.now(timezone.utc) - timedelta(days=90)
        rows = [
            SalesOrder(
                id=str(uuid.uuid4()),
                company_id=co.id,
                number=f"SO-PRE-{i:06d}",
                customer_id=customer.id,
                status=statuses[i % len(statuses)],
                order_date=base_date + timedelta(hours=i * 2),
                subtotal=Decimal(str(100 + (i % 97))),
                tax_rate=Decimal("0.08"),
                tax_amount=Decimal(
                    str(round((100 + (i % 97)) * 0.08, 2))
                ),
                total=Decimal(str(round((100 + (i % 97)) * 1.08, 2))),
            )
            for i in range(_SEED_ROW_COUNT)
        ]
        db.bulk_save_objects(rows)
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
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


# ── Test shapes ─────────────────────────────────────────────────────


def _preview_config(
    *,
    mode: str = "list",
    filters: list | None = None,
    sort: list | None = None,
    grouping: dict | None = None,
    kanban_config: dict | None = None,
    chart_config: dict | None = None,
    limit: int | None = None,
) -> dict:
    return {
        "query": {
            "entity_type": "sales_order",
            "filters": filters or [],
            "sort": sort or [],
            "grouping": grouping,
            "limit": limit,
        },
        "presentation": {
            "mode": mode,
            "table_config": None,
            "card_config": None,
            "kanban_config": kanban_config,
            "calendar_config": None,
            "chart_config": chart_config,
            "stat_config": None,
        },
        "permissions": {
            "owner_user_id": "",
            "visibility": "private",
            "shared_with_users": [],
            "shared_with_roles": [],
            "shared_with_tenants": [],
            "cross_tenant_field_visibility": {"per_tenant_fields": {}},
        },
        "extras": {},
    }


# Four shapes exercising different executor hot paths. Mixed order
# during the sample loop so no single shape dominates.
_MIXED_SHAPES = [
    _preview_config(
        filters=[{"field": "status", "operator": "eq", "value": "draft"}],
        sort=[{"field": "order_date", "direction": "desc"}],
    ),
    _preview_config(
        mode="table",
        filters=[{"field": "status", "operator": "in", "value": ["draft", "confirmed"]}],
    ),
    _preview_config(
        mode="kanban",
        grouping={"field": "status"},
        kanban_config={
            "group_by_field": "status",
            "card_title_field": "number",
            "card_meta_fields": ["total"],
        },
    ),
    _preview_config(
        mode="chart",
        grouping={"field": "status"},
        chart_config={
            "chart_type": "bar",
            "x_field": "status",
            "y_field": "total",
            "y_aggregation": "sum",
        },
    ),
]


def test_preview_latency_gate(client, headers):
    """BLOCKING: /api/v1/saved-views/preview p50 < 150ms, p99 < 500ms."""
    # Warm-up (JIT + first-call Pydantic costs excluded).
    for i in range(_WARMUP_COUNT):
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": _MIXED_SHAPES[i % len(_MIXED_SHAPES)]},
            headers=headers,
        )
        assert r.status_code == 200, r.text

    durations_ms: list[float] = []
    for i in range(_SAMPLE_COUNT):
        cfg = _MIXED_SHAPES[i % len(_MIXED_SHAPES)]
        t0 = time.perf_counter()
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": cfg},
            headers=headers,
        )
        t1 = time.perf_counter()
        assert r.status_code == 200, (
            f"preview → {r.status_code} {r.text[:120]}"
        )
        durations_ms.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations_ms):.1f}ms "
        f"max={max(durations_ms):.1f}ms)"
    )
    print(f"\n[saved-view-preview-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, (
        f"preview p50 {p50:.1f}ms > target {_TARGET_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_P99_MS, (
        f"preview p99 {p99:.1f}ms > target {_TARGET_P99_MS}ms — {diag}"
    )


def test_row_cap_respected_at_scale(client, headers):
    """With 1000 rows seeded, preview MUST cap at 100. Guard against
    a regression where the cap accidentally becomes configurable by
    the caller."""
    r = client.post(
        "/api/v1/saved-views/preview",
        # Caller explicitly asks for 1000 — server overrides to 100.
        json={"config": _preview_config(limit=1000)},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_count"] == _SEED_ROW_COUNT
    assert len(body["rows"]) == 100
    # Client derives truncated from these two fields.
    assert len(body["rows"]) < body["total_count"]
