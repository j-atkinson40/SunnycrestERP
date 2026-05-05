"""V-1c CRM activity feed integration for calendar events —
Phase W-4b Layer 1 Calendar Step 5 Surface 7.

Per §3.26.16.10 row 7: "Calendar events surface in entity activity
feed (event scheduled, event modified, event cancelled, attendee
responded)". Calendar is one of multiple event source types in the
existing pluralistic activity log (mirrors Email Step 5 surface 3
verbatim).

**No new infrastructure** — uses the canonical
``app.services.crm.activity_log_service.log_system_event()`` write
path. Frontend ``RecentActivityWidget`` ``activityVerb`` map gets a
new ``calendar`` entry (one-line addition) so the widget renders
"logged a calendar event" without any other code change.

**Four event-lifecycle write sites wired**:

  1. **Event scheduled** (`event_service.create_event` post-commit):
     when an event is created with a linked CompanyEntity OR an
     attendee whose resolved_company_entity_id matches a known
     customer → write activity row(s).
  2. **Event modified** (`event_service.update_event` post-commit OR
     `outbound_service.send_event` on commit-from-tentative):
     significant time/location changes surface as activity.
  3. **Event cancelled** (`event_service.delete_event` OR
     `outbound_service.cancel_event`): cancellation surfaces.
  4. **Attendee responded** (`itip_inbound.process_inbound_reply`):
     when an attendee accepts/declines a cross-tenant invitation,
     activity surfaces on the customer entity.

**master_company_id resolver helper** (parallels Email Step 5):
  - Direct: ``CalendarEventLinkage`` with linked_entity_type="customer"
    + linked_entity_id is a CompanyEntity.id → use directly
  - Direct: ``CalendarEventAttendee.resolved_company_entity_id`` is a
    CompanyEntity.id → use directly
  - Indirect: ``CalendarEventLinkage`` with linked_entity_type="fh_case"
    → FHCase.customer_id → Customer.master_company_id
  - Indirect: ``CalendarEventLinkage`` with linked_entity_type=
    "sales_order" → SalesOrder.customer_id → Customer.master_company_id

**Tenant isolation discipline**:
  - Every activity write enforces ``tenant_id`` matches the calendar
    event's tenant_id
  - Cross-tenant CompanyEntity references are NOT written into the
    caller's activity feed (per §3.25.x masking — partner tenant's
    CompanyEntity surfaces only in their own activity log)

**Failure-mode discipline**:
  - Activity log writes are best-effort; failures are logged but
    NEVER block calendar event mutations
  - Mirror of the canonical CRM activity log discipline +
    Email Step 5 activity_feed_integration

**Click-through routing**:
  - Activity row body carries ``event_id=<uuid>`` reference; widget
    click navigates to ``/calendar/events/<id>`` (Step 5 native event
    detail page route per Q4 confirmed)
"""

from __future__ import annotations

import logging
from typing import Iterable, Literal

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventLinkage,
)

logger = logging.getLogger(__name__)


CalendarActivityKind = Literal[
    "scheduled", "modified", "cancelled", "attendee_responded"
]


def _resolve_master_company_ids_for_event(
    db: Session, event: CalendarEvent
) -> set[str]:
    """Return CompanyEntity ids that should receive activity for this event.

    Sources (deduped via set):
      1. CalendarEventLinkage with linked_entity_type="customer" →
         linked_entity_id IS CompanyEntity.id directly
      2. CalendarEventAttendee.resolved_company_entity_id (auto-resolved
         attendees whose master_company linkage points at CompanyEntity)
      3. CalendarEventLinkage with linked_entity_type="fh_case" →
         resolve FHCase → Customer.master_company_id
      4. CalendarEventLinkage with linked_entity_type="sales_order" →
         resolve SalesOrder → Customer.master_company_id

    Tenant-scoped via event.tenant_id; we never resolve cross-tenant
    company entities. Returns empty set when the event has no
    resolvable master_company linkage.
    """
    master_company_ids: set[str] = set()

    # Source 1 + 3 + 4: linkage rows
    linkage_rows = (
        db.query(
            CalendarEventLinkage.linked_entity_type,
            CalendarEventLinkage.linked_entity_id,
        )
        .filter(
            CalendarEventLinkage.event_id == event.id,
            CalendarEventLinkage.tenant_id == event.tenant_id,
            CalendarEventLinkage.dismissed_at.is_(None),
        )
        .all()
    )
    for entity_type, entity_id in linkage_rows:
        if entity_type == "customer":
            master_company_ids.add(entity_id)
        elif entity_type == "fh_case":
            mc_id = _resolve_master_company_for_case(
                db, fh_case_id=entity_id, tenant_id=event.tenant_id
            )
            if mc_id:
                master_company_ids.add(mc_id)
        elif entity_type == "sales_order":
            mc_id = _resolve_master_company_for_order(
                db, sales_order_id=entity_id, tenant_id=event.tenant_id
            )
            if mc_id:
                master_company_ids.add(mc_id)
        # Other entity types (vault_item, quote) don't surface in CRM
        # activity feeds — they aren't CompanyEntity-scoped surfaces.

    # Source 2: auto-resolved attendee linkage
    attendee_rows = (
        db.query(CalendarEventAttendee.resolved_company_entity_id)
        .filter(
            CalendarEventAttendee.event_id == event.id,
            CalendarEventAttendee.tenant_id == event.tenant_id,
            CalendarEventAttendee.resolved_company_entity_id.isnot(None),
        )
        .all()
    )
    for (company_entity_id,) in attendee_rows:
        if company_entity_id:
            master_company_ids.add(company_entity_id)

    return master_company_ids


def _resolve_master_company_for_case(
    db: Session, *, fh_case_id: str, tenant_id: str
) -> str | None:
    """Resolve FHCase.customer_id → Customer.master_company_id."""
    try:
        from app.models.customer import Customer
        from app.models.fh_case import FHCase

        case = (
            db.query(FHCase.customer_id)
            .filter(
                FHCase.id == fh_case_id,
                FHCase.company_id == tenant_id,
            )
            .first()
        )
        if not case or not case[0]:
            return None
        cust = (
            db.query(Customer.master_company_id)
            .filter(
                Customer.id == case[0],
                Customer.company_id == tenant_id,
            )
            .first()
        )
        return cust[0] if cust and cust[0] else None
    except Exception:
        logger.exception(
            "Failed to resolve master_company for fh_case %s", fh_case_id
        )
        return None


def _resolve_master_company_for_order(
    db: Session, *, sales_order_id: str, tenant_id: str
) -> str | None:
    """Resolve SalesOrder.customer_id → Customer.master_company_id."""
    try:
        from app.models.customer import Customer
        from app.models.sales_order import SalesOrder

        so = (
            db.query(SalesOrder.customer_id)
            .filter(
                SalesOrder.id == sales_order_id,
                SalesOrder.company_id == tenant_id,
            )
            .first()
        )
        if not so or not so[0]:
            return None
        cust = (
            db.query(Customer.master_company_id)
            .filter(
                Customer.id == so[0],
                Customer.company_id == tenant_id,
            )
            .first()
        )
        return cust[0] if cust and cust[0] else None
    except Exception:
        logger.exception(
            "Failed to resolve master_company for sales_order %s",
            sales_order_id,
        )
        return None


def _kind_to_title(
    *, kind: CalendarActivityKind, subject: str
) -> str:
    """Build the activity row title for the given lifecycle event kind."""
    label = subject or "(no subject)"
    if kind == "scheduled":
        return f"Calendar event scheduled — {label}"
    if kind == "modified":
        return f"Calendar event updated — {label}"
    if kind == "cancelled":
        return f"Calendar event cancelled — {label}"
    if kind == "attendee_responded":
        return f"Attendee responded — {label}"
    return f"Calendar event — {label}"


def log_calendar_event_activity(
    db: Session,
    *,
    event: CalendarEvent,
    kind: CalendarActivityKind,
    actor_user_id: str | None = None,
    detail: str | None = None,
) -> None:
    """Write activity log entries for every CompanyEntity that should
    surface this calendar event lifecycle event in their V-1c activity
    feed.

    Best-effort; failures are logged but never block the caller. The
    canonical ``activity_log_service.log_system_event`` already wraps
    write failures in try/except — this wrapper adds master_company
    resolution + per-entity fan-out + lifecycle-aware title shaping.

    Args:
      event: the persisted CalendarEvent
      kind: lifecycle event — "scheduled" | "modified" | "cancelled" |
        "attendee_responded"
      actor_user_id: user who triggered the event (None for inbound iTIP
        REPLY which has no Bridgeable actor)
      detail: optional override text appended to body (e.g. "Mary Hopkins
        accepted" for attendee_responded)
    """
    if not event:
        return

    try:
        master_company_ids = _resolve_master_company_ids_for_event(db, event)
    except Exception:
        logger.exception(
            "master_company resolution failed for calendar event %s", event.id
        )
        return

    if not master_company_ids:
        # No CRM linkage — nothing to write. Activity feed surface is
        # CompanyEntity-scoped; events without customer linkage don't
        # surface there.
        return

    title = _kind_to_title(kind=kind, subject=event.subject or "")

    # Body carries event_id reference for click-through routing
    # (widget renders body field; click resolves /calendar/events/{id}).
    body_parts: list[str] = []
    if detail:
        body_parts.append(detail)
    when = event.start_at.isoformat() if event.start_at else "(no time)"
    body_parts.append(f"Starts {when}.")
    body_parts.append(f"event_id={event.id}")
    body = " ".join(body_parts)

    # Defer import to avoid circular cycles between calendar + crm.
    from app.services.crm.activity_log_service import log_system_event

    for master_company_id in master_company_ids:
        try:
            log_system_event(
                db,
                tenant_id=event.tenant_id,
                master_company_id=master_company_id,
                activity_type="calendar",
                title=title,
                body=body,
            )
        except Exception:
            logger.exception(
                "log_system_event failed for calendar event=%s "
                "master_company=%s",
                event.id,
                master_company_id,
            )
            # Continue to other entities — one failure shouldn't cascade.


def fan_out_master_company_ids(
    master_company_ids: Iterable[str],
) -> list[str]:
    """Return a deterministic-ordered list of unique master_company ids.

    Helper for tests + callers who need a stable order over a set.
    """
    return sorted({mc_id for mc_id in master_company_ids if mc_id})
