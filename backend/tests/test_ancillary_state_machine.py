"""Phase B Session 4 Phase 4.3.3 — ancillary three-state machine tests.

Covers:
  - service-layer transitions (pool ↔ paired ↔ standalone)
  - API endpoints (attach / detach / assign-standalone / return-to-pool)
  - permission + tenant-scope guards
  - error cases (not_attached, parent_not_kanban, self_attach,
    not_ancillary, cross-tenant 404)
  - field invariants per state (FK + driver + date + fulfillment_status)

PRODUCT_PRINCIPLES §Domain-Specific Operational Semantics canonical
state definitions (post-Phase 4.3.3 amendment):

  - pool — attached_to NULL + assignee NULL + date NULL
  - paired — attached_to set
  - standalone — attached_to NULL + assignee set + date set

These tests assert the field invariants per state directly.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _make_ctx():
    """Tenant + admin + 2 drivers (each linked to a User via
    Driver.employee_id) — same fixture shape as
    test_delivery_reassignment.py for consistency."""
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
            name=f"Anc-{suffix}",
            slug=f"anc-{suffix}",
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

        admin = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"admin-{suffix}@anc.co",
            first_name="A", last_name="A",
            hashed_password="x", is_active=True,
            role_id=admin_role.id,
        )
        u_dave = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"dave-{suffix}@anc.co",
            first_name="Dave", last_name="D",
            hashed_password="x", is_active=True,
            role_id=admin_role.id,
        )
        u_mike = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"mike-{suffix}@anc.co",
            first_name="Mike", last_name="M",
            hashed_password="x", is_active=True,
            role_id=admin_role.id,
        )
        db.add_all([admin, u_dave, u_mike])
        db.flush()

        d_dave = Driver(
            id=str(uuid.uuid4()), company_id=co.id,
            employee_id=u_dave.id,
            license_number=f"D-{suffix}", license_class="CDL-A", active=True,
        )
        d_mike = Driver(
            id=str(uuid.uuid4()), company_id=co.id,
            employee_id=u_mike.id,
            license_number=f"M-{suffix}", license_class="CDL-A", active=True,
        )
        db.add_all([d_dave, d_mike])
        db.commit()

        return {
            "company_id": co.id,
            "slug": co.slug,
            "admin_token": create_access_token(
                {"sub": admin.id, "company_id": co.id, "realm": "tenant"}
            ),
            "user_dave_id": u_dave.id,
            "user_mike_id": u_mike.id,
            "driver_dave_id": d_dave.id,
            "driver_mike_id": d_mike.id,
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx()


def _hdr(token: str, slug: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Company-Slug": slug}


def _make_delivery(
    company_id: str,
    *,
    scheduling_type: str = "kanban",
    primary_assignee_id: str | None = None,
    requested_date: date | None = None,
    attached_to_delivery_id: str | None = None,
    ancillary_is_floating: bool | None = None,
) -> str:
    from app.database import SessionLocal
    from app.models.delivery import Delivery

    db = SessionLocal()
    try:
        d = Delivery(
            id=str(uuid.uuid4()),
            company_id=company_id,
            delivery_type="vault" if scheduling_type == "kanban" else "funeral_home_dropoff",
            requested_date=requested_date,
            status="pending",
            priority="normal",
            scheduling_type=scheduling_type,
            primary_assignee_id=primary_assignee_id,
            attached_to_delivery_id=attached_to_delivery_id,
            ancillary_is_floating=ancillary_is_floating,
        )
        db.add(d)
        db.commit()
        return d.id
    finally:
        db.close()


def _refetch(delivery_id: str):
    from app.database import SessionLocal
    from app.models.delivery import Delivery

    db = SessionLocal()
    try:
        return db.query(Delivery).filter(Delivery.id == delivery_id).one()
    finally:
        db.close()


# ── Service-layer tests ────────────────────────────────────────────


class TestAttachAncillary:
    """attach_ancillary: pool/standalone → paired."""

    def test_attach_from_pool_inherits_driver_and_date(self, ctx):
        from app.database import SessionLocal
        from app.services import ancillary_service

        target_date = date(2026, 4, 25)
        parent_id = _make_delivery(
            ctx["company_id"],
            scheduling_type="kanban",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=target_date,
        )
        ancillary_id = _make_delivery(
            ctx["company_id"],
            scheduling_type="ancillary",
            ancillary_is_floating=True,
        )
        db = SessionLocal()
        try:
            a = ancillary_service.attach_ancillary(
                db, ancillary_id, parent_id, ctx["company_id"]
            )
            assert a.attached_to_delivery_id == parent_id
            assert a.primary_assignee_id == ctx["user_dave_id"]
            assert a.requested_date == target_date
            assert a.ancillary_is_floating is False
            assert a.ancillary_fulfillment_status == "assigned_to_driver"
        finally:
            db.close()

    def test_attach_overwrites_standalone_assignment_with_parent_values(self, ctx):
        """Standalone → paired transition: when attaching a standalone
        ancillary (already has a driver/date) to a parent, the
        parent's driver + date OVERWRITE the prior values. Spec
        intent: paired ancillaries follow their parent."""
        from app.database import SessionLocal
        from app.services import ancillary_service

        parent_date = date(2026, 4, 25)
        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=parent_date,
        )
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            primary_assignee_id=ctx["user_mike_id"],   # different driver
            requested_date=date(2026, 4, 28),          # different date
        )
        db = SessionLocal()
        try:
            a = ancillary_service.attach_ancillary(
                db, ancillary_id, parent_id, ctx["company_id"]
            )
            assert a.primary_assignee_id == ctx["user_dave_id"]   # parent's
            assert a.requested_date == parent_date                # parent's
            assert a.attached_to_delivery_id == parent_id
        finally:
            db.close()

    def test_attach_to_non_kanban_parent_raises_invalid(self, ctx):
        """Parent must be scheduling_type='kanban'. Attaching to
        another ancillary or direct_ship is rejected."""
        from app.database import SessionLocal
        from app.services import ancillary_service

        # Parent is ancillary, not kanban — invalid.
        bad_parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary"
        )
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary"
        )
        db = SessionLocal()
        try:
            with pytest.raises(ancillary_service.InvalidAncillaryTransition) as exc:
                ancillary_service.attach_ancillary(
                    db, ancillary_id, bad_parent_id, ctx["company_id"]
                )
            assert exc.value.code == "parent_not_kanban"
        finally:
            db.close()

    def test_attach_to_self_raises(self, ctx):
        from app.database import SessionLocal
        from app.services import ancillary_service

        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary"
        )
        db = SessionLocal()
        try:
            with pytest.raises(ancillary_service.InvalidAncillaryTransition) as exc:
                ancillary_service.attach_ancillary(
                    db, ancillary_id, ancillary_id, ctx["company_id"]
                )
            assert exc.value.code in {"self_attach", "parent_not_kanban"}
            # The ancillary itself is scheduling_type='ancillary', so
            # parent_not_kanban fires before self_attach. Either is
            # correct rejection.
        finally:
            db.close()

    def test_attach_unknown_parent_raises_404(self, ctx):
        from app.database import SessionLocal
        from app.services import ancillary_service

        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary"
        )
        db = SessionLocal()
        try:
            with pytest.raises(ancillary_service.ParentNotFound):
                ancillary_service.attach_ancillary(
                    db, ancillary_id, str(uuid.uuid4()), ctx["company_id"]
                )
        finally:
            db.close()


class TestDetachAncillary:
    """detach_ancillary: paired → standalone (default, single-path)."""

    def test_detach_to_standalone_preserves_driver_and_date(self, ctx):
        """Per Phase 4.3.3 spec: detach defaults to standalone.
        Driver + date PRESERVED (independent stop)."""
        from app.database import SessionLocal
        from app.services import ancillary_service

        target_date = date(2026, 4, 25)
        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=target_date,
        )
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            attached_to_delivery_id=parent_id,
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=target_date,
        )
        db = SessionLocal()
        try:
            a = ancillary_service.detach_ancillary(
                db, ancillary_id, ctx["company_id"]
            )
            assert a.attached_to_delivery_id is None
            # Standalone state: driver + date preserved
            assert a.primary_assignee_id == ctx["user_dave_id"]
            assert a.requested_date == target_date
            assert a.ancillary_fulfillment_status == "assigned_to_driver"
        finally:
            db.close()

    def test_detach_when_not_attached_raises(self, ctx):
        from app.database import SessionLocal
        from app.services import ancillary_service

        # Pool ancillary — not attached
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary"
        )
        db = SessionLocal()
        try:
            with pytest.raises(ancillary_service.InvalidAncillaryTransition) as exc:
                ancillary_service.detach_ancillary(
                    db, ancillary_id, ctx["company_id"]
                )
            assert exc.value.code == "not_attached"
        finally:
            db.close()


class TestAssignStandalone:
    """assign_ancillary_standalone: any state → standalone."""

    def test_pool_to_standalone(self, ctx):
        from app.database import SessionLocal
        from app.services import ancillary_service

        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            ancillary_is_floating=True,
        )
        target_date = date(2026, 4, 25)
        db = SessionLocal()
        try:
            a = ancillary_service.assign_ancillary_standalone(
                db, ancillary_id, ctx["user_dave_id"],
                target_date, ctx["company_id"],
            )
            assert a.attached_to_delivery_id is None
            assert a.primary_assignee_id == ctx["user_dave_id"]
            assert a.requested_date == target_date
            assert a.ancillary_is_floating is False
            assert a.ancillary_fulfillment_status == "assigned_to_driver"
        finally:
            db.close()

    def test_paired_to_standalone_clears_parent_fk(self, ctx):
        """Re-assignment from paired-to-different-driver via the
        standalone endpoint clears the FK (you can't be both)."""
        from app.database import SessionLocal
        from app.services import ancillary_service

        target_date = date(2026, 4, 25)
        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=target_date,
        )
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            attached_to_delivery_id=parent_id,
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=target_date,
        )
        db = SessionLocal()
        try:
            a = ancillary_service.assign_ancillary_standalone(
                db, ancillary_id, ctx["user_mike_id"],
                date(2026, 4, 26), ctx["company_id"],
            )
            assert a.attached_to_delivery_id is None  # FK cleared
            assert a.primary_assignee_id == ctx["user_mike_id"]
            assert a.requested_date == date(2026, 4, 26)
        finally:
            db.close()


class TestReturnToPool:
    """return_ancillary_to_pool: any state → pool. Idempotent."""

    def test_standalone_to_pool_clears_assignment(self, ctx):
        from app.database import SessionLocal
        from app.services import ancillary_service

        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=date(2026, 4, 25),
        )
        db = SessionLocal()
        try:
            a = ancillary_service.return_ancillary_to_pool(
                db, ancillary_id, ctx["company_id"]
            )
            assert a.attached_to_delivery_id is None
            assert a.primary_assignee_id is None
            assert a.requested_date is None
            assert a.ancillary_is_floating is True
            assert a.ancillary_fulfillment_status == "unassigned"
        finally:
            db.close()

    def test_paired_to_pool_clears_everything(self, ctx):
        """Paired → pool: FK + driver + date all clear."""
        from app.database import SessionLocal
        from app.services import ancillary_service

        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=date(2026, 4, 25),
        )
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            attached_to_delivery_id=parent_id,
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=date(2026, 4, 25),
        )
        db = SessionLocal()
        try:
            a = ancillary_service.return_ancillary_to_pool(
                db, ancillary_id, ctx["company_id"]
            )
            assert a.attached_to_delivery_id is None
            assert a.primary_assignee_id is None
            assert a.requested_date is None
            assert a.ancillary_is_floating is True
        finally:
            db.close()

    def test_pool_to_pool_is_idempotent(self, ctx):
        """Calling return_to_pool on a pool ancillary is a no-op
        (just stamps modified_at). Useful for idempotent admin
        scripts + retry-safe drag handlers."""
        from app.database import SessionLocal
        from app.services import ancillary_service

        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            ancillary_is_floating=True,
        )
        db = SessionLocal()
        try:
            a = ancillary_service.return_ancillary_to_pool(
                db, ancillary_id, ctx["company_id"]
            )
            assert a.primary_assignee_id is None
            assert a.ancillary_is_floating is True
            # Run again — still pool.
            a2 = ancillary_service.return_ancillary_to_pool(
                db, ancillary_id, ctx["company_id"]
            )
            assert a2.primary_assignee_id is None
        finally:
            db.close()


class TestNonAncillaryGuardrail:
    """All four methods reject scheduling_type != 'ancillary'."""

    def test_attach_kanban_delivery_raises(self, ctx):
        from app.database import SessionLocal
        from app.services import ancillary_service

        kanban_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban"
        )
        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban"
        )
        db = SessionLocal()
        try:
            with pytest.raises(ancillary_service.InvalidAncillaryTransition) as exc:
                ancillary_service.attach_ancillary(
                    db, kanban_id, parent_id, ctx["company_id"]
                )
            assert exc.value.code == "not_ancillary"
        finally:
            db.close()


# ── API endpoint tests ─────────────────────────────────────────────


class TestAttachAPI:
    def test_attach_returns_200_with_inherited_fields(self, client, ctx):
        target_date = date(2026, 4, 25)
        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=target_date,
        )
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            ancillary_is_floating=True,
        )
        r = client.post(
            f"/api/v1/extensions/funeral-kanban/ancillary/{ancillary_id}/attach",
            json={"parent_delivery_id": parent_id},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # _serialize_ancillary_card carries primary_assignee_id +
        # requested_date (the inherited values)
        assert body["primary_assignee_id"] == ctx["user_dave_id"]
        assert body["requested_date"] == target_date.isoformat()

    def test_attach_to_unknown_parent_returns_404(self, client, ctx):
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary"
        )
        r = client.post(
            f"/api/v1/extensions/funeral-kanban/ancillary/{ancillary_id}/attach",
            json={"parent_delivery_id": str(uuid.uuid4())},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 404


class TestDetachAPI:
    def test_detach_returns_200_with_standalone_fields(self, client, ctx):
        target_date = date(2026, 4, 25)
        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=target_date,
        )
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            attached_to_delivery_id=parent_id,
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=target_date,
        )
        r = client.post(
            f"/api/v1/extensions/funeral-kanban/ancillary/{ancillary_id}/detach",
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        # Driver + date preserved (standalone), parent FK cleared
        body = r.json()
        assert body["primary_assignee_id"] == ctx["user_dave_id"]
        assert body["requested_date"] == target_date.isoformat()
        # Verify FK cleared at DB level
        d = _refetch(ancillary_id)
        assert d.attached_to_delivery_id is None

    def test_detach_when_not_attached_returns_400(self, client, ctx):
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary"
        )
        r = client.post(
            f"/api/v1/extensions/funeral-kanban/ancillary/{ancillary_id}/detach",
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 400
        body = r.json()
        assert body["detail"]["code"] == "not_attached"


class TestAssignStandaloneAPI:
    def test_assign_standalone_via_user_id(self, client, ctx):
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            ancillary_is_floating=True,
        )
        r = client.post(
            f"/api/v1/extensions/funeral-kanban/ancillary/{ancillary_id}/assign-standalone",
            json={
                "primary_assignee_id": ctx["user_dave_id"],
                "scheduled_date": "2026-04-25",
            },
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["primary_assignee_id"] == ctx["user_dave_id"]
        assert body["requested_date"] == "2026-04-25"

    def test_assign_standalone_via_driver_id_translates(self, client, ctx):
        """Phase 4.3.2 transitional path: caller passes Driver.id;
        backend translates via Driver.employee_id → users.id."""
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            ancillary_is_floating=True,
        )
        r = client.post(
            f"/api/v1/extensions/funeral-kanban/ancillary/{ancillary_id}/assign-standalone",
            json={
                "primary_assignee_id": ctx["driver_dave_id"],
                "scheduled_date": "2026-04-25",
            },
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        # Stored value is the User.id (translated from driver.id)
        d = _refetch(ancillary_id)
        assert d.primary_assignee_id == ctx["user_dave_id"]


class TestReturnToPoolAPI:
    def test_return_to_pool_clears_assignment(self, client, ctx):
        ancillary_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            primary_assignee_id=ctx["user_dave_id"],
            requested_date=date(2026, 4, 25),
        )
        r = client.post(
            f"/api/v1/extensions/funeral-kanban/ancillary/{ancillary_id}/return-to-pool",
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["primary_assignee_id"] is None
        assert body["requested_date"] is None
        assert body["ancillary_is_floating"] is True


# ── Cross-tenant isolation ─────────────────────────────────────────


class TestCrossTenantIsolation:
    """Operations on an ancillary belonging to a different tenant
    return 404 — not 403 — to avoid leaking existence."""

    def test_attach_other_tenant_ancillary_returns_404(self, client, ctx):
        other = _make_ctx()
        ancillary_id = _make_delivery(
            other["company_id"], scheduling_type="ancillary"
        )
        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban"
        )
        r = client.post(
            f"/api/v1/extensions/funeral-kanban/ancillary/{ancillary_id}/attach",
            json={"parent_delivery_id": parent_id},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 404


# ── MonitorDeliveryDTO new fields surface ─────────────────────────


class TestMonitorDTONewFieldsSurface:
    """Phase 4.3.3 commit 1 wires three r56 fields through to the
    Monitor's response: helper_user_id, attached_to_delivery_id,
    driver_start_time. Pre-4.3.3 these were stored on the column
    but not propagated."""

    def test_monitor_returns_helper_user_id(self, client, ctx):
        from app.database import SessionLocal
        from app.models.delivery import Delivery

        delivery_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            requested_date=date(2026, 4, 25),
        )
        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).one()
            d.helper_user_id = ctx["user_mike_id"]
            db.commit()
        finally:
            db.close()

        r = client.get(
            "/api/v1/dispatch/deliveries",
            params={"start": "2026-04-25", "end": "2026-04-25"},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        match = next((x for x in rows if x["id"] == delivery_id), None)
        assert match is not None
        assert match["helper_user_id"] == ctx["user_mike_id"]

    def test_monitor_returns_driver_start_time(self, client, ctx):
        from app.database import SessionLocal
        from datetime import time as dtime
        from app.models.delivery import Delivery

        delivery_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            requested_date=date(2026, 4, 25),
        )
        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).one()
            d.driver_start_time = dtime(6, 30)
            db.commit()
        finally:
            db.close()

        r = client.get(
            "/api/v1/dispatch/deliveries",
            params={"start": "2026-04-25", "end": "2026-04-25"},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        rows = r.json()
        match = next((x for x in rows if x["id"] == delivery_id), None)
        assert match is not None
        assert match["driver_start_time"] == "06:30:00"

    def test_monitor_returns_attached_to_delivery_id(self, client, ctx):
        from app.database import SessionLocal
        from app.models.delivery import Delivery

        parent_id = _make_delivery(
            ctx["company_id"], scheduling_type="kanban",
            requested_date=date(2026, 4, 25),
        )
        anc_id = _make_delivery(
            ctx["company_id"], scheduling_type="ancillary",
            requested_date=date(2026, 4, 25),
        )
        db = SessionLocal()
        try:
            a = db.query(Delivery).filter(Delivery.id == anc_id).one()
            a.attached_to_delivery_id = parent_id
            db.commit()
        finally:
            db.close()

        r = client.get(
            "/api/v1/dispatch/deliveries",
            params={"start": "2026-04-25", "end": "2026-04-25"},
            headers=_hdr(ctx["admin_token"], ctx["slug"]),
        )
        rows = r.json()
        match = next((x for x in rows if x["id"] == anc_id), None)
        assert match is not None
        assert match["attached_to_delivery_id"] == parent_id


# ── DeliverySettings r57 default ───────────────────────────────────


class TestDeliverySettingsDefaultStartTime:
    """r57 added `default_driver_start_time` TEXT column with
    server_default '07:00'. Existing rows backfill via default;
    new rows use the model default."""

    def test_existing_settings_row_has_default(self, ctx):
        from app.database import SessionLocal
        from app.models.delivery_settings import DeliverySettings

        db = SessionLocal()
        try:
            row = (
                db.query(DeliverySettings)
                .filter(DeliverySettings.company_id == ctx["company_id"])
                .first()
            )
            if row is None:
                row = DeliverySettings(company_id=ctx["company_id"])
                db.add(row)
                db.commit()
                db.refresh(row)
            assert row.default_driver_start_time == "07:00"
        finally:
            db.close()
