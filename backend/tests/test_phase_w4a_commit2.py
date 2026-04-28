"""Phase W-4a Commit 2 — Layer composition services tests.

Verifies the four Pulse layer services compose content correctly,
respect tenant isolation, drive operational composition by user
work_areas, and emit canonical empty-state advisories.

Test classes:
  • TestPersonalLayer — tasks + approvals; empty state
  • TestOperationalLayerWorkAreas — work_areas-driven composition
  • TestOperationalLayerVerticalDefault — D4 vertical-default fallback
  • TestOperationalLayerWidgetGating — 5-axis filter pre-filter
  • TestAnomalyLayer — intelligence stream + widget + compliance
  • TestActivityLayer — recent_activity + system events
  • TestTenantIsolation — cross-tenant data never leaks (canonical
    Phase W-3a discipline applied to all four layers)
  • TestWorkAreasMappingShape — lock the WORK_AREA_WIDGET_MAPPING +
    VERTICAL_DEFAULT_COMPOSITIONS contract for D5 demo composition
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterator

import pytest


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
def db_session() -> Iterator:
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_tenant_user(
    *,
    vertical: str = "manufacturing",
    work_areas: list[str] | None = None,
    product_lines: list[tuple[str, str]] | None = None,
    extensions: list[str] | None = None,
    permissions: list[str] | None = None,
) -> dict:
    """Spin up a tenant + user with optional work_areas + product_lines
    + extensions + role permissions. Returns ids for downstream
    queries."""
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
            name=f"PulseLayer-{suffix}",
            slug=f"pl-{suffix}",
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
        if permissions:
            db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@example.com",
            first_name="Pulse",
            last_name="Test",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
            work_areas=work_areas,
        )
        db.add(user)
        db.commit()
        if product_lines:
            from app.services import product_line_service

            for line_key, mode in product_lines:
                product_line_service.enable_line(
                    db,
                    company_id=co.id,
                    line_key=line_key,
                    operating_mode=mode,
                )
        if extensions:
            from app.models.extension_definition import ExtensionDefinition
            from app.models.tenant_extension import TenantExtension

            for ext_key in extensions:
                ext_def = (
                    db.query(ExtensionDefinition)
                    .filter(ExtensionDefinition.extension_key == ext_key)
                    .first()
                )
                if ext_def is None:
                    ext_def = ExtensionDefinition(
                        id=str(uuid.uuid4()),
                        extension_key=ext_key,
                        module_key=ext_key,
                        display_name=ext_key,
                    )
                    db.add(ext_def)
                    db.flush()
                te = TenantExtension(
                    id=str(uuid.uuid4()),
                    tenant_id=co.id,
                    extension_key=ext_key,
                    extension_id=ext_def.id,
                    enabled=True,
                    status="active",
                )
                db.add(te)
            db.commit()
        return {"company_id": co.id, "user_id": user.id}
    finally:
        db.close()


def _make_task(
    db_session,
    *,
    company_id: str,
    assignee_user_id: str,
    title: str = "Test task",
    status: str = "open",
    priority: str = "normal",
):
    from app.models.task import Task

    t = Task(
        id=str(uuid.uuid4()),
        company_id=company_id,
        title=title,
        status=status,
        priority=priority,
        assignee_user_id=assignee_user_id,
        is_active=True,
    )
    db_session.add(t)
    db_session.commit()
    return t


def _make_agent_job(
    db_session,
    *,
    tenant_id: str,
    status: str = "awaiting_approval",
    job_type: str = "month_end_close",
):
    from app.models.agent import AgentJob

    j = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        job_type=job_type,
        status=status,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(j)
    db_session.commit()
    return j


def _make_anomaly(
    db_session,
    *,
    tenant_id: str,
    severity: str = "critical",
    anomaly_type: str = "balance_mismatch",
    description: str = "Test anomaly",
):
    """Create an anomaly tied to a fresh AgentJob (the only path that
    correctly establishes tenant scoping per the W-3a anomalies pattern)."""
    from app.models.agent_anomaly import AgentAnomaly

    job = _make_agent_job(
        db_session, tenant_id=tenant_id, status="complete"
    )
    a = AgentAnomaly(
        id=str(uuid.uuid4()),
        agent_job_id=job.id,
        severity=severity,
        anomaly_type=anomaly_type,
        description=description,
        resolved=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(a)
    db_session.commit()
    return a


# ── Personal layer ──────────────────────────────────────────────────


class TestPersonalLayer:
    def test_empty_state_advisory(self, db_session):
        from app.models.user import User
        from app.services.pulse.personal_layer_service import compose_for_user

        ctx = _make_tenant_user()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        assert result.layer == "personal"
        assert result.items == []
        assert result.advisory == "Nothing addressed to you right now."

    def test_tasks_assigned_surface_with_count_and_top_items(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.personal_layer_service import (
            TASKS_ASSIGNED_KEY,
            compose_for_user,
        )

        ctx = _make_tenant_user()
        for i in range(5):
            _make_task(
                db_session,
                company_id=ctx["company_id"],
                assignee_user_id=ctx["user_id"],
                title=f"Task {i}",
            )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        tasks = next(
            (it for it in result.items if it.component_key == TASKS_ASSIGNED_KEY),
            None,
        )
        assert tasks is not None
        assert tasks.kind == "stream"
        assert tasks.payload["total_count"] == 5
        assert len(tasks.payload["top_items"]) == 3  # top N=3

    def test_completed_tasks_excluded(self, db_session):
        from app.models.user import User
        from app.services.pulse.personal_layer_service import (
            TASKS_ASSIGNED_KEY,
            compose_for_user,
        )

        ctx = _make_tenant_user()
        _make_task(
            db_session,
            company_id=ctx["company_id"],
            assignee_user_id=ctx["user_id"],
            status="done",
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        # Done task → no surface (function returns None)
        assert all(
            it.component_key != TASKS_ASSIGNED_KEY for it in result.items
        )

    def test_approvals_waiting_surface(self, db_session):
        from app.models.user import User
        from app.services.pulse.personal_layer_service import (
            APPROVALS_WAITING_KEY,
            compose_for_user,
        )

        ctx = _make_tenant_user()
        _make_agent_job(db_session, tenant_id=ctx["company_id"])
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        approvals = next(
            (it for it in result.items if it.component_key == APPROVALS_WAITING_KEY),
            None,
        )
        assert approvals is not None
        assert approvals.payload["total_count"] == 1


# ── Operational layer — work_areas-driven ──────────────────────────


class TestOperationalLayerWorkAreas:
    def test_production_scheduling_emits_vault_schedule_detail(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical="manufacturing",
            work_areas=["Production Scheduling"],
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        keys = {it.component_key for it in result.items}
        # vault_schedule + line_status per the mapping
        assert "vault_schedule" in keys
        assert "line_status" in keys
        # vault_schedule emits at Detail variant + 2x2 sizing per D5
        vs = next(
            it for it in result.items if it.component_key == "vault_schedule"
        )
        assert vs.variant_id == "detail"
        assert vs.cols == 2 and vs.rows == 2

    def test_delivery_scheduling_full_demo_composition(self, db_session):
        """Sunnycrest dispatcher demo composition per D5: vault_schedule
        Detail + line_status Brief + ancillary_pool Brief + today
        Glance. Requires `delivery.view` permission for the
        ancillary_pool widget (Sunnycrest dispatchers have it)."""
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical="manufacturing",
            work_areas=["Production Scheduling", "Delivery Scheduling"],
            product_lines=[("vault", "production")],
            permissions=["delivery.view"],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        keys = {it.component_key for it in result.items}
        # Demo composition sans urn_catalog_status (no urn_sales here)
        assert "vault_schedule" in keys
        assert "line_status" in keys
        assert "scheduling.ancillary-pool" in keys
        assert "today" in keys

    def test_dedupe_across_overlapping_work_areas(self, db_session):
        """Production Scheduling + Delivery Scheduling both list
        vault_schedule. The composed layer should contain ONE
        vault_schedule item, not two."""
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical="manufacturing",
            work_areas=["Production Scheduling", "Delivery Scheduling"],
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        vs_count = sum(
            1 for it in result.items if it.component_key == "vault_schedule"
        )
        assert vs_count == 1

    def test_inventory_management_with_urn_extension(self, db_session):
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical="manufacturing",
            work_areas=["Inventory Management"],
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        keys = {it.component_key for it in result.items}
        # urn_catalog_status surfaces because urn_sales extension
        # active + product line enabled
        assert "urn_catalog_status" in keys

    def test_inventory_management_without_urn_extension(self, db_session):
        """5-axis filter pre-filter: urn_catalog_status filters out
        when urn_sales extension not active."""
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical="manufacturing",
            work_areas=["Inventory Management"],
            product_lines=[("vault", "production")],  # vault, NOT urn_sales
            extensions=[],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        keys = {it.component_key for it in result.items}
        assert "urn_catalog_status" not in keys

    def test_priority_ordering_within_layer(self, db_session):
        """Items sort by priority desc within the layer."""
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical="manufacturing",
            work_areas=["Delivery Scheduling"],
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        priorities = [it.priority for it in result.items]
        assert priorities == sorted(priorities, reverse=True)

    def test_stub_work_area_emits_advisory(self, db_session):
        """Inside Sales has no widgets shipped today — empty
        operational layer surfaces advisory."""
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical="manufacturing",
            work_areas=["Inside Sales"],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        assert result.items == []
        assert "extensions activate" in (result.advisory or "")


# ── Operational layer — vertical-default fallback (D4) ─────────────


class TestOperationalLayerVerticalDefault:
    def test_manufacturing_default_includes_sunnycrest_widgets(
        self, db_session
    ):
        """User without work_areas set falls back to manufacturing
        vertical default — Sunnycrest-equivalent dispatcher
        composition per D5. Requires `delivery.view` for the
        ancillary_pool widget (canonical Sunnycrest dispatcher
        permission)."""
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical="manufacturing",
            work_areas=None,  # NOT set
            product_lines=[("vault", "production")],
            permissions=["delivery.view"],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        keys = {it.component_key for it in result.items}
        # Sunnycrest demo composition
        assert "vault_schedule" in keys
        assert "line_status" in keys
        assert "scheduling.ancillary-pool" in keys
        assert "today" in keys
        # Advisory points user toward profile setup
        assert "Personalize" in (result.advisory or "")

    @pytest.mark.parametrize(
        "vertical", ["funeral_home", "cemetery", "crematory"]
    )
    def test_other_verticals_get_sparse_default(
        self, db_session, vertical
    ):
        """FH / cemetery / crematory get sparse but meaningful
        defaults — today + recent_activity."""
        from app.models.user import User
        from app.services.pulse.operational_layer_service import compose_for_user

        ctx = _make_tenant_user(
            vertical=vertical, work_areas=None
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        keys = {it.component_key for it in result.items}
        # today is cross-vertical; recent_activity is cross-vertical.
        # Both should surface.
        assert "today" in keys
        assert "recent_activity" in keys


# ── Anomaly layer ───────────────────────────────────────────────────


class TestAnomalyLayer:
    def test_empty_state_advisory(self, db_session):
        from app.models.user import User
        from app.services.pulse.anomaly_layer_service import compose_for_user

        ctx = _make_tenant_user()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        assert result.items == []
        assert "All clear" in (result.advisory or "")

    def test_anomaly_intelligence_stream_surfaces_with_payload(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.anomaly_layer_service import (
            ANOMALY_INTELLIGENCE_STREAM_KEY,
            compose_for_user,
        )

        ctx = _make_tenant_user(
            work_areas=["Production Scheduling"]
        )
        _make_anomaly(db_session, tenant_id=ctx["company_id"])
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        intel = next(
            (
                it
                for it in result.items
                if it.component_key == ANOMALY_INTELLIGENCE_STREAM_KEY
            ),
            None,
        )
        assert intel is not None
        assert intel.payload["total_unresolved"] == 1
        assert intel.payload["critical_count"] == 1
        # Work areas relayed for frontend template
        assert intel.payload["work_areas"] == ["Production Scheduling"]

    def test_intelligence_stream_priority_above_widget(self, db_session):
        """Synthesis surfaces above raw widget per layer composition
        intent — intel stream priority > widget priority."""
        from app.models.user import User
        from app.services.pulse.anomaly_layer_service import (
            ANOMALIES_WIDGET_KEY,
            ANOMALY_INTELLIGENCE_STREAM_KEY,
            compose_for_user,
        )

        ctx = _make_tenant_user()
        _make_anomaly(db_session, tenant_id=ctx["company_id"])
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        intel = next(
            it
            for it in result.items
            if it.component_key == ANOMALY_INTELLIGENCE_STREAM_KEY
        )
        widget = next(
            it
            for it in result.items
            if it.component_key == ANOMALIES_WIDGET_KEY
        )
        assert intel.priority > widget.priority
        # Layer-internal sort respects priority
        keys = [it.component_key for it in result.items]
        assert keys.index(ANOMALY_INTELLIGENCE_STREAM_KEY) < keys.index(
            ANOMALIES_WIDGET_KEY
        )


# ── Activity layer ──────────────────────────────────────────────────


class TestActivityLayer:
    def test_empty_state_advisory(self, db_session):
        from app.models.user import User
        from app.services.pulse.activity_layer_service import compose_for_user

        ctx = _make_tenant_user()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        # No activity log entries + no agent jobs → empty advisory
        assert result.items == []
        assert "Quiet day" in (result.advisory or "")

    def test_system_events_stream_surfaces_recent_completions(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.activity_layer_service import (
            SYSTEM_EVENTS_STREAM_KEY,
            compose_for_user,
        )

        ctx = _make_tenant_user()
        # Recent (1h ago) completion
        from app.models.agent import AgentJob

        j = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=ctx["company_id"],
            job_type="month_end_close",
            status="complete",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(j)
        db_session.commit()

        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        events = next(
            (
                it
                for it in result.items
                if it.component_key == SYSTEM_EVENTS_STREAM_KEY
            ),
            None,
        )
        assert events is not None
        assert events.payload["total_count"] == 1

    def test_old_system_events_excluded(self, db_session):
        """Events older than 24h don't surface."""
        from app.models.agent import AgentJob
        from app.models.user import User
        from app.services.pulse.activity_layer_service import (
            SYSTEM_EVENTS_STREAM_KEY,
            compose_for_user,
        )

        ctx = _make_tenant_user()
        # 2 days ago — outside the 24h window
        j = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=ctx["company_id"],
            job_type="month_end_close",
            status="complete",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            completed_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db_session.add(j)
        db_session.commit()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user)
        assert all(
            it.component_key != SYSTEM_EVENTS_STREAM_KEY
            for it in result.items
        )


# ── Tenant isolation (canonical W-3a discipline applied) ────────────


class TestTenantIsolation:
    def test_personal_layer_tasks_scoped_to_caller_tenant(
        self, db_session
    ):
        from app.models.user import User
        from app.services.pulse.personal_layer_service import (
            TASKS_ASSIGNED_KEY,
            compose_for_user,
        )

        ctx_a = _make_tenant_user()
        ctx_b = _make_tenant_user()
        # Tenant B has 5 tasks for B's user; A's user has 0.
        for i in range(5):
            _make_task(
                db_session,
                company_id=ctx_b["company_id"],
                assignee_user_id=ctx_b["user_id"],
            )
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user_a)
        # A's user sees nothing
        assert all(
            it.component_key != TASKS_ASSIGNED_KEY for it in result.items
        )

    def test_anomaly_layer_scoped_to_caller_tenant(self, db_session):
        from app.models.user import User
        from app.services.pulse.anomaly_layer_service import (
            ANOMALY_INTELLIGENCE_STREAM_KEY,
            compose_for_user,
        )

        ctx_a = _make_tenant_user()
        ctx_b = _make_tenant_user()
        # Anomalies in tenant B should not surface for A
        for _ in range(3):
            _make_anomaly(db_session, tenant_id=ctx_b["company_id"])
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user_a)
        # A sees no anomalies → empty layer with All-clear advisory
        assert all(
            it.component_key != ANOMALY_INTELLIGENCE_STREAM_KEY
            for it in result.items
        )

    def test_activity_layer_scoped_to_caller_tenant(self, db_session):
        from app.models.agent import AgentJob
        from app.models.user import User
        from app.services.pulse.activity_layer_service import (
            SYSTEM_EVENTS_STREAM_KEY,
            compose_for_user,
        )

        ctx_a = _make_tenant_user()
        ctx_b = _make_tenant_user()
        # Tenant B agent completion
        j = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=ctx_b["company_id"],
            job_type="month_end_close",
            status="complete",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(j)
        db_session.commit()
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        result = compose_for_user(db_session, user=user_a)
        # A sees no system events from B
        assert all(
            it.component_key != SYSTEM_EVENTS_STREAM_KEY
            for it in result.items
        )


# ── Mapping shape locks (canon contract) ────────────────────────────


class TestWorkAreasMappingShape:
    """Canon contract tests — pin the work-areas mapping + vertical
    defaults so future changes surface explicitly."""

    def test_all_canonical_work_areas_have_mapping_entries(self):
        """Every work area listed in the canonical operator-profile
        vocabulary must have an entry in WORK_AREA_WIDGET_MAPPING
        (even if empty list — explicit "no widgets yet")."""
        from app.services.operator_profile_service import WORK_AREAS
        from app.services.pulse.operational_layer_service import (
            WORK_AREA_WIDGET_MAPPING,
        )

        for area in WORK_AREAS:
            assert area in WORK_AREA_WIDGET_MAPPING, (
                f"Work area {area!r} missing mapping entry. Add an "
                f"explicit list (possibly empty) for clarity."
            )

    def test_all_verticals_have_default_compositions(self):
        from app.services.pulse.operational_layer_service import (
            VERTICAL_DEFAULT_COMPOSITIONS,
        )

        # All four verticals per CLAUDE.md tenant presets
        for vertical in (
            "manufacturing",
            "funeral_home",
            "cemetery",
            "crematory",
        ):
            assert vertical in VERTICAL_DEFAULT_COMPOSITIONS

    def test_manufacturing_default_matches_d5_demo_composition(self):
        """Lock the Sunnycrest dispatcher demo composition per D5 —
        regression guard against future drift."""
        from app.services.pulse.operational_layer_service import (
            VERTICAL_DEFAULT_COMPOSITIONS,
        )

        mfg = VERTICAL_DEFAULT_COMPOSITIONS["manufacturing"]
        widget_ids = {entry[0] for entry in mfg}
        assert "vault_schedule" in widget_ids
        assert "line_status" in widget_ids
        assert "scheduling.ancillary-pool" in widget_ids
        assert "today" in widget_ids
        # urn_catalog_status conditional on extension
        assert "urn_catalog_status" in widget_ids
        # vault_schedule MUST be Detail (2x2) per D5
        vs_entry = next(
            entry for entry in mfg if entry[0] == "vault_schedule"
        )
        assert vs_entry[1] == "detail"
        assert vs_entry[2] == 2 and vs_entry[3] == 2

    def test_production_scheduling_emits_vault_schedule_detail(self):
        """Mapping contract — Production Scheduling primary surface
        is vault_schedule at Detail variant per §3.26.2.4."""
        from app.services.pulse.operational_layer_service import (
            WORK_AREA_WIDGET_MAPPING,
        )

        ps = WORK_AREA_WIDGET_MAPPING["Production Scheduling"]
        widget_ids = {entry[0] for entry in ps}
        assert "vault_schedule" in widget_ids
        vs_entry = next(
            entry for entry in ps if entry[0] == "vault_schedule"
        )
        assert vs_entry[1] == "detail"
