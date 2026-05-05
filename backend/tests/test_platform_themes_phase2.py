"""Phase 2 of the Admin Visual Editor — platform_themes tests.

Covers:
  - Service layer: scope-key validation, mode validation,
    versioning on create/update, inheritance resolution
  - Mode independence: editing light doesn't affect dark
  - Inheritance edge cases: tenant override on a vertical with no
    vertical default falls back to platform default
  - API: admin-gated, request shape validation, response shape
  - Claude API E2E equivalent: programmatic create →
    resolve → update → resolve → fall-back-on-delete dance
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
    """Create a tenant + admin user; return ctx dict."""
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
            name=f"Themes {suffix}",
            slug=f"themes-{suffix}",
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
            email=f"admin-{suffix}@themes.test",
            hashed_password="x",
            first_name="Theme",
            last_name="Admin",
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(admin)

        # Non-admin user for permission gating tests.
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
            email=f"office-{suffix}@themes.test",
            hashed_password="x",
            first_name="Theme",
            last_name="Office",
            role_id=non_admin_role.id,
            is_active=True,
        )
        db.add(non_admin)

        db.commit()

        admin_token = create_access_token(
            {"sub": admin.id, "company_id": co.id},
            realm="tenant",
        )
        non_admin_token = create_access_token(
            {"sub": non_admin.id, "company_id": co.id},
            realm="tenant",
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "admin_id": admin.id,
            "admin_token": admin_token,
            "non_admin_token": non_admin_token,
            "vertical": vertical,
        }
    finally:
        db.close()


def _admin_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['admin_token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _non_admin_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['non_admin_token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _cleanup_themes():
    """Remove every PlatformTheme row left behind by other tests
    in the suite. The tests below use real Postgres + commit, so
    isolation depends on this teardown."""
    from app.database import SessionLocal
    from app.models.platform_theme import PlatformTheme

    db = SessionLocal()
    try:
        db.query(PlatformTheme).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_themes_each_test():
    _cleanup_themes()
    yield
    _cleanup_themes()


# ─── Service-layer tests ──────────────────────────────────────


class TestServiceValidation:
    def test_platform_default_rejects_vertical(self, db_session):
        from app.services.platform_themes import (
            ThemeScopeMismatch,
            create_theme,
        )

        with pytest.raises(ThemeScopeMismatch):
            create_theme(
                db_session,
                scope="platform_default",
                vertical="manufacturing",
                mode="light",
            )

    def test_vertical_default_requires_vertical(self, db_session):
        from app.services.platform_themes import (
            ThemeScopeMismatch,
            create_theme,
        )

        with pytest.raises(ThemeScopeMismatch):
            create_theme(
                db_session,
                scope="vertical_default",
                vertical=None,
                mode="light",
            )

    def test_tenant_override_requires_tenant_id(self, db_session):
        from app.services.platform_themes import (
            ThemeScopeMismatch,
            create_theme,
        )

        with pytest.raises(ThemeScopeMismatch):
            create_theme(
                db_session,
                scope="tenant_override",
                tenant_id=None,
                mode="light",
            )

    def test_invalid_mode_rejected(self, db_session):
        from app.services.platform_themes import (
            InvalidThemeShape,
            create_theme,
        )

        with pytest.raises(InvalidThemeShape):
            create_theme(
                db_session,
                scope="platform_default",
                mode="evening",  # type: ignore[arg-type]
            )

    def test_overrides_non_dict_rejected(self, db_session):
        from app.services.platform_themes import (
            InvalidThemeShape,
            create_theme,
        )

        with pytest.raises(InvalidThemeShape):
            create_theme(
                db_session,
                scope="platform_default",
                mode="light",
                token_overrides="oops",  # type: ignore[arg-type]
            )


class TestVersioning:
    def test_create_initial_version_is_one(self, db_session):
        from app.services.platform_themes import create_theme

        row = create_theme(
            db_session,
            scope="platform_default",
            mode="light",
            token_overrides={"accent": "oklch(0.50 0.10 39)"},
        )
        assert row.version == 1
        assert row.is_active is True

    def test_create_at_existing_tuple_versions(self, db_session):
        from app.services.platform_themes import create_theme

        first = create_theme(
            db_session,
            scope="platform_default",
            mode="light",
            token_overrides={"accent": "oklch(0.50 0.10 39)"},
        )
        second = create_theme(
            db_session,
            scope="platform_default",
            mode="light",
            token_overrides={"accent": "oklch(0.55 0.10 39)"},
        )
        assert second.version == 2
        assert second.is_active is True
        # Refetch first to confirm it was deactivated
        db_session.refresh(first)
        assert first.is_active is False

    def test_update_versions_and_replaces_overrides(self, db_session):
        from app.services.platform_themes import create_theme, update_theme

        first = create_theme(
            db_session,
            scope="platform_default",
            mode="light",
            token_overrides={"accent": "oklch(0.50 0.10 39)"},
        )
        new_row = update_theme(
            db_session,
            first.id,
            token_overrides={"accent": "oklch(0.60 0.10 39)"},
        )
        assert new_row.version == 2
        assert new_row.is_active is True
        db_session.refresh(first)
        assert first.is_active is False


class TestModeIndependence:
    def test_light_edit_does_not_affect_dark(self, db_session):
        from app.services.platform_themes import create_theme, resolve_theme

        create_theme(
            db_session,
            scope="platform_default",
            mode="light",
            token_overrides={"accent": "oklch(0.50 0.10 39)"},
        )
        create_theme(
            db_session,
            scope="platform_default",
            mode="dark",
            token_overrides={"accent": "oklch(0.66 0.13 39)"},
        )

        light = resolve_theme(db_session, mode="light")
        dark = resolve_theme(db_session, mode="dark")

        assert light["tokens"]["accent"] == "oklch(0.50 0.10 39)"
        assert dark["tokens"]["accent"] == "oklch(0.66 0.13 39)"

    def test_resolve_filters_by_mode(self, db_session):
        from app.services.platform_themes import create_theme, resolve_theme

        # Only seed dark mode.
        create_theme(
            db_session,
            scope="platform_default",
            mode="dark",
            token_overrides={"accent": "oklch(0.66 0.13 39)"},
        )

        light = resolve_theme(db_session, mode="light")
        assert light["tokens"] == {}
        assert light["sources"] == []


class TestInheritance:
    def test_platform_only(self, db_session):
        from app.services.platform_themes import create_theme, resolve_theme

        create_theme(
            db_session,
            scope="platform_default",
            mode="light",
            token_overrides={"accent": "oklch(0.50 0.10 39)"},
        )
        result = resolve_theme(db_session, mode="light")
        assert result["tokens"]["accent"] == "oklch(0.50 0.10 39)"
        assert len(result["sources"]) == 1
        assert result["sources"][0]["scope"] == "platform_default"

    def test_vertical_overrides_platform(self, db_session):
        from app.services.platform_themes import create_theme, resolve_theme

        create_theme(
            db_session,
            scope="platform_default",
            mode="light",
            token_overrides={"accent": "oklch(0.50 0.10 39)"},
        )
        create_theme(
            db_session,
            scope="vertical_default",
            vertical="funeral_home",
            mode="light",
            token_overrides={"accent": "oklch(0.55 0.12 30)"},
        )

        # FH gets the FH override
        fh = resolve_theme(db_session, mode="light", vertical="funeral_home")
        assert fh["tokens"]["accent"] == "oklch(0.55 0.12 30)"
        assert len(fh["sources"]) == 2

        # Manufacturing has no vertical override → platform default
        mfg = resolve_theme(db_session, mode="light", vertical="manufacturing")
        assert mfg["tokens"]["accent"] == "oklch(0.50 0.10 39)"
        assert len(mfg["sources"]) == 1

    def test_tenant_overrides_everything(self, db_session):
        from app.services.platform_themes import create_theme, resolve_theme

        ctx = _make_tenant_with_admin(vertical="funeral_home")
        try:
            create_theme(
                db_session,
                scope="platform_default",
                mode="light",
                token_overrides={"accent": "oklch(0.50 0.10 39)"},
            )
            create_theme(
                db_session,
                scope="vertical_default",
                vertical="funeral_home",
                mode="light",
                token_overrides={"accent": "oklch(0.55 0.12 30)"},
            )
            create_theme(
                db_session,
                scope="tenant_override",
                tenant_id=ctx["company_id"],
                mode="light",
                token_overrides={"accent": "oklch(0.70 0.05 250)"},
            )

            result = resolve_theme(
                db_session,
                mode="light",
                vertical="funeral_home",
                tenant_id=ctx["company_id"],
            )
            assert result["tokens"]["accent"] == "oklch(0.70 0.05 250)"
            assert len(result["sources"]) == 3
        finally:
            _cleanup_themes()

    def test_tenant_override_without_vertical_default_falls_back_to_platform(
        self, db_session
    ):
        from app.services.platform_themes import create_theme, resolve_theme

        ctx = _make_tenant_with_admin(vertical="cemetery")
        try:
            create_theme(
                db_session,
                scope="platform_default",
                mode="light",
                token_overrides={"surface-base": "oklch(0.94 0.030 82)"},
            )
            create_theme(
                db_session,
                scope="tenant_override",
                tenant_id=ctx["company_id"],
                mode="light",
                token_overrides={"accent": "oklch(0.70 0.05 250)"},
            )

            result = resolve_theme(
                db_session,
                mode="light",
                vertical="cemetery",
                tenant_id=ctx["company_id"],
            )
            # Tenant override layered on platform default — surface-base
            # comes from platform, accent from tenant.
            assert result["tokens"]["surface-base"] == "oklch(0.94 0.030 82)"
            assert result["tokens"]["accent"] == "oklch(0.70 0.05 250)"
        finally:
            _cleanup_themes()


# ─── API tests ────────────────────────────────────────────────


class TestAdminGating:
    def test_anonymous_403_or_401(self, client):
        resp = client.get("/api/v1/admin/themes/")
        # No auth → 401 (FastAPI bearer scheme returns 403 in some
        # configs; both are acceptable rejections).
        assert resp.status_code in (401, 403)

    def test_non_admin_rejected_403(self, client):
        ctx = _make_tenant_with_admin()
        resp = client.get(
            "/api/v1/admin/themes/",
            headers=_non_admin_headers(ctx),
        )
        assert resp.status_code == 403


class TestApiCreateAndList:
    def test_create_then_list(self, client):
        ctx = _make_tenant_with_admin()
        create_resp = client.post(
            "/api/v1/admin/themes/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "mode": "light",
                "token_overrides": {"accent": "oklch(0.55 0.10 39)"},
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        body = create_resp.json()
        assert body["scope"] == "platform_default"
        assert body["mode"] == "light"
        assert body["version"] == 1
        assert body["is_active"] is True

        list_resp = client.get(
            "/api/v1/admin/themes/?scope=platform_default&mode=light",
            headers=_admin_headers(ctx),
        )
        assert list_resp.status_code == 200
        rows = list_resp.json()
        assert len(rows) == 1
        assert rows[0]["id"] == body["id"]

    def test_create_invalid_scope_returns_400(self, client):
        ctx = _make_tenant_with_admin()
        resp = client.post(
            "/api/v1/admin/themes/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "vertical": "funeral_home",  # not allowed at platform scope
                "mode": "light",
                "token_overrides": {},
            },
        )
        assert resp.status_code == 400

    def test_patch_versions(self, client):
        ctx = _make_tenant_with_admin()
        create_resp = client.post(
            "/api/v1/admin/themes/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "mode": "light",
                "token_overrides": {"accent": "oklch(0.50 0.10 39)"},
            },
        )
        first_id = create_resp.json()["id"]

        patch_resp = client.patch(
            f"/api/v1/admin/themes/{first_id}",
            headers=_admin_headers(ctx),
            json={"token_overrides": {"accent": "oklch(0.60 0.10 39)"}},
        )
        assert patch_resp.status_code == 200
        new_body = patch_resp.json()
        assert new_body["version"] == 2
        assert new_body["id"] != first_id  # versioning creates new row

    def test_resolve_endpoint_walks_inheritance(self, client):
        ctx = _make_tenant_with_admin(vertical="funeral_home")

        client.post(
            "/api/v1/admin/themes/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "mode": "light",
                "token_overrides": {"accent": "oklch(0.50 0.10 39)"},
            },
        )
        client.post(
            "/api/v1/admin/themes/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "mode": "light",
                "token_overrides": {"accent": "oklch(0.55 0.12 30)"},
            },
        )

        resolve_resp = client.get(
            "/api/v1/admin/themes/resolve",
            headers=_admin_headers(ctx),
            params={"mode": "light", "vertical": "funeral_home"},
        )
        assert resolve_resp.status_code == 200, resolve_resp.text
        body = resolve_resp.json()
        assert body["tokens"]["accent"] == "oklch(0.55 0.12 30)"
        assert len(body["sources"]) == 2


class TestE2EClaudeApiEquivalent:
    """Programmatic dance: create → resolve → update → resolve →
    fallback-on-delete. Mirrors the prompt's spec for the 'Claude
    API end-to-end test'."""

    def test_full_lifecycle(self, client, db_session):
        ctx = _make_tenant_with_admin(vertical="funeral_home")

        # Platform default at base
        client.post(
            "/api/v1/admin/themes/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "mode": "light",
                "token_overrides": {"accent": "oklch(0.50 0.10 39)"},
            },
        )
        # Vertical override
        create_resp = client.post(
            "/api/v1/admin/themes/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "vertical": "funeral_home",
                "mode": "light",
                "token_overrides": {"accent": "oklch(0.70 0.10 39)"},
            },
        )
        vertical_id = create_resp.json()["id"]

        # Resolve for a tenant in the vertical → should see overridden value
        r1 = client.get(
            "/api/v1/admin/themes/resolve",
            headers=_admin_headers(ctx),
            params={
                "mode": "light",
                "vertical": "funeral_home",
                "tenant_id": ctx["company_id"],
            },
        ).json()
        assert r1["tokens"]["accent"] == "oklch(0.70 0.10 39)"

        # Update the vertical override
        r2_resp = client.patch(
            f"/api/v1/admin/themes/{vertical_id}",
            headers=_admin_headers(ctx),
            json={"token_overrides": {"accent": "oklch(0.80 0.10 39)"}},
        )
        assert r2_resp.status_code == 200

        # Resolve again → new value propagates
        r2 = client.get(
            "/api/v1/admin/themes/resolve",
            headers=_admin_headers(ctx),
            params={"mode": "light", "vertical": "funeral_home"},
        ).json()
        assert r2["tokens"]["accent"] == "oklch(0.80 0.10 39)"

        # "Delete" the vertical override = empty its overrides
        # (semantically equivalent to removing the customization);
        # delete-as-row is a Phase 3 concern + would need a new
        # endpoint not in this phase's scope.
        new_active_id = r2_resp.json()["id"]
        client.patch(
            f"/api/v1/admin/themes/{new_active_id}",
            headers=_admin_headers(ctx),
            json={"token_overrides": {}},
        )

        # Resolve falls back to platform default
        r3 = client.get(
            "/api/v1/admin/themes/resolve",
            headers=_admin_headers(ctx),
            params={"mode": "light", "vertical": "funeral_home"},
        ).json()
        assert r3["tokens"]["accent"] == "oklch(0.50 0.10 39)"
