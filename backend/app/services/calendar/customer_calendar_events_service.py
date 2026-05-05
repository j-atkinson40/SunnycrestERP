"""Customer Pulse calendar events composition source —
Phase W-4b Layer 1 Calendar Step 5 Surface 4.

Per §3.26.16.10 + §3.26.12.3 Customer Pulse composition canon:
scoped Pulses orchestrate existing primitives at scope; the Customer
Pulse template (per §3.26.12.4 Layer A platform default) composes
recent + upcoming events filtered to the orchestration entity (the
customer).

**Step 5 ships data-layer-only** per the canon-faithful scope (matches
Email Step 5 ``customer_email_threads_service`` pattern verbatim):
  - This service + endpoint establish the canonical query pattern
  - Customer Pulse template extension (slot mapping declaration)
    deferred until scoped Pulse infrastructure ships per §3.26.12.4
  - Endpoint stands alone as a queryable resource that any future
    composition (Customer Pulse, related-entities peek panel,
    customer-detail page event timeline, etc.) can consume

**Canonical resource for future scoped Pulse consumption** — when
scoped Pulse summoning + per-template slot mapping infrastructure
lands per §3.26.12.4, the Customer Pulse template's
``calendar_events`` slot consumes
``GET /api/v1/customers/{customer_entity_id}/calendar-events`` rather
than building parallel query patterns.

**Event-to-customer matching** (two-source resolution mirrors Email
Step 5 ``customer_email_threads_service``):
  1. **Direct entity linkage** — events with
     ``CalendarEventLinkage(linked_entity_type='customer',
     linked_entity_id=<CompanyEntity.id>)``
  2. **Indirect via FH case** — events with
     ``CalendarEventLinkage(linked_entity_type='fh_case', ...)`` whose
     FHCase resolves through Customer.master_company_id to the
     CompanyEntity
  3. **Indirect via sales order** — events with
     ``CalendarEventLinkage(linked_entity_type='sales_order', ...)``
     whose SalesOrder resolves through Customer.master_company_id
  4. **Auto-resolved attendee linkage** — events whose
     CalendarEventAttendee.resolved_company_entity_id matches the
     CompanyEntity.id

All paths union; event-id deduplication via Python set. Sort by
``CalendarEvent.start_at DESC`` (recent first, walking backward + a
forward-window for upcoming events). Cap at ``limit`` (default 5,
hard ceiling 50) per §3.26.12.4 Layer C live-data discipline.

**Tenant isolation discipline**:
  - Service requires ``caller_tenant_id`` parameter; events filtered
    to ``tenant_id == caller_tenant_id``
  - Cross-tenant CompanyEntity probes return existence-hiding empty
    payload (parallel to Email Step 5 cross-tenant guard)
  - User access enforced via ``CalendarAccountAccess`` junction
    (mirrors ``calendar_glance_service._accessible_account_ids``)

**Performance budget** (per Step 5 spec): p50 < 300ms — matches
scoped Pulse composition resolution budget per §3.26.12.4 Layer B.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventLinkage,
)
from app.models.company_entity import CompanyEntity
from app.services.widgets.calendar_glance_service import (
    _accessible_account_ids,
)

logger = logging.getLogger(__name__)


def get_calendar_events_for_customer(
    db: Session,
    *,
    customer_entity_id: str,
    caller_tenant_id: str,
    caller_user_id: str,
    limit: int = 5,
    upcoming_window_days: int = 60,
    recent_window_days: int = 60,
) -> dict[str, Any]:
    """Return recent + upcoming calendar events scoped to a customer.

    Args:
      customer_entity_id: CompanyEntity.id (caller's tenant's CRM-side
        customer representation).
      caller_tenant_id: caller's tenant; cross-tenant CompanyEntity
        probes return existence-hiding empty payload.
      caller_user_id: drives accessible-account resolution (per
        CalendarAccountAccess junction).
      limit: per-bucket (recent + upcoming) cap. Hard ceiling 50.
      upcoming_window_days: forward window for "upcoming" bucket.
      recent_window_days: backward window for "recent" bucket.

    Returns dict shape:
      {
        "customer_entity_id": str,
        "customer_name": str | None,
        "recent_events": [event_payload, ...],     # past, recency-sorted
        "upcoming_events": [event_payload, ...],   # future, soon-first
        "total_count": int,                        # union of both buckets
      }

    Cross-tenant guard: when CompanyEntity row's company_id mismatches
    caller_tenant_id, returns empty payload with customer_name=None
    (existence-hiding parallel to Email Step 5).
    """
    # Cap limit at hard ceiling.
    effective_limit = max(1, min(int(limit), 50))

    # Tenant isolation — verify the CompanyEntity belongs to caller.
    customer = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.id == customer_entity_id,
            CompanyEntity.company_id == caller_tenant_id,
        )
        .first()
    )
    if customer is None:
        # Existence-hiding: cross-tenant or unknown customer → empty.
        return {
            "customer_entity_id": customer_entity_id,
            "customer_name": None,
            "recent_events": [],
            "upcoming_events": [],
            "total_count": 0,
        }

    # Caller's accessible accounts.
    account_ids = _accessible_account_ids(
        db, tenant_id=caller_tenant_id, user_id=caller_user_id
    )
    if not account_ids:
        return {
            "customer_entity_id": customer_entity_id,
            "customer_name": customer.name,
            "recent_events": [],
            "upcoming_events": [],
            "total_count": 0,
        }

    # Resolve event ids matching the customer (multi-source union).
    event_ids = _resolve_event_ids_for_customer(
        db,
        customer_entity_id=customer_entity_id,
        caller_tenant_id=caller_tenant_id,
    )
    if not event_ids:
        return {
            "customer_entity_id": customer_entity_id,
            "customer_name": customer.name,
            "recent_events": [],
            "upcoming_events": [],
            "total_count": 0,
        }

    now = datetime.now(timezone.utc)
    upcoming_horizon = now + timedelta(days=upcoming_window_days)
    recent_horizon = now - timedelta(days=recent_window_days)

    # Upcoming bucket: start_at in [now, now + upcoming_window_days].
    upcoming_rows = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.id.in_(event_ids),
            CalendarEvent.account_id.in_(account_ids),
            CalendarEvent.tenant_id == caller_tenant_id,
            CalendarEvent.is_active.is_(True),
            CalendarEvent.status != "cancelled",
            CalendarEvent.start_at >= now,
            CalendarEvent.start_at < upcoming_horizon,
        )
        .order_by(CalendarEvent.start_at.asc())
        .limit(effective_limit)
        .all()
    )

    # Recent bucket: start_at in [now - recent_window_days, now).
    recent_rows = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.id.in_(event_ids),
            CalendarEvent.account_id.in_(account_ids),
            CalendarEvent.tenant_id == caller_tenant_id,
            CalendarEvent.is_active.is_(True),
            CalendarEvent.status != "cancelled",
            CalendarEvent.start_at >= recent_horizon,
            CalendarEvent.start_at < now,
        )
        .order_by(desc(CalendarEvent.start_at))
        .limit(effective_limit)
        .all()
    )

    return {
        "customer_entity_id": customer_entity_id,
        "customer_name": customer.name,
        "recent_events": [_event_payload(e) for e in recent_rows],
        "upcoming_events": [_event_payload(e) for e in upcoming_rows],
        "total_count": len(recent_rows) + len(upcoming_rows),
    }


# ─────────────────────────────────────────────────────────────────────
# Event-to-customer matching helpers
# ─────────────────────────────────────────────────────────────────────


def _resolve_event_ids_for_customer(
    db: Session,
    *,
    customer_entity_id: str,
    caller_tenant_id: str,
) -> set[str]:
    """Return event ids matching the customer via multi-source linkage.

    Four sources:
      1. CalendarEventLinkage(linked_entity_type='customer',
         linked_entity_id=<CompanyEntity.id>) — direct
      2. CalendarEventLinkage(linked_entity_type='fh_case', ...) →
         FHCase.customer_id → Customer.master_company_id
      3. CalendarEventLinkage(linked_entity_type='sales_order', ...) →
         SalesOrder.customer_id → Customer.master_company_id
      4. CalendarEventAttendee.resolved_company_entity_id matches
    """
    event_ids: set[str] = set()

    # Source 1: direct customer linkage
    direct_rows = (
        db.query(CalendarEventLinkage.event_id)
        .filter(
            CalendarEventLinkage.tenant_id == caller_tenant_id,
            CalendarEventLinkage.linked_entity_type == "customer",
            CalendarEventLinkage.linked_entity_id == customer_entity_id,
            CalendarEventLinkage.dismissed_at.is_(None),
        )
        .all()
    )
    for (eid,) in direct_rows:
        event_ids.add(eid)

    # Source 2: indirect via fh_case
    try:
        from app.models.customer import Customer
        from app.models.fh_case import FHCase

        fh_event_rows = (
            db.query(CalendarEventLinkage.event_id)
            .join(FHCase, FHCase.id == CalendarEventLinkage.linked_entity_id)
            .join(Customer, Customer.id == FHCase.customer_id)
            .filter(
                CalendarEventLinkage.tenant_id == caller_tenant_id,
                CalendarEventLinkage.linked_entity_type == "fh_case",
                CalendarEventLinkage.dismissed_at.is_(None),
                Customer.master_company_id == customer_entity_id,
                Customer.company_id == caller_tenant_id,
            )
            .all()
        )
        for (eid,) in fh_event_rows:
            event_ids.add(eid)
    except Exception:
        # FHCase / Customer model issues never block customer event resolution.
        logger.exception(
            "fh_case-indirect resolution failed for customer %s",
            customer_entity_id,
        )

    # Source 3: indirect via sales_order
    try:
        from app.models.customer import Customer
        from app.models.sales_order import SalesOrder

        so_event_rows = (
            db.query(CalendarEventLinkage.event_id)
            .join(
                SalesOrder, SalesOrder.id == CalendarEventLinkage.linked_entity_id
            )
            .join(Customer, Customer.id == SalesOrder.customer_id)
            .filter(
                CalendarEventLinkage.tenant_id == caller_tenant_id,
                CalendarEventLinkage.linked_entity_type == "sales_order",
                CalendarEventLinkage.dismissed_at.is_(None),
                Customer.master_company_id == customer_entity_id,
                Customer.company_id == caller_tenant_id,
            )
            .all()
        )
        for (eid,) in so_event_rows:
            event_ids.add(eid)
    except Exception:
        logger.exception(
            "sales_order-indirect resolution failed for customer %s",
            customer_entity_id,
        )

    # Source 4: attendee resolved_company_entity_id
    attendee_rows = (
        db.query(CalendarEventAttendee.event_id)
        .filter(
            CalendarEventAttendee.tenant_id == caller_tenant_id,
            CalendarEventAttendee.resolved_company_entity_id
            == customer_entity_id,
        )
        .all()
    )
    for (eid,) in attendee_rows:
        event_ids.add(eid)

    return event_ids


def _event_payload(event: CalendarEvent) -> dict[str, Any]:
    """Serialize a calendar event for Customer Pulse rendering."""
    return {
        "id": event.id,
        "subject": event.subject,
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat(),
        "location": event.location,
        "status": event.status,
        "is_cross_tenant": event.is_cross_tenant,
    }
