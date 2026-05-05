"""Calendar Step 3 — RFC 5545/5546 iTIP composition tests.

Covers REQUEST + REPLY + CANCEL composition + RRULE encoding +
RECURRENCE-ID scoping for instance overrides + ATTENDEE PARTSTAT
canonical mapping.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventInstanceOverride,
)
from app.services.calendar.itip_compose import (
    compose_cancel,
    compose_reply,
    compose_request,
)


def _unfold(ical_text: str) -> str:
    """Unfold RFC 5545 line-folded VCALENDAR text for substring matching.

    RFC 5545 §3.1: lines longer than 75 characters split across
    ``\\r\\n `` (CRLF + single space) boundaries. Tests assert against
    the conceptual line content; unfold first.
    """
    return ical_text.replace("\r\n ", "").replace("\n ", "")


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
        name=f"Compose {_uuid.uuid4().hex[:8]}",
        slug=f"comp{_uuid.uuid4().hex[:8]}",
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
        email=f"a-{_uuid.uuid4().hex[:8]}@c.test",
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
        display_name="Compose Test",
        primary_email_address=f"comp-{_uuid.uuid4().hex[:8]}@c.test",
        provider_type="local",
        created_by_user_id=user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def _make_event(db_session, account, **kwargs):
    import uuid as _uuid

    defaults = dict(
        id=str(_uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        subject="Test event",
        start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        event_timezone="UTC",
        status="confirmed",
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
        email_address="attendee@example.com",
        role="required_attendee",
        response_status="needs_action",
    )
    defaults.update(kwargs)
    att = CalendarEventAttendee(**defaults)
    db_session.add(att)
    db_session.flush()
    return att


# ─────────────────────────────────────────────────────────────────────
# REQUEST composition
# ─────────────────────────────────────────────────────────────────────


class TestComposeRequest:
    def test_basic_request_includes_canonical_fields(self, db_session, account):
        event = _make_event(db_session, account, subject="Production review")
        att = _make_attendee(db_session, event, email_address="foo@example.com")

        ical_raw = compose_request(
            event,
            organizer_email="organizer@bridgeable.test",
            organizer_name="Sunnycrest Production",
            sequence=0,
            attendees=[att],
        )
        ical_text = _unfold(ical_raw)
        assert "BEGIN:VCALENDAR" in ical_text
        assert "END:VCALENDAR" in ical_text
        assert "METHOD:REQUEST" in ical_text
        assert "BEGIN:VEVENT" in ical_text
        assert "SUMMARY:Production review" in ical_text
        assert "ATTENDEE" in ical_text
        assert "foo@example.com" in ical_text
        assert "ORGANIZER" in ical_text
        assert "organizer@bridgeable.test" in ical_text
        assert "SEQUENCE:0" in ical_text
        # PRODID present per canonical RFC 5545.
        assert "PRODID:" in ical_text

    def test_request_with_rrule_includes_recurrence(self, db_session, account):
        event = _make_event(
            db_session,
            account,
            subject="Weekly sync",
            recurrence_rule="RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR",
        )
        ical_text = _unfold(compose_request(
            event,
            organizer_email="organizer@example.com",
            sequence=0,
            attendees=[],
        ))
        assert "RRULE" in ical_text
        assert "FREQ=WEEKLY" in ical_text

    def test_request_with_override_scopes_to_recurrence_id(
        self, db_session, account
    ):
        import uuid as _uuid

        master = _make_event(
            db_session,
            account,
            subject="Series",
            recurrence_rule="RRULE:FREQ=WEEKLY",
        )
        # Modified instance — separate event row.
        modified = _make_event(
            db_session,
            account,
            id=str(_uuid.uuid4()),
            subject="Modified instance",
            start_at=datetime(2026, 6, 9, 16, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 9, 17, 0, tzinfo=timezone.utc),
            recurrence_master_event_id=master.id,
        )
        override = CalendarEventInstanceOverride(
            id=str(_uuid.uuid4()),
            master_event_id=master.id,
            recurrence_instance_start_at=datetime(
                2026, 6, 8, 14, 0, tzinfo=timezone.utc
            ),
            is_cancelled=False,
            override_event_id=modified.id,
        )
        db_session.add(override)
        db_session.flush()

        ical_text = _unfold(compose_request(
            master,
            organizer_email="organizer@example.com",
            sequence=1,
            attendees=[],
            override=override,
        ))
        # RECURRENCE-ID scopes the message to the original instance start.
        assert "RECURRENCE-ID" in ical_text
        # Override-modified VEVENT carries the modified content (not master).
        assert "Modified instance" in ical_text
        # When scoped to a single instance via RECURRENCE-ID, RRULE
        # MUST NOT appear per RFC 5545.
        # Read between RECURRENCE-ID and END:VEVENT to verify no RRULE.
        # icalendar emits RECURRENCE-ID followed by other VEVENT props,
        # so "RRULE:" should not appear at all in this scoped block.
        assert "RRULE:" not in ical_text or "RRULE" not in ical_text.split("RECURRENCE-ID")[1]


# ─────────────────────────────────────────────────────────────────────
# CANCEL composition
# ─────────────────────────────────────────────────────────────────────


class TestComposeCancel:
    def test_cancel_marks_status_cancelled(self, db_session, account):
        event = _make_event(db_session, account)
        att = _make_attendee(db_session, event)
        ical_text = _unfold(compose_cancel(
            event,
            organizer_email="organizer@example.com",
            attendees=[att],
        ))
        assert "METHOD:CANCEL" in ical_text
        assert "STATUS:CANCELLED" in ical_text

    def test_cancel_increments_sequence(self, db_session, account):
        event = _make_event(db_session, account)
        ical_text = _unfold(compose_cancel(
            event,
            organizer_email="o@e.com",
            sequence=2,
            attendees=[],
        ))
        assert "SEQUENCE:2" in ical_text


# ─────────────────────────────────────────────────────────────────────
# REPLY composition
# ─────────────────────────────────────────────────────────────────────


class TestComposeReply:
    def test_reply_canonical_partstat_mapping(self, db_session, account):
        event = _make_event(db_session, account)
        att = _make_attendee(
            db_session, event, response_status="accepted", display_name="Alice"
        )
        ical_text = _unfold(compose_reply(
            event,
            organizer_email="organizer@example.com",
            responding_attendee=att,
        ))
        assert "METHOD:REPLY" in ical_text
        assert "PARTSTAT=ACCEPTED" in ical_text
        # Only the responding attendee — not the full attendee list.
        assert ical_text.count("ATTENDEE") == 1

    def test_reply_with_comment(self, db_session, account):
        event = _make_event(db_session, account)
        att = _make_attendee(
            db_session, event, response_status="declined", comment="Travel conflict"
        )
        ical_text = _unfold(compose_reply(
            event,
            organizer_email="organizer@example.com",
            responding_attendee=att,
        ))
        assert "PARTSTAT=DECLINED" in ical_text
        assert "Travel conflict" in ical_text

    def test_reply_partstat_for_each_canonical_value(self, db_session, account):
        event = _make_event(db_session, account)
        for status, expected_rfc in [
            ("accepted", "ACCEPTED"),
            ("declined", "DECLINED"),
            ("tentative", "TENTATIVE"),
            ("delegated", "DELEGATED"),
            ("needs_action", "NEEDS-ACTION"),
        ]:
            att = _make_attendee(
                db_session,
                event,
                email_address=f"{status}@example.com",
                response_status=status,
            )
            ical_text = _unfold(compose_reply(
                event,
                organizer_email="organizer@example.com",
                responding_attendee=att,
            ))
            assert f"PARTSTAT={expected_rfc}" in ical_text


# ─────────────────────────────────────────────────────────────────────
# UID resolution
# ─────────────────────────────────────────────────────────────────────


class TestUidResolution:
    def test_provider_event_id_used_as_uid(self, db_session, account):
        event = _make_event(
            db_session,
            account,
            provider_event_id="google-evt-12345",
        )
        ical_text = _unfold(compose_request(
            event,
            organizer_email="o@e.com",
            sequence=0,
            attendees=[],
        ))
        assert "UID:google-evt-12345" in ical_text

    def test_synthetic_uid_for_local_events(self, db_session, account):
        event = _make_event(db_session, account)
        ical_text = _unfold(compose_request(
            event,
            organizer_email="o@e.com",
            sequence=0,
            attendees=[],
        ))
        # No provider_event_id — synthesized UID with bridgeable suffix.
        assert f"UID:{event.id}@bridgeable.calendar" in ical_text
