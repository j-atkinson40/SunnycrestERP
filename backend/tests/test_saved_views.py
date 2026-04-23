"""Integration tests — Saved Views full stack.

Covers executor + crud + seed + API + command-bar integration +
cross-tenant masking. One file, multiple test classes, shared
fixtures.

Broken out from the registry-only unit tests at
`test_saved_views_registry.py`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


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
    is_super_admin: bool = False,
    role_slug: str = "admin",
    preset: str | None = "manufacturing",
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
            name=f"SV-{suffix}",
            slug=f"sv-{suffix}",
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
            email=f"u-{suffix}@sv.co",
            first_name="SV",
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
            "role_slug": role_slug,
        }
    finally:
        db.close()


@pytest.fixture
def admin_ctx():
    return _make_tenant_user(is_super_admin=True, role_slug="admin", preset="manufacturing")


@pytest.fixture
def fh_director_ctx():
    return _make_tenant_user(
        is_super_admin=False, role_slug="director", preset="funeral_home"
    )


@pytest.fixture
def other_tenant_user():
    return _make_tenant_user(
        is_super_admin=False, role_slug="admin", preset="manufacturing"
    )


@pytest.fixture
def auth_headers(admin_ctx):
    return {
        "Authorization": f"Bearer {admin_ctx['token']}",
        "X-Company-Slug": admin_ctx["slug"],
    }


def _config_dict(
    *,
    entity_type: str = "sales_order",
    filters: list | None = None,
    sort: list | None = None,
    mode: str = "list",
    owner_user_id: str = "",
    visibility: str = "private",
    shared_with_users: list | None = None,
    shared_with_roles: list | None = None,
    shared_with_tenants: list | None = None,
    cross_tenant_field_visibility: dict | None = None,
) -> dict:
    """Convenience — build a valid JSON config body for the API tests."""
    return {
        "query": {
            "entity_type": entity_type,
            "filters": filters or [],
            "sort": sort or [],
            "grouping": None,
            "limit": None,
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
            "visibility": visibility,
            "shared_with_users": shared_with_users or [],
            "shared_with_roles": shared_with_roles or [],
            "shared_with_tenants": shared_with_tenants or [],
            "cross_tenant_field_visibility": {
                "per_tenant_fields": cross_tenant_field_visibility or {},
            },
        },
        "extras": {},
    }


def _make_sales_order(db, *, company_id: str, number: str, status: str = "draft"):
    from app.models.customer import Customer
    from app.models.sales_order import SalesOrder

    cust = Customer(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=f"Customer {number}",
        is_active=True,
    )
    db.add(cust)
    db.flush()
    so = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=number,
        customer_id=cust.id,
        status=status,
        order_date=datetime.now(timezone.utc),
        subtotal=Decimal("100"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total=Decimal("100"),
    )
    db.add(so)
    db.commit()
    return so


# ── CRUD tests ───────────────────────────────────────────────────────


class TestCrud:
    def test_create_reads_back_as_typed_saved_view(self, db_session, admin_ctx):
        from app.models.user import User
        from app.services.saved_views import (
            SavedViewConfig,
            create_saved_view,
            get_saved_view,
        )

        user = db_session.query(User).filter(User.id == admin_ctx["user_id"]).one()
        config = SavedViewConfig.from_dict(_config_dict())
        sv = create_saved_view(
            db_session, user=user, title="My orders", description="d", config=config,
        )
        fetched = get_saved_view(db_session, user=user, view_id=sv.id)
        assert fetched.title == "My orders"
        assert fetched.config.query.entity_type == "sales_order"
        # Server-side ownership enforcement
        assert fetched.config.permissions.owner_user_id == user.id

    def test_update_title_and_config(self, db_session, admin_ctx):
        from app.models.user import User
        from app.services.saved_views import (
            SavedViewConfig,
            create_saved_view,
            update_saved_view,
        )

        user = db_session.query(User).filter(User.id == admin_ctx["user_id"]).one()
        sv = create_saved_view(
            db_session, user=user, title="v1", description=None,
            config=SavedViewConfig.from_dict(_config_dict()),
        )
        # Change title
        new_cfg = SavedViewConfig.from_dict(_config_dict(entity_type="invoice"))
        updated = update_saved_view(
            db_session, user=user, view_id=sv.id,
            title="v2", config=new_cfg,
        )
        assert updated.title == "v2"
        assert updated.config.query.entity_type == "invoice"

    def test_delete_soft_deletes(self, db_session, admin_ctx):
        from app.models.user import User
        from app.models.vault_item import VaultItem
        from app.services.saved_views import (
            SavedViewConfig,
            SavedViewNotFound,
            create_saved_view,
            delete_saved_view,
            get_saved_view,
        )

        user = db_session.query(User).filter(User.id == admin_ctx["user_id"]).one()
        sv = create_saved_view(
            db_session, user=user, title="del", description=None,
            config=SavedViewConfig.from_dict(_config_dict()),
        )
        delete_saved_view(db_session, user=user, view_id=sv.id)
        with pytest.raises(SavedViewNotFound):
            get_saved_view(db_session, user=user, view_id=sv.id)
        # The row still exists but is_active=False
        row = db_session.query(VaultItem).filter(VaultItem.id == sv.id).one()
        assert row.is_active is False

    def test_duplicate_creates_private_copy_owned_by_caller(
        self, db_session, admin_ctx
    ):
        from app.models.user import User
        from app.services.saved_views import (
            SavedViewConfig,
            create_saved_view,
            duplicate_saved_view,
        )

        user = db_session.query(User).filter(User.id == admin_ctx["user_id"]).one()
        original = create_saved_view(
            db_session, user=user, title="orig", description=None,
            config=SavedViewConfig.from_dict(
                _config_dict(visibility="tenant_public")
            ),
        )
        copy = duplicate_saved_view(
            db_session, user=user, view_id=original.id, new_title="my copy"
        )
        assert copy.id != original.id
        assert copy.title == "my copy"
        # Duplicates are private regardless of source visibility
        assert copy.config.permissions.visibility == "private"
        assert copy.config.permissions.owner_user_id == user.id


# ── Executor tests ──────────────────────────────────────────────────


class TestExecutorFilters:
    def test_eq_filter_matches_status(self, db_session, admin_ctx):
        from app.models.user import User
        from app.services.saved_views import (
            SavedViewConfig, execute,
        )

        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-EXEC-A", status="draft")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-EXEC-B", status="confirmed")

        cfg = SavedViewConfig.from_dict(
            _config_dict(
                entity_type="sales_order",
                filters=[{"field": "status", "operator": "eq", "value": "draft"}],
            )
        )
        result = execute(
            db_session,
            config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        numbers = {r["number"] for r in result.rows}
        assert "SO-EXEC-A" in numbers
        assert "SO-EXEC-B" not in numbers

    def test_in_filter_matches_multiple_statuses(self, db_session, admin_ctx):
        from app.services.saved_views import SavedViewConfig, execute

        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-IN-A", status="draft")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-IN-B", status="confirmed")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-IN-C", status="cancelled")

        cfg = SavedViewConfig.from_dict(
            _config_dict(
                filters=[{"field": "status", "operator": "in", "value": ["draft", "confirmed"]}],
            )
        )
        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        numbers = {r["number"] for r in result.rows}
        assert numbers >= {"SO-IN-A", "SO-IN-B"}
        assert "SO-IN-C" not in numbers

    def test_contains_filter_on_text(self, db_session, admin_ctx):
        from app.services.saved_views import SavedViewConfig, execute

        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-CONTAINS-WILBERT-001")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-CONTAINS-OTHER-001")

        cfg = SavedViewConfig.from_dict(
            _config_dict(
                filters=[{"field": "number", "operator": "contains", "value": "WILBERT"}],
            )
        )
        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        assert any("WILBERT" in r["number"] for r in result.rows)
        assert not any("OTHER" in r["number"] for r in result.rows)

    def test_unknown_field_raises_executor_error(self, db_session, admin_ctx):
        from app.services.saved_views import (
            ExecutorError, SavedViewConfig, execute,
        )

        cfg = SavedViewConfig.from_dict(
            _config_dict(
                filters=[{"field": "nonexistent_field", "operator": "eq", "value": "x"}],
            )
        )
        with pytest.raises(ExecutorError):
            execute(
                db_session, config=cfg,
                caller_company_id=admin_ctx["company_id"],
                owner_company_id=admin_ctx["company_id"],
            )

    def test_is_null_filter(self, db_session, admin_ctx):
        from app.services.saved_views import SavedViewConfig, execute

        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-NULLTEST")

        cfg = SavedViewConfig.from_dict(
            _config_dict(
                # ship_to_name is nullable on SalesOrder; our factory
                # doesn't set it.
                filters=[{"field": "ship_to_name", "operator": "is_null"}],
            )
        )
        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        assert any(r["number"] == "SO-NULLTEST" for r in result.rows)


class TestExecutorTenantIsolation:
    def test_executor_scopes_to_owner_tenant(
        self, db_session, admin_ctx, other_tenant_user
    ):
        """Owner tenant seeds data; a view owned by that tenant
        executed by the owner's user returns only their data even
        when other tenants have rows with similar numbers."""
        from app.services.saved_views import SavedViewConfig, execute

        _make_sales_order(
            db_session, company_id=admin_ctx["company_id"],
            number="SO-TENANT-MINE",
        )
        _make_sales_order(
            db_session, company_id=other_tenant_user["company_id"],
            number="SO-TENANT-THEIRS",
        )

        cfg = SavedViewConfig.from_dict(_config_dict())
        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        numbers = {r["number"] for r in result.rows}
        assert "SO-TENANT-MINE" in numbers
        assert "SO-TENANT-THEIRS" not in numbers


class TestExecutorSort:
    def test_sort_asc_orders_results(self, db_session, admin_ctx):
        from app.services.saved_views import SavedViewConfig, execute

        # Seed in reverse alphabetic order
        for n in ["SO-SORT-C", "SO-SORT-A", "SO-SORT-B"]:
            _make_sales_order(db_session, company_id=admin_ctx["company_id"], number=n)

        cfg = SavedViewConfig.from_dict(
            _config_dict(
                filters=[{"field": "number", "operator": "contains", "value": "SO-SORT-"}],
                sort=[{"field": "number", "direction": "asc"}],
            )
        )
        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        numbers = [r["number"] for r in result.rows if r["number"].startswith("SO-SORT-")]
        assert numbers == sorted(numbers)


class TestExecutorGroup:
    def test_kanban_grouping_buckets_rows(self, db_session, admin_ctx):
        from app.services.saved_views import (
            Grouping, SavedViewConfig, execute,
        )

        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-GRP-D1", status="draft")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-GRP-D2", status="draft")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="SO-GRP-C1", status="confirmed")

        cfg_dict = _config_dict(
            filters=[{"field": "number", "operator": "contains", "value": "SO-GRP"}],
        )
        cfg_dict["query"]["grouping"] = {"field": "status"}
        cfg = SavedViewConfig.from_dict(cfg_dict)

        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        assert result.groups is not None
        assert len(result.groups.get("draft", [])) == 2
        assert len(result.groups.get("confirmed", [])) == 1


class TestExecutorAggregation:
    def test_chart_aggregation_groups_by_x(self, db_session, admin_ctx):
        from app.services.saved_views import SavedViewConfig, execute

        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="CHART-A-1", status="draft")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="CHART-A-2", status="draft")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="CHART-A-3", status="confirmed")

        cfg_dict = _config_dict(mode="chart",
            filters=[{"field": "number", "operator": "contains", "value": "CHART-A-"}],
        )
        cfg_dict["presentation"]["chart_config"] = {
            "chart_type": "bar",
            "x_field": "status",
            "y_field": None,
            "aggregation": "count",
        }
        cfg = SavedViewConfig.from_dict(cfg_dict)
        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        assert result.aggregations is not None
        buckets = {b["x"]: b["y"] for b in result.aggregations["buckets"]}
        assert buckets.get("draft", 0) >= 2
        assert buckets.get("confirmed", 0) >= 1

    def test_stat_aggregation_sum(self, db_session, admin_ctx):
        from app.services.saved_views import SavedViewConfig, execute

        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="STAT-1")
        _make_sales_order(db_session, company_id=admin_ctx["company_id"], number="STAT-2")

        cfg_dict = _config_dict(mode="stat",
            filters=[{"field": "number", "operator": "contains", "value": "STAT-"}],
        )
        cfg_dict["presentation"]["stat_config"] = {
            "metric_field": "total",
            "aggregation": "sum",
            "comparison": None,
        }
        cfg = SavedViewConfig.from_dict(cfg_dict)
        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        assert result.aggregations is not None
        assert result.aggregations["value"] >= 200  # 2 × 100.00


# ── Cross-tenant masking tests ───────────────────────────────────────


class TestCrossTenantMasking:
    def test_caller_from_other_tenant_masks_fields_not_in_whitelist(
        self, db_session, admin_ctx, other_tenant_user
    ):
        """Realistic scenario — an accountant at Tenant B is granted
        access to a sales-order view owned by Tenant A. The sharing
        config says only (id, number, total) are visible to Tenant B;
        customer PII + ship-to must be masked.

        The UI path for cross-tenant sharing is NOT built in Phase 2
        but the masking logic ships and must be correct.
        """
        from app.services.saved_views import MASK_SENTINEL, SavedViewConfig, execute

        owner = admin_ctx
        caller = other_tenant_user

        _make_sales_order(
            db_session, company_id=owner["company_id"],
            number="SO-XT-SENSITIVE",
        )

        # View shared with caller's tenant + field whitelist excludes
        # customer_id and ship_to_name.
        cfg = SavedViewConfig.from_dict(_config_dict(
            filters=[{"field": "number", "operator": "eq", "value": "SO-XT-SENSITIVE"}],
            shared_with_tenants=[caller["company_id"]],
            cross_tenant_field_visibility={
                caller["company_id"]: ["id", "number", "total"],
            },
        ))
        result = execute(
            db_session,
            config=cfg,
            caller_company_id=caller["company_id"],
            owner_company_id=owner["company_id"],
        )
        assert result.permission_mode == "cross_tenant_masked"
        assert "customer_id" in result.masked_fields
        assert "ship_to_name" in result.masked_fields
        assert result.rows, "expected at least one row"
        row = result.rows[0]
        # Whitelisted fields survive
        assert row["number"] == "SO-XT-SENSITIVE"
        assert row["total"] is not None
        # Masked fields replaced with MASK_SENTINEL
        assert row["customer_id"] == MASK_SENTINEL
        assert row["ship_to_name"] == MASK_SENTINEL

    def test_caller_without_tenant_whitelist_gets_everything_masked(
        self, db_session, admin_ctx, other_tenant_user
    ):
        """Cross-tenant caller with no whitelist entry — executor's
        defense in depth masks all fields except id."""
        from app.services.saved_views import MASK_SENTINEL, SavedViewConfig, execute

        owner = admin_ctx
        caller = other_tenant_user

        _make_sales_order(
            db_session, company_id=owner["company_id"],
            number="SO-XT-NO-WHITELIST",
        )
        # No cross_tenant_field_visibility entry for caller's tenant
        cfg = SavedViewConfig.from_dict(_config_dict(
            filters=[{"field": "number", "operator": "eq", "value": "SO-XT-NO-WHITELIST"}],
            shared_with_tenants=[caller["company_id"]],
            cross_tenant_field_visibility={},  # empty whitelist
        ))
        result = execute(
            db_session, config=cfg,
            caller_company_id=caller["company_id"],
            owner_company_id=owner["company_id"],
        )
        assert result.permission_mode == "cross_tenant_masked"
        row = result.rows[0]
        assert row["id"] is not None and row["id"] != MASK_SENTINEL
        # Everything else masked
        for k in ["number", "total", "status", "customer_id", "ship_to_name"]:
            assert row[k] == MASK_SENTINEL, k

    def test_same_tenant_caller_no_masking(self, db_session, admin_ctx):
        from app.services.saved_views import SavedViewConfig, execute

        _make_sales_order(
            db_session, company_id=admin_ctx["company_id"],
            number="SO-SAME-TENANT",
        )
        cfg = SavedViewConfig.from_dict(_config_dict(
            filters=[{"field": "number", "operator": "eq", "value": "SO-SAME-TENANT"}],
            cross_tenant_field_visibility={"some-other-tenant": ["number"]},
        ))
        # Caller == owner → no masking
        result = execute(
            db_session, config=cfg,
            caller_company_id=admin_ctx["company_id"],
            owner_company_id=admin_ctx["company_id"],
        )
        assert result.permission_mode == "full"
        assert result.masked_fields == []


# ── Seed tests ───────────────────────────────────────────────────────


class TestSeed:
    def test_seed_for_new_fh_director_creates_views(
        self, db_session, fh_director_ctx
    ):
        from app.models.user import User
        from app.services.saved_views import (
            list_saved_views_for_user, seed_for_user,
        )

        user = db_session.query(User).filter(User.id == fh_director_ctx["user_id"]).one()
        created = seed_for_user(db_session, user=user)
        assert created >= 2  # director has at least 2 templates
        views = list_saved_views_for_user(db_session, user=user)
        titles = {v.title for v in views}
        assert "My active cases" in titles
        assert "This week's services" in titles

    def test_seed_is_idempotent(self, db_session, fh_director_ctx):
        from app.models.user import User
        from app.services.saved_views import seed_for_user

        user = db_session.query(User).filter(User.id == fh_director_ctx["user_id"]).one()
        first = seed_for_user(db_session, user=user)
        # Refetch — seed may have updated preferences
        db_session.refresh(user)
        second = seed_for_user(db_session, user=user)
        assert first >= 1
        assert second == 0  # idempotent

    def test_seed_records_role_in_preferences(self, db_session, fh_director_ctx):
        from app.models.user import User
        from app.services.saved_views import seed_for_user

        user = db_session.query(User).filter(User.id == fh_director_ctx["user_id"]).one()
        seed_for_user(db_session, user=user)
        db_session.refresh(user)
        seeded = user.preferences.get("saved_views_seeded_for_roles", [])
        assert "director" in seeded


# ── API tests ────────────────────────────────────────────────────────


class TestAPI:
    def test_list_entity_types_returns_8(self, client, auth_headers):
        # Phase B Session 1 added `delivery` as the 8th saved-view
        # entity type alongside fh_case / sales_order / invoice /
        # contact / product / document / vault_item.
        resp = client.get("/api/v1/saved-views/entity-types", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 8
        types = {e["entity_type"] for e in body}
        assert "sales_order" in types
        assert "vault_item" in types
        assert "delivery" in types

    def test_create_and_get(self, client, auth_headers):
        create = client.post(
            "/api/v1/saved-views",
            json={
                "title": "API test",
                "description": "d",
                "config": _config_dict(),
            },
            headers=auth_headers,
        )
        assert create.status_code == 201
        body = create.json()
        view_id = body["id"]
        get = client.get(f"/api/v1/saved-views/{view_id}", headers=auth_headers)
        assert get.status_code == 200
        assert get.json()["title"] == "API test"

    def test_update_config(self, client, auth_headers):
        create = client.post(
            "/api/v1/saved-views",
            json={"title": "upd", "description": None, "config": _config_dict()},
            headers=auth_headers,
        )
        view_id = create.json()["id"]
        update = client.patch(
            f"/api/v1/saved-views/{view_id}",
            json={"title": "updated"},
            headers=auth_headers,
        )
        assert update.status_code == 200
        assert update.json()["title"] == "updated"

    def test_delete_then_404(self, client, auth_headers):
        create = client.post(
            "/api/v1/saved-views",
            json={"title": "doomed", "description": None, "config": _config_dict()},
            headers=auth_headers,
        )
        view_id = create.json()["id"]
        delete = client.delete(f"/api/v1/saved-views/{view_id}", headers=auth_headers)
        assert delete.status_code == 200
        get = client.get(f"/api/v1/saved-views/{view_id}", headers=auth_headers)
        assert get.status_code == 404

    def test_execute_returns_results_envelope(
        self, client, auth_headers, admin_ctx, db_session
    ):
        _make_sales_order(
            db_session, company_id=admin_ctx["company_id"], number="SO-API-EXEC"
        )
        create = client.post(
            "/api/v1/saved-views",
            json={
                "title": "exec",
                "description": None,
                "config": _config_dict(
                    filters=[{"field": "number", "operator": "eq", "value": "SO-API-EXEC"}],
                ),
            },
            headers=auth_headers,
        )
        view_id = create.json()["id"]
        exec_resp = client.post(
            f"/api/v1/saved-views/{view_id}/execute", headers=auth_headers,
        )
        assert exec_resp.status_code == 200
        body = exec_resp.json()
        assert "total_count" in body
        assert "rows" in body
        assert "permission_mode" in body
        assert body["permission_mode"] == "full"
        assert body["total_count"] >= 1

    def test_auth_required(self, client):
        resp = client.post(
            "/api/v1/saved-views",
            json={"title": "x", "description": None, "config": _config_dict()},
        )
        assert resp.status_code in (401, 403)


# ── Command bar integration tests ────────────────────────────────────


class TestCommandBarIntegration:
    def test_saved_view_appears_in_command_bar_results(
        self, client, auth_headers, admin_ctx
    ):
        # Create a view with a distinctive title
        create = client.post(
            "/api/v1/saved-views",
            json={
                "title": "DistinctiveTitleZZZ",
                "description": None,
                "config": _config_dict(),
            },
            headers=auth_headers,
        )
        assert create.status_code == 201

        # Query the command bar for part of the title
        q = client.post(
            "/api/v1/command-bar/query",
            json={"query": "DistinctiveTitle", "max_results": 10},
            headers=auth_headers,
        )
        assert q.status_code == 200
        body = q.json()
        # Find the saved-view result among the merged results
        sv_results = [r for r in body["results"] if r["type"] == "saved_view"]
        assert len(sv_results) >= 1
        top = sv_results[0]
        assert "DistinctiveTitle" in top["primary_label"]
        assert top["url"].startswith("/saved-views/")

    def test_new_view_visible_on_very_next_query_no_caching(
        self, client, auth_headers
    ):
        # Live-query semantics per refinement #6.
        create = client.post(
            "/api/v1/saved-views",
            json={
                "title": "NoCacheFreshZZZ",
                "description": None,
                "config": _config_dict(),
            },
            headers=auth_headers,
        )
        assert create.status_code == 201
        # Immediately query command bar
        q = client.post(
            "/api/v1/command-bar/query",
            json={"query": "NoCacheFresh", "max_results": 10},
            headers=auth_headers,
        )
        assert any(r["type"] == "saved_view" for r in q.json()["results"])

    def test_deleted_view_stops_appearing(self, client, auth_headers):
        create = client.post(
            "/api/v1/saved-views",
            json={
                "title": "ToDeleteZZZ",
                "description": None,
                "config": _config_dict(),
            },
            headers=auth_headers,
        )
        view_id = create.json()["id"]
        client.delete(f"/api/v1/saved-views/{view_id}", headers=auth_headers)
        q = client.post(
            "/api/v1/command-bar/query",
            json={"query": "ToDelete", "max_results": 10},
            headers=auth_headers,
        )
        # The deleted view MUST NOT appear
        assert not any(
            r["type"] == "saved_view" and r["id"] == f"saved_view:{view_id}"
            for r in q.json()["results"]
        )
