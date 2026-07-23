"""BLOCKING CI gate — Entity-portal hydration latency (S-1, §4.2).

Targets: p50 < 150 ms, p99 < 400 ms.

The portal endpoint fires on result HIGHLIGHT (150 ms debounce on
the client), so it sits directly in the type→arrow→read loop. It is
deliberately a SEPARATE endpoint from /command-bar/query — that
endpoint's own BLOCKING gate (p50<100/p99<300) is untouched by S-1
and must stay green independently.

Methodology mirrors test_peek_latency.py:
  - Single seeded tenant with the full flagship-card constellation
    (company entity + AR customer + contacts + orders + invoices)
    plus one row of each other portal type
  - 3 warm-ups, 24 sequential samples mixed across the 6 portal
    types (company_entity weighted 2x — it is the flagship and the
    heaviest builder)
  - p50/p99 across samples; fail if budget exceeded

Environment opt-out:
  PORTAL_LATENCY_DISABLE=1 skips (underpowered CI runners only).
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
_TARGET_P99_MS: float = 400.0
_WARMUP_COUNT: int = 3
_SAMPLE_COUNT: int = 24


if os.environ.get("PORTAL_LATENCY_DISABLE") == "1":
    pytest.skip(
        "PORTAL_LATENCY_DISABLE=1 — skipping portal latency gate",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def seeded():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.company_entity import CompanyEntity
    from app.models.contact import Contact
    from app.models.customer import Customer
    from app.models.funeral_case import CaseDeceased, FuneralCase
    from app.models.invoice import Invoice
    from app.models.product import Product
    from app.models.role import Role
    from app.models.sales_order import SalesOrder
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()), name=f"PORTLAT-{suffix}",
            slug=f"portlat-{suffix}", is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()), company_id=co.id, name="Admin",
            slug="admin", is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"pl-{suffix}@portlat.co", first_name="P",
            last_name="Lat", hashed_password="x", is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        ce = CompanyEntity(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Latency Funeral Home", phone="+15555550000",
            is_funeral_home=True, is_customer=True, is_active=True,
        )
        db.add(ce)
        db.flush()
        cust = Customer(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Latency Funeral Home", master_company_id=ce.id,
            is_active=True, current_balance=Decimal("100"),
        )
        db.add(cust)
        db.flush()
        contact = Contact(
            id=str(uuid.uuid4()), company_id=co.id,
            master_company_id=ce.id, name="Lat Person",
            phone="+15555550001", is_active=True,
        )
        db.add(contact)
        so = SalesOrder(
            id=str(uuid.uuid4()), company_id=co.id, number="SO-PL-1",
            customer_id=cust.id, status="confirmed",
            order_date=datetime.now(timezone.utc),
            subtotal=Decimal("100"), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal("100"),
        )
        db.add(so)
        db.flush()
        inv = Invoice(
            id=str(uuid.uuid4()), company_id=co.id, number="INV-PL-1",
            customer_id=cust.id, status="sent",
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
            subtotal=Decimal("100"), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal("100"),
            amount_paid=Decimal("0"),
        )
        db.add(inv)
        case = FuneralCase(
            id=str(uuid.uuid4()), company_id=co.id,
            case_number="C-PL-1", current_step="arrangement_conference",
            status="active",
        )
        db.add(case)
        db.flush()
        db.add(
            CaseDeceased(
                id=str(uuid.uuid4()), case_id=case.id, company_id=co.id,
                first_name="Pat", last_name="Latency",
            )
        )
        prod = Product(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Latency Vault", sku="LAT-1", price=Decimal("900"),
            is_active=True,
        )
        db.add(prod)
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        out = {
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-Company-Slug": co.slug,
            },
            "shapes": [
                ("company_entity", ce.id),   # flagship — weighted 2x
                ("company_entity", ce.id),
                ("contact", contact.id),
                ("sales_order", so.id),
                ("invoice", inv.id),
                ("fh_case", case.id),
                ("product", prod.id),
            ],
            "_company_id": co.id,
        }
    finally:
        db.close()

    yield out

    # Teardown — no company litter (per-table commits; see
    # tests/test_so_class_killers.py world fixture).
    from sqlalchemy import text as sql_text

    from app.database import SessionLocal as _SL

    db = _SL()
    try:
        cid = out["_company_id"]
        for t in (
            "case_deceased", "funeral_cases", "invoices", "sales_orders",
            "contacts", "customers", "company_entities", "products",
            "users", "roles", "companies",
        ):
            try:
                col = "id" if t == "companies" else "company_id"
                db.execute(
                    sql_text(f"DELETE FROM {t} WHERE {col} = :c"),
                    {"c": cid},
                )
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()


def test_portal_latency_gate(client, seeded):
    """BLOCKING: /command-bar/portal p50 < 150 ms, p99 < 400 ms."""
    shapes = seeded["shapes"]
    headers = seeded["headers"]

    for i in range(_WARMUP_COUNT):
        et, eid = shapes[i % len(shapes)]
        r = client.get(
            f"/api/v1/command-bar/portal/{et}/{eid}", headers=headers
        )
        assert r.status_code == 200, r.text

    durations_ms: list[float] = []
    for i in range(_SAMPLE_COUNT):
        et, eid = shapes[i % len(shapes)]
        t0 = time.perf_counter()
        r = client.get(
            f"/api/v1/command-bar/portal/{et}/{eid}", headers=headers
        )
        t1 = time.perf_counter()
        assert r.status_code == 200, (
            f"portal {et}/{eid} → {r.status_code} {r.text[:120]}"
        )
        durations_ms.append((t1 - t0) * 1000.0)

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms (n={_SAMPLE_COUNT}, "
        f"min={min(durations_ms):.1f}ms max={max(durations_ms):.1f}ms)"
    )
    print(f"\n[portal-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, (
        f"portal p50 {p50:.1f}ms > {_TARGET_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_P99_MS, (
        f"portal p99 {p99:.1f}ms > {_TARGET_P99_MS}ms — {diag}"
    )
