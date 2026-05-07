"""R-2.5 — tenant-realm theme resolve endpoint.

Validates `GET /api/v1/themes/resolve`:
  - Requires tenant auth (rejects platform realm tokens, rejects no auth)
  - Infers vertical + tenant_id from caller's company; ignores any
    query-param hint pretending to override
  - Returns the same shape as the admin endpoint
  - Tenants without authored overrides receive empty tokens + sources
    (frontend falls through to tokens.css defaults)
  - Vertical-default + tenant-override resolutions compose correctly
    in inheritance order
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


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


def _make_tenant_with_admin(vertical: str = "manufacturing") -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.platform_user import PlatformUser
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"Themes-T {suffix}",
            slug=f"themes-t-{suffix}",
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

        tenant_token = create_access_token(
            {"sub": admin.id, "company_id": co.id},
            realm="tenant",
        )
        platform_token = create_access_token(
            {"sub": platform_admin.id},
            realm="platform",
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "admin_id": admin.id,
            "tenant_token": tenant_token,
            "platform_token": platform_token,
            "vertical": vertical,
        }
    finally:
        db.close()


def _tenant_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['tenant_token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _seed_theme(
    *,
    scope: str,
    mode: str,
    vertical: str | None,
    tenant_id: str | None,
    overrides: dict,
) -> None:
    from app.database import SessionLocal
    from app.services.platform_themes import create_theme

    db = SessionLocal()
    try:
        create_theme(
            db,
            scope=scope,
            vertical=vertical,
            tenant_id=tenant_id,
            mode=mode,
            token_overrides=overrides,
            actor_user_id=None,
        )
        db.commit()
    finally:
        db.close()


# ─── Auth gating ──────────────────────────────────────────────


def test_resolve_requires_auth(client):
    response = client.get("/api/v1/themes/resolve?mode=light")
    # FastAPI's HTTPBearer returns 403 when no Authorization header is
    # supplied (no token to evaluate); subsequent realm checks return
    # 401 when a token IS supplied but is wrong realm. Either is
    # canonical "unauthenticated" — endpoint is gated.
    assert response.status_code in {401, 403}


def test_resolve_rejects_platform_token(client):
    ctx = _make_tenant_with_admin()
    response = client.get(
        "/api/v1/themes/resolve?mode=light",
        headers={
            "Authorization": f"Bearer {ctx['platform_token']}",
            "X-Company-Slug": ctx["slug"],
        },
    )
    # Tenant deps reject platform tokens with 401 (cross-realm boundary).
    assert response.status_code == 401


# ─── Resolve behavior ─────────────────────────────────────────


def test_resolve_empty_returns_static_default_shape(client):
    ctx = _make_tenant_with_admin()
    response = client.get(
        "/api/v1/themes/resolve?mode=light",
        headers=_tenant_headers(ctx),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "light"
    assert body["vertical"] == "manufacturing"
    assert body["tenant_id"] == ctx["company_id"]
    # No authored overrides anywhere → empty tokens + empty sources.
    # Frontend's composeEffective falls through to tokens.css defaults.
    assert body["tokens"] == {}
    assert body["sources"] == []


def test_resolve_picks_up_vertical_default(client):
    ctx = _make_tenant_with_admin(vertical="manufacturing")
    _seed_theme(
        scope="vertical_default",
        mode="light",
        vertical="manufacturing",
        tenant_id=None,
        overrides={"accent": "oklch(0.55 0.13 240)"},
    )
    response = client.get(
        "/api/v1/themes/resolve?mode=light",
        headers=_tenant_headers(ctx),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tokens"].get("accent") == "oklch(0.55 0.13 240)"
    assert any(
        s.get("scope") == "vertical_default" for s in body["sources"]
    )


def test_resolve_tenant_override_beats_vertical_default(client):
    ctx = _make_tenant_with_admin(vertical="manufacturing")
    _seed_theme(
        scope="vertical_default",
        mode="light",
        vertical="manufacturing",
        tenant_id=None,
        overrides={"accent": "oklch(0.55 0.13 240)"},
    )
    _seed_theme(
        scope="tenant_override",
        mode="light",
        vertical=None,
        tenant_id=ctx["company_id"],
        overrides={"accent": "oklch(0.62 0.18 30)"},
    )
    response = client.get(
        "/api/v1/themes/resolve?mode=light",
        headers=_tenant_headers(ctx),
    )
    assert response.status_code == 200
    body = response.json()
    # tenant_override wins over vertical_default
    assert body["tokens"]["accent"] == "oklch(0.62 0.18 30)"
    scopes = {s["scope"] for s in body["sources"]}
    assert "tenant_override" in scopes
    assert "vertical_default" in scopes


def test_resolve_mode_isolation(client):
    ctx = _make_tenant_with_admin(vertical="manufacturing")
    _seed_theme(
        scope="vertical_default",
        mode="light",
        vertical="manufacturing",
        tenant_id=None,
        overrides={"accent": "oklch(0.55 0.13 240)"},
    )
    # Light mode resolves the override; dark mode resolves to empty.
    light = client.get(
        "/api/v1/themes/resolve?mode=light",
        headers=_tenant_headers(ctx),
    )
    dark = client.get(
        "/api/v1/themes/resolve?mode=dark",
        headers=_tenant_headers(ctx),
    )
    assert light.status_code == 200 and dark.status_code == 200
    assert light.json()["tokens"].get("accent") == "oklch(0.55 0.13 240)"
    assert dark.json()["tokens"] == {}


def test_resolve_cannot_request_other_tenant(client):
    """Caller's company is inferred server-side. Even if a malicious
    client passes a `vertical=` or `tenant_id=` query param hoping to
    pivot to another tenant's overrides, the endpoint ignores them —
    those query params are not declared on the route signature."""
    ctx_a = _make_tenant_with_admin(vertical="manufacturing")
    ctx_b = _make_tenant_with_admin(vertical="funeral_home")
    _seed_theme(
        scope="tenant_override",
        mode="light",
        vertical=None,
        tenant_id=ctx_b["company_id"],
        overrides={"accent": "oklch(0.99 0.0 0)"},
    )
    # Pass tenant B's id as a query param hint while authed as tenant A.
    response = client.get(
        f"/api/v1/themes/resolve?mode=light&tenant_id={ctx_b['company_id']}",
        headers=_tenant_headers(ctx_a),
    )
    assert response.status_code == 200
    # Resolution is for tenant A — no override for A means empty tokens,
    # tenant B's override is NOT visible.
    body = response.json()
    assert body["tenant_id"] == ctx_a["company_id"]
    assert body["tokens"] == {}


def test_resolve_invalid_mode_returns_422(client):
    ctx = _make_tenant_with_admin()
    response = client.get(
        "/api/v1/themes/resolve?mode=midnight",
        headers=_tenant_headers(ctx),
    )
    # Pydantic Literal["light", "dark"] rejects at the route layer.
    assert response.status_code == 422
