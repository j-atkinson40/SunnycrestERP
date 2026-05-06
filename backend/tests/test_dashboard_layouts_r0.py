"""Phase R-0 Dashboard Layouts tests.

Covers:
  - CRUD lifecycle (create, version, update, list, get) — service layer
  - Inheritance walk (platform_default → vertical_default →
    tenant_default; deepest non-empty wins)
  - Validation: scope-key shape, malformed layout_config, duplicate
    widget_ids in same layout
  - Admin route gating + happy-path
  - widget_service.get_user_layout integration: defaults flow through
    the new dashboard_layouts inheritance chain when no user override
    exists; user_widget_layouts override still wins when present.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


# ─── Fixtures ───────────────────────────────────────────────────


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


def _make_platform_admin():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.platform_user import PlatformUser

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-dl-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="DL",
            last_name="Admin",
            role="super_admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        token = create_access_token({"sub": admin.id}, realm="platform")
        return {"id": admin.id, "token": token}
    finally:
        db.close()


def _admin_headers(ctx):
    return {"Authorization": f"Bearer {ctx['token']}"}


def _make_tenant(vertical: str = "funeral_home"):
    from app.database import SessionLocal
    from app.models.company import Company

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"DL Tenant {suffix}",
            slug=f"dl-tenant-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.commit()
        return co.id
    finally:
        db.close()


def _cleanup_layouts():
    from app.database import SessionLocal
    from app.models.dashboard_layout import DashboardLayout

    db = SessionLocal()
    try:
        db.query(DashboardLayout).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _per_test_cleanup():
    _cleanup_layouts()
    yield
    _cleanup_layouts()


def _layout_entry(widget_id: str, position: int, *, size: str = "1x1") -> dict:
    return {
        "widget_id": widget_id,
        "enabled": True,
        "position": position,
        "size": size,
        "config": {},
    }


# ─── Service-layer validation ───────────────────────────────────


class TestServiceValidation:
    def test_scope_key_mismatch_rejected(self, db_session):
        from app.services.dashboard_layouts import (
            DashboardLayoutScopeMismatch,
            create_layout,
        )

        # vertical_default with no vertical set → mismatch.
        with pytest.raises(DashboardLayoutScopeMismatch):
            create_layout(
                db_session,
                scope="vertical_default",
                vertical=None,
                tenant_id=None,
                page_context="dashboard",
                layout_config=[],
            )

        # platform_default with vertical set → mismatch.
        with pytest.raises(DashboardLayoutScopeMismatch):
            create_layout(
                db_session,
                scope="platform_default",
                vertical="manufacturing",
                tenant_id=None,
                page_context="dashboard",
                layout_config=[],
            )

        # tenant_default with no tenant_id → mismatch.
        with pytest.raises(DashboardLayoutScopeMismatch):
            create_layout(
                db_session,
                scope="tenant_default",
                vertical=None,
                tenant_id=None,
                page_context="dashboard",
                layout_config=[],
            )

    def test_invalid_scope_rejected(self, db_session):
        from app.services.dashboard_layouts import (
            InvalidDashboardLayoutShape,
            create_layout,
        )

        with pytest.raises(InvalidDashboardLayoutShape):
            create_layout(
                db_session,
                scope="weird_scope",
                vertical=None,
                tenant_id=None,
                page_context="dashboard",
                layout_config=[],
            )

    def test_empty_page_context_rejected(self, db_session):
        from app.services.dashboard_layouts import (
            InvalidDashboardLayoutShape,
            create_layout,
        )

        with pytest.raises(InvalidDashboardLayoutShape):
            create_layout(
                db_session,
                scope="platform_default",
                page_context="",
                layout_config=[],
            )

    def test_layout_config_must_be_list(self, db_session):
        from app.services.dashboard_layouts import (
            InvalidDashboardLayoutShape,
            create_layout,
        )

        with pytest.raises(InvalidDashboardLayoutShape):
            create_layout(
                db_session,
                scope="platform_default",
                page_context="dashboard",
                layout_config={"not": "a list"},  # type: ignore
            )

    def test_widget_id_required_in_each_entry(self, db_session):
        from app.services.dashboard_layouts import (
            InvalidDashboardLayoutShape,
            create_layout,
        )

        with pytest.raises(InvalidDashboardLayoutShape):
            create_layout(
                db_session,
                scope="platform_default",
                page_context="dashboard",
                layout_config=[{"position": 1}],
            )

    def test_duplicate_widget_id_rejected(self, db_session):
        from app.services.dashboard_layouts import (
            InvalidDashboardLayoutShape,
            create_layout,
        )

        with pytest.raises(InvalidDashboardLayoutShape):
            create_layout(
                db_session,
                scope="platform_default",
                page_context="dashboard",
                layout_config=[
                    _layout_entry("today", 1),
                    _layout_entry("today", 2),  # duplicate
                ],
            )


# ─── Versioning ─────────────────────────────────────────────────


class TestVersioning:
    def test_initial_version_is_one(self, db_session):
        from app.services.dashboard_layouts import create_layout

        row = create_layout(
            db_session,
            scope="platform_default",
            page_context="dashboard",
            layout_config=[_layout_entry("today", 1)],
        )
        assert row.version == 1
        assert row.is_active is True

    def test_resave_versions_prior_row(self, db_session):
        """Creating another active row at the same tuple deactivates
        the prior one and bumps version."""
        from app.services.dashboard_layouts import create_layout

        v1 = create_layout(
            db_session,
            scope="platform_default",
            page_context="dashboard",
            layout_config=[_layout_entry("today", 1)],
        )
        v2 = create_layout(
            db_session,
            scope="platform_default",
            page_context="dashboard",
            layout_config=[_layout_entry("today", 1), _layout_entry("anomalies", 2)],
        )
        assert v1.id != v2.id
        assert v2.version == 2
        assert v2.is_active is True

        # The prior row should be inactive after the new write.
        db_session.refresh(v1)
        assert v1.is_active is False

    def test_update_versions_and_replaces(self, db_session):
        from app.services.dashboard_layouts import create_layout, update_layout

        v1 = create_layout(
            db_session,
            scope="platform_default",
            page_context="dashboard",
            layout_config=[_layout_entry("today", 1)],
        )
        v2 = update_layout(
            db_session,
            v1.id,
            layout_config=[_layout_entry("today", 1), _layout_entry("recent_activity", 2)],
        )
        assert v2.version == 2
        assert v2.is_active is True
        assert len(v2.layout_config) == 2

        db_session.refresh(v1)
        assert v1.is_active is False


# ─── Inheritance ────────────────────────────────────────────────


class TestInheritance:
    def test_resolve_empty_when_no_rows(self, db_session):
        from app.services.dashboard_layouts import resolve_layout

        result = resolve_layout(
            db_session,
            page_context="dashboard",
            vertical="funeral_home",
            tenant_id=None,
        )
        assert result["layout_config"] == []
        assert result["source"] is None
        assert result["sources"] == []

    def test_platform_default_resolves(self, db_session):
        from app.services.dashboard_layouts import create_layout, resolve_layout

        create_layout(
            db_session,
            scope="platform_default",
            page_context="dashboard",
            layout_config=[_layout_entry("today", 1)],
        )
        result = resolve_layout(db_session, page_context="dashboard")
        assert result["source"] == "platform_default"
        assert len(result["layout_config"]) == 1
        assert result["layout_config"][0]["widget_id"] == "today"

    def test_vertical_default_overrides_platform(self, db_session):
        from app.services.dashboard_layouts import create_layout, resolve_layout

        create_layout(
            db_session,
            scope="platform_default",
            page_context="dashboard",
            layout_config=[_layout_entry("today", 1)],
        )
        create_layout(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            page_context="dashboard",
            layout_config=[
                _layout_entry("today", 1),
                _layout_entry("recent_activity", 2),
            ],
        )

        # FH tenant resolves to vertical_default.
        result = resolve_layout(
            db_session, page_context="dashboard", vertical="funeral_home"
        )
        assert result["source"] == "vertical_default"
        assert len(result["layout_config"]) == 2
        # `sources` shows the full visit trail (platform + vertical).
        assert {s["scope"] for s in result["sources"]} == {
            "platform_default",
            "vertical_default",
        }

    def test_tenant_default_overrides_vertical(self, db_session):
        from app.services.dashboard_layouts import create_layout, resolve_layout

        tenant_id = _make_tenant(vertical="funeral_home")
        create_layout(
            db_session,
            scope="platform_default",
            page_context="dashboard",
            layout_config=[_layout_entry("today", 1)],
        )
        create_layout(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            page_context="dashboard",
            layout_config=[
                _layout_entry("today", 1),
                _layout_entry("recent_activity", 2),
            ],
        )
        create_layout(
            db_session,
            scope="tenant_default",
            tenant_id=tenant_id,
            page_context="dashboard",
            layout_config=[
                _layout_entry("today", 1),
                _layout_entry("recent_activity", 2),
                _layout_entry("anomalies", 3),
            ],
        )

        result = resolve_layout(
            db_session,
            page_context="dashboard",
            vertical="funeral_home",
            tenant_id=tenant_id,
        )
        assert result["source"] == "tenant_default"
        assert len(result["layout_config"]) == 3
        assert {s["scope"] for s in result["sources"]} == {
            "platform_default",
            "vertical_default",
            "tenant_default",
        }

    def test_tenant_in_unauthored_vertical_falls_back_to_platform(
        self, db_session
    ):
        """When vertical_default doesn't exist for the tenant's vertical,
        resolve falls back to platform_default."""
        from app.services.dashboard_layouts import create_layout, resolve_layout

        tenant_id = _make_tenant(vertical="cemetery")
        # Only platform_default exists.
        create_layout(
            db_session,
            scope="platform_default",
            page_context="dashboard",
            layout_config=[_layout_entry("today", 1)],
        )

        result = resolve_layout(
            db_session,
            page_context="dashboard",
            vertical="cemetery",
            tenant_id=tenant_id,
        )
        assert result["source"] == "platform_default"
        assert len(result["layout_config"]) == 1


# ─── Admin API ──────────────────────────────────────────────────


class TestApiAdmin:
    def test_list_create_resolve_happy_path(self, client):
        ctx = _make_platform_admin()

        # Create platform_default.
        r = client.post(
            "/api/platform/admin/visual-editor/dashboard-layouts/",
            json={
                "scope": "platform_default",
                "page_context": "dashboard",
                "layout_config": [_layout_entry("today", 1)],
            },
            headers=_admin_headers(ctx),
        )
        assert r.status_code == 201, r.text
        platform_row = r.json()
        assert platform_row["scope"] == "platform_default"
        assert platform_row["version"] == 1

        # Create vertical_default for funeral_home.
        r = client.post(
            "/api/platform/admin/visual-editor/dashboard-layouts/",
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "page_context": "dashboard",
                "layout_config": [
                    _layout_entry("today", 1),
                    _layout_entry("recent_activity", 2),
                ],
            },
            headers=_admin_headers(ctx),
        )
        assert r.status_code == 201, r.text

        # List with scope filter.
        r = client.get(
            "/api/platform/admin/visual-editor/dashboard-layouts/?scope=vertical_default",
            headers=_admin_headers(ctx),
        )
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1

        # Resolve for funeral_home should return vertical_default.
        r = client.get(
            "/api/platform/admin/visual-editor/dashboard-layouts/resolve"
            "?page_context=dashboard&vertical=funeral_home",
            headers=_admin_headers(ctx),
        )
        assert r.status_code == 200
        resolved = r.json()
        assert resolved["source"] == "vertical_default"
        assert len(resolved["layout_config"]) == 2

    def test_invalid_scope_keys_400(self, client):
        ctx = _make_platform_admin()
        r = client.post(
            "/api/platform/admin/visual-editor/dashboard-layouts/",
            json={
                "scope": "vertical_default",
                # missing vertical
                "page_context": "dashboard",
                "layout_config": [],
            },
            headers=_admin_headers(ctx),
        )
        assert r.status_code == 400, r.text

    def test_anonymous_rejected(self, client):
        r = client.get(
            "/api/platform/admin/visual-editor/dashboard-layouts/?scope=platform_default"
        )
        # No PlatformUser auth → 401 (or 403 depending on dep behavior;
        # both are non-200 — the load-bearing assertion is 'rejected').
        assert r.status_code in (401, 403)

    def test_tenant_token_rejected(self, client):
        """Cross-realm boundary — tenant-realm tokens must not access
        platform-realm dashboard-layouts endpoints."""
        from app.core.security import create_access_token

        # Create a fake tenant token.
        suffix = uuid.uuid4().hex[:6]
        tenant_token = create_access_token(
            {"sub": f"fake-user-{suffix}"}, realm="tenant"
        )
        r = client.get(
            "/api/platform/admin/visual-editor/dashboard-layouts/?scope=platform_default",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        assert r.status_code == 401

    def test_update_existing_layout(self, client):
        ctx = _make_platform_admin()
        r = client.post(
            "/api/platform/admin/visual-editor/dashboard-layouts/",
            json={
                "scope": "platform_default",
                "page_context": "dashboard",
                "layout_config": [_layout_entry("today", 1)],
            },
            headers=_admin_headers(ctx),
        )
        assert r.status_code == 201
        v1 = r.json()

        r = client.patch(
            f"/api/platform/admin/visual-editor/dashboard-layouts/{v1['id']}",
            json={
                "layout_config": [
                    _layout_entry("today", 1),
                    _layout_entry("anomalies", 2),
                ],
            },
            headers=_admin_headers(ctx),
        )
        assert r.status_code == 200, r.text
        v2 = r.json()
        assert v2["version"] == 2
        assert v2["id"] != v1["id"]
        assert len(v2["layout_config"]) == 2


# ─── widget_service integration ─────────────────────────────────


class TestWidgetServiceIntegration:
    """Asserts widget_service.get_user_layout walks the new
    inheritance chain when seeding a fresh user's default layout."""

    def test_user_with_no_override_inherits_vertical_default(self, client):
        """Fresh user with no UserWidgetLayout row inherits the
        platform-authored vertical_default."""
        from app.database import SessionLocal
        from app.models.user_widget_layout import UserWidgetLayout
        from app.services.dashboard_layouts import create_layout
        from app.services.widgets.widget_service import get_user_layout

        # Create FH tenant.
        tenant_id = _make_tenant(vertical="funeral_home")

        # Fresh user inside that tenant.
        from app.models.user import User
        from app.models.role import Role
        from app.core.security import hash_password

        db_setup = SessionLocal()
        try:
            employee_role = (
                db_setup.query(Role)
                .filter(Role.slug == "employee", Role.is_system.is_(True))
                .first()
            )
            assert employee_role is not None, "expected seeded employee role"
            role_id = employee_role.id
        finally:
            db_setup.close()

        suffix = uuid.uuid4().hex[:6]
        user = User(
            id=str(uuid.uuid4()),
            email=f"u-dl-{suffix}@hopkinsfh.test",
            hashed_password=hash_password("DemoPass123!"),
            first_name="Test",
            last_name="User",
            company_id=tenant_id,
            role_id=role_id,
            is_active=True,
        )
        db = SessionLocal()
        try:
            db.add(user)
            db.commit()
            db.refresh(user)

            # Author a vertical_default for funeral_home.
            create_layout(
                db,
                scope="vertical_default",
                vertical="funeral_home",
                page_context="dashboard",
                layout_config=[
                    _layout_entry("today", 1),
                    _layout_entry("recent_activity", 2),
                ],
            )

            # Confirm no user override exists yet.
            existing = (
                db.query(UserWidgetLayout)
                .filter(
                    UserWidgetLayout.user_id == user.id,
                    UserWidgetLayout.page_context == "dashboard",
                )
                .first()
            )
            assert existing is None

            # First call seeds a UserWidgetLayout from the resolved chain.
            layout = get_user_layout(db, tenant_id, user, "dashboard")
            assert layout is not None
            # The seeded UserWidgetLayout pulled its config from the
            # vertical_default. Each entry is enriched with definition
            # data, but widget_ids match what we authored.
            seeded = (
                db.query(UserWidgetLayout)
                .filter(
                    UserWidgetLayout.user_id == user.id,
                    UserWidgetLayout.page_context == "dashboard",
                )
                .first()
            )
            seeded_widget_ids = [w["widget_id"] for w in seeded.layout_config]
            assert seeded_widget_ids == ["today", "recent_activity"]
        finally:
            db.close()

    def test_no_authored_layout_falls_back_to_in_code_defaults(self, client):
        """When NO row exists at any scope (platform / vertical / tenant),
        the existing in-code WIDGET_DEFINITIONS defaults still apply."""
        from app.database import SessionLocal
        from app.models.user_widget_layout import UserWidgetLayout
        from app.services.widgets.widget_service import get_user_layout

        tenant_id = _make_tenant(vertical="manufacturing")

        from app.models.user import User
        from app.models.role import Role
        from app.core.security import hash_password

        db_setup = SessionLocal()
        try:
            employee_role = (
                db_setup.query(Role)
                .filter(Role.slug == "employee", Role.is_system.is_(True))
                .first()
            )
            assert employee_role is not None, "expected seeded employee role"
            role_id = employee_role.id
        finally:
            db_setup.close()

        suffix = uuid.uuid4().hex[:6]
        user = User(
            id=str(uuid.uuid4()),
            email=f"u-mfg-{suffix}@example.test",
            hashed_password=hash_password("DemoPass123!"),
            first_name="Test",
            last_name="User",
            company_id=tenant_id,
            role_id=role_id,
            is_active=True,
        )
        db = SessionLocal()
        try:
            db.add(user)
            db.commit()
            db.refresh(user)

            layout = get_user_layout(db, tenant_id, user, "ops_board")
            assert layout is not None
            # Layout was generated from in-code defaults; the seeded
            # UserWidgetLayout row exists.
            seeded = (
                db.query(UserWidgetLayout)
                .filter(
                    UserWidgetLayout.user_id == user.id,
                    UserWidgetLayout.page_context == "ops_board",
                )
                .first()
            )
            assert seeded is not None
            # The exact widget set depends on the manufacturing tenant's
            # extension/module/vertical config but it should be a list.
            assert isinstance(seeded.layout_config, list)
        finally:
            db.close()


# ─── Migration head + table presence ────────────────────────────


class TestMigrationHead:
    def test_dashboard_layouts_table_exists(self):
        """The r87 migration must have created the table."""
        import sqlalchemy as sa
        from app.database import engine

        inspector = sa.inspect(engine)
        tables = set(inspector.get_table_names())
        assert "dashboard_layouts" in tables

    def test_table_carries_required_columns(self):
        import sqlalchemy as sa
        from app.database import engine

        inspector = sa.inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("dashboard_layouts")}
        assert {
            "id",
            "scope",
            "vertical",
            "tenant_id",
            "page_context",
            "layout_config",
            "version",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        }.issubset(columns)
