"""Phase V-1c — CRM absorption into Vault.

Covers the new tenant-wide activity endpoint, CRM registration in the
Vault hub registry with permission-gated visibility, and the new V-1c
widget definitions (vault_crm_recent_activity + extended at_risk_accounts
page_contexts).

Route migration + frontend widget rendering are covered by Playwright
(`frontend/tests/e2e/vault-v1c-crm.spec.ts`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from app.services.vault.hub_registry import (
    VaultServiceDescriptor,
    list_services,
    register_service,
    reset_registry,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_registry()
    yield
    reset_registry()


# ── Hub registry: CRM service registered with permission gate ────────


class TestCrmServiceInHubRegistry:
    def test_crm_service_seeded(self):
        svcs = {s.service_key: s for s in list_services()}
        assert "crm" in svcs

    def test_crm_requires_customers_view_permission(self):
        svcs = {s.service_key: s for s in list_services()}
        assert svcs["crm"].required_permission == "customers.view"

    def test_crm_has_both_overview_widgets(self):
        svcs = {s.service_key: s for s in list_services()}
        assert svcs["crm"].overview_widget_ids == [
            "vault_crm_recent_activity",
            "at_risk_accounts",
        ]

    def test_crm_sort_order_between_documents_and_intelligence(self):
        svcs = {s.service_key: s for s in list_services()}
        assert svcs["documents"].sort_order < svcs["crm"].sort_order
        assert svcs["crm"].sort_order < svcs["intelligence"].sort_order

    def test_crm_route_prefix(self):
        svcs = {s.service_key: s for s in list_services()}
        assert svcs["crm"].route_prefix == "/vault/crm"


# ── /vault/services: CRM visibility gated by customers.view ──────────


class TestCrmServiceVisibility:
    def test_admin_sees_crm_in_services_list(self, client, admin_headers):
        resp = client.get("/api/v1/vault/services", headers=admin_headers)
        assert resp.status_code == 200
        keys = {s["service_key"] for s in resp.json()["services"]}
        assert "crm" in keys

    def test_non_admin_without_permission_hides_crm(
        self, client, non_admin_headers
    ):
        # Non-admin without customers.view: CRM filtered.
        resp = client.get("/api/v1/vault/services", headers=non_admin_headers)
        assert resp.status_code == 200
        keys = {s["service_key"] for s in resp.json()["services"]}
        assert "crm" not in keys


# ── /vault/overview/widgets: CRM widgets gated + listed ──────────────


class TestCrmOverviewWidgets:
    def test_admin_sees_crm_widgets(self, client, admin_headers):
        resp = client.get(
            "/api/v1/vault/overview/widgets", headers=admin_headers
        )
        assert resp.status_code == 200
        ids = {w["widget_id"] for w in resp.json()["widgets"]}
        assert "vault_crm_recent_activity" in ids
        assert "at_risk_accounts" in ids

    def test_non_admin_without_permission_hides_crm_widgets(
        self, client, non_admin_headers
    ):
        # Non-admin without customers.view: CRM widgets drop out
        # because the owning service is filtered.
        resp = client.get(
            "/api/v1/vault/overview/widgets", headers=non_admin_headers
        )
        assert resp.status_code == 200
        ids = {w["widget_id"] for w in resp.json()["widgets"]}
        assert "vault_crm_recent_activity" not in ids
        assert "at_risk_accounts" not in ids

    def test_widget_service_key_is_crm(self, client, admin_headers):
        resp = client.get(
            "/api/v1/vault/overview/widgets", headers=admin_headers
        )
        ids_to_services = {
            w["widget_id"]: w["service_key"] for w in resp.json()["widgets"]
        }
        assert ids_to_services.get("vault_crm_recent_activity") == "crm"
        assert ids_to_services.get("at_risk_accounts") == "crm"


# ── /vault/activity/recent ───────────────────────────────────────────


class TestRecentActivityEndpoint:
    def test_returns_200_with_empty_list_by_default(
        self, client, admin_headers
    ):
        resp = client.get(
            "/api/v1/vault/activity/recent", headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "activities" in body
        assert isinstance(body["activities"], list)

    def test_returns_tenant_scoped_feed(
        self, client, admin_headers, admin_ctx, db_session
    ):
        """Seed 2 activities in the admin's tenant + 1 in another
        tenant; endpoint must return only the admin's 2."""
        from app.models.activity_log import ActivityLog
        from app.models.company_entity import CompanyEntity

        # Admin's tenant entity
        ent_a = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=admin_ctx["company_id"],
            name="Acme Funeral Home",
            is_active=True,
        )
        # Other tenant entity
        other_company_id = str(uuid.uuid4())
        from app.models.company import Company

        other_co = Company(
            id=other_company_id,
            name="Other Co",
            slug=f"other-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        ent_b = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=other_company_id,
            name="Other Entity",
            is_active=True,
        )
        db_session.add_all([ent_a, other_co, ent_b])
        db_session.flush()

        now = datetime.now(timezone.utc)
        db_session.add_all([
            ActivityLog(
                id=str(uuid.uuid4()),
                tenant_id=admin_ctx["company_id"],
                master_company_id=ent_a.id,
                activity_type="call",
                title="Admin tenant activity 1",
                created_at=now,
            ),
            ActivityLog(
                id=str(uuid.uuid4()),
                tenant_id=admin_ctx["company_id"],
                master_company_id=ent_a.id,
                activity_type="note",
                title="Admin tenant activity 2",
                created_at=now - timedelta(minutes=5),
            ),
            ActivityLog(
                id=str(uuid.uuid4()),
                tenant_id=other_company_id,
                master_company_id=ent_b.id,
                activity_type="call",
                title="Other tenant activity — should NOT be visible",
                created_at=now,
            ),
        ])
        db_session.commit()

        resp = client.get(
            "/api/v1/vault/activity/recent", headers=admin_headers
        )
        assert resp.status_code == 200
        titles = [a["title"] for a in resp.json()["activities"]]
        assert "Admin tenant activity 1" in titles
        assert "Admin tenant activity 2" in titles
        assert not any("should NOT be visible" in t for t in titles)

    def test_limit_parameter_respected(
        self, client, admin_headers, admin_ctx, db_session
    ):
        """Seed 5 activities, call with limit=3, expect exactly 3."""
        from app.models.activity_log import ActivityLog
        from app.models.company_entity import CompanyEntity

        ent = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=admin_ctx["company_id"],
            name="Company Z",
            is_active=True,
        )
        db_session.add(ent)
        db_session.flush()
        now = datetime.now(timezone.utc)
        for i in range(5):
            db_session.add(
                ActivityLog(
                    id=str(uuid.uuid4()),
                    tenant_id=admin_ctx["company_id"],
                    master_company_id=ent.id,
                    activity_type="note",
                    title=f"Limit test {i}",
                    created_at=now - timedelta(minutes=i),
                )
            )
        db_session.commit()
        resp = client.get(
            "/api/v1/vault/activity/recent?limit=3", headers=admin_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()["activities"]) == 3

    def test_since_days_filters_older_activities(
        self, client, admin_headers, admin_ctx, db_session
    ):
        """Seed one 10-day-old + one recent; since_days=3 returns only recent."""
        from app.models.activity_log import ActivityLog
        from app.models.company_entity import CompanyEntity

        ent = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=admin_ctx["company_id"],
            name="Time Filter Co",
            is_active=True,
        )
        db_session.add(ent)
        db_session.flush()
        now = datetime.now(timezone.utc)
        db_session.add_all([
            ActivityLog(
                id=str(uuid.uuid4()),
                tenant_id=admin_ctx["company_id"],
                master_company_id=ent.id,
                activity_type="call",
                title="recent",
                created_at=now - timedelta(hours=1),
            ),
            ActivityLog(
                id=str(uuid.uuid4()),
                tenant_id=admin_ctx["company_id"],
                master_company_id=ent.id,
                activity_type="call",
                title="ancient",
                created_at=now - timedelta(days=10),
            ),
        ])
        db_session.commit()
        resp = client.get(
            "/api/v1/vault/activity/recent?since_days=3",
            headers=admin_headers,
        )
        titles = [a["title"] for a in resp.json()["activities"]]
        assert "recent" in titles
        assert "ancient" not in titles

    def test_joins_company_name(
        self, client, admin_headers, admin_ctx, db_session
    ):
        """Response rows include the owning CompanyEntity's name."""
        from app.models.activity_log import ActivityLog
        from app.models.company_entity import CompanyEntity

        ent = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=admin_ctx["company_id"],
            name="Distinctive Name Inc",
            is_active=True,
        )
        db_session.add(ent)
        db_session.flush()
        db_session.add(
            ActivityLog(
                id=str(uuid.uuid4()),
                tenant_id=admin_ctx["company_id"],
                master_company_id=ent.id,
                activity_type="call",
                title="Join test",
                created_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
        resp = client.get(
            "/api/v1/vault/activity/recent", headers=admin_headers
        )
        rows = resp.json()["activities"]
        assert any(
            r["company_name"] == "Distinctive Name Inc"
            and r["company_id"] == ent.id
            for r in rows
        )

    def test_endpoint_requires_auth(self, client):
        resp = client.get("/api/v1/vault/activity/recent")
        assert resp.status_code in (401, 403)


# ── conftest-ish fixtures ─────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _make_user(*, is_super_admin: bool):
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        slug = f"vaultv1c-{suffix}"
        company = Company(
            id=str(uuid.uuid4()),
            name=f"VaultV1C-{suffix}",
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
            email=f"{'admin' if is_super_admin else 'user'}-{suffix}@v1c.co",
            first_name="V",
            last_name="C",
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
def admin_ctx():
    return _make_user(is_super_admin=True)


@pytest.fixture
def non_admin_ctx():
    return _make_user(is_super_admin=False)


@pytest.fixture
def admin_headers(admin_ctx):
    return {
        "Authorization": f"Bearer {admin_ctx['token']}",
        "X-Company-Slug": admin_ctx["slug"],
    }


@pytest.fixture
def non_admin_headers(non_admin_ctx):
    return {
        "Authorization": f"Bearer {non_admin_ctx['token']}",
        "X-Company-Slug": non_admin_ctx["slug"],
    }


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()
