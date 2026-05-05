"""Phase 3 of the Admin Visual Editor — component_configurations
tests.

Mirrors test_platform_themes_phase2.py structure: service-layer
validation, versioning, mode/scope independence, inheritance,
edge cases, admin gating, registry-validation rejection of bad
overrides, orphaned-key behavior, full E2E lifecycle.
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


def _make_tenant_with_admin(vertical: str = "manufacturing"):
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
            name=f"CompConfig {suffix}",
            slug=f"cfg-{suffix}",
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
            email=f"admin-{suffix}@cfg.test",
            hashed_password="x",
            first_name="Cfg",
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
            email=f"office-{suffix}@cfg.test",
            hashed_password="x",
            first_name="Cfg",
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
    from app.models.component_configuration import ComponentConfiguration

    db = SessionLocal()
    try:
        db.query(ComponentConfiguration).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_each():
    _cleanup()
    yield
    _cleanup()


# ─── Service-layer tests ──────────────────────────────────────


class TestServiceValidation:
    def test_unknown_component_rejected(self, db_session):
        from app.services.component_config import (
            UnknownComponent,
            create_configuration,
        )

        with pytest.raises(UnknownComponent):
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="widget",
                component_name="nonexistent-widget",
                prop_overrides={},
            )

    def test_unknown_prop_rejected(self, db_session):
        from app.services.component_config import (
            PropValidationError,
            create_configuration,
        )

        with pytest.raises(PropValidationError):
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="widget",
                component_name="today",
                prop_overrides={"unknownProp": "x"},
            )

    def test_out_of_bounds_number_rejected(self, db_session):
        from app.services.component_config import (
            PropValidationError,
            create_configuration,
        )

        with pytest.raises(PropValidationError):
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="widget",
                component_name="today",
                # refreshIntervalSeconds bounds [60, 3600]
                prop_overrides={"refreshIntervalSeconds": 5},
            )

    def test_invalid_enum_value_rejected(self, db_session):
        from app.services.component_config import (
            PropValidationError,
            create_configuration,
        )

        with pytest.raises(PropValidationError):
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="widget",
                component_name="today",
                prop_overrides={"dateFormatStyle": "not-a-style"},
            )

    def test_string_max_length_rejected(self, db_session):
        from app.services.component_config import (
            PropValidationError,
            create_configuration,
        )

        with pytest.raises(PropValidationError):
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="document-block",
                component_name="header-block",
                # title bounds maxLength 120
                prop_overrides={"title": "x" * 200},
            )

    def test_wrong_type_rejected(self, db_session):
        from app.services.component_config import (
            PropValidationError,
            create_configuration,
        )

        with pytest.raises(PropValidationError):
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="widget",
                component_name="today",
                prop_overrides={"showRowBreakdown": "yes"},  # should be bool
            )

    def test_scope_keys_validation(self, db_session):
        from app.services.component_config import (
            ConfigScopeMismatch,
            create_configuration,
        )

        with pytest.raises(ConfigScopeMismatch):
            create_configuration(
                db_session,
                scope="vertical_default",
                # missing vertical
                component_kind="widget",
                component_name="today",
                prop_overrides={"showRowBreakdown": True},
            )

    def test_invalid_kind_rejected(self, db_session):
        from app.services.component_config import (
            InvalidConfigShape,
            create_configuration,
        )

        with pytest.raises(InvalidConfigShape):
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="not-a-kind",  # type: ignore[arg-type]
                component_name="today",
                prop_overrides={},
            )


class TestVersioning:
    def test_create_at_existing_tuple_versions(self, db_session):
        from app.services.component_config import create_configuration

        first = create_configuration(
            db_session,
            scope="platform_default",
            component_kind="widget",
            component_name="today",
            prop_overrides={"showRowBreakdown": True},
        )
        assert first.version == 1
        assert first.is_active is True

        second = create_configuration(
            db_session,
            scope="platform_default",
            component_kind="widget",
            component_name="today",
            prop_overrides={"showRowBreakdown": False},
        )
        assert second.version == 2
        assert second.is_active is True

        db_session.refresh(first)
        assert first.is_active is False

    def test_update_versions(self, db_session):
        from app.services.component_config import (
            create_configuration,
            update_configuration,
        )

        first = create_configuration(
            db_session,
            scope="platform_default",
            component_kind="widget",
            component_name="today",
            prop_overrides={"refreshIntervalSeconds": 300},
        )
        new_row = update_configuration(
            db_session,
            first.id,
            prop_overrides={"refreshIntervalSeconds": 600},
        )
        assert new_row.version == 2
        assert new_row.is_active is True
        db_session.refresh(first)
        assert first.is_active is False


class TestInheritance:
    def test_platform_only(self, db_session):
        from app.services.component_config import (
            create_configuration,
            resolve_configuration,
        )

        create_configuration(
            db_session,
            scope="platform_default",
            component_kind="widget",
            component_name="today",
            prop_overrides={"showRowBreakdown": True, "maxCategoriesShown": 5},
        )
        result = resolve_configuration(
            db_session,
            component_kind="widget",
            component_name="today",
        )
        assert result["props"]["showRowBreakdown"] is True
        assert result["props"]["maxCategoriesShown"] == 5
        assert len(result["sources"]) == 1
        assert result["sources"][0]["scope"] == "platform_default"

    def test_vertical_overrides_platform(self, db_session):
        from app.services.component_config import (
            create_configuration,
            resolve_configuration,
        )

        create_configuration(
            db_session,
            scope="platform_default",
            component_kind="widget",
            component_name="today",
            prop_overrides={"maxCategoriesShown": 5, "showRowBreakdown": True},
        )
        create_configuration(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            component_kind="widget",
            component_name="today",
            prop_overrides={"maxCategoriesShown": 8},
        )

        fh = resolve_configuration(
            db_session,
            component_kind="widget",
            component_name="today",
            vertical="funeral_home",
        )
        # Vertical overrides max; platform contributes show flag
        assert fh["props"]["maxCategoriesShown"] == 8
        assert fh["props"]["showRowBreakdown"] is True
        assert len(fh["sources"]) == 2

        # Manufacturing has no override → platform default only
        mfg = resolve_configuration(
            db_session,
            component_kind="widget",
            component_name="today",
            vertical="manufacturing",
        )
        assert mfg["props"]["maxCategoriesShown"] == 5

    def test_tenant_overrides_everything(self, db_session):
        from app.services.component_config import (
            create_configuration,
            resolve_configuration,
        )

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="widget",
                component_name="today",
                prop_overrides={"maxCategoriesShown": 5},
            )
            create_configuration(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                component_kind="widget",
                component_name="today",
                prop_overrides={"maxCategoriesShown": 8},
            )
            create_configuration(
                db_session,
                scope="tenant_override",
                tenant_id=ctx["company_id"],
                component_kind="widget",
                component_name="today",
                prop_overrides={"maxCategoriesShown": 12},
            )

            result = resolve_configuration(
                db_session,
                component_kind="widget",
                component_name="today",
                vertical="funeral_home",
                tenant_id=ctx["company_id"],
            )
            assert result["props"]["maxCategoriesShown"] == 12
            assert len(result["sources"]) == 3
        finally:
            _cleanup()

    def test_tenant_override_without_vertical_default_falls_back_to_platform(
        self, db_session
    ):
        from app.services.component_config import (
            create_configuration,
            resolve_configuration,
        )

        ctx = _make_tenant_with_admin(vertical="cemetery")
        try:
            create_configuration(
                db_session,
                scope="platform_default",
                component_kind="widget",
                component_name="today",
                prop_overrides={"maxCategoriesShown": 5, "showRowBreakdown": True},
            )
            create_configuration(
                db_session,
                scope="tenant_override",
                tenant_id=ctx["company_id"],
                component_kind="widget",
                component_name="today",
                prop_overrides={"showTotalCount": False},
            )

            result = resolve_configuration(
                db_session,
                component_kind="widget",
                component_name="today",
                vertical="cemetery",
                tenant_id=ctx["company_id"],
            )
            # Platform layer contributes maxCategoriesShown + showRowBreakdown;
            # tenant layer contributes showTotalCount; no vertical layer.
            assert result["props"]["maxCategoriesShown"] == 5
            assert result["props"]["showRowBreakdown"] is True
            assert result["props"]["showTotalCount"] is False
            scopes = [s["scope"] for s in result["sources"]]
            assert "vertical_default" not in scopes
        finally:
            _cleanup()

    def test_empty_overrides_falls_through(self, db_session):
        from app.services.component_config import (
            create_configuration,
            resolve_configuration,
        )

        create_configuration(
            db_session,
            scope="platform_default",
            component_kind="widget",
            component_name="today",
            prop_overrides={"maxCategoriesShown": 5},
        )
        # Vertical row exists but is empty
        create_configuration(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            component_kind="widget",
            component_name="today",
            prop_overrides={},
        )

        result = resolve_configuration(
            db_session,
            component_kind="widget",
            component_name="today",
            vertical="funeral_home",
        )
        # Empty vertical override → fall through to platform
        assert result["props"]["maxCategoriesShown"] == 5

    def test_orphaned_keys_surfaced_in_resolve(self, db_session):
        """An override row with a key the registry no longer
        recognizes is silently dropped from props but reported in
        orphaned_keys for admin cleanup."""
        from app.models.component_configuration import ComponentConfiguration
        from app.services.component_config import resolve_configuration

        # Insert directly with raw SQL so we bypass the strict
        # validation at the create boundary — simulating a
        # previously-valid override that was orphaned by a
        # registry change.
        row = ComponentConfiguration(
            scope="platform_default",
            vertical=None,
            tenant_id=None,
            component_kind="widget",
            component_name="today",
            prop_overrides={
                "maxCategoriesShown": 5,
                "deprecatedProp": "xyz",
            },
            version=1,
            is_active=True,
        )
        db_session.add(row)
        db_session.commit()

        result = resolve_configuration(
            db_session,
            component_kind="widget",
            component_name="today",
        )
        assert result["props"]["maxCategoriesShown"] == 5
        assert "deprecatedProp" not in result["props"]
        assert "deprecatedProp" in result["orphaned_keys"]


# ─── API tests ────────────────────────────────────────────────


class TestAdminGating:
    def test_anonymous_rejected(self, client):
        resp = client.get("/api/platform/admin/visual-editor/components/")
        assert resp.status_code in (401, 403)

    def test_tenant_token_rejected(self, client):
        """Tenant tokens cannot reach platform endpoints (realm mismatch → 401)."""
        ctx = _make_tenant_with_admin()
        resp = client.get(
            "/api/platform/admin/visual-editor/components/",
            headers=_non_admin_headers(ctx),
        )
        assert resp.status_code == 401


class TestRegistryEndpoint:
    def test_returns_all_components(self, client):
        ctx = _make_tenant_with_admin()
        resp = client.get(
            "/api/platform/admin/visual-editor/components/registry",
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "components" in body
        # Phase 1 ships 17 components; Phase 3 backfill leaves the
        # count at 17 (no new registrations, just expanded props).
        assert len(body["components"]) == 17


class TestApiCrud:
    def test_create_then_list(self, client):
        ctx = _make_tenant_with_admin()
        create_resp = client.post(
            "/api/platform/admin/visual-editor/components/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "component_kind": "widget",
                "component_name": "today",
                "prop_overrides": {"showRowBreakdown": False},
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        body = create_resp.json()
        assert body["component_kind"] == "widget"
        assert body["component_name"] == "today"
        assert body["version"] == 1

        list_resp = client.get(
            "/api/platform/admin/visual-editor/components/?scope=platform_default",
            headers=_admin_headers(ctx),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    def test_create_invalid_prop_returns_400(self, client):
        ctx = _make_tenant_with_admin()
        resp = client.post(
            "/api/platform/admin/visual-editor/components/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "component_kind": "widget",
                "component_name": "today",
                "prop_overrides": {"refreshIntervalSeconds": 1},  # below min 60
            },
        )
        assert resp.status_code == 400

    def test_resolve_endpoint_walks_inheritance(self, client):
        ctx = _make_tenant_with_admin(vertical="funeral_home")
        client.post(
            "/api/platform/admin/visual-editor/components/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "component_kind": "widget",
                "component_name": "today",
                "prop_overrides": {"maxCategoriesShown": 5},
            },
        )
        client.post(
            "/api/platform/admin/visual-editor/components/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "component_kind": "widget",
                "component_name": "today",
                "prop_overrides": {"maxCategoriesShown": 8},
            },
        )
        resolve_resp = client.get(
            "/api/platform/admin/visual-editor/components/resolve",
            headers=_admin_headers(ctx),
            params={
                "component_kind": "widget",
                "component_name": "today",
                "vertical": "funeral_home",
            },
        )
        assert resolve_resp.status_code == 200, resolve_resp.text
        body = resolve_resp.json()
        assert body["props"]["maxCategoriesShown"] == 8
        assert len(body["sources"]) == 2

    def test_patch_versions(self, client):
        ctx = _make_tenant_with_admin()
        create_resp = client.post(
            "/api/platform/admin/visual-editor/components/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "component_kind": "widget",
                "component_name": "today",
                "prop_overrides": {"showRowBreakdown": True},
            },
        )
        first_id = create_resp.json()["id"]

        patch_resp = client.patch(
            f"/api/platform/admin/visual-editor/components/{first_id}",
            headers=_admin_headers(ctx),
            json={"prop_overrides": {"showRowBreakdown": False}},
        )
        assert patch_resp.status_code == 200
        new_body = patch_resp.json()
        assert new_body["version"] == 2
        assert new_body["id"] != first_id


class TestE2EClaudeApiEquivalent:
    def test_full_lifecycle(self, client):
        ctx = _make_tenant_with_admin(vertical="funeral_home")

        # Platform default
        client.post(
            "/api/platform/admin/visual-editor/components/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "component_kind": "widget",
                "component_name": "today",
                "prop_overrides": {"maxCategoriesShown": 5},
            },
        )
        # Vertical default for funeral_home
        v_resp = client.post(
            "/api/platform/admin/visual-editor/components/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "component_kind": "widget",
                "component_name": "today",
                "prop_overrides": {"maxCategoriesShown": 8},
            },
        )
        vertical_id = v_resp.json()["id"]

        # Resolve for tenant in funeral_home
        r1 = client.get(
            "/api/platform/admin/visual-editor/components/resolve",
            headers=_admin_headers(ctx),
            params={
                "component_kind": "widget",
                "component_name": "today",
                "vertical": "funeral_home",
                "tenant_id": ctx["company_id"],
            },
        ).json()
        assert r1["props"]["maxCategoriesShown"] == 8

        # Update vertical override
        r2_resp = client.patch(
            f"/api/platform/admin/visual-editor/components/{vertical_id}",
            headers=_admin_headers(ctx),
            json={"prop_overrides": {"maxCategoriesShown": 10}},
        )
        assert r2_resp.status_code == 200

        r2 = client.get(
            "/api/platform/admin/visual-editor/components/resolve",
            headers=_admin_headers(ctx),
            params={
                "component_kind": "widget",
                "component_name": "today",
                "vertical": "funeral_home",
            },
        ).json()
        assert r2["props"]["maxCategoriesShown"] == 10

        # Empty overrides on the active vertical row → falls back
        new_active_id = r2_resp.json()["id"]
        client.patch(
            f"/api/platform/admin/visual-editor/components/{new_active_id}",
            headers=_admin_headers(ctx),
            json={"prop_overrides": {}},
        )

        r3 = client.get(
            "/api/platform/admin/visual-editor/components/resolve",
            headers=_admin_headers(ctx),
            params={
                "component_kind": "widget",
                "component_name": "today",
                "vertical": "funeral_home",
            },
        ).json()
        assert r3["props"]["maxCategoriesShown"] == 5
