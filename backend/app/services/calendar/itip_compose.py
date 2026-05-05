"""iTIP composition — Phase W-4b Layer 1 Calendar Step 3.

RFC 5545 (iCalendar) + RFC 5546 (iTIP) VCALENDAR composition for
outbound event creation, update, and cancellation per §3.26.16.5
Path 1 + Path 2.

**Three canonical METHOD values shipped at Step 3**:
  - ``REQUEST`` — invite attendees to a new event OR update an existing
    event (per §3.26.16.5 Path 1 + Path 2 update; SEQUENCE incremented
    on update).
  - ``CANCEL`` — cancel an event (per §3.26.16.5 Path 2; STATUS=CANCELLED
    + tombstone propagated to attendees).
  - ``REPLY`` — composed by the canonical Bridgeable-as-attendee
    response flow (Step 3 ships compose; outbound iTIP REPLY ships at
    Step 5+ once per-attendee response actions surface).

**RECURRENCE-ID scoping** for instance overrides per §3.26.16.5 Path 2:
  - Recurrence-modification: instance override with ``override_event_id``
    creates iTIP REQUEST scoped to RECURRENCE-ID matching the original
    instance start (NOT the modified start).
  - Recurrence-cancellation: instance override with ``is_cancelled=True``
    creates iTIP CANCEL scoped to RECURRENCE-ID.

**Step 3 boundary** (deferred to later steps):
  - Counter-proposals (METHOD=COUNTER) — deferred per §3.26.16.21
    strategic vision deferral catalog
  - METHOD=REFRESH — deferred (rare client request)
  - METHOD=ADD / DECLINECOUNTER — deferred per same canon
  - VALARM blocks (alarm components) — Step 3 leaves to provider
    defaults per §3.26.16.5 reminder semantics deduplication discipline
  - VTIMEZONE blocks for cross-timezone events — Step 3 emits floating
    UTC times for events without explicit event_timezone; full VTIMEZONE
    block emission deferred until Windows-TZ → IANA mapping ships

**Library**: ``icalendar~=6.1`` (RFC 5545 + RFC 5546 support; pure-Python).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from icalendar import Calendar, Event as IcsEvent, vCalAddress, vRecur, vText

from app.models.calendar_primitive import (
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventInstanceOverride,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────


# RFC 5545 PRODID — canonical product identifier for VCALENDAR objects
# emitted by Bridgeable. Used by every outbound iTIP message.
_PRODID = "-//Bridgeable//Calendar Primitive 1.0//EN"
_VERSION = "2.0"


# RFC 5545 ROLE → iTIP ROLE map (canonical iTIP doesn't reuse our
# canonical role enum verbatim; we map to RFC 5546-compliant values).
_ROLE_TO_RFC = {
    "organizer": "CHAIR",
    "required_attendee": "REQ-PARTICIPANT",
    "optional_attendee": "OPT-PARTICIPANT",
    "chair": "CHAIR",
    "non_participant": "NON-PARTICIPANT",
}


# Canonical PARTSTAT mapping — our enum → RFC 5546.
_PARTSTAT_TO_RFC = {
    "needs_action": "NEEDS-ACTION",
    "accepted": "ACCEPTED",
    "declined": "DECLINED",
    "tentative": "TENTATIVE",
    "delegated": "DELEGATED",
}


# ─────────────────────────────────────────────────────────────────────
# Public API — VCALENDAR string composers
# ─────────────────────────────────────────────────────────────────────


def compose_request(
    event: CalendarEvent,
    *,
    organizer_email: str,
    organizer_name: str | None = None,
    sequence: int = 0,
    attendees: Iterable[CalendarEventAttendee] | None = None,
    override: CalendarEventInstanceOverride | None = None,
) -> str:
    """Compose an iTIP METHOD=REQUEST VCALENDAR string.

    Used for both initial event invitations (Path 1) and update
    propagation (Path 2). Caller passes ``sequence=0`` for initial
    requests; subsequent updates increment per RFC 5546.

    When ``override`` is supplied, the REQUEST is scoped to the
    modified instance via RECURRENCE-ID matching the original instance
    start_at (NOT the override's modified start). Per §3.26.16.5 Path 2.
    """
    cal = _new_calendar(method="REQUEST")
    cal.add_component(
        _build_vevent(
            event,
            organizer_email=organizer_email,
            organizer_name=organizer_name,
            sequence=sequence,
            attendees=attendees,
            override=override,
            status_override=None,  # REQUEST inherits event.status
        )
    )
    return cal.to_ical().decode("utf-8")


def compose_cancel(
    event: CalendarEvent,
    *,
    organizer_email: str,
    organizer_name: str | None = None,
    sequence: int = 1,
    attendees: Iterable[CalendarEventAttendee] | None = None,
    override: CalendarEventInstanceOverride | None = None,
) -> str:
    """Compose an iTIP METHOD=CANCEL VCALENDAR string.

    Per §3.26.16.5 Path 2: STATUS=CANCELLED + sequence increment.
    Sequence default 1 because cancellation always implies prior
    REQUEST happened (sequence 0 = first send). Caller may override
    if multiple updates preceded cancellation.

    When ``override`` is supplied, CANCEL is scoped to RECURRENCE-ID
    for instance-cancellation; otherwise cancels the entire event.
    """
    cal = _new_calendar(method="CANCEL")
    cal.add_component(
        _build_vevent(
            event,
            organizer_email=organizer_email,
            organizer_name=organizer_name,
            sequence=sequence,
            attendees=attendees,
            override=override,
            status_override="CANCELLED",
        )
    )
    return cal.to_ical().decode("utf-8")


def compose_reply(
    event: CalendarEvent,
    *,
    organizer_email: str,
    responding_attendee: CalendarEventAttendee,
    sequence: int = 0,
) -> str:
    """Compose an iTIP METHOD=REPLY VCALENDAR string.

    Per RFC 5546: a REPLY echoes the event UID + DTSTAMP + SUMMARY +
    ORGANIZER + the responding ATTENDEE with their PARTSTAT. Other
    attendees are NOT included in the REPLY (privacy + RFC 5546
    canonical structure).

    Used by the future per-attendee response flow (Step 5+); Step 3
    ships compose only — outbound REPLY propagation deferred.
    """
    cal = _new_calendar(method="REPLY")

    vevent = IcsEvent()
    vevent.add("uid", _event_uid(event))
    vevent.add("dtstamp", datetime.now(timezone.utc))
    vevent.add("dtstart", event.start_at)
    vevent.add("dtend", event.end_at)
    if event.subject:
        vevent.add("summary", event.subject)
    if sequence:
        vevent.add("sequence", sequence)

    organizer = vCalAddress(f"mailto:{organizer_email}")
    vevent.add("organizer", organizer)

    # Responding attendee only — REPLY canonical structure.
    attendee_addr = vCalAddress(f"mailto:{responding_attendee.email_address}")
    if responding_attendee.display_name:
        attendee_addr.params["cn"] = vText(responding_attendee.display_name)
    attendee_addr.params["partstat"] = vText(
        _PARTSTAT_TO_RFC.get(responding_attendee.response_status, "NEEDS-ACTION")
    )
    attendee_addr.params["role"] = vText(
        _ROLE_TO_RFC.get(responding_attendee.role, "REQ-PARTICIPANT")
    )
    if responding_attendee.comment:
        # RFC 5546 doesn't standardize a field for response comment;
        # icalendar accepts COMMENT as a top-level VEVENT property.
        vevent.add("comment", responding_attendee.comment)
    vevent.add("attendee", attendee_addr)

    cal.add_component(vevent)
    return cal.to_ical().decode("utf-8")


# ─────────────────────────────────────────────────────────────────────
# Internal builders
# ─────────────────────────────────────────────────────────────────────


def _new_calendar(*, method: str) -> Calendar:
    """Construct a VCALENDAR object with canonical PRODID + VERSION + METHOD."""
    cal = Calendar()
    cal.add("prodid", _PRODID)
    cal.add("version", _VERSION)
    cal.add("method", method)
    return cal


def _event_uid(event: CalendarEvent) -> str:
    """Resolve the canonical RFC 5545 UID for an event.

    For provider-synced events, ``provider_event_id`` is the canonical
    UID (Google + MS Graph events.list returns the original iCalendar
    UID via the API; ingestion stores it on provider_event_id). For
    Bridgeable-native (local) events with no provider_event_id,
    synthesize from event.id + a Bridgeable domain suffix.
    """
    if event.provider_event_id:
        return event.provider_event_id
    return f"{event.id}@bridgeable.calendar"


def _build_vevent(
    event: CalendarEvent,
    *,
    organizer_email: str,
    organizer_name: str | None,
    sequence: int,
    attendees: Iterable[CalendarEventAttendee] | None,
    override: CalendarEventInstanceOverride | None,
    status_override: str | None,
) -> IcsEvent:
    """Build a single VEVENT block with canonical RFC 5545 properties.

    When ``override`` is supplied, RECURRENCE-ID is added matching the
    override's recurrence_instance_start_at (per RFC 5545 RECURRENCE-ID
    semantics — references the ORIGINAL instance start, not any
    modified time). The DTSTART/DTEND of the VEVENT reflects the
    modified instance content if override.override_event is set,
    otherwise the master event content.
    """
    vevent = IcsEvent()

    # UID — canonical RFC 5545 RECURRENCE-ID + UID combo identifies the
    # specific instance for override; UID alone identifies the master
    # series.
    vevent.add("uid", _event_uid(event))
    vevent.add("dtstamp", datetime.now(timezone.utc))
    vevent.add("sequence", sequence)

    # Resolve content source: when modified-instance override carries
    # override_event_id, the override's CalendarEvent provides the
    # modified content; otherwise master event content.
    if override and override.override_event:
        content_event = override.override_event
    else:
        content_event = event

    vevent.add("dtstart", content_event.start_at)
    vevent.add("dtend", content_event.end_at)
    if content_event.subject:
        vevent.add("summary", content_event.subject)
    if content_event.description_text:
        vevent.add("description", content_event.description_text)
    if content_event.location:
        vevent.add("location", content_event.location)

    # STATUS — REQUEST inherits event.status; CANCEL passes status_override.
    status = status_override or _normalize_status_to_rfc(content_event.status)
    vevent.add("status", status)

    # TRANSP — opaque (busy) or transparent (free).
    transp = (
        "TRANSPARENT"
        if content_event.transparency == "transparent"
        else "OPAQUE"
    )
    vevent.add("transp", transp)

    # RRULE — only on master event, not on override-scoped REQUESTs.
    # When override is supplied, RECURRENCE-ID scopes the message to a
    # single instance; RRULE on a RECURRENCE-ID-scoped VEVENT would be
    # malformed per RFC 5545.
    if event.recurrence_rule and not override:
        vrecur = _parse_rrule_for_compose(event.recurrence_rule)
        if vrecur is not None:
            vevent.add("rrule", vrecur)

    # RECURRENCE-ID — scopes the message to a single instance per RFC
    # 5545. Set when override is supplied (for both REQUEST and CANCEL
    # of modified or cancelled instance).
    if override:
        vevent.add(
            "recurrence-id", override.recurrence_instance_start_at
        )

    # ORGANIZER (RFC 5545 mandatory on iTIP messages).
    organizer = vCalAddress(f"mailto:{organizer_email}")
    if organizer_name:
        organizer.params["cn"] = vText(organizer_name)
    vevent.add("organizer", organizer)

    # ATTENDEEs — caller-provided list (may be empty for events with no
    # attendees).
    for att in attendees or []:
        attendee_addr = vCalAddress(f"mailto:{att.email_address}")
        if att.display_name:
            attendee_addr.params["cn"] = vText(att.display_name)
        attendee_addr.params["role"] = vText(
            _ROLE_TO_RFC.get(att.role, "REQ-PARTICIPANT")
        )
        attendee_addr.params["partstat"] = vText(
            _PARTSTAT_TO_RFC.get(att.response_status, "NEEDS-ACTION")
        )
        attendee_addr.params["rsvp"] = vText("TRUE")
        vevent.add("attendee", attendee_addr)

    return vevent


def _normalize_status_to_rfc(status: str) -> str:
    """Map canonical event status → RFC 5545 STATUS uppercase.

    Our enum: tentative / confirmed / cancelled.
    RFC 5545 STATUS values for VEVENT: TENTATIVE / CONFIRMED / CANCELLED.
    """
    return status.upper() if status else "CONFIRMED"


def _parse_rrule_for_compose(rrule_str: str) -> vRecur | None:
    """Parse a stored RRULE string into a vRecur for icalendar emission.

    Stored rules can be:
      - Bare ``FREQ=WEEKLY;BYDAY=MO``
      - ``RRULE:FREQ=WEEKLY;...``
      - Multi-line block including DTSTART + EXDATE + RDATE

    For compose emission, we extract the FIRST RRULE: line's parameters
    only — DTSTART is set separately on the VEVENT, and EXDATE/RDATE
    don't survive across iTIP REQUEST messages by canonical convention
    (recurring-instance modifications use RECURRENCE-ID-scoped
    REQUESTs per §3.26.16.5 Path 2 + RFC 5546).
    """
    s = rrule_str.strip()
    if not s:
        return None

    # Extract the RRULE: line (multi-line block) OR strip leading RRULE:
    # prefix (single line).
    rrule_payload: str | None = None
    for line in s.split("\n"):
        line = line.strip()
        if line.startswith("RRULE:"):
            rrule_payload = line[len("RRULE:"):]
            break
    if rrule_payload is None:
        # Single-line bare form — accept verbatim if it starts with FREQ=.
        if s.startswith("FREQ=") or "FREQ=" in s.split(";", 1)[0]:
            rrule_payload = s
        else:
            return None

    # Parse FREQ=...;BYDAY=...;... into a dict + construct vRecur.
    parts = {}
    for kv in rrule_payload.split(";"):
        if "=" not in kv:
            continue
        key, value = kv.split("=", 1)
        key = key.strip().upper()
        value = value.strip()
        if not key or not value:
            continue
        # Some keys take comma-separated lists.
        if "," in value:
            parts[key.lower()] = value.split(",")
        else:
            # UNTIL needs datetime; COUNT/INTERVAL/etc are integers.
            if key == "UNTIL":
                # icalendar accepts string; preserves wire format
                parts[key.lower()] = value
            elif key in ("COUNT", "INTERVAL"):
                try:
                    parts[key.lower()] = int(value)
                except ValueError:
                    parts[key.lower()] = value
            else:
                parts[key.lower()] = value

    try:
        return vRecur(parts)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to construct vRecur from %r: %s — emitting VEVENT "
            "without RRULE (per stale-but-correct discipline)",
            rrule_payload,
            exc,
        )
        return None
