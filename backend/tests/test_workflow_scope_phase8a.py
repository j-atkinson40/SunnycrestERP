"""Workflow Arc Phase 8a — tests for scope filtering + fork mechanism.

Covers:
  - Migration r36 backfill (scope populated for all existing rows
    from tier; agent_registry_key set for 3 wf_sys_* workflows)
  - GET /workflows?scope=core|vertical|tenant filtering
  - GET /workflows?include_used_by=true populates used_by_count
  - POST /workflows/{id}/fork happy path
  - Fork preserves steps + step params + DAG edges
  - Fork sets forked_from_workflow_id + forked_at
  - Fork rejects non-forkable scopes (tenant-scoped source)
  - Fork rejects cross-vertical fork
  - Fork prevents double-fork (409 AlreadyForked)
  - Fork clears agent_registry_key (fork runs through
    workflow_engine, not AgentRunner)
  - used_by count counts distinct active enrollments only
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(*, vertical: str = "manufacturing"):
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"WF-{suffix}",
            slug=f"wf-{suffix}",
            is_active=True,
            vertical=vertical,
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
            email=f"u-{suffix}@wf.co",
            first_name="Wf",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "vertical": vertical,
            "token": token,
            "slug": co.slug,
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-Company-Slug": co.slug,
            },
        }
    finally:
        db.close()


def _make_workflow(
    db,
    *,
    wf_id: str | None = None,
    scope: str,
    vertical: str | None,
    company_id: str | None = None,
    tier: int = 2,
    agent_registry_key: str | None = None,
    name: str | None = None,
) -> str:
    from app.models.workflow import Workflow, WorkflowStep

    wf_id = wf_id or str(uuid.uuid4())
    wf = Workflow(
        id=wf_id,
        company_id=company_id,
        name=name or f"TestWF-{wf_id[:6]}",
        description="test",
        tier=tier,
        scope=scope,
        vertical=vertical,
        trigger_type="manual",
        is_active=True,
        is_system=(scope == "core"),
        agent_registry_key=agent_registry_key,
    )
    db.add(wf)
    db.flush()
    # Two steps so fork-DAG tests have something to verify.
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    db.add(
        WorkflowStep(
            id=s1_id,
            workflow_id=wf.id,
            step_order=1,
            step_key="step_a",
            step_type="action",
            config={"x": 1},
            next_step_id=s2_id,
        )
    )
    db.add(
        WorkflowStep(
            id=s2_id,
            workflow_id=wf.id,
            step_order=2,
            step_key="step_b",
            step_type="action",
            config={"y": 2},
        )
    )
    db.commit()
    return wf_id


# ── Migration backfill ─────────────────────────────────────────────


class TestMigrationBackfill:
    def test_all_existing_workflows_have_scope(self, db_session):
        from app.models.workflow import Workflow

        nulls = (
            db_session.query(Workflow)
            .filter(Workflow.scope.is_(None))
            .count()
        )
        assert nulls == 0

    def test_tier_1_cross_vertical_workflows_are_core(self, db_session):
        # Tightened by Phase 8d r38_fix_vertical_scope_backfill. The
        # original r36 rule "tier=1 ⇒ scope=core" ignored the
        # `vertical` column and misclassified 10 vertical-specific
        # system workflows. Post-r38, the invariant is split:
        #   tier=1 AND vertical IS NULL    → core
        #   tier=1 AND vertical IS NOT NULL → vertical
        # The companion regression gate lives in
        # test_r38_scope_backfill_fix.py.
        from app.models.workflow import Workflow

        tier1_cross_vertical_not_core = (
            db_session.query(Workflow)
            .filter(
                Workflow.tier == 1,
                Workflow.vertical.is_(None),
                Workflow.scope != "core",
            )
            .count()
        )
        assert tier1_cross_vertical_not_core == 0

    def test_tier_2_and_3_workflows_are_vertical(self, db_session):
        from app.models.workflow import Workflow

        mismatched = (
            db_session.query(Workflow)
            .filter(
                Workflow.tier.in_([2, 3]),
                Workflow.scope != "vertical",
                Workflow.company_id.is_(None),  # ignore tenant-owned edge
            )
            .count()
        )
        assert mismatched == 0

    def test_agent_registry_key_set_on_three_workflows(self, db_session):
        from app.models.workflow import Workflow

        agent_backed = (
            db_session.query(Workflow.id)
            .filter(Workflow.agent_registry_key.isnot(None))
            .all()
        )
        ids = {row.id for row in agent_backed}
        # These three wf_sys_* workflows have registered agents in
        # AgentRunner.AGENT_REGISTRY. Other agents (unbilled_orders,
        # cash_receipts, etc.) don't have wf_sys_* stubs yet; they
        # get added in Phase 8b-8f.
        assert "wf_sys_month_end_close" in ids
        assert "wf_sys_ar_collections" in ids
        assert "wf_sys_expense_categorization" in ids


# ── Scope-filter API ───────────────────────────────────────────────


class TestScopeFiltering:
    def test_core_tab_returns_core_only(self, client):
        ctx = _make_ctx(vertical="manufacturing")
        r = client.get(
            "/api/v1/workflows?scope=core", headers=ctx["headers"]
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) > 0
        for row in rows:
            assert row["scope"] == "core"

    def test_vertical_tab_filters_by_tenant_vertical(self, client):
        ctx = _make_ctx(vertical="manufacturing")
        r = client.get(
            "/api/v1/workflows?scope=vertical", headers=ctx["headers"]
        )
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) > 0
        for row in rows:
            assert row["scope"] == "vertical"
            # Either matches tenant's vertical or has no vertical.
            assert row["vertical"] in (None, "manufacturing")

    def test_tenant_tab_returns_only_caller_owned(self, client, db_session):
        ctx_a = _make_ctx()
        ctx_b = _make_ctx()
        # Create one tenant workflow per tenant.
        _make_workflow(
            db_session,
            scope="tenant",
            vertical=None,
            company_id=ctx_a["company_id"],
            name="A-tenant-wf",
            tier=4,
        )
        _make_workflow(
            db_session,
            scope="tenant",
            vertical=None,
            company_id=ctx_b["company_id"],
            name="B-tenant-wf",
            tier=4,
        )

        r = client.get(
            "/api/v1/workflows?scope=tenant", headers=ctx_a["headers"]
        )
        assert r.status_code == 200
        rows = r.json()
        names = {row["name"] for row in rows}
        assert "A-tenant-wf" in names
        assert "B-tenant-wf" not in names

    def test_invalid_scope_rejected(self, client):
        ctx = _make_ctx()
        r = client.get(
            "/api/v1/workflows?scope=invalid", headers=ctx["headers"]
        )
        assert r.status_code == 422  # Pydantic regex mismatch

    def test_include_used_by_populates_count(self, client, db_session):
        from app.models.workflow import Workflow, WorkflowEnrollment

        ctx = _make_ctx()
        # Pick a core workflow and enroll 2 tenants.
        core = (
            db_session.query(Workflow).filter(Workflow.scope == "core").first()
        )
        assert core is not None

        for _ in range(2):
            new_ctx = _make_ctx()
            db_session.add(
                WorkflowEnrollment(
                    id=str(uuid.uuid4()),
                    workflow_id=core.id,
                    company_id=new_ctx["company_id"],
                    is_active=True,
                )
            )
        db_session.commit()

        r = client.get(
            "/api/v1/workflows?scope=core&include_used_by=true",
            headers=ctx["headers"],
        )
        assert r.status_code == 200
        rows = r.json()
        hit = next((row for row in rows if row["id"] == core.id), None)
        assert hit is not None
        assert hit["used_by_count"] is not None
        assert hit["used_by_count"] >= 2


# ── Fork mechanism ─────────────────────────────────────────────────


class TestForkEndpoint:
    def test_fork_core_workflow_happy_path(self, client, db_session):
        from app.models.workflow import Workflow, WorkflowStep

        ctx = _make_ctx(vertical="manufacturing")
        core = (
            db_session.query(Workflow).filter(Workflow.scope == "core").first()
        )
        assert core is not None
        source_step_count = (
            db_session.query(WorkflowStep)
            .filter(WorkflowStep.workflow_id == core.id)
            .count()
        )

        r = client.post(
            f"/api/v1/workflows/{core.id}/fork",
            json={"new_name": "My Forked Workflow"},
            headers=ctx["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scope"] == "tenant"
        assert body["company_id"] == ctx["company_id"]
        assert body["forked_from_workflow_id"] == core.id
        assert body["forked_at"] is not None
        assert body["name"] == "My Forked Workflow"
        # Agent-backed workflows clear the key on fork — the fork
        # runs via workflow_engine, not AgentRunner.
        assert body["agent_registry_key"] is None
        # Steps copied
        assert body["step_count"] == source_step_count

    def test_fork_preserves_step_dag_edges(self, client, db_session):
        from app.models.workflow import Workflow, WorkflowStep

        ctx = _make_ctx(vertical="manufacturing")
        # Build a 2-step chain specifically so we can verify
        # next_step_id remap lands on the fork's new step ids.
        src_id = _make_workflow(
            db_session,
            scope="core",
            vertical=None,
            tier=1,
            name="Chain test",
        )
        r = client.post(
            f"/api/v1/workflows/{src_id}/fork",
            json={},
            headers=ctx["headers"],
        )
        assert r.status_code == 200
        fork_id = r.json()["id"]

        fork_steps = (
            db_session.query(WorkflowStep)
            .filter(WorkflowStep.workflow_id == fork_id)
            .order_by(WorkflowStep.step_order.asc())
            .all()
        )
        assert len(fork_steps) == 2
        # First step's next_step_id should point at the fork's second
        # step (NOT the source's second step).
        assert fork_steps[0].next_step_id == fork_steps[1].id

    def test_fork_cannot_fork_tenant_scoped_source(self, client, db_session):
        ctx = _make_ctx()
        src = _make_workflow(
            db_session,
            scope="tenant",
            vertical=None,
            company_id=ctx["company_id"],
            tier=4,
            name="TenantOwned",
        )
        r = client.post(
            f"/api/v1/workflows/{src}/fork",
            json={},
            headers=ctx["headers"],
        )
        assert r.status_code == 403  # ForkNotAllowed
        assert "only core and vertical" in r.text.lower()

    def test_fork_blocks_cross_vertical(self, client, db_session):
        # FH tenant trying to fork a manufacturing-vertical workflow
        fh_ctx = _make_ctx(vertical="funeral_home")
        src = _make_workflow(
            db_session,
            scope="vertical",
            vertical="manufacturing",
            tier=2,
            name="MfgOnly",
        )
        r = client.post(
            f"/api/v1/workflows/{src}/fork",
            json={},
            headers=fh_ctx["headers"],
        )
        assert r.status_code == 403

    def test_fork_blocks_double_fork(self, client, db_session):
        ctx = _make_ctx(vertical="manufacturing")
        src = _make_workflow(
            db_session,
            scope="core",
            vertical=None,
            tier=1,
            name="SrcForDouble",
        )
        r1 = client.post(
            f"/api/v1/workflows/{src}/fork",
            json={},
            headers=ctx["headers"],
        )
        assert r1.status_code == 200
        r2 = client.post(
            f"/api/v1/workflows/{src}/fork",
            json={},
            headers=ctx["headers"],
        )
        assert r2.status_code == 409  # AlreadyForked

    def test_fork_not_found(self, client):
        ctx = _make_ctx()
        r = client.post(
            "/api/v1/workflows/does-not-exist/fork",
            json={},
            headers=ctx["headers"],
        )
        assert r.status_code == 404


class TestCountTenantsUsingWorkflow:
    def test_counts_only_active_enrollments(self, db_session):
        from app.models.workflow import WorkflowEnrollment
        from app.services.workflow_fork import (
            count_tenants_using_workflow,
        )

        src = _make_workflow(
            db_session,
            scope="core",
            vertical=None,
            tier=1,
            name="CountTest",
        )
        # 3 real tenants so the FK constraint satisfies.
        tenants = [_make_ctx()["company_id"] for _ in range(3)]
        for i, is_active in enumerate((True, True, False)):
            db_session.add(
                WorkflowEnrollment(
                    id=str(uuid.uuid4()),
                    workflow_id=src,
                    company_id=tenants[i],
                    is_active=is_active,
                )
            )
        db_session.commit()

        assert count_tenants_using_workflow(db_session, workflow_id=src) == 2
