"""Phase W-3d manufacturing per-line widget cluster — integration tests.

End-to-end coverage of the 3 manufacturing per-line widgets shipped
in Commits 1-3:
  • vault_schedule  — workspace-core widget (mode-aware production /
                      purchase / hybrid)
  • line_status     — cross-line health aggregator
  • urn_catalog_status — first extension-gated widget

Verifies:
  • All 3 widgets in the catalog with correct 5-axis filter
    declarations
  • 5-axis filter end-to-end: vertical + product_line + extension
    axes all exercised
  • Variant declarations match §12.10 (vault_schedule: 4 variants;
    line_status: 2; urn_catalog_status: 2)
  • Sidebar pin compatibility per §12.2
  • Workspace-core canon (§12.6) demonstrated by vault_schedule
    surfaces declaration
  • Cross-cluster: invariants hold across W-3a + W-3b + W-3d (no
    regressions to prior clusters)
"""

from __future__ import annotations

import uuid
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


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
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def _make_tenant_user_token(
    *,
    vertical: str = "manufacturing",
    permissions: list[str] | None = None,
    product_lines: list[tuple[str, str]] | None = None,
    extensions: list[str] | None = None,
) -> dict:
    """Spin up tenant + user + space + optional extension activation."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user import User
    from app.services.spaces import create_space

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"W3dInt-{suffix}",
            slug=f"w3d-{suffix}",
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
            email=f"u-{suffix}@w3d.test",
            first_name="W3d",
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
        sp = create_space(db, user=user, name="Test Space", icon="home")
        token = create_access_token(
            {"sub": user.id, "company_id": co.id, "realm": "tenant"}
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "user_id": user.id,
            "token": token,
            "space_id": sp.space_id,
        }
    finally:
        db.close()


def _auth_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


W3D_MANUFACTURING_WIDGETS = [
    "vault_schedule",
    "line_status",
    "urn_catalog_status",
]


# ── Catalog sanity ──────────────────────────────────────────────────


class TestW3dCatalog:
    """All 3 W-3d widgets registered with correct shape."""

    def test_all_three_widgets_in_catalog_for_full_mfg_tenant(self, client):
        """Manufacturing tenant with vault + urn_sales lines + urn_sales
        extension activated sees all three W-3d widgets."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[
                ("vault", "production"),
                ("urn_sales", "purchase"),
            ],
            extensions=["urn_sales"],
        )
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200, r.text
        widget_ids = {w["widget_id"] for w in r.json()}
        for wid in W3D_MANUFACTURING_WIDGETS:
            assert wid in widget_ids, (
                f"W-3d widget '{wid}' missing from catalog. "
                f"Got: {widget_ids}"
            )

    def test_vault_schedule_invisible_to_funeral_home(self, client):
        ctx = _make_tenant_user_token(vertical="funeral_home")
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200
        widgets_by_id = {w["widget_id"]: w for w in r.json()}
        vs = widgets_by_id.get("vault_schedule")
        if vs is not None:
            assert vs["is_available"] is False


# ── 5-axis filter end-to-end (the load-bearing W-3d test) ──────────


class TestFiveAxisFilterEndToEnd:
    """**Phase W-3d activates the full 5-axis filter end-to-end** —
    vertical + product_line + extension axes all exercised. Prior
    clusters (W-3a + W-3b) used `"*"` for everything; W-3d is the
    first cluster with concrete activation on every axis.
    """

    def test_extension_axis_filters_urn_catalog_status_invisible(
        self, client
    ):
        """Tenant with vault line activated but no urn_sales extension
        — urn_catalog_status filtered out by `required_extension` axis.
        First widget in the catalog testing this axis end-to-end."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
            extensions=[],  # no urn_sales
        )
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        widgets_by_id = {w["widget_id"]: w for w in r.json()}
        ucs = widgets_by_id.get("urn_catalog_status")
        if ucs is not None:
            assert ucs["is_available"] is False

    def test_extension_axis_filters_urn_catalog_status_visible(
        self, client
    ):
        """Same tenant + urn_sales extension activated → widget visible."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[
                ("vault", "production"),
                ("urn_sales", "purchase"),
            ],
            extensions=["urn_sales"],
        )
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        widgets_by_id = {w["widget_id"]: w for w in r.json()}
        ucs = widgets_by_id.get("urn_catalog_status")
        assert ucs is not None
        assert ucs["is_available"] is True

    def test_product_line_axis_filters_vault_schedule_without_vault_line(
        self, client
    ):
        ctx = _make_tenant_user_token(
            vertical="manufacturing", product_lines=[]
        )
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        widgets_by_id = {w["widget_id"]: w for w in r.json()}
        vs = widgets_by_id.get("vault_schedule")
        if vs is not None:
            assert vs["is_available"] is False

    def test_vertical_axis_filters_all_three_for_non_mfg(self, client):
        """All 3 W-3d widgets are manufacturing-vertical scoped.
        Other verticals see none of them as available."""
        for vertical in ("funeral_home", "cemetery", "crematory"):
            ctx = _make_tenant_user_token(vertical=vertical)
            r = client.get(
                "/api/v1/widgets/available?page_context=pulse",
                headers=_auth_headers(ctx),
            )
            widgets_by_id = {w["widget_id"]: w for w in r.json()}
            for wid in W3D_MANUFACTURING_WIDGETS:
                w = widgets_by_id.get(wid)
                if w is not None:
                    assert w["is_available"] is False, (
                        f"{wid} should be unavailable to {vertical}"
                    )


# ── Variant declarations match §12.10 reference ─────────────────────


class TestW3dVariantDeclarations:
    """Per [DESIGN_LANGUAGE.md §12.10](../../DESIGN_LANGUAGE.md):
      • vault_schedule: Glance + Brief + Detail + Deep (workspace-core
        canonical reference; full variant set)
      • line_status: Brief + Detail (NO Glance — operational health
        doesn't compress to count)
      • urn_catalog_status: Glance + Brief (catalog management at the
        page; widget surfaces health)
    """

    @pytest.mark.parametrize(
        "widget_id,expected_variants,expected_default",
        [
            (
                "vault_schedule",
                {"glance", "brief", "detail", "deep"},
                "brief",
            ),
            ("line_status", {"brief", "detail"}, "brief"),
            ("urn_catalog_status", {"glance", "brief"}, "brief"),
        ],
    )
    def test_widget_variants_match_section_12_10(
        self, widget_id, expected_variants, expected_default
    ):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            row = (
                db.query(WidgetDefinition)
                .filter(WidgetDefinition.widget_id == widget_id)
                .one()
            )
            actual = {v["variant_id"] for v in row.variants}
            assert actual == expected_variants, (
                f"{widget_id}: actual={actual} != expected={expected_variants}"
            )
            assert row.default_variant_id == expected_default
        finally:
            db.close()

    def test_line_status_explicitly_has_no_glance(self):
        """Regression guard against accidental Glance addition.
        Operational health needs at least Brief context."""
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            row = (
                db.query(WidgetDefinition)
                .filter(WidgetDefinition.widget_id == "line_status")
                .one()
            )
            variant_ids = {v["variant_id"] for v in row.variants}
            assert "glance" not in variant_ids


            assert "spaces_pin" not in row.supported_surfaces, (
                "line_status has no Glance — sidebar requires Glance"
            )
        finally:
            db.close()


# ── Sidebar pin compatibility ──────────────────────────────────────


class TestW3dSidebarPinCompatibility:
    def test_vault_schedule_pin_to_sidebar_accepted(self, client):
        """vault_schedule declares Glance + spaces_pin → accepted."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        r = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "vault_schedule",
            },
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201, r.text
        pin = r.json()
        assert pin["widget_id"] == "vault_schedule"
        assert pin["variant_id"] == "glance"

    def test_line_status_pin_to_sidebar_rejected(self, client):
        """line_status excludes spaces_pin (no Glance) → rejected."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        r = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "line_status",
            },
            headers=_auth_headers(ctx),
        )
        assert r.status_code in (400, 403, 409, 422), (
            f"line_status sidebar pin should reject; got {r.status_code}"
        )

    def test_urn_catalog_status_pin_to_sidebar_accepted(self, client):
        """urn_catalog_status declares Glance + spaces_pin → accepted
        when extension activated."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        r = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "urn_catalog_status",
            },
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201, r.text


# ── Workspace-core canon (§12.6) — vault_schedule surface decl ──


class TestWorkspaceCoreCanon:
    """vault_schedule is the **first workspace-core widget** per
    §12.6. Verifies canonical surface declarations."""

    def test_vault_schedule_supports_all_grid_surfaces(self):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            row = (
                db.query(WidgetDefinition)
                .filter(WidgetDefinition.widget_id == "vault_schedule")
                .one()
            )
            for s in (
                "pulse_grid",
                "spaces_pin",
                "dashboard_grid",
                "focus_canvas",
            ):
                assert s in row.supported_surfaces
            # Workspace-core widgets do NOT compose into peek_inline
            # — schedules are not entity-scoped.
            assert "peek_inline" not in row.supported_surfaces
        finally:
            db.close()

    def test_vault_schedule_has_full_variant_set(self):
        """Workspace-core canon: vault_schedule declares the full
        Glance + Brief + Detail + Deep set because it's a first-
        class workspace-core widget."""
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            row = (
                db.query(WidgetDefinition)
                .filter(WidgetDefinition.widget_id == "vault_schedule")
                .one()
            )
            variant_ids = {v["variant_id"] for v in row.variants}
            assert variant_ids == {"glance", "brief", "detail", "deep"}
        finally:
            db.close()


# ── Cross-cluster regression (W-3a + W-3b + W-3d coexist) ──────────


class TestCrossClusterRegression:
    def test_w3a_widgets_still_present(self, client):
        """W-3d additions don't regress W-3a foundation widgets."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        widget_ids = {w["widget_id"] for w in r.json()}
        for wid in (
            "today",
            "operator_profile",
            "recent_activity",
            "anomalies",
        ):
            assert wid in widget_ids, f"W-3a widget {wid} regressed"

    def test_w3b_widgets_still_present(self, client):
        """W-3d additions don't regress W-3b infrastructure widgets."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        widget_ids = {w["widget_id"] for w in r.json()}
        for wid in ("saved_view", "briefing"):
            assert wid in widget_ids, f"W-3b widget {wid} regressed"


# ── Endpoint contract sanity ──────────────────────────────────────


class TestW3dEndpointContracts:
    def test_vault_schedule_endpoint_responds(self, client):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/widget-data/vault-schedule",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for key in (
            "date",
            "operating_mode",
            "production",
            "purchase",
            "primary_navigation_target",
            "is_vault_enabled",
        ):
            assert key in body

    def test_line_status_endpoint_responds(self, client):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("vault", "production")],
        )
        r = client.get(
            "/api/v1/widget-data/line-status",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for key in (
            "date",
            "lines",
            "total_active_lines",
            "any_attention_needed",
        ):
            assert key in body

    def test_urn_catalog_status_endpoint_responds(self, client):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            product_lines=[("urn_sales", "purchase")],
            extensions=["urn_sales"],
        )
        r = client.get(
            "/api/v1/widget-data/urn-catalog-status",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for key in (
            "total_skus",
            "stocked_skus",
            "drop_ship_skus",
            "low_stock_count",
            "low_stock_items",
            "recent_order_count",
            "navigation_target",
        ):
            assert key in body
