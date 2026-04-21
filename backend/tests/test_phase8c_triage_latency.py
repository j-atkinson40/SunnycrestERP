"""BLOCKING CI gates — Phase 8c triage latency for all three
migrations.

Six gates (two per migration):
  month_end_close_triage:
    next_item     p50 < 100 ms, p99 < 300 ms
    apply_action  p50 < 200 ms, p99 < 500 ms (apply = approve_close
                  which triggers statement_run + period_lock writes —
                  the widest action latency budget in Phase 8c)
  ar_collections_triage:
    next_item     p50 < 100 ms, p99 < 300 ms
    apply_action  p50 < 200 ms, p99 < 500 ms (apply = send_customer_email
                  which routes through delivery_service →
                  email_channel in test-mode = in-memory)
  expense_categorization_triage:
    next_item     p50 < 100 ms, p99 < 300 ms
    apply_action  p50 < 200 ms, p99 < 500 ms (apply = approve_line
                  which writes VendorBillLine.expense_category +
                  resolves anomaly)

Methodology mirrors Phase 5/8b latency patterns:
  - Seed one tenant + admin user + 40 items per queue.
  - 3 warmups + 30 samples sequential per operation.
  - p50 = statistics.median, p99 = statistics.quantiles(n=100)[-1].

Opt-out: TRIAGE_LATENCY_DISABLE=1.
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

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
        "TRIAGE_LATENCY_DISABLE=1 — skipping Phase 8c latency gates",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


# ── Fixtures per migration ──────────────────────────────────────────


def _seed_tenant_with_mec_jobs() -> dict:
    """Seed a tenant + admin + N pending month_end_close AgentJob rows
    across distinct periods so each approve_action consumes a
    different period (avoids period_lock uniqueness conflicts)."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.agent import AgentJob
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"MECLAT-{suffix}",
            slug=f"meclat-{suffix}",
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
            email=f"lat-{suffix}@mec.co",
            first_name="MEC",
            last_name="Lat",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        job_ids: list[str] = []
        # N distinct prior-month periods (current-1, current-2, ...).
        today = date.today()
        for i in range(_SEED_ITEM_COUNT):
            # Roll back i months.
            period_end = today.replace(day=1) - timedelta(days=1)
            for _ in range(i):
                period_end = period_end.replace(day=1) - timedelta(days=1)
            period_start = period_end.replace(day=1)
            j = AgentJob(
                id=str(uuid.uuid4()),
                tenant_id=co.id,
                job_type="month_end_close",
                status="awaiting_approval",
                period_start=period_start,
                period_end=period_end,
                dry_run=False,
                triggered_by=user.id,
                trigger_type="manual",
                run_log=[],
                anomaly_count=0,
                report_payload={
                    "executive_summary": {},
                    "steps": {},
                    "anomalies": [],
                },
            )
            db.add(j)
            job_ids.append(j.id)
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
            "job_ids": job_ids,
        }
    finally:
        db.close()


def _seed_tenant_with_arc_anomalies() -> dict:
    """Seed tenant + N customers each with an AR collections anomaly
    + draft email ready to send."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.company import Company
    from app.models.customer import Customer
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"ARCLAT-{suffix}",
            slug=f"arclat-{suffix}",
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
            email=f"lat-{suffix}@arc.co",
            first_name="ARC",
            last_name="Lat",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        today = date.today()
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=co.id,
            job_type="ar_collections",
            status="awaiting_approval",
            period_start=today.replace(day=1),
            period_end=today,
            dry_run=False,
            triggered_by=user.id,
            trigger_type="manual",
            run_log=[],
            anomaly_count=0,
            report_payload={
                "executive_summary": {},
                "steps": {
                    "draft_communications": {"communications": []}
                },
                "anomalies": [],
            },
        )
        db.add(job)
        db.flush()

        anomaly_ids: list[str] = []
        communications: list[dict] = []
        for i in range(_SEED_ITEM_COUNT):
            cust = Customer(
                id=str(uuid.uuid4()),
                company_id=co.id,
                name=f"Cust-{i:03d}",
                billing_email=f"cust{i:03d}@example.com",
                is_active=True,
            )
            db.add(cust)
            db.flush()
            a = AgentAnomaly(
                id=str(uuid.uuid4()),
                agent_job_id=job.id,
                severity="CRITICAL",
                anomaly_type="collections_critical",
                entity_type="customer",
                entity_id=cust.id,
                description=f"Cust-{i:03d} past due",
                amount=Decimal("1000.00"),
                resolved=False,
            )
            db.add(a)
            anomaly_ids.append(a.id)
            communications.append(
                {
                    "customer_id": cust.id,
                    "customer_name": cust.name,
                    "tier": "CRITICAL",
                    "total_outstanding": 1000.00,
                    "subject": f"Past-due balance for {cust.name}",
                    "body": f"Dear {cust.name}, payment due.",
                }
            )

        # Stamp all drafts onto the job.report_payload.
        from sqlalchemy.orm.attributes import flag_modified

        payload = dict(job.report_payload)
        steps = dict(payload["steps"])
        dc = dict(steps["draft_communications"])
        dc["communications"] = communications
        steps["draft_communications"] = dc
        payload["steps"] = steps
        job.report_payload = payload
        flag_modified(job, "report_payload")
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
            "anomaly_ids": anomaly_ids,
        }
    finally:
        db.close()


def _seed_tenant_with_expense_lines() -> dict:
    """Seed tenant + N VendorBillLines + anomalies ready for
    approve_line dispatch."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.models.vendor import Vendor
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_bill_line import VendorBillLine

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"EXCLAT-{suffix}",
            slug=f"exclat-{suffix}",
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
            email=f"lat-{suffix}@exc.co",
            first_name="EXC",
            last_name="Lat",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        vendor = Vendor(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="LatTestVendor",
            is_active=True,
        )
        db.add(vendor)
        db.flush()

        now = datetime.now(timezone.utc)
        bill = VendorBill(
            id=str(uuid.uuid4()),
            company_id=co.id,
            number=f"BILL-{suffix}",
            vendor_id=vendor.id,
            status="approved",
            bill_date=now,
            due_date=now + timedelta(days=30),
            subtotal=Decimal("10000.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("10000.00"),
            amount_paid=Decimal("0.00"),
        )
        db.add(bill)
        db.flush()

        today = date.today()
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=co.id,
            job_type="expense_categorization",
            status="awaiting_approval",
            period_start=today.replace(day=1),
            period_end=today,
            dry_run=False,
            triggered_by=user.id,
            trigger_type="manual",
            run_log=[],
            anomaly_count=0,
            report_payload={
                "executive_summary": {},
                "steps": {
                    "map_to_gl_accounts": {"mappings": []},
                    "classify_expenses": {"classifications": []},
                },
                "anomalies": [],
            },
        )
        db.add(job)
        db.flush()

        anomaly_ids: list[str] = []
        mappings: list[dict] = []
        for i in range(_SEED_ITEM_COUNT):
            line = VendorBillLine(
                id=str(uuid.uuid4()),
                bill_id=bill.id,
                sort_order=i,
                description=f"Line-{i:03d}",
                quantity=Decimal("1"),
                unit_cost=Decimal("100.00"),
                amount=Decimal("100.00"),
                expense_category=None,
            )
            db.add(line)
            db.flush()
            a = AgentAnomaly(
                id=str(uuid.uuid4()),
                agent_job_id=job.id,
                severity="WARNING",
                anomaly_type="expense_low_confidence",
                entity_type="vendor_bill_line",
                entity_id=line.id,
                description=f"Line-{i:03d}: 0.70 confidence",
                amount=Decimal("100.00"),
                resolved=False,
            )
            db.add(a)
            anomaly_ids.append(a.id)
            mappings.append(
                {
                    "line_id": line.id,
                    "proposed_category": "office_supplies",
                    "mapping_status": "mapped",
                    "confidence": 0.70,
                }
            )

        from sqlalchemy.orm.attributes import flag_modified

        payload = dict(job.report_payload)
        payload["steps"]["map_to_gl_accounts"] = {"mappings": mappings}
        job.report_payload = payload
        flag_modified(job, "report_payload")
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
            "anomaly_ids": anomaly_ids,
        }
    finally:
        db.close()


# ── Generic latency harness ─────────────────────────────────────────


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
    payload_for_index: callable | None = None,
) -> None:
    """Run apply_action latency gate using each item_id once.
    `payload_for_index(i)` may return an action-payload dict."""
    headers = {
        "Authorization": f"Bearer {tenant_ctx['token']}",
        "X-Company-Slug": tenant_ctx["slug"],
    }
    r = client.post(
        f"/api/v1/triage/queues/{queue_id}/sessions", headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["session_id"]

    # Warmup consumes the first N items.
    for i in range(_WARMUP_COUNT):
        body = {"action_id": action_id}
        if payload_for_index is not None:
            body["payload"] = payload_for_index(i)
        client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{item_ids[i]}/action",
            json=body,
            headers=headers,
        )

    durations: list[float] = []
    for i in range(_SAMPLE_COUNT):
        idx = _WARMUP_COUNT + i
        body = {"action_id": action_id}
        if payload_for_index is not None:
            body["payload"] = payload_for_index(idx)
        t0 = time.perf_counter()
        r = client.post(
            f"/api/v1/triage/sessions/{session_id}/items/{item_ids[idx]}/action",
            json=body,
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


# ── month_end_close gates ───────────────────────────────────────────


@pytest.fixture(scope="module")
def mec_tenant():
    return _seed_tenant_with_mec_jobs()


def test_month_end_close_next_item_latency(client, mec_tenant):
    _run_next_item_gate(
        client, mec_tenant, "month_end_close_triage", "month-end-close"
    )


def test_month_end_close_apply_action_latency(client, mec_tenant):
    _run_apply_action_gate(
        client,
        mec_tenant,
        "month_end_close_triage",
        "month-end-close",
        item_ids=mec_tenant["job_ids"],
        action_id="approve",
    )


# ── ar_collections gates ────────────────────────────────────────────


@pytest.fixture(scope="module")
def arc_tenant():
    return _seed_tenant_with_arc_anomalies()


def test_ar_collections_next_item_latency(client, arc_tenant):
    _run_next_item_gate(
        client, arc_tenant, "ar_collections_triage", "ar-collections"
    )


def test_ar_collections_apply_action_latency(client, arc_tenant):
    _run_apply_action_gate(
        client,
        arc_tenant,
        "ar_collections_triage",
        "ar-collections",
        item_ids=arc_tenant["anomaly_ids"],
        action_id="send",
    )


# ── expense_categorization gates ────────────────────────────────────


@pytest.fixture(scope="module")
def exc_tenant():
    return _seed_tenant_with_expense_lines()


def test_expense_categorization_next_item_latency(client, exc_tenant):
    _run_next_item_gate(
        client,
        exc_tenant,
        "expense_categorization_triage",
        "expense-categorization",
    )


def test_expense_categorization_apply_action_latency(
    client, exc_tenant
):
    _run_apply_action_gate(
        client,
        exc_tenant,
        "expense_categorization_triage",
        "expense-categorization",
        item_ids=exc_tenant["anomaly_ids"],
        action_id="approve",
    )
