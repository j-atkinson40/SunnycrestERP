"""BLOCKING CI gates — Phase 8d triage latency for both Phase 8d
triage queues.

Four gates (two per queue):
  aftercare_triage:
    next_item     p50 < 100 ms, p99 < 300 ms
    apply_action  p50 < 200 ms, p99 < 500 ms
      (apply = aftercare.send which routes through delivery_service
       + VaultItem creation; delivery_service monkey-patched to no-op)
  catalog_fetch_triage:
    next_item     p50 < 100 ms, p99 < 300 ms
    apply_action  p50 < 200 ms, p99 < 500 ms
      (apply = catalog_fetch.approve which calls
       WilbertIngestionService.ingest_from_pdf; both ingest + R2
       download monkey-patched so we measure orchestration overhead
       only — consistent with Phase 8c methodology)

Methodology mirrors Phase 5/8b/8c latency patterns:
  - Seed one tenant + admin + 40 items per queue.
  - 3 warmups + 30 samples sequential per operation.
  - Gates are sequential (single-process) so we're measuring
    orchestration overhead, not IO wall clock.

Opt-out: TRIAGE_LATENCY_DISABLE=1.
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

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
        "TRIAGE_LATENCY_DISABLE=1 — skipping Phase 8d latency gates",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


# ── Aftercare fixtures ───────────────────────────────────────────────


def _seed_aftercare_tenant() -> dict:
    """Seed a FH tenant + admin + N funeral cases each with a
    service_date = today-7 + a staged AgentAnomaly ready for
    aftercare.send dispatch."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.company import Company
    from app.models.funeral_case import (
        CaseDeceased,
        CaseInformant,
        CaseService,
        FuneralCase,
    )
    from app.models.role import Role
    from app.models.user import User
    from app.services.workflows.aftercare_adapter import (
        AFTERCARE_JOB_TYPE,
        ANOMALY_TYPE,
    )

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"ACLAT-{suffix}",
            slug=f"aclat-{suffix}",
            is_active=True,
            vertical="funeral_home",
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
            email=f"lat-{suffix}@ac.co",
            first_name="AC",
            last_name="Lat",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        today = date.today()
        service_date = today - timedelta(days=7)

        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=co.id,
            job_type=AFTERCARE_JOB_TYPE,
            status="complete",
            period_start=today,
            period_end=today,
            dry_run=False,
            triggered_by=user.id,
            trigger_type="manual",
            run_log=[],
            anomaly_count=_SEED_ITEM_COUNT,
            report_payload={"pipeline": "fh_aftercare_7day"},
        )
        db.add(job)
        db.flush()

        anomaly_ids: list[str] = []
        for i in range(_SEED_ITEM_COUNT):
            fc = FuneralCase(
                id=str(uuid.uuid4()),
                company_id=co.id,
                case_number=f"LAT-{i:03d}",
                status="active",
                current_step="aftercare",
            )
            db.add(fc)
            db.flush()
            db.add(
                CaseDeceased(
                    case_id=fc.id,
                    company_id=co.id,
                    first_name="A",
                    last_name=f"Family{i:03d}",
                )
            )
            db.add(
                CaseInformant(
                    case_id=fc.id,
                    company_id=co.id,
                    name=f"Primary {i}",
                    email=f"primary{i:03d}@example.com",
                    is_primary=True,
                )
            )
            db.add(
                CaseService(
                    case_id=fc.id,
                    company_id=co.id,
                    service_date=service_date,
                )
            )
            a = AgentAnomaly(
                id=str(uuid.uuid4()),
                agent_job_id=job.id,
                severity="info",
                anomaly_type=ANOMALY_TYPE,
                entity_type="funeral_case",
                entity_id=fc.id,
                description=f"Aftercare case {i:03d}",
                resolved=False,
            )
            db.add(a)
            anomaly_ids.append(a.id)
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


# ── Catalog fetch fixtures ───────────────────────────────────────────


def _seed_catalog_fetch_tenant() -> dict:
    """Seed tenant + admin + N pending-review UrnCatalogSyncLog rows
    ready for catalog_fetch.approve dispatch. Each has a unique
    pdf_filename so approve can be run per-row."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"CFLAT-{suffix}",
            slug=f"cflat-{suffix}",
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
            email=f"lat-{suffix}@cf.co",
            first_name="CF",
            last_name="Lat",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        # Grant the urn_sales extension so the queue's
        # required_extension gate passes.
        from app.models.tenant_extension import TenantExtension

        ext_row = TenantExtension(
            id=str(uuid.uuid4()),
            tenant_id=co.id,
            extension_key="urn_sales",
            enabled=True,
            status="active",
        )
        db.add(ext_row)
        db.flush()

        log_ids: list[str] = []
        for i in range(_SEED_ITEM_COUNT):
            # Stagger started_at so ordering is stable.
            ts = datetime.now(timezone.utc) - timedelta(minutes=i)
            log = UrnCatalogSyncLog(
                id=str(uuid.uuid4()),
                tenant_id=co.id,
                started_at=ts,
                status="running",
                publication_state="pending_review",
                sync_type="pdf_staged",
                pdf_filename=f"catalogs/wilbert/latency-{i:03d}.pdf",
                products_added=0,
                products_updated=i + 1,  # preview count
                products_discontinued=0,
                products_skipped=0,
            )
            db.add(log)
            log_ids.append(log.id)
        db.commit()

        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
            "log_ids": log_ids,
        }
    finally:
        db.close()


# ── Generic harness (copied from Phase 8c, same targets) ─────────────


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


# ── Aftercare gates ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def aftercare_tenant():
    return _seed_aftercare_tenant()


def test_aftercare_next_item_latency(client, aftercare_tenant):
    _run_next_item_gate(
        client, aftercare_tenant, "aftercare_triage", "aftercare"
    )


def test_aftercare_apply_action_latency(client, aftercare_tenant):
    """Measure apply_action orchestration overhead with
    delivery_service + VaultItem creation monkey-patched to no-op."""

    class _FakeDelivery:
        def __init__(self):
            self.id = "delivery-fake-" + uuid.uuid4().hex[:8]

    def _fake_send(db, **kwargs):
        return _FakeDelivery()

    def _fake_vault(db, **kwargs):
        return None

    with patch(
        "app.services.delivery.delivery_service.send_email_with_template",
        side_effect=_fake_send,
    ), patch(
        "app.services.vault_service.create_vault_item",
        side_effect=_fake_vault,
    ):
        _run_apply_action_gate(
            client,
            aftercare_tenant,
            "aftercare_triage",
            "aftercare",
            item_ids=aftercare_tenant["anomaly_ids"],
            action_id="send",
        )


# ── Catalog fetch gates ─────────────────────────────────────────────


@pytest.fixture(scope="module")
def catalog_fetch_tenant():
    return _seed_catalog_fetch_tenant()


def test_catalog_fetch_next_item_latency(client, catalog_fetch_tenant):
    _run_next_item_gate(
        client,
        catalog_fetch_tenant,
        "catalog_fetch_triage",
        "catalog-fetch",
    )


def test_catalog_fetch_apply_action_latency(
    client, catalog_fetch_tenant
):
    """Measure approve orchestration overhead. R2 download +
    WilbertIngestionService.ingest_from_pdf monkey-patched so we
    measure the adapter's state-flip + commit, not the PDF parse."""
    from app.models.urn_catalog_sync_log import UrnCatalogSyncLog

    def _fake_ingest(db, tenant_id, pdf_path, enrich_from_website=False):
        # Return a fake log row the adapter can mark superseded.
        log = UrnCatalogSyncLog(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            status="completed",
            publication_state="published",
            products_added=1,
            products_updated=0,
            products_discontinued=0,
            products_skipped=0,
        )
        db.add(log)
        db.flush()
        return log

    with patch(
        "app.services.legacy_r2_client.download_bytes",
        return_value=b"fake-pdf-bytes",
    ), patch(
        "app.services.wilbert_ingestion_service.WilbertIngestionService.ingest_from_pdf",
        side_effect=_fake_ingest,
    ):
        _run_apply_action_gate(
            client,
            catalog_fetch_tenant,
            "catalog_fetch_triage",
            "catalog-fetch",
            item_ids=catalog_fetch_tenant["log_ids"],
            action_id="approve",
        )
