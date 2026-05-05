"""Phase 4 of the Admin Visual Editor — workflow_templates +
tenant_workflow_forks tests.

Mirrors test_platform_themes_phase2.py + test_component_configurations_phase3.py
shape: service-layer validation, versioning, inheritance,
fork lifecycle (create, accept-merge, reject-merge), API admin
gating, full Claude API E2E lifecycle dance.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


# ─── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _make_tenant_with_admin(vertical: str = "funeral_home"):
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
            name=f"Wf {suffix}",
            slug=f"wf-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()

        admin_role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(admin_role)
        db.flush()

        admin = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"admin-{suffix}@wf.test",
            hashed_password="x",
            first_name="Wf",
            last_name="Admin",
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(admin)

        non_admin_role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Office",
            slug="office",
            is_system=False,
        )
        db.add(non_admin_role)
        db.flush()

        non_admin = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"office-{suffix}@wf.test",
            hashed_password="x",
            first_name="Wf",
            last_name="Office",
            role_id=non_admin_role.id,
            is_active=True,
        )
        db.add(non_admin)
        db.commit()

        admin_token = create_access_token(
            {"sub": admin.id, "company_id": co.id}, realm="tenant"
        )
        non_admin_token = create_access_token(
            {"sub": non_admin.id, "company_id": co.id}, realm="tenant"
        )

        # Platform admin user for visual editor endpoints (relocation phase).
        from app.models.platform_user import PlatformUser
        platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="Platform",
            last_name="Admin",
            role="super_admin",
            is_active=True,
        )
        db.add(platform_admin)
        db.commit()
        platform_token = create_access_token(
            {"sub": platform_admin.id},
            realm="platform",
        )

        return {
            "company_id": co.id,
            "slug": co.slug,
            "admin_token": admin_token,
            "non_admin_token": non_admin_token,
            "platform_id": platform_admin.id,
            "platform_token": platform_token,
            "vertical": vertical,
        }
    finally:
        db.close()


def _admin_headers(ctx: dict) -> dict:
    """Return platform-admin auth headers.

    Visual Editor endpoints are gated by PlatformUser auth (realm=platform)
    after the relocation phase (May 2026). The ctx fixture seeds both a
    PlatformUser + tenant for tests that exercise tenant_override scope.
    """
    return {"Authorization": f"Bearer {ctx['platform_token']}"}


def _non_admin_headers(ctx: dict) -> dict:
    """Return tenant-admin auth headers — used to verify cross-realm
    rejection (tenant token at platform endpoint = 401)."""
    return {
        "Authorization": f"Bearer {ctx['admin_token']}",
        "X-Company-Slug": ctx['slug'],
    }


def _cleanup():
    from app.database import SessionLocal
    from app.models.workflow_template import (
        TenantWorkflowFork,
        WorkflowTemplate,
    )

    db = SessionLocal()
    try:
        db.query(TenantWorkflowFork).delete()
        db.query(WorkflowTemplate).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_each():
    _cleanup()
    yield
    _cleanup()


# ─── Canvas helpers ──────────────────────────────────────────────


def _minimal_canvas(label: str = "v1") -> dict:
    return {
        "version": 1,
        "trigger": {"trigger_type": "manual", "trigger_config": {}},
        "nodes": [
            {
                "id": "n_start",
                "type": "start",
                "label": label,
                "position": {"x": 0, "y": 0},
                "config": {},
            },
            {
                "id": "n_end",
                "type": "end",
                "label": "end",
                "position": {"x": 0, "y": 100},
                "config": {},
            },
        ],
        "edges": [
            {"id": "e_start", "source": "n_start", "target": "n_end"},
        ],
    }


# ─── Validator tests ────────────────────────────────────────────


class TestCanvasValidator:
    def test_empty_dict_is_valid(self):
        from app.services.workflow_templates import validate_canvas_state

        validate_canvas_state({})  # no raise

    def test_missing_required_keys_rejected(self):
        from app.services.workflow_templates import (
            CanvasValidationError,
            validate_canvas_state,
        )

        with pytest.raises(CanvasValidationError):
            validate_canvas_state({"version": 1})

    def test_unknown_node_type_rejected(self):
        from app.services.workflow_templates import (
            CanvasValidationError,
            validate_canvas_state,
        )

        bad = _minimal_canvas()
        bad["nodes"][0]["type"] = "not-a-real-type"
        with pytest.raises(CanvasValidationError):
            validate_canvas_state(bad)

    def test_dangling_edge_rejected(self):
        from app.services.workflow_templates import (
            CanvasValidationError,
            validate_canvas_state,
        )

        bad = _minimal_canvas()
        bad["edges"][0]["target"] = "n_does_not_exist"
        with pytest.raises(CanvasValidationError):
            validate_canvas_state(bad)

    def test_duplicate_node_id_rejected(self):
        from app.services.workflow_templates import (
            CanvasValidationError,
            validate_canvas_state,
        )

        bad = _minimal_canvas()
        bad["nodes"].append(dict(bad["nodes"][0]))
        with pytest.raises(CanvasValidationError):
            validate_canvas_state(bad)

    def test_cycle_rejected(self):
        from app.services.workflow_templates import (
            CanvasValidationError,
            validate_canvas_state,
        )

        bad = _minimal_canvas()
        # Add an edge from n_end back to n_start (creates a cycle)
        bad["edges"].append(
            {"id": "e_cycle", "source": "n_end", "target": "n_start"}
        )
        with pytest.raises(CanvasValidationError):
            validate_canvas_state(bad)

    def test_iteration_edge_doesnt_trip_cycle_check(self):
        from app.services.workflow_templates import validate_canvas_state

        canvas = _minimal_canvas()
        canvas["edges"].append(
            {
                "id": "e_iter",
                "source": "n_end",
                "target": "n_start",
                "is_iteration": True,
            }
        )
        validate_canvas_state(canvas)  # no raise

    def test_seeded_funeral_cascade_validates(self):
        from app.services.workflow_templates import validate_canvas_state
        from scripts.seed_workflow_templates_phase4 import funeral_cascade_canvas

        validate_canvas_state(funeral_cascade_canvas())

    def test_seeded_quote_to_pour_validates(self):
        from app.services.workflow_templates import validate_canvas_state
        from scripts.seed_workflow_templates_phase4 import quote_to_pour_canvas

        validate_canvas_state(quote_to_pour_canvas())


# ─── Service-layer tests ────────────────────────────────────────


class TestServiceValidation:
    def test_platform_default_rejects_vertical(self, db_session):
        from app.services.workflow_templates import (
            TemplateScopeMismatch,
            create_template,
        )

        with pytest.raises(TemplateScopeMismatch):
            create_template(
                db_session,
                scope="platform_default",
                vertical="funeral_home",
                workflow_type="test_workflow",
                display_name="Test",
                canvas_state={},
            )

    def test_vertical_default_requires_vertical(self, db_session):
        from app.services.workflow_templates import (
            TemplateScopeMismatch,
            create_template,
        )

        with pytest.raises(TemplateScopeMismatch):
            create_template(
                db_session,
                scope="vertical_default",
                vertical=None,
                workflow_type="test_workflow",
                display_name="Test",
                canvas_state={},
            )

    def test_invalid_canvas_rejected_at_create(self, db_session):
        from app.services.workflow_templates import (
            CanvasValidationError,
            create_template,
        )

        bad = _minimal_canvas()
        bad["edges"][0]["target"] = "n_missing"

        with pytest.raises(CanvasValidationError):
            create_template(
                db_session,
                scope="platform_default",
                workflow_type="test",
                display_name="Test",
                canvas_state=bad,
            )


class TestVersioning:
    def test_create_at_existing_tuple_versions(self, db_session):
        from app.services.workflow_templates import create_template

        first = create_template(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            workflow_type="test_workflow",
            display_name="Test v1",
            canvas_state=_minimal_canvas("v1"),
        )
        assert first.version == 1
        assert first.is_active is True

        second = create_template(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            workflow_type="test_workflow",
            display_name="Test v2",
            canvas_state=_minimal_canvas("v2"),
        )
        assert second.version == 2
        assert second.is_active is True
        db_session.refresh(first)
        assert first.is_active is False

    def test_update_versions(self, db_session):
        from app.services.workflow_templates import (
            create_template,
            update_template,
        )

        first = create_template(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            workflow_type="test_workflow",
            display_name="Test",
            canvas_state=_minimal_canvas("v1"),
        )
        new_row = update_template(
            db_session,
            first.id,
            display_name="Test renamed",
            canvas_state=_minimal_canvas("v2"),
        )
        assert new_row.version == 2
        assert new_row.is_active is True
        assert new_row.display_name == "Test renamed"
        db_session.refresh(first)
        assert first.is_active is False


class TestInheritance:
    def test_resolve_returns_platform_default_when_no_vertical(self, db_session):
        from app.services.workflow_templates import (
            create_template,
            resolve_workflow,
        )

        create_template(
            db_session,
            scope="platform_default",
            workflow_type="test",
            display_name="Platform",
            canvas_state=_minimal_canvas("platform"),
        )
        result = resolve_workflow(db_session, workflow_type="test")
        assert result["source"] == "platform_default"
        assert result["canvas_state"]["nodes"][0]["label"] == "platform"

    def test_resolve_prefers_vertical_default_over_platform(self, db_session):
        from app.services.workflow_templates import (
            create_template,
            resolve_workflow,
        )

        create_template(
            db_session,
            scope="platform_default",
            workflow_type="test",
            display_name="Platform",
            canvas_state=_minimal_canvas("platform"),
        )
        create_template(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            workflow_type="test",
            display_name="FH",
            canvas_state=_minimal_canvas("fh"),
        )
        result = resolve_workflow(
            db_session, workflow_type="test", vertical="funeral_home"
        )
        assert result["source"] == "vertical_default"
        assert result["canvas_state"]["nodes"][0]["label"] == "fh"

        # Manufacturing has no vertical default → platform fallback
        mfg = resolve_workflow(
            db_session, workflow_type="test", vertical="manufacturing"
        )
        assert mfg["source"] == "platform_default"

    def test_resolve_prefers_tenant_fork_over_vertical_default(self, db_session):
        from app.services.workflow_templates import (
            create_template,
            fork_for_tenant,
            resolve_workflow,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            v_template = create_template(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                workflow_type="test",
                display_name="FH",
                canvas_state=_minimal_canvas("fh-default"),
            )
            fork_for_tenant(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
                source_template_id=v_template.id,
            )
            # Modify the fork to confirm it's distinct from the
            # template's canvas_state
            from app.models.workflow_template import TenantWorkflowFork

            fork = (
                db_session.query(TenantWorkflowFork)
                .filter(
                    TenantWorkflowFork.tenant_id == ctx["company_id"],
                    TenantWorkflowFork.is_active.is_(True),
                )
                .first()
            )
            fork.canvas_state = _minimal_canvas("tenant-customized")
            db_session.commit()

            result = resolve_workflow(
                db_session,
                workflow_type="test",
                vertical="funeral_home",
                tenant_id=ctx["company_id"],
            )
            assert result["source"] == "tenant_fork"
            assert (
                result["canvas_state"]["nodes"][0]["label"]
                == "tenant-customized"
            )
        finally:
            _cleanup()

    def test_resolve_returns_empty_when_no_template_authored(self, db_session):
        from app.services.workflow_templates import resolve_workflow

        result = resolve_workflow(db_session, workflow_type="nonexistent")
        assert result["source"] is None
        assert result["canvas_state"] == {}


# ─── Fork lifecycle tests ───────────────────────────────────────


class TestForkLifecycle:
    def test_fork_creates_record_with_correct_version(self, db_session):
        from app.services.workflow_templates import (
            create_template,
            fork_for_tenant,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            template = create_template(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                workflow_type="test",
                display_name="FH",
                canvas_state=_minimal_canvas("fh-v1"),
            )
            fork = fork_for_tenant(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
                source_template_id=template.id,
            )
            assert fork.forked_from_template_id == template.id
            assert fork.forked_from_version == 1
            assert fork.canvas_state == template.canvas_state
            assert fork.pending_merge_available is False
            assert fork.is_active is True
        finally:
            _cleanup()

    def test_duplicate_fork_rejected(self, db_session):
        from app.services.workflow_templates import (
            WorkflowTemplateError,
            create_template,
            fork_for_tenant,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            template = create_template(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                workflow_type="test",
                display_name="FH",
                canvas_state=_minimal_canvas("v1"),
            )
            fork_for_tenant(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
                source_template_id=template.id,
            )
            with pytest.raises(WorkflowTemplateError):
                fork_for_tenant(
                    db_session,
                    tenant_id=ctx["company_id"],
                    workflow_type="test",
                    source_template_id=template.id,
                )
        finally:
            _cleanup()

    def test_updating_vertical_default_flags_pending_merge(self, db_session):
        from app.services.workflow_templates import (
            create_template,
            fork_for_tenant,
            update_template,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            v1 = create_template(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                workflow_type="test",
                display_name="FH v1",
                canvas_state=_minimal_canvas("v1"),
            )
            fork = fork_for_tenant(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
                source_template_id=v1.id,
            )
            assert fork.pending_merge_available is False

            # Update the vertical default — should flag the fork
            update_template(
                db_session,
                v1.id,
                canvas_state=_minimal_canvas("v2-new"),
                notify_forks=True,
            )

            db_session.refresh(fork)
            assert fork.pending_merge_available is True
            assert fork.pending_merge_template_id is not None
            # canvas_state on the fork is untouched
            assert (
                fork.canvas_state["nodes"][0]["label"] == "v1"
            )
        finally:
            _cleanup()

    def test_locked_to_fork_resolution(self, db_session):
        """Updating the vertical default does NOT change what
        the fork's resolved canvas_state returns."""
        from app.services.workflow_templates import (
            create_template,
            fork_for_tenant,
            resolve_workflow,
            update_template,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            v1 = create_template(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                workflow_type="test",
                display_name="FH v1",
                canvas_state=_minimal_canvas("v1"),
            )
            fork_for_tenant(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
                source_template_id=v1.id,
            )

            # Update the vertical default
            update_template(
                db_session,
                v1.id,
                canvas_state=_minimal_canvas("v2-new"),
                notify_forks=True,
            )

            # Fork's canvas_state stays at v1 — locked-to-fork
            result = resolve_workflow(
                db_session,
                workflow_type="test",
                vertical="funeral_home",
                tenant_id=ctx["company_id"],
            )
            assert result["source"] == "tenant_fork"
            assert result["canvas_state"]["nodes"][0]["label"] == "v1"
            assert result["pending_merge_available"] is True
        finally:
            _cleanup()

    def test_accept_merge_replaces_canvas_state(self, db_session):
        from app.services.workflow_templates import (
            accept_merge,
            create_template,
            fork_for_tenant,
            update_template,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            v1 = create_template(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                workflow_type="test",
                display_name="FH",
                canvas_state=_minimal_canvas("v1"),
            )
            fork = fork_for_tenant(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
                source_template_id=v1.id,
            )
            initial_fork_version = fork.version

            update_template(
                db_session,
                v1.id,
                canvas_state=_minimal_canvas("v2-new"),
                notify_forks=True,
            )

            # Accept the merge
            updated_fork = accept_merge(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
            )
            assert (
                updated_fork.canvas_state["nodes"][0]["label"] == "v2-new"
            )
            assert updated_fork.pending_merge_available is False
            assert updated_fork.pending_merge_template_id is None
            assert updated_fork.forked_from_version == 2
            assert updated_fork.version == initial_fork_version + 1
        finally:
            _cleanup()

    def test_reject_merge_preserves_canvas_state(self, db_session):
        from app.services.workflow_templates import (
            create_template,
            fork_for_tenant,
            reject_merge,
            update_template,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            v1 = create_template(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                workflow_type="test",
                display_name="FH",
                canvas_state=_minimal_canvas("v1"),
            )
            fork = fork_for_tenant(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
                source_template_id=v1.id,
            )

            # Tenant customizes their fork
            from app.models.workflow_template import TenantWorkflowFork

            fork_in_db = (
                db_session.query(TenantWorkflowFork)
                .filter(TenantWorkflowFork.id == fork.id)
                .first()
            )
            fork_in_db.canvas_state = _minimal_canvas("tenant-custom")
            db_session.commit()

            update_template(
                db_session,
                v1.id,
                canvas_state=_minimal_canvas("v2-new"),
                notify_forks=True,
            )

            updated_fork = reject_merge(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
            )
            # canvas_state preserved
            assert (
                updated_fork.canvas_state["nodes"][0]["label"]
                == "tenant-custom"
            )
            assert updated_fork.pending_merge_available is False
            assert updated_fork.pending_merge_template_id is None
            # forked_from_version updated to acknowledged version
            assert updated_fork.forked_from_version == 2
        finally:
            _cleanup()

    def test_dependent_forks_lookup(self, db_session):
        from app.services.workflow_templates import (
            create_template,
            fork_for_tenant,
            get_dependent_forks,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            template = create_template(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                workflow_type="test",
                display_name="FH",
                canvas_state=_minimal_canvas("v1"),
            )
            fork_for_tenant(
                db_session,
                tenant_id=ctx["company_id"],
                workflow_type="test",
                source_template_id=template.id,
            )

            forks = get_dependent_forks(db_session, template.id)
            assert len(forks) == 1
            assert forks[0].tenant_id == ctx["company_id"]
        finally:
            _cleanup()


# ─── API tests ──────────────────────────────────────────────────


class TestAdminGating:
    def test_anonymous_rejected(self, client):
        resp = client.get("/api/platform/admin/visual-editor/workflows/")
        assert resp.status_code in (401, 403)

    def test_tenant_token_rejected(self, client):
        """Tenant tokens cannot reach platform endpoints (realm mismatch → 401)."""
        ctx = _make_tenant_with_admin()
        resp = client.get(
            "/api/platform/admin/visual-editor/workflows/",
            headers=_non_admin_headers(ctx),
        )
        assert resp.status_code == 401


class TestApiCrud:
    def test_create_then_list(self, client):
        ctx = _make_tenant_with_admin()
        create_resp = client.post(
            "/api/platform/admin/visual-editor/workflows/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "workflow_type": "test",
                "display_name": "Test",
                "description": "Test workflow",
                "canvas_state": _minimal_canvas("v1"),
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        body = create_resp.json()
        assert body["workflow_type"] == "test"
        assert body["version"] == 1
        # canvas_state present on full response
        assert "nodes" in body["canvas_state"]

        list_resp = client.get(
            "/api/platform/admin/visual-editor/workflows/?vertical=funeral_home",
            headers=_admin_headers(ctx),
        )
        assert list_resp.status_code == 200
        rows = list_resp.json()
        assert len(rows) == 1
        # List response shape — metadata only, no canvas_state
        assert "canvas_state" not in rows[0]

    def test_create_invalid_canvas_returns_400(self, client):
        ctx = _make_tenant_with_admin()
        bad_canvas = _minimal_canvas()
        bad_canvas["edges"][0]["target"] = "n_does_not_exist"
        resp = client.post(
            "/api/platform/admin/visual-editor/workflows/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "workflow_type": "test",
                "display_name": "Test",
                "canvas_state": bad_canvas,
            },
        )
        assert resp.status_code == 400

    def test_resolve_endpoint(self, client):
        ctx = _make_tenant_with_admin(vertical="funeral_home")
        client.post(
            "/api/platform/admin/visual-editor/workflows/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "workflow_type": "test",
                "display_name": "FH",
                "canvas_state": _minimal_canvas("fh"),
            },
        )
        resp = client.get(
            "/api/platform/admin/visual-editor/workflows/resolve",
            headers=_admin_headers(ctx),
            params={"workflow_type": "test", "vertical": "funeral_home"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["source"] == "vertical_default"
        assert body["canvas_state"]["nodes"][0]["label"] == "fh"


class TestE2EClaudeApiEquivalent:
    def test_full_lifecycle(self, client):
        ctx = _make_tenant_with_admin(vertical="funeral_home")

        # 1. Create vertical default
        v1_resp = client.post(
            "/api/platform/admin/visual-editor/workflows/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "workflow_type": "test_lifecycle",
                "display_name": "FH",
                "canvas_state": _minimal_canvas("v1"),
            },
        )
        v1_id = v1_resp.json()["id"]

        # 2. Fork for tenant
        fork_resp = client.post(
            f"/api/platform/admin/visual-editor/workflows/{v1_id}/fork",
            headers=_admin_headers(ctx),
            json={"tenant_id": ctx["company_id"]},
        )
        assert fork_resp.status_code == 201, fork_resp.text
        fork_id = fork_resp.json()["id"]

        # 3. Resolve for tenant — should return fork's canvas_state
        r1 = client.get(
            "/api/platform/admin/visual-editor/workflows/resolve",
            headers=_admin_headers(ctx),
            params={
                "workflow_type": "test_lifecycle",
                "vertical": "funeral_home",
                "tenant_id": ctx["company_id"],
            },
        ).json()
        assert r1["source"] == "tenant_fork"
        assert r1["canvas_state"]["nodes"][0]["label"] == "v1"
        assert r1["pending_merge_available"] is False

        # 4. Update vertical default (new version) — should flag fork
        client.patch(
            f"/api/platform/admin/visual-editor/workflows/{v1_id}",
            headers=_admin_headers(ctx),
            json={"canvas_state": _minimal_canvas("v2-new")},
        )

        # 5. Resolve again — fork's canvas_state still v1 (locked)
        r2 = client.get(
            "/api/platform/admin/visual-editor/workflows/resolve",
            headers=_admin_headers(ctx),
            params={
                "workflow_type": "test_lifecycle",
                "vertical": "funeral_home",
                "tenant_id": ctx["company_id"],
            },
        ).json()
        assert r2["source"] == "tenant_fork"
        assert r2["canvas_state"]["nodes"][0]["label"] == "v1"
        assert r2["pending_merge_available"] is True

        # 6. Accept merge programmatically
        accept_resp = client.post(
            f"/api/platform/admin/visual-editor/workflows/forks/{fork_id}/accept-merge",
            headers=_admin_headers(ctx),
        )
        assert accept_resp.status_code == 200, accept_resp.text

        # 7. Resolve again — fork now has v2-new
        r3 = client.get(
            "/api/platform/admin/visual-editor/workflows/resolve",
            headers=_admin_headers(ctx),
            params={
                "workflow_type": "test_lifecycle",
                "vertical": "funeral_home",
                "tenant_id": ctx["company_id"],
            },
        ).json()
        assert r3["canvas_state"]["nodes"][0]["label"] == "v2-new"
        assert r3["pending_merge_available"] is False

        # 8. Verify fork's forked_from_version updated
        fork_resp_2 = client.get(
            "/api/platform/admin/visual-editor/workflows/forks/",
            headers=_admin_headers(ctx),
            params={"tenant_id": ctx["company_id"]},
        )
        forks = fork_resp_2.json()
        assert len(forks) == 1
        assert forks[0]["forked_from_version"] == 2


# ─── Backfill verification ──────────────────────────────────────


class TestBackfill:
    def test_seed_script_creates_funeral_cascade(self, db_session):
        # Re-run seed against a clean DB; verify both templates land.
        # The autouse cleanup fixture has already wiped state.
        from scripts.seed_workflow_templates_phase4 import main

        rc = main()
        assert rc == 0

        from app.models.workflow_template import WorkflowTemplate

        funeral = (
            db_session.query(WorkflowTemplate)
            .filter(
                WorkflowTemplate.workflow_type == "funeral_cascade",
                WorkflowTemplate.is_active.is_(True),
            )
            .first()
        )
        assert funeral is not None
        assert funeral.scope == "vertical_default"
        assert funeral.vertical == "funeral_home"
        # Funeral cascade is substantive — at least 15 nodes
        assert len(funeral.canvas_state["nodes"]) >= 15

    def test_seed_script_creates_quote_to_pour(self, db_session):
        from scripts.seed_workflow_templates_phase4 import main

        main()
        from app.models.workflow_template import WorkflowTemplate

        q2p = (
            db_session.query(WorkflowTemplate)
            .filter(
                WorkflowTemplate.workflow_type == "quote_to_pour",
                WorkflowTemplate.is_active.is_(True),
            )
            .first()
        )
        assert q2p is not None
        assert q2p.scope == "vertical_default"
        assert q2p.vertical == "manufacturing"
        assert len(q2p.canvas_state["nodes"]) >= 15
