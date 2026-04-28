"""Phase W-3a `operator_profile` widget — backend catalog tests.

The operator_profile widget reads entirely from auth context +
spaces context client-side. There's no backend endpoint to test;
this file verifies the widget catalog registration + 5-axis filter
visibility (cross-vertical + cross-line).
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
            name=f"OperatorWidget-{suffix}",
            slug=f"opw-{suffix}",
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
            email=f"u-{suffix}@opw.test",
            first_name="O",
            last_name="P",
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

        return {"company_id": co.id, "user_id": user.id, "vertical": vertical}
    finally:
        db.close()


# ── Catalog registration ───────────────────────────────────────────


class TestOperatorProfileCatalog:
    """Phase W-3a operator_profile widget should be visible to every
    tenant via the 5-axis filter (cross-vertical + cross-line)."""

    def test_widget_registered_with_glance_and_brief_variants(
        self, db_session
    ):
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "operator_profile")
            .one()
        )
        variant_ids = {v["variant_id"] for v in row.variants}
        assert variant_ids == {"glance", "brief"}
        assert row.default_variant_id == "brief"
        assert row.required_vertical == ["*"]
        assert row.required_product_line == ["*"]

    def test_widget_visible_to_manufacturing(self, db_session):
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_user(
            vertical="manufacturing", product_lines=["vault"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        op = next(
            (w for w in widgets if w["widget_id"] == "operator_profile"),
            None,
        )
        assert op is not None
        assert op["is_available"] is True

    def test_widget_visible_to_funeral_home(self, db_session):
        from app.models.user import User
        from app.services.widgets.widget_service import get_available_widgets

        ctx = _make_tenant_user(vertical="funeral_home", product_lines=[])
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()
        widgets = get_available_widgets(
            db_session, ctx["company_id"], user, "pulse"
        )
        op = next(
            (w for w in widgets if w["widget_id"] == "operator_profile"),
            None,
        )
        assert op is not None
        assert op["is_available"] is True

    def test_widget_supports_spaces_pin_surface(self, db_session):
        """Spaces sidebar mounting requires `spaces_pin` in
        supported_surfaces. Phase W-2 add_pin defense-in-depth check
        will reject pin attempts otherwise."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "operator_profile")
            .one()
        )
        assert "spaces_pin" in row.supported_surfaces
        # Glance variant declares spaces_pin (the only valid sidebar
        # variant per §12.2 compatibility matrix).
        glance = next(
            v for v in row.variants if v["variant_id"] == "glance"
        )
        assert "spaces_pin" in glance["supported_surfaces"]
