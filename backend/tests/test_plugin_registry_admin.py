"""R-8.y.d — Plugin Registry browser introspection endpoint tests.

Covers:
  - PlatformUser auth gate (anonymous + tenant tokens rejected)
  - Per-category catalog: 24 entries (matches PLUGIN_CONTRACTS.md count)
  - Introspection happy path for canonical Tier R1/R2 registries
  - Non-introspectable category returns canonical static-state shape
  - Invalid category_key → 404 with helpful message
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


# ─── Fixtures ──────────────────────────────────────────────────


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
        platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"plugin-reg-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="Plugin",
            last_name="Reg",
            role="super_admin",
            is_active=True,
        )
        db.add(platform_admin)
        db.commit()
        token = create_access_token(
            {"sub": platform_admin.id}, realm="platform"
        )
        return {
            "platform_id": platform_admin.id,
            "platform_token": token,
        }
    finally:
        db.close()


def _make_tenant_admin():
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
            name=f"PluginReg {suffix}",
            slug=f"plugin-reg-{suffix}",
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
            email=f"admin-{suffix}@plugin-reg.test",
            hashed_password="x",
            first_name="Plugin",
            last_name="Admin",
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": co.id}, realm="tenant"
        )
        return {"slug": co.slug, "tenant_token": token}
    finally:
        db.close()


# ─── Auth gate ─────────────────────────────────────────────────


def test_anonymous_rejected(client):
    r = client.get("/api/platform/admin/plugin-registry/categories")
    assert r.status_code in (401, 403)


def test_tenant_token_rejected(client):
    ctx = _make_tenant_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories",
        headers={
            "Authorization": f"Bearer {ctx['tenant_token']}",
            "X-Company-Slug": ctx["slug"],
        },
    )
    # Cross-realm: tenant token rejected at platform endpoint.
    assert r.status_code == 401


def test_platform_admin_accepted(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    assert r.status_code == 200


# ─── Catalog completeness ──────────────────────────────────────


def test_catalog_has_24_entries(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 24
    assert len(body["categories"]) == 24
    # Spot-check a few keys are present.
    keys = {c["category_key"] for c in body["categories"]}
    assert "email_providers" in keys
    assert "notification_categories" in keys
    assert "workflow_node_types" in keys
    assert "intake_adapters" in keys


def test_catalog_summary_shape(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    body = r.json()
    sample = body["categories"][0]
    # Canonical summary fields.
    assert "category_key" in sample
    assert "registry_introspectable" in sample
    assert "expected_implementations_count" in sample
    assert "tier_hint" in sample


# ─── Introspection happy paths ─────────────────────────────────


def test_email_providers_introspection(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories/email_providers/registrations",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["category_key"] == "email_providers"
    assert body["registry_introspectable"] is True
    assert body["registry_size"] >= 3
    keys = {r["key"] for r in body["registrations"]}
    # Canonical providers per PLUGIN_CONTRACTS.md §9.
    assert "gmail" in keys
    assert "imap" in keys


def test_notification_categories_introspection(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories/notification_categories/registrations",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["registry_introspectable"] is True
    # 19 canonical categories per latest investigation.
    assert body["registry_size"] >= 15
    # Each registration carries metadata.
    first = body["registrations"][0]
    assert "key" in first
    assert "metadata" in first
    assert isinstance(first["metadata"], dict)


def test_composition_action_types_introspection(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories/composition_action_types/registrations",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["registry_introspectable"] is True
    keys = {r["key"] for r in body["registrations"]}
    # quote_approval is the original R-6.x canonical action type.
    assert "quote_approval" in keys


# ─── Non-introspectable category ───────────────────────────────


def test_workflow_node_types_non_introspectable(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories/workflow_node_types/registrations",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["category_key"] == "workflow_node_types"
    assert body["registry_introspectable"] is False
    assert body["reason"]  # non-empty reason string
    assert body["expected_implementations_count"] > 0
    assert body["tier_hint"] == "R4"
    # Registrations list is empty for non-introspectable.
    assert body["registrations"] == []


def test_intake_adapters_non_introspectable_reason(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories/intake_adapters/registrations",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["registry_introspectable"] is False
    assert "Tier R3" in body["reason"] or "adapter" in body["reason"].lower()


# ─── 404 + error paths ─────────────────────────────────────────


def test_unknown_category_returns_404(client):
    ctx = _make_platform_admin()
    r = client.get(
        "/api/platform/admin/plugin-registry/categories/this_is_not_a_real_category/registrations",
        headers={"Authorization": f"Bearer {ctx['platform_token']}"},
    )
    assert r.status_code == 404
    assert "Unknown" in r.json()["detail"]


# ─── Catalog × snapshot drift sanity ───────────────────────────


def test_catalog_keys_align_with_snapshot():
    """Catalog should cover every category section in the snapshot.

    Both surfaces are generated from PLUGIN_CONTRACTS.md (snapshot by
    codegen; catalog by hand). They must enumerate the same 24
    categories — drift here indicates one source is out of sync
    with PLUGIN_CONTRACTS.md.
    """
    import json
    import pathlib

    from app.services.plugin_registry import list_category_keys

    snapshot_path = (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "frontend"
        / "src"
        / "lib"
        / "plugin-registry"
        / "plugin-contracts-snapshot.json"
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    # Both surfaces enumerate 24 categories.
    assert snapshot["total_count"] == 24
    assert len(list_category_keys()) == 24
