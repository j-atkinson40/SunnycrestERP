"""Saved View Preview endpoint — follow-up 3 tests.

Covers POST /api/v1/saved-views/preview:

  - Happy path: valid transient config returns populated
    SavedViewResult against caller's tenant
  - 100-row cap enforced server-side regardless of caller limit
    (caller passes limit=500 → server caps to 100)
  - Caller limit LESS than 100 is respected (cap is a ceiling, not
    a floor)
  - total_count is the UNCAPPED count (so client can derive
    "showing 100 of 247" from len(rows) + total_count)
  - Permission filtering: preview executes as caller; owner ==
    caller (no cross-tenant masking needed)
  - Tenant isolation: caller in tenant A cannot preview tenant B's
    data even if they guess the entity_type + filters
  - Malformed config returns 400 with helpful detail
  - Unknown filter field returns 400 via ExecutorError translation
  - Auth required
  - Arc telemetry: record() called with "saved_view_preview" key
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest


# ── Fixtures (shaped after test_saved_views.py) ─────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant_user(
    *,
    role_slug: str = "admin",
    preset: str = "manufacturing",
    is_super_admin: bool = True,
):
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
            name=f"SVP-{suffix}",
            slug=f"svp-{suffix}",
            is_active=True,
            vertical=preset,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@svp.co",
            first_name="SVP",
            last_name="User",
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
            "token": token,
            "slug": co.slug,
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-Company-Slug": co.slug,
            },
        }
    finally:
        db.close()


@pytest.fixture
def admin_ctx():
    return _make_tenant_user()


@pytest.fixture
def other_tenant_ctx():
    return _make_tenant_user()


def _config(
    *,
    entity_type: str = "sales_order",
    filters: list | None = None,
    mode: str = "list",
    limit: int | None = None,
    owner_user_id: str = "",
) -> dict:
    return {
        "query": {
            "entity_type": entity_type,
            "filters": filters or [],
            "sort": [],
            "grouping": None,
            "limit": limit,
        },
        "presentation": {
            "mode": mode,
            "table_config": None,
            "card_config": None,
            "kanban_config": None,
            "calendar_config": None,
            "chart_config": None,
            "stat_config": None,
        },
        "permissions": {
            "owner_user_id": owner_user_id,
            "visibility": "private",
            "shared_with_users": [],
            "shared_with_roles": [],
            "shared_with_tenants": [],
            "cross_tenant_field_visibility": {"per_tenant_fields": {}},
        },
        "extras": {},
    }


def _seed_sales_orders(db, *, company_id: str, n: int) -> None:
    from app.models.customer import Customer
    from app.models.sales_order import SalesOrder

    cust = Customer(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=f"Customer {company_id[:6]}",
        is_active=True,
    )
    db.add(cust)
    db.flush()
    for i in range(n):
        so = SalesOrder(
            id=str(uuid.uuid4()),
            company_id=company_id,
            number=f"SO-{company_id[:6]}-{i:04d}",
            customer_id=cust.id,
            status="draft",
            order_date=datetime.now(timezone.utc),
            subtotal=Decimal("100"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
        )
        db.add(so)
    db.commit()


@pytest.fixture(autouse=True)
def _reset_arc_telemetry():
    from app.services.arc_telemetry import reset_for_testing

    reset_for_testing()
    yield
    reset_for_testing()


# ── Happy path ──────────────────────────────────────────────────────


class TestPreviewHappy:
    def test_roundtrip_list_mode(self, client, db_session, admin_ctx):
        _seed_sales_orders(db_session, company_id=admin_ctx["company_id"], n=5)
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": _config()},
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_count"] == 5
        assert len(body["rows"]) == 5
        assert body["permission_mode"] == "full"
        assert body["masked_fields"] == []

    def test_happy_with_filter(self, client, db_session, admin_ctx):
        from app.models.sales_order import SalesOrder

        _seed_sales_orders(db_session, company_id=admin_ctx["company_id"], n=3)
        # Flip one to "sent" so we can filter on status.
        first = (
            db_session.query(SalesOrder)
            .filter(SalesOrder.company_id == admin_ctx["company_id"])
            .first()
        )
        first.status = "sent"
        db_session.commit()

        r = client.post(
            "/api/v1/saved-views/preview",
            json={
                "config": _config(
                    filters=[
                        {
                            "field": "status",
                            "operator": "eq",
                            "value": "sent",
                        }
                    ]
                )
            },
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total_count"] == 1
        assert body["rows"][0]["status"] == "sent"


# ── Row cap ────────────────────────────────────────────────────────


class TestPreviewRowCap:
    def test_caps_at_100_when_caller_requests_500(
        self, client, db_session, admin_ctx
    ):
        # Seed 150 rows so both caller-limit=500 and the 100-row cap
        # are visible in the response.
        _seed_sales_orders(db_session, company_id=admin_ctx["company_id"], n=150)
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": _config(limit=500)},
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["rows"]) == 100, "rows must be capped at 100"
        assert body["total_count"] == 150, (
            "total_count is the full count BEFORE cap"
        )
        # Client derives truncated = rows.length < total_count.
        assert len(body["rows"]) < body["total_count"]

    def test_caps_at_100_when_caller_omits_limit(
        self, client, db_session, admin_ctx
    ):
        _seed_sales_orders(db_session, company_id=admin_ctx["company_id"], n=120)
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": _config(limit=None)},
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["rows"]) == 100
        assert body["total_count"] == 120

    def test_respects_smaller_caller_limit(
        self, client, db_session, admin_ctx
    ):
        """Cap is a ceiling, not a floor. limit=25 → returns 25."""
        _seed_sales_orders(db_session, company_id=admin_ctx["company_id"], n=50)
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": _config(limit=25)},
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["rows"]) == 25
        assert body["total_count"] == 50


# ── Tenant isolation ───────────────────────────────────────────────


class TestPreviewTenantIsolation:
    def test_caller_does_not_see_other_tenant_rows(
        self, client, db_session, admin_ctx, other_tenant_ctx
    ):
        _seed_sales_orders(
            db_session, company_id=other_tenant_ctx["company_id"], n=10
        )
        # Caller previews in their own (empty) tenant.
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": _config()},
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total_count"] == 0
        assert body["rows"] == []
        # permission_mode stays "full" because owner == caller.
        assert body["permission_mode"] == "full"


# ── Error handling ────────────────────────────────────────────────


class TestPreviewErrors:
    def test_unknown_filter_field_400(self, client, admin_ctx):
        r = client.post(
            "/api/v1/saved-views/preview",
            json={
                "config": _config(
                    filters=[
                        {
                            "field": "nonexistent_field",
                            "operator": "eq",
                            "value": "x",
                        }
                    ]
                )
            },
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 400
        assert "nonexistent_field" in r.text.lower() or "unknown field" in r.text.lower()

    def test_unknown_entity_type_400(self, client, admin_ctx):
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": _config(entity_type="nonexistent_entity")},
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 400

    def test_malformed_config_400(self, client, admin_ctx):
        # query sub-dict is missing — Pydantic rejects at body parse.
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": {"presentation": {"mode": "list"}}},
            headers=admin_ctx["headers"],
        )
        assert r.status_code in (400, 422)

    def test_auth_required(self, client):
        r = client.post(
            "/api/v1/saved-views/preview",
            json={"config": _config()},
        )
        assert r.status_code in (401, 403)


# ── Telemetry wrapping ─────────────────────────────────────────────


class TestPreviewTelemetry:
    """Observe `arc_telemetry.record` via its canonical module path.
    The route imports `_arc_t` as a function-local alias so patching
    the route's module doesn't work — patch the source instead."""

    def test_successful_call_records_saved_view_preview(
        self, client, db_session, admin_ctx
    ):
        from app.services import arc_telemetry as _arc_t

        _seed_sales_orders(db_session, company_id=admin_ctx["company_id"], n=2)
        with patch.object(
            _arc_t, "record", wraps=_arc_t.record
        ) as spy:
            r = client.post(
                "/api/v1/saved-views/preview",
                json={"config": _config()},
                headers=admin_ctx["headers"],
            )
        assert r.status_code == 200
        preview_calls = [
            c for c in spy.call_args_list if c.args and c.args[0] == "saved_view_preview"
        ]
        assert len(preview_calls) >= 1
        assert preview_calls[0].kwargs.get("errored") is False

    def test_errored_call_still_records_with_errored_true(
        self, client, admin_ctx
    ):
        from app.services import arc_telemetry as _arc_t

        with patch.object(
            _arc_t, "record", wraps=_arc_t.record
        ) as spy:
            r = client.post(
                "/api/v1/saved-views/preview",
                json={"config": _config(entity_type="nonexistent_entity")},
                headers=admin_ctx["headers"],
            )
        assert r.status_code == 400
        preview_calls = [
            c for c in spy.call_args_list if c.args and c.args[0] == "saved_view_preview"
        ]
        assert len(preview_calls) >= 1
        assert preview_calls[0].kwargs.get("errored") is True


# ── Arc telemetry registration ────────────────────────────────────


class TestPreviewTelemetryRegistration:
    def test_saved_view_preview_in_tracked_endpoints(self):
        from app.services.arc_telemetry import TRACKED_ENDPOINTS

        assert "saved_view_preview" in TRACKED_ENDPOINTS

    def test_snapshot_includes_saved_view_preview_key(self):
        from app.services.arc_telemetry import snapshot

        snap = snapshot()
        endpoint_keys = {e["endpoint"] for e in snap["endpoints"]}
        assert "saved_view_preview" in endpoint_keys
