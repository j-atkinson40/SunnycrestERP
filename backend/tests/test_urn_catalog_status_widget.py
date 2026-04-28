"""Phase W-3d `urn_catalog_status` widget — backend catalog + service tests.

**FIRST widget exercising the `required_extension` axis of the
5-axis filter end-to-end.** Phase W-1 implemented extension gating
in `widget_service.get_available_widgets`; W-3a + W-3b cross-vertical
widgets all use `"*"`. This file verifies extension gating WORKS for
the urn_catalog_status widget — visible only to tenants with the
`urn_sales` extension activated.

Verifies:
  • Catalog: Glance + Brief, required_extension="urn_sales"
  • 5-axis filter end-to-end: tenant without urn_sales doesn't see
    widget; tenant with urn_sales does
  • Catalog status aggregation (SKU counts, low-stock, recent orders)
  • Tenant isolation (catalog data scoped to caller's tenant)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
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
    product_lines: list[tuple[str, str]] | None = None,
    extensions: list[str] | None = None,
) -> dict:
    """Spin up tenant + user. `extensions` activates each via the
    TenantExtension table — drives the required_extension axis test."""
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"UC-{suffix}",
            slug=f"uc-{suffix}",
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
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@uc.test",
            first_name="UC",
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
        if extensions:
            from app.models.extension_definition import ExtensionDefinition
            from app.models.tenant_extension import TenantExtension

            for ext_key in extensions:
                # Resolve or create ExtensionDefinition for the key.
                # Real seed runs at startup; tests fast-create.
                ext_def = (
                    db.query(ExtensionDefinition)
                    .filter(ExtensionDefinition.extension_key == ext_key)
                    .first()
                )
                if ext_def is None:
                    ext_def = ExtensionDefinition(
                        id=str(uuid.uuid4()),
                        extension_key=ext_key,
                        module_key=ext_key,
                        display_name=ext_key,
                        description=f"{ext_key} extension",
                    )
                    db.add(ext_def)
                    db.flush()
                te = TenantExtension(
                    id=str(uuid.uuid4()),
                    tenant_id=co.id,
                    extension_key=ext_key,
                    extension_id=ext_def.id,
                    enabled=True,
                    status="active",
                )
                db.add(te)
            db.commit()
        return {"company_id": co.id, "user_id": user.id}
    finally:
        db.close()


def _make_urn_product(
    db_session,
    *,
    tenant_id: str,
    name: str = "Test Urn",
    sku: str = "P-TEST",
    source_type: str = "stocked",
    is_active: bool = True,
    discontinued: bool = False,
):
    from app.models.urn_product import UrnProduct

    p = UrnProduct(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        source_type=source_type,
        is_active=is_active,
        discontinued=discontinued,
    )
    db_session.add(p)
    db_session.commit()
    return p


def _make_urn_inventory(
    db_session,
    *,
    tenant_id: str,
    urn_product_id: str,
    qty_on_hand: int = 10,
    qty_reserved: int = 0,
    reorder_point: int = 5,
):
    from app.models.urn_inventory import UrnInventory

    inv = UrnInventory(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        urn_product_id=urn_product_id,
        qty_on_hand=qty_on_hand,
        qty_reserved=qty_reserved,
        reorder_point=reorder_point,
    )
    db_session.add(inv)
    db_session.commit()
    return inv


# ── Catalog ─────────────────────────────────────────────────────────


class TestUrnCatalogStatusCatalog:
    def test_widget_registered_glance_brief_only(self, db_session):
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "urn_catalog_status")
            .one()
        )
        variant_ids = {v["variant_id"] for v in row.variants}
        assert variant_ids == {"glance", "brief"}, (
            f"urn_catalog_status: Glance + Brief only; got {variant_ids}"
        )

    def test_widget_required_extension_urn_sales(self, db_session):
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "urn_catalog_status")
            .one()
        )
        # First catalog entry exercising required_extension axis
        assert row.required_extension == "urn_sales"
        assert row.required_vertical == ["manufacturing"]
        assert row.required_product_line == ["urn_sales"]


# ── 5-axis filter end-to-end (the load-bearing test) ──────────────


class TestExtensionGatingEndToEnd:
    """**First widget testing the `required_extension` axis.** Phase
    W-3a + W-3b cross-vertical widgets used `"*"`. urn_catalog_status
    is the first concrete activation — verify it actually filters."""

    def test_invisible_to_tenant_without_urn_sales_extension(
        self, db_session
    ):
        """Manufacturing tenant + urn_sales product line activated,
        but extension NOT activated — widget filtered out."""
        from app.models.user import User
        from app.services.widgets.widget_service import (
            get_available_widgets,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("urn_sales", "purchase")],
            extensions=[],  # NO urn_sales extension
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        ucs = next(
            (w for w in widgets if w["widget_id"] == "urn_catalog_status"),
            None,
        )
        # Filter dropped it OR returned with is_available=False
        if ucs is not None:
            assert ucs["is_available"] is False, (
                "urn_catalog_status must be unavailable without "
                "urn_sales extension"
            )

    def test_visible_to_tenant_with_urn_sales_extension(self, db_session):
        """Same tenant + extension activated → widget visible +
        available. The extension axis activated successfully."""
        from app.models.user import User
        from app.services.widgets.widget_service import (
            get_available_widgets,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        ucs = next(
            (w for w in widgets if w["widget_id"] == "urn_catalog_status"),
            None,
        )
        assert ucs is not None, (
            "urn_catalog_status invisible to mfg+urn_sales-line+ext tenant"
        )
        assert ucs["is_available"] is True, (
            f"urn_catalog_status unavailable: {ucs.get('unavailable_reason')!r}"
        )

    def test_invisible_to_tenant_with_extension_but_no_product_line(
        self, db_session
    ):
        """5-axis filter: ALL axes must pass. Extension activated but
        urn_sales product line NOT enabled → widget filtered out by
        the product_line axis."""
        from app.models.user import User
        from app.services.widgets.widget_service import (
            get_available_widgets,
        )

        ctx = _make_tenant_user(
            vertical="manufacturing",
            product_lines=[],  # NO urn_sales line
            extensions=["urn_sales"],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        ucs = next(
            (w for w in widgets if w["widget_id"] == "urn_catalog_status"),
            None,
        )
        if ucs is not None:
            assert ucs["is_available"] is False


# ── Catalog status aggregation ──────────────────────────────────────


class TestCatalogStatusAggregation:
    def test_total_skus_counts_active_non_discontinued(self, db_session):
        from app.models.user import User
        from app.services.widgets.urn_catalog_status_service import (
            get_urn_catalog_status,
        )

        ctx = _make_tenant_user(
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        # 3 active + 1 discontinued + 1 inactive = 3 counted
        for i in range(3):
            _make_urn_product(
                db_session,
                tenant_id=ctx["company_id"],
                sku=f"P-{i}",
                name=f"Active {i}",
            )
        _make_urn_product(
            db_session,
            tenant_id=ctx["company_id"],
            sku="P-discon",
            discontinued=True,
        )
        _make_urn_product(
            db_session,
            tenant_id=ctx["company_id"],
            sku="P-inact",
            is_active=False,
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_urn_catalog_status(db_session, user=user)
        assert result["total_skus"] == 3

    def test_stocked_vs_drop_ship_split(self, db_session):
        from app.models.user import User
        from app.services.widgets.urn_catalog_status_service import (
            get_urn_catalog_status,
        )

        ctx = _make_tenant_user(
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        for i in range(2):
            _make_urn_product(
                db_session,
                tenant_id=ctx["company_id"],
                sku=f"S-{i}",
                source_type="stocked",
            )
        for i in range(5):
            _make_urn_product(
                db_session,
                tenant_id=ctx["company_id"],
                sku=f"D-{i}",
                source_type="drop_ship",
            )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_urn_catalog_status(db_session, user=user)
        assert result["stocked_skus"] == 2
        assert result["drop_ship_skus"] == 5
        assert result["total_skus"] == 7

    def test_low_stock_identification(self, db_session):
        """Stocked SKUs where qty_on_hand <= reorder_point AND
        reorder_point > 0 are flagged. Drop-ship SKUs never flagged."""
        from app.models.user import User
        from app.services.widgets.urn_catalog_status_service import (
            get_urn_catalog_status,
        )

        ctx = _make_tenant_user(
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        # SKU 1: low (qty=2 vs reorder=5)
        p1 = _make_urn_product(
            db_session,
            tenant_id=ctx["company_id"],
            sku="P-low",
            source_type="stocked",
        )
        _make_urn_inventory(
            db_session,
            tenant_id=ctx["company_id"],
            urn_product_id=p1.id,
            qty_on_hand=2,
            reorder_point=5,
        )
        # SKU 2: healthy (qty=20 vs reorder=5)
        p2 = _make_urn_product(
            db_session,
            tenant_id=ctx["company_id"],
            sku="P-ok",
            source_type="stocked",
        )
        _make_urn_inventory(
            db_session,
            tenant_id=ctx["company_id"],
            urn_product_id=p2.id,
            qty_on_hand=20,
            reorder_point=5,
        )
        # SKU 3: no monitoring (reorder_point=0) — never flagged
        p3 = _make_urn_product(
            db_session,
            tenant_id=ctx["company_id"],
            sku="P-unmon",
            source_type="stocked",
        )
        _make_urn_inventory(
            db_session,
            tenant_id=ctx["company_id"],
            urn_product_id=p3.id,
            qty_on_hand=0,
            reorder_point=0,
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_urn_catalog_status(db_session, user=user)
        assert result["low_stock_count"] == 1
        assert len(result["low_stock_items"]) == 1
        assert result["low_stock_items"][0]["sku"] == "P-low"
        assert result["low_stock_items"][0]["qty_on_hand"] == 2
        assert result["low_stock_items"][0]["reorder_point"] == 5

    def test_empty_catalog_returns_zero_counts(self, db_session):
        from app.models.user import User
        from app.services.widgets.urn_catalog_status_service import (
            get_urn_catalog_status,
        )

        ctx = _make_tenant_user(
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_urn_catalog_status(db_session, user=user)
        assert result["total_skus"] == 0
        assert result["stocked_skus"] == 0
        assert result["drop_ship_skus"] == 0
        assert result["low_stock_count"] == 0
        assert result["recent_order_count"] == 0


# ── Tenant isolation ────────────────────────────────────────────────


class TestUrnCatalogTenantIsolation:
    def test_catalog_data_scoped_to_caller_tenant(self, db_session):
        from app.models.user import User
        from app.services.widgets.urn_catalog_status_service import (
            get_urn_catalog_status,
        )

        ctx_a = _make_tenant_user(
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        ctx_b = _make_tenant_user(
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        # B has 5 SKUs, A has 1
        _make_urn_product(
            db_session, tenant_id=ctx_a["company_id"], sku="A-1"
        )
        for i in range(5):
            _make_urn_product(
                db_session,
                tenant_id=ctx_b["company_id"],
                sku=f"B-{i}",
            )
        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        result = get_urn_catalog_status(db_session, user=user_a)
        assert result["total_skus"] == 1, (
            "Cross-tenant catalog data leaked into widget"
        )
