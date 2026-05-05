"""Calendar Summary widget data + today_widget calendar extension —
Phase W-4b Layer 1 Calendar Step 5.

Per §3.26.16.10 Pulse **Operational Layer extensions**:

  - existing ``today_widget`` extends to surface today's calendar
    events as operational signals (extension via this module's
    ``today_calendar_extension``)
  - new ``calendar_summary`` widget surfaces this-week schedule for
    operational coordination

**Operational vs Communications discipline** (per §3.26.16.10 hybrid
contribution canonical): this module surfaces operational-work
signals (today's confirmed events + week schedule). Interpersonal-
scheduling signals (responses awaiting + new cross-tenant invitations)
route to ``calendar_glance`` widget (Communications Layer); they
DON'T re-surface here.

**Data discipline**:
  - Confirmed events only (``status='confirmed'``) — tentative drafts +
    cancelled events do NOT surface in operational layer rendering
  - Opaque transparency only (``transparency='opaque'``) — transparent
    events don't represent operational time-blocks per RFC 5545
  - Cross-account aggregation across all calendar accounts caller has
    read access to (per CalendarAccountAccess junction)

**Tenant isolation discipline** (parallel to ``calendar_glance``):
  caller's accessible accounts resolved via the access junction; every
  query joins the access-grants chain.

**Performance budget** (per Step 5 spec): p50 < 200ms — matches widget
data service standard. Today-events query bounded by date filter;
week-summary query similarly bounded.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountAccess,
    CalendarEvent,
)
from app.models.user import User
from app.services.widgets.calendar_glance_service import (
    _accessible_account_ids,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# today_widget calendar extension
# ─────────────────────────────────────────────────────────────────────


def get_today_calendar_extension(
    db: Session, *, user: User, now: datetime | None = None
) -> dict[str, Any]:
    """Return today's calendar events for the today_widget extension.

    Extends the existing ``today_widget`` rendering with calendar
    events as operational-layer signals per §3.26.16.10. Caller (the
    today_widget service) composes this into its rendered payload.

    Per §3.26.16.10 Operational Layer scope: confirmed + opaque events
    only. Tentative drafts route to the drafted-event review queue
    (Step 3 surface), not the operational layer.

    Args:
        user: caller (drives accessible-account resolution).
        now: optional override for testing; defaults to current UTC.

    Returns dict shape:
      {
        "has_calendar_access": bool,
        "today_event_count": int,
        "events": [
          {
            "id": str,
            "subject": str,
            "start_at": ISO datetime,
            "end_at": ISO datetime,
            "location": str | None,
            "is_cross_tenant": bool,
          },
          ...
        ],  # ordered ascending by start_at; capped at 20 for fan-out
      }
    """
    if not user.company_id:
        return {"has_calendar_access": False, "today_event_count": 0, "events": []}

    account_ids = _accessible_account_ids(
        db, tenant_id=user.company_id, user_id=user.id
    )
    if not account_ids:
        return {"has_calendar_access": False, "today_event_count": 0, "events": []}

    now = now or datetime.now(timezone.utc)
    # Day window in caller's UTC frame — tenant timezone application
    # deferred per §3.26.16.x timezone canon (Step 5 reads UTC events;
    # frontend applies tenant timezone for display per §14.10.1).
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    rows = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.account_id.in_(account_ids),
            CalendarEvent.tenant_id == user.company_id,
            CalendarEvent.is_active.is_(True),
            CalendarEvent.status == "confirmed",
            CalendarEvent.transparency == "opaque",
            CalendarEvent.start_at >= day_start,
            CalendarEvent.start_at < day_end,
        )
        .order_by(asc(CalendarEvent.start_at))
        .limit(20)
        .all()
    )

    return {
        "has_calendar_access": True,
        "today_event_count": len(rows),
        "events": [
            {
                "id": e.id,
                "subject": e.subject,
                "start_at": e.start_at.isoformat(),
                "end_at": e.end_at.isoformat(),
                "location": e.location,
                "is_cross_tenant": e.is_cross_tenant,
            }
            for e in rows
        ],
    }


# ─────────────────────────────────────────────────────────────────────
# calendar_summary widget — week/period schedule
# ─────────────────────────────────────────────────────────────────────


def get_calendar_summary(
    db: Session,
    *,
    user: User,
    days: int = 7,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return next-N-days calendar summary for the calendar_summary widget.

    Per §3.26.16.10 Operational Layer extension: surfaces this-week
    schedule for operational coordination — NOT individual event
    response state (that lives in calendar_glance).

    Args:
        user: caller.
        days: window length in days. Default 7 (one week from today).
        now: optional override for testing.

    Returns dict shape:
      {
        "has_calendar_access": bool,
        "window_days": int,
        "total_event_count": int,
        "next_event": { id, subject, start_at, end_at, location } | None,
        "by_day": [
          {
            "date": ISO date string,
            "event_count": int,
            "first_event_subject": str | None,
          },
          ...  # one row per day in window; ordered ascending
        ],
      }

    Capped at 200 total event rows for fan-out — pathological large
    cross-account aggregations are summary-truncated, never
    blocking.
    """
    if not user.company_id:
        return _empty_summary(days=days)

    account_ids = _accessible_account_ids(
        db, tenant_id=user.company_id, user_id=user.id
    )
    if not account_ids:
        return _empty_summary(days=days)

    now = now or datetime.now(timezone.utc)
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=days)

    rows = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.account_id.in_(account_ids),
            CalendarEvent.tenant_id == user.company_id,
            CalendarEvent.is_active.is_(True),
            CalendarEvent.status == "confirmed",
            CalendarEvent.transparency == "opaque",
            CalendarEvent.start_at >= window_start,
            CalendarEvent.start_at < window_end,
        )
        .order_by(asc(CalendarEvent.start_at))
        .limit(200)
        .all()
    )

    # Aggregate by day for the by_day surface.
    by_day_map: dict[str, dict[str, Any]] = {}
    for d in range(days):
        date_key = (window_start + timedelta(days=d)).date().isoformat()
        by_day_map[date_key] = {
            "date": date_key,
            "event_count": 0,
            "first_event_subject": None,
        }

    for e in rows:
        date_key = e.start_at.date().isoformat()
        if date_key not in by_day_map:
            # Defensive — event slipped outside window via timezone math
            continue
        bucket = by_day_map[date_key]
        bucket["event_count"] += 1
        if bucket["first_event_subject"] is None:
            bucket["first_event_subject"] = e.subject

    next_event_payload: dict[str, Any] | None = None
    if rows:
        n = rows[0]
        next_event_payload = {
            "id": n.id,
            "subject": n.subject,
            "start_at": n.start_at.isoformat(),
            "end_at": n.end_at.isoformat(),
            "location": n.location,
        }

    return {
        "has_calendar_access": True,
        "window_days": days,
        "total_event_count": len(rows),
        "next_event": next_event_payload,
        "by_day": [by_day_map[k] for k in sorted(by_day_map.keys())],
    }


def _empty_summary(*, days: int) -> dict[str, Any]:
    return {
        "has_calendar_access": False,
        "window_days": days,
        "total_event_count": 0,
        "next_event": None,
        "by_day": [],
    }
