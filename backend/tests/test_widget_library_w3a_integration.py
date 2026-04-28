"""Phase W-3a foundation widget cluster — integration tests.

End-to-end coverage of the 4 cross-vertical foundation widgets shipped
in Commits 2-5:
  • today
  • operator_profile
  • recent_activity
  • anomalies

Verifies:
  • All 4 widgets in the catalog with correct 5-axis filter (cross-
    vertical + cross-line)
  • Cross-vertical visibility: every vertical (manufacturing,
    funeral_home, cemetery, crematory) sees all 4 widgets
  • Each widget pinnable to a Spaces sidebar via the Phase W-2
    `pin_type: "widget"` API
  • Cross-surface availability: catalog respects spaces_pin +
    pulse_grid + dashboard_grid declarations
  • Three of four widgets declare Glance variants (anomalies declares
    Brief + Detail only per §12.10)
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
    product_lines: list[str] | None = None,
) -> dict:
    """Spin up tenant + user + space ready for pin tests."""
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
            name=f"W3aInt-{suffix}",
            slug=f"w3a-{suffix}",
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
            email=f"u-{suffix}@w3a.test",
            first_name="W3a",
            last_name="Test",
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


W3A_FOUNDATION_WIDGETS = ["today", "operator_profile", "recent_activity", "anomalies"]


# ── Catalog sanity ──────────────────────────────────────────────────


class TestW3aCatalog:
    """All 4 W-3a foundation widgets registered with correct shape."""

    def test_all_four_widgets_in_catalog(self, client):
        """Verify all 4 widgets land in the available catalog for a
        manufacturing+vault tenant on the pulse page context."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing", product_lines=["vault"]
        )
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200, r.text
        widget_ids = {w["widget_id"] for w in r.json()}
        for wid in W3A_FOUNDATION_WIDGETS:
            assert wid in widget_ids, (
                f"W-3a foundation widget '{wid}' missing from catalog. "
                f"Got: {widget_ids}"
            )

    def test_all_four_widgets_visible_to_all_verticals(self, client):
        """Cross-vertical visibility: every vertical sees all 4 widgets."""
        for vertical in ("manufacturing", "funeral_home", "cemetery", "crematory"):
            ctx = _make_tenant_user_token(vertical=vertical)
            r = client.get(
                "/api/v1/widgets/available?page_context=pulse",
                headers=_auth_headers(ctx),
            )
            assert r.status_code == 200, r.text
            widgets_by_id = {w["widget_id"]: w for w in r.json()}
            for wid in W3A_FOUNDATION_WIDGETS:
                w = widgets_by_id.get(wid)
                assert w is not None, (
                    f"{wid} invisible to {vertical} tenant"
                )
                assert w["is_available"] is True, (
                    f"{wid} unavailable to {vertical} tenant: "
                    f"reason={w['unavailable_reason']!r}"
                )


# ── 5-axis filter conformance ───────────────────────────────────────


class TestFiveAxisFilterConformance:
    """All 4 W-3a widgets declare cross-vertical + cross-line scope."""

    def test_all_widgets_declare_cross_vertical_and_cross_line(self):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for wid in W3A_FOUNDATION_WIDGETS:
                row = (
                    db.query(WidgetDefinition)
                    .filter(WidgetDefinition.widget_id == wid)
                    .first()
                )
                assert row is not None, f"{wid} not in catalog"
                assert row.required_vertical == ["*"], (
                    f"{wid} required_vertical={row.required_vertical!r}, "
                    f"expected ['*'] for cross-vertical foundation"
                )
                assert row.required_product_line == ["*"], (
                    f"{wid} required_product_line={row.required_product_line!r}, "
                    f"expected ['*'] for cross-line foundation"
                )
        finally:
            db.close()


# ── Variant declarations match §12.10 reference ─────────────────────


class TestVariantDeclarations:
    """Per [DESIGN_LANGUAGE.md §12.10](../../DESIGN_LANGUAGE.md):
      • today: Glance + Brief
      • operator_profile: Glance + Brief
      • recent_activity: Glance + Brief + Detail
      • anomalies: Brief + Detail (NO Glance — needs at least Brief context)
    """

    @pytest.mark.parametrize(
        "widget_id,expected_variants,expected_default",
        [
            ("today", {"glance", "brief"}, "brief"),
            ("operator_profile", {"glance", "brief"}, "brief"),
            ("recent_activity", {"glance", "brief", "detail"}, "brief"),
            ("anomalies", {"brief", "detail"}, "brief"),
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
            actual_variants = {v["variant_id"] for v in row.variants}
            assert actual_variants == expected_variants, (
                f"{widget_id} variant mismatch: actual={actual_variants}, "
                f"expected={expected_variants}"
            )
            assert row.default_variant_id == expected_default
        finally:
            db.close()

    def test_anomalies_explicitly_has_no_glance(self):
        """Section 12.10 explicitly carves out: anomalies need at
        least Brief context. Regression guard against accidental
        Glance addition during future variant work."""
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            row = (
                db.query(WidgetDefinition)
                .filter(WidgetDefinition.widget_id == "anomalies")
                .one()
            )
            variant_ids = {v["variant_id"] for v in row.variants}
            assert "glance" not in variant_ids, (
                "anomalies must NOT declare a Glance variant per "
                "§12.10 — anomalies need at least Brief context"
            )
        finally:
            db.close()


# ── Sidebar pin lifecycle ────────────────────────────────────────────


class TestSidebarPinLifecycle:
    """Each W-3a widget that supports `spaces_pin` surface can be
    pinned to a Spaces sidebar via the Phase W-2 widget pin API."""

    @pytest.mark.parametrize(
        "widget_id",
        ["today", "operator_profile", "recent_activity", "anomalies"],
    )
    def test_widget_pinnable_to_sidebar(self, client, widget_id):
        ctx = _make_tenant_user_token(
            vertical="manufacturing", product_lines=["vault"]
        )
        # Pin the widget
        r = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={"pin_type": "widget", "target_id": widget_id},
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201, (
            f"{widget_id} pin failed: {r.status_code} {r.text}"
        )
        pin = r.json()
        assert pin["pin_type"] == "widget"
        assert pin["widget_id"] == widget_id
        # Sidebar pins always default to glance per §12.2 — even for
        # anomalies which doesn't declare a Glance. The defense-in-depth
        # filter at add_pin time accepts the pin (it has spaces_pin in
        # supported_surfaces); render-time the dispatcher falls through
        # to Brief for anomalies.
        assert pin["variant_id"] == "glance"
        assert pin["unavailable"] is False

        # Re-fetch via list endpoint — confirm persisted
        r2 = client.get("/api/v1/spaces", headers=_auth_headers(ctx))
        space = next(
            s for s in r2.json()["spaces"]
            if s["space_id"] == ctx["space_id"]
        )
        widget_pins = [p for p in space["pins"] if p["pin_type"] == "widget"]
        assert any(p["widget_id"] == widget_id for p in widget_pins)


# ── Cross-surface coverage ──────────────────────────────────────────


class TestCrossSurfaceCoverage:
    """All 4 widgets declare spaces_pin + grid surfaces; canvas
    surface availability per their respective declarations."""

    def test_all_widgets_support_spaces_pin(self):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for wid in W3A_FOUNDATION_WIDGETS:
                row = (
                    db.query(WidgetDefinition)
                    .filter(WidgetDefinition.widget_id == wid)
                    .one()
                )
                assert "spaces_pin" in row.supported_surfaces, (
                    f"{wid} missing spaces_pin from supported_surfaces"
                )
        finally:
            db.close()

    def test_all_widgets_support_dashboard_grid(self):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for wid in W3A_FOUNDATION_WIDGETS:
                row = (
                    db.query(WidgetDefinition)
                    .filter(WidgetDefinition.widget_id == wid)
                    .one()
                )
                assert "dashboard_grid" in row.supported_surfaces, (
                    f"{wid} missing dashboard_grid from supported_surfaces"
                )
        finally:
            db.close()

    def test_all_widgets_support_pulse_grid(self):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for wid in W3A_FOUNDATION_WIDGETS:
                row = (
                    db.query(WidgetDefinition)
                    .filter(WidgetDefinition.widget_id == wid)
                    .one()
                )
                assert "pulse_grid" in row.supported_surfaces, (
                    f"{wid} missing pulse_grid from supported_surfaces"
                )
        finally:
            db.close()


# ── Widget data endpoints contract ──────────────────────────────────


class TestWidgetDataEndpointsResolve:
    """All 4 widgets have working data endpoints (or auth-context-only
    rendering). Verifies the endpoints return shapes the widgets can
    consume."""

    def test_today_endpoint(self, client):
        ctx = _make_tenant_user_token(
            vertical="manufacturing", product_lines=["vault"]
        )
        r = client.get(
            "/api/v1/widget-data/today", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200
        body = r.json()
        for key in (
            "date",
            "total_count",
            "categories",
            "primary_navigation_target",
        ):
            assert key in body

    def test_recent_activity_endpoint(self, client):
        ctx = _make_tenant_user_token()
        r = client.get(
            "/api/v1/vault/activity/recent",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200
        assert "activities" in r.json()

    def test_anomalies_endpoint(self, client):
        ctx = _make_tenant_user_token()
        r = client.get(
            "/api/v1/widget-data/anomalies",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200
        body = r.json()
        for key in ("anomalies", "total_unresolved", "critical_count"):
            assert key in body

    def test_operator_profile_no_endpoint_needed(self, client):
        """operator_profile reads entirely from auth context + spaces
        context client-side. No backend endpoint test — the widget's
        data flow is exercised by the auth + spaces-context tests."""
        # Just confirm operator_profile is in the catalog as proof
        # the widget is registered.
        ctx = _make_tenant_user_token()
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200
        widget_ids = {w["widget_id"] for w in r.json()}
        assert "operator_profile" in widget_ids
