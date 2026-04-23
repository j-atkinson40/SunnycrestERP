"""Phase B Session 1 — Dispatch schedule state machine + API tests.

Covers:
  - State machine: draft → finalize → revert → re-finalize
  - Finalize guards (user_id required unless auto=True)
  - Revert on delivery edit (delivery_service.update_delivery hook)
  - Hole-dug quick-edit (with and without schedule revert)
  - Auto-finalize logic (tenant-local tz, Focus-open deferral,
    hard cutoff)
  - Cross-tenant isolation
  - API endpoints (auth required, permission-gated, ownership 404)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _make_ctx(*, vertical: str = "manufacturing"):
    """Build a tenant + admin + dispatcher user. Returns a dict of
    handles the tests use — user_id, company_id, slug, tokens."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user import User
    from app.core.permissions import DISPATCHER_DEFAULT_PERMISSIONS

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"Dispatch-{suffix}",
            slug=f"dispatch-{suffix}",
            is_active=True,
            vertical=vertical,
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()

        admin_role = Role(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Admin", slug="admin", is_system=True,
        )
        db.add(admin_role)

        dispatcher_role = Role(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Dispatcher", slug="dispatcher", is_system=True,
        )
        db.add(dispatcher_role)
        db.flush()
        for p in DISPATCHER_DEFAULT_PERMISSIONS:
            db.add(RolePermission(role_id=dispatcher_role.id, permission_key=p))

        admin_user = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"admin-{suffix}@dispatch.co",
            first_name="A", last_name="Admin",
            hashed_password="x", is_active=True,
            role_id=admin_role.id,
        )
        dispatcher_user = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"disp-{suffix}@dispatch.co",
            first_name="D", last_name="Dispatch",
            hashed_password="x", is_active=True,
            role_id=dispatcher_role.id,
        )
        readonly_user = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"ro-{suffix}@dispatch.co",
            first_name="R", last_name="Readonly",
            hashed_password="x", is_active=True,
            role_id=admin_role.id,  # admin gets wildcard so use a non-dispatcher role
        )
        # Create a no-perm role for the readonly user
        noperm_role = Role(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Noperm", slug="noperm", is_system=False,
        )
        db.add(noperm_role)
        db.flush()
        readonly_user.role_id = noperm_role.id

        db.add_all([admin_user, dispatcher_user, readonly_user])
        db.commit()

        return {
            "company_id": co.id,
            "slug": co.slug,
            "admin_id": admin_user.id,
            "admin_token": create_access_token(
                {"sub": admin_user.id, "company_id": co.id, "realm": "tenant"}
            ),
            "dispatcher_id": dispatcher_user.id,
            "dispatcher_token": create_access_token(
                {"sub": dispatcher_user.id, "company_id": co.id, "realm": "tenant"}
            ),
            "readonly_id": readonly_user.id,
            "readonly_token": create_access_token(
                {"sub": readonly_user.id, "company_id": co.id, "realm": "tenant"}
            ),
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx()


@pytest.fixture
def ctx_other():
    return _make_ctx()


def _hdr(token: str, slug: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": slug,
    }


def _make_delivery(company_id: str, *, requested_date: date | None = None) -> str:
    """Create a minimal Delivery row for a tenant. Returns id."""
    from app.database import SessionLocal
    from app.models.delivery import Delivery

    db = SessionLocal()
    try:
        d = Delivery(
            id=str(uuid.uuid4()),
            company_id=company_id,
            delivery_type="vault",
            requested_date=requested_date,
            status="pending",
            priority="normal",
            scheduling_type="kanban",
        )
        db.add(d)
        db.commit()
        return d.id
    finally:
        db.close()


# ── Service-layer: state machine ────────────────────────────────────


class TestStateMachine:
    def test_get_on_empty_returns_none(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            r = svc.get_schedule_state(db, ctx["company_id"], date.today())
            assert r is None
        finally:
            db.close()

    def test_ensure_creates_draft(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            r = svc.ensure_schedule(db, ctx["company_id"], date.today())
            assert r.state == "draft"
            assert r.finalized_at is None
            assert r.finalized_by_user_id is None
            assert r.auto_finalized is False
        finally:
            db.close()

    def test_ensure_is_idempotent(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            r1 = svc.ensure_schedule(db, ctx["company_id"], date.today())
            r2 = svc.ensure_schedule(db, ctx["company_id"], date.today())
            assert r1.id == r2.id
        finally:
            db.close()

    def test_finalize_without_user_id_raises(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            with pytest.raises(svc.ScheduleStateError):
                svc.finalize_schedule(
                    db, ctx["company_id"], date.today(),
                    user_id=None, auto=False,
                )
        finally:
            db.close()

    def test_explicit_finalize(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            r = svc.finalize_schedule(
                db, ctx["company_id"], date.today(),
                user_id=ctx["admin_id"],
            )
            assert r.state == "finalized"
            assert r.finalized_by_user_id == ctx["admin_id"]
            assert r.finalized_at is not None
            assert r.auto_finalized is False
        finally:
            db.close()

    def test_auto_finalize_stamps_flags(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            r = svc.finalize_schedule(
                db, ctx["company_id"], date.today(),
                user_id=None, auto=True,
            )
            assert r.state == "finalized"
            assert r.finalized_by_user_id is None
            assert r.auto_finalized is True
        finally:
            db.close()

    def test_finalize_idempotent(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            r1 = svc.finalize_schedule(
                db, ctx["company_id"], date.today(),
                user_id=ctx["admin_id"],
            )
            r2 = svc.finalize_schedule(
                db, ctx["company_id"], date.today(),
                user_id=ctx["admin_id"],
            )
            assert r1.id == r2.id
            assert r2.state == "finalized"
        finally:
            db.close()

    def test_revert_preserves_audit(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            svc.finalize_schedule(
                db, ctx["company_id"], date.today(),
                user_id=ctx["admin_id"],
            )
            r = svc.revert_to_draft(
                db, ctx["company_id"], date.today(),
                reason="delivery edit",
            )
            assert r is not None
            assert r.state == "draft"
            # Audit trail preserved
            assert r.finalized_at is not None
            assert r.finalized_by_user_id == ctx["admin_id"]
            # Revert markers stamped
            assert r.last_reverted_at is not None
            assert r.last_revert_reason == "delivery edit"
        finally:
            db.close()

    def test_revert_on_missing_returns_none(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            r = svc.revert_to_draft(
                db, ctx["company_id"], date(2099, 12, 31),
                reason="test",
            )
            assert r is None
        finally:
            db.close()

    def test_revert_on_draft_is_noop(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            r1 = svc.ensure_schedule(db, ctx["company_id"], date.today())
            assert r1.state == "draft"
            r2 = svc.revert_to_draft(
                db, ctx["company_id"], date.today(),
                reason="redundant",
            )
            assert r2.state == "draft"
            # No stamp on no-op
            assert r2.last_revert_reason is None
        finally:
            db.close()

    def test_re_finalize_after_revert(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            svc.finalize_schedule(
                db, ctx["company_id"], date.today(),
                user_id=ctx["admin_id"],
            )
            svc.revert_to_draft(
                db, ctx["company_id"], date.today(),
                reason="edit",
            )
            r = svc.finalize_schedule(
                db, ctx["company_id"], date.today(),
                user_id=ctx["admin_id"],
            )
            assert r.state == "finalized"
            # Finalized-by updates but revert stamp persists
            assert r.last_reverted_at is not None
        finally:
            db.close()


# ── Delivery-edit revert hook ───────────────────────────────────────


class TestRevertOnDeliveryEdit:
    def test_edit_reverts_finalized_schedule(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc
        from app.services import delivery_service as delivery_svc
        from app.models.delivery import Delivery

        today = date.today()
        delivery_id = _make_delivery(ctx["company_id"], requested_date=today)
        svc.finalize_schedule(
            db := SessionLocal(), ctx["company_id"], today,
            user_id=ctx["admin_id"],
        )
        db.close()

        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
            assert d is not None
            delivery_svc.update_delivery(db, d, {"priority": "urgent"})
            # Check schedule flipped back to draft
            r = svc.get_schedule_state(db, ctx["company_id"], today)
            assert r is not None
            assert r.state == "draft"
            assert r.last_revert_reason is not None
            assert "edited" in r.last_revert_reason.lower()
        finally:
            db.close()

    def test_edit_on_draft_schedule_no_revert(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc
        from app.services import delivery_service as delivery_svc
        from app.models.delivery import Delivery

        today = date.today()
        delivery_id = _make_delivery(ctx["company_id"], requested_date=today)
        svc.ensure_schedule(
            db := SessionLocal(), ctx["company_id"], today,
        )
        db.close()

        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
            delivery_svc.update_delivery(db, d, {"priority": "urgent"})
            r = svc.get_schedule_state(db, ctx["company_id"], today)
            # Still draft, no revert stamps
            assert r.state == "draft"
            assert r.last_revert_reason is None
        finally:
            db.close()

    def test_edit_on_delivery_without_date_no_crash(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_service as delivery_svc
        from app.models.delivery import Delivery

        # Delivery without requested_date → revert hook is a no-op.
        delivery_id = _make_delivery(ctx["company_id"], requested_date=None)
        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
            # Should not raise
            delivery_svc.update_delivery(db, d, {"priority": "urgent"})
        finally:
            db.close()


# ── Hole-dug quick-edit ─────────────────────────────────────────────


class TestHoleDug:
    def test_set_valid_values(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc
        from app.models.delivery import Delivery

        delivery_id = _make_delivery(ctx["company_id"], requested_date=date.today())
        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
            for value in ("unknown", "yes", "no", None):
                svc.set_hole_dug_status(db, d, value)
                db.refresh(d)
                assert d.hole_dug_status == value
        finally:
            db.close()

    def test_set_invalid_value_raises(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc
        from app.models.delivery import Delivery

        delivery_id = _make_delivery(ctx["company_id"], requested_date=date.today())
        db = SessionLocal()
        try:
            d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
            with pytest.raises(ValueError):
                svc.set_hole_dug_status(db, d, "maybe")
        finally:
            db.close()

    def test_edit_reverts_finalized_schedule(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc
        from app.models.delivery import Delivery

        today = date.today()
        delivery_id = _make_delivery(ctx["company_id"], requested_date=today)
        db = SessionLocal()
        try:
            svc.finalize_schedule(
                db, ctx["company_id"], today,
                user_id=ctx["admin_id"],
            )
            d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
            svc.set_hole_dug_status(db, d, "yes")
            r = svc.get_schedule_state(db, ctx["company_id"], today)
            assert r.state == "draft"
        finally:
            db.close()


# ── Auto-finalize logic ──────────────────────────────────────────────


class TestAutoFinalize:
    """Auto-finalize sweep semantics: targets TOMORROW's schedule only.

    Past-date drafts are anomalies; today's schedule is live work.
    Neither is auto-finalized. Only `schedule_date = local_today + 1`
    is considered.
    """

    def test_sweep_skips_tenant_before_1pm_local(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            tomorrow = date.today() + timedelta(days=1)
            svc.ensure_schedule(db, ctx["company_id"], tomorrow)
            # Fire sweep at a UTC time that's 11am ET (= 16:00 UTC) —
            # before tenant's 1pm cutoff.
            fake_now = datetime.now(timezone.utc).replace(hour=16, minute=0, second=0, microsecond=0)
            results = svc.auto_finalize_pending_schedules(
                db, now_utc=fake_now, company_ids=[ctx["company_id"]]
            )
            own = [r for r in results if r.company_id == ctx["company_id"]]
            # Tenant skipped entirely → no result entry
            assert len(own) == 0
            # Tomorrow's schedule still draft
            r = svc.get_schedule_state(db, ctx["company_id"], tomorrow)
            assert r.state == "draft"
        finally:
            db.close()

    def test_sweep_finalizes_tomorrow_past_1pm(self, ctx):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            tomorrow = date.today() + timedelta(days=1)
            svc.ensure_schedule(db, ctx["company_id"], tomorrow)
            # Well past 1pm ET (20:00 UTC = 16:00 ET)
            fake_now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
            results = svc.auto_finalize_pending_schedules(
                db, now_utc=fake_now, company_ids=[ctx["company_id"]]
            )
            own = [r for r in results if r.company_id == ctx["company_id"]]
            assert len(own) == 1
            assert tomorrow in own[0].finalized_dates
            r = svc.get_schedule_state(db, ctx["company_id"], tomorrow)
            assert r.state == "finalized"
            assert r.auto_finalized is True
            assert r.finalized_by_user_id is None
        finally:
            db.close()

    def test_sweep_never_touches_today(self, ctx):
        """Regression guard — today's schedule stays draft, not auto-
        finalized. Today's work is already live at 1pm."""
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            today = date.today()
            svc.ensure_schedule(db, ctx["company_id"], today)
            fake_now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
            svc.auto_finalize_pending_schedules(
                db, now_utc=fake_now, company_ids=[ctx["company_id"]]
            )
            r = svc.get_schedule_state(db, ctx["company_id"], today)
            assert r.state == "draft"
            assert r.auto_finalized is False
        finally:
            db.close()

    def test_sweep_never_touches_past_drafts(self, ctx):
        """Regression guard — past-date drafts are anomalies (dispatcher
        forgot to finalize) and stay draft. Surface via the Pulse
        `overdue_draft_schedules` anomaly widget, don't auto-resolve."""
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            past = date.today() - timedelta(days=2)
            svc.ensure_schedule(db, ctx["company_id"], past)
            fake_now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
            svc.auto_finalize_pending_schedules(
                db, now_utc=fake_now, company_ids=[ctx["company_id"]]
            )
            r = svc.get_schedule_state(db, ctx["company_id"], past)
            # Past draft stays draft
            assert r.state == "draft"
            assert r.auto_finalized is False
            assert r.finalized_by_user_id is None
        finally:
            db.close()

    def test_sweep_never_touches_two_days_out(self, ctx):
        """Regression guard — schedules beyond tomorrow stay untouched.
        The 1pm sweep only locks in tomorrow's work."""
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            two_days_out = date.today() + timedelta(days=2)
            svc.ensure_schedule(db, ctx["company_id"], two_days_out)
            fake_now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
            svc.auto_finalize_pending_schedules(
                db, now_utc=fake_now, company_ids=[ctx["company_id"]]
            )
            r = svc.get_schedule_state(db, ctx["company_id"], two_days_out)
            assert r.state == "draft"
            assert r.auto_finalized is False
        finally:
            db.close()

    def test_sweep_scope_boundary_with_multiple_drafts(self, ctx):
        """Integration — seeded tenant with drafts at past/today/
        tomorrow/+2d. Only tomorrow should flip. Regression for the
        exact bug (user-reported) where the filter erroneously matched
        multiple dates."""
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            past = date.today() - timedelta(days=1)
            today = date.today()
            tomorrow = date.today() + timedelta(days=1)
            day2 = date.today() + timedelta(days=2)
            for d in (past, today, tomorrow, day2):
                svc.ensure_schedule(db, ctx["company_id"], d)

            fake_now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
            svc.auto_finalize_pending_schedules(
                db, now_utc=fake_now, company_ids=[ctx["company_id"]]
            )

            # Only tomorrow is finalized.
            states = {
                d: svc.get_schedule_state(db, ctx["company_id"], d).state
                for d in (past, today, tomorrow, day2)
            }
            assert states[past] == "draft"
            assert states[today] == "draft"
            assert states[tomorrow] == "finalized"
            assert states[day2] == "draft"
        finally:
            db.close()

    def test_sweep_idempotent_on_user_finalized_tomorrow(self, ctx):
        """If the dispatcher explicitly finalized tomorrow's schedule
        before the 1pm cron fires, the cron leaves it alone — the
        filter is `state='draft'`, so a user-finalized row isn't
        considered. User's finalize markers (auto_finalized=False,
        finalized_by_user_id) stay intact."""
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            tomorrow = date.today() + timedelta(days=1)
            svc.finalize_schedule(
                db, ctx["company_id"], tomorrow,
                user_id=ctx["admin_id"],
            )
            fake_now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
            results = svc.auto_finalize_pending_schedules(
                db, now_utc=fake_now, company_ids=[ctx["company_id"]]
            )
            own = [r for r in results if r.company_id == ctx["company_id"]]
            # Row already finalized, not included in considered (filter
            # is state='draft'), so finalized_dates should be empty.
            if own:
                assert tomorrow not in own[0].finalized_dates
            r = svc.get_schedule_state(db, ctx["company_id"], tomorrow)
            # Still carrying the explicit user finalize (NOT auto_finalized)
            assert r.state == "finalized"
            assert r.auto_finalized is False
            assert r.finalized_by_user_id == ctx["admin_id"]
        finally:
            db.close()


# ── Cross-tenant isolation ──────────────────────────────────────────


class TestCrossTenant:
    def test_service_level_isolation(self, ctx, ctx_other):
        from app.database import SessionLocal
        from app.services import delivery_schedule_service as svc

        db = SessionLocal()
        try:
            # Tenant A creates + finalizes
            svc.finalize_schedule(
                db, ctx["company_id"], date.today(),
                user_id=ctx["admin_id"],
            )
            # Tenant B sees nothing
            r = svc.get_schedule_state(
                db, ctx_other["company_id"], date.today()
            )
            assert r is None
            # Tenant B revert is a no-op against its own (empty) state
            r = svc.revert_to_draft(
                db, ctx_other["company_id"], date.today(),
                reason="cross-tenant noop",
            )
            assert r is None
            # Tenant A still finalized
            r = svc.get_schedule_state(db, ctx["company_id"], date.today())
            assert r is not None and r.state == "finalized"
        finally:
            db.close()


# ── API endpoints ────────────────────────────────────────────────────


class TestAPI:
    def test_get_schedule_not_created(self, client, ctx):
        r = client.get(
            f"/api/v1/dispatch/schedule/{date.today().isoformat()}",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "not_created"

    def test_ensure_then_get(self, client, ctx):
        d = date.today().isoformat()
        r = client.post(
            f"/api/v1/dispatch/schedule/{d}/ensure",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        assert r.status_code == 200
        assert r.json()["state"] == "draft"
        r = client.get(
            f"/api/v1/dispatch/schedule/{d}",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        assert r.status_code == 200
        assert r.json()["state"] == "draft"

    def test_finalize_endpoint(self, client, ctx):
        d = date.today().isoformat()
        r = client.post(
            f"/api/v1/dispatch/schedule/{d}/finalize",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "finalized"
        assert body["finalized_by_user_id"] == ctx["dispatcher_id"]
        assert body["auto_finalized"] is False

    def test_revert_endpoint(self, client, ctx):
        d = date.today().isoformat()
        client.post(
            f"/api/v1/dispatch/schedule/{d}/finalize",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        r = client.post(
            f"/api/v1/dispatch/schedule/{d}/revert",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
            json={"reason": "I need to fix something"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "draft"
        assert body["last_revert_reason"] == "I need to fix something"

    def test_range_endpoint_happy_path(self, client, ctx):
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=3)).isoformat()
        r = client.get(
            f"/api/v1/dispatch/schedule/range?start={start}&end={end}",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["start_date"] == start
        assert body["end_date"] == end
        assert isinstance(body["schedules"], list)

    def test_range_end_before_start_400(self, client, ctx):
        start = date.today().isoformat()
        end = (date.today() - timedelta(days=1)).isoformat()
        r = client.get(
            f"/api/v1/dispatch/schedule/range?start={start}&end={end}",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        assert r.status_code == 400

    def test_range_too_wide_400(self, client, ctx):
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=60)).isoformat()
        r = client.get(
            f"/api/v1/dispatch/schedule/range?start={start}&end={end}",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        assert r.status_code == 400

    def test_hole_dug_happy_path(self, client, ctx):
        today = date.today()
        delivery_id = _make_delivery(ctx["company_id"], requested_date=today)
        r = client.patch(
            f"/api/v1/dispatch/delivery/{delivery_id}/hole-dug",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
            json={"status": "yes"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["hole_dug_status"] == "yes"

    def test_hole_dug_reverts_finalized(self, client, ctx):
        today = date.today()
        delivery_id = _make_delivery(ctx["company_id"], requested_date=today)
        client.post(
            f"/api/v1/dispatch/schedule/{today.isoformat()}/finalize",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
        )
        r = client.patch(
            f"/api/v1/dispatch/delivery/{delivery_id}/hole-dug",
            headers=_hdr(ctx["dispatcher_token"], ctx["slug"]),
            json={"status": "yes"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["schedule_reverted"] is True
        assert body["schedule_date"] == today.isoformat()

    def test_hole_dug_cross_tenant_404(self, client, ctx, ctx_other):
        delivery_id = _make_delivery(ctx["company_id"], requested_date=date.today())
        # Try to access from the OTHER tenant
        r = client.patch(
            f"/api/v1/dispatch/delivery/{delivery_id}/hole-dug",
            headers=_hdr(ctx_other["admin_token"], ctx_other["slug"]),
            json={"status": "yes"},
        )
        assert r.status_code == 404

    def test_no_auth_rejected(self, client):
        r = client.get(f"/api/v1/dispatch/schedule/{date.today().isoformat()}")
        assert r.status_code in (401, 403)

    def test_readonly_role_cannot_finalize(self, client, ctx):
        # User with `noperm` role has no delivery.finalize_schedule
        r = client.post(
            f"/api/v1/dispatch/schedule/{date.today().isoformat()}/finalize",
            headers=_hdr(ctx["readonly_token"], ctx["slug"]),
        )
        assert r.status_code == 403
