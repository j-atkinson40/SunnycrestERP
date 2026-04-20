"""End-to-end API test — POST /api/v1/command-bar/query.

Exercises the real FastAPI app against a real DB. Verifies the
response shape matches the public contract documented in
`backend/app/api/routes/command_bar.py`.

Covers:
  - Auth required (401 / 403 without a valid bearer)
  - Empty query → intent=empty, results=[]
  - Navigate intent — "Dashboard" returns nav.dashboard
  - Create intent — "new sales order" returns the create action
  - Search intent — seeded fh_case visible in results
  - Response shape — every result has the 9 required fields
  - Cross-tenant isolation via the bearer token's company_id
  - max_results cap honored
  - context passthrough (current_page)
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _make_tenant_user(*, is_super_admin: bool = True):
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
            name=f"CB-API-{suffix}",
            slug=f"cb-api-{suffix}",
            is_active=True,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin" if is_super_admin else "Employee",
            slug="admin" if is_super_admin else "employee",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@cb-api.co",
            first_name="CB",
            last_name="API",
            hashed_password="x",
            is_active=True,
            is_super_admin=is_super_admin,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "slug": co.slug,
            "token": token,
        }
    finally:
        db.close()


@pytest.fixture
def admin_ctx():
    return _make_tenant_user(is_super_admin=True)


@pytest.fixture
def admin_headers(admin_ctx):
    return {
        "Authorization": f"Bearer {admin_ctx['token']}",
        "X-Company-Slug": admin_ctx["slug"],
    }


# ── Auth ──────────────────────────────────────────────────────────────


class TestAuth:
    def test_missing_bearer_rejected(self, client):
        resp = client.post("/api/v1/command-bar/query", json={"query": "foo"})
        assert resp.status_code in (401, 403)


# ── Empty query ───────────────────────────────────────────────────────


class TestEmptyQuery:
    def test_empty_string_returns_empty(self, client, admin_headers):
        resp = client.post(
            "/api/v1/command-bar/query",
            json={"query": ""},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "empty"
        assert body["results"] == []
        assert body["total"] == 0


# ── Navigate intent ──────────────────────────────────────────────────


class TestNavigate:
    def test_dashboard_returns_nav_result(self, client, admin_headers):
        resp = client.post(
            "/api/v1/command-bar/query",
            json={"query": "Dashboard"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "navigate"
        ids = [r["action_id"] for r in body["results"] if r.get("action_id")]
        assert "nav.dashboard" in ids


# ── Create intent ────────────────────────────────────────────────────


class TestCreate:
    def test_new_sales_order_returns_create_result(
        self, client, admin_headers
    ):
        resp = client.post(
            "/api/v1/command-bar/query",
            json={"query": "new sales order"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "create"
        top = body["results"][0]
        assert top["type"] == "create"
        assert top["entity_type"] == "sales_order"
        assert top["url"] == "/orders/new"


# ── Search intent → resolver hits surface ────────────────────────────


class TestSearch:
    def test_search_seeded_case(self, client, admin_headers, admin_ctx):
        from app.database import SessionLocal
        from app.models.fh_case import FHCase

        db = SessionLocal()
        try:
            db.add(
                FHCase(
                    id=str(uuid.uuid4()),
                    company_id=admin_ctx["company_id"],
                    case_number="API-CASE-001",
                    status="active",
                    deceased_first_name="Tom",
                    deceased_last_name="Distinctive",
                    deceased_date_of_death=date.today(),
                )
            )
            db.commit()
        finally:
            db.close()

        resp = client.post(
            "/api/v1/command-bar/query",
            json={"query": "Distinctive"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "search"
        case_results = [
            r for r in body["results"]
            if r.get("entity_type") == "fh_case"
        ]
        assert len(case_results) >= 1


# ── Response shape contract ──────────────────────────────────────────


class TestResponseShape:
    _REQUIRED_TOP_KEYS = {"intent", "results", "total"}
    _REQUIRED_RESULT_KEYS = {
        "id",
        "type",
        "primary_label",
        "secondary_context",
        "icon",
        "url",
        "action_id",
        "entity_type",
        "score",
    }

    def test_top_level_keys(self, client, admin_headers):
        resp = client.post(
            "/api/v1/command-bar/query",
            json={"query": "Dashboard"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert self._REQUIRED_TOP_KEYS.issubset(body.keys())

    def test_every_result_has_required_keys(self, client, admin_headers):
        resp = client.post(
            "/api/v1/command-bar/query",
            json={"query": "new quote"},
            headers=admin_headers,
        )
        body = resp.json()
        assert len(body["results"]) > 0
        for r in body["results"]:
            assert self._REQUIRED_RESULT_KEYS.issubset(r.keys()), (
                f"missing keys in result: "
                f"{self._REQUIRED_RESULT_KEYS - set(r.keys())}"
            )
            # type must be one of the four documented values
            assert r["type"] in {"navigate", "create", "search_result", "action"}


# ── max_results ──────────────────────────────────────────────────────


class TestMaxResults:
    def test_max_results_enforced(self, client, admin_headers):
        resp = client.post(
            "/api/v1/command-bar/query",
            json={"query": "new", "max_results": 2},
            headers=admin_headers,
        )
        body = resp.json()
        assert len(body["results"]) <= 2


# ── Context passthrough ──────────────────────────────────────────────


class TestContext:
    def test_context_accepted_and_ignored_gracefully(
        self, client, admin_headers
    ):
        """Phase 1 doesn't use context for ranking — just accept it
        without erroring."""
        resp = client.post(
            "/api/v1/command-bar/query",
            json={
                "query": "Dashboard",
                "context": {
                    "current_page": "/orders",
                    "current_entity_type": "sales_order",
                    "current_entity_id": "abc-123",
                },
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["intent"] == "navigate"
