"""Phase B Session 4 Phase 4.2.2 — delivery reassignment regression tests.

Covers the PATCH `/api/v1/delivery/deliveries/{id}` endpoint's handling
of `assigned_driver_id`, with specific focus on the null-stripping bug
that made drag-to-Unassigned silently fail in both the Funeral Schedule
Monitor widget and the Scheduling Focus Decide surface:

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

These tests exercise the full HTTP round-trip so they catch both the
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
    """Build a tenant + admin user with delivery.edit permission + two
    drivers. Returns a dict of handles for the tests."""
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

        # Driver-delivery module must be enabled for the route's
        # require_module gate.
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
        db.add(admin_user)
        db.flush()

        driver_dave = Driver(
            id=str(uuid.uuid4()), company_id=co.id,
            employee_id=None,
            license_number=f"CDL-DAVE-{suffix}",
            license_class="CDL-A",
            active=True,
        )
        driver_mike = Driver(
            id=str(uuid.uuid4()), company_id=co.id,
            employee_id=None,
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


def _make_delivery(company_id: str, *, assigned_driver_id: str | None = None) -> str:
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
            assigned_driver_id=assigned_driver_id,
        )
        db.add(d)
        db.commit()
        return d.id
    finally:
        db.close()


def _refetch_assigned_driver(delivery_id: str) -> str | None:
    from app.database import SessionLocal
    from app.models.delivery import Delivery

    db = SessionLocal()
    try:
        d = db.query(Delivery).filter(Delivery.id == delivery_id).one()
        return d.assigned_driver_id
    finally:
        db.close()


# ── Tests ───────────────────────────────────────────────────────────


class TestAssignedDriverReassignment:
    """Covers the full drag-and-drop reassignment matrix: null→driver,
    driver→driver, driver→null (the previously-broken case), null→null
    (no-op), and round-trips."""

    def test_assign_null_to_driver(self, client, ctx):
        # Starting condition: unassigned (Unassigned column).
        delivery_id = _make_delivery(ctx["company_id"])
        assert _refetch_assigned_driver(delivery_id) is None

        # Drag → Dave.
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"assigned_driver_id": ctx["driver_dave_id"]},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        assert _refetch_assigned_driver(delivery_id) == ctx["driver_dave_id"]

    def test_reassign_driver_to_driver(self, client, ctx):
        delivery_id = _make_delivery(
            ctx["company_id"], assigned_driver_id=ctx["driver_dave_id"]
        )

        # Dave → Mike.
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"assigned_driver_id": ctx["driver_mike_id"]},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        assert _refetch_assigned_driver(delivery_id) == ctx["driver_mike_id"]

    def test_unassign_driver_to_null_4_2_2_regression_guard(self, client, ctx):
        """THE regression guard for the 4.2.2 bug. Pre-4.2.2 this
        silently no-op'd because `exclude_none=True` at the route +
        `if v is not None` at the service filtered the null out twice.
        Post-4.2.2 the null reaches the column and clears it."""
        delivery_id = _make_delivery(
            ctx["company_id"], assigned_driver_id=ctx["driver_dave_id"]
        )
        assert _refetch_assigned_driver(delivery_id) == ctx["driver_dave_id"]

        # Drag → Unassigned (null clears the assignment).
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"assigned_driver_id": None},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        assert _refetch_assigned_driver(delivery_id) is None

    def test_full_roundtrip_null_driver_null(self, client, ctx):
        """End-to-end drag sequence: Unassigned → Dave → Unassigned →
        Mike. Every step must stick. This is the mental-model test —
        the dispatcher reassigns and un-assigns repeatedly during a
        planning session, and state has to track perfectly."""
        delivery_id = _make_delivery(ctx["company_id"])
        headers = _hdr(ctx["admin_token"], ctx["slug"])

        # null → Dave
        client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"assigned_driver_id": ctx["driver_dave_id"]},
            headers=headers,
        ).raise_for_status()
        assert _refetch_assigned_driver(delivery_id) == ctx["driver_dave_id"]

        # Dave → null
        client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"assigned_driver_id": None},
            headers=headers,
        ).raise_for_status()
        assert _refetch_assigned_driver(delivery_id) is None

        # null → Mike
        client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"assigned_driver_id": ctx["driver_mike_id"]},
            headers=headers,
        ).raise_for_status()
        assert _refetch_assigned_driver(delivery_id) == ctx["driver_mike_id"]

        # Mike → Dave (drag back to a prior column — must work)
        client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"assigned_driver_id": ctx["driver_dave_id"]},
            headers=headers,
        ).raise_for_status()
        assert _refetch_assigned_driver(delivery_id) == ctx["driver_dave_id"]

    def test_unset_fields_are_not_touched(self, client, ctx):
        """`exclude_unset=True` semantics: a patch that doesn't mention
        a field leaves it alone. Confirms we didn't accidentally start
        clobbering every unspecified column to NULL."""
        delivery_id = _make_delivery(
            ctx["company_id"], assigned_driver_id=ctx["driver_dave_id"]
        )

        # Patch only `priority`. assigned_driver_id was NOT set on the
        # request payload → backend must preserve Dave's assignment.
        r = client.patch(
            f"/api/v1/delivery/deliveries/{delivery_id}",
            json={"priority": "high"},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        assert _refetch_assigned_driver(delivery_id) == ctx["driver_dave_id"]

    def test_explicit_null_on_one_field_leaves_others_alone(self, client, ctx):
        """Mixed patch: clear `assigned_driver_id`, simultaneously leave
        `priority` untouched. Validates exclude_unset's per-field
        discrimination."""
        delivery_id = _make_delivery(
            ctx["company_id"], assigned_driver_id=ctx["driver_dave_id"]
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
            json={"assigned_driver_id": None},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text

        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).one()
            assert d.assigned_driver_id is None
            assert d.priority == "high"
        finally:
            db.close()
