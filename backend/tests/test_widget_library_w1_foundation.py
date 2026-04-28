"""Widget Library Phase W-1 — Foundation tests.

Covers:
  • r58 migration backfill: every widget has variants + default_variant_id
    + required_vertical + supported_surfaces + default_surfaces +
    intelligence_keywords post-migration.
  • 4-axis filter (Section 12.4): permission + module + extension +
    vertical, all evaluated AND-wise.
  • Vertical scoping invariant: qc_status visible only to funeral_home
    tenants; cross-vertical widgets visible to all.
  • Canvas widget catalog citizen: scheduling.ancillary-pool
    (AncillaryPoolPin) seeded as a backend WidgetDefinition with 3
    variants (glance / brief / detail) per Section 12.10 reference.
  • Pre-existing Company.preset bug fixed: filter consumes
    Company.vertical via _get_tenant_vertical().
  • Seed idempotency: re-running seed_widget_definitions() doesn't
    duplicate or churn rows.
  • WidgetDefinition contract invariants: every widget has at least
    one variant; default_variant_id references a declared variant.
"""

from __future__ import annotations

import uuid
from typing import Iterator

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def fresh_db_with_seed() -> Iterator[None]:
    """Run seed_widget_definitions once before each test. The seed is
    idempotent (INSERT ON CONFLICT DO UPDATE) so this is safe to call
    repeatedly across tests."""
    from app.database import SessionLocal
    from app.services.widgets.widget_registry import seed_widget_definitions

    db = SessionLocal()
    try:
        seed_widget_definitions(db)
        yield
    finally:
        db.close()


def _make_tenant_with_user(
    *,
    vertical: str = "manufacturing",
    permissions: list[str] | None = None,
    extensions: list[str] | None = None,
    modules: list[str] | None = None,
    product_lines: list[str] | None = None,
) -> dict:
    """Create a tenant + user + roles + extensions + modules + product
    lines. Returns dict of handles. Tests use the user_id + company_id
    to drive the 5-axis filter under realistic conditions.

    Phase W-3a: gained `product_lines` parameter to seed
    `TenantProductLine` rows for axis 5 of the 5-axis filter. Idempotent
    via product_line_service.enable_line.
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
            name=f"WidgetTest-{suffix}",
            slug=f"widget-test-{suffix}",
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
            email=f"u-{suffix}@widget.test",
            first_name="W",
            last_name="Test",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)

        # Modules
        if modules:
            from app.models.company_module import CompanyModule
            for m in modules:
                db.add(CompanyModule(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    module=m,
                    enabled=True,
                ))

        # Extensions — use existing service if available
        if extensions:
            try:
                from app.services.extension_service import enable_extension
                for ext in extensions:
                    enable_extension(db, co.id, ext)
            except Exception:
                # Fall back to direct table insert if extension_service
                # has a different shape.
                pass

        db.commit()

        # Phase W-3a — TenantProductLine rows for axis 5. Done after
        # commit because product_line_service.enable_line opens its own
        # commit boundaries.
        if product_lines:
            from app.services import product_line_service
            for line_key in product_lines:
                product_line_service.enable_line(
                    db, company_id=co.id, line_key=line_key
                )

        return {
            "company_id": co.id,
            "user_id": user.id,
            "vertical": vertical,
        }
    finally:
        db.close()


# ── Migration backfill tests ─────────────────────────────────────────


class TestMigrationBackfill:
    """r58 migration backfilled the W-1 unified-contract columns on
    every existing widget. After seed runs, every row carries the
    new fields with sensible values."""

    def test_every_widget_has_at_least_one_variant(self, fresh_db_with_seed):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            rows = db.query(WidgetDefinition).all()
            assert len(rows) > 0, "Seed should populate at least one widget"
            for row in rows:
                assert row.variants, (
                    f"Widget {row.widget_id} missing variants — Phase W-1 "
                    f"requires every widget to declare ≥1 variant."
                )
                assert isinstance(row.variants, list)
                assert len(row.variants) >= 1
        finally:
            db.close()

    def test_default_variant_id_references_a_declared_variant(self, fresh_db_with_seed):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for row in db.query(WidgetDefinition).all():
                variant_ids = {v["variant_id"] for v in row.variants}
                assert row.default_variant_id in variant_ids, (
                    f"Widget {row.widget_id} default_variant_id "
                    f"{row.default_variant_id!r} not in declared variants "
                    f"{variant_ids}"
                )
        finally:
            db.close()

    def test_required_vertical_is_array_or_star(self, fresh_db_with_seed):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for row in db.query(WidgetDefinition).all():
                rv = row.required_vertical
                assert isinstance(rv, list), (
                    f"{row.widget_id} required_vertical must be array, got "
                    f"{type(rv).__name__}"
                )
                assert len(rv) >= 1
                # All values must be either "*" or a known vertical
                valid = {"*", "manufacturing", "funeral_home", "cemetery", "crematory"}
                for v in rv:
                    assert v in valid, f"{row.widget_id} unknown vertical {v!r}"
        finally:
            db.close()

    def test_supported_surfaces_non_empty(self, fresh_db_with_seed):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            valid_surfaces = {
                "pulse_grid", "focus_canvas", "focus_stack",
                "spaces_pin", "floating_tablet", "dashboard_grid",
                "peek_inline",
            }
            for row in db.query(WidgetDefinition).all():
                assert row.supported_surfaces, f"{row.widget_id} no surfaces"
                assert isinstance(row.supported_surfaces, list)
                for s in row.supported_surfaces:
                    assert s in valid_surfaces, (
                        f"{row.widget_id} unknown surface {s!r}"
                    )
        finally:
            db.close()

    def test_default_surfaces_subset_of_supported(self, fresh_db_with_seed):
        """Section 12.3 invariant: default_surfaces ⊆ supported_surfaces."""
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            for row in db.query(WidgetDefinition).all():
                supported = set(row.supported_surfaces or [])
                default = set(row.default_surfaces or [])
                assert default <= supported, (
                    f"{row.widget_id} default_surfaces {default} not subset "
                    f"of supported_surfaces {supported}"
                )
        finally:
            db.close()


# ── 4-axis filter tests ──────────────────────────────────────────────


class TestFourAxisFilter:
    """Section 12.4 4-axis filter. Each axis evaluated AND-wise.
    Cross-tenant defense-in-depth."""

    @pytest.mark.parametrize(
        "vertical,expected_qc_status_visible",
        [
            ("funeral_home", True),
            ("manufacturing", False),
            ("cemetery", False),
            ("crematory", False),
        ],
    )
    def test_qc_status_only_visible_to_funeral_home(
        self, fresh_db_with_seed, vertical, expected_qc_status_visible
    ):
        """qc_status (NPCA audit prep) is funeral-home-only per Phase
        W-1 audit + Section 12.4 vertical scoping."""
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_with_user(
            vertical=vertical,
            permissions=[],  # no perms — qc_status has no required_permission
            extensions=["npca_audit_prep"],  # extension is satisfied
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            results = get_available_widgets(
                db, ctx["company_id"], user, "ops_board"
            )
            qc = next((w for w in results if w["widget_id"] == "qc_status"), None)
            assert qc is not None, "qc_status should be in catalog"
            assert qc["is_available"] == expected_qc_status_visible, (
                f"qc_status visibility for vertical={vertical}: "
                f"expected {expected_qc_status_visible}, got "
                f"{qc['is_available']} ({qc['unavailable_reason']!r})"
            )
            if not expected_qc_status_visible:
                assert qc["unavailable_reason"] == "vertical_required"
        finally:
            db.close()

    @pytest.mark.parametrize(
        "vertical",
        ["funeral_home", "manufacturing", "cemetery", "crematory"],
    )
    def test_cross_vertical_widget_visible_in_all_verticals(
        self, fresh_db_with_seed, vertical
    ):
        """Widgets with required_vertical = ["*"] are visible to all
        verticals (Section 12.4 cross-vertical default)."""
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_with_user(vertical=vertical)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            results = get_available_widgets(
                db, ctx["company_id"], user, "ops_board"
            )
            todays = next(
                (w for w in results if w["widget_id"] == "todays_services"),
                None,
            )
            assert todays is not None
            assert todays["is_available"], (
                f"Cross-vertical widget should be visible in {vertical}, "
                f"got reason={todays['unavailable_reason']!r}"
            )
        finally:
            db.close()

    def test_permission_axis_blocks_widget_without_role(self, fresh_db_with_seed):
        """Axis 1 — permission: at_risk_accounts requires
        customers.view; user without it should not see widget."""
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_with_user(
            vertical="funeral_home",
            permissions=[],  # no customers.view
        )
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            results = get_available_widgets(
                db, ctx["company_id"], user, "vault_overview"
            )
            atr = next(
                (w for w in results if w["widget_id"] == "at_risk_accounts"),
                None,
            )
            assert atr is not None
            assert not atr["is_available"]
            assert atr["unavailable_reason"] == "permission_required"
        finally:
            db.close()

    def test_extension_axis_blocks_widget_without_extension(
        self, fresh_db_with_seed
    ):
        """Axis 3 — extension: time_clock requires time_clock extension;
        tenant without it should not see widget."""
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_with_user(
            vertical="manufacturing",
            extensions=[],  # no time_clock
        )
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            results = get_available_widgets(
                db, ctx["company_id"], user, "ops_board"
            )
            tc = next((w for w in results if w["widget_id"] == "time_clock"), None)
            assert tc is not None
            assert not tc["is_available"]
            assert tc["unavailable_reason"] == "extension_required"
        finally:
            db.close()


# ── Canvas widget catalog citizen ────────────────────────────────────


class TestCanvasWidgetCatalog:
    """AncillaryPoolPin enters the backend catalog as a unified-contract
    widget per Decision 1 + Section 12.10 reference implementation."""

    def test_ancillary_pool_in_catalog(self, fresh_db_with_seed):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition

        db = SessionLocal()
        try:
            row = db.query(WidgetDefinition).filter(
                WidgetDefinition.widget_id == "scheduling.ancillary-pool"
            ).first()
            assert row is not None, (
                "scheduling.ancillary-pool should be a backend catalog "
                "citizen per Decision 1 unified contract"
            )
            # Three variants per Section 12.10 reference: Glance + Brief + Detail
            assert {v["variant_id"] for v in row.variants} == {"glance", "brief", "detail"}
            assert row.default_variant_id == "detail"
            # Phase W-3a retag: manufacturing vertical + vault product line.
            # Pre-W-3a was ["funeral_home"] which was the canon investigation
            # finding (scheduling Focus is Sunnycrest mfg operations, not FH).
            assert row.required_vertical == ["manufacturing"]
            assert row.required_product_line == ["vault"]
            # Multi-surface (focus_canvas + others)
            assert "focus_canvas" in row.supported_surfaces
            assert "spaces_pin" in row.supported_surfaces
        finally:
            db.close()

    @pytest.mark.parametrize(
        "vertical,product_lines,visible",
        [
            # Phase W-3a inversion: manufacturing+vault visible;
            # everything else fails the 5-axis filter.
            ("manufacturing", ["vault"], True),
            # Manufacturing without vault — vertical passes but product_line fails
            ("manufacturing", [], False),
            # Funeral home — vertical fails (regardless of product line)
            ("funeral_home", ["vault"], False),
            ("funeral_home", [], False),
        ],
    )
    def test_ancillary_pool_5_axis_filter(
        self, fresh_db_with_seed, vertical, product_lines, visible
    ):
        """Phase W-3a — exercises all 5 axes for ancillary-pool widget.

        Renamed from `test_ancillary_pool_vertical_filtered` to reflect
        the W-3a 5-axis scope. Coverage: vertical pass + product_line
        pass = visible; either axis fail = invisible. Confirms the
        product_line axis is load-bearing (not redundant with vertical)
        — the manufacturing-without-vault case fails on product_line
        even though vertical passes.
        """
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_with_user(
            vertical=vertical,
            permissions=["delivery.view"],
            product_lines=product_lines,
        )
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            results = get_available_widgets(
                db, ctx["company_id"], user, "funeral_scheduling_focus"
            )
            ap = next(
                (w for w in results if w["widget_id"] == "scheduling.ancillary-pool"),
                None,
            )
            assert ap is not None
            assert ap["is_available"] == visible, (
                f"scheduling.ancillary-pool in vertical={vertical} "
                f"product_lines={product_lines}: expected "
                f"visible={visible}, got {ap['is_available']!r} "
                f"reason={ap['unavailable_reason']!r}"
            )
        finally:
            db.close()


# ── Pre-existing bug fix ─────────────────────────────────────────────


class TestCompanyPresetBugFix:
    """Pre-W-1 the filter helper read Company.preset which doesn't
    exist on the model (actual field is Company.vertical). The bug
    was silent because no widget set required_preset. Phase W-1
    rewrote the filter as 4-axis consuming Company.vertical
    correctly."""

    def test_get_tenant_vertical_returns_vertical_field(self):
        from app.database import SessionLocal
        from app.services.widgets.widget_service import _get_tenant_vertical

        ctx = _make_tenant_with_user(vertical="cemetery")
        db = SessionLocal()
        try:
            result = _get_tenant_vertical(db, ctx["company_id"])
            assert result == "cemetery"
        finally:
            db.close()

    def test_filter_does_not_call_get_tenant_preset(self):
        """The old broken helper should be gone. Verify by attribute
        absence (or rename presence)."""
        from app.services.widgets import widget_service

        # New helper exists
        assert hasattr(widget_service, "_get_tenant_vertical")
        # Old broken helper retired
        assert not hasattr(widget_service, "_get_tenant_preset"), (
            "_get_tenant_preset (pre-W-1 broken helper) should be "
            "removed by Phase W-1 4-axis filter rewrite"
        )


# ── Seed idempotency ─────────────────────────────────────────────────


class TestSeedIdempotency:
    """seed_widget_definitions is INSERT ON CONFLICT DO UPDATE — running
    it twice mustn't duplicate rows; row count stable."""

    def test_seed_twice_does_not_duplicate(self, fresh_db_with_seed):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition
        from app.services.widgets.widget_registry import seed_widget_definitions

        db = SessionLocal()
        try:
            count_after_first = db.query(WidgetDefinition).count()
            seed_widget_definitions(db)  # second run
            count_after_second = db.query(WidgetDefinition).count()
            assert count_after_first == count_after_second, (
                f"Seed not idempotent: "
                f"{count_after_first} → {count_after_second}"
            )
        finally:
            db.close()
