"""Calendar Step 3 — outbound_service orchestration tests.

Per §3.26.16.5 outbound canon + drafted-not-auto-sent discipline:
  - send_event flips status tentative → confirmed only on provider success
  - cancel_event flips status to "cancelled" + emits METHOD=CANCEL
  - Provider failures preserve tentative state + audit failure
  - Audit log writes for every outbound operation (success + failure)
  - Tenant isolation + access control via user_has_access
  - outbound_enabled gate per account
  - Idempotent re-cancel returns "already_cancelled" no-op
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountAccess,
    CalendarAuditLog,
    CalendarEvent,
    CalendarEventAttendee,
)
from app.services.calendar.outbound_service import (
    OutboundDisabled,
    OutboundError,
    OutboundProviderError,
    cancel_event,
    send_event,
)
from app.services.calendar.account_service import (
    CalendarAccountPermissionDenied,
)
from app.services.calendar.providers.base import ProviderSendEventResult


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def tenant(db_session):
    import uuid as _uuid

    co = Company(
        id=str(_uuid.uuid4()),
        name=f"Outbound {_uuid.uuid4().hex[:8]}",
        slug=f"out{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


@pytest.fixture
def user(db_session, tenant):
    import uuid as _uuid

    role = Role(
        id=str(_uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(_uuid.uuid4()),
        email=f"u-{_uuid.uuid4().hex[:8]}@o.test",
        hashed_password="x",
        first_name="O",
        last_name="U",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def account(db_session, tenant, user):
    import uuid as _uuid

    acc = CalendarAccount(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="shared",
        display_name="Outbound Test",
        primary_email_address=f"out-{_uuid.uuid4().hex[:8]}@o.test",
        provider_type="local",
        outbound_enabled=True,
        created_by_user_id=user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


@pytest.fixture
def access_grant(db_session, account, user):
    import uuid as _uuid

    grant = CalendarAccountAccess(
        id=str(_uuid.uuid4()),
        account_id=account.id,
        user_id=user.id,
        tenant_id=account.tenant_id,
        access_level="admin",
    )
    db_session.add(grant)
    db_session.flush()
    return grant


def _make_event(db_session, account, **kwargs):
    import uuid as _uuid

    defaults = dict(
        id=str(_uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        subject="Outbound test event",
        start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        event_timezone="UTC",
        status="tentative",
        transparency="opaque",
    )
    defaults.update(kwargs)
    event = CalendarEvent(**defaults)
    db_session.add(event)
    db_session.flush()
    return event


def _make_attendee(db_session, event, **kwargs):
    import uuid as _uuid

    defaults = dict(
        id=str(_uuid.uuid4()),
        event_id=event.id,
        tenant_id=event.tenant_id,
        email_address="invitee@example.com",
        role="required_attendee",
        response_status="needs_action",
    )
    defaults.update(kwargs)
    att = CalendarEventAttendee(**defaults)
    db_session.add(att)
    db_session.flush()
    return att


# ─────────────────────────────────────────────────────────────────────
# send_event happy path
# ─────────────────────────────────────────────────────────────────────


class TestSendEventSuccess:
    def test_send_flips_tentative_to_confirmed(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account)
        _make_attendee(db_session, event)

        result = send_event(db_session, event=event, sender=user)
        db_session.flush()

        assert result["status"] == "sent"
        assert result["event_id"] == event.id
        assert result["recipient_count"] == 1
        # Local provider returns no provider_event_id; status flips.
        db_session.refresh(event)
        assert event.status == "confirmed"

    def test_send_writes_event_sent_audit_row(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account)
        _make_attendee(
            db_session, event, email_address="alice@example.com"
        )
        _make_attendee(
            db_session, event, email_address="bob@example.com"
        )

        send_event(db_session, event=event, sender=user)
        db_session.flush()

        audit_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == event.id,
                CalendarAuditLog.action == "event_sent",
            )
            .all()
        )
        assert len(audit_rows) == 1
        changes = audit_rows[0].changes or {}
        assert changes.get("method") == "REQUEST"
        assert changes.get("recipient_count") == 2
        recipients = set(changes.get("recipients") or [])
        assert recipients == {"alice@example.com", "bob@example.com"}

    def test_send_persists_provider_event_id_when_returned(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account)
        _make_attendee(db_session, event)

        with patch(
            "app.services.calendar.providers.local.LocalCalendarProvider.send_event",
            return_value=ProviderSendEventResult(
                success=True,
                provider_event_id="google-evt-123",
                provider_calendar_id=None,
                error_message=None,
            ),
        ):
            send_event(db_session, event=event, sender=user)
        db_session.flush()
        db_session.refresh(event)
        assert event.provider_event_id == "google-evt-123"

    def test_send_already_confirmed_event_resends(
        self, db_session, account, user, access_grant
    ):
        # Already-confirmed events can be re-sent (re-issues iTIP REQUEST).
        event = _make_event(db_session, account, status="confirmed")
        _make_attendee(db_session, event)
        result = send_event(db_session, event=event, sender=user)
        assert result["status"] == "sent"


# ─────────────────────────────────────────────────────────────────────
# send_event failure paths
# ─────────────────────────────────────────────────────────────────────


class TestSendEventFailures:
    def test_send_provider_failure_preserves_tentative(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account)
        _make_attendee(db_session, event)

        with patch(
            "app.services.calendar.providers.local.LocalCalendarProvider.send_event",
            return_value=ProviderSendEventResult(
                success=False,
                provider_event_id=None,
                provider_calendar_id=None,
                error_message="provider rate-limited",
                error_retryable=True,
            ),
        ):
            with pytest.raises(OutboundProviderError):
                send_event(db_session, event=event, sender=user)

        db_session.refresh(event)
        # Status stays tentative on failure.
        assert event.status == "tentative"

        audit_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == event.id,
                CalendarAuditLog.action == "event_send_failed",
            )
            .all()
        )
        assert len(audit_rows) == 1
        assert "rate-limited" in (audit_rows[0].changes or {}).get(
            "error_message", ""
        )

    def test_send_outbound_disabled_raises(
        self, db_session, account, user, access_grant
    ):
        account.outbound_enabled = False
        db_session.flush()
        event = _make_event(db_session, account)
        _make_attendee(db_session, event)

        with pytest.raises(OutboundDisabled):
            send_event(db_session, event=event, sender=user)
        db_session.refresh(event)
        assert event.status == "tentative"

    def test_send_cancelled_event_rejected(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account, status="cancelled")
        _make_attendee(db_session, event)
        with pytest.raises(OutboundError):
            send_event(db_session, event=event, sender=user)


# ─────────────────────────────────────────────────────────────────────
# Access control + tenant isolation
# ─────────────────────────────────────────────────────────────────────


class TestSendEventAccessControl:
    def test_send_without_access_grant_denied(
        self, db_session, account, user
    ):
        # No access_grant fixture used here.
        event = _make_event(db_session, account)
        _make_attendee(db_session, event)
        with pytest.raises(CalendarAccountPermissionDenied):
            send_event(db_session, event=event, sender=user)

    def test_send_with_read_only_denied(
        self, db_session, account, user
    ):
        import uuid as _uuid

        # Read-only grant — insufficient for send (needs read_write+).
        grant = CalendarAccountAccess(
            id=str(_uuid.uuid4()),
            account_id=account.id,
            user_id=user.id,
            tenant_id=account.tenant_id,
            access_level="read",
        )
        db_session.add(grant)
        db_session.flush()

        event = _make_event(db_session, account)
        _make_attendee(db_session, event)
        with pytest.raises(CalendarAccountPermissionDenied):
            send_event(db_session, event=event, sender=user)

    def test_send_cross_tenant_user_denied(self, db_session, account):
        import uuid as _uuid

        # Build a separate-tenant user without any grant on `account`.
        co2 = Company(
            id=str(_uuid.uuid4()),
            name=f"Other {_uuid.uuid4().hex[:8]}",
            slug=f"oth{_uuid.uuid4().hex[:8]}",
            vertical="manufacturing",
        )
        db_session.add(co2)
        db_session.flush()
        role2 = Role(
            id=str(_uuid.uuid4()),
            company_id=co2.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db_session.add(role2)
        db_session.flush()
        other_user = User(
            id=str(_uuid.uuid4()),
            email=f"x-{_uuid.uuid4().hex[:8]}@x.test",
            hashed_password="x",
            first_name="X",
            last_name="U",
            company_id=co2.id,
            role_id=role2.id,
            is_active=True,
        )
        db_session.add(other_user)
        db_session.flush()

        event = _make_event(db_session, account)
        _make_attendee(db_session, event)
        with pytest.raises(CalendarAccountPermissionDenied):
            send_event(db_session, event=event, sender=other_user)


# ─────────────────────────────────────────────────────────────────────
# cancel_event
# ─────────────────────────────────────────────────────────────────────


class TestCancelEvent:
    def test_cancel_flips_to_cancelled(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account, status="confirmed")
        _make_attendee(db_session, event)

        result = cancel_event(db_session, event=event, sender=user)
        db_session.flush()

        assert result["status"] == "cancelled"
        db_session.refresh(event)
        assert event.status == "cancelled"

    def test_cancel_writes_audit_row(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account, status="confirmed")
        _make_attendee(db_session, event, email_address="x@y.test")

        cancel_event(db_session, event=event, sender=user)
        db_session.flush()

        audit_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == event.id,
                CalendarAuditLog.action == "event_cancelled",
            )
            .all()
        )
        assert len(audit_rows) == 1
        changes = audit_rows[0].changes or {}
        assert changes.get("method") == "CANCEL"
        assert "x@y.test" in (changes.get("recipients") or [])

    def test_cancel_already_cancelled_is_idempotent(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account, status="cancelled")
        _make_attendee(db_session, event)

        result = cancel_event(db_session, event=event, sender=user)
        assert result["status"] == "already_cancelled"

        # Should NOT emit a new event_cancelled audit row.
        audit_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == event.id,
                CalendarAuditLog.action == "event_cancelled",
            )
            .all()
        )
        assert audit_rows == []

    def test_cancel_provider_failure_preserves_status(
        self, db_session, account, user, access_grant
    ):
        event = _make_event(db_session, account, status="confirmed")
        _make_attendee(db_session, event)

        with patch(
            "app.services.calendar.providers.local.LocalCalendarProvider.send_event",
            return_value=ProviderSendEventResult(
                success=False,
                provider_event_id=None,
                provider_calendar_id=None,
                error_message="provider down",
                error_retryable=True,
            ),
        ):
            with pytest.raises(OutboundProviderError):
                cancel_event(db_session, event=event, sender=user)

        db_session.refresh(event)
        # Status stays confirmed on cancel failure.
        assert event.status == "confirmed"

        audit_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == event.id,
                CalendarAuditLog.action == "event_cancel_failed",
            )
            .all()
        )
        assert len(audit_rows) == 1
