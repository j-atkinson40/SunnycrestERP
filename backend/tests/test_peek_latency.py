"""BLOCKING CI gate — Peek endpoint latency (follow-up 4 / arc finale).

Targets: p50 < 100 ms, p99 < 300 ms.

Peek backs hover + click previews across 4 surfaces. Hover triggers
fire on mouse-over so the call frequency per user is high. The
client side ships a session cache (5-min TTL) that absorbs most
repeats, but cold-cache hits land on this endpoint and need to feel
instantaneous.

Methodology mirrors test_saved_view_preview_latency.py:
  - Single seeded tenant with 1 of each entity type
  - 3 warm-ups (JIT + Pydantic first-call costs excluded)
  - 24 sequential samples, mixed across 6 entity types
  - Compute p50 + p99 across all samples
  - Fail if budget exceeded

Mixed-shape sampling matters: each builder runs different ORM
queries (single-row primary, customer JOIN, line-count subquery,
etc.). The aggregate p99 reflects the worst-of-six pattern, which
is the right thing to gate on for a cross-cutting endpoint.

Environment opt-out:
  PEEK_LATENCY_DISABLE=1 skips (underpowered CI runners only).
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest


_TARGET_P50_MS: float = 100.0
_TARGET_P99_MS: float = 300.0
_WARMUP_COUNT: int = 3
_SAMPLE_COUNT: int = 24


if os.environ.get("PEEK_LATENCY_DISABLE") == "1":
    pytest.skip(
        "PEEK_LATENCY_DISABLE=1 — skipping peek latency gate",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def seeded_tenant():
    """One tenant + one row of every peek-supported entity type +
    a saved view + a task. Module-scoped: setup once, share across
    all samples."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.company_entity import CompanyEntity
    from app.models.contact import Contact
    from app.models.customer import Customer
    from app.models.funeral_case import (
        CaseDeceased,
        CaseService,
        FuneralCase,
    )
    from app.models.invoice import Invoice
    from app.models.role import Role
    from app.models.sales_order import SalesOrder, SalesOrderLine
    from app.models.user import User
    from app.services.saved_views import create_saved_view
    from app.services.saved_views.types import (
        Permissions,
        Presentation,
        Query,
        SavedViewConfig,
    )
    from app.services.task_service import create_task

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"PEEKLAT-{suffix}",
            slug=f"peeklat-{suffix}",
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
            email=f"pl-{suffix}@peeklat.co",
            first_name="Peek",
            last_name="Latency",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        # FH case
        case = FuneralCase(
            id=str(uuid.uuid4()),
            company_id=co.id,
            case_number="C-LAT-001",
            current_step="arrangement_conference",
            status="active",
        )
        db.add(case)
        db.flush()
        db.add(
            CaseDeceased(
                id=str(uuid.uuid4()),
                case_id=case.id,
                company_id=co.id,
                first_name="Pat",
                last_name="Sample",
                date_of_death=date(2026, 3, 1),
            )
        )
        db.add(
            CaseService(
                id=str(uuid.uuid4()),
                case_id=case.id,
                company_id=co.id,
                service_date=date(2026, 3, 5),
            )
        )

        # Customer + Invoice + SalesOrder
        cust = Customer(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Lat Customer",
            is_active=True,
        )
        db.add(cust)
        db.flush()
        inv = Invoice(
            id=str(uuid.uuid4()),
            company_id=co.id,
            number="INV-LAT-001",
            customer_id=cust.id,
            status="sent",
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
            subtotal=Decimal("100"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
            amount_paid=Decimal("0"),
        )
        db.add(inv)
        so = SalesOrder(
            id=str(uuid.uuid4()),
            company_id=co.id,
            number="SO-LAT-001",
            customer_id=cust.id,
            status="confirmed",
            order_date=datetime.now(timezone.utc),
            subtotal=Decimal("200"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("200"),
        )
        db.add(so)
        db.flush()
        for i in range(2):
            db.add(
                SalesOrderLine(
                    id=str(uuid.uuid4()),
                    sales_order_id=so.id,
                    product_id=None,
                    description=f"Line {i}",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100"),
                    line_total=Decimal("100"),
                )
            )

        # Task
        task = create_task(
            db,
            company_id=co.id,
            title="Latency-gate task",
            created_by_user_id=user.id,
            assignee_user_id=user.id,
            priority="normal",
            due_date=date.today() + timedelta(days=3),
        )

        # Contact + CompanyEntity for the contact
        ce = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Lat Vendor",
            is_active=True,
        )
        db.add(ce)
        db.flush()
        contact = Contact(
            id=str(uuid.uuid4()),
            company_id=co.id,
            master_company_id=ce.id,
            name="Lat Contact",
            phone="+15555550000",
            is_active=True,
        )
        db.add(contact)

        # Saved view
        view = create_saved_view(
            db,
            user=user,
            title="Latency view",
            description="for the latency gate",
            config=SavedViewConfig(
                query=Query(entity_type="sales_order", filters=[], sort=[]),
                presentation=Presentation(mode="list"),
                permissions=Permissions(
                    owner_user_id=user.id, visibility="private"
                ),
            ),
        )

        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "token": token,
            "slug": co.slug,
            "ids": {
                "fh_case": case.id,
                "invoice": inv.id,
                "sales_order": so.id,
                "task": task.id,
                "contact": contact.id,
                "saved_view": view.id,
            },
        }
    finally:
        db.close()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


def test_peek_latency_gate(client, headers, seeded_tenant):
    """BLOCKING: /peek p50 < 100 ms, p99 < 300 ms across 6 entity
    types."""
    ids = seeded_tenant["ids"]
    shapes = [
        ("fh_case", ids["fh_case"]),
        ("invoice", ids["invoice"]),
        ("sales_order", ids["sales_order"]),
        ("task", ids["task"]),
        ("contact", ids["contact"]),
        ("saved_view", ids["saved_view"]),
    ]

    # Warm-up across all 6 shapes (bypassed JIT / first-call costs).
    for i in range(_WARMUP_COUNT):
        et, eid = shapes[i % len(shapes)]
        r = client.get(f"/api/v1/peek/{et}/{eid}", headers=headers)
        assert r.status_code == 200, r.text

    durations_ms: list[float] = []
    for i in range(_SAMPLE_COUNT):
        et, eid = shapes[i % len(shapes)]
        t0 = time.perf_counter()
        r = client.get(f"/api/v1/peek/{et}/{eid}", headers=headers)
        t1 = time.perf_counter()
        assert r.status_code == 200, (
            f"peek {et}/{eid} → {r.status_code} {r.text[:120]}"
        )
        durations_ms.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations_ms):.1f}ms "
        f"max={max(durations_ms):.1f}ms)"
    )
    print(f"\n[peek-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, (
        f"peek p50 {p50:.1f}ms > target {_TARGET_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_P99_MS, (
        f"peek p99 {p99:.1f}ms > target {_TARGET_P99_MS}ms — {diag}"
    )
