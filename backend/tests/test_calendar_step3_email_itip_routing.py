"""Calendar Step 3 — cross-primitive Email→Calendar iTIP REPLY routing.

Per §3.26.16.5 Path 3 + cross-primitive boundary discipline:
  - Email primitive's ingestion pipeline calls extract_itip_reply_text
    on every inbound message.
  - When iTIP REPLY content detected, the calendar primitive's
    process_inbound_reply is invoked with extracted VCALENDAR text +
    source_message_id + tenant_id.
  - Detection covers Gmail-shape (text/calendar parts with method=REPLY
    and base64url body data) + MS Graph-shape (application/ics
    attachments with METHOD:REPLY).
  - Cross-primitive idempotency via source_message_id audit log entries.
  - Boundary discipline: extract_itip_reply_text lives in email package
    (operates on ProviderFetchedMessage); process_inbound_reply lives
    in calendar package (operates on canonical CalendarEvent state).
  - Multi-message replies tracked via audit log without double-applying
    state to the canonical attendee row.
"""

from __future__ import annotations

import base64
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
from app.services.email.itip_detection import extract_itip_reply_text
from app.services.email.providers.base import ProviderFetchedMessage


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
        name=f"Routing {_uuid.uuid4().hex[:8]}",
        slug=f"rt{_uuid.uuid4().hex[:8]}",
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
        email=f"u-{_uuid.uuid4().hex[:8]}@r.test",
        hashed_password="x",
        first_name="R",
        last_name="T",
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
        display_name="Routing test",
        primary_email_address=f"r-{_uuid.uuid4().hex[:8]}@r.test",
        provider_type="local",
        created_by_user_id=user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


# ─────────────────────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────────────────────


def _build_reply_vcalendar(
    *,
    uid: str,
    organizer_email: str,
    attendee_email: str,
    partstat: str = "ACCEPTED",
    comment: str | None = None,
) -> str:
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


def _gmail_payload_with_text_calendar(
    vcalendar_text: str,
    *,
    method_header: bool = True,
) -> dict:
    """Build a Gmail-shape raw_payload with a text/calendar; method=REPLY part."""
    body_data = base64.urlsafe_b64encode(
        vcalendar_text.encode("utf-8")
    ).decode("ascii").rstrip("=")
    headers = []
    if method_header:
        headers.append(
            {
                "name": "Content-Type",
                "value": 'text/calendar; charset="UTF-8"; method=REPLY',
            }
        )
    part = {
        "mimeType": "text/calendar",
        "headers": headers,
        "body": {"data": body_data},
    }
    return {
        "payload": {
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": ""}},
                part,
            ],
        }
    }


def _msgraph_payload_with_ics_attachment(
    vcalendar_text: str,
) -> dict:
    """Build an MS Graph-shape raw_payload with application/ics attachment."""
    content_b64 = base64.b64encode(
        vcalendar_text.encode("utf-8")
    ).decode("ascii")
    return {
        "attachments": [
            {
                "contentType": "application/ics",
                "contentBytes": content_b64,
            }
        ]
    }


def _make_message(raw_payload: dict) -> ProviderFetchedMessage:
    return ProviderFetchedMessage(
        provider_message_id="msg-routing-1",
        provider_thread_id="thread-routing-1",
        sender_email="responder@example.com",
        sender_name="Test Responder",
        to=[("organizer@bridgeable.test", "Organizer")],
        subject="Re: Test Event",
        raw_payload=raw_payload,
    )


def _make_event_with_attendee(
    db_session, account, *, provider_event_id: str, attendee_email: str
):
    import uuid as _uuid

    event = CalendarEvent(
        id=str(_uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        subject="Test Event",
        start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        event_timezone="UTC",
        status="confirmed",
        transparency="opaque",
        provider_event_id=provider_event_id,
    )
    db_session.add(event)
    db_session.flush()
    attendee = CalendarEventAttendee(
        id=str(_uuid.uuid4()),
        event_id=event.id,
        tenant_id=event.tenant_id,
        email_address=attendee_email,
        role="required_attendee",
        response_status="needs_action",
    )
    db_session.add(attendee)
    db_session.flush()
    return event, attendee


# ─────────────────────────────────────────────────────────────────────
# Detection — Gmail-shape
# ─────────────────────────────────────────────────────────────────────


class TestGmailDetection:
    def test_gmail_text_calendar_method_reply_detected_via_header(self):
        ical = _build_reply_vcalendar(
            uid="evt-1",
            organizer_email="o@e.test",
            attendee_email="a@e.test",
        )
        payload = _gmail_payload_with_text_calendar(ical, method_header=True)
        msg = _make_message(payload)

        extracted = extract_itip_reply_text(msg)
        assert extracted is not None
        assert "METHOD:REPLY" in extracted
        assert "UID:evt-1" in extracted

    def test_gmail_text_calendar_detected_via_body_method_line(self):
        # No Content-Type header but body still carries METHOD:REPLY.
        ical = _build_reply_vcalendar(
            uid="evt-2",
            organizer_email="o@e.test",
            attendee_email="a@e.test",
        )
        payload = _gmail_payload_with_text_calendar(ical, method_header=False)
        msg = _make_message(payload)

        extracted = extract_itip_reply_text(msg)
        assert extracted is not None
        assert "UID:evt-2" in extracted

    def test_non_itip_message_returns_none(self):
        msg = _make_message(
            {
                "payload": {
                    "mimeType": "text/plain",
                    "body": {"data": ""},
                    "parts": [],
                }
            }
        )
        assert extract_itip_reply_text(msg) is None

    def test_empty_raw_payload_returns_none(self):
        msg = _make_message({})
        assert extract_itip_reply_text(msg) is None


# ─────────────────────────────────────────────────────────────────────
# Detection — MS Graph-shape
# ─────────────────────────────────────────────────────────────────────


class TestMsGraphDetection:
    def test_msgraph_ics_attachment_method_reply_detected(self):
        ical = _build_reply_vcalendar(
            uid="evt-mg-1",
            organizer_email="o@e.test",
            attendee_email="a@e.test",
        )
        payload = _msgraph_payload_with_ics_attachment(ical)
        msg = _make_message(payload)

        extracted = extract_itip_reply_text(msg)
        assert extracted is not None
        assert "METHOD:REPLY" in extracted
        assert "UID:evt-mg-1" in extracted

    def test_msgraph_non_calendar_attachment_ignored(self):
        msg = _make_message(
            {
                "attachments": [
                    {
                        "contentType": "application/pdf",
                        "contentBytes": base64.b64encode(b"%PDF-").decode(),
                    }
                ]
            }
        )
        assert extract_itip_reply_text(msg) is None


# ─────────────────────────────────────────────────────────────────────
# End-to-end cross-primitive flow
# ─────────────────────────────────────────────────────────────────────


class TestCrossPrimitiveBoundary:
    def test_extract_then_process_updates_attendee(
        self, db_session, account
    ):
        # Seed the canonical event + attendee.
        event, attendee = _make_event_with_attendee(
            db_session,
            account,
            provider_event_id="evt-e2e-1",
            attendee_email="responder@example.com",
        )
        # Build the inbound email-side payload.
        ical = _build_reply_vcalendar(
            uid="evt-e2e-1",
            organizer_email="organizer@bridgeable.test",
            attendee_email="responder@example.com",
            partstat="ACCEPTED",
        )
        payload = _gmail_payload_with_text_calendar(ical)
        msg = _make_message(payload)

        extracted = extract_itip_reply_text(msg)
        assert extracted is not None

        # Hand off to the calendar primitive entry point.
        result = process_inbound_reply(
            db_session,
            vcalendar_text=extracted,
            source_message_id=msg.provider_message_id,
            tenant_id=account.tenant_id,
        )
        db_session.flush()

        assert result["status"] == "updated"
        db_session.refresh(attendee)
        assert attendee.response_status == "accepted"
        assert attendee.responded_at is not None

    def test_extract_then_process_declined_with_comment(
        self, db_session, account
    ):
        event, attendee = _make_event_with_attendee(
            db_session,
            account,
            provider_event_id="evt-decl-1",
            attendee_email="dec@example.com",
        )
        ical = _build_reply_vcalendar(
            uid="evt-decl-1",
            organizer_email="organizer@bridgeable.test",
            attendee_email="dec@example.com",
            partstat="DECLINED",
            comment="Travel conflict that week",
        )
        payload = _msgraph_payload_with_ics_attachment(ical)
        msg = _make_message(payload)

        extracted = extract_itip_reply_text(msg)
        assert extracted is not None

        process_inbound_reply(
            db_session,
            vcalendar_text=extracted,
            source_message_id=msg.provider_message_id,
            tenant_id=account.tenant_id,
        )
        db_session.refresh(attendee)
        assert attendee.response_status == "declined"
        assert attendee.comment == "Travel conflict that week"


# ─────────────────────────────────────────────────────────────────────
# Multi-message idempotency via audit log
# ─────────────────────────────────────────────────────────────────────


class TestMultiMessageIdempotency:
    def test_two_messages_two_audit_rows(self, db_session, account):
        # Same attendee replies twice via two messages — each invocation
        # writes a distinct audit row, but the canonical attendee state
        # reflects only the latest response.
        event, attendee = _make_event_with_attendee(
            db_session,
            account,
            provider_event_id="evt-multi-1",
            attendee_email="r@example.com",
        )

        # Message 1 — TENTATIVE.
        ical1 = _build_reply_vcalendar(
            uid="evt-multi-1",
            organizer_email="o@e.test",
            attendee_email="r@example.com",
            partstat="TENTATIVE",
        )
        process_inbound_reply(
            db_session,
            vcalendar_text=ical1,
            source_message_id="msg-1",
            tenant_id=account.tenant_id,
        )
        db_session.flush()

        # Message 2 — ACCEPTED (changed mind).
        ical2 = _build_reply_vcalendar(
            uid="evt-multi-1",
            organizer_email="o@e.test",
            attendee_email="r@example.com",
            partstat="ACCEPTED",
        )
        process_inbound_reply(
            db_session,
            vcalendar_text=ical2,
            source_message_id="msg-2",
            tenant_id=account.tenant_id,
        )
        db_session.flush()

        db_session.refresh(attendee)
        # Latest response wins on the canonical row.
        assert attendee.response_status == "accepted"

        # Two audit rows for the two source messages — itip_inbound
        # emits ``event_iTIP_REPLY_received`` against the attendee.id
        # (cross-primitive idempotency lives in the audit log).
        audit_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == attendee.id,
                CalendarAuditLog.action == "event_iTIP_REPLY_received",
            )
            .all()
        )
        source_msg_ids = {
            (r.changes or {}).get("source_message_id") for r in audit_rows
        }
        assert "msg-1" in source_msg_ids
        assert "msg-2" in source_msg_ids
        # The previous_response_status field documents the canonical
        # state-transition chain across the two messages.
        statuses = sorted(
            (r.changes or {}).get("new_response_status") for r in audit_rows
        )
        assert statuses == ["accepted", "tentative"]
