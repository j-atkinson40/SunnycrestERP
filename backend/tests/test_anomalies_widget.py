"""Phase W-3a `anomalies` widget — backend service + endpoint tests.

Critical coverage areas:
  • get_anomalies returns tenant-scoped list (TestTenantIsolation
    explicit cross-tenant rejection)
  • severity filtering + sort order (critical → warning → info)
  • acknowledge endpoint requires authentication
  • acknowledge endpoint rejects cross-tenant anomaly_id (404, not 403,
    to prevent existence leakage)
  • acknowledge writes audit log entry
  • acknowledge is idempotent (re-ack of resolved anomaly is no-op)
  • Widget catalog visibility (Brief + Detail only, NO Glance)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterator

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _seeded() -> Iterator[None]:
    from app.database import SessionLocal
    from app.services.widgets.widget_registry import seed_widget_definitions

    db = SessionLocal()
    try:
        seed_widget_definitions(db)
        yield
    finally:
        db.close()


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_tenant_user_token(
    *,
    vertical: str = "manufacturing",
    permissions: list[str] | None = None,
    product_lines: list[str] | None = None,
) -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"AnomaliesTest-{suffix}",
            slug=f"an-{suffix}",
            is_active=True,
            vertical=vertical,
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Test",
            slug="test",
            is_system=False,
        )
        db.add(role)
        db.flush()
        for p in permissions or []:
            db.add(RolePermission(role_id=role.id, permission_key=p))
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@an.test",
            first_name="Anom",
            last_name="Test",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        if product_lines:
            from app.services import product_line_service

            for line_key in product_lines:
                product_line_service.enable_line(
                    db, company_id=co.id, line_key=line_key
                )
        token = create_access_token(
            {"sub": user.id, "company_id": co.id, "realm": "tenant"}
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "user_id": user.id,
            "token": token,
        }
    finally:
        db.close()


def _seed_agent_job(db_session, *, tenant_id: str, job_type: str = "month_end_close"):
    from app.models.agent import AgentJob

    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        job_type=job_type,
        status="complete",
    )
    db_session.add(job)
    db_session.commit()
    return job


def _seed_anomaly(
    db_session,
    *,
    agent_job_id: str,
    severity: str = "critical",
    anomaly_type: str = "balance_mismatch",
    description: str = "Test anomaly",
    resolved: bool = False,
):
    from app.models.agent_anomaly import AgentAnomaly

    a = AgentAnomaly(
        id=str(uuid.uuid4()),
        agent_job_id=agent_job_id,
        severity=severity,
        anomaly_type=anomaly_type,
        description=description,
        resolved=resolved,
    )
    db_session.add(a)
    db_session.commit()
    return a


# ── get_anomalies — service-layer ───────────────────────────────────


class TestGetAnomalies:
    def test_returns_unresolved_for_tenant(self, db_session):
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            get_anomalies,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        _seed_anomaly(
            db_session,
            agent_job_id=job.id,
            severity="critical",
            description="Critical issue",
        )

        result = get_anomalies(db_session, user=user)
        assert result["total_unresolved"] == 1
        assert result["critical_count"] == 1
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["severity"] == "critical"

    def test_severity_sort_order_critical_first(self, db_session):
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            get_anomalies,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        # Seed in opposite order — service must re-sort.
        _seed_anomaly(db_session, agent_job_id=job.id, severity="info")
        _seed_anomaly(db_session, agent_job_id=job.id, severity="warning")
        _seed_anomaly(db_session, agent_job_id=job.id, severity="critical")

        result = get_anomalies(db_session, user=user)
        severities = [a["severity"] for a in result["anomalies"]]
        assert severities == ["critical", "warning", "info"]

    def test_severity_filter(self, db_session):
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            get_anomalies,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        _seed_anomaly(db_session, agent_job_id=job.id, severity="critical")
        _seed_anomaly(db_session, agent_job_id=job.id, severity="warning")
        _seed_anomaly(db_session, agent_job_id=job.id, severity="info")

        result = get_anomalies(
            db_session, user=user, severity_filter="critical"
        )
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["severity"] == "critical"
        # total_unresolved counts ALL severities, ignoring the filter
        assert result["total_unresolved"] == 3

    def test_resolved_excluded_by_default(self, db_session):
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            get_anomalies,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        _seed_anomaly(
            db_session,
            agent_job_id=job.id,
            severity="critical",
            resolved=True,
        )
        _seed_anomaly(
            db_session,
            agent_job_id=job.id,
            severity="warning",
            resolved=False,
        )

        result = get_anomalies(db_session, user=user)
        assert result["total_unresolved"] == 1
        assert result["anomalies"][0]["severity"] == "warning"

    def test_include_resolved_returns_all(self, db_session):
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            get_anomalies,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        _seed_anomaly(
            db_session,
            agent_job_id=job.id,
            severity="critical",
            resolved=True,
        )
        _seed_anomaly(
            db_session, agent_job_id=job.id, severity="warning"
        )

        result = get_anomalies(
            db_session, user=user, include_resolved=True
        )
        assert len(result["anomalies"]) == 2

    def test_limit_caps_results(self, db_session):
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            get_anomalies,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        for _ in range(10):
            _seed_anomaly(
                db_session, agent_job_id=job.id, severity="warning"
            )

        result = get_anomalies(db_session, user=user, limit=3)
        assert len(result["anomalies"]) == 3
        assert result["total_unresolved"] == 10  # not capped


# ── Tenant isolation (load-bearing security gate) ────────────────────


class TestTenantIsolation:
    """The anomalies widget exposes sensitive operational data.
    Tenant isolation is verified explicitly — both directions
    (read + acknowledge) — to prevent cross-tenant leak by construction."""

    def test_anomaly_from_other_tenant_excluded(self, db_session):
        """Tenant A queries → must NOT see tenant B's anomalies."""
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            get_anomalies,
        )

        ctx_a = _make_tenant_user_token()
        ctx_b = _make_tenant_user_token()
        # Seed anomaly for tenant B
        job_b = _seed_agent_job(db_session, tenant_id=ctx_b["company_id"])
        _seed_anomaly(
            db_session,
            agent_job_id=job_b.id,
            severity="critical",
            description="Tenant B's anomaly",
        )

        # Tenant A queries — must see ZERO
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        result = get_anomalies(db_session, user=user_a)
        assert result["total_unresolved"] == 0
        assert result["anomalies"] == []

    def test_resolve_anomaly_rejects_cross_tenant(self, db_session):
        """Tenant A cannot resolve tenant B's anomaly. Returns None
        (caller surfaces 404 to prevent existence leakage)."""
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            resolve_anomaly,
        )

        ctx_a = _make_tenant_user_token()
        ctx_b = _make_tenant_user_token()
        job_b = _seed_agent_job(db_session, tenant_id=ctx_b["company_id"])
        anomaly = _seed_anomaly(
            db_session,
            agent_job_id=job_b.id,
            severity="critical",
            description="Tenant B's anomaly",
        )

        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        result = resolve_anomaly(
            db_session, user=user_a, anomaly_id=anomaly.id
        )
        assert result is None

        # Verify tenant B's anomaly is still unresolved
        db_session.refresh(anomaly)
        assert anomaly.resolved is False

    def test_acknowledge_endpoint_returns_404_for_cross_tenant(self):
        """HTTP-level: cross-tenant acknowledge returns 404, not 403,
        to prevent existence leakage."""
        from app.main import app
        from fastapi.testclient import TestClient

        from app.database import SessionLocal

        client = TestClient(app)
        ctx_a = _make_tenant_user_token()
        ctx_b = _make_tenant_user_token()

        # Seed anomaly for tenant B via a fresh session (TestClient
        # closes its own session per request).
        sess = SessionLocal()
        try:
            job_b = _seed_agent_job(sess, tenant_id=ctx_b["company_id"])
            anomaly = _seed_anomaly(
                sess,
                agent_job_id=job_b.id,
                severity="critical",
            )
            anomaly_id = anomaly.id
        finally:
            sess.close()

        # Tenant A user attempts acknowledge → 404
        r = client.post(
            f"/api/v1/widget-data/anomalies/{anomaly_id}/acknowledge",
            json={},
            headers={
                "Authorization": f"Bearer {ctx_a['token']}",
                "X-Company-Slug": ctx_a["slug"],
            },
        )
        assert r.status_code == 404


# ── Acknowledge action ───────────────────────────────────────────────


class TestAcknowledge:
    def test_resolve_flips_state_and_records_resolver(self, db_session):
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            resolve_anomaly,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        anomaly = _seed_anomaly(db_session, agent_job_id=job.id)

        result = resolve_anomaly(
            db_session,
            user=user,
            anomaly_id=anomaly.id,
            resolution_note="False alarm — verified manually",
        )
        assert result is not None
        assert result.resolved is True
        assert result.resolved_by == user.id
        assert result.resolved_at is not None
        assert result.resolution_note == "False alarm — verified manually"

        # Re-query to confirm persistence
        refreshed = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == anomaly.id)
            .one()
        )
        assert refreshed.resolved is True

    def test_resolve_idempotent_no_op_on_already_resolved(self, db_session):
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            resolve_anomaly,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        anomaly = _seed_anomaly(
            db_session, agent_job_id=job.id, resolved=True
        )

        # Pre-state — already resolved by no one (test fixture skipped
        # those fields).
        original_resolved_by = anomaly.resolved_by
        result = resolve_anomaly(
            db_session, user=user, anomaly_id=anomaly.id
        )
        # Idempotent — returned the existing row, no state mutation
        assert result is not None
        assert result.resolved is True
        assert result.resolved_by == original_resolved_by

    def test_acknowledge_writes_audit_log(self, db_session):
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.audit_log import AuditLog
        from app.models.user import User
        from app.services.widgets.anomalies_widget_service import (
            resolve_anomaly,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        job = _seed_agent_job(db_session, tenant_id=ctx["company_id"])
        anomaly = _seed_anomaly(db_session, agent_job_id=job.id)

        resolve_anomaly(db_session, user=user, anomaly_id=anomaly.id)

        # Verify audit log entry was written
        audit_row = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "anomaly_resolved",
                AuditLog.entity_id == anomaly.id,
                AuditLog.company_id == ctx["company_id"],
            )
            .first()
        )
        assert audit_row is not None
        assert audit_row.user_id == user.id
        assert audit_row.entity_type == "agent_anomaly"

    def test_acknowledge_endpoint_requires_auth(self):
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        r = client.post(
            "/api/v1/widget-data/anomalies/some-id/acknowledge", json={}
        )
        assert r.status_code in (401, 403)

    def test_acknowledge_endpoint_404_for_nonexistent(self):
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        ctx = _make_tenant_user_token()
        r = client.post(
            "/api/v1/widget-data/anomalies/does-not-exist/acknowledge",
            json={},
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 404


# ── Endpoint shape ───────────────────────────────────────────────────


class TestEndpointShape:
    def test_get_anomalies_endpoint_shape(self):
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        ctx = _make_tenant_user_token()
        r = client.get(
            "/api/v1/widget-data/anomalies",
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "anomalies" in body
        assert "total_unresolved" in body
        assert "critical_count" in body

    def test_severity_query_param_validated(self):
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        ctx = _make_tenant_user_token()
        # Invalid severity → 422
        r = client.get(
            "/api/v1/widget-data/anomalies?severity=invalid_value",
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 422


# ── Widget catalog visibility ───────────────────────────────────────


class TestWidgetCatalog:
    def test_widget_registered_brief_and_detail_only_no_glance(
        self, db_session
    ):
        """Per §12.10: anomalies has Brief + Detail only — NO Glance.
        Anomalies need at least Brief context (count alone doesn't
        communicate severity or actionability)."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "anomalies")
            .one()
        )
        variant_ids = {v["variant_id"] for v in row.variants}
        assert variant_ids == {"brief", "detail"}, (
            f"anomalies must have Brief + Detail only (no Glance) per "
            f"§12.10; got {variant_ids}"
        )
        assert row.default_variant_id == "brief"
        assert row.required_vertical == ["*"]
        assert row.required_product_line == ["*"]
        assert "spaces_pin" in row.supported_surfaces

    def test_widget_visible_to_all_verticals(self, db_session):
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        for vertical in ("manufacturing", "funeral_home", "cemetery", "crematory"):
            ctx = _make_tenant_user_token(vertical=vertical)
            user = (
                db_session.query(User)
                .filter(User.id == ctx["user_id"])
                .one()
            )
            widgets = get_available_widgets(
                db_session, ctx["company_id"], user, "pulse"
            )
            an = next(
                (w for w in widgets if w["widget_id"] == "anomalies"),
                None,
            )
            assert an is not None, f"anomalies widget invisible to {vertical}"
            assert an["is_available"] is True
