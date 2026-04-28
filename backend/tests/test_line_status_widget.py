"""Phase W-3d `line_status` widget — backend catalog + service tests.

Cross-line health aggregator. Multi-line builder pattern mirrors
today_widget_service: vault metrics real, other lines placeholder.

Verifies:
  • Catalog: Brief + Detail variants only (NO Glance per §12.10)
  • 5-axis filter: required_vertical=["manufacturing"] +
    required_product_line=["*"] (cross-line aggregator)
  • Status assessment per mode (on_track / behind / blocked / idle)
  • Multi-line: returns one row per active TenantProductLine
  • Tenant isolation: vault metrics scoped to caller's tenant
  • Empty state: zero active lines returns empty list
  • Placeholder rows for non-vault lines (red_rock, urn_sales) until
    their per-line aggregators ship
"""

from __future__ import annotations

import uuid
from datetime import date
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
) -> dict:
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"LS-{suffix}",
            slug=f"ls-{suffix}",
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
            email=f"u-{suffix}@ls.test",
            first_name="LS",
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
        return {"company_id": co.id, "user_id": user.id}
    finally:
        db.close()


def _make_delivery(
    db_session,
    *,
    tenant_id: str,
    requested_date: date,
    primary_assignee_id: str | None = None,
    status: str = "pending",
):
    from app.models.delivery import Delivery

    d = Delivery(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        delivery_type="funeral_vault",
        requested_date=requested_date,
        primary_assignee_id=primary_assignee_id,
        status=status,
        priority="normal",
    )
    db_session.add(d)
    db_session.commit()
    return d


# ── Catalog ─────────────────────────────────────────────────────────


class TestLineStatusCatalog:
    def test_widget_registered_brief_detail_no_glance(self, db_session):
        """Per §12.10: line_status declares Brief + Detail only.
        NO Glance — operational health doesn't compress to count."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "line_status")
            .one()
        )
        variant_ids = {v["variant_id"] for v in row.variants}
        assert variant_ids == {"brief", "detail"}, (
            f"line_status must declare Brief + Detail only per §12.10; "
            f"got {variant_ids}"
        )
        assert row.default_variant_id == "brief"

    def test_widget_required_vertical_and_cross_line(self, db_session):
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "line_status")
            .one()
        )
        assert row.required_vertical == ["manufacturing"]
        # Cross-line aggregator — "*" means renders for whichever
        # lines are active.
        assert row.required_product_line == ["*"]

    def test_widget_supported_surfaces_excludes_spaces_pin(
        self, db_session
    ):
        """No Glance variant → no spaces_pin support."""
        from app.models.widget_definition import WidgetDefinition

        row = (
            db_session.query(WidgetDefinition)
            .filter(WidgetDefinition.widget_id == "line_status")
            .one()
        )
        for surface in (
            "pulse_grid",
            "dashboard_grid",
            "focus_canvas",
        ):
            assert surface in row.supported_surfaces
        assert "spaces_pin" not in row.supported_surfaces, (
            "line_status has no Glance variant — sidebar requires "
            "Glance per §12.2"
        )


# ── Vault health (production / purchase / hybrid) ───────────────────


class TestVaultHealth:
    def test_production_on_track_when_all_assigned(self, db_session):
        from app.models.user import User
        from app.services.widgets.line_status_service import get_line_status

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        today = date.today()
        _make_delivery(
            db_session,
            tenant_id=ctx["company_id"],
            requested_date=today,
            primary_assignee_id=ctx["user_id"],
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_line_status(db_session, user=user)
        vault = next(ln for ln in result["lines"] if ln["line_key"] == "vault")
        assert vault["status"] == "on_track"
        assert vault["operating_mode"] == "production"
        assert vault["metrics"]["production_today"] == 1
        assert vault["metrics"]["production_unassigned"] == 0
        assert result["any_attention_needed"] is False

    def test_production_behind_when_unassigned_above_threshold(
        self, db_session
    ):
        """>25% unassigned triggers 'behind' status."""
        from app.models.user import User
        from app.services.widgets.line_status_service import get_line_status

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        today = date.today()
        # 4 deliveries: 1 assigned, 3 unassigned (75% unassigned)
        _make_delivery(
            db_session,
            tenant_id=ctx["company_id"],
            requested_date=today,
            primary_assignee_id=ctx["user_id"],
        )
        for _ in range(3):
            _make_delivery(
                db_session,
                tenant_id=ctx["company_id"],
                requested_date=today,
                primary_assignee_id=None,
            )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_line_status(db_session, user=user)
        vault = next(ln for ln in result["lines"] if ln["line_key"] == "vault")
        assert vault["status"] == "behind"
        assert result["any_attention_needed"] is True

    def test_production_idle_when_zero_deliveries(self, db_session):
        from app.models.user import User
        from app.services.widgets.line_status_service import get_line_status

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_line_status(db_session, user=user)
        vault = next(ln for ln in result["lines"] if ln["line_key"] == "vault")
        assert vault["status"] == "idle"
        assert "no" in vault["headline"] or "0 pours" in vault["headline"]

    def test_purchase_idle_when_no_incoming(self, db_session):
        from app.models.user import User
        from app.services.widgets.line_status_service import get_line_status

        ctx = _make_tenant_user(
            product_lines=[("vault", "purchase")]
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_line_status(db_session, user=user)
        vault = next(ln for ln in result["lines"] if ln["line_key"] == "vault")
        assert vault["status"] == "idle"
        assert vault["operating_mode"] == "purchase"

    def test_purchase_navigation_target_routes_to_incoming(self, db_session):
        from app.models.user import User
        from app.services.widgets.line_status_service import get_line_status

        ctx = _make_tenant_user(product_lines=[("vault", "purchase")])
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_line_status(db_session, user=user)
        vault = next(ln for ln in result["lines"] if ln["line_key"] == "vault")
        assert vault["navigation_target"] == "/licensee-transfers/incoming"


# ── Multi-line aggregation ──────────────────────────────────────────


class TestMultiLineAggregation:
    def test_zero_lines_returns_empty(self, db_session):
        from app.models.user import User
        from app.services.widgets.line_status_service import get_line_status

        ctx = _make_tenant_user(product_lines=[])
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_line_status(db_session, user=user)
        assert result["lines"] == []
        assert result["total_active_lines"] == 0
        assert result["any_attention_needed"] is False

    def test_multiple_lines_each_get_a_row(self, db_session):
        """Vault gets real metrics; redi_rock + urn_sales get
        placeholder rows (status=unknown). Multi-line builder
        pattern works — every active line surfaces."""
        from app.models.user import User
        from app.services.widgets.line_status_service import get_line_status

        ctx = _make_tenant_user(
            product_lines=[
                ("vault", "production"),
                ("redi_rock", "production"),
                ("urn_sales", "purchase"),
            ]
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        result = get_line_status(db_session, user=user)
        line_keys = {ln["line_key"] for ln in result["lines"]}
        assert line_keys == {"vault", "redi_rock", "urn_sales"}
        assert result["total_active_lines"] == 3

        # Vault has real metrics
        vault = next(ln for ln in result["lines"] if ln["line_key"] == "vault")
        assert vault["status"] in (
            "on_track",
            "behind",
            "blocked",
            "idle",
        )

        # Other lines are placeholders (status=unknown)
        for line_key in ("redi_rock", "urn_sales"):
            ln = next(
                ll for ll in result["lines"] if ll["line_key"] == line_key
            )
            assert ln["status"] == "unknown", (
                f"{line_key} should be placeholder until aggregator ships"
            )


# ── Tenant isolation ────────────────────────────────────────────────


class TestLineStatusTenantIsolation:
    def test_vault_metrics_scoped_to_caller_tenant(self, db_session):
        from app.models.user import User
        from app.services.widgets.line_status_service import get_line_status

        ctx_a = _make_tenant_user(product_lines=[("vault", "production")])
        ctx_b = _make_tenant_user(product_lines=[("vault", "production")])
        today = date.today()
        # B has 5 deliveries; A has 0
        for _ in range(5):
            _make_delivery(
                db_session,
                tenant_id=ctx_b["company_id"],
                requested_date=today,
            )
        user_a = (
            db_session.query(User)
            .filter(User.id == ctx_a["user_id"])
            .one()
        )
        result = get_line_status(db_session, user=user_a)
        vault = next(ln for ln in result["lines"] if ln["line_key"] == "vault")
        assert vault["metrics"]["production_today"] == 0
        assert vault["status"] == "idle"
