"""Phase B Session 4 Phase 4.2.2 + 4.3.2 — delivery reassignment regression tests.

Covers the PATCH `/api/v1/delivery/deliveries/{id}` endpoint's handling
of `primary_assignee_id` (Phase 4.3.2 rename from `assigned_driver_id`).

**Phase 4.2.2 regression guard (still active):**

The null-stripping bug that made drag-to-Unassigned silently fail:

    Before 4.2.2:
      - Route used `data.model_dump(exclude_none=True)` → stripped any
        explicit null from the patch before it reached the service.
      - Service then re-guarded with `if v is not None: setattr(...)`.
      - Net effect: every null was discarded, so the legitimate
        "clear this driver assignment" operation was a no-op.

    After 4.2.2:
      - Route uses `exclude_unset=True` → only omits fields the client
        didn't set. Explicit nulls reach the service.
      - Service loops without the null guard → null sets the column
        to NULL as intended.

**Phase 4.3.2 rename + FK — new coverage:**

The column was renamed `assigned_driver_id` → `primary_assignee_id`
and now FK's to `users.id` (was a bare String storing `drivers.id`).
Tests exercise both entry paths:

  - JSON payload with `primary_assignee_id=<user.id>`: stored as-is.
  - JSON payload with `primary_assignee_id=<driver.id>`: backend's
    transitional `resolve_primary_assignee_id` helper translates via
    `Driver.employee_id` so existing frontend surfaces (which still
    pass `MonitorDriverDTO.id`) continue to work until Phase 4.3.3
    surfaces `user_id` explicitly.

These tests exercise the full HTTP round-trip — they catch both the
route-layer serialization choice and the service-layer mutation loop
together. A regression in either layer fails this suite loudly.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _make_ctx():
    """Build a tenant + admin + two driver-users with linked Driver rows.

    Phase 4.3.2 — Driver rows must carry ``employee_id`` FK to the
    ``User`` they represent; the primary_assignee_id FK targets
    ``users.id``. We create a User per driver so the reassignment
    round-trip exercises both the direct user.id path and the
    transitional translate-from-driver.id path.
    """
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.company_module import CompanyModule
    from app.models.driver import Driver
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"Reassign-{suffix}",
            slug=f"reassign-{suffix}",
            is_active=True,
            vertical="manufacturing",
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()

        db.add(CompanyModule(
            id=str(uuid.uuid4()),
            company_id=co.id,
            module="driver_delivery",
            enabled=True,
        ))

        admin_role = Role(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Admin", slug="admin", is_system=True,
        )
        db.add(admin_role)
        db.flush()

        admin_user = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"admin-{suffix}@reassign.co",
            first_name="A", last_name="Admin",
            hashed_password="x", is_active=True,
            role_id=admin_role.id,
        )
        user_dave = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"dave-{suffix}@reassign.co",
            first_name="Dave", last_name="Driver",
            hashed_password="x", is_active=True,
            role_id=admin_role.id,
        )
        user_mike = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"mike-{suffix}@reassign.co",
            first_name="Mike", last_name="Driver",
            hashed_password="x", is_active=True,
            role_id=admin_role.id,
        )
        db.add_all([admin_user, user_dave, user_mike])
        db.flush()

        # Driver rows carry employee_id FK to the User. The legacy
        # `drivers.id` values are what the Monitor UI currently passes
        # as `primary_assignee_id`; the backend translates to
        # `Driver.employee_id` (= users.id) before storing.
        driver_dave = Driver(
            id=str(uuid.uuid4()), company_id=co.id,
            employee_id=user_dave.id,
            license_number=f"CDL-DAVE-{suffix}",
            license_class="CDL-A",
            active=True,
        )
        driver_mike = Driver(
            id=str(uuid.uuid4()), company_id=co.id,
            employee_id=user_mike.id,
            license_number=f"CDL-MIKE-{suffix}",
            license_class="CDL-A",
            active=True,
        )
        db.add_all([driver_dave, driver_mike])
        db.commit()

        return {
            "company_id": co.id,
            "slug": co.slug,
            "admin_token": create_access_token(
                {"sub": admin_user.id, "company_id": co.id, "realm": "tenant"}
            ),
            # Users (what primary_assignee_id stores).
            "user_dave_id": user_dave.id,
            "user_mike_id": user_mike.id,
            # Drivers (what legacy frontend passes as primary_assignee_id).
            "driver_dave_id": driver_dave.id,
            "driver_mike_id": driver_mike.id,
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx()


def _hdr(token: str, slug: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": slug,
    }


def _make_delivery(
    company_id: str, *, primary_assignee_id: str | None = None
) -> str:
    from app.database import SessionLocal
    from app.models.delivery import Delivery

    db = SessionLocal()
    try:
        d = Delivery(
            id=str(uuid.uuid4()),
            company_id=company_id,
            delivery_type="vault",
            requested_date=date.today(),
            status="pending",
            priority="normal",
            scheduling_type="kanban",
            primary_assignee_id=primary_assignee_id,
        )
        db.add(d)
        db.commit()
        return d.id
    finally:
        db.close()


def _refetch_primary_assignee(delivery_id: str) -> str | None:
    from app.database import SessionLocal
    from app.models.delivery import Delivery

    db = SessionLocal()
    try:
        d = db.query(Delivery).filter(Delivery.id == delivery_id).one()
        return d.primary_assignee_id
    finally:
        db.close()


# ── Tests ───────────────────────────────────────────────────────────


class TestPrimaryAssigneeReassignment:
    """Covers the full drag-and-drop reassignment matrix.

    Phase 4.3.2 renamed `assigned_driver_id` → `primary_assignee_id`.
    The test names + assertions reflect the new field name; the
    Phase 4.2.2 null-stripping regression guard is preserved verbatim.
    """

    def test_assign_null_to_user(self, client, ctx):
        # Starting condition: unassigned.
        delivery_id = _make_delivery(ctx["company_id"])
        assert _refetch_primary_assignee(delivery_id) is None

        # Assign via user.id (canonical post-rename path).
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": ctx["user_dave_id"]},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        assert _refetch_primary_assignee(delivery_id) == ctx["user_dave_id"]

    def test_assign_null_to_driver_id_translates(self, client, ctx):
        """Transitional path: frontend passes drivers.id; backend
        helper translates to Driver.employee_id (users.id)."""
        delivery_id = _make_delivery(ctx["company_id"])
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": ctx["driver_dave_id"]},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        # Stored value is user_dave.id (translated from driver_dave.id).
        assert _refetch_primary_assignee(delivery_id) == ctx["user_dave_id"]

    def test_reassign_user_to_user(self, client, ctx):
        delivery_id = _make_delivery(
            ctx["company_id"], primary_assignee_id=ctx["user_dave_id"]
        )
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": ctx["user_mike_id"]},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        assert _refetch_primary_assignee(delivery_id) == ctx["user_mike_id"]

    def test_unassign_to_null_4_2_2_regression_guard(self, client, ctx):
        """THE regression guard for the Phase 4.2.2 bug. Pre-4.2.2
        this silently no-op'd because `exclude_none=True` at the
        route + `if v is not None` at the service filtered the null
        out twice. Post-4.2.2 the null reaches the column and clears
        it. Rename in 4.3.2 preserves this behavior."""
        delivery_id = _make_delivery(
            ctx["company_id"], primary_assignee_id=ctx["user_dave_id"]
        )
        assert _refetch_primary_assignee(delivery_id) == ctx["user_dave_id"]

        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": None},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        assert _refetch_primary_assignee(delivery_id) is None

    def test_full_roundtrip_null_user_null(self, client, ctx):
        """End-to-end drag sequence: Unassigned → Dave → Unassigned →
        Mike → Dave. Every step must stick. This is the mental-model
        test — the dispatcher reassigns and un-assigns repeatedly
        during a planning session, and state has to track perfectly."""
        delivery_id = _make_delivery(ctx["company_id"])
        headers = _hdr(ctx["admin_token"], ctx["slug"])

        # null → Dave (by user_id)
        client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": ctx["user_dave_id"]},
            headers=headers,
        ).raise_for_status()
        assert _refetch_primary_assignee(delivery_id) == ctx["user_dave_id"]

        # Dave → null
        client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": None},
            headers=headers,
        ).raise_for_status()
        assert _refetch_primary_assignee(delivery_id) is None

        # null → Mike (by user_id)
        client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": ctx["user_mike_id"]},
            headers=headers,
        ).raise_for_status()
        assert _refetch_primary_assignee(delivery_id) == ctx["user_mike_id"]

        # Mike → Dave (drag back to a prior column — must work)
        client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": ctx["user_dave_id"]},
            headers=headers,
        ).raise_for_status()
        assert _refetch_primary_assignee(delivery_id) == ctx["user_dave_id"]

    def test_unset_fields_are_not_touched(self, client, ctx):
        """`exclude_unset=True` semantics: a patch that doesn't
        mention a field leaves it alone. Confirms we didn't
        accidentally start clobbering every unspecified column to
        NULL."""
        delivery_id = _make_delivery(
            ctx["company_id"], primary_assignee_id=ctx["user_dave_id"]
        )

        # Patch only `priority`. primary_assignee_id was NOT set on
        # the request payload → backend must preserve Dave's
        # assignment.
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"priority": "high"},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        assert _refetch_primary_assignee(delivery_id) == ctx["user_dave_id"]

    def test_explicit_null_on_one_field_leaves_others_alone(self, client, ctx):
        """Mixed patch: clear `primary_assignee_id`, simultaneously
        leave `priority` untouched. Validates exclude_unset's per-field
        discrimination."""
        delivery_id = _make_delivery(
            ctx["company_id"], primary_assignee_id=ctx["user_dave_id"]
        )
        # Set an initial priority we can observe.
        from app.database import SessionLocal
        from app.models.delivery import Delivery

        db = SessionLocal()
        try:
            db.query(Delivery).filter(Delivery.id == delivery_id).update(
                {"priority": "high"}
            )
            db.commit()
        finally:
            db.close()

        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": None},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text

        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).one()
            assert d.primary_assignee_id is None
            assert d.priority == "high"
        finally:
            db.close()

    def test_invalid_primary_assignee_id_returns_400(self, client, ctx):
        """Phase 4.3.2 — the resolve helper raises ValueError when
        the value is neither a user.id nor a driver.id under the
        caller's tenant. Route translates to HTTP 400."""
        delivery_id = _make_delivery(ctx["company_id"])
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"primary_assignee_id": "not-a-real-id"},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 400, r.text
        assert "does not resolve" in r.json()["detail"].lower()


class TestNewFieldsShipped:
    """Phase 4.3.2 added `helper_user_id`, `attached_to_delivery_id`,
    and `driver_start_time` columns. Lightweight round-trip tests
    confirm the schema + DeliveryUpdate wiring land without triggering
    FK violations or serialization issues. Full service-method
    coverage (attach/detach/assign-standalone/return-to-pool) ships
    in Phase 4.3.3 alongside the endpoints + AncillaryCard UI."""

    def test_helper_user_id_roundtrip(self, client, ctx):
        delivery_id = _make_delivery(ctx["company_id"])
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"helper_user_id": ctx["user_mike_id"]},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text

        from app.database import SessionLocal
        from app.models.delivery import Delivery

        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).one()
            assert d.helper_user_id == ctx["user_mike_id"]
        finally:
            db.close()

    def test_attached_to_delivery_id_roundtrip(self, client, ctx):
        parent_id = _make_delivery(
            ctx["company_id"], primary_assignee_id=ctx["user_dave_id"]
        )
        child_id = _make_delivery(ctx["company_id"])
        r = client.patch(
            f"/api/v1/delivery/deliveries/{child_id}",
            json={"attached_to_delivery_id": parent_id},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text

        from app.database import SessionLocal
        from app.models.delivery import Delivery

        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == child_id).one()
            assert d.attached_to_delivery_id == parent_id
        finally:
            db.close()

    def test_driver_start_time_roundtrip(self, client, ctx):
        delivery_id = _make_delivery(ctx["company_id"])
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"driver_start_time": "07:30:00"},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text

        from app.database import SessionLocal
        from app.models.delivery import Delivery

        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).one()
            assert d.driver_start_time is not None
            assert d.driver_start_time.hour == 7
            assert d.driver_start_time.minute == 30
        finally:
            db.close()
