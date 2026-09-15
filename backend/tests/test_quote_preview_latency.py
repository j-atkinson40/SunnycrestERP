"""BLOCKING latency gate — S-2 quote-preview endpoint (§4.3).

Fired on the extraction-settle trigger while composing a quote. Heavier
than the peek/portal hot paths (product resolution + order-resolver
pricing + tax resolution + a real Jinja render of quote.standard per
fire), so its own budget: p50 < 200 ms, p99 < 500 ms.

Methodology mirrors tests/test_command_bar_portal_latency.py: seed a
tenant + products, warm up, then time N sequential samples against the
real endpoint. Company rows are torn down (litter tripwire).

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
import uuid
from decimal import Decimal

import pytest

from tests._gc_latency import Gen2Excluded, assert_allocation_ceiling

_TARGET_P50_MS = 200.0
_TARGET_P99_MS = 500.0
_WARMUP_COUNT = 3
_SAMPLE_COUNT = 24

#: ⚠️ ALLOCATION CEILINGS — the half of the gate that excluding gen-2
#: pauses would otherwise delete. Counted in gen-0 collections over the
#: sample loop (see tests/_gc_latency.py). Measured 2026-09-15 over 3-4
#: runs with a spread of <= 1, times 3 headroom.
_ALLOC_CEIL_QUOTE: int = 15

if os.environ.get("QUOTE_PREVIEW_LATENCY_DISABLE") == "1":
    pytest.skip(
        "quote-preview latency gate disabled via env",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def seeded():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.product import Product
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"QPL {suffix}",
        slug=f"qpl-{suffix}",
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
        email=f"a-{suffix}@qpl.co",
        first_name="Q",
        last_name="L",
        hashed_password="x",
        is_active=True,
        is_super_admin=True,
        role_id=role.id,
    )
    db.add(user)
    db.add_all(
        [
            Product(
                id=str(uuid.uuid4()),
                company_id=co.id,
                name="Monticello",
                sku=f"MON-{suffix}",
                price=Decimal("1250.00"),
                is_active=True,
                product_line="monticello",
            ),
            Product(
                id=str(uuid.uuid4()),
                company_id=co.id,
                name="Continental",
                sku=f"CON-{suffix}",
                price=Decimal("1607.00"),
                is_active=True,
                product_line="continental",
            ),
        ]
    )
    db.commit()

    token = create_access_token({"sub": user.id, "company_id": co.id})
    out = {
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Company-Slug": co.slug,
        },
        # Realistic in-flight shapes, INCLUDING the miss path: a
        # qualifier-suffixed ref ("Monticello Standard") that misses the
        # substring fast path and exercises the pg_trgm fuzzy fallback —
        # so the gate proves the fallback doesn't breach the budget.
        "payloads": [
            {
                "customer_name": "Hopkins FH",
                "lines": [{"product_ref": "Monticello", "quantity": 3}],
            },
            {
                "customer_name": "Hopkins FH",
                "lines": [{"product_ref": "Monticello Standard", "quantity": 3}],
            },
            {
                "customer_name": "Murphy FH",
                "lines": [
                    {"product_ref": "Continental", "quantity": 2},
                    {"product_ref": "Monticello", "quantity": 1},
                ],
            },
        ],
    }
    yield out

    db2 = SessionLocal()
    try:
        db2.query(Product).filter(Product.company_id == co.id).delete(
            synchronize_session=False
        )
        db2.query(User).filter(User.company_id == co.id).delete(
            synchronize_session=False
        )
        db2.query(Role).filter(Role.company_id == co.id).delete(
            synchronize_session=False
        )
        db2.query(Company).filter(Company.id == co.id).delete(
            synchronize_session=False
        )
        db2.commit()
    finally:
        db2.close()
        db.close()


def test_quote_preview_latency_gate(client, seeded):
    """BLOCKING: /command-bar/quote-preview p50 < 200 ms, p99 < 500 ms."""
    payloads = seeded["payloads"]
    headers = seeded["headers"]
    url = "/api/v1/command-bar/quote-preview"

    for i in range(_WARMUP_COUNT):
        r = client.post(url, json=payloads[i % len(payloads)], headers=headers)
        assert r.status_code == 200, r.text

    with Gen2Excluded() as gc_s:
        for i in range(_SAMPLE_COUNT):
            with gc_s.sample():
                r = client.post(url, json=payloads[i % len(payloads)], headers=headers)
            assert r.status_code == 200, r.text

    durations_ms = gc_s.durations_ms

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms (n={_SAMPLE_COUNT}, "
        f"min={min(durations_ms):.1f}ms max={max(durations_ms):.1f}ms) [{gc_s.exclusion_note()}]"
    )
    print(f"\n[quote-preview-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, f"quote-preview p50 {p50:.1f}ms — {diag}"
    assert p99 <= _TARGET_P99_MS, f"quote-preview p99 {p99:.1f}ms — {diag}"
    assert_allocation_ceiling(gc_s, _ALLOC_CEIL_QUOTE, "quote-preview")
