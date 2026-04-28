"""Widget Library Phase W-2 — Spaces sidebar widget pin tests.

Phase W-2 absorbs widget pins into the Spaces primitive per
DESIGN_LANGUAGE.md §12.5 composition rules. A widget that declares
`spaces_pin` in its supported_surfaces array can be pinned to a
user's Space sidebar; render uses the Glance variant per §12.2
compatibility matrix.

Covers:
  • PinConfig + ResolvedPin schema extensions (variant_id + config)
  • add_pin validation: 4-axis filter at pin time, surface check,
    widget-existence check
  • _resolve_pin widget branch: catalog lookup + 4-axis re-check
    (defense-in-depth) + label/icon resolution
  • API request/response shapes accept and surface widget metadata
  • Cross-vertical isolation: a manufacturing tenant cannot pin a
    funeral_home-vertical widget
  • Idempotency on pin: repeat pin of same widget is a no-op
  • Persistence: variant_id + config round-trip through JSONB
  • Per-instance config storage (e.g. saved_view widget config={view_id})

Test widget: scheduling.ancillary-pool — funeral_home vertical,
spaces_pin in supported_surfaces, glance variant declared.
"""

from __future__ import annotations

import uuid
from typing import Iterator

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _seeded_widgets() -> Iterator[None]:
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
    role_slug: str = "director",
    product_lines: list[str] | None = None,
) -> dict:
    """Spin up a tenant + role + permissions + user. Returns handles.

    Phase W-3a: gained `product_lines` parameter. When supplied, creates
    `TenantProductLine` rows for each line_key in the list. Fixtures
    that test product-line-scoped widgets (e.g. ancillary-pool requires
    vault) must pass `product_lines=["vault"]` so the 5-axis filter
    has data to evaluate against.

    Default vertical flipped from "funeral_home" → "manufacturing"
    because the canonical widget under test (scheduling.ancillary-pool)
    was retagged from FH → manufacturing+vault per the Product Line
    canon. Tests that genuinely need a funeral_home tenant pass
    `vertical="funeral_home"` explicitly.
    """
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
            name=f"WidgetW2-{suffix}",
            slug=f"w2-{suffix}",
            is_active=True,
            vertical=vertical,
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()

        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=False,
        )
        db.add(role)
        db.flush()
        for p in permissions or []:
            db.add(RolePermission(role_id=role.id, permission_key=p))

        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@w2.test",
            first_name="W",
            last_name="Two",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()

        # Phase W-3a — seed TenantProductLine rows. Idempotent via
        # enable_line's existing-row check.
        if product_lines:
            from app.services import product_line_service
            for line_key in product_lines:
                product_line_service.enable_line(
                    db, company_id=co.id, line_key=line_key
                )

        return {
            "user_id": user.id,
            "company_id": co.id,
            "vertical": vertical,
        }
    finally:
        db.close()


def _user_with_space(
    db_session,
    *,
    vertical: str = "manufacturing",
    permissions: list[str] | None = None,
    role_slug: str = "director",
    product_lines: list[str] | None = None,
):
    """Create a tenant user, return (user, space_id) ready to pin to.

    Phase W-3a: gained `product_lines` parameter — passed through to
    `_make_tenant_user` for tests that pin product-line-scoped widgets.
    Default vertical flipped to "manufacturing" + default
    product_lines=["vault"] (when not explicitly overridden) so
    ancillary-pool fixture tests pass without each call site repeating.
    """
    from app.models.user import User
    from app.services.spaces import create_space

    # Default vault product line for manufacturing tenants — the most
    # common test case is "tenant has vault activated, can see/pin
    # ancillary-pool widget". Tests that need a vertical without vault
    # pass product_lines=[] explicitly OR override vertical.
    effective_lines = (
        product_lines if product_lines is not None
        else (["vault"] if vertical == "manufacturing" else [])
    )

    handles = _make_tenant_user(
        vertical=vertical,
        permissions=permissions or ["delivery.view"],
        role_slug=role_slug,
        product_lines=effective_lines,
    )
    user = (
        db_session.query(User)
        .filter(User.id == handles["user_id"])
        .one()
    )
    sp = create_space(
        db_session, user=user, name="Test Space", icon="home"
    )
    return user, sp.space_id


# ── add_pin validation ──────────────────────────────────────────────


class TestAddWidgetPinValidation:
    """add_pin runs the 4-axis filter + surface check + existence
    check at pin time per W-2 defense-in-depth discipline."""

    def test_funeral_home_can_pin_ancillary_pool(self, db_session):
        from app.services.spaces import add_pin

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        pin = add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
        )
        assert pin.pin_type == "widget"
        assert pin.widget_id == "scheduling.ancillary-pool"
        assert pin.target_id == "scheduling.ancillary-pool"
        # Default variant_id is "glance" when omitted.
        assert pin.variant_id == "glance"
        assert pin.unavailable is False
        # Widget label resolves to widget.title.
        assert "Ancillary Pool" in pin.label
        assert pin.href is None  # Sidebar pins don't navigate.

    def test_explicit_variant_id_respected(self, db_session):
        from app.services.spaces import add_pin

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        pin = add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
            variant_id="glance",
        )
        assert pin.variant_id == "glance"

    def test_per_instance_config_persists(self, db_session):
        from app.services.spaces import add_pin, get_spaces_for_user

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        config = {"view_id": "abc123", "color": "warm"}
        pin = add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
            config=config,
        )
        assert pin.config == config

        # Re-fetch via the read path to verify JSONB round-trip.
        db_session.refresh(user)
        spaces = get_spaces_for_user(db_session, user=user)
        widget_pin = next(
            p for sp in spaces for p in sp.pins if p.pin_type == "widget"
        )
        assert widget_pin.config == config

    def test_label_override_respected(self, db_session):
        from app.services.spaces import add_pin

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        pin = add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
            label_override="Pool",
        )
        assert pin.label == "Pool"
        assert pin.widget_id == "scheduling.ancillary-pool"

    def test_unknown_widget_id_rejected(self, db_session):
        from app.services.spaces import add_pin
        from app.services.spaces.types import SpaceError

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        with pytest.raises(SpaceError) as exc_info:
            add_pin(
                db_session,
                user=user,
                space_id=space_id,
                pin_type="widget",
                target_id="does.not.exist",
            )
        assert "not found" in str(exc_info.value).lower()

    def test_funeral_home_cannot_pin_manufacturing_vault_widget(self, db_session):
        """Cross-vertical + cross-line pin attempt is rejected by the
        5-axis filter at pin time.

        Phase W-3a: AncillaryPoolPin retagged from FH → manufacturing+vault
        per Product Line canon (BRIDGEABLE_MASTER §5.2). Inversion of the
        pre-W-3a test: now an FH tenant fails the filter. Even if FH had
        vault product line activated (it doesn't auto-seed for FH), the
        vertical axis would still reject manufacturing-only widgets.
        """
        from app.services.spaces import add_pin
        from app.services.spaces.types import SpaceError

        user, space_id = _user_with_space(
            db_session, vertical="funeral_home",
            permissions=["delivery.view"],
            role_slug="director",
            product_lines=[],  # FH tenant, no vault — confirms inversion
        )
        with pytest.raises(SpaceError) as exc_info:
            add_pin(
                db_session,
                user=user,
                space_id=space_id,
                pin_type="widget",
                target_id="scheduling.ancillary-pool",
            )
        assert "not available" in str(exc_info.value).lower() or \
               "filter" in str(exc_info.value).lower()

    def test_widget_without_spaces_pin_surface_rejected(self, db_session):
        """Verify the surface check rejects widgets that don't declare
        spaces_pin in supported_surfaces.

        Inserts a synthetic widget into the catalog that lacks
        spaces_pin; pinning it must raise SpaceError naming the
        spaces_pin surface requirement.
        """
        import json
        import uuid as _u
        from sqlalchemy import text

        from app.services.spaces import add_pin
        from app.services.spaces.types import SpaceError

        synth_id = f"test.no_sidebar_{_u.uuid4().hex[:8]}"
        # Insert a minimal WidgetDefinition row WITHOUT spaces_pin.
        db_session.execute(
            text(
                """
                INSERT INTO widget_definitions (
                    id, widget_id, title, description, page_contexts,
                    default_size, supported_sizes, category, icon,
                    default_enabled, default_position,
                    variants, default_variant_id, required_vertical,
                    supported_surfaces, default_surfaces,
                    intelligence_keywords
                ) VALUES (
                    :id, :wid, :title, '', :ctx,
                    '1x1', :sizes, 'operations', 'Box',
                    true, 99,
                    :variants, 'brief', :rv,
                    :ss, :ds, :kw
                )
                """
            ),
            {
                "id": str(_u.uuid4()),
                "wid": synth_id,
                "title": "Test Widget Without Sidebar",
                "ctx": json.dumps(["funeral_scheduling_focus"]),
                "sizes": json.dumps(["1x1"]),
                "variants": json.dumps(
                    [
                        {
                            "variant_id": "brief",
                            "density": "focused",
                            "grid_size": {"cols": 1, "rows": 1},
                            "canvas_size": {"width": 200, "height": 200},
                            "supported_surfaces": ["dashboard_grid"],
                        }
                    ]
                ),
                "rv": json.dumps(["*"]),
                "ss": json.dumps(["dashboard_grid"]),
                "ds": json.dumps(["dashboard_grid"]),
                "kw": json.dumps([]),
            },
        )
        db_session.commit()

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=[],
        )
        try:
            with pytest.raises(SpaceError) as exc_info:
                add_pin(
                    db_session,
                    user=user,
                    space_id=space_id,
                    pin_type="widget",
                    target_id=synth_id,
                )
            assert "spaces_pin" in str(exc_info.value)
        finally:
            db_session.execute(
                text("DELETE FROM widget_definitions WHERE widget_id = :wid"),
                {"wid": synth_id},
            )
            db_session.commit()

    def test_idempotent_repeat_pin(self, db_session):
        """Pinning the same widget twice returns the existing pin
        without creating a duplicate. Mirrors saved_view + nav_item
        idempotency contract."""
        from app.services.spaces import add_pin, get_space

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        first = add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
        )
        db_session.refresh(user)
        second = add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
        )
        assert first.pin_id == second.pin_id

        db_session.refresh(user)
        sp = get_space(db_session, user=user, space_id=space_id)
        widget_pins = [p for p in sp.pins if p.pin_type == "widget"]
        assert len(widget_pins) == 1


# ── _resolve_pin widget branch ──────────────────────────────────────


class TestResolveWidgetPin:
    """The widget branch of _resolve_pin runs the 4-axis filter as
    defense-in-depth at fetch time — the user's role / vertical /
    extension state may have changed since the pin was created."""

    def test_visible_widget_resolves_with_metadata(self, db_session):
        from app.services.spaces import add_pin, get_spaces_for_user

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
        )

        db_session.refresh(user)
        spaces = get_spaces_for_user(db_session, user=user)
        widget_pin = next(
            p for sp in spaces for p in sp.pins if p.pin_type == "widget"
        )

        assert widget_pin.unavailable is False
        assert widget_pin.widget_id == "scheduling.ancillary-pool"
        assert widget_pin.variant_id == "glance"
        # icon and label resolved from widget definition.
        assert widget_pin.icon == "Inbox"
        assert "Ancillary Pool" in widget_pin.label
        # Sidebar pins don't navigate to a route.
        assert widget_pin.href is None

    def test_widget_removed_from_catalog_renders_unavailable(self, db_session):
        """When the widget definition is deleted (e.g. extension
        uninstall removed it), the pin renders unavailable instead
        of crashing."""
        from sqlalchemy import text

        from app.services.spaces import add_pin, get_spaces_for_user

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
        )

        # Now delete the catalog row to simulate uninstall.
        db_session.execute(
            text(
                "DELETE FROM widget_definitions "
                "WHERE widget_id = 'scheduling.ancillary-pool'"
            )
        )
        db_session.commit()

        try:
            db_session.refresh(user)
            spaces = get_spaces_for_user(db_session, user=user)
            widget_pin = next(
                p for sp in spaces for p in sp.pins if p.pin_type == "widget"
            )
            assert widget_pin.unavailable is True
            assert widget_pin.href is None
            assert widget_pin.widget_id == "scheduling.ancillary-pool"
        finally:
            # Re-seed for follow-on tests.
            from app.services.widgets.widget_registry import seed_widget_definitions
            seed_widget_definitions(db_session)

    def test_user_lost_vertical_access_renders_unavailable(self, db_session):
        """Pin survives a tenant vertical change but renders
        unavailable. Migration history contract: a pin should not be
        deleted just because access lapsed; admin can decide.

        Phase W-3a: scenario flipped — start as manufacturing+vault
        (can pin), then flip vertical to funeral_home to simulate
        access loss. Pre-W-3a this test started as FH (could pin) and
        flipped to manufacturing; with the canon retag the scenario
        inverts.
        """
        from app.models.company import Company
        from app.services.spaces import add_pin, get_spaces_for_user

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
        )

        # Flip tenant vertical to funeral_home — the widget no longer
        # passes the 5-axis filter for this user (vertical axis fails).
        co = (
            db_session.query(Company)
            .filter(Company.id == user.company_id)
            .one()
        )
        co.vertical = "funeral_home"
        db_session.commit()
        db_session.refresh(user)

        spaces = get_spaces_for_user(db_session, user=user)
        widget_pin = next(
            p for sp in spaces for p in sp.pins if p.pin_type == "widget"
        )
        assert widget_pin.unavailable is True
        # Widget metadata still surfaced so frontend can render a
        # readable "no longer available" affordance.
        assert widget_pin.widget_id == "scheduling.ancillary-pool"

    def test_remove_widget_pin(self, db_session):
        from app.services.spaces import add_pin, get_space, remove_pin

        user, space_id = _user_with_space(
            db_session, vertical="manufacturing",
            permissions=["delivery.view"],
        )
        pin = add_pin(
            db_session,
            user=user,
            space_id=space_id,
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
        )
        db_session.refresh(user)
        remove_pin(
            db_session, user=user, space_id=space_id, pin_id=pin.pin_id
        )
        db_session.refresh(user)

        sp = get_space(db_session, user=user, space_id=space_id)
        widget_pins = [p for p in sp.pins if p.pin_type == "widget"]
        assert widget_pins == []


# ── PinConfig dataclass round-trip ──────────────────────────────────


class TestPinConfigSchema:
    """variant_id + config round-trip through to_dict/from_dict so the
    JSONB persistence layer never loses widget pin metadata."""

    def test_widget_pin_round_trip(self):
        from app.services.spaces.types import PinConfig

        pin = PinConfig(
            pin_id="pn_test1234",
            pin_type="widget",
            target_id="scheduling.ancillary-pool",
            display_order=0,
            variant_id="glance",
            config={"view_id": "abc", "filter": {"status": "open"}},
        )
        d = pin.to_dict()
        assert d["pin_type"] == "widget"
        assert d["variant_id"] == "glance"
        assert d["config"] == {
            "view_id": "abc",
            "filter": {"status": "open"},
        }

        rt = PinConfig.from_dict(d)
        assert rt.pin_type == "widget"
        assert rt.target_id == "scheduling.ancillary-pool"
        assert rt.variant_id == "glance"
        assert rt.config == {
            "view_id": "abc",
            "filter": {"status": "open"},
        }

    def test_legacy_pin_without_w2_fields_round_trips(self):
        """Pre-W-2 saved JSONB rows lack variant_id + config keys.
        from_dict must default both to None without crashing."""
        from app.services.spaces.types import PinConfig

        legacy = {
            "pin_id": "pn_legacy",
            "pin_type": "saved_view",
            "target_id": "view-uuid",
            "display_order": 0,
            "label_override": None,
            "target_seed_key": None,
        }
        rt = PinConfig.from_dict(legacy)
        assert rt.variant_id is None
        assert rt.config is None


# ── get_widgets_for_surface ─────────────────────────────────────────


class TestGetWidgetsForSurface:
    """Phase W-2 surface-scoped catalog endpoint. Used by the
    WidgetPicker (`destination="sidebar"`) to populate pinnable
    widgets without coupling to a specific page_context."""

    def test_returns_widgets_with_spaces_pin_surface(self, db_session):
        from app.models.user import User
        from app.services.widgets.widget_service import (
            get_widgets_for_surface,
        )

        handles = _make_tenant_user(
            vertical="manufacturing",
            permissions=["delivery.view"],
            role_slug="director",
        )
        user = (
            db_session.query(User)
            .filter(User.id == handles["user_id"])
            .one()
        )

        results = get_widgets_for_surface(
            db_session, user.company_id, user, "spaces_pin"
        )
        # Every result must declare spaces_pin in supported_surfaces.
        assert results, "expected at least one spaces_pin widget"
        for w in results:
            assert "spaces_pin" in w["supported_surfaces"], (
                f"{w['widget_id']} surfaced in spaces_pin catalog "
                f"but doesn't declare spaces_pin in supported_surfaces"
            )

    def test_ancillary_pool_visible_to_manufacturing_with_vault(self, db_session):
        """Phase W-3a: ancillary-pool requires manufacturing vertical AND
        vault product line. A manufacturing tenant with vault activated
        sees the widget in the spaces_pin catalog with is_available=True."""
        from app.models.user import User
        from app.services.widgets.widget_service import (
            get_widgets_for_surface,
        )

        handles = _make_tenant_user(
            vertical="manufacturing",
            permissions=["delivery.view"],
            role_slug="director",
            product_lines=["vault"],
        )
        user = (
            db_session.query(User)
            .filter(User.id == handles["user_id"])
            .one()
        )

        results = get_widgets_for_surface(
            db_session, user.company_id, user, "spaces_pin"
        )
        ancillary = next(
            (w for w in results if w["widget_id"] == "scheduling.ancillary-pool"),
            None,
        )
        assert ancillary is not None
        assert ancillary["is_available"] is True

    def test_ancillary_pool_unavailable_to_funeral_home(self, db_session):
        """Phase W-3a inversion: cross-vertical filter applies in the
        surface catalog too — a funeral_home tenant sees the widget in
        the catalog but with is_available=False + reason=vertical_required.

        Note on axis evaluation order: the filter walks all 5 axes
        without short-circuit and the LAST failing axis sets the
        unavailable_reason. To assert "vertical_required" specifically,
        we seed vault product line for the FH tenant — that way only
        the vertical axis fails (product_line passes), so vertical is
        the reported reason. A FH tenant without vault would fail BOTH
        axes; product_line would be reported because it's evaluated
        after vertical."""
        from app.models.user import User
        from app.services.widgets.widget_service import (
            get_widgets_for_surface,
        )

        handles = _make_tenant_user(
            vertical="funeral_home",
            permissions=["delivery.view"],
            role_slug="director",
            # Seed vault so only the vertical axis fails — produces
            # clean unavailable_reason="vertical_required" for assertion.
            product_lines=["vault"],
        )
        user = (
            db_session.query(User)
            .filter(User.id == handles["user_id"])
            .one()
        )

        results = get_widgets_for_surface(
            db_session, user.company_id, user, "spaces_pin"
        )
        ancillary = next(
            (w for w in results if w["widget_id"] == "scheduling.ancillary-pool"),
            None,
        )
        # Widget is present (declares spaces_pin) but unavailable due
        # to vertical filter (manufacturing-only post-W-3a).
        if ancillary is not None:
            assert ancillary["is_available"] is False
            assert ancillary["unavailable_reason"] == "vertical_required"

    def test_ancillary_pool_unavailable_to_manufacturing_without_vault(self, db_session):
        """Phase W-3a NEW: a manufacturing tenant WITHOUT vault product
        line activated still fails the 5-axis filter — the product_line
        axis catches it after vertical passes. Confirms the 5th axis is
        load-bearing (not redundant with vertical)."""
        from app.models.user import User
        from app.services.widgets.widget_service import (
            get_widgets_for_surface,
        )

        handles = _make_tenant_user(
            vertical="manufacturing",
            permissions=["delivery.view"],
            role_slug="director",
            product_lines=[],  # vertical passes; product_line axis fails
        )
        user = (
            db_session.query(User)
            .filter(User.id == handles["user_id"])
            .one()
        )

        results = get_widgets_for_surface(
            db_session, user.company_id, user, "spaces_pin"
        )
        ancillary = next(
            (w for w in results if w["widget_id"] == "scheduling.ancillary-pool"),
            None,
        )
        if ancillary is not None:
            assert ancillary["is_available"] is False
            assert ancillary["unavailable_reason"] == "product_line_required"

    def test_unknown_surface_returns_empty(self, db_session):
        from app.models.user import User
        from app.services.widgets.widget_service import (
            get_widgets_for_surface,
        )

        handles = _make_tenant_user(
            vertical="manufacturing",
            permissions=["delivery.view"],
            role_slug="director",
        )
        user = (
            db_session.query(User)
            .filter(User.id == handles["user_id"])
            .one()
        )

        results = get_widgets_for_surface(
            db_session, user.company_id, user, "nonexistent_surface"
        )
        assert results == []
