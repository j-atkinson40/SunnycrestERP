"""Phase V-1b — Vault Overview widget registry + /vault/overview/widgets.

Covers the hub-registry widget_id population + the new metadata
endpoint that maps Vault services → their overview widgets, filtered
by the user's visibility.

Widget rendering itself is covered by Playwright
(`frontend/tests/e2e/vault-v1b-widgets.spec.ts`).
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
    """Each test starts with the default seed, re-run between tests."""
    reset_registry()
    yield
    reset_registry()


class TestVaultHubRegistryWidgetIds:
    def test_documents_service_owns_four_overview_widgets(self):
        services = {s.service_key: s for s in list_services()}
        assert "documents" in services
        assert services["documents"].overview_widget_ids == [
            "vault_recent_documents",
            "vault_pending_signatures",
            "vault_unread_inbox",
            "vault_recent_deliveries",
        ]

    def test_notifications_proto_service_registered_with_widget(self):
        services = {s.service_key: s for s in list_services()}
        assert "notifications" in services
        assert services["notifications"].overview_widget_ids == [
            "vault_notifications"
        ]

    def test_intelligence_has_no_overview_widgets_yet(self):
        services = {s.service_key: s for s in list_services()}
        assert "intelligence" in services
        assert services["intelligence"].overview_widget_ids == []

    def test_all_widget_ids_are_unique_across_services(self):
        seen: set[str] = set()
        for svc in list_services():
            for wid in svc.overview_widget_ids:
                assert wid not in seen, (
                    f"widget_id {wid!r} claimed by multiple services"
                )
                seen.add(wid)

    def test_widget_ids_match_widget_definitions_seed(self):
        """Every widget_id a Vault service claims must exist in the
        widget framework seed with page_contexts including
        'vault_overview'. Otherwise the backend registry is out of
        lock-step with the widget framework."""
        from app.services.widgets.widget_registry import WIDGET_DEFINITIONS

        seeded = {
            d["widget_id"]
            for d in WIDGET_DEFINITIONS
            if "vault_overview" in d.get("page_contexts", [])
        }
        claimed: set[str] = set()
        for svc in list_services():
            claimed.update(svc.overview_widget_ids)

        missing = claimed - seeded
        assert not missing, (
            f"service descriptors claim widget_ids {missing!r} but the "
            f"widget framework seed has no page_contexts=['vault_overview'] "
            f"entries for them"
        )

    def test_registering_custom_service_adds_widget_ids(self):
        list_services()  # seed
        register_service(
            VaultServiceDescriptor(
                service_key="crm",
                display_name="CRM",
                icon="Building2",
                route_prefix="/vault/crm",
                overview_widget_ids=["crm_recent_activity"],
                sort_order=15,
            )
        )
        svcs = {s.service_key: s for s in list_services()}
        assert svcs["crm"].overview_widget_ids == ["crm_recent_activity"]


# ── /vault/overview/widgets endpoint ──────────────────────────────────


class TestOverviewWidgetsEndpoint:
    def test_endpoint_returns_registered_widgets_for_admin(
        self, client, admin_headers
    ):
        resp = client.get(
            "/api/v1/vault/overview/widgets", headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        widget_ids = {w["widget_id"] for w in body["widgets"]}
        # All 5 V-1b widgets should be present for a super-admin.
        assert widget_ids >= {
            "vault_recent_documents",
            "vault_pending_signatures",
            "vault_unread_inbox",
            "vault_recent_deliveries",
            "vault_notifications",
        }

    def test_each_widget_entry_has_required_fields(
        self, client, admin_headers
    ):
        resp = client.get(
            "/api/v1/vault/overview/widgets", headers=admin_headers
        )
        body = resp.json()
        # Known Vault services across all shipped V-1 phases. Update
        # as new services register (V-1d notifications full service,
        # V-1e accounting admin).
        known_services = {
            "documents",
            "intelligence",
            "notifications",
            "crm",  # V-1c
            "accounting",  # V-1e
        }
        for w in body["widgets"]:
            assert set(w.keys()) >= {
                "widget_id",
                "service_key",
                "display_name",
                "default_size",
                "default_position",
                "is_available",
            }
            assert w["service_key"] in known_services

    def test_default_layout_sorted_by_position_and_contains_available_only(
        self, client, admin_headers
    ):
        resp = client.get(
            "/api/v1/vault/overview/widgets", headers=admin_headers
        )
        body = resp.json()
        positions = [e["position"] for e in body["default_layout"]]
        assert positions == sorted(positions)
        # For admin: every default-layout entry should be available.
        widget_by_id = {w["widget_id"]: w for w in body["widgets"]}
        for entry in body["default_layout"]:
            w = widget_by_id[entry["widget_id"]]
            assert w["is_available"] is True

    def test_widgets_unavailable_for_non_admin_without_permission(
        self, client, non_admin_headers
    ):
        """Non-admin + no matching permission: the 5 V-1b widgets have
        no required_permission so all remain available. This test
        verifies the happy path + leaves the gate-filtering edge case
        to the service-level filter in test_vault_v1a_hub.py."""
        resp = client.get(
            "/api/v1/vault/overview/widgets", headers=non_admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        # V-1b widgets have no permission/extension gates, so they
        # show up for any authenticated tenant user.
        ids = {w["widget_id"] for w in body["widgets"]}
        assert "vault_notifications" in ids

    def test_endpoint_requires_auth(self, client):
        resp = client.get("/api/v1/vault/overview/widgets")
        assert resp.status_code in (401, 403)


# ── Widget definitions seeded with vault_overview page_context ────────


class TestWidgetDefinitionsSeed:
    def test_vault_overview_widgets_include_the_five_v1b_ids(self):
        """V-1b invariant: the 5 original widgets exist in
        `page_contexts=['vault_overview']`. Later phases add more
        widgets (V-1c adds 2); assertion is inclusive, not equality."""
        from app.services.widgets.widget_registry import WIDGET_DEFINITIONS

        vault_widgets = [
            d
            for d in WIDGET_DEFINITIONS
            if "vault_overview" in d.get("page_contexts", [])
        ]
        ids = {d["widget_id"] for d in vault_widgets}
        assert ids >= {
            "vault_recent_documents",
            "vault_pending_signatures",
            "vault_unread_inbox",
            "vault_recent_deliveries",
            "vault_notifications",
        }

    def test_widgets_have_sequential_default_positions(self):
        """Default positions on vault_overview should form a
        contiguous 1..N sequence — no gaps, no duplicates. V-1b
        shipped 1..5; V-1c extends to 1..7."""
        from app.services.widgets.widget_registry import WIDGET_DEFINITIONS

        positions = sorted(
            d["default_position"]
            for d in WIDGET_DEFINITIONS
            if "vault_overview" in d.get("page_contexts", [])
        )
        n = len(positions)
        assert positions == list(range(1, n + 1)), (
            f"positions should be 1..{n} sequential — got {positions}"
        )


# ── conftest-ish fixtures (lightweight — same pattern as V-1a) ────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _make_user(*, is_super_admin: bool):
    import uuid
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        slug = f"vaultv1b-{suffix}"
        company = Company(
            id=str(uuid.uuid4()),
            name=f"VaultV1B-{suffix}",
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
            email=f"{'admin' if is_super_admin else 'user'}-{suffix}@v1b.co",
            first_name="V",
            last_name="B",
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
def admin_headers(client):
    ctx = _make_user(is_super_admin=True)
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


@pytest.fixture
def non_admin_headers(client):
    ctx = _make_user(is_super_admin=False)
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }
