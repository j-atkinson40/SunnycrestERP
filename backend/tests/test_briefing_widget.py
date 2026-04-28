"""Phase W-3b `briefing` widget — backend catalog tests.

The briefing widget is **per-user scoped** — it surfaces the current
user's latest Phase 6 briefing via the existing
`/briefings/v2/latest` endpoint. The Phase 6 service enforces
`user_id == current_user.id` server-side, so widget instances cannot
leak briefings between users. This file verifies catalog
registration + 5-axis filter visibility + variant declaration
(Glance + Brief + Detail) per §12.10.

Per-user scoping is inherited from Phase 6 infrastructure (see
`backend/tests/test_briefings_phase6.py` for endpoint-level tenant +
user isolation tests). This file does NOT re-test the briefing
endpoint — it tests the widget catalog row.
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
            name=f"BriefingW3b-{suffix}",
            slug=f"bw-{suffix}",
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
            email=f"u-{suffix}@bw.test",
            first_name="BW",
            last_name="Test",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {"company_id": co.id, "user_id": user.id}
    finally:
        db.close()


# ── Catalog registration ────────────────────────────────────────────


class TestBriefingWidgetCatalog:
    def test_widget_registered_glance_brief_detail(self, db_session):
        """Per §12.10: briefing declares Glance + Brief + Detail.
        No Deep — briefing detail is informationally complete; Deep
        would just re-render the dedicated /briefing page in widget
        chrome which §12.6a discourages (page owns heavy actions)."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "briefing")
            .one()
        )
        variant_ids = {v["variant_id"] for v in row.variants}
        assert variant_ids == {"glance", "brief", "detail"}, (
            f"briefing must declare Glance + Brief + Detail per §12.10; "
            f"got {variant_ids}"
        )
        assert row.default_variant_id == "brief"
        assert row.required_vertical == ["*"]
        assert row.required_product_line == ["*"]

    def test_widget_supports_canonical_surfaces(self, db_session):
        """Per §12.5: briefing renders on pulse_grid, spaces_pin
        (Glance), dashboard_grid, focus_canvas. Excludes peek_inline
        (briefing is per-user, not entity-scoped)."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "briefing")
            .one()
        )
        for surface in (
            "pulse_grid",
            "spaces_pin",
            "dashboard_grid",
            "focus_canvas",
        ):
            assert surface in row.supported_surfaces, (
                f"briefing must support {surface} per §12.5"
            )
        assert "peek_inline" not in row.supported_surfaces, (
            "briefing is per-user, not entity-scoped — peek_inline "
            "would have no meaningful entity to compose around"
        )

    def test_glance_variant_supports_spaces_pin(self, db_session):
        """The Glance variant is the sidebar entry point per §12.2
        compatibility matrix. Without spaces_pin on the Glance
        variant the widget can't be sidebar-pinned at all."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "briefing")
            .one()
        )
        glance = next(
            (v for v in row.variants if v["variant_id"] == "glance"),
            None,
        )
        assert glance is not None
        assert "spaces_pin" in glance["supported_surfaces"], (
            "Glance variant MUST support spaces_pin — sidebar requires "
            "Glance per §12.2 compatibility matrix"
        )

    def test_widget_visible_to_all_verticals(self, db_session):
        """Cross-vertical foundation widget — every vertical sees
        briefing in their catalog."""
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        for vertical in (
            "manufacturing",
            "funeral_home",
            "cemetery",
            "crematory",
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
            br = next(
                (w for w in widgets if w["widget_id"] == "briefing"),
                None,
            )
            assert br is not None, f"briefing invisible to {vertical}"
            assert br["is_available"] is True


# ── Spaces sidebar pin (Glance variant) ─────────────────────────────


class TestBriefingSidebarPin:
    """briefing CAN be pinned to a Spaces sidebar because it
    declares a Glance variant (unlike saved_view in W-3b). The
    Phase W-2 add_pin surface check should accept the pin."""

    def test_pinning_briefing_to_sidebar_accepted(self, db_session):
        from app.models.user import User
        from app.services.spaces import add_pin, create_space

        ctx = _make_tenant_user(vertical="manufacturing")
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        sp = create_space(
            db_session, user=user, name="Test", icon="home"
        )

        # Pinning briefing to sidebar should succeed — briefing
        # declares Glance + spaces_pin per §12.10. Phase W-2 add_pin
        # surface check accepts because supported_surfaces includes
        # spaces_pin.
        pin = add_pin(
            db_session,
            user=user,
            space_id=sp.space_id,
            pin_type="widget",
            target_id="briefing",
            config={"briefing_type": "morning"},
        )
        assert pin is not None
        # Verify the config plumbed through the pin row.
        assert pin.config == {"briefing_type": "morning"}
