"""BLOCKING CI gate — Command Bar latency.

Fails CI if p99 > 300 ms or p50 > 100 ms for the /command-bar/query
endpoint. The command bar is the spine of the Power Operator UX;
latency regressions here are user-visible and must block merges.

This is NOT a one-off load test — it runs in the regular pytest
suite as a gate.

Methodology:
  1. Seed a representative tenant with ~20 rows across the 6 entity
     types (enough to exercise the UNION ALL but not so much that
     it dwarfs what production tenants have).
  2. Warm-up the connection pool + plan cache with a few throwaway
     queries (not counted in percentile calc).
  3. Run N=50 sequential queries of mixed shapes (nav alias, record
     number, fuzzy name, create verb, empty).
  4. Compute p50 + p99 from the sample.
  5. Fail if p50 > 100 ms or p99 > 300 ms.

We use sequential queries, not concurrent. Concurrent would measure
server-side parallelism; sequential measures worst-case single-call
latency — the number the user actually feels.

Environment opt-outs:
  - `COMMAND_BAR_LATENCY_DISABLE=1` skips the test (for environments
    that can't hit the latency target, e.g. underpowered CI runners).
    Use sparingly.
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest


# ── Config ───────────────────────────────────────────────────────────

_TARGET_P50_MS: float = 100.0
_TARGET_P99_MS: float = 300.0
_WARMUP_COUNT: int = 5
_SAMPLE_COUNT: int = 50

# Mixed-shape query set — every shape the user types.
_QUERY_SHAPES: list[str] = [
    "Dashboard",              # nav exact
    "AR",                     # nav alias
    "new sales order",        # create intent
    "SMITH",                  # search fuzzy
    "INV-2026-0001",          # record pattern
    "bronze vault",           # search + resolver
    "order",                  # multi-match
    "go to financials",       # navigate verb prefix
    "quote",                  # short token
    "",                       # empty intent (fast path)
]


# ── Opt-out ──────────────────────────────────────────────────────────

if os.environ.get("COMMAND_BAR_LATENCY_DISABLE") == "1":
    pytest.skip(
        "COMMAND_BAR_LATENCY_DISABLE=1 — skipping latency gate",
        allow_module_level=True,
    )


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _seed_tenant_and_user():
    """Seed a tenant + admin user + ~20 entity rows representative
    of a small production tenant.

    Phase 8e.1 update — also seeds:
      - 1 user-created space (sp_lat_primary) so active_space_id
        lookup works in retrieval.
      - 10 user_space_affinity rows (~5 per target_type) so the
        affinity boost pass gets exercised in the latency sample.
    """
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.canonical_document import Document
    from app.models.company import Company
    from app.models.company_entity import CompanyEntity
    from app.models.contact import Contact
    from app.models.customer import Customer
    from app.models.fh_case import FHCase
    from app.models.invoice import Invoice
    from app.models.product import Product
    from app.models.role import Role
    from app.models.sales_order import SalesOrder
    from app.models.user import User
    from app.models.user_space_affinity import UserSpaceAffinity

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"LAT-{suffix}",
            slug=f"lat-{suffix}",
            is_active=True,
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
            email=f"admin-{suffix}@lat.co",
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
            name="Latency Test Customer",
            is_active=True,
        )
        entity = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Latency Test Entity",
            is_active=True,
        )
        db.add_all([customer, entity])
        db.flush()

        # Seed ~4 of each entity type.
        for i in range(4):
            db.add(
                FHCase(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    case_number=f"CASE-LAT-{i:04d}",
                    status="active",
                    deceased_first_name=f"First{i}",
                    deceased_last_name=f"Last{i}Smithson",
                    deceased_date_of_death=date.today(),
                )
            )
            db.add(
                SalesOrder(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    number=f"SO-LAT-{i:04d}",
                    customer_id=customer.id,
                    status="draft",
                    order_date=datetime.now(timezone.utc),
                    subtotal=Decimal("0"),
                    tax_rate=Decimal("0"),
                    tax_amount=Decimal("0"),
                    total=Decimal("0"),
                )
            )
            db.add(
                Invoice(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    number=f"INV-LAT-{i:04d}",
                    customer_id=customer.id,
                    status="draft",
                    invoice_date=date.today(),
                    due_date=date.today() + timedelta(days=30),
                    subtotal=Decimal("0"),
                    tax_rate=Decimal("0"),
                    tax_amount=Decimal("0"),
                    total=Decimal("0"),
                    amount_paid=Decimal("0"),
                )
            )
            db.add(
                Contact(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    master_company_id=entity.id,
                    name=f"Contact Person {i}",
                    is_active=True,
                )
            )
            db.add(
                Product(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    name=f"Product Latency {i}",
                    sku=f"PROD-LAT-{i:04d}",
                    is_active=True,
                )
            )
            db.add(
                Document(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    title=f"Latency Test Document {i}",
                    document_type="statement",
                    status="final",
                    storage_key=f"tenants/{co.id}/documents/lat-{i}/v1.pdf",
                )
            )

        # Phase 8e.1 — seed a user space + affinity rows so the
        # latency gate exercises the boost path. We attach a single
        # space to user.preferences directly (bypasses the normal
        # create_space flow to avoid its own seed side effects).
        space_id = "sp_lattest00001"
        user.preferences = {
            "spaces": [
                {
                    "space_id": space_id,
                    "name": "Latency Test Space",
                    "icon": "home",
                    "accent": "neutral",
                    "display_order": 0,
                    "is_default": True,
                    "density": "comfortable",
                    "is_system": False,
                    "default_home_route": "/dashboard",
                    "pins": [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "active_space_id": space_id,
            "spaces_seeded_for_roles": ["admin"],
        }
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(user, "preferences")

        # Seed ~10 affinity rows across the 4 target_types so the
        # prefetch + boost loop runs a realistic dict size.
        now = datetime.now(timezone.utc)
        affinity_seeds = [
            ("nav_item", "/dashboard", 5),
            ("nav_item", "/financials", 3),
            ("nav_item", "/scheduling", 2),
            ("saved_view", str(uuid.uuid4()), 7),
            ("saved_view", str(uuid.uuid4()), 2),
            ("entity_record", str(uuid.uuid4()), 4),
            ("entity_record", str(uuid.uuid4()), 1),
            ("triage_queue", "task_triage", 6),
            ("triage_queue", "safety_program_triage", 2),
            ("nav_item", "/production-hub", 8),
        ]
        for target_type, target_id, visit_count in affinity_seeds:
            db.add(
                UserSpaceAffinity(
                    user_id=user.id,
                    company_id=co.id,
                    space_id=space_id,
                    target_type=target_type,
                    target_id=target_id,
                    visit_count=visit_count,
                    last_visited_at=now,
                )
            )

        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
            "space_id": space_id,
        }
    finally:
        db.close()


@pytest.fixture(scope="module")
def seeded_tenant():
    return _seed_tenant_and_user()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


# ── The gate ─────────────────────────────────────────────────────────


def test_command_bar_p50_p99_under_budget(client, headers, seeded_tenant):
    """BLOCKING CI gate. Fails the test run if p50 > 100 ms or
    p99 > 300 ms on the sequential sample.

    Phase 8e.1 — the seeded tenant carries 10 user_space_affinity
    rows and an active_space_id; queries pass `active_space_id` in
    the context so the affinity prefetch + starter-template boost
    passes are both exercised. If this fails in CI, the command bar
    is too slow. Profile before shipping.
    """
    active_space_id = seeded_tenant["space_id"]

    def _post(query: str):
        return client.post(
            "/api/v1/command-bar/query",
            json={
                "query": query,
                "context": {"active_space_id": active_space_id},
            },
            headers=headers,
        )

    # Warm-up — not counted.
    for _ in range(_WARMUP_COUNT):
        _post("Dashboard")

    # Sample N calls with mixed shapes.
    durations_ms: list[float] = []
    for i in range(_SAMPLE_COUNT):
        q = _QUERY_SHAPES[i % len(_QUERY_SHAPES)]
        t0 = time.perf_counter()
        resp = _post(q)
        t1 = time.perf_counter()
        # Record only successful queries — 5xx responses shouldn't
        # distort percentile math, but should also fail the test
        # separately.
        assert resp.status_code == 200, f"query {q!r} → {resp.status_code}"
        durations_ms.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations_ms)
    # statistics.quantiles(n=100) returns 99 cut points; last is p99.
    p99 = statistics.quantiles(durations_ms, n=100)[-1]

    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, sample min={min(durations_ms):.1f}ms "
        f"max={max(durations_ms):.1f}ms, affinity=ENABLED)"
    )
    # Emit stats into pytest output for visibility on green runs.
    print(f"\n[command-bar-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, (
        f"command-bar p50 {p50:.1f}ms > target {_TARGET_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_P99_MS, (
        f"command-bar p99 {p99:.1f}ms > target {_TARGET_P99_MS}ms — {diag}"
    )
