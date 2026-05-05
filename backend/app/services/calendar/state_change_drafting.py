"""State-change → calendar event drafting — Phase W-4b Layer 1 Calendar Step 3.

Canonical implementation of §3.26.16.18: state changes in operational
entities automatically generate calendar events. **Drafted-not-auto-sent
discipline** per §3.26.14.14.5: state change → calendar event is
drafted automatically (event row with ``status="tentative"``); operator
reviews + confirms before invitation propagation.

**Canonical 7 mappings** (per §3.26.16.18 verbatim):
  1. ``SalesOrder.scheduled_date`` set → event with linked_entity_type="sales_order"
  2. ``FHCase.service_date`` set → event with linked_entity_type="fh_case"
  3. ``Quote.delivery_date`` set on quote acceptance → event with linked_entity_type="quote"
  4. ``WorkOrder.scheduled_date`` set → event with linked_entity_type="vault_item"
  5. ``Equipment.next_maintenance_date`` set → event with linked_entity → equipment
  6. ``ComplianceRequirement.expires_at`` minus 30 days → event + admin attendees
  7. ``Disinterment.scheduled_date`` set → event with cross-tenant invitation FH/cemetery + driver routing

**Auto-confirmation exceptions** (verbatim §3.26.16.18):
  - Internal-only events (no cross-tenant attendees, no external attendees) auto-confirm
  - Recurring-meeting modifications inherit parent's confirmation state
  - System-generated reminder events auto-confirm

**Step 3 boundary** (per Q4 architectural decision):
  - Ships canonical helper API + 7-mapping registry + auto-confirmation rules
  - Hook wiring into 7 entity update sites is DEFERRED to per-entity follow-on arcs
  - Each entity-specific arc imports + invokes the canonical helper at the
    state change site (e.g. SalesOrder.scheduled_date setter calls
    ``draft_event_from_state_change(db, source_entity_type="sales_order", ...)``)

**Audit trail** per §3.26.16.18: events from state changes carry
``generation_source="state_change"`` metadata + ``generation_entity_type``
+ ``generation_entity_id`` + audit row with linkage to operational entity.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventLinkage,
)
from app.services.calendar.account_service import _audit

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Canonical 7 state-change → event mapping registry
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StateChangeMapping:
    """Canonical mapping per §3.26.16.18 row.

    Attributes:
        source_entity_type: Operational entity name (e.g. "sales_order").
        linked_entity_type: Calendar event linkage entity_type (per §3.26.16.7
            polymorphic linkage canonical catalog).
        default_subject_template: Pythonic format string for the auto-
            generated subject. ``{entity}`` placeholder gets replaced
            with caller-supplied entity context.
        cross_tenant: True when canonical mapping calls for cross-tenant
            attendee invitation per §3.26.16.18 prose. Drives auto-
            confirmation rule (cross-tenant always requires manual
            review per drafted-not-auto-sent discipline).
        days_before_event: For "minus 30 days" pattern (compliance
            renewal). When set, event start_at = source_date - timedelta(days=N).
    """

    source_entity_type: str
    linked_entity_type: str
    default_subject_template: str
    cross_tenant: bool = False
    days_before_event: int = 0


# Canonical 7 mappings — verbatim per §3.26.16.18.
CANONICAL_MAPPINGS: dict[str, StateChangeMapping] = {
    "sales_order": StateChangeMapping(
        source_entity_type="sales_order",
        linked_entity_type="sales_order",
        default_subject_template="Delivery: {entity}",
        cross_tenant=False,
    ),
    "fh_case": StateChangeMapping(
        source_entity_type="fh_case",
        linked_entity_type="fh_case",
        default_subject_template="Service: {entity}",
        # Cross-tenant invitation to manufacturer when vault scheduled
        # per §3.26.16.18 row 2.
        cross_tenant=True,
    ),
    "quote": StateChangeMapping(
        source_entity_type="quote",
        linked_entity_type="quote",
        default_subject_template="Quote delivery: {entity}",
        cross_tenant=False,
    ),
    "work_order": StateChangeMapping(
        source_entity_type="work_order",
        linked_entity_type="vault_item",
        default_subject_template="Production: {entity}",
        cross_tenant=False,
    ),
    "equipment": StateChangeMapping(
        source_entity_type="equipment",
        linked_entity_type="vault_item",
        default_subject_template="Maintenance: {entity}",
        cross_tenant=False,
    ),
    "compliance_requirement": StateChangeMapping(
        source_entity_type="compliance_requirement",
        linked_entity_type="vault_item",
        default_subject_template="Compliance renewal: {entity}",
        cross_tenant=False,
        days_before_event=30,  # 30-day reminder window per §3.26.16.18
    ),
    "disinterment": StateChangeMapping(
        source_entity_type="disinterment",
        linked_entity_type="vault_item",
        default_subject_template="Disinterment: {entity}",
        # Cross-tenant invitation to FH + cemetery + driver routing
        # per §3.26.16.18 row 7.
        cross_tenant=True,
    ),
}


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


@dataclass
class DraftEventRequest:
    """Caller-supplied context for state-change drafting.

    Attributes:
        source_entity_type: Operational entity name; must be a key in
            ``CANONICAL_MAPPINGS``.
        source_entity_id: Operational entity id (becomes
            generation_entity_id + linked_entity_id on linkage row).
        source_entity_label: Human-readable label (e.g. customer name +
            order number) interpolated into subject_template's ``{entity}``.
        date_at: Date the operational entity scheduled for. Compliance
            mapping subtracts ``days_before_event`` from this; others
            use this directly as event start_at.
        duration_minutes: Default event duration. Caller knows entity
            domain (delivery = 60min default, service = 120min, etc).
        attendee_emails: Operator/team email addresses to invite. Empty
            list = internal-only event (auto-confirm eligible per
            §3.26.16.18 auto-confirmation rules).
        external_attendee_emails: External (non-tenant) attendee emails.
            Non-empty disables auto-confirmation per drafted-not-auto-sent
            discipline.
        tenant_id: Caller's tenant — every CalendarEvent row tenant-scoped.
        actor_user_id: Originator of the state change (audit linkage).
    """

    source_entity_type: str
    source_entity_id: str
    source_entity_label: str
    date_at: datetime
    duration_minutes: int = 60
    attendee_emails: list[str] | None = None
    external_attendee_emails: list[str] | None = None
    tenant_id: str | None = None
    actor_user_id: str | None = None
    location: str | None = None
    description: str | None = None


def get_mapping(source_entity_type: str) -> StateChangeMapping | None:
    """Look up the canonical mapping for an operational entity type."""
    return CANONICAL_MAPPINGS.get(source_entity_type)


def should_auto_confirm(
    *,
    mapping: StateChangeMapping,
    has_external_attendees: bool,
    has_cross_tenant_attendees: bool,
) -> bool:
    """Apply §3.26.16.18 auto-confirmation rules.

    Auto-confirms when ALL of the following hold:
      - Mapping is NOT canonically cross-tenant (e.g. sales_order vs
        fh_case + disinterment which are canonically cross-tenant)
      - No external attendees passed by caller
      - No cross-tenant attendees passed by caller

    Returns False otherwise — drafted-not-auto-sent discipline applies
    + operator must review + confirm before iTIP propagation.
    """
    if mapping.cross_tenant:
        return False
    if has_external_attendees:
        return False
    if has_cross_tenant_attendees:
        return False
    return True


def draft_event_from_state_change(
    db: Session,
    *,
    request: DraftEventRequest,
    account: CalendarAccount,
) -> CalendarEvent:
    """Draft a calendar event from an operational state change.

    Per §3.26.16.18 + drafted-not-auto-sent discipline:
      - Creates CalendarEvent with status="tentative" (default)
      - generation_source="state_change" + generation_entity_* metadata
      - Auto-flips to status="confirmed" when auto-confirmation rules
        per §3.26.16.18 apply
      - Adds CalendarEventLinkage row for polymorphic linkage to source entity
      - Adds CalendarEventAttendee rows for each attendee email
      - Audit log row with generation_source provenance

    Returns the persisted CalendarEvent row.

    Raises:
        ValueError: source_entity_type not in CANONICAL_MAPPINGS
    """
    mapping = get_mapping(request.source_entity_type)
    if mapping is None:
        raise ValueError(
            f"No canonical mapping for source_entity_type "
            f"{request.source_entity_type!r}. Canonical mappings: "
            f"{sorted(CANONICAL_MAPPINGS.keys())}"
        )

    # Resolve event timestamps — compliance subtracts days_before_event.
    if mapping.days_before_event:
        start_at = request.date_at - timedelta(days=mapping.days_before_event)
    else:
        start_at = request.date_at
    end_at = start_at + timedelta(minutes=request.duration_minutes)

    # Compose subject from template.
    subject = mapping.default_subject_template.format(
        entity=request.source_entity_label
    )

    # Determine attendee partition.
    internal_emails = list(request.attendee_emails or [])
    external_emails = list(request.external_attendee_emails or [])
    has_external = len(external_emails) > 0
    # has_cross_tenant_attendees: would require a check against User
    # table to detect whether internal_emails resolve to a different
    # tenant. Step 3 ships the auto-confirmation rule but defers actual
    # cross-tenant attendee detection at this entry point (caller can
    # explicitly mark cross-tenant via the mapping's cross_tenant flag).
    has_cross_tenant = mapping.cross_tenant

    auto_confirm = should_auto_confirm(
        mapping=mapping,
        has_external_attendees=has_external,
        has_cross_tenant_attendees=has_cross_tenant,
    )

    initial_status = "confirmed" if auto_confirm else "tentative"

    tenant_id = request.tenant_id or account.tenant_id

    # Create the canonical CalendarEvent row.
    event = CalendarEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        account_id=account.id,
        subject=subject,
        description_text=request.description,
        location=request.location,
        start_at=start_at,
        end_at=end_at,
        is_all_day=False,
        event_timezone=account.default_event_timezone,
        recurrence_rule=None,
        status=initial_status,
        transparency="opaque",
        is_cross_tenant=mapping.cross_tenant,
        # Step 3 state-change provenance per §3.26.16.18.
        generation_source="state_change",
        generation_entity_type=request.source_entity_type,
        generation_entity_id=request.source_entity_id,
        created_by_user_id=request.actor_user_id,
    )
    db.add(event)
    db.flush()

    # Attendees — internal first, then external.
    for email in internal_emails:
        normalized = email.strip().lower()
        if "@" not in normalized:
            continue
        db.add(
            CalendarEventAttendee(
                id=str(uuid.uuid4()),
                event_id=event.id,
                tenant_id=tenant_id,
                email_address=normalized,
                role="required_attendee",
                response_status="needs_action",
                is_internal=True,
            )
        )
    for email in external_emails:
        normalized = email.strip().lower()
        if "@" not in normalized:
            continue
        db.add(
            CalendarEventAttendee(
                id=str(uuid.uuid4()),
                event_id=event.id,
                tenant_id=tenant_id,
                email_address=normalized,
                role="required_attendee",
                response_status="needs_action",
                is_internal=False,
            )
        )
    db.flush()

    # Linkage row — polymorphic per §3.26.16.7.
    linkage = CalendarEventLinkage(
        id=str(uuid.uuid4()),
        event_id=event.id,
        tenant_id=tenant_id,
        linked_entity_type=mapping.linked_entity_type,
        linked_entity_id=request.source_entity_id,
        linkage_source="manual_pre_link",
        linked_by_user_id=request.actor_user_id,
    )
    db.add(linkage)
    db.flush()

    # Audit log per §3.26.16.18 audit trail discipline.
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=request.actor_user_id,
        action="event_drafted_from_state_change",
        entity_type="calendar_event",
        entity_id=event.id,
        changes={
            "generation_source": "state_change",
            "source_entity_type": request.source_entity_type,
            "source_entity_id": request.source_entity_id,
            "auto_confirmed": auto_confirm,
            "initial_status": initial_status,
            "internal_attendee_count": len(internal_emails),
            "external_attendee_count": len(external_emails),
            "cross_tenant": mapping.cross_tenant,
            "days_before_event": mapping.days_before_event,
        },
    )
    db.flush()

    return event


# ─────────────────────────────────────────────────────────────────────
# Read helpers — drafted-event review queue
# ─────────────────────────────────────────────────────────────────────


def list_drafted_state_change_events(
    db: Session,
    *,
    tenant_id: str,
    limit: int = 100,
) -> list[CalendarEvent]:
    """List tentative state-change-drafted events for the operator review queue.

    Returns events with `status="tentative"` AND
    `generation_source="state_change"` ordered by `start_at` ascending
    (soonest-first).
    """
    return (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.tenant_id == tenant_id,
            CalendarEvent.is_active.is_(True),
            CalendarEvent.status == "tentative",
            CalendarEvent.generation_source == "state_change",
        )
        .order_by(CalendarEvent.start_at.asc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
