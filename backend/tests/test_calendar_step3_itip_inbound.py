"""Calendar Step 3 — iTIP inbound REPLY processing tests.

Cross-primitive boundary tests per §3.26.16.5 Path 3:
  - VCALENDAR parsing — defensive on malformed input
  - UID match (provider_event_id + synthetic Bridgeable UID + miss)
  - Attendee response_status update (PARTSTAT canonical mapping)
  - Cross-primitive idempotency via audit log tracking
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAuditLog,
    CalendarEvent,
    CalendarEventAttendee,
)
from app.services.calendar.itip_inbound import process_inbound_reply


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
        name=f"Inbound {_uuid.uuid4().hex[:8]}",
        slug=f"inb{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


@pytest.fixture
def account(db_session, tenant):
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
        email=f"a-{_uuid.uuid4().hex[:8]}@i.test",
        hashed_password="x",
        first_name="A",
        last_name="U",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    acc = CalendarAccount(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="shared",
        display_name="Inbound Test",
        primary_email_address=f"in-{_uuid.uuid4().hex[:8]}@i.test",
        provider_type="local",
        created_by_user_id=user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def _make_event(db_session, account, *, provider_event_id=None, **kwargs):
    import uuid as _uuid

    defaults = dict(
        id=str(_uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        subject="Inbound test event",
        start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        event_timezone="UTC",
        status="confirmed",
        transparency="opaque",
        provider_event_id=provider_event_id,
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
        email_address="responder@example.com",
        role="required_attendee",
        response_status="needs_action",
    )
    defaults.update(kwargs)
    att = CalendarEventAttendee(**defaults)
    db_session.add(att)
    db_session.flush()
    return att


def _build_reply_vcalendar(
    *,
    uid: str,
    organizer_email: str,
    attendee_email: str,
    partstat: str,
    comment: str | None = None,
) -> str:
    """Build a canonical iTIP REPLY VCALENDAR for testing."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Test//iTIP REPLY//EN",
        "METHOD:REPLY",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        "DTSTAMP:20260601T120000Z",
        "DTSTART:20260601T140000Z",
        "DTEND:20260601T150000Z",
        "SUMMARY:Test Event",
        f"ORGANIZER:mailto:{organizer_email}",
        f"ATTENDEE;PARTSTAT={partstat};ROLE=REQ-PARTICIPANT:mailto:{attendee_email}",
    ]
    if comment:
        lines.append(f"COMMENT:{comment}")
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(lines) + "\r\n"


# ─────────────────────────────────────────────────────────────────────
# Defensive parsing
# ─────────────────────────────────────────────────────────────────────


class TestDefensiveParsing:
    def test_malformed_vcalendar_returns_malformed(self, db_session, tenant):
        result = process_inbound_reply(
            db_session,
            vcalendar_text="not a vcalendar at all",
            source_message_id="msg-1",
            tenant_id=tenant.id,
        )
        assert result["status"] == "malformed"

    def test_non_reply_method_returns_not_a_reply(self, db_session, tenant):
        ical = _build_reply_vcalendar(
            uid="evt-1",
            organizer_email="o@example.com",
            attendee_email="r@example.com",
            partstat="ACCEPTED",
        ).replace("METHOD:REPLY", "METHOD:REQUEST")
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-1",
            tenant_id=tenant.id,
        )
        assert result["status"] == "not_a_reply"


# ─────────────────────────────────────────────────────────────────────
# UID matching strategies
# ─────────────────────────────────────────────────────────────────────


class TestUidMatching:
    def test_match_via_provider_event_id(self, db_session, account):
        event = _make_event(
            db_session, account, provider_event_id="google-evt-canonical-uid"
        )
        att = _make_attendee(db_session, event)
        ical = _build_reply_vcalendar(
            uid="google-evt-canonical-uid",
            organizer_email="organizer@bridgeable.test",
            attendee_email=att.email_address,
            partstat="ACCEPTED",
        )
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-1",
            tenant_id=account.tenant_id,
        )
        assert result["status"] == "updated"
        assert result["event_id"] == event.id

    def test_match_via_synthetic_bridgeable_uid(self, db_session, account):
        event = _make_event(db_session, account)  # no provider_event_id
        att = _make_attendee(db_session, event)
        synthetic_uid = f"{event.id}@bridgeable.calendar"
        ical = _build_reply_vcalendar(
            uid=synthetic_uid,
            organizer_email="organizer@bridgeable.test",
            attendee_email=att.email_address,
            partstat="DECLINED",
        )
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-2",
            tenant_id=account.tenant_id,
        )
        assert result["status"] == "updated"
        assert result["event_id"] == event.id

    def test_unmatched_uid_logs_audit(self, db_session, account):
        ical = _build_reply_vcalendar(
            uid="not-a-real-uid-12345",
            organizer_email="o@example.com",
            attendee_email="r@example.com",
            partstat="ACCEPTED",
        )
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-3",
            tenant_id=account.tenant_id,
        )
        assert result["status"] == "unmatched"
        # Audit row written.
        audits = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.tenant_id == account.tenant_id,
                CalendarAuditLog.action == "event_iTIP_REPLY_unmatched",
            )
            .all()
        )
        assert len(audits) >= 1


# ─────────────────────────────────────────────────────────────────────
# Attendee response state updates
# ─────────────────────────────────────────────────────────────────────


class TestAttendeeResponseUpdate:
    def test_accepted_partstat_updates_response_status(
        self, db_session, account
    ):
        event = _make_event(db_session, account, provider_event_id="evt-A")
        att = _make_attendee(
            db_session, event, email_address="alice@example.com"
        )
        assert att.response_status == "needs_action"
        assert att.responded_at is None

        ical = _build_reply_vcalendar(
            uid="evt-A",
            organizer_email="o@example.com",
            attendee_email="alice@example.com",
            partstat="ACCEPTED",
        )
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-A",
            tenant_id=account.tenant_id,
        )
        assert result["status"] == "updated"
        assert result["new_response_status"] == "accepted"

        db_session.refresh(att)
        assert att.response_status == "accepted"
        assert att.responded_at is not None

    def test_declined_with_comment(self, db_session, account):
        event = _make_event(db_session, account, provider_event_id="evt-D")
        att = _make_attendee(
            db_session, event, email_address="bob@example.com"
        )
        ical = _build_reply_vcalendar(
            uid="evt-D",
            organizer_email="o@example.com",
            attendee_email="bob@example.com",
            partstat="DECLINED",
            comment="Travel conflict",
        )
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-D",
            tenant_id=account.tenant_id,
        )
        assert result["status"] == "updated"
        db_session.refresh(att)
        assert att.response_status == "declined"
        assert att.comment == "Travel conflict"

    def test_tentative_partstat_canonical(self, db_session, account):
        event = _make_event(db_session, account, provider_event_id="evt-T")
        att = _make_attendee(db_session, event, email_address="t@example.com")
        ical = _build_reply_vcalendar(
            uid="evt-T",
            organizer_email="o@example.com",
            attendee_email="t@example.com",
            partstat="TENTATIVE",
        )
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-T",
            tenant_id=account.tenant_id,
        )
        assert result["status"] == "updated"
        db_session.refresh(att)
        assert att.response_status == "tentative"


# ─────────────────────────────────────────────────────────────────────
# Cross-primitive idempotency + tenant isolation
# ─────────────────────────────────────────────────────────────────────


class TestCrossPrimitiveIdempotency:
    def test_multiple_replies_track_via_audit(self, db_session, account):
        """Multi-message replies for same event update most-recent state.

        Each reply emits one audit row with source_message_id; the
        audit log preserves the multi-message history.
        """
        event = _make_event(db_session, account, provider_event_id="evt-M")
        att = _make_attendee(db_session, event, email_address="m@example.com")

        # First reply: tentative.
        ical_1 = _build_reply_vcalendar(
            uid="evt-M",
            organizer_email="o@example.com",
            attendee_email="m@example.com",
            partstat="TENTATIVE",
        )
        process_inbound_reply(
            db_session,
            vcalendar_text=ical_1,
            source_message_id="msg-first",
            tenant_id=account.tenant_id,
        )

        # Second reply for the SAME event (Outlook redundant emit):
        # accepted.
        ical_2 = _build_reply_vcalendar(
            uid="evt-M",
            organizer_email="o@example.com",
            attendee_email="m@example.com",
            partstat="ACCEPTED",
        )
        process_inbound_reply(
            db_session,
            vcalendar_text=ical_2,
            source_message_id="msg-second",
            tenant_id=account.tenant_id,
        )

        # Most-recent state wins.
        db_session.refresh(att)
        assert att.response_status == "accepted"

        # Audit log carries both messages.
        audits = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.tenant_id == account.tenant_id,
                CalendarAuditLog.action == "event_iTIP_REPLY_received",
            )
            .all()
        )
        assert len(audits) == 2
        message_ids = {a.changes.get("source_message_id") for a in audits}
        assert message_ids == {"msg-first", "msg-second"}

    def test_unmatched_attendee_logs_audit(self, db_session, account):
        """Reply from someone not on the attendee list — log + skip update."""
        event = _make_event(db_session, account, provider_event_id="evt-U")
        att = _make_attendee(
            db_session, event, email_address="known@example.com"
        )

        ical = _build_reply_vcalendar(
            uid="evt-U",
            organizer_email="o@example.com",
            attendee_email="someone-else@example.com",
            partstat="ACCEPTED",
        )
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-unmatched-att",
            tenant_id=account.tenant_id,
        )
        assert result["status"] == "unmatched"

        # Original attendee state untouched.
        db_session.refresh(att)
        assert att.response_status == "needs_action"

    def test_tenant_isolation_uid_not_found_in_other_tenant(
        self, db_session, account
    ):
        """Event in tenant A with UID 'shared-uid' is not matched when
        the reply arrives in tenant B's pipeline."""
        import uuid as _uuid

        # Create a separate tenant.
        other_co = Company(
            id=str(_uuid.uuid4()),
            name="Other Tenant",
            slug=f"other{_uuid.uuid4().hex[:6]}",
            vertical="manufacturing",
        )
        db_session.add(other_co)
        db_session.flush()

        # Event in tenant A.
        event = _make_event(
            db_session, account, provider_event_id="shared-uid"
        )

        # Reply arrives with tenant_id of OTHER tenant.
        ical = _build_reply_vcalendar(
            uid="shared-uid",
            organizer_email="o@example.com",
            attendee_email="any@example.com",
            partstat="ACCEPTED",
        )
        result = process_inbound_reply(
            db_session,
            vcalendar_text=ical,
            source_message_id="msg-cross",
            tenant_id=other_co.id,  # WRONG tenant
        )
        # Cross-tenant lookup misses — UID not found in the other tenant.
        assert result["status"] == "unmatched"
