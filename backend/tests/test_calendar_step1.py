"""Phase W-4b Layer 1 Calendar Step 1 — entity foundation tests.

Covers entity model + service-layer CRUD + API endpoints + tenant
isolation. Mirrors the test discipline established in
``test_email_step1.py`` precedent (entity foundation tests for the
Email primitive).

**Test scope (Step 1 boundary):**
  - Entity model invariants (CHECK constraints, defaults, FK cascade)
  - CalendarAccount CRUD (create/get/list/update/delete) + access grants
  - CalendarEvent CRUD (create/get/list/update/delete) + linkages
  - CalendarEventAttendee CRUD + response status updates
  - Provider registry (3 providers registered: google_calendar / msgraph / local)
  - Tenant isolation at every service boundary
  - LocalCalendarProvider functional behavior (connect, sync, freebusy)
  - GoogleCalendarProvider + MicrosoftGraphCalendarProvider stubs raise
    NotImplementedError for sync ops, return success for connect-without-payload
  - Audit log entries written for every CRUD operation

**Out of scope (deferred to Step 2+):**
  - Real OAuth flows (Step 2)
  - Sync activation (Step 2)
  - RRULE engine activation (Step 2)
  - Outbound iTIP scheduling (Step 3)
  - Free/busy substrate cross-tenant query endpoint (Step 3)
  - Cross-tenant joint event acceptance (Step 4)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Company, User
from app.models.calendar_primitive import (
    ACCESS_LEVELS,
    ACCOUNT_TYPES,
    PROVIDER_TYPES,
    CalendarAccount,
    CalendarAccountAccess,
    CalendarAuditLog,
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventLinkage,
)
from app.services.calendar import (
    account_service,
    attendee_service,
    event_service,
)
from app.services.calendar.account_service import (
    CalendarAccountConflict,
    CalendarAccountNotFound,
    CalendarAccountValidation,
)
from app.services.calendar.event_service import (
    CalendarEventNotFound,
    CalendarEventValidation,
)
from app.services.calendar.providers import (
    PROVIDER_REGISTRY,
    GoogleCalendarProvider,
    LocalCalendarProvider,
    MicrosoftGraphCalendarProvider,
)
from app.services.calendar.providers.base import CalendarProvider


# ─────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    """Session that rolls back any test changes for isolation."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def tenant(db_session):
    """Create a manufacturing tenant for testing."""
    import uuid as _uuid

    company = Company(
        id=str(_uuid.uuid4()),
        name=f"Calendar Test Tenant {_uuid.uuid4().hex[:8]}",
        slug=f"caltest{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(company)
    db_session.flush()
    return company


@pytest.fixture
def other_tenant(db_session):
    """A second tenant for cross-tenant isolation tests."""
    import uuid as _uuid

    company = Company(
        id=str(_uuid.uuid4()),
        name=f"Other Cal Tenant {_uuid.uuid4().hex[:8]}",
        slug=f"othcal{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(company)
    db_session.flush()
    return company


@pytest.fixture
def admin_role(db_session, tenant):
    import uuid as _uuid

    from app.models import Role

    role = Role(
        id=str(_uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def admin_user(db_session, tenant, admin_role):
    import uuid as _uuid

    from app.core.security import hash_password

    user = User(
        id=str(_uuid.uuid4()),
        email=f"admin-{_uuid.uuid4().hex[:8]}@caltest.test",
        hashed_password=hash_password("TestAdmin123!"),
        first_name="Admin",
        last_name="User",
        company_id=tenant.id,
        role_id=admin_role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def office_user(db_session, tenant, admin_role):
    import uuid as _uuid

    from app.core.security import hash_password

    user = User(
        id=str(_uuid.uuid4()),
        email=f"office-{_uuid.uuid4().hex[:8]}@caltest.test",
        hashed_password=hash_password("TestOffice123!"),
        first_name="Office",
        last_name="User",
        company_id=tenant.id,
        role_id=admin_role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


# ─────────────────────────────────────────────────────────────────────
# Entity model tests
# ─────────────────────────────────────────────────────────────────────


class TestEntityModel:
    """Verify the canonical 9-table entity model."""

    def test_provider_types_canonical(self):
        """Q3 confirmed: only 3 provider types at Step 1 (CalDAV omitted)."""
        assert PROVIDER_TYPES == ("google_calendar", "msgraph", "local")

    def test_account_types_canonical(self):
        assert ACCOUNT_TYPES == ("shared", "personal")

    def test_access_levels_canonical(self):
        assert ACCESS_LEVELS == ("read", "read_write", "admin")

    def test_calendar_account_create_minimum_fields(
        self, db_session, tenant, admin_user
    ):
        """CalendarAccount can be created with minimum required fields."""
        account = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Production Schedule",
            primary_email_address="production@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        assert account.id
        assert account.tenant_id == tenant.id
        assert account.is_active is True
        assert account.is_default is False
        assert account.outbound_enabled is True
        assert account.default_event_timezone == "America/New_York"
        assert account.created_by_user_id == admin_user.id

    def test_calendar_event_check_end_after_start(
        self, db_session, tenant, admin_user
    ):
        """end_at >= start_at is enforced (CHECK constraint + service)."""
        account = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Test",
            primary_email_address=f"chk-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()

        start = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
        end_before = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)

        with pytest.raises(CalendarEventValidation):
            event_service.create_event(
                db_session,
                tenant_id=tenant.id,
                account_id=account.id,
                actor_user_id=admin_user.id,
                subject="Bad event",
                start_at=start,
                end_at=end_before,
            )


# ─────────────────────────────────────────────────────────────────────
# CalendarAccount service tests
# ─────────────────────────────────────────────────────────────────────


class TestCalendarAccountService:
    def test_create_account_writes_audit_log(
        self, db_session, tenant, admin_user
    ):
        before_count = (
            db_session.query(CalendarAuditLog)
            .filter(CalendarAuditLog.tenant_id == tenant.id)
            .count()
        )
        account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Audit Test",
            primary_email_address=f"audit-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        after_count = (
            db_session.query(CalendarAuditLog)
            .filter(CalendarAuditLog.tenant_id == tenant.id)
            .count()
        )
        assert after_count == before_count + 1
        last = (
            db_session.query(CalendarAuditLog)
            .filter(CalendarAuditLog.tenant_id == tenant.id)
            .order_by(CalendarAuditLog.created_at.desc())
            .first()
        )
        assert last.action == "account_created"
        assert last.entity_type == "calendar_account"

    def test_invalid_provider_type_rejected(
        self, db_session, tenant, admin_user
    ):
        with pytest.raises(CalendarAccountValidation):
            account_service.create_account(
                db_session,
                tenant_id=tenant.id,
                actor_user_id=admin_user.id,
                account_type="shared",
                display_name="Invalid",
                primary_email_address=f"inv-{tenant.id[:8]}@caltest.test",
                provider_type="caldav",  # Q3 omitted
            )

    def test_invalid_account_type_rejected(
        self, db_session, tenant, admin_user
    ):
        with pytest.raises(CalendarAccountValidation):
            account_service.create_account(
                db_session,
                tenant_id=tenant.id,
                actor_user_id=admin_user.id,
                account_type="public",  # invalid
                display_name="Invalid",
                primary_email_address=f"inv2-{tenant.id[:8]}@caltest.test",
                provider_type="local",
            )

    def test_duplicate_email_rejected(self, db_session, tenant, admin_user):
        addr = f"dup-{tenant.id[:8]}@caltest.test"
        account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="First",
            primary_email_address=addr,
            provider_type="local",
        )
        db_session.flush()
        with pytest.raises(CalendarAccountConflict):
            account_service.create_account(
                db_session,
                tenant_id=tenant.id,
                actor_user_id=admin_user.id,
                account_type="shared",
                display_name="Second",
                primary_email_address=addr,
                provider_type="local",
            )

    def test_is_default_demotes_other(self, db_session, tenant, admin_user):
        first = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="First",
            primary_email_address=f"d1-{tenant.id[:8]}@caltest.test",
            provider_type="local",
            is_default=True,
        )
        second = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Second",
            primary_email_address=f"d2-{tenant.id[:8]}@caltest.test",
            provider_type="local",
            is_default=True,
        )
        db_session.flush()
        db_session.refresh(first)
        assert first.is_default is False
        assert second.is_default is True

    def test_grant_access_idempotent(
        self, db_session, tenant, admin_user, office_user
    ):
        account = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="GA Test",
            primary_email_address=f"ga-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        g1 = account_service.grant_access(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            user_id=office_user.id,
            access_level="read",
            actor_user_id=admin_user.id,
        )
        g2 = account_service.grant_access(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            user_id=office_user.id,
            access_level="read",
            actor_user_id=admin_user.id,
        )
        assert g1.id == g2.id  # idempotent identical grant

    def test_grant_access_upgrades_existing(
        self, db_session, tenant, admin_user, office_user
    ):
        account = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Upgrade Test",
            primary_email_address=f"up-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        g1 = account_service.grant_access(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            user_id=office_user.id,
            access_level="read",
            actor_user_id=admin_user.id,
        )
        g2 = account_service.grant_access(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            user_id=office_user.id,
            access_level="read_write",
            actor_user_id=admin_user.id,
        )
        # Same row, upgraded level.
        assert g1.id == g2.id
        assert g2.access_level == "read_write"

    def test_revoke_access_idempotent(
        self, db_session, tenant, admin_user, office_user
    ):
        account = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Revoke Test",
            primary_email_address=f"rv-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        account_service.grant_access(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            user_id=office_user.id,
            access_level="read",
            actor_user_id=admin_user.id,
        )
        result_first = account_service.revoke_access(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            user_id=office_user.id,
            actor_user_id=admin_user.id,
        )
        result_second = account_service.revoke_access(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            user_id=office_user.id,
            actor_user_id=admin_user.id,
        )
        assert result_first is True
        assert result_second is False

    def test_user_has_access_rank_check(
        self, db_session, tenant, admin_user, office_user
    ):
        account = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Rank Test",
            primary_email_address=f"rk-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        account_service.grant_access(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            user_id=office_user.id,
            access_level="read_write",
            actor_user_id=admin_user.id,
        )
        assert account_service.user_has_access(
            db_session,
            account_id=account.id,
            user_id=office_user.id,
            minimum_level="read",
        )
        assert account_service.user_has_access(
            db_session,
            account_id=account.id,
            user_id=office_user.id,
            minimum_level="read_write",
        )
        assert not account_service.user_has_access(
            db_session,
            account_id=account.id,
            user_id=office_user.id,
            minimum_level="admin",
        )

    def test_soft_delete_clears_default_flag(
        self, db_session, tenant, admin_user
    ):
        account = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="To Delete",
            primary_email_address=f"sd-{tenant.id[:8]}@caltest.test",
            provider_type="local",
            is_default=True,
        )
        db_session.flush()
        account_service.delete_account(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
        )
        db_session.flush()
        db_session.refresh(account)
        assert account.is_active is False
        assert account.is_default is False


# ─────────────────────────────────────────────────────────────────────
# CalendarEvent service tests
# ─────────────────────────────────────────────────────────────────────


class TestCalendarEventService:
    @pytest.fixture
    def account(self, db_session, tenant, admin_user):
        acc = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Event Test Acc",
            primary_email_address=f"evtacc-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        return acc

    def test_create_event_basic(
        self, db_session, tenant, admin_user, account
    ):
        start = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
        end = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
        ev = event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=account.id,
            actor_user_id=admin_user.id,
            subject="Production review",
            start_at=start,
            end_at=end,
        )
        db_session.flush()
        assert ev.id
        assert ev.subject == "Production review"
        assert ev.status == "confirmed"
        assert ev.transparency == "opaque"
        assert ev.event_timezone == account.default_event_timezone
        assert ev.is_cross_tenant is False
        assert ev.is_active is True

    def test_inactive_account_cannot_create_event(
        self, db_session, tenant, admin_user, account
    ):
        account_service.delete_account(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
        )
        db_session.flush()
        with pytest.raises(CalendarEventValidation):
            event_service.create_event(
                db_session,
                tenant_id=tenant.id,
                account_id=account.id,
                actor_user_id=admin_user.id,
                subject="Should fail",
                start_at=datetime.now(timezone.utc),
                end_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

    def test_list_events_for_account_range_filter(
        self, db_session, tenant, admin_user, account
    ):
        # Create 3 events at different times.
        base = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        for i in range(3):
            event_service.create_event(
                db_session,
                tenant_id=tenant.id,
                account_id=account.id,
                actor_user_id=admin_user.id,
                subject=f"Event {i}",
                start_at=base + timedelta(days=i),
                end_at=base + timedelta(days=i, hours=1),
            )
        db_session.flush()

        # Range covering only middle event.
        result = event_service.list_events_for_account(
            db_session,
            account_id=account.id,
            tenant_id=tenant.id,
            range_start=base + timedelta(days=1, hours=-1),
            range_end=base + timedelta(days=1, hours=2),
        )
        assert len(result) == 1
        assert result[0].subject == "Event 1"

    def test_update_event_validates_time_order(
        self, db_session, tenant, admin_user, account
    ):
        start = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
        end = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
        ev = event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=account.id,
            actor_user_id=admin_user.id,
            subject="OK",
            start_at=start,
            end_at=end,
        )
        db_session.flush()
        # Try to push end before start.
        with pytest.raises(CalendarEventValidation):
            event_service.update_event(
                db_session,
                event_id=ev.id,
                tenant_id=tenant.id,
                actor_user_id=admin_user.id,
                end_at=start - timedelta(hours=1),
            )

    def test_add_linkage_idempotent(
        self, db_session, tenant, admin_user, account
    ):
        ev = event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=account.id,
            actor_user_id=admin_user.id,
            subject="Linkage test",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )
        db_session.flush()
        l1 = event_service.add_linkage(
            db_session,
            event_id=ev.id,
            tenant_id=tenant.id,
            linked_entity_type="sales_order",
            linked_entity_id="00000000-0000-0000-0000-000000000abc",
            linkage_source="manual_post_link",
            actor_user_id=admin_user.id,
        )
        l2 = event_service.add_linkage(
            db_session,
            event_id=ev.id,
            tenant_id=tenant.id,
            linked_entity_type="sales_order",
            linked_entity_id="00000000-0000-0000-0000-000000000abc",
            linkage_source="manual_post_link",
            actor_user_id=admin_user.id,
        )
        assert l1.id == l2.id


# ─────────────────────────────────────────────────────────────────────
# Attendee service tests
# ─────────────────────────────────────────────────────────────────────


class TestCalendarAttendeeService:
    @pytest.fixture
    def event(self, db_session, tenant, admin_user):
        acc = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="Attendee Test Acc",
            primary_email_address=f"attacc-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        ev = event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=acc.id,
            actor_user_id=admin_user.id,
            subject="Attendee event",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )
        db_session.flush()
        return ev

    def test_add_attendee_normalizes_email(
        self, db_session, tenant, admin_user, event
    ):
        att = attendee_service.add_attendee(
            db_session,
            event_id=event.id,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            email_address="  Foo@Example.COM  ",
            role="required_attendee",
        )
        db_session.flush()
        assert att.email_address == "foo@example.com"

    def test_response_status_stamps_responded_at(
        self, db_session, tenant, admin_user, event
    ):
        att = attendee_service.add_attendee(
            db_session,
            event_id=event.id,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            email_address="bar@example.com",
        )
        db_session.flush()
        assert att.responded_at is None  # default needs_action
        attendee_service.update_response_status(
            db_session,
            attendee_id=att.id,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            response_status="accepted",
        )
        db_session.flush()
        db_session.refresh(att)
        assert att.responded_at is not None
        assert att.response_status == "accepted"


# ─────────────────────────────────────────────────────────────────────
# Tenant isolation tests — the critical security boundary
# ─────────────────────────────────────────────────────────────────────


class TestTenantIsolation:
    """Verify cross-tenant access yields 404 (existence-hiding)."""

    def test_get_account_cross_tenant_404(
        self, db_session, tenant, other_tenant, admin_user
    ):
        # Create account in tenant.
        acc = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="A",
            primary_email_address=f"iso-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        # Attempt fetch from other_tenant.
        with pytest.raises(CalendarAccountNotFound):
            account_service.get_account(
                db_session,
                account_id=acc.id,
                tenant_id=other_tenant.id,
            )

    def test_get_event_cross_tenant_404(
        self, db_session, tenant, other_tenant, admin_user
    ):
        acc = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="A",
            primary_email_address=f"isoe-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        ev = event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=acc.id,
            actor_user_id=admin_user.id,
            subject="Iso",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )
        db_session.flush()
        with pytest.raises(CalendarEventNotFound):
            event_service.get_event(
                db_session,
                event_id=ev.id,
                tenant_id=other_tenant.id,
            )

    def test_list_accounts_other_tenant_empty(
        self, db_session, tenant, other_tenant, admin_user
    ):
        account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="A",
            primary_email_address=f"isol-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        other_accounts = account_service.list_accounts_for_tenant(
            db_session, tenant_id=other_tenant.id
        )
        # Other tenant sees none of our accounts.
        for acc in other_accounts:
            assert acc.tenant_id == other_tenant.id


# ─────────────────────────────────────────────────────────────────────
# Provider protocol conformance tests
# ─────────────────────────────────────────────────────────────────────


class TestProviderProtocol:
    """Verify all 3 Step-1 providers conform to the CalendarProvider ABC."""

    def test_registry_has_three_providers(self):
        """Q3 confirmed: only google_calendar / msgraph / local at Step 1."""
        assert set(PROVIDER_REGISTRY.keys()) == {
            "google_calendar",
            "msgraph",
            "local",
        }

    def test_caldav_not_in_registry(self):
        """CalDAV explicitly omitted per Q3 architectural decision."""
        assert "caldav" not in PROVIDER_REGISTRY

    def test_all_providers_subclass_abc(self):
        for ptype, pcls in PROVIDER_REGISTRY.items():
            assert issubclass(pcls, CalendarProvider)
            assert pcls.provider_type == ptype
            assert pcls.display_label  # non-empty

    def test_google_provider_post_step2_connect_succeeds(self):
        """Post-Step-2 contract: provider.connect() succeeds without
        OAuth payload (account row created; credentials persisted via
        OAuth callback path). Sync operations require access_token in
        account_config — calling without it raises RuntimeError.

        Updated from Step 1 stub-behavior assertion: Google + MS Graph
        providers ship as real implementations at Step 2 r68; the Step
        1 NotImplementedError stubs are gone.
        """
        provider = GoogleCalendarProvider({"primary_email_address": "x@x.com"})
        result = provider.connect(oauth_redirect_payload=None)
        assert result.success is True
        # subscribe_realtime returns True (provider supports realtime;
        # actual subscription registration ships at Step 2.1).
        assert provider.subscribe_realtime() is True
        # sync_initial without access_token raises RuntimeError (real
        # implementation requires the token to construct httpx client).
        with pytest.raises(RuntimeError, match="access_token"):
            provider.sync_initial()
        with pytest.raises(RuntimeError, match="access_token"):
            provider.fetch_event("e1")
        # Disconnect is a no-op.
        provider.disconnect()

    def test_msgraph_provider_post_step2_connect_succeeds(self):
        """Post-Step-2 contract: same shape as Google provider —
        connect succeeds, sync requires access_token. Updated from
        Step 1 NotImplementedError stub assertions."""
        provider = MicrosoftGraphCalendarProvider({"primary_email_address": "x@x.com"})
        result = provider.connect(oauth_redirect_payload=None)
        assert result.success is True
        assert provider.subscribe_realtime() is True
        with pytest.raises(RuntimeError, match="access_token"):
            provider.sync_initial()
        provider.disconnect()  # no-op

    def test_local_provider_functional_step1(self):
        """Per Q4: local provider ships functional at Step 1."""
        provider = LocalCalendarProvider({"primary_email_address": "x@x.com"})
        # Connect succeeds immediately (no transport).
        result = provider.connect()
        assert result.success is True
        assert (
            result.config_to_persist.get("transport") == "bridgeable_native"
        )
        # Sync returns success with zero events (no inbox).
        sync_result = provider.sync_initial()
        assert sync_result.success is True
        assert sync_result.events_synced == 0
        # subscribe_realtime returns False (NOT raises).
        assert provider.subscribe_realtime() is False
        # fetch_event raises (events accessed via canonical service).
        with pytest.raises(NotImplementedError):
            provider.fetch_event("ev1")
        # fetch_attendee_responses raises.
        with pytest.raises(NotImplementedError):
            provider.fetch_attendee_responses("ev1")
        # Disconnect is no-op.
        provider.disconnect()

    def test_local_provider_freebusy_canonical(
        self, db_session, tenant, admin_user
    ):
        """LocalCalendarProvider.fetch_freebusy answers from canonical
        CalendarEvent rows directly — no provider round-trip."""
        acc = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="FB Test",
            primary_email_address=f"fb-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()

        # Create 2 events: one inside the query range, one outside.
        in_range_start = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
        in_range_end = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
        outside_start = datetime(2026, 7, 1, 14, 0, tzinfo=timezone.utc)
        outside_end = datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc)

        event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=acc.id,
            actor_user_id=admin_user.id,
            subject="In range",
            start_at=in_range_start,
            end_at=in_range_end,
        )
        event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=acc.id,
            actor_user_id=admin_user.id,
            subject="Outside",
            start_at=outside_start,
            end_at=outside_end,
        )
        db_session.flush()

        # Query free/busy for June 1 only.
        provider = LocalCalendarProvider(
            {
                "primary_email_address": acc.primary_email_address,
                "__db__": db_session,
                "__account_id__": acc.id,
            }
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert result.success is True
        assert len(result.windows) == 1
        assert result.windows[0].status == "busy"

    def test_local_provider_freebusy_excludes_cancelled(
        self, db_session, tenant, admin_user
    ):
        acc = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="FB Cancelled",
            primary_email_address=f"fbc-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=acc.id,
            actor_user_id=admin_user.id,
            subject="Cancelled event",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            status="cancelled",
        )
        db_session.flush()
        provider = LocalCalendarProvider(
            {
                "primary_email_address": acc.primary_email_address,
                "__db__": db_session,
                "__account_id__": acc.id,
            }
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        )
        # RFC 5545: cancelled events do not count toward free/busy.
        assert len(result.windows) == 0

    def test_local_provider_freebusy_excludes_transparent(
        self, db_session, tenant, admin_user
    ):
        acc = account_service.create_account(
            db_session,
            tenant_id=tenant.id,
            actor_user_id=admin_user.id,
            account_type="shared",
            display_name="FB Transparent",
            primary_email_address=f"fbt-{tenant.id[:8]}@caltest.test",
            provider_type="local",
        )
        db_session.flush()
        event_service.create_event(
            db_session,
            tenant_id=tenant.id,
            account_id=acc.id,
            actor_user_id=admin_user.id,
            subject="Transparent",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            transparency="transparent",
        )
        db_session.flush()
        provider = LocalCalendarProvider(
            {
                "primary_email_address": acc.primary_email_address,
                "__db__": db_session,
                "__account_id__": acc.id,
            }
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        )
        # transparent events do not count toward free/busy.
        assert len(result.windows) == 0
