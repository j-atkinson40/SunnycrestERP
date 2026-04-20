"""Phase V-1a — Bridgeable Vault Hub registry + /api/v1/vault/services.

Covers the new frontend-facing registry that backs the Vault Hub
sidebar. Actual UI rendering is covered by Playwright
(`frontend/tests/e2e/vault-v1a.spec.ts`).

Separate from the existing `test_vault_*.py` suites that exercise
`VaultItem` CRUD — this file is ONLY about the hub-service registry.
"""

from __future__ import annotations

import pytest

from app.services.vault.hub_registry import (
    VaultServiceDescriptor,
    list_services,
    register_service,
    reset_registry,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    """Each test gets a clean registry; the default seed runs on first
    `list_services()` call."""
    reset_registry()
    yield
    reset_registry()


class TestVaultHubRegistry:
    def test_default_seed_registers_documents_and_intelligence(self):
        keys = [s.service_key for s in list_services()]
        assert "documents" in keys
        assert "intelligence" in keys

    def test_sort_order_respected(self):
        services = list_services()
        # Seed gives documents sort_order=10, intelligence=20
        doc_idx = next(
            i for i, s in enumerate(services) if s.service_key == "documents"
        )
        int_idx = next(
            i for i, s in enumerate(services) if s.service_key == "intelligence"
        )
        assert doc_idx < int_idx

    def test_register_adds_new_service(self):
        # Trigger seed.
        list_services()
        register_service(
            VaultServiceDescriptor(
                service_key="crm",
                display_name="CRM",
                icon="Building2",
                route_prefix="/vault/crm",
                sort_order=15,
            )
        )
        keys = [s.service_key for s in list_services()]
        assert "crm" in keys

    def test_register_replaces_existing_key(self):
        """Intentional — extensions / tests override by reusing key."""
        list_services()
        register_service(
            VaultServiceDescriptor(
                service_key="documents",
                display_name="Documents (overridden)",
                icon="Files",
                route_prefix="/vault/documents",
            )
        )
        services = list_services()
        doc = next(s for s in services if s.service_key == "documents")
        assert doc.display_name == "Documents (overridden)"

    def test_route_prefix_shape_is_consistent(self):
        for s in list_services():
            assert s.route_prefix.startswith("/vault/"), (
                f"service {s.service_key!r} has non-/vault prefix "
                f"{s.route_prefix!r}"
            )

    def test_descriptor_has_default_empty_widget_ids(self):
        d = VaultServiceDescriptor(
            service_key="test",
            display_name="Test",
            icon="Boxes",
            route_prefix="/vault/test",
        )
        assert d.overview_widget_ids == []


# ── /api/v1/vault/services endpoint ───────────────────────────────────


class TestVaultServicesEndpoint:
    def test_endpoint_returns_registered_services(self, client, admin_headers):
        """Authenticated admin hitting /vault/services gets both
        V-1a services back in sort order."""
        resp = client.get("/api/v1/vault/services", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        keys = [s["service_key"] for s in body["services"]]
        assert "documents" in keys
        assert "intelligence" in keys
        # documents (sort 10) before intelligence (sort 20)
        assert keys.index("documents") < keys.index("intelligence")

    def test_endpoint_shape(self, client, admin_headers):
        """Each service row has the fields the frontend sidebar reads."""
        resp = client.get("/api/v1/vault/services", headers=admin_headers)
        body = resp.json()
        for s in body["services"]:
            assert set(s.keys()) >= {
                "service_key",
                "display_name",
                "icon",
                "route_prefix",
                "sort_order",
            }
            assert s["route_prefix"].startswith("/vault/")

    def test_endpoint_requires_auth(self, client):
        """Without auth the endpoint rejects."""
        resp = client.get("/api/v1/vault/services")
        assert resp.status_code in (401, 403)

    def test_extension_gate_filters_non_admin(
        self, client, admin_headers, non_admin_headers
    ):
        """A service gated on a missing extension is visible to super
        admin but filtered for a non-admin tenant user."""
        list_services()  # ensure seed
        register_service(
            VaultServiceDescriptor(
                service_key="ext_only",
                display_name="Ext Only",
                icon="Puzzle",
                route_prefix="/vault/ext-only",
                required_extension="nonexistent_extension",
                sort_order=99,
            )
        )
        # Super admin bypasses extension gates.
        admin_resp = client.get(
            "/api/v1/vault/services", headers=admin_headers
        ).json()
        admin_keys = {s["service_key"] for s in admin_resp["services"]}
        assert "ext_only" in admin_keys

        # Non-admin user: extension gate applies.
        non_admin_resp = client.get(
            "/api/v1/vault/services", headers=non_admin_headers
        ).json()
        non_admin_keys = {s["service_key"] for s in non_admin_resp["services"]}
        assert "ext_only" not in non_admin_keys


# ── conftest-ish fixtures ──────────────────────────────────────────────
# These are minimal helpers local to this test file; the larger test
# suites use the project-wide conftest.py. Defining them here keeps
# V-1a's audit surface self-contained.


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


@pytest.fixture
def admin_headers(_bootstrap_admin):
    return {
        "Authorization": f"Bearer {_bootstrap_admin['token']}",
        "X-Company-Slug": _bootstrap_admin["slug"],
    }


@pytest.fixture
def non_admin_headers(_bootstrap_non_admin):
    return {
        "Authorization": f"Bearer {_bootstrap_non_admin['token']}",
        "X-Company-Slug": _bootstrap_non_admin["slug"],
    }


def _make_user(*, is_super_admin: bool):
    """Create a company + admin role + user, return id/token/slug."""
    import uuid
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        slug = f"vaulttest-{suffix}"
        company = Company(
            id=str(uuid.uuid4()),
            name=f"VaultTest-{suffix}",
            slug=slug,
            is_active=True,
        )
        db.add(company)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name="Admin" if is_super_admin else "Employee",
            slug="admin" if is_super_admin else "employee",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=company.id,
            email=f"{'admin' if is_super_admin else 'user'}-{suffix}@vaulttest.com",
            first_name="V",
            last_name="Test",
            hashed_password="x",
            is_active=True,
            is_super_admin=is_super_admin,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": company.id}
        )
        return {
            "user_id": user.id,
            "token": token,
            "company_id": company.id,
            "slug": slug,
        }
    finally:
        db.close()


@pytest.fixture
def _bootstrap_admin(client):
    return _make_user(is_super_admin=True)


@pytest.fixture
def _bootstrap_non_admin(client):
    return _make_user(is_super_admin=False)
