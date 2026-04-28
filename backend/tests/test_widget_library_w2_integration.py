"""Widget Library Phase W-2 — integration tests.

End-to-end coverage of the Spaces sidebar widget pin contract via
the real API client + auth. Complements
`test_widget_library_w2_pins.py` (unit-level service tests).

Covers:
  • POST /api/v1/spaces/{id}/pins with pin_type="widget" — happy path,
    cross-vertical rejection, unknown widget rejection, surface
    rejection
  • GET /api/v1/spaces — widget pin surfaces widget_id + variant_id +
    config in the response
  • DELETE /api/v1/spaces/{id}/pins/{pin_id} — remove widget pin
  • GET /api/v1/widgets/available-for-surface?surface=spaces_pin —
    surface-scoped catalog
  • Idempotency: re-pinning same widget returns same pin_id
"""

from __future__ import annotations

import uuid
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    from app.main import app
    return TestClient(app)


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


def _make_tenant_user_token(
    *,
    vertical: str,
    permissions: list[str],
    product_lines: list[str] | None = None,
) -> dict:
    """Create a tenant + user + role + space; return token + space_id.

    Phase W-3a — gained `product_lines` parameter. When supplied, creates
    `TenantProductLine` rows for each line_key in the list. Tests that
    pin product-line-scoped widgets must pass the relevant lines so the
    5-axis filter has data to evaluate against.
    """
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
            name=f"WidgetW2Int-{suffix}",
            slug=f"w2-int-{suffix}",
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
        for p in permissions:
            db.add(RolePermission(role_id=role.id, permission_key=p))

        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@w2int.test",
            first_name="W",
            last_name="Two",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()

        # Phase W-3a — seed TenantProductLine rows when requested.
        # Idempotent via enable_line's existing-row check.
        if product_lines:
            from app.services import product_line_service
            for line_key in product_lines:
                product_line_service.enable_line(
                    db, company_id=co.id, line_key=line_key
                )

        # Create a space the test can pin to.
        sp = create_space(
            db, user=user, name="Test Space", icon="home"
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
            "space_id": sp.space_id,
        }
    finally:
        db.close()


def _auth_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


# ── End-to-end widget pin lifecycle ──────────────────────────────────


class TestWidgetPinLifecycle:
    """Section 12.4 + §12.6a — pin lifecycle from add → fetch → remove,
    enforced through the public API surface (no service-layer
    shortcuts)."""

    def test_pin_unpin_cycle(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=["delivery.view"],
            product_lines=["vault"],
        )

        # POST add widget pin
        add_res = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "scheduling.ancillary-pool",
            },
            headers=_auth_headers(ctx),
        )
        assert add_res.status_code == 201, add_res.text
        pin = add_res.json()
        assert pin["pin_type"] == "widget"
        assert pin["widget_id"] == "scheduling.ancillary-pool"
        # Backend defaults to "glance" per §12.2.
        assert pin["variant_id"] == "glance"
        assert pin["unavailable"] is False
        assert pin["href"] is None  # Sidebar pins don't navigate.
        pin_id = pin["pin_id"]

        # GET space — pin surfaces with widget metadata
        list_res = client.get("/api/v1/spaces", headers=_auth_headers(ctx))
        assert list_res.status_code == 200
        spaces = list_res.json()["spaces"]
        space = next(s for s in spaces if s["space_id"] == ctx["space_id"])
        widget_pins = [p for p in space["pins"] if p["pin_type"] == "widget"]
        assert len(widget_pins) == 1
        assert widget_pins[0]["widget_id"] == "scheduling.ancillary-pool"
        assert widget_pins[0]["variant_id"] == "glance"

        # DELETE pin
        del_res = client.delete(
            f"/api/v1/spaces/{ctx['space_id']}/pins/{pin_id}",
            headers=_auth_headers(ctx),
        )
        assert del_res.status_code == 200, del_res.text

        # Verify removal
        list_res2 = client.get("/api/v1/spaces", headers=_auth_headers(ctx))
        space2 = next(
            s for s in list_res2.json()["spaces"]
            if s["space_id"] == ctx["space_id"]
        )
        widget_pins2 = [p for p in space2["pins"] if p["pin_type"] == "widget"]
        assert widget_pins2 == []

    def test_idempotent_pin(self, client: TestClient):
        """Re-pinning the same widget returns the SAME pin_id (no
        duplicate). Mirrors saved_view + nav_item idempotency."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=["delivery.view"],
            product_lines=["vault"],
        )

        first = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "scheduling.ancillary-pool",
            },
            headers=_auth_headers(ctx),
        )
        assert first.status_code == 201
        first_pin_id = first.json()["pin_id"]

        # Re-add — should return same pin (idempotent).
        # Note: backend's add_pin returns the existing pin without
        # incrementing display_order or creating a duplicate.
        second = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "scheduling.ancillary-pool",
            },
            headers=_auth_headers(ctx),
        )
        assert second.status_code == 201
        assert second.json()["pin_id"] == first_pin_id

    def test_per_instance_config_round_trips(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=["delivery.view"],
            product_lines=["vault"],
        )
        custom_config = {"foo": "bar", "nested": {"key": 42}}

        add_res = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "scheduling.ancillary-pool",
                "config": custom_config,
            },
            headers=_auth_headers(ctx),
        )
        assert add_res.status_code == 201
        assert add_res.json()["config"] == custom_config

        # Re-fetch via list endpoint.
        list_res = client.get("/api/v1/spaces", headers=_auth_headers(ctx))
        space = next(
            s for s in list_res.json()["spaces"]
            if s["space_id"] == ctx["space_id"]
        )
        widget_pin = next(
            p for p in space["pins"] if p["pin_type"] == "widget"
        )
        assert widget_pin["config"] == custom_config

    def test_cross_vertical_widget_rejected(self, client: TestClient):
        """Phase W-3a inversion: a funeral_home tenant cannot pin
        AncillaryPoolPin which is now manufacturing+vault scoped per
        Product Line canon (BRIDGEABLE_MASTER §5.2). Pre-W-3a this test
        verified the opposite direction (manufacturing tenant rejected
        for FH-tagged widget); the canon retag reverses the test
        meaning while preserving cross-vertical rejection coverage."""
        ctx = _make_tenant_user_token(
            vertical="funeral_home",
            permissions=[],
        )

        res = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "scheduling.ancillary-pool",
            },
            headers=_auth_headers(ctx),
        )
        assert res.status_code == 400, res.text
        # Error message mentions the failure mode.
        body = res.json()
        detail = body.get("detail", "").lower()
        assert "not available" in detail or "filter" in detail

    def test_unknown_widget_rejected(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=["delivery.view"],
            product_lines=["vault"],
        )

        res = client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "does.not.exist.anywhere",
            },
            headers=_auth_headers(ctx),
        )
        assert res.status_code == 400
        assert "not found" in res.json()["detail"].lower()


# ── Surface-scoped catalog endpoint ──────────────────────────────────


class TestSurfaceScopedCatalog:
    """GET /widgets/available-for-surface — Phase W-2 sidebar catalog."""

    def test_returns_spaces_pin_widgets(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=["delivery.view"],
            product_lines=["vault"],
        )

        res = client.get(
            "/api/v1/widgets/available-for-surface",
            params={"surface": "spaces_pin"},
            headers=_auth_headers(ctx),
        )
        assert res.status_code == 200
        widgets = res.json()
        assert len(widgets) > 0
        for w in widgets:
            assert "spaces_pin" in w["supported_surfaces"]
        # AncillaryPoolPin should be present.
        ids = {w["widget_id"] for w in widgets}
        assert "scheduling.ancillary-pool" in ids

    def test_unknown_surface_empty(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=["delivery.view"],
            product_lines=["vault"],
        )

        res = client.get(
            "/api/v1/widgets/available-for-surface",
            params={"surface": "nonexistent_surface"},
            headers=_auth_headers(ctx),
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_response_shape_matches_available_endpoint(self, client: TestClient):
        """The frontend WidgetPicker accepts both /widgets/available and
        /widgets/available-for-surface responses interchangeably — they
        must share the same shape."""
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=["delivery.view"],
            product_lines=["vault"],
        )

        res = client.get(
            "/api/v1/widgets/available-for-surface",
            params={"surface": "spaces_pin"},
            headers=_auth_headers(ctx),
        )
        widgets = res.json()
        assert widgets, "expected non-empty response"
        for w in widgets:
            for key in (
                "widget_id",
                "title",
                "description",
                "icon",
                "category",
                "default_size",
                "supported_sizes",
                "default_enabled",
                "default_position",
                "variants",
                "default_variant_id",
                "required_vertical",
                "supported_surfaces",
                "default_surfaces",
                "intelligence_keywords",
                "is_available",
                "unavailable_reason",
            ):
                assert key in w, f"{w['widget_id']} missing field {key!r}"


# ── Mixed pin types coexistence (regression) ─────────────────────────


class TestMixedPinTypes:
    """Verify widget pins coexist with saved_view + nav_item pins —
    regression guard against the new pin_type breaking other shapes."""

    def test_widget_and_nav_pins_coexist(self, client: TestClient):
        ctx = _make_tenant_user_token(
            vertical="manufacturing",
            permissions=["delivery.view"],
            product_lines=["vault"],
        )

        # Add widget pin
        client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "widget",
                "target_id": "scheduling.ancillary-pool",
            },
            headers=_auth_headers(ctx),
        )
        # Add nav pin
        client.post(
            f"/api/v1/spaces/{ctx['space_id']}/pins",
            json={
                "pin_type": "nav_item",
                "target_id": "/cases",
            },
            headers=_auth_headers(ctx),
        )

        # Both surface in /spaces response.
        list_res = client.get("/api/v1/spaces", headers=_auth_headers(ctx))
        space = next(
            s for s in list_res.json()["spaces"]
            if s["space_id"] == ctx["space_id"]
        )
        types = {p["pin_type"] for p in space["pins"]}
        assert "widget" in types
        assert "nav_item" in types
