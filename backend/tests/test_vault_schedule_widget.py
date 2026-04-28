"""Phase W-3d `vault_schedule` widget — backend catalog + service tests.

The vault_schedule widget is the **first workspace-core widget** per
DESIGN_LANGUAGE.md §12.6 — renders the SAME data the scheduling Focus
kanban core consumes with a deliberately abridged interactive surface.
Mode-aware: production mode reads `Delivery` rows, purchase mode reads
`LicenseeTransfer` incoming rows, hybrid composes both.

This file verifies:
  • Catalog registration with required_vertical=["manufacturing"] +
    required_product_line=["vault"] + Glance+Brief+Detail+Deep variants
  • 5-axis filter visibility (FH / cemetery / crematory tenants don't
    see it; manufacturing+vault tenants do)
  • Mode dispatch: TenantProductLine.config["operating_mode"] reads
    correctly across production / purchase / hybrid
  • Production-mode service returns Delivery rows with SalesOrder
    enrichment
  • Purchase-mode service returns LicenseeTransfer incoming rows
  • Hybrid composes both
  • Tenant isolation (cross-tenant data never leaks)
  • Empty-state shapes (no vault enabled, vault enabled with no work)
"""

from __future__ import annotations

import uuid
from datetime import date, time, timedelta
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _seeded() -> Iterator[None]:
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
    product_lines: list[tuple[str, str]] | None = None,
) -> dict:
    """Spin up a tenant + role + user. `product_lines` is an optional
    list of (line_key, operating_mode) tuples — vault uses
    `operating_mode` JSON config per Phase W-3a canon."""
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
            name=f"VS-{suffix}",
            slug=f"vs-{suffix}",
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
            email=f"u-{suffix}@vs.test",
            first_name="VS",
            last_name="Test",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        if product_lines:
            from app.services import product_line_service

            for line_key, mode in product_lines:
                product_line_service.enable_line(
                    db,
                    company_id=co.id,
                    line_key=line_key,
                    operating_mode=mode,
                )
        return {"company_id": co.id, "user_id": user.id}
    finally:
        db.close()


def _make_delivery(
    db_session,
    *,
    tenant_id: str,
    requested_date: date | None,
    primary_assignee_id: str | None = None,
    delivery_type: str = "funeral_vault",
    scheduling_type: str | None = None,
    status: str = "pending",
    order_id: str | None = None,
    attached_to_delivery_id: str | None = None,
    driver_start_time: time | None = None,
    hole_dug_status: str = "unknown",
):
    from app.models.delivery import Delivery

    d = Delivery(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        delivery_type=delivery_type,
        order_id=order_id,
        requested_date=requested_date,
        scheduling_type=scheduling_type,
        primary_assignee_id=primary_assignee_id,
        attached_to_delivery_id=attached_to_delivery_id,
        status=status,
        priority="normal",
        driver_start_time=driver_start_time,
        hole_dug_status=hole_dug_status,
    )
    db_session.add(d)
    db_session.commit()
    return d


def _make_sales_order(
    db_session,
    *,
    tenant_id: str,
    deceased_name: str | None = None,
):
    """Create a SalesOrder + the Customer it FK-points-at. The Customer
    FK is real on sales_orders, so tests that need order enrichment
    must seed both rows."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from app.models.customer import Customer
    from app.models.sales_order import SalesOrder

    customer = Customer(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        name=f"Test Customer {uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(customer)
    db_session.flush()
    o = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        number=f"SO-{uuid.uuid4().hex[:8]}",
        customer_id=customer.id,
        status="confirmed",
        order_date=datetime.now(timezone.utc),
        subtotal=Decimal("100"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total=Decimal("100"),
        deceased_name=deceased_name,
    )
    db_session.add(o)
    db_session.commit()
    return o


# ── Catalog registration ────────────────────────────────────────────


class TestVaultScheduleCatalog:
    def test_widget_registered_glance_brief_detail_deep(self, db_session):
        """Per §12.10: vault_schedule declares Glance + Brief + Detail
        + Deep — the full variant set, since it is a workspace-core
        widget and Detail/Deep are first-class."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "vault_schedule")
            .one()
        )
        variant_ids = {v["variant_id"] for v in row.variants}
        assert variant_ids == {"glance", "brief", "detail", "deep"}, (
            f"vault_schedule must declare full variant set per §12.10; "
            f"got {variant_ids}"
        )
        assert row.default_variant_id == "brief"

    def test_widget_required_vertical_and_product_line(self, db_session):
        """vault_schedule is manufacturing-vertical + vault-line scoped."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "vault_schedule")
            .one()
        )
        assert row.required_vertical == ["manufacturing"]
        assert row.required_product_line == ["vault"]

    def test_widget_supported_surfaces(self, db_session):
        """All four surfaces. Glance variant carries spaces_pin."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "vault_schedule")
            .one()
        )
        for surface in (
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
            "focus_canvas",
        ):
            assert surface in row.supported_surfaces
        # peek_inline excluded — schedule is not entity-scoped
        assert "peek_inline" not in row.supported_surfaces

        glance = next(v for v in row.variants if v["variant_id"] == "glance")
        assert "spaces_pin" in glance["supported_surfaces"]


# ── 5-axis filter visibility ────────────────────────────────────────


class TestFiveAxisFilterVisibility:
    def test_visible_to_manufacturing_with_vault(self, db_session):
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        vs = next(
            (w for w in widgets if w["widget_id"] == "vault_schedule"),
            None,
        )
        assert vs is not None, "vault_schedule invisible to mfg+vault"
        assert vs["is_available"] is True

    def test_invisible_to_manufacturing_without_vault(self, db_session):
        """Manufacturing tenant with no vault line activated —
        vault_schedule should fall through the 5-axis product_line
        filter."""
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=[]
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        vs = next(
            (w for w in widgets if w["widget_id"] == "vault_schedule"),
            None,
        )
        # Either filtered out entirely OR present but is_available=False.
        # Per the canon contract, surfaces typically receive only
        # available widgets; ensure either filtered or unavailable.
        if vs is not None:
            assert vs["is_available"] is False

    @pytest.mark.parametrize(
        "vertical", ["funeral_home", "cemetery", "crematory"]
    )
    def test_invisible_to_other_verticals(self, db_session, vertical):
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_user(vertical=vertical)
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        vs = next(
            (w for w in widgets if w["widget_id"] == "vault_schedule"),
            None,
        )
        if vs is not None:
            assert vs["is_available"] is False, (
                f"vault_schedule should be unavailable to {vertical}"
            )


# ── Mode dispatch ───────────────────────────────────────────────────


class TestModeDispatch:
    def test_production_mode_reads_deliveries(self, db_session):
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        today = date.today()
        # Seed two deliveries: one assigned, one unassigned.
        order = _make_sales_order(
            db_session, tenant_id=ctx["company_id"], deceased_name="Smith"
        )
        d1 = _make_delivery(
            db_session,
            tenant_id=ctx["company_id"],
            requested_date=today,
            primary_assignee_id=ctx["user_id"],
            order_id=order.id,
            driver_start_time=time(9, 0),
        )
        _make_delivery(
            db_session,
            tenant_id=ctx["company_id"],
            requested_date=today,
            primary_assignee_id=None,  # unassigned
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_vault_schedule(
            db_session, user=user, target_date=today
        )

        assert result["operating_mode"] == "production"
        assert result["is_vault_enabled"] is True
        assert result["production"] is not None
        assert result["production"]["total_count"] == 2
        assert result["production"]["assigned_count"] == 1
        assert result["production"]["unassigned_count"] == 1
        assert result["production"]["driver_count"] == 1
        # SalesOrder enrichment: deceased_name flows through to row
        rows = result["production"]["deliveries"]
        smith_row = next(
            r for r in rows if r["delivery_id"] == d1.id
        )
        assert smith_row["deceased_name"] == "Smith"
        # Purchase branch null in production mode
        assert result["purchase"] is None

    def test_purchase_mode_reads_licensee_transfers(self, db_session):
        from app.models.licensee_transfer import LicenseeTransfer
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "purchase")],
        )
        today = date.today()
        # Seed an incoming transfer where this tenant is the area
        # licensee (receiver of the PO).
        supplier_ctx = _make_tenant_user(vertical="manufacturing")
        t = LicenseeTransfer(
            id=str(uuid.uuid4()),
            transfer_number=f"LT-{uuid.uuid4().hex[:6]}",
            home_tenant_id=supplier_ctx["company_id"],  # supplier
            area_tenant_id=ctx["company_id"],  # this tenant receives
            status="accepted",
            service_date=today + timedelta(days=2),
            deceased_name="Jones",
            funeral_home_name="Hopkins FH",
            cemetery_name="Oakwood",
            transfer_items=[],
        )
        db_session.add(t)
        db_session.commit()

        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_vault_schedule(
            db_session, user=user, target_date=today
        )

        assert result["operating_mode"] == "purchase"
        assert result["production"] is None
        assert result["purchase"] is not None
        assert result["purchase"]["total_count"] == 1
        rows = result["purchase"]["transfers"]
        assert rows[0]["deceased_name"] == "Jones"
        assert rows[0]["funeral_home_name"] == "Hopkins FH"

    def test_hybrid_mode_composes_both(self, db_session):
        from app.models.licensee_transfer import LicenseeTransfer
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "hybrid")],
        )
        today = date.today()
        _make_delivery(
            db_session,
            tenant_id=ctx["company_id"],
            requested_date=today,
            primary_assignee_id=ctx["user_id"],
        )
        supplier_ctx = _make_tenant_user(vertical="manufacturing")
        t = LicenseeTransfer(
            id=str(uuid.uuid4()),
            transfer_number=f"LT-{uuid.uuid4().hex[:6]}",
            home_tenant_id=supplier_ctx["company_id"],
            area_tenant_id=ctx["company_id"],
            status="accepted",
            service_date=today + timedelta(days=1),
            deceased_name="Brown",
            transfer_items=[],
        )
        db_session.add(t)
        db_session.commit()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_vault_schedule(
            db_session, user=user, target_date=today
        )
        assert result["operating_mode"] == "hybrid"
        assert result["production"] is not None
        assert result["production"]["total_count"] == 1
        assert result["purchase"] is not None
        assert result["purchase"]["total_count"] == 1

    def test_no_vault_line_returns_disabled_state(self, db_session):
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=[]
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_vault_schedule(db_session, user=user)
        assert result["is_vault_enabled"] is False
        assert result["operating_mode"] is None
        assert result["production"] is None
        assert result["purchase"] is None


# ── Tenant isolation ────────────────────────────────────────────────


class TestTenantIsolation:
    def test_production_mode_only_returns_own_tenant_deliveries(
        self, db_session
    ):
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx_a = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        ctx_b = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        today = date.today()
        # B has 3 deliveries, A has 1
        _make_delivery(
            db_session, tenant_id=ctx_a["company_id"], requested_date=today
        )
        for _ in range(3):
            _make_delivery(
                db_session,
                tenant_id=ctx_b["company_id"],
                requested_date=today,
            )
        user_a = (
            db_session.query(User)
            .filter(User.id == ctx_a["user_id"])
            .one()
        )
        result = get_vault_schedule(
            db_session, user=user_a, target_date=today
        )
        # A only sees its own one delivery
        assert result["production"]["total_count"] == 1

    def test_purchase_mode_only_returns_incoming_for_caller_tenant(
        self, db_session
    ):
        from app.models.licensee_transfer import LicenseeTransfer
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx_a = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "purchase")],
        )
        ctx_b = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "purchase")],
        )
        supplier = _make_tenant_user(vertical="manufacturing")
        today = date.today()
        # Transfer to A (this tenant receives)
        t_a = LicenseeTransfer(
            id=str(uuid.uuid4()),
            transfer_number="LT-A",
            home_tenant_id=supplier["company_id"],
            area_tenant_id=ctx_a["company_id"],
            status="accepted",
            service_date=today + timedelta(days=1),
            deceased_name="A-side",
            transfer_items=[],
        )
        # Transfer to B
        t_b = LicenseeTransfer(
            id=str(uuid.uuid4()),
            transfer_number="LT-B",
            home_tenant_id=supplier["company_id"],
            area_tenant_id=ctx_b["company_id"],
            status="accepted",
            service_date=today + timedelta(days=2),
            deceased_name="B-side",
            transfer_items=[],
        )
        db_session.add_all([t_a, t_b])
        db_session.commit()
        user_a = (
            db_session.query(User)
            .filter(User.id == ctx_a["user_id"])
            .one()
        )
        result = get_vault_schedule(
            db_session, user=user_a, target_date=today
        )
        # A only sees its own incoming transfer
        rows = result["purchase"]["transfers"]
        assert len(rows) == 1
        assert rows[0]["deceased_name"] == "A-side"


# ── Empty states + edge cases ──────────────────────────────────────


class TestEmptyAndEdgeCases:
    def test_production_mode_with_zero_deliveries(self, db_session):
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_vault_schedule(db_session, user=user)
        assert result["is_vault_enabled"] is True
        assert result["operating_mode"] == "production"
        assert result["production"]["total_count"] == 0
        assert result["production"]["deliveries"] == []

    def test_cancelled_deliveries_excluded(self, db_session):
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        today = date.today()
        _make_delivery(
            db_session,
            tenant_id=ctx["company_id"],
            requested_date=today,
            status="cancelled",
        )
        _make_delivery(
            db_session,
            tenant_id=ctx["company_id"],
            requested_date=today,
            status="pending",
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_vault_schedule(
            db_session, user=user, target_date=today
        )
        assert result["production"]["total_count"] == 1

    def test_attached_ancillary_count_populated(self, db_session):
        """Per the SalesOrder vs Delivery investigation: ancillary
        Deliveries can be ATTACHED to a parent vault Delivery for
        ride-along scheduling. The widget surfaces this count so
        operators see "vault delivery + 2 ancillaries on same truck"
        at a glance — pure logistics signal, no commercial nesting."""
        from app.models.user import User
        from app.services.widgets.vault_schedule_service import (
            get_vault_schedule,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        today = date.today()
        parent = _make_delivery(
            db_session,
            tenant_id=ctx["company_id"],
            requested_date=today,
            primary_assignee_id=ctx["user_id"],
        )
        for _ in range(2):
            _make_delivery(
                db_session,
                tenant_id=ctx["company_id"],
                requested_date=today,
                delivery_type="ancillary",
                scheduling_type="ancillary",
                attached_to_delivery_id=parent.id,
                primary_assignee_id=ctx["user_id"],  # inherits parent driver
            )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_vault_schedule(
            db_session, user=user, target_date=today
        )
        # Parent delivery surfaces with attached_ancillary_count=2
        rows = result["production"]["deliveries"]
        parent_row = next(r for r in rows if r["delivery_id"] == parent.id)
        assert parent_row["attached_ancillary_count"] == 2
