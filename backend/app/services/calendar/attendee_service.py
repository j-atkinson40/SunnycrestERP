"""CalendarEventAttendee service layer — Phase W-4b Layer 1 Calendar Step 1.

Basic CRUD for ``CalendarEventAttendee`` + response status updates.
Mirrors the shape pattern established in ``account_service`` +
``event_service``.

**Step 1 boundary:** this service ships basic CRUD against the
canonical ``calendar_event_attendees`` table. It does NOT ship:

  - iTIP invitation propagation to external attendees (Step 3)
  - Magic-link contextual surface for non-Bridgeable participants
    (Step 4 — depends on platform_action_tokens substrate consolidation)
  - Cross-tenant participant routing per §3.26.11.7 (Step 4)
  - Attendee resolution to internal Users / CompanyEntities via
    Intelligence (Post-Step-5)

What Step 1 does ship:
  - Add attendee to event with role + initial response_status
  - Update response_status (accept / decline / tentative / delegate)
  - Remove attendee from event
  - List attendees for event

**Tenant isolation discipline:** every query reaches attendees via
the parent event, which is tenant-scoped via ``event_service.get_event``.
Direct attendee lookup by id without event context is not supported
in Step 1 — Step 4 magic-link substrate adds that pattern alongside
the token-bound external-participant flow.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    ATTENDEE_ROLES,
    RESPONSE_STATUSES,
    CalendarEvent,
    CalendarEventAttendee,
)
from app.services.calendar.account_service import _audit
from app.services.calendar.event_service import (
    CalendarEventError,
    CalendarEventNotFound,
    CalendarEventValidation,
    get_event,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# CRUD: CalendarEventAttendee
# ─────────────────────────────────────────────────────────────────────


def add_attendee(
    db: Session,
    *,
    event_id: str,
    tenant_id: str,
    actor_user_id: str | None,
    email_address: str,
    display_name: str | None = None,
    role: str = "required_attendee",
    response_status: str = "needs_action",
    resolved_user_id: str | None = None,
    resolved_company_entity_id: str | None = None,
    external_tenant_id: str | None = None,
    is_internal: bool = False,
) -> CalendarEventAttendee:
    """Add an attendee to a calendar event.

    Validation:
      - role must be one of ATTENDEE_ROLES
      - response_status must be one of RESPONSE_STATUSES
      - email_address must contain '@'
      - duplicate (event_id, email_address) raises CalendarEventConflict
        (also guarded by DB unique index)

    Side effects:
      - Audit log entry: action='attendee_added'.
    """
    if role not in ATTENDEE_ROLES:
        raise CalendarEventValidation(
            f"role must be one of {ATTENDEE_ROLES}, got {role!r}"
        )
    if response_status not in RESPONSE_STATUSES:
        raise CalendarEventValidation(
            f"response_status must be one of {RESPONSE_STATUSES}, "
            f"got {response_status!r}"
        )
    if not email_address or "@" not in email_address:
        raise CalendarEventValidation(
            f"email_address must be a valid email, got {email_address!r}"
        )

    # Tenant-scope check via event.
    event = get_event(db, event_id=event_id, tenant_id=tenant_id)

    normalized_email = email_address.strip().lower()

    # Duplicate check (also enforced by uq_calendar_event_attendees_event_email).
    existing = (
        db.query(CalendarEventAttendee)
        .filter(
            CalendarEventAttendee.event_id == event.id,
            CalendarEventAttendee.email_address == normalized_email,
        )
        .first()
    )
    if existing:
        # Idempotent on identical inputs; raise on conflicting role/etc.
        if (
            existing.role == role
            and existing.response_status == response_status
        ):
            return existing
        from app.services.calendar.event_service import CalendarEventConflict

        raise CalendarEventConflict(
            f"Attendee {normalized_email!r} already on event {event.id!r} "
            f"with different role/response_status."
        )

    attendee = CalendarEventAttendee(
        id=str(uuid.uuid4()),
        event_id=event.id,
        tenant_id=tenant_id,
        email_address=normalized_email,
        display_name=display_name,
        resolved_user_id=resolved_user_id,
        resolved_company_entity_id=resolved_company_entity_id,
        external_tenant_id=external_tenant_id,
        role=role,
        response_status=response_status,
        responded_at=(
            datetime.now(timezone.utc)
            if response_status != "needs_action"
            else None
        ),
        is_internal=is_internal,
    )
    db.add(attendee)
    db.flush()

    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="attendee_added",
        entity_type="calendar_event_attendee",
        entity_id=attendee.id,
        changes={
            "event_id": event.id,
            "email_address": normalized_email,
            "role": role,
            "response_status": response_status,
        },
    )
    db.flush()
    return attendee


def list_attendees_for_event(
    db: Session,
    *,
    event_id: str,
    tenant_id: str,
) -> list[CalendarEventAttendee]:
    """List all attendees on a calendar event."""
    # Tenant-scope check via event.
    event = get_event(db, event_id=event_id, tenant_id=tenant_id)

    return (
        db.query(CalendarEventAttendee)
        .filter(CalendarEventAttendee.event_id == event.id)
        .order_by(CalendarEventAttendee.first_seen_at.asc())
        .all()
    )


def update_response_status(
    db: Session,
    *,
    attendee_id: str,
    tenant_id: str,
    actor_user_id: str | None,
    response_status: str,
    comment: str | None = None,
) -> CalendarEventAttendee:
    """Update an attendee's response_status.

    Used when an internal user (or, in Step 4, a magic-link external
    participant) responds to an event invitation. Stamps
    ``responded_at`` to current time when transitioning out of
    ``needs_action``.
    """
    if response_status not in RESPONSE_STATUSES:
        raise CalendarEventValidation(
            f"response_status must be one of {RESPONSE_STATUSES}, "
            f"got {response_status!r}"
        )

    attendee = (
        db.query(CalendarEventAttendee)
        .filter(
            CalendarEventAttendee.id == attendee_id,
            CalendarEventAttendee.tenant_id == tenant_id,
        )
        .first()
    )
    if not attendee:
        raise CalendarEventNotFound(
            f"CalendarEventAttendee {attendee_id!r} not found."
        )

    if attendee.response_status == response_status and comment is None:
        # Idempotent — no audit row.
        return attendee

    prev_status = attendee.response_status
    attendee.response_status = response_status
    if response_status != "needs_action":
        attendee.responded_at = datetime.now(timezone.utc)
    if comment is not None:
        attendee.comment = comment

    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="attendee_response_updated",
        entity_type="calendar_event_attendee",
        entity_id=attendee.id,
        changes={
            "event_id": attendee.event_id,
            "email_address": attendee.email_address,
            "response_status": {"old": prev_status, "new": response_status},
        },
    )
    db.flush()
    return attendee


def remove_attendee(
    db: Session,
    *,
    attendee_id: str,
    tenant_id: str,
    actor_user_id: str | None,
) -> None:
    """Remove an attendee from a calendar event.

    Hard-delete (not soft) — attendee removal from an event is not an
    audit-sensitive privacy event in the same way that, e.g., account
    deletion is. The audit log row preserves the removal action for
    audit compliance.

    Per Step 1 boundary: external attendee removal does NOT propagate
    iTIP CANCEL to the attendee — that ships in Step 3 alongside the
    outbound iTIP scheduling infrastructure.
    """
    attendee = (
        db.query(CalendarEventAttendee)
        .filter(
            CalendarEventAttendee.id == attendee_id,
            CalendarEventAttendee.tenant_id == tenant_id,
        )
        .first()
    )
    if not attendee:
        raise CalendarEventNotFound(
            f"CalendarEventAttendee {attendee_id!r} not found."
        )

    event_id = attendee.event_id
    email_address = attendee.email_address

    db.delete(attendee)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="attendee_removed",
        entity_type="calendar_event_attendee",
        entity_id=attendee_id,
        changes={
            "event_id": event_id,
            "email_address": email_address,
        },
    )
    db.flush()
