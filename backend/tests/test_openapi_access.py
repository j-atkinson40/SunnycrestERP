"""R-7-β — /openapi.json platform-admin-gated on staging.

Auth matrix per environment:
  - staging + anonymous → 401
  - staging + tenant-realm token → 401 (cross-realm rejected)
  - staging + platform admin → 200 + valid OpenAPI spec
  - staging + platform admin → /docs returns 200 HTML
  - staging + platform admin → /redoc returns 200 HTML
  - production + anonymous → 404 (routes not mounted)
  - production + platform admin → 404 (routes not mounted)
  - dev + anonymous → 200 (open access for local developer ergonomics)
"""

from __future__ import annotations

import importlib
import uuid

import pytest
from fastapi.testclient import TestClient


# ─── Helpers ──────────────────────────────────────────────────


def _client_for_env(monkeypatch, env: str) -> TestClient:
    """Build a TestClient with settings.ENVIRONMENT set + app re-imported.

    Each environment branch (dev/staging/production) instantiates a fresh
    FastAPI app so the conditional `_should_mount_openapi` / `_should_gate_openapi`
    branches fire at module-import time correctly.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", env)
    import app.main as main_mod
    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def _make_platform_admin_token() -> str:
    """Create a platform admin user + return a realm='platform' JWT."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.platform_user import PlatformUser

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        pu = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"openapi-test-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="OpenAPI",
            last_name="Test",
            role="super_admin",
            is_active=True,
        )
        db.add(pu)
        db.commit()
        return create_access_token({"sub": pu.id}, realm="platform")
    finally:
        db.close()


def _make_tenant_token() -> str:
    """Create a tenant user + return a realm-less (tenant) JWT."""
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
            name=f"OpenAPI Tenant {suffix}",
            slug=f"openapi-{suffix}",
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
            email=f"tenant-{suffix}@openapi.test",
            hashed_password="x",
            first_name="Tenant",
            last_name="User",
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        # Tenant tokens are created without realm="platform" — they default
        # or carry realm="tenant" per the canonical security helpers.
        return create_access_token({"sub": user.id})
    finally:
        db.close()


# ─── Staging branch ──────────────────────────────────────────────────


def test_staging_anonymous_openapi_rejected(monkeypatch):
    client = _client_for_env(monkeypatch, "staging")
    resp = client.get("/openapi.json")
    # HTTPBearer rejects missing creds with 403; explicit token with bad
    # realm returns 401. Both are auth failures from the operator's POV.
    assert resp.status_code in (401, 403)


def test_staging_tenant_token_openapi_rejected(monkeypatch):
    token = _make_tenant_token()
    client = _client_for_env(monkeypatch, "staging")
    resp = client.get(
        "/openapi.json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert "platform" in body.get("detail", "").lower() or body.get("detail")


def test_staging_platform_admin_openapi_200(monkeypatch):
    token = _make_platform_admin_token()
    client = _client_for_env(monkeypatch, "staging")
    resp = client.get(
        "/openapi.json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    spec = resp.json()
    assert "openapi" in spec
    assert "paths" in spec
    # Sanity: at least a handful of paths exist
    assert len(spec["paths"]) > 10


def test_staging_platform_admin_docs_html(monkeypatch):
    token = _make_platform_admin_token()
    client = _client_for_env(monkeypatch, "staging")
    resp = client.get(
        "/docs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    # Swagger UI references the openapi spec URL
    assert "/openapi.json" in resp.text


def test_staging_platform_admin_redoc_html(monkeypatch):
    token = _make_platform_admin_token()
    client = _client_for_env(monkeypatch, "staging")
    resp = client.get(
        "/redoc",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "/openapi.json" in resp.text


# ─── Production branch ──────────────────────────────────────────────────


def test_production_anonymous_openapi_404(monkeypatch):
    client = _client_for_env(monkeypatch, "production")
    resp = client.get("/openapi.json")
    assert resp.status_code == 404


def test_production_platform_admin_openapi_404(monkeypatch):
    token = _make_platform_admin_token()
    client = _client_for_env(monkeypatch, "production")
    resp = client.get(
        "/openapi.json",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Production stays disabled — even an authenticated platform admin
    # gets 404 because no route is mounted.
    assert resp.status_code == 404


# ─── Dev branch ──────────────────────────────────────────────────


def test_dev_anonymous_openapi_open(monkeypatch):
    """Dev keeps unauthenticated access for local developer ergonomics."""
    client = _client_for_env(monkeypatch, "dev")
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "openapi" in resp.json()


# ─── Teardown ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_app_after(monkeypatch):
    """After each test, reload main with the default settings so unrelated
    tests don't inherit production/staging env state."""
    yield
    # Reset to dev default + reload to leave the canonical app shape
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "dev", raising=False)
    import app.main as main_mod
    importlib.reload(main_mod)
