"""BLOCKING CI gate — Cash Receipts Matching Triage latency.

Workflow Arc Phase 8b — inherits the Phase 5 triage latency budget:

  cash_receipts_triage next_item     p50 < 100 ms, p99 < 300 ms
  cash_receipts_triage apply_action  p50 < 200 ms, p99 < 500 ms

The apply_action budget is wider than task_triage's because
`cash_receipts.approve` writes a `CustomerPaymentApplication` row +
mutates `Invoice.amount_paid` + resolves an anomaly in a single
transaction — three writes per call.

Methodology mirrors Phase 5's `test_triage_latency.py`:
  1. Seed one tenant + admin user + one AgentJob + N pending
     anomalies with matching payment/invoice pairs.
  2. Warm-up 3 calls for each operation.
  3. Run 30 samples sequentially per op, measure each.
  4. Compute p50 / p99 and assert budgets.

Opt-out: `TRIAGE_LATENCY_DISABLE=1` (matches Phase 5 convention).
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest


_TARGET_NEXT_P50_MS: float = 100.0
_TARGET_NEXT_P99_MS: float = 300.0
_TARGET_ACTION_P50_MS: float = 200.0
_TARGET_ACTION_P99_MS: float = 500.0
_WARMUP_COUNT: int = 3
_SAMPLE_COUNT: int = 30
_SEED_ANOMALY_COUNT: int = 40  # enough for warmup + samples + buffer


if os.environ.get("TRIAGE_LATENCY_DISABLE") == "1":
    pytest.skip(
        "TRIAGE_LATENCY_DISABLE=1 — skipping Phase 8b cash receipts "
        "triage latency gate",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _seed_tenant_with_anomalies():
    from datetime import date

    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.company import Company
    from app.models.customer import Customer
    from app.models.customer_payment import CustomerPayment
    from app.models.invoice import Invoice
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"CRLAT-{suffix}",
            slug=f"crlat-{suffix}",
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
            email=f"lat-{suffix}@cr.co",
            first_name="CRLat",
            last_name="Gate",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=co.id,
            job_type="cash_receipts_matching",
            status="awaiting_approval",
            period_start=date.today().replace(day=1),
            period_end=date.today(),
            dry_run=False,
            triggered_by=user.id,
            trigger_type="schedule",
            run_log=[],
            anomaly_count=0,
        )
        db.add(job)
        db.flush()

        # Each anomaly points at a payment — seed a
        # payment + invoice + customer triple per anomaly so the
        # approve action has real rows to write against.
        anomaly_ids: list[str] = []
        payment_ids: list[str] = []
        invoice_ids: list[str] = []
        now = datetime.now(timezone.utc)
        for i in range(_SEED_ANOMALY_COUNT):
            cust = Customer(
                id=str(uuid.uuid4()),
                company_id=co.id,
                name=f"Cust-{i:03d}",
                is_active=True,
            )
            db.add(cust)
            db.flush()
            inv = Invoice(
                id=str(uuid.uuid4()),
                company_id=co.id,
                number=f"INV-{suffix}-{i:03d}",
                customer_id=cust.id,
                status="sent",
                invoice_date=now,
                due_date=now,
                subtotal=Decimal("100.00"),
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                total=Decimal("100.00"),
                amount_paid=Decimal("0"),
            )
            db.add(inv)
            db.flush()
            pay = CustomerPayment(
                id=str(uuid.uuid4()),
                company_id=co.id,
                customer_id=cust.id,
                payment_date=now,
                total_amount=Decimal("100.00"),
                payment_method="check",
                reference_number=f"CHK-{i:03d}",
            )
            db.add(pay)
            db.flush()
            a = AgentAnomaly(
                id=str(uuid.uuid4()),
                agent_job_id=job.id,
                severity="INFO",
                anomaly_type="payment_possible_match",
                entity_type="payment",
                entity_id=pay.id,
                description=f"Possible match for payment #{i:03d}",
                amount=Decimal("100.00"),
                resolved=False,
            )
            db.add(a)
            anomaly_ids.append(a.id)
            payment_ids.append(pay.id)
            invoice_ids.append(inv.id)
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
            "anomaly_ids": anomaly_ids,
            "payment_ids": payment_ids,
            "invoice_ids": invoice_ids,
        }
    finally:
        db.close()


@pytest.fixture(scope="module")
def seeded_tenant():
    return _seed_tenant_with_anomalies()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


# ── Gate ─────────────────────────────────────────────────────────────


def test_cash_receipts_triage_next_item_latency_gate(client, headers):
    """BLOCKING: cash_receipts next_item p50 < 100 ms, p99 < 300 ms."""
    r = client.post(
        "/api/v1/triage/queues/cash_receipts_matching_triage/sessions",
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["session_id"]

    for _ in range(_WARMUP_COUNT):
        client.post(f"/api/v1/triage/sessions/{session_id}/next", headers=headers)

    durations_ms: list[float] = []
    for _ in range(_SAMPLE_COUNT):
        t0 = time.perf_counter()
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/next", headers=headers
        )
        t1 = time.perf_counter()
        # 200 with an item, 204 when exhausted — both valid.
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
    print(f"\n[cash-receipts-triage-next-item-latency] {diag}")

    assert p50 <= _TARGET_NEXT_P50_MS, (
        f"cash_receipts next_item p50 {p50:.1f}ms > target "
        f"{_TARGET_NEXT_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_NEXT_P99_MS, (
        f"cash_receipts next_item p99 {p99:.1f}ms > target "
        f"{_TARGET_NEXT_P99_MS}ms — {diag}"
    )


def test_cash_receipts_triage_apply_action_latency_gate(
    client, headers, seeded_tenant
):
    """BLOCKING: cash_receipts apply_action p50 < 200 ms, p99 < 500 ms.

    Each apply_action writes a CustomerPaymentApplication row + mutates
    Invoice + resolves the anomaly — three writes per call — making it
    representative of the Phase 8b production approval hot path.
    """
    r = client.post(
        "/api/v1/triage/queues/cash_receipts_matching_triage/sessions",
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["session_id"]

    anomaly_ids = seeded_tenant["anomaly_ids"]
    payment_ids = seeded_tenant["payment_ids"]
    invoice_ids = seeded_tenant["invoice_ids"]

    # Warm up — also consumes some anomalies.
    for i in range(_WARMUP_COUNT):
        aid = anomaly_ids[i]
        client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{aid}/action",
            json={
                "action_id": "approve",
                "payload": {
                    "payment_id": payment_ids[i],
                    "invoice_id": invoice_ids[i],
                },
            },
            headers=headers,
        )

    durations_ms: list[float] = []
    for i in range(_SAMPLE_COUNT):
        idx = _WARMUP_COUNT + i
        aid = anomaly_ids[idx]
        t0 = time.perf_counter()
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{aid}/action",
            json={
                "action_id": "approve",
                "payload": {
                    "payment_id": payment_ids[idx],
                    "invoice_id": invoice_ids[idx],
                },
            },
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
    print(f"\n[cash-receipts-triage-apply-action-latency] {diag}")

    assert p50 <= _TARGET_ACTION_P50_MS, (
        f"cash_receipts apply_action p50 {p50:.1f}ms > target "
        f"{_TARGET_ACTION_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_ACTION_P99_MS, (
        f"cash_receipts apply_action p99 {p99:.1f}ms > target "
        f"{_TARGET_ACTION_P99_MS}ms — {diag}"
    )
