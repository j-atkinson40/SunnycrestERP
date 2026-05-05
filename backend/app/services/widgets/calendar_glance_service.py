"""Calendar Glance widget data service — Phase W-4b Layer 1 Calendar Step 5.

Surfaces calendar signals for the Pulse Communications Layer per
§3.26.16.10 Pulse Communications Layer Glance widget canon. Pattern
parallels Email's ``email_glance`` widget (Step 5 surface 1) verbatim.

**Signals computed** (per §3.26.16.10 verbatim):
  - ``pending_response_count`` — total events where caller is an
    attendee + ``response_status='needs_action'``, across all calendar
    accounts the caller has read access to.
  - ``cross_tenant_invitation_count`` — subset of above where
    `event.is_cross_tenant=True` AND a `cross_tenant_event_pairing`
    row exists with `paired_at IS NULL` (pending bilateral acceptance);
    these are NEW cross-tenant invitations awaiting the caller's
    response.
  - ``top_inviter_email`` + ``top_inviter_name`` + ``top_inviter_tenant_label``
    — most-recent pending event's organizer; tenant_label populated
    only when cross-tenant per §3.26.9.4 anonymization-at-layer canon.
  - ``target_event_id`` — set ONLY when single-event surface (drives
    ``/calendar/events/{id}`` direct-link click navigation per §14.10
    canonical chrome).
  - ``has_calendar_access`` — bool driving empty-state vs "All
    responded" rendering.

**Communications Layer scope discipline** (per §3.26.16.10 verbatim):
this widget surfaces ONLY interpersonal-scheduling signals (responses
awaiting the caller's reply OR new cross-tenant invitations).
Operational-today-scheduling signals route to the Operational layer
separately (`today_widget` extension + `calendar_summary` widget).
Hybrid contribution pattern canonical for future Layer 1 primitives
per §3.26.16.10.

**Tenant isolation discipline**:
  - Caller's accessible accounts resolved via
    ``CalendarAccountAccess`` junction filtered to caller's tenant
    (mirrors `account_service.user_has_access` canonical helper at
    list scope).
  - Every query joins ``calendar_event_attendees`` →
    ``calendar_events`` → ``calendar_accounts`` → access junction so
    we never read an event the caller lacks access to.
  - Per-user discipline: response-needs-action state is per-attendee;
    only attendee rows where ``email_address`` matches caller's email
    OR ``resolved_user_id`` matches caller's id surface.

**Performance budget** (per Step 5 spec): p50 < 200ms — matches
``email_glance`` budget. Cap unread fan-out at 50 rows for
sender-resolution; precise-count query when capped.

**Empty/disabled states**:
  - User has no accessible accounts → ``has_calendar_access: False``;
    widget renders empty-state.
  - User has accounts but zero pending → ``pending_response_count: 0``,
    ``has_calendar_access: True``; widget renders "All responded"
    canonical empty state.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountAccess,
    CalendarEvent,
    CalendarEventAttendee,
    CrossTenantEventPairing,
)
from app.models.company import Company
from app.models.user import User

logger = logging.getLogger(__name__)


def _accessible_account_ids(
    db: Session, *, tenant_id: str, user_id: str
) -> list[str]:
    """Return CalendarAccount ids the caller currently has read access on.

    Mirrors the canonical access-grants helper for Calendar accounts
    (parallels Email's ``inbox_service._accessible_account_ids``).
    Local helper is deliberate: widget data fetches happen on Pulse
    load + 5-min refresh; coupling to a heavy upstream module forces
    needless imports per fetch.
    """
    rows = (
        db.query(CalendarAccount.id)
        .join(
            CalendarAccountAccess,
            CalendarAccountAccess.account_id == CalendarAccount.id,
        )
        .filter(
            CalendarAccount.tenant_id == tenant_id,
            CalendarAccount.is_active.is_(True),
            CalendarAccountAccess.user_id == user_id,
            CalendarAccountAccess.revoked_at.is_(None),
        )
        .all()
    )
    return [row[0] for row in rows]


def get_calendar_glance(db: Session, *, user: User) -> dict[str, Any]:
    """Return the calendar_glance widget data payload for the given user.

    Returns a JSON-serializable dict with:
      - has_calendar_access: bool
      - pending_response_count: int — events caller is invited to with
        response_status='needs_action'
      - cross_tenant_invitation_count: int — subset of above that are
        NEW cross-tenant invitations (pairing pending bilateral accept)
      - top_inviter_email: str | None
      - top_inviter_name: str | None
      - top_inviter_tenant_label: str | None — populated only for
        cross-tenant invitations per §3.26.9.4
      - target_event_id: str | None — single-event direct link
    """
    if not user.company_id:
        return _empty_payload(has_calendar_access=False)

    account_ids = _accessible_account_ids(
        db, tenant_id=user.company_id, user_id=user.id
    )
    if not account_ids:
        return _empty_payload(has_calendar_access=False)

    # Match attendee rows by email_address OR resolved_user_id — Calendar
    # primitive's CalendarEventAttendee carries both columns per Step 1
    # entity model. Match either to support pre- + post-resolution rows.
    pending_query = (
        db.query(
            CalendarEventAttendee.id.label("attendee_id"),
            CalendarEvent.id.label("event_id"),
            CalendarEvent.is_cross_tenant,
            CalendarEvent.start_at,
        )
        .join(
            CalendarEvent,
            CalendarEvent.id == CalendarEventAttendee.event_id,
        )
        .filter(
            CalendarEvent.account_id.in_(account_ids),
            CalendarEvent.tenant_id == user.company_id,
            CalendarEvent.is_active.is_(True),
            CalendarEvent.status != "cancelled",
            CalendarEventAttendee.response_status == "needs_action",
            or_(
                CalendarEventAttendee.email_address == (user.email or ""),
                CalendarEventAttendee.resolved_user_id == user.id,
            ),
        )
        .order_by(desc(CalendarEvent.start_at))
    )

    pending_rows = pending_query.limit(50).all()  # cap fan-out for perf
    pending_response_count = len(pending_rows)

    # If we hit the cap, run a precise count so the rendered value is
    # honest (50+ rendering decision lives in widget UI).
    if pending_response_count >= 50:
        precise_count = (
            db.query(func.count(CalendarEventAttendee.id))
            .join(
                CalendarEvent,
                CalendarEvent.id == CalendarEventAttendee.event_id,
            )
            .filter(
                CalendarEvent.account_id.in_(account_ids),
                CalendarEvent.tenant_id == user.company_id,
                CalendarEvent.is_active.is_(True),
                CalendarEvent.status != "cancelled",
                CalendarEventAttendee.response_status == "needs_action",
                or_(
                    CalendarEventAttendee.email_address == (user.email or ""),
                    CalendarEventAttendee.resolved_user_id == user.id,
                ),
            )
            .scalar()
        )
        pending_response_count = int(precise_count or 0)

    # Cross-tenant invitation count — subset where the event is
    # cross-tenant AND has a pending pairing row (paired_at IS NULL +
    # revoked_at IS NULL per Step 4 pairing semantics).
    cross_tenant_invitation_count = 0
    target_event_id: str | None = None
    top_inviter_email: str | None = None
    top_inviter_name: str | None = None
    top_inviter_tenant_label: str | None = None

    if pending_rows:
        pending_event_ids = {row.event_id for row in pending_rows}
        cross_tenant_pending = (
            db.query(func.count(CrossTenantEventPairing.id))
            .filter(
                CrossTenantEventPairing.event_a_id.in_(pending_event_ids),
                CrossTenantEventPairing.paired_at.is_(None),
                CrossTenantEventPairing.revoked_at.is_(None),
            )
            .scalar()
        )
        cross_tenant_invitation_count = int(cross_tenant_pending or 0)

        # Top inviter resolution — most-recent pending event's organizer.
        top_event_id = pending_rows[0].event_id
        organizer = (
            db.query(CalendarEventAttendee, CalendarEvent)
            .join(
                CalendarEvent,
                CalendarEvent.id == CalendarEventAttendee.event_id,
            )
            .filter(
                CalendarEventAttendee.event_id == top_event_id,
                CalendarEventAttendee.role == "organizer",
            )
            .first()
        )
        if organizer:
            organizer_attendee, organizer_event = organizer
            top_inviter_email = organizer_attendee.email_address
            top_inviter_name = organizer_attendee.display_name

            # Cross-tenant indicator → resolve partner tenant label
            # per §3.26.9.4 anonymization-at-layer.
            if organizer_event.is_cross_tenant:
                top_inviter_tenant_label = _resolve_partner_tenant_label(
                    db,
                    event_id=organizer_event.id,
                    caller_tenant_id=user.company_id,
                )

        # target_event_id surfaces ONLY when there's exactly one pending
        # event → click goes directly to that event detail page.
        # Multi-event surface lands on /calendar?status=needs_action.
        if len(pending_event_ids) == 1:
            target_event_id = next(iter(pending_event_ids))

    return {
        "has_calendar_access": True,
        "pending_response_count": pending_response_count,
        "cross_tenant_invitation_count": cross_tenant_invitation_count,
        "top_inviter_email": top_inviter_email,
        "top_inviter_name": top_inviter_name,
        "top_inviter_tenant_label": top_inviter_tenant_label,
        "target_event_id": target_event_id,
    }


def _empty_payload(*, has_calendar_access: bool) -> dict[str, Any]:
    """Return the canonical empty-state shape."""
    return {
        "has_calendar_access": has_calendar_access,
        "pending_response_count": 0,
        "cross_tenant_invitation_count": 0,
        "top_inviter_email": None,
        "top_inviter_name": None,
        "top_inviter_tenant_label": None,
        "target_event_id": None,
    }


def _resolve_partner_tenant_label(
    db: Session, *, event_id: str, caller_tenant_id: str
) -> str | None:
    """Resolve a display label for the cross-tenant partner inviter.

    Per §3.26.9.4 anonymization-at-layer-rendering: organizer identity
    surfaces at the company level by default for cross-tenant signals.
    Walks ``cross_tenant_event_pairing`` to find the partner tenant
    and returns its company name. Returns None when partner tenant
    cannot be resolved.
    """
    pairing = (
        db.query(CrossTenantEventPairing)
        .filter(
            or_(
                CrossTenantEventPairing.event_a_id == event_id,
                CrossTenantEventPairing.event_b_id == event_id,
            ),
            CrossTenantEventPairing.revoked_at.is_(None),
        )
        .first()
    )
    if not pairing:
        return None

    partner_tenant_id = (
        pairing.tenant_b_id
        if pairing.tenant_a_id == caller_tenant_id
        else pairing.tenant_a_id
    )
    partner = (
        db.query(Company.name).filter(Company.id == partner_tenant_id).first()
    )
    return partner[0] if partner else None
