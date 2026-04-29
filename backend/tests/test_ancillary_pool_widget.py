"""Phase W-4a Cleanup Session B.2 — `scheduling.ancillary-pool` widget
backend service + endpoint tests.

The ancillary pool widget powers the **pulse_grid surface** rendering
of `scheduling.ancillary-pool`. Closes the Path 3 deferral surfaced
in Phase W-4a Step 5: AncillaryPoolPin's strict `useSchedulingFocus()`
hook prevented pulse_grid mounting; this service powers the read-only
fallback path.

This file verifies:
  • Mode dispatch via `TenantProductLine(line_key="vault").config[
    "operating_mode"]` — production / purchase / hybrid / disabled
  • Tenant isolation — cross-tenant pool data NEVER leaks
  • Empty pool shape — `is_vault_enabled=True` + `total_count=0`
  • Purchase mode advisory — `mode_note="no_pool_in_purchase_mode"`
    with empty items + workspace-shape preservation
  • Auth gate — endpoint requires authenticated user
  • Response shape — fields the Brief variant renders against
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def _seeded() -> Iterator[None]:
    """Seed widget definitions so `scheduling.ancillary-pool` exists
    in `widget_definitions` before any test runs. Mirrors
    test_vault_schedule_widget.py setup."""
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
    """Spin up a tenant + role + user. `product_lines` is an optional
    list of (line_key, operating_mode) tuples — vault uses
    `operating_mode` JSON config per Phase W-3a canon."""
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"AP-{suffix}",
            slug=f"ap-{suffix}",
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
            email=f"u-{suffix}@ap.test",
            first_name="AP",
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


def _make_pool_ancillary(
    db_session,
    *,
    tenant_id: str,
    type_config: dict | None = None,
    delivery_type: str = "supply_delivery",
    status: str = "pending",
    fulfillment_status: str | None = None,
    soft_target_date=None,
):
    """Seed an ancillary delivery in pool state — date-less, unassigned,
    floating. Matches the Pool definition in
    `ancillary_pool_service._serialize_pool_item` filter."""
    from app.models.delivery import Delivery

    d = Delivery(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        delivery_type=delivery_type,
        order_id=None,
        requested_date=None,
        scheduling_type="ancillary",
        primary_assignee_id=None,
        attached_to_delivery_id=None,
        ancillary_is_floating=True,
        ancillary_fulfillment_status=fulfillment_status,
        ancillary_soft_target_date=soft_target_date,
        status=status,
        priority="normal",
        type_config=type_config or {},
    )
    db_session.add(d)
    db_session.commit()
    return d


# ── Mode dispatch tests ─────────────────────────────────────────────


class TestModeDispatch:
    def test_production_mode_returns_pool_items(self, db_session):
        """Production / hybrid → real pool with full items list."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")],
        )
        # Seed 2 pool items
        _make_pool_ancillary(
            db_session,
            tenant_id=ctx["company_id"],
            type_config={
                "product_summary": "Bronze urn",
                "family_name": "Smith",
            },
        )
        _make_pool_ancillary(
            db_session,
            tenant_id=ctx["company_id"],
            type_config={
                "product_summary": "Cremation tray",
                "family_name": "Jones",
            },
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_ancillary_pool(db_session, user=user)

        assert result["operating_mode"] == "production"
        assert result["is_vault_enabled"] is True
        assert result["total_count"] == 2
        assert len(result["items"]) == 2
        assert result["mode_note"] is None
        assert result["primary_navigation_target"] == "/dispatch"

    def test_purchase_mode_returns_advisory_with_empty_items(self, db_session):
        """Purchase mode → empty items + mode_note advisory.
        Workspace-shape preservation per §13.3.2.1: Brief variant
        renders advisory + CTA, NOT a generic empty state."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx = _make_tenant_user(
            product_lines=[("vault", "purchase")],
        )
        # Seed an ancillary that WOULD be in pool — should be ignored
        # because purchase mode short-circuits before the query runs.
        _make_pool_ancillary(
            db_session, tenant_id=ctx["company_id"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_ancillary_pool(db_session, user=user)

        assert result["operating_mode"] == "purchase"
        assert result["is_vault_enabled"] is True
        assert result["items"] == []
        assert result["total_count"] == 0
        assert result["mode_note"] == "no_pool_in_purchase_mode"
        # Workspace-shape preservation: CTA preserved even in purchase mode
        assert result["primary_navigation_target"] == "/dispatch"

    def test_hybrid_mode_returns_pool_items(self, db_session):
        """Hybrid mode → real pool (vault is poured in-house and also
        purchased; pool concept applies to in-house side)."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx = _make_tenant_user(
            product_lines=[("vault", "hybrid")],
        )
        _make_pool_ancillary(
            db_session, tenant_id=ctx["company_id"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_ancillary_pool(db_session, user=user)

        assert result["operating_mode"] == "hybrid"
        assert result["is_vault_enabled"] is True
        assert result["total_count"] == 1
        assert result["mode_note"] is None


class TestVaultDisabled:
    def test_no_vault_line_returns_disabled_state(self, db_session):
        """Tenant without vault line activated → is_vault_enabled=False
        + empty items + null operating_mode + null primary_navigation_
        target."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx = _make_tenant_user(product_lines=[])
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_ancillary_pool(db_session, user=user)

        assert result["is_vault_enabled"] is False
        assert result["operating_mode"] is None
        assert result["items"] == []
        assert result["total_count"] == 0
        assert result["mode_note"] is None
        assert result["primary_navigation_target"] is None


# ── Tenant isolation ────────────────────────────────────────────────


class TestTenantIsolation:
    def test_production_mode_only_returns_own_tenant_pool(self, db_session):
        """Cross-tenant pool data NEVER leaks. Caller's company_id is
        the canonical isolation gate."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx_a = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        ctx_b = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        # B has 3 pool items; A has 1
        _make_pool_ancillary(
            db_session, tenant_id=ctx_a["company_id"]
        )
        for _ in range(3):
            _make_pool_ancillary(
                db_session, tenant_id=ctx_b["company_id"]
            )

        user_a = (
            db_session.query(User).filter(User.id == ctx_a["user_id"]).one()
        )
        result = get_ancillary_pool(db_session, user=user_a)
        # A only sees its own 1 item
        assert result["total_count"] == 1
        assert len(result["items"]) == 1

    def test_excludes_cancelled_and_completed(self, db_session):
        """Cancelled deliveries + completed ancillaries excluded —
        matches /dispatch/pool-ancillaries filter."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        # Active pool item
        _make_pool_ancillary(
            db_session, tenant_id=ctx["company_id"]
        )
        # Cancelled — should be excluded
        _make_pool_ancillary(
            db_session,
            tenant_id=ctx["company_id"],
            status="cancelled",
        )
        # Completed fulfillment — should be excluded
        _make_pool_ancillary(
            db_session,
            tenant_id=ctx["company_id"],
            fulfillment_status="completed",
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_ancillary_pool(db_session, user=user)
        assert result["total_count"] == 1


# ── Empty pool shape ────────────────────────────────────────────────


class TestEmptyPool:
    def test_empty_pool_with_vault_enabled_returns_zero_items(
        self, db_session
    ):
        """Vault enabled + no pool items → empty items list +
        is_vault_enabled=True. Distinct from vault-disabled state."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        # No pool items seeded
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_ancillary_pool(db_session, user=user)

        assert result["is_vault_enabled"] is True
        assert result["operating_mode"] == "production"
        assert result["items"] == []
        assert result["total_count"] == 0
        assert result["primary_navigation_target"] == "/dispatch"


# ── Response shape ──────────────────────────────────────────────────


class TestResponseShape:
    def test_response_contains_all_expected_top_level_fields(
        self, db_session
    ):
        """Response shape contract — frontend Brief variant + hook
        depend on these exact keys."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_ancillary_pool(db_session, user=user)

        assert "operating_mode" in result
        assert "is_vault_enabled" in result
        assert "items" in result
        assert "total_count" in result
        assert "mode_note" in result
        assert "primary_navigation_target" in result

    def test_pool_item_shape_matches_brief_variant_contract(
        self, db_session
    ):
        """Each pool item has the fields AncillaryPoolPin's Brief
        variant renders — id + delivery_type + type_config (for
        label/subhead resolution)."""
        from app.models.user import User
        from app.services.widgets.ancillary_pool_service import (
            get_ancillary_pool,
        )

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        d = _make_pool_ancillary(
            db_session,
            tenant_id=ctx["company_id"],
            type_config={
                "product_summary": "Bronze urn",
                "family_name": "Smith",
                "funeral_home_name": "Hopkins",
            },
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        result = get_ancillary_pool(db_session, user=user)
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["id"] == d.id
        assert item["delivery_type"] == "supply_delivery"
        assert item["type_config"]["product_summary"] == "Bronze urn"
        assert item["type_config"]["family_name"] == "Smith"


# ── API endpoint (auth gate + tenant scoping via /widget-data/) ─────


class TestAPIEndpoint:
    def test_endpoint_requires_authentication(self, db_session):
        """Endpoint requires authenticated user. No anon access."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        response = client.get("/api/v1/widget-data/ancillary-pool")
        assert response.status_code in (401, 403)

    def test_endpoint_returns_200_with_expected_shape(self, db_session):
        """End-to-end: authenticated request returns 200 + expected
        keys. Auth happens via current_user dependency override
        pattern matching the existing widget_data tests."""
        from fastapi.testclient import TestClient

        from app.api.deps import get_current_user
        from app.main import app
        from app.models.user import User

        ctx = _make_tenant_user(
            product_lines=[("vault", "production")]
        )
        _make_pool_ancillary(
            db_session, tenant_id=ctx["company_id"]
        )
        user = db_session.query(User).filter(User.id == ctx["user_id"]).one()

        def _override_user():
            return user

        app.dependency_overrides[get_current_user] = _override_user
        try:
            client = TestClient(app)
            response = client.get("/api/v1/widget-data/ancillary-pool")
            assert response.status_code == 200
            data = response.json()
            assert data["operating_mode"] == "production"
            assert data["is_vault_enabled"] is True
            assert data["total_count"] == 1
            assert data["primary_navigation_target"] == "/dispatch"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
