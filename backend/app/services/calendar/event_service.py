"""CalendarEvent service layer — Phase W-4b Layer 1 Calendar Step 1.

Basic CRUD for ``CalendarEvent`` with linkage support. Mirrors the
shape pattern established in ``account_service``.

**Step 1 boundary (per Email r63 precedent):** this service ships
basic CRUD against the canonical ``calendar_events`` table. It does
NOT ship:

  - RRULE engine activation (Step 2) — recurring events store the
    RRULE string verbatim; expansion + materialization ship in Step 2
  - Outbound iTIP scheduling (Step 3) — events created here do not
    propagate invitations to external attendees; attendees are stored
    on canonical rows but no invitation transport runs
  - State-changes-generate-events drafted-not-auto-sent discipline
    (Step 3 — §3.26.16.18)
  - Cross-tenant joint event acceptance (Step 4 — §3.26.16.20)

Events created against the local provider work fully end-to-end at
Step 1 (no transport needed). Events created against Google Calendar
or MS Graph providers store fine but won't sync to / from the provider
until Step 2 ships sync activation.

**Tenant isolation discipline:** every query filters by ``tenant_id``;
cross-tenant access yields ``CalendarEventNotFound`` (existence-hiding
404 to prevent cross-tenant id enumeration), parallel to the
``CalendarAccountNotFound`` pattern in ``account_service``.

**Audit log discipline (§3.26.16.8):** every CRUD operation writes a
row to ``calendar_audit_log`` via the shared ``account_service._audit``
helper.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    EVENT_STATUSES,
    LINKAGE_SOURCES,
    TRANSPARENCY_VALUES,
    CalendarAccount,
    CalendarEvent,
    CalendarEventLinkage,
)
from app.services.calendar.account_service import (
    CalendarAccountError,
    CalendarAccountNotFound,
    _audit,
    get_account,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors — reuse account_service error class hierarchy
# ─────────────────────────────────────────────────────────────────────


class CalendarEventError(CalendarAccountError):
    """Base error for calendar event operations.

    Inherits from ``CalendarAccountError`` so the same ``http_status``-
    based translation in route handlers works uniformly across both
    accounts + events.
    """


class CalendarEventNotFound(CalendarEventError):
    http_status = 404


class CalendarEventValidation(CalendarEventError):
    http_status = 400


class CalendarEventConflict(CalendarEventError):
    http_status = 409


class CalendarEventPermissionDenied(CalendarEventError):
    http_status = 403


# ─────────────────────────────────────────────────────────────────────
# CRUD: CalendarEvent
# ─────────────────────────────────────────────────────────────────────


def create_event(
    db: Session,
    *,
    tenant_id: str,
    account_id: str,
    actor_user_id: str | None,
    subject: str | None,
    start_at: datetime,
    end_at: datetime,
    description_text: str | None = None,
    description_html: str | None = None,
    location: str | None = None,
    is_all_day: bool = False,
    event_timezone: str | None = None,
    recurrence_rule: str | None = None,
    status: str = "confirmed",
    transparency: str = "opaque",
    is_cross_tenant: bool = False,
    provider_event_id: str | None = None,
) -> CalendarEvent:
    """Create a new CalendarEvent.

    Validation:
      - account exists in this tenant
      - end_at >= start_at (also enforced by DB CHECK constraint)
      - status one of EVENT_STATUSES
      - transparency one of TRANSPARENCY_VALUES

    Side effects:
      - Audit log entry: action='event_created'.

    Per §3.26.16.4 Step 1 boundary: ``recurrence_rule`` is stored
    verbatim. The canonical recurrence engine that materializes
    instances on demand ships in Step 2. Step 1 does not validate the
    RRULE string (a malformed RRULE will be caught at Step 2 expansion
    time).
    """
    if status not in EVENT_STATUSES:
        raise CalendarEventValidation(
            f"status must be one of {EVENT_STATUSES}, got {status!r}"
        )
    if transparency not in TRANSPARENCY_VALUES:
        raise CalendarEventValidation(
            f"transparency must be one of {TRANSPARENCY_VALUES}, "
            f"got {transparency!r}"
        )
    if end_at < start_at:
        raise CalendarEventValidation(
            "end_at must be greater than or equal to start_at"
        )

    # Tenant-scoped account lookup (raises CalendarAccountNotFound
    # for cross-tenant or missing accounts).
    account = get_account(db, account_id=account_id, tenant_id=tenant_id)

    if not account.is_active:
        raise CalendarEventValidation(
            f"CalendarAccount {account_id!r} is not active; cannot create "
            f"events against an inactive account."
        )

    event = CalendarEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        account_id=account.id,
        provider_event_id=provider_event_id,
        subject=subject,
        description_text=description_text,
        description_html=description_html,
        location=location,
        start_at=start_at,
        end_at=end_at,
        is_all_day=is_all_day,
        event_timezone=event_timezone or account.default_event_timezone,
        recurrence_rule=recurrence_rule,
        status=status,
        transparency=transparency,
        is_cross_tenant=is_cross_tenant,
        created_by_user_id=actor_user_id,
    )
    db.add(event)
    db.flush()

    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="event_created",
        entity_type="calendar_event",
        entity_id=event.id,
        changes={
            "account_id": account.id,
            "subject": subject,
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "status": status,
            "is_recurring": recurrence_rule is not None,
            "is_cross_tenant": is_cross_tenant,
        },
    )
    db.flush()

    # Step 5 — V-1c CRM activity feed integration (Surface 7) per
    # §3.26.16.10 row 7. Best-effort fan-out; failure never blocks
    # event creation.
    try:
        from app.services.calendar.activity_feed_integration import (
            log_calendar_event_activity,
        )

        log_calendar_event_activity(
            db,
            event=event,
            kind="scheduled",
            actor_user_id=actor_user_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "log_calendar_event_activity failed for event=%s (kind=scheduled)",
            event.id,
        )

    return event


def get_event(
    db: Session,
    *,
    event_id: str,
    tenant_id: str,
) -> CalendarEvent:
    """Fetch a single CalendarEvent, tenant-scoped.

    Raises ``CalendarEventNotFound`` (HTTP 404) if the event doesn't
    exist OR exists in a different tenant — existence-hiding to prevent
    cross-tenant id enumeration.
    """
    event = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.id == event_id,
            CalendarEvent.tenant_id == tenant_id,
        )
        .first()
    )
    if not event:
        raise CalendarEventNotFound(f"CalendarEvent {event_id!r} not found.")
    return event


def list_events_for_account(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    include_inactive: bool = False,
    limit: int = 500,
) -> list[CalendarEvent]:
    """List events for a calendar account in an optional time range.

    Defaults: returns up to ``limit`` events (default 500), most-recent-
    first. When ``range_start`` + ``range_end`` are provided, filters
    by half-open [range_start, range_end) overlap with each event's
    [start_at, end_at) interval.

    Per Step 1 boundary: this does NOT expand recurring events.
    Recurring rows return their master event row only; instance
    materialization ships in Step 2 alongside the canonical recurrence
    engine.
    """
    # Tenant-scope check via account.
    account = get_account(db, account_id=account_id, tenant_id=tenant_id)

    query = db.query(CalendarEvent).filter(
        CalendarEvent.account_id == account.id,
        CalendarEvent.tenant_id == tenant_id,
    )
    if not include_inactive:
        query = query.filter(CalendarEvent.is_active.is_(True))
    if range_start is not None:
        query = query.filter(CalendarEvent.end_at > range_start)
    if range_end is not None:
        query = query.filter(CalendarEvent.start_at < range_end)
    return (
        query.order_by(CalendarEvent.start_at.desc())
        .limit(max(1, min(limit, 5000)))
        .all()
    )


def update_event(
    db: Session,
    *,
    event_id: str,
    tenant_id: str,
    actor_user_id: str | None,
    subject: str | None = None,
    description_text: str | None = None,
    description_html: str | None = None,
    location: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    is_all_day: bool | None = None,
    event_timezone: str | None = None,
    recurrence_rule: str | None = None,
    status: str | None = None,
    transparency: str | None = None,
) -> CalendarEvent:
    """Patch a CalendarEvent.

    Only the supplied fields are updated. account_id + tenant_id +
    is_cross_tenant + provider_event_id are immutable post-create.
    """
    event = get_event(db, event_id=event_id, tenant_id=tenant_id)

    changes: dict[str, Any] = {}

    if subject is not None and subject != event.subject:
        changes["subject"] = {"old": event.subject, "new": subject}
        event.subject = subject

    if description_text is not None:
        if description_text != event.description_text:
            changes["description_text_changed"] = True
            event.description_text = description_text

    if description_html is not None:
        if description_html != event.description_html:
            changes["description_html_changed"] = True
            event.description_html = description_html

    if location is not None and location != event.location:
        changes["location"] = {"old": event.location, "new": location}
        event.location = location

    new_start = start_at if start_at is not None else event.start_at
    new_end = end_at if end_at is not None else event.end_at
    if new_end < new_start:
        raise CalendarEventValidation(
            "end_at must be greater than or equal to start_at"
        )
    if start_at is not None and start_at != event.start_at:
        changes["start_at"] = {
            "old": event.start_at.isoformat(),
            "new": start_at.isoformat(),
        }
        event.start_at = start_at
    if end_at is not None and end_at != event.end_at:
        changes["end_at"] = {
            "old": event.end_at.isoformat(),
            "new": end_at.isoformat(),
        }
        event.end_at = end_at

    if is_all_day is not None and is_all_day != event.is_all_day:
        changes["is_all_day"] = {"old": event.is_all_day, "new": is_all_day}
        event.is_all_day = is_all_day

    if event_timezone is not None and event_timezone != event.event_timezone:
        changes["event_timezone"] = {
            "old": event.event_timezone,
            "new": event_timezone,
        }
        event.event_timezone = event_timezone

    if recurrence_rule is not None and recurrence_rule != event.recurrence_rule:
        changes["recurrence_rule_changed"] = True
        event.recurrence_rule = recurrence_rule

    if status is not None:
        if status not in EVENT_STATUSES:
            raise CalendarEventValidation(
                f"status must be one of {EVENT_STATUSES}, got {status!r}"
            )
        if status != event.status:
            changes["status"] = {"old": event.status, "new": status}
            event.status = status

    if transparency is not None:
        if transparency not in TRANSPARENCY_VALUES:
            raise CalendarEventValidation(
                f"transparency must be one of {TRANSPARENCY_VALUES}, "
                f"got {transparency!r}"
            )
        if transparency != event.transparency:
            changes["transparency"] = {
                "old": event.transparency,
                "new": transparency,
            }
            event.transparency = transparency

    if not changes:
        return event

    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="event_updated",
        entity_type="calendar_event",
        entity_id=event.id,
        changes=changes,
    )
    db.flush()

    # Step 5 — V-1c CRM activity feed integration. Surface "modified"
    # only for substantive changes (start_at + end_at + status +
    # location). Pure metadata edits (subject + description tweaks) do
    # NOT surface as activity — too chatty for the customer activity feed.
    _SUBSTANTIVE_FIELDS = {"start_at", "end_at", "status", "location"}
    if any(field in changes for field in _SUBSTANTIVE_FIELDS):
        try:
            from app.services.calendar.activity_feed_integration import (
                log_calendar_event_activity,
            )

            log_calendar_event_activity(
                db,
                event=event,
                kind="modified",
                actor_user_id=actor_user_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "log_calendar_event_activity failed for event=%s (kind=modified)",
                event.id,
            )

    return event


def delete_event(
    db: Session,
    *,
    event_id: str,
    tenant_id: str,
    actor_user_id: str | None,
) -> None:
    """Soft-delete a CalendarEvent by setting is_active=False.

    Per Email r63 precedent: row stays for audit compliance; subsequent
    reads filter by is_active=True by default.
    """
    event = get_event(db, event_id=event_id, tenant_id=tenant_id)
    if not event.is_active:
        return

    event.is_active = False
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="event_deleted",
        entity_type="calendar_event",
        entity_id=event.id,
        changes={"subject": event.subject},
    )
    db.flush()

    # Step 5 — V-1c CRM activity feed integration. Soft-delete is the
    # canonical "cancelled" surface for the activity feed.
    try:
        from app.services.calendar.activity_feed_integration import (
            log_calendar_event_activity,
        )

        log_calendar_event_activity(
            db,
            event=event,
            kind="cancelled",
            actor_user_id=actor_user_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "log_calendar_event_activity failed for event=%s (kind=cancelled)",
            event.id,
        )


# ─────────────────────────────────────────────────────────────────────
# Linkage management
# ─────────────────────────────────────────────────────────────────────


def add_linkage(
    db: Session,
    *,
    event_id: str,
    tenant_id: str,
    linked_entity_type: str,
    linked_entity_id: str,
    linkage_source: str,
    actor_user_id: str | None,
    confidence: float | None = None,
) -> CalendarEventLinkage:
    """Add a polymorphic linkage to a Bridgeable entity.

    Per §3.26.16.7 — same junction shape as email_thread_linkages.
    Idempotent: if an active linkage already exists for the same
    (event_id, linked_entity_type, linked_entity_id) tuple, returns it
    unchanged.
    """
    if linkage_source not in LINKAGE_SOURCES:
        raise CalendarEventValidation(
            f"linkage_source must be one of {LINKAGE_SOURCES}, "
            f"got {linkage_source!r}"
        )

    # Tenant-scope check via event.
    event = get_event(db, event_id=event_id, tenant_id=tenant_id)

    existing = (
        db.query(CalendarEventLinkage)
        .filter(
            CalendarEventLinkage.event_id == event.id,
            CalendarEventLinkage.linked_entity_type == linked_entity_type,
            CalendarEventLinkage.linked_entity_id == linked_entity_id,
            CalendarEventLinkage.dismissed_at.is_(None),
        )
        .first()
    )
    if existing:
        return existing

    linkage = CalendarEventLinkage(
        id=str(uuid.uuid4()),
        event_id=event.id,
        tenant_id=tenant_id,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        linkage_source=linkage_source,
        confidence=confidence,
        linked_by_user_id=actor_user_id,
    )
    db.add(linkage)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="linkage_added",
        entity_type="calendar_event_linkage",
        entity_id=linkage.id,
        changes={
            "event_id": event.id,
            "linked_entity_type": linked_entity_type,
            "linked_entity_id": linked_entity_id,
            "linkage_source": linkage_source,
        },
    )
    db.flush()
    return linkage


def dismiss_linkage(
    db: Session,
    *,
    linkage_id: str,
    tenant_id: str,
    actor_user_id: str | None,
) -> bool:
    """Soft-dismiss a calendar event linkage.

    Returns True if the linkage was dismissed, False if it was already
    dismissed (idempotent).
    """
    from datetime import datetime, timezone

    linkage = (
        db.query(CalendarEventLinkage)
        .filter(
            CalendarEventLinkage.id == linkage_id,
            CalendarEventLinkage.tenant_id == tenant_id,
        )
        .first()
    )
    if not linkage:
        raise CalendarEventNotFound(
            f"CalendarEventLinkage {linkage_id!r} not found."
        )
    if linkage.dismissed_at is not None:
        return False

    linkage.dismissed_at = datetime.now(timezone.utc)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="linkage_dismissed",
        entity_type="calendar_event_linkage",
        entity_id=linkage.id,
        changes={
            "event_id": linkage.event_id,
            "linked_entity_type": linkage.linked_entity_type,
        },
    )
    db.flush()
    return True


def list_linkages_for_event(
    db: Session,
    *,
    event_id: str,
    tenant_id: str,
    include_dismissed: bool = False,
) -> list[CalendarEventLinkage]:
    """Return all linkages for an event, ordered by linked_at ascending.

    Tenant-scope check via event lookup. Defaults to active linkages
    (``dismissed_at IS NULL``); ``include_dismissed=True`` returns the
    full history including soft-dismissed rows.

    Phase W-4b Layer 1 Calendar Step 5 — powers the linked-entities
    section of the native event detail page (§14.10.3).
    """
    # Tenant-scope check via event.
    get_event(db, event_id=event_id, tenant_id=tenant_id)

    query = db.query(CalendarEventLinkage).filter(
        CalendarEventLinkage.event_id == event_id,
        CalendarEventLinkage.tenant_id == tenant_id,
    )
    if not include_dismissed:
        query = query.filter(CalendarEventLinkage.dismissed_at.is_(None))
    return query.order_by(CalendarEventLinkage.linked_at.asc()).all()
