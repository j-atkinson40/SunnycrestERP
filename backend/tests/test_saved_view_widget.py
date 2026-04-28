"""Phase W-3b `saved_view` widget — backend catalog tests.

The saved_view widget is **config-driven**: each instance carries
`config: {view_id}` selecting which view to render. Backend reuses the
existing V-1c `/saved-views/{view_id}` + `/execute` endpoints — no new
backend service or endpoint.

This file verifies catalog registration + 5-axis filter visibility +
the canonical `spaces_pin` exclusion (saved_view declares no Glance
variant, sidebar requires Glance per §12.2 compatibility matrix).
Tenant isolation + visibility enforcement at view fetch time inherits
from the V-1c saved-views infrastructure (covered by existing
test_saved_views.py).
"""

from __future__ import annotations

import uuid
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
    product_lines: list[str] | None = None,
) -> dict:
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
            name=f"SavedViewW3b-{suffix}",
            slug=f"sv-{suffix}",
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
            email=f"u-{suffix}@sv.test",
            first_name="SV",
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
        return {"company_id": co.id, "user_id": user.id}
    finally:
        db.close()


# ── Catalog registration ────────────────────────────────────────────


class TestSavedViewWidgetCatalog:
    def test_widget_registered_brief_detail_deep_no_glance(self, db_session):
        """Per §12.10: saved_view declares Brief + Detail + Deep only.
        NO Glance variant — saved views need at minimum a list to be
        informative; sidebar Glance shape doesn't accommodate that."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "saved_view")
            .one()
        )
        variant_ids = {v["variant_id"] for v in row.variants}
        assert variant_ids == {"brief", "detail", "deep"}, (
            f"saved_view must declare Brief + Detail + Deep only "
            f"(no Glance) per §12.10; got {variant_ids}"
        )
        assert row.default_variant_id == "detail"
        assert row.required_vertical == ["*"]
        assert row.required_product_line == ["*"]

    def test_widget_excludes_spaces_pin_surface(self, db_session):
        """Per §12.10: saved_view excludes spaces_pin surface because
        sidebar requires Glance variant (§12.2 compatibility matrix)
        and saved_view declares no Glance. Regression guard against
        accidental sidebar pinning."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "saved_view")
            .one()
        )
        assert "spaces_pin" not in row.supported_surfaces, (
            f"saved_view MUST NOT declare spaces_pin surface (no Glance "
            f"variant); got supported_surfaces={row.supported_surfaces}"
        )
        # Required surfaces per spec
        for surface in ("pulse_grid", "dashboard_grid", "focus_canvas"):
            assert surface in row.supported_surfaces, (
                f"saved_view missing required {surface} surface"
            )

    def test_widget_visible_to_all_verticals(self, db_session):
        """Cross-vertical foundation widget — every vertical sees
        saved_view in their catalog."""
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        for vertical in (
            "manufacturing", "funeral_home", "cemetery", "crematory",
        ):
            ctx = _make_tenant_user(vertical=vertical)
            user = (
                db_session.query(User)
                .filter(User.id == ctx["user_id"])
                .one()
            )
            widgets = get_available_widgets(
                db_session, ctx["company_id"], user, "pulse"
            )
            sv = next(
                (w for w in widgets if w["widget_id"] == "saved_view"),
                None,
            )
            assert sv is not None, f"saved_view invisible to {vertical}"
            assert sv["is_available"] is True


# ── Spaces sidebar pin rejection (canonical guard) ───────────────────


class TestSavedViewSidebarRejection:
    """Per §12.10 surface compatibility: saved_view CANNOT be pinned
    to a Spaces sidebar (no Glance variant). The Phase W-2 add_pin
    surface check should reject the attempt."""

    def test_pinning_saved_view_to_sidebar_rejected(self, db_session):
        from app.models.user import User
        from app.services.spaces import add_pin, create_space
        from app.services.spaces.types import SpaceError

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        sp = create_space(db_session, user=user, name="Test", icon="home")

        # Attempt to pin saved_view widget to sidebar — must reject
        with pytest.raises(SpaceError) as exc_info:
            add_pin(
                db_session,
                user=user,
                space_id=sp.space_id,
                pin_type="widget",
                target_id="saved_view",
                config={"view_id": "any-uuid"},
            )
        # Phase W-2 add_pin surface check: rejects when widget doesn't
        # declare spaces_pin in supported_surfaces.
        assert "spaces_pin" in str(exc_info.value).lower() or \
               "surface" in str(exc_info.value).lower(), (
            f"Expected spaces_pin/surface rejection; got: {exc_info.value}"
        )
