"""BLOCKING CI gate — Saved View execute latency.

Fails CI if p99 > 500 ms or p50 > 150 ms for the
`/saved-views/{id}/execute` endpoint. Saved views are the rendering
engine for every list / kanban / calendar / table / card grid /
chart / dashboard in the platform — latency here is multiplied
across every hub and every widget. Regressions must block merges.

This is NOT a one-off load test; it runs alongside the rest of
pytest as a gate.

Methodology:
  1. Seed a tenant + 1,000 sales_order rows (a realistic upper-
     bound mid-sized tenant — bigger than a small FH, smaller than
     a multi-location licensee).
  2. Create four saved views with different presentation modes so
     the sample exercises executor dispatch + filters + sort +
     grouping + aggregation, not one hot path:
       a. list  — filter on status + sort on order_date
       b. table — full-column list with one filter
       c. kanban — groupBy status (in-memory bucket build)
       d. chart/stat — sum(total) aggregation
  3. Warm-up with 5 throwaway executes per view (not counted).
  4. Run 50 sequential mixed-shape executes and compute p50 + p99.
  5. Fail if p50 > 150 ms or p99 > 500 ms.

Sequential, not concurrent — same reason as the command-bar gate:
we measure what a single user feels per call, not server-side
parallelism.

Environment opt-outs:
  - `SAVED_VIEW_LATENCY_DISABLE=1` skips the test. Use sparingly
    (underpowered CI runners only).

⚠️ WHAT THIS GATE EXCLUDES — generation-2 GC pauses, and nothing else.
A full collection on this application's heap costs ~450 ms whatever the
garbage volume, because the cost is walking ~2.08M permanent objects. It
lands on whichever request is in flight. Every sample here is measured with
`tests/_gc_latency.Gen2Excluded`, which subtracts the collector's own
interval from the sample it landed in and SAYS SO in the printed diagnostic,
every run, including when nothing was excluded. Nothing is disabled, frozen
or tuned: the endpoint runs under exactly the runtime that ships. gen-0 and
gen-1 stay in the number, and an allocation ceiling on gen-0 keeps the
regression signal the exclusion would otherwise remove. Ruled 2026-09-15;
see docs/investigations/2026-09-15-latency-gates-exclude-gc.md.
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests._gc_latency import Gen2Excluded, assert_allocation_ceiling


# ── Config ───────────────────────────────────────────────────────────

_TARGET_P50_MS: float = 150.0
_TARGET_P99_MS: float = 500.0
_WARMUP_COUNT: int = 5
_SAMPLE_COUNT: int = 50
_SEED_ROW_COUNT: int = 1_000

#: ⚠️ ALLOCATION CEILINGS — the half of the gate that excluding gen-2
#: pauses would otherwise delete. Counted in gen-0 collections over the
#: sample loop (see tests/_gc_latency.py). Measured 2026-09-15 over 3-4
#: runs with a spread of <= 1, times 3 headroom.
_ALLOC_CEIL_EXECUTE: int = 500


# ── Opt-out ──────────────────────────────────────────────────────────

if os.environ.get("SAVED_VIEW_LATENCY_DISABLE") == "1":
    pytest.skip(
        "SAVED_VIEW_LATENCY_DISABLE=1 — skipping latency gate",
        allow_module_level=True,
    )


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _seed_large_tenant():
    """Seed a tenant with admin + 1 customer + _SEED_ROW_COUNT sales
    orders spread across a handful of statuses so grouping + filters
    hit realistic cardinalities."""
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
            name=f"SVLAT-{suffix}",
            slug=f"svlat-{suffix}",
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
            email=f"admin-{suffix}@svlat.co",
            first_name="Lat",
            last_name="Gate",
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

        # Spread orders across 5 statuses — roughly 20% each. Weekday
        # order_date spread across 90 days so the sort ORDER BY
        # touches every page of a B-tree, not a hot cache slot.
        statuses = ["draft", "confirmed", "in_production", "delivered", "cancelled"]
        base_date = datetime.now(timezone.utc) - timedelta(days=90)
        rows = []
        for i in range(_SEED_ROW_COUNT):
            rows.append(
                SalesOrder(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    number=f"SO-LAT-{i:06d}",
                    customer_id=customer.id,
                    status=statuses[i % len(statuses)],
                    order_date=base_date + timedelta(hours=i * 2),
                    subtotal=Decimal(str(100 + (i % 97))),
                    tax_rate=Decimal("0.08"),
                    tax_amount=Decimal(str(round((100 + (i % 97)) * 0.08, 2))),
                    total=Decimal(str(round((100 + (i % 97)) * 1.08, 2))),
                )
            )
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


def _create_view(client, headers, *, title: str, config: dict) -> str:
    resp = client.post(
        "/api/v1/saved-views",
        json={"title": title, "description": None, "config": config},
        headers=headers,
    )
    assert resp.status_code == 201, f"create view failed: {resp.status_code} {resp.text}"
    return resp.json()["id"]


def _config(
    *,
    filters: list | None = None,
    sort: list | None = None,
    mode: str = "list",
    grouping: dict | None = None,
    aggregations: list | None = None,
    group_by: str | None = None,
    table_config: dict | None = None,
    kanban_config: dict | None = None,
    chart_config: dict | None = None,
) -> dict:
    query: dict = {
        "entity_type": "sales_order",
        "filters": filters or [],
        "sort": sort or [],
    }
    if grouping is not None:
        query["grouping"] = grouping
    if aggregations is not None:
        query["aggregations"] = aggregations
    presentation: dict = {"mode": mode}
    if table_config is not None:
        presentation["table_config"] = table_config
    if kanban_config is not None:
        presentation["kanban_config"] = kanban_config
    if chart_config is not None:
        presentation["chart_config"] = chart_config
    return {
        "query": query,
        "presentation": presentation,
        "permissions": {
            "owner_user_id": "unused",
            "visibility": "private",
        },
        "extras": {},
    }


@pytest.fixture(scope="module")
def seeded_tenant():
    return _seed_large_tenant()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


@pytest.fixture
def view_ids(client, headers):
    """Create four views up-front — returned as a dict keyed by shape.
    Done once per test to keep the gate measuring execute-path latency,
    not create-path latency."""
    ids = {}
    ids["list"] = _create_view(
        client, headers,
        title="Latency: active orders list",
        config=_config(
            filters=[{"field": "status", "operator": "in",
                      "value": ["draft", "confirmed", "in_production"]}],
            sort=[{"field": "order_date", "direction": "desc"}],
            mode="list",
        ),
    )
    ids["table"] = _create_view(
        client, headers,
        title="Latency: all orders table",
        config=_config(
            filters=[{"field": "status", "operator": "ne",
                      "value": "cancelled"}],
            sort=[{"field": "number", "direction": "asc"}],
            mode="table",
            table_config={"columns": [
                "number", "status", "order_date", "subtotal", "total",
            ]},
        ),
    )
    ids["kanban"] = _create_view(
        client, headers,
        title="Latency: orders kanban",
        config=_config(
            filters=[],
            mode="kanban",
            grouping={"field": "status"},
            kanban_config={
                "group_by_field": "status",
                "card_title_field": "number",
                "card_meta_fields": ["total"],
            },
        ),
    )
    ids["chart"] = _create_view(
        client, headers,
        title="Latency: revenue by status chart",
        config=_config(
            filters=[],
            mode="chart",
            grouping={"field": "status"},
            aggregations=[{"function": "sum", "field": "total"}],
            chart_config={
                "chart_type": "bar",
                "x_field": "status",
                "y_field": "total",
                "y_aggregation": "sum",
            },
        ),
    )
    return ids


# ── The gate ─────────────────────────────────────────────────────────


def test_saved_view_execute_p50_p99_under_budget(client, headers, view_ids):
    """BLOCKING CI gate. Fails if p50 > 150 ms or p99 > 500 ms on the
    sequential sample across 4 view shapes over 1,000 rows.

    If this fails in CI, the saved-view executor is too slow. Profile
    before shipping — check for missing indexes, unbounded queries,
    or expensive in-Python aggregation.
    """
    shapes = list(view_ids.keys())  # deterministic order

    # Warm-up — pool + plan cache + auth cache. Not counted.
    for _ in range(_WARMUP_COUNT):
        for shape in shapes:
            client.post(
                f"/api/v1/saved-views/{view_ids[shape]}/execute",
                headers=headers,
            )

    # Sample N mixed-shape executes.
    with Gen2Excluded() as gc_s:
        for i in range(_SAMPLE_COUNT):
            shape = shapes[i % len(shapes)]
            vid = view_ids[shape]
            with gc_s.sample():
                resp = client.post(
                    f"/api/v1/saved-views/{vid}/execute",
                    headers=headers,
                )
            assert resp.status_code == 200, (
                f"execute shape={shape} vid={vid} → {resp.status_code} {resp.text}"
            )

    durations_ms = gc_s.durations_ms

    p50 = statistics.median(durations_ms)
    # statistics.quantiles(n=100) returns 99 cut points; last is p99.
    p99 = statistics.quantiles(durations_ms, n=100)[-1]

    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, rows={_SEED_ROW_COUNT}, "
        f"min={min(durations_ms):.1f}ms max={max(durations_ms):.1f}ms) [{gc_s.exclusion_note()}]"
    )
    # Emit on green runs for visibility.
    print(f"\n[saved-view-execute-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, (
        f"saved-view execute p50 {p50:.1f}ms > target {_TARGET_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_P99_MS, (
        f"saved-view execute p99 {p99:.1f}ms > target {_TARGET_P99_MS}ms — {diag}"
    )
    assert_allocation_ceiling(gc_s, _ALLOC_CEIL_EXECUTE, "saved-view-execute")
