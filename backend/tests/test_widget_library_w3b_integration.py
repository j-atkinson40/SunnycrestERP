"""Phase W-3b cross-surface infrastructure widget cluster — integration tests.

End-to-end coverage of the 2 cross-surface infrastructure widgets
shipped in Commits 1-2:
  • saved_view (config-driven; user-authored widget catalog pattern)
  • briefing (Phase 6 BriefingCard promoted to widget contract)

Verifies:
  • Both widgets in the catalog with correct 5-axis filter (cross-
    vertical + cross-line)
  • Cross-vertical visibility: every vertical sees both widgets
  • Variant declarations match §12.10 (saved_view: Brief+Detail+Deep
    no Glance; briefing: Glance+Brief+Detail no Deep)
  • saved_view excludes spaces_pin (no Glance) — sidebar rejection
    enforced at the Phase W-2 add_pin level
  • briefing supports spaces_pin via Glance — sidebar pinnable
  • Config plumbing — `config` JSONB carries through pin
    persistence + lookup (pre-requisite for both W-3b widgets)
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
            name=f"W3bInt-{suffix}",
            slug=f"w3b-{suffix}",
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
            email=f"u-{suffix}@w3b.test",
            first_name="W3b",
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


W3B_INFRASTRUCTURE_WIDGETS = ["saved_view", "briefing"]


# ── Catalog sanity ──────────────────────────────────────────────────


class TestW3bCatalog:
    """Both W-3b infrastructure widgets registered with correct shape."""

    def test_both_widgets_in_catalog(self, client):
        ctx = _make_tenant_user_token(
            vertical="manufacturing", product_lines=["vault"]
        )
        r = client.get(
            "/api/v1/widgets/available?page_context=pulse",
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 200, r.text
        widget_ids = {w["widget_id"] for w in r.json()}
        for wid in W3B_INFRASTRUCTURE_WIDGETS:
            assert wid in widget_ids, (
                f"W-3b infrastructure widget '{wid}' missing from catalog. "
                f"Got: {widget_ids}"
            )

    def test_both_widgets_visible_to_all_verticals(self, client):
        for vertical in (
            "manufacturing",
            "funeral_home",
            "cemetery",
            "crematory",
        ):
            ctx = _make_tenant_user_token(vertical=vertical)
            r = client.get(
                "/api/v1/widgets/available?page_context=pulse",
                headers=_auth_headers(ctx),
            )
            assert r.status_code == 200, r.text
            widgets_by_id = {w["widget_id"]: w for w in r.json()}
            for wid in W3B_INFRASTRUCTURE_WIDGETS:
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
    """Both W-3b widgets declare cross-vertical + cross-line scope."""

    def test_both_widgets_declare_cross_vertical_and_cross_line(self):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for wid in W3B_INFRASTRUCTURE_WIDGETS:
                row = (
                    db.query(WidgetDefinition)
                    .filter(WidgetDefinition.widget_id == wid)
                    .first()
                )
                assert row is not None, f"{wid} not in catalog"
                assert row.required_vertical == ["*"], (
                    f"{wid} required_vertical={row.required_vertical!r}, "
                    f"expected ['*'] for cross-vertical infrastructure"
                )
                assert row.required_product_line == ["*"], (
                    f"{wid} required_product_line={row.required_product_line!r}, "
                    f"expected ['*'] for cross-line infrastructure"
                )
        finally:
            db.close()


# ── Variant declarations match §12.10 reference ─────────────────────


class TestW3bVariantDeclarations:
    """Per [DESIGN_LANGUAGE.md §12.10](../../DESIGN_LANGUAGE.md):
      • saved_view: Brief + Detail + Deep (NO Glance — saved views
        need at minimum a list to be informative)
      • briefing: Glance + Brief + Detail (NO Deep — briefing detail
        is informationally complete; /briefing page owns deep
        actions per §12.6a)
    """

    @pytest.mark.parametrize(
        "widget_id,expected_variants,expected_default",
        [
            ("saved_view", {"brief", "detail", "deep"}, "detail"),
            ("briefing", {"glance", "brief", "detail"}, "brief"),
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

    def test_saved_view_explicitly_has_no_glance(self):
        """Section 12.10 carves out: saved_view is sidebar-incompatible
        per §12.2 (Glance-required for sidebar)."""
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            row = (
                db.query(WidgetDefinition)
                .filter(WidgetDefinition.widget_id == "saved_view")
                .one()
            )
            variant_ids = {v["variant_id"] for v in row.variants}
            assert "glance" not in variant_ids, (
                "saved_view must NOT declare a Glance variant per §12.10 — "
                "saved views need at minimum a list"
            )
            assert "spaces_pin" not in row.supported_surfaces, (
                "saved_view must NOT declare spaces_pin in "
                "supported_surfaces (§12.2: sidebar requires Glance)"
            )
        finally:
            db.close()

    def test_briefing_explicitly_has_no_deep(self):
        """Briefing detail variant is informationally complete; Deep
        would just re-render /briefing in widget chrome — §12.6a
        keeps heavy actions on the page, not the widget."""
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            row = (
                db.query(WidgetDefinition)
                .filter(WidgetDefinition.widget_id == "briefing")
                .one()
            )
            variant_ids = {v["variant_id"] for v in row.variants}
            assert "deep" not in variant_ids, (
                "briefing must NOT declare a Deep variant per §12.10 — "
                "/briefing page owns heavy actions per §12.6a"
            )
        finally:
            db.close()


# ── Sidebar pin compatibility (the §12.2 + §12.10 rule) ─────────────


class TestSidebarPinCompatibility:
    """saved_view CANNOT be sidebar-pinned (no Glance);
    briefing CAN (declares Glance + spaces_pin)."""

    def test_saved_view_pin_to_sidebar_rejected(self, client):
        """Phase W-2 add_pin surface check rejects saved_view —
        spaces_pin not in supported_surfaces."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing", product_lines=["vault"]
        )
        r = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "saved_view",
                "config": {"view_id": "any-uuid"},
            },
            headers=_auth_headers(ctx),
        )
        # Surface-incompatible widget — Phase W-2 reject
        assert r.status_code in (400, 403, 409, 422), (
            f"Expected sidebar pin rejection; got {r.status_code} {r.text}"
        )

    def test_briefing_pin_to_sidebar_accepted(self, client):
        """briefing declares Glance + spaces_pin, accepted."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing", product_lines=["vault"]
        )
        r = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "briefing",
                "config": {"briefing_type": "morning"},
            },
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201, (
            f"briefing sidebar pin should succeed; "
            f"got {r.status_code} {r.text}"
        )
        pin = r.json()
        assert pin["pin_type"] == "widget"
        assert pin["widget_id"] == "briefing"
        assert pin["variant_id"] == "glance"  # §12.2: sidebar = Glance
        assert pin["unavailable"] is False


# ── Config plumbing — Phase W-3b Commit 0 dependency ────────────────


class TestConfigPlumbingPersistence:
    """Phase W-3b Commit 0 widened the pin contract to carry config
    JSONB end-to-end. Both W-3b widgets depend on config — saved_view
    reads view_id, briefing reads briefing_type. Verify config
    round-trips through pin creation + listing."""

    def test_briefing_config_round_trips_through_pin(self, client):
        """Pin briefing with config={briefing_type: evening}; assert
        listing returns the same config."""
        ctx = _make_tenant_user_token(vertical="manufacturing")
        r = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "briefing",
                "config": {"briefing_type": "evening"},
            },
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201, r.text

        # Re-fetch via list endpoint — confirm config persisted
        r2 = client.get("/api/v1/spaces", headers=_auth_headers(ctx))
        assert r2.status_code == 200
        space = next(
            s for s in r2.json()["spaces"]
            if s["space_id"] == ctx["space_id"]
        )
        widget_pins = [
            p for p in space["pins"]
            if p["pin_type"] == "widget" and p["widget_id"] == "briefing"
        ]
        assert len(widget_pins) == 1
        assert widget_pins[0]["config"] == {"briefing_type": "evening"}

    def test_briefing_config_defaults_when_omitted(self, client):
        """Pin briefing without config; verify pin created with
        empty/default config (frontend reads default 'morning' from
        widget code)."""
        ctx = _make_tenant_user_token(vertical="manufacturing")
        r = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "briefing",
            },
            headers=_auth_headers(ctx),
        )
        assert r.status_code == 201, r.text
        pin = r.json()
        # Config should be empty dict or None — widget reads default
        # from code (briefing_type defaults to "morning")
        assert pin.get("config") in (None, {}, {"briefing_type": "morning"})


# ── Cross-surface coverage ──────────────────────────────────────────


class TestW3bCrossSurfaceCoverage:
    """Both widgets declare dashboard_grid + pulse_grid + focus_canvas;
    only briefing declares spaces_pin (Glance); neither declares
    peek_inline."""

    def test_both_widgets_support_grid_surfaces(self):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for wid in W3B_INFRASTRUCTURE_WIDGETS:
                row = (
                    db.query(WidgetDefinition)
                    .filter(WidgetDefinition.widget_id == wid)
                    .one()
                )
                for surface in (
                    "dashboard_grid",
                    "pulse_grid",
                    "focus_canvas",
                ):
                    assert surface in row.supported_surfaces, (
                        f"{wid} missing {surface} from supported_surfaces"
                    )
        finally:
            db.close()

    def test_neither_widget_declares_peek_inline(self):
        """Both W-3b widgets are not entity-scoped — saved_view is
        view-scoped (multi-row), briefing is per-user. peek_inline
        composes around an entity, neither has one."""
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for wid in W3B_INFRASTRUCTURE_WIDGETS:
                row = (
                    db.query(WidgetDefinition)
                    .filter(WidgetDefinition.widget_id == wid)
                    .one()
                )
                assert "peek_inline" not in row.supported_surfaces, (
                    f"{wid} should NOT declare peek_inline — neither is "
                    f"entity-scoped"
                )
        finally:
            db.close()
