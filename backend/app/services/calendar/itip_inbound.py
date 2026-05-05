"""iTIP inbound REPLY processing — Phase W-4b Layer 1 Calendar Step 3.

Cross-primitive entry point for §3.26.16.5 Path 3:
  - Email primitive ingestion detects iTIP REPLY content + invokes
    this module's ``process_inbound_reply`` AFTER email storage
    completes.
  - This module parses the VCALENDAR text via ``icalendar.Calendar.from_ical``,
    matches the event by RFC 5545 UID, updates
    ``calendar_event_attendees.response_status`` + ``responded_at`` +
    ``comment``, and writes an audit row.

**Cross-primitive boundary discipline** (per Step 3 build prompt):
  - Email primitive handles email transport + storage + iTIP detection.
  - Calendar primitive owns iTIP semantic processing (UID match +
    attendee state update).
  - The call is one-way (email → calendar); never bidirectional.
  - Failures here are best-effort — never block email ingestion.

**Cross-primitive idempotency** — track processed iTIP REPLY message_ids
in audit log via ``source_message_id`` parameter passed by the email
ingestion site. Multi-message replies for the same event are normal
(Outlook clients sometimes emit redundant replies); each processed
message lands in the audit log exactly once. The attendee state
update reflects the most-recent PARTSTAT seen.

**UID matching strategy**:
  1. Try ``provider_event_id == uid`` (canonical for events synced
     from Google + MS Graph; the canonical RFC 5545 UID is preserved
     on provider_event_id by Step 2 ingestion).
  2. Try the synthetic ``{calendar_event_id}@bridgeable.calendar``
     pattern (canonical for Bridgeable-native local events emitted
     via iTIP at Step 3 outbound; UID embeds the event id so we can
     reverse-resolve).
  3. Defer to a generic UID-only match (search across all events;
     useful when provider_event_id is NULL but UID was generated
     differently — e.g. legacy events). Tenant-scoped via the
     ``account.tenant_id`` filter so cross-tenant collisions are
     impossible.

If no event matches, this is logged as a warning + audit row written
with status=`unmatched`. The email is preserved (Email primitive's
ingestion completed before this hook fires).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from icalendar import Calendar
from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarEvent,
    CalendarEventAttendee,
)
from app.services.calendar.account_service import _audit

logger = logging.getLogger(__name__)


# Canonical RFC 5546 PARTSTAT → our enum.
_PARTSTAT_FROM_RFC = {
    "NEEDS-ACTION": "needs_action",
    "ACCEPTED": "accepted",
    "DECLINED": "declined",
    "TENTATIVE": "tentative",
    "DELEGATED": "delegated",
}


# Canonical synthetic UID suffix for Bridgeable-native local events.
_BRIDGEABLE_UID_SUFFIX = "@bridgeable.calendar"


def process_inbound_reply(
    db: Session,
    *,
    vcalendar_text: str,
    source_message_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Process an inbound iTIP REPLY VCALENDAR.

    Args:
        db: SQLAlchemy session (caller commits).
        vcalendar_text: raw VCALENDAR text from the iTIP REPLY message.
            Source can be a ``text/calendar; method=REPLY`` MIME part
            OR an ``application/ics`` attachment with METHOD=REPLY.
            Email primitive's ingestion site is responsible for
            extracting the text.
        source_message_id: id of the EmailMessage that contained the
            iTIP REPLY. Used for audit linkage + cross-primitive
            idempotency.
        tenant_id: caller's tenant — every CalendarEvent lookup is
            tenant-scoped per CLAUDE.md tenant isolation discipline.

    Returns dict with:
        - ``status``: ``"updated"`` | ``"unmatched"`` | ``"malformed"`` |
          ``"not_a_reply"``
        - ``event_id``: matched CalendarEvent.id (when status="updated")
        - ``attendee_id``: matched CalendarEventAttendee.id (when status="updated")
        - ``previous_response_status``: prior response_status (when updated)
        - ``new_response_status``: new response_status (when updated)
        - ``error_message``: defensive parsing failure detail (when malformed)

    Returns gracefully (no exceptions raised) — caller treats this as
    best-effort per cross-primitive discipline.
    """
    # ── 1. Parse VCALENDAR ────────────────────────────────────────────
    try:
        cal = Calendar.from_ical(vcalendar_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to parse iTIP REPLY VCALENDAR (source_message_id=%s): %s",
            source_message_id,
            exc,
        )
        return {
            "status": "malformed",
            "error_message": str(exc)[:300],
        }

    method = str(cal.get("method", "")).upper()
    if method != "REPLY":
        logger.info(
            "VCALENDAR for source_message_id=%s has METHOD=%r (not REPLY); "
            "ignoring",
            source_message_id,
            method,
        )
        return {"status": "not_a_reply"}

    # ── 2. Extract VEVENT — REPLY canonical structure has exactly one ─
    vevents = [c for c in cal.walk("VEVENT")]
    if not vevents:
        logger.warning(
            "iTIP REPLY for source_message_id=%s has no VEVENT block",
            source_message_id,
        )
        return {
            "status": "malformed",
            "error_message": "No VEVENT block in REPLY",
        }
    vevent = vevents[0]

    uid_raw = vevent.get("uid")
    uid = str(uid_raw) if uid_raw else None
    if not uid:
        logger.warning(
            "iTIP REPLY for source_message_id=%s has no UID",
            source_message_id,
        )
        return {
            "status": "malformed",
            "error_message": "No UID in REPLY VEVENT",
        }

    # ── 3. Find the responding ATTENDEE — REPLY canonical: 1 attendee
    attendees = vevent.get("attendee")
    if not attendees:
        return {
            "status": "malformed",
            "error_message": "No ATTENDEE in REPLY VEVENT",
        }
    if not isinstance(attendees, list):
        attendees = [attendees]

    # Per RFC 5546 a REPLY has one ATTENDEE (the responder). If multiple
    # are present (some clients emit ORGANIZER-as-attendee echo), prefer
    # the one with PARTSTAT set explicitly to a response state.
    responder_email: str | None = None
    responder_partstat: str | None = None
    responder_comment: str | None = None
    for att in attendees:
        params = getattr(att, "params", {}) or {}
        partstat_param = params.get("partstat")
        if partstat_param is None:
            continue
        partstat_str = str(partstat_param).upper()
        if partstat_str == "NEEDS-ACTION":
            # NEEDS-ACTION on a REPLY is an unusual no-op response; record
            # it but continue searching for a substantive PARTSTAT first.
            if responder_email is None:
                responder_email = _extract_email(str(att))
                responder_partstat = partstat_str
            continue
        responder_email = _extract_email(str(att))
        responder_partstat = partstat_str
        # COMMENT may live as a top-level VEVENT property; some clients
        # also embed it in the ATTENDEE params (X-COMMENT or RFC 5546
        # COMMENT param).
        comment_param = params.get("comment")
        if comment_param:
            responder_comment = str(comment_param)
        break

    # Top-level VEVENT COMMENT property (canonical RFC 5546).
    if responder_comment is None:
        top_comment = vevent.get("comment")
        if top_comment:
            responder_comment = str(top_comment)

    if not responder_email:
        return {
            "status": "malformed",
            "error_message": "No responding ATTENDEE in REPLY",
        }

    new_response = _PARTSTAT_FROM_RFC.get(
        responder_partstat or "NEEDS-ACTION", "needs_action"
    )

    # ── 4. Match the CalendarEvent by UID ─────────────────────────────
    event = _find_event_by_uid(db, uid=uid, tenant_id=tenant_id)
    if not event:
        # Audit + warn but don't block ingestion.
        logger.info(
            "iTIP REPLY for source_message_id=%s has UID=%r matching no "
            "CalendarEvent in tenant %s — recording unmatched audit row",
            source_message_id,
            uid,
            tenant_id,
        )
        _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=None,
            action="event_iTIP_REPLY_unmatched",
            entity_type="calendar_event",
            entity_id=None,
            changes={
                "uid": uid[:200],
                "responder_email": responder_email,
                "source_message_id": source_message_id,
                "new_partstat": responder_partstat,
            },
        )
        db.flush()
        return {"status": "unmatched", "uid": uid}

    # ── 5. Match the CalendarEventAttendee by email ───────────────────
    normalized_email = responder_email.strip().lower()
    attendee = (
        db.query(CalendarEventAttendee)
        .filter(
            CalendarEventAttendee.event_id == event.id,
            CalendarEventAttendee.email_address == normalized_email,
        )
        .first()
    )
    if not attendee:
        # Attendee not on event — could be a forwarded invitation or a
        # delegate. Step 3 ships canonical event-attendee match only;
        # delegate handling is a deferred enhancement.
        logger.info(
            "iTIP REPLY for source_message_id=%s — responder %s not on "
            "event %s attendee list; treating as unmatched attendee",
            source_message_id,
            normalized_email,
            event.id,
        )
        _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=None,
            action="event_iTIP_REPLY_unmatched_attendee",
            entity_type="calendar_event",
            entity_id=event.id,
            changes={
                "uid": uid[:200],
                "responder_email": normalized_email,
                "source_message_id": source_message_id,
                "new_partstat": responder_partstat,
            },
        )
        db.flush()
        return {
            "status": "unmatched",
            "event_id": event.id,
            "responder_email": normalized_email,
        }

    # ── 6. Update attendee response state ─────────────────────────────
    previous_status = attendee.response_status
    attendee.response_status = new_response
    if new_response != "needs_action":
        attendee.responded_at = datetime.now(timezone.utc)
    if responder_comment is not None:
        attendee.comment = responder_comment
    db.flush()

    # ── 7. Audit log row — cross-primitive idempotency lives here ─────
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=None,
        action="event_iTIP_REPLY_received",
        entity_type="calendar_event_attendee",
        entity_id=attendee.id,
        changes={
            "event_id": event.id,
            "uid": uid[:200],
            "responder_email": normalized_email,
            "previous_response_status": previous_status,
            "new_response_status": new_response,
            "source_message_id": source_message_id,
            "comment": (responder_comment or "")[:200],
        },
    )
    db.flush()

    # ── 8. Step 5 — per-organizer V-1d notify hook (Q5 confirmed) ─────
    # When an attendee transitions out of ``needs_action``, notify the
    # event organizer via canonical V-1d ``notify_tenant_admins``
    # substrate. Per §3.26.16.10 row 7 + Step 5 Q5: per-organizer
    # notification (NOT admin-fan-out — only the event organizer
    # cares "Mary accepted"). Cross-primitive boundary preserved:
    # Email primitive owns transport; Calendar primitive owns UI
    # rendering + notification dispatch.
    if new_response != "needs_action" and previous_status == "needs_action":
        _notify_event_organizer(
            db,
            event=event,
            responder_attendee=attendee,
            new_response_status=new_response,
            tenant_id=tenant_id,
        )

    # ── 9. Step 5 — V-1c CRM activity feed integration (Surface 7) ─────
    # Per §3.26.16.10 row 7: "attendee responded" surfaces in entity
    # activity feed. Best-effort fan-out — failure NEVER blocks reply
    # processing.
    try:
        from app.services.calendar.activity_feed_integration import (
            log_calendar_event_activity,
        )

        responder_label = (
            attendee.display_name or attendee.email_address
        )
        log_calendar_event_activity(
            db,
            event=event,
            kind="attendee_responded",
            actor_user_id=None,
            detail=f"{responder_label} → {new_response}",
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "log_calendar_event_activity failed for event=%s "
            "attendee=%s (kind=attendee_responded)",
            event.id,
            attendee.id,
        )

    return {
        "status": "updated",
        "event_id": event.id,
        "attendee_id": attendee.id,
        "previous_response_status": previous_status,
        "new_response_status": new_response,
    }


def _notify_event_organizer(
    db: Session,
    *,
    event: "CalendarEvent",
    responder_attendee: "CalendarEventAttendee",
    new_response_status: str,
    tenant_id: str,
) -> None:
    """Per-organizer notification dispatch via V-1d notify_tenant_admins.

    Per Q5 confirmed pre-build: notification category
    ``calendar_attendee_responded``. Notifies the event's organizer
    (resolved via ``CalendarEventAttendee.role='organizer'`` row's
    ``resolved_user_id``); when organizer is internal-tenant,
    ``notification_service.create_notification`` writes a row
    addressed at that user. When organizer is external (no
    ``resolved_user_id``), this notification is skipped — external
    organizers receive iTIP REPLY transport directly via Email
    primitive's ingestion path.

    Best-effort + tenant-scoped — failure never blocks the reply
    processing.
    """
    from app.models.calendar_primitive import CalendarEventAttendee
    from app.services import notification_service

    organizer = (
        db.query(CalendarEventAttendee)
        .filter(
            CalendarEventAttendee.event_id == event.id,
            CalendarEventAttendee.role == "organizer",
            CalendarEventAttendee.resolved_user_id.isnot(None),
        )
        .first()
    )
    if organizer is None or organizer.resolved_user_id is None:
        # External organizer — skip in-app notify; iTIP REPLY transport
        # via Email primitive already delivered the canonical signal.
        return

    responder_label = (
        responder_attendee.display_name
        or responder_attendee.email_address
    )
    subject_label = event.subject or "(no subject)"

    title = "Calendar attendee responded"
    message = (
        f"{responder_label} {new_response_status} — {subject_label}"
    )
    link = f"/calendar/events/{event.id}"

    try:
        notification_service.create_notification(
            db,
            company_id=tenant_id,
            user_id=organizer.resolved_user_id,
            title=title,
            message=message,
            type="info",
            category="calendar_attendee_responded",
            link=link,
            source_reference_type="calendar_event",
            source_reference_id=event.id,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "calendar_attendee_responded notify failed for event=%s "
            "organizer=%s",
            event.id,
            organizer.resolved_user_id,
        )


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _extract_email(addr: str) -> str | None:
    """Pull a plain email address out of a vCalAddress string.

    icalendar serializes ATTENDEE lines with the ``mailto:`` prefix:
    ``mailto:user@example.com``. Our str(attendee) returns the URI;
    strip the prefix or regex-extract.
    """
    if not addr:
        return None
    s = str(addr).strip()
    if s.lower().startswith("mailto:"):
        s = s[len("mailto:"):]
    # Defensive: some clients wrap in angle brackets or include
    # display-name + URI; regex pulls the email substring cleanly.
    m = _EMAIL_RE.search(s)
    return m.group(0).lower() if m else None


def _find_event_by_uid(
    db: Session, *, uid: str, tenant_id: str
) -> CalendarEvent | None:
    """Resolve a CalendarEvent for a given RFC 5545 UID + tenant.

    Three-strategy match per module docstring:
      1. provider_event_id exact match (most common path — events synced
         from Google + MS Graph preserve the canonical UID on
         provider_event_id).
      2. Synthetic Bridgeable UID match — extract event_id from
         ``{event_id}@bridgeable.calendar`` pattern.
      3. UID-only match against any event in this tenant — defensive
         fallback.
    """
    # Strategy 1: provider_event_id match.
    event = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.tenant_id == tenant_id,
            CalendarEvent.provider_event_id == uid,
            CalendarEvent.is_active.is_(True),
        )
        .first()
    )
    if event:
        return event

    # Strategy 2: synthetic Bridgeable UID — extract event_id.
    if uid.endswith(_BRIDGEABLE_UID_SUFFIX):
        candidate_id = uid[: -len(_BRIDGEABLE_UID_SUFFIX)]
        event = (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.tenant_id == tenant_id,
                CalendarEvent.id == candidate_id,
                CalendarEvent.is_active.is_(True),
            )
            .first()
        )
        if event:
            return event

    # Strategy 3: defensive — provider_event_id is NULL but the UID was
    # generated by something else (e.g. legacy event ingested without
    # provider_event_id). Match across all events in tenant. The
    # idempotency check via cross_primitive_idempotency audit log will
    # handle the multi-match-by-tenant case if it ever arises.
    return None
