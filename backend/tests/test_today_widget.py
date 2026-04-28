"""Phase W-3a `today` widget — backend service + endpoint tests.

Covers:
  • Tenant-vertical-aware breakdown logic
  • Manufacturing+vault breakdown: kanban deliveries + ancillary pool +
    unscheduled count
  • Empty-state behavior for non-manufacturing tenants
  • Per-vertical primary_navigation_target resolution
  • Tenant isolation (no cross-tenant leak)
  • Endpoint auth gate
  • 5-axis filter integration: widget visible to every tenant
    (cross-vertical + cross-line)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Iterator

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _seeded() -> Iterator[None]:
    """Ensure widget catalog is seeded before each test."""
    from app.database import SessionLocal
    from app.services.widgets.widget_registry import seed_widget_definitions

    db = SessionLocal()
    try:
        seed_widget_definitions(db)
        yield
    finally:
        db.close()


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_tenant_user(
    *,
    vertical: str = "manufacturing",
    permissions: list[str] | None = None,
    product_lines: list[str] | None = None,
) -> dict:
    """Spin up a tenant + user. Returns handles for direct service test
    + bearer token for HTTP client tests."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"TodayWidget-{suffix}",
            slug=f"today-{suffix}",
            is_active=True,
            vertical=vertical,
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()

        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Test",
            slug="test",
            is_system=False,
        )
        db.add(role)
        db.flush()
        for p in permissions or []:
            db.add(RolePermission(role_id=role.id, permission_key=p))

        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@today.test",
            first_name="T",
            last_name="W",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()

        if product_lines:
            from app.services import product_line_service
            for line_key in product_lines:
                product_line_service.enable_line(
                    db, company_id=co.id, line_key=line_key
                )

        token = create_access_token(
            {"sub": user.id, "company_id": co.id, "realm": "tenant"}
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "user_id": user.id,
            "vertical": vertical,
            "token": token,
        }
    finally:
        db.close()


def _seed_kanban_delivery(
    db_session,
    *,
    company_id: str,
    requested_date,
    primary_assignee_id: str | None = None,
    status: str = "pending",
    scheduling_type: str | None = None,
    attached_to_delivery_id: str | None = None,
):
    """Seed a Delivery row for testing the kanban / ancillary breakdown.

    Default args produce a kanban (non-ancillary) delivery on the
    given date with NO assignee (counts as unscheduled).
    """
    from app.models.delivery import Delivery

    delivery = Delivery(
        id=str(uuid.uuid4()),
        company_id=company_id,
        delivery_type="vault_delivery",
        requested_date=requested_date,
        status=status,
        scheduling_type=scheduling_type,
        primary_assignee_id=primary_assignee_id,
        attached_to_delivery_id=attached_to_delivery_id,
    )
    db_session.add(delivery)
    db_session.commit()
    return delivery


def _seed_ancillary_pool_item(db_session, *, company_id: str):
    """Seed an ancillary delivery in the pool (date-less + unassigned)."""
    from app.models.delivery import Delivery

    delivery = Delivery(
        id=str(uuid.uuid4()),
        company_id=company_id,
        delivery_type="urn_dropoff",
        requested_date=None,
        status="pending",
        scheduling_type="ancillary",
        ancillary_fulfillment_status="unassigned",
        primary_assignee_id=None,
        attached_to_delivery_id=None,
    )
    db_session.add(delivery)
    db_session.commit()
    return delivery


# ── Service-layer tests ─────────────────────────────────────────────


class TestTodayWidgetService:
    """Pure service-layer coverage of `get_today_summary`."""

    def test_manufacturing_vault_with_kanban_deliveries(self, db_session):
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        # Today's kanban delivery — assigned (counts as kanban, NOT unscheduled)
        _seed_kanban_delivery(
            db_session,
            company_id=ctx["company_id"],
            requested_date=date.today(),
            primary_assignee_id=user.id,
        )
        # Two more kanban deliveries unassigned (kanban + unscheduled)
        _seed_kanban_delivery(
            db_session,
            company_id=ctx["company_id"],
            requested_date=date.today(),
            primary_assignee_id=None,
        )
        _seed_kanban_delivery(
            db_session,
            company_id=ctx["company_id"],
            requested_date=date.today(),
            primary_assignee_id=None,
        )

        result = get_today_summary(db_session, user=user)
        assert result["total_count"] == 3
        # Brief breakdown: vault_deliveries (3) + unscheduled (2)
        keys = {c["key"] for c in result["categories"]}
        assert "vault_deliveries" in keys
        assert "unscheduled" in keys
        assert "ancillary_pool" not in keys  # no ancillary seeded
        assert result["primary_navigation_target"] == "/dispatch"

    def test_manufacturing_vault_with_ancillary_pool(self, db_session):
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        _seed_ancillary_pool_item(db_session, company_id=ctx["company_id"])
        _seed_ancillary_pool_item(db_session, company_id=ctx["company_id"])

        result = get_today_summary(db_session, user=user)
        # Ancillary pool counts in total
        assert result["total_count"] == 2
        ancillary_cat = next(
            (c for c in result["categories"] if c["key"] == "ancillary_pool"),
            None,
        )
        assert ancillary_cat is not None
        assert ancillary_cat["count"] == 2
        assert "2 ancillary items waiting" in ancillary_cat["label"]

    def test_singular_label_for_count_of_one(self, db_session):
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        _seed_ancillary_pool_item(db_session, company_id=ctx["company_id"])

        result = get_today_summary(db_session, user=user)
        ancillary_cat = next(
            c for c in result["categories"] if c["key"] == "ancillary_pool"
        )
        assert "1 ancillary item waiting" in ancillary_cat["label"]
        # Should NOT pluralize when 1.
        assert "items" not in ancillary_cat["label"]

    def test_empty_state_for_manufacturing_vault(self, db_session):
        """No deliveries → empty categories + total 0 + primary target."""
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_today_summary(db_session, user=user)
        assert result["total_count"] == 0
        assert result["categories"] == []
        assert result["primary_navigation_target"] == "/dispatch"
        # Date is today (verification only — service uses tenant TZ)
        assert "date" in result

    def test_manufacturing_without_vault_returns_empty(self, db_session):
        """Manufacturing tenant without vault product line activated
        sees the widget but with empty content (Phase W-3a Phase 1 —
        non-vault lines ship in W-3d)."""
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=[]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        # Even seeding a delivery — no vault line means we don't surface it
        _seed_kanban_delivery(
            db_session,
            company_id=ctx["company_id"],
            requested_date=date.today(),
        )

        result = get_today_summary(db_session, user=user)
        assert result["total_count"] == 0
        assert result["categories"] == []
        # Primary target still /dispatch — manufacturing tenants land
        # there even without vault activated (other lines may exist).
        assert result["primary_navigation_target"] == "/dispatch"

    def test_funeral_home_empty_with_correct_primary_target(self, db_session):
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(vertical="funeral_home", product_lines=[])
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_today_summary(db_session, user=user)
        assert result["total_count"] == 0
        assert result["categories"] == []
        assert result["primary_navigation_target"] == "/cases"

    def test_cemetery_empty_with_correct_primary_target(self, db_session):
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(vertical="cemetery", product_lines=[])
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_today_summary(db_session, user=user)
        assert result["primary_navigation_target"] == "/interments"

    def test_crematory_empty_with_correct_primary_target(self, db_session):
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(vertical="crematory", product_lines=[])
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_today_summary(db_session, user=user)
        assert result["primary_navigation_target"] == "/crematory/schedule"

    def test_cancelled_deliveries_excluded(self, db_session):
        """Cancelled deliveries shouldn't count in today's summary."""
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        _seed_kanban_delivery(
            db_session,
            company_id=ctx["company_id"],
            requested_date=date.today(),
            status="cancelled",
        )
        _seed_kanban_delivery(
            db_session,
            company_id=ctx["company_id"],
            requested_date=date.today(),
            status="pending",
        )

        result = get_today_summary(db_session, user=user)
        # Only 1 active delivery (the pending one); cancelled excluded
        assert result["total_count"] == 1

    def test_yesterday_deliveries_excluded(self, db_session):
        """Deliveries on other days don't bleed into today's count."""
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        # Seed yesterday's delivery — must NOT count
        _seed_kanban_delivery(
            db_session,
            company_id=ctx["company_id"],
            requested_date=date.today() - timedelta(days=1),
        )

        result = get_today_summary(db_session, user=user)
        assert result["total_count"] == 0


# ── Tenant isolation ─────────────────────────────────────────────────


class TestTenantIsolation:
    """The today widget reads delivery data tenant-scoped per
    [BRIDGEABLE_MASTER §3.23](../../BRIDGEABLE_MASTER.md). Cross-tenant
    leaks would be a critical security defect; explicit isolation
    test verifies the company_id filter is load-bearing."""

    def test_delivery_from_another_tenant_excluded(self, db_session):
        from app.models.user import User
        from app.services.widgets.today_widget_service import get_today_summary

        ctx_a = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        ctx_b = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        # Seed delivery for tenant B
        _seed_kanban_delivery(
            db_session,
            company_id=ctx_b["company_id"],
            requested_date=date.today(),
        )
        # Tenant A's user queries — should see ZERO deliveries
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        result = get_today_summary(db_session, user=user_a)
        assert result["total_count"] == 0, (
            f"Tenant A leaked tenant B's delivery! result={result}"
        )


# ── HTTP endpoint tests ─────────────────────────────────────────────


class TestTodayWidgetEndpoint:
    """`GET /api/v1/widget-data/today` end-to-end coverage."""

    def test_endpoint_requires_auth(self):
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        r = client.get("/api/v1/widget-data/today")
        assert r.status_code in (401, 403)

    def test_endpoint_returns_summary_shape(self):
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        r = client.get(
            "/api/v1/widget-data/today",
            headers={
                "Authorization": f"Bearer {ctx['token']}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Shape contract
        assert "date" in body
        assert "total_count" in body
        assert "categories" in body
        assert "primary_navigation_target" in body
        assert isinstance(body["categories"], list)
        assert isinstance(body["total_count"], int)


# ── Widget catalog visibility (5-axis filter integration) ────────────


class TestWidgetCatalogVisibility:
    """Phase W-3a `today` widget should be visible to every tenant
    via the 5-axis filter (cross-vertical + cross-line). Confirms
    catalog registration + axes don't accidentally gate visibility."""

    def test_today_widget_visible_to_manufacturing(self, db_session):
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        today_widget = next(
            (w for w in widgets if w["widget_id"] == "today"), None
        )
        assert today_widget is not None
        assert today_widget["is_available"] is True

    def test_today_widget_visible_to_funeral_home(self, db_session):
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_user(vertical="funeral_home", product_lines=[])
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        today_widget = next(
            (w for w in widgets if w["widget_id"] == "today"), None
        )
        assert today_widget is not None
        assert today_widget["is_available"] is True

    def test_today_widget_declares_glance_and_brief_variants(self, db_session):
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "today")
            .one()
        )
        variant_ids = {v["variant_id"] for v in row.variants}
        assert variant_ids == {"glance", "brief"}
        assert row.default_variant_id == "brief"
        assert row.required_vertical == ["*"]
        assert row.required_product_line == ["*"]
