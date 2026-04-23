"""Dispatch schedule API — Phase B Session 1.

Routes under `/api/v1/dispatch/*` covering the scheduling state
machine (draft/finalized), the three-day Monitor range query, and
hole-dug quick-edits.

Permission model: all endpoints require `delivery.view` at minimum.
Finalize / revert require `delivery.finalize_schedule`. Hole-dug
updates require `delivery.edit_hole_dug`. The `dispatcher` system
role (seeded via role_service) has all three; other roles can be
granted via the per-role permissions UI.

Endpoints:
  GET    /api/v1/dispatch/schedule/{date}              — read state
  GET    /api/v1/dispatch/schedule/range               — Monitor 3-day
  POST   /api/v1/dispatch/schedule/{date}/ensure       — lazy create
  POST   /api/v1/dispatch/schedule/{date}/finalize     — explicit
  POST   /api/v1/dispatch/schedule/{date}/revert       — explicit
  PATCH  /api/v1/dispatch/delivery/{id}/hole-dug       — quick-edit
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.delivery import Delivery
from app.models.driver import Driver
from app.models.user import User
from app.services import delivery_schedule_service as schedule_service


router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────


class ScheduleStateResponse(BaseModel):
    id: str | None
    company_id: str | None
    schedule_date: str
    state: Literal["draft", "finalized", "not_created"]
    finalized_at: str | None
    finalized_by_user_id: str | None
    auto_finalized: bool
    last_reverted_at: str | None
    last_revert_reason: str | None
    created_at: str | None
    updated_at: str | None


class ScheduleRangeResponse(BaseModel):
    """Monitor three-day (or N-day) response. `schedules` is ONLY the
    rows that exist — the Monitor UI computes the set of visible dates
    and renders empty-state for dates where `schedules` has no entry."""
    start_date: str
    end_date: str
    schedules: list[ScheduleStateResponse]


class FinalizeRequest(BaseModel):
    """No body fields today — the user_id comes from the auth context.
    Accepts an empty JSON body. Present as a schema for future
    expansion (e.g., a `notes` field stamped on the finalize event)."""
    notes: str | None = Field(default=None, max_length=500)


class RevertRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class HoleDugRequest(BaseModel):
    status: Literal["unknown", "yes", "no"] | None


class HoleDugResponse(BaseModel):
    delivery_id: str
    hole_dug_status: str | None
    schedule_reverted: bool
    schedule_date: str | None


# ── Helpers ────────────────────────────────────────────────────────────


def _schedule_to_response(row) -> ScheduleStateResponse:
    data = schedule_service.schedule_to_dict(row)
    return ScheduleStateResponse(**data)


def _placeholder_response(schedule_date: date) -> ScheduleStateResponse:
    """Returned when a date has no schedule row yet (lazy-create
    semantics — no row means 'draft with nothing committed'). Caller
    still sees state=`not_created` so the UI can render a clean
    empty state rather than inventing a fake draft row."""
    return ScheduleStateResponse(
        id=None,
        company_id=None,
        schedule_date=schedule_date.isoformat(),
        state="not_created",
        finalized_at=None,
        finalized_by_user_id=None,
        auto_finalized=False,
        last_reverted_at=None,
        last_revert_reason=None,
        created_at=None,
        updated_at=None,
    )


# ── Schedule state read ────────────────────────────────────────────────
#
# ROUTE ORDERING NOTE: `/schedule/range` MUST be declared BEFORE
# `/schedule/{schedule_date}` or FastAPI's router would try to parse
# "range" as a date and 422. Declaring specifics before param captures
# is the pattern used elsewhere in the codebase (spaces/affinity
# routes, briefings/v2/latest, etc).


@router.get(
    "/schedule/range",
    response_model=ScheduleRangeResponse,
    dependencies=[Depends(require_permission("delivery.view"))],
)
def get_schedule_range(
    start: date = Query(..., description="Inclusive start date"),
    end: date = Query(..., description="Inclusive end date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleRangeResponse:
    """Read schedules for a date range — the Monitor's primary read
    path. Cap: 31 days (one calendar month) to bound query cost."""
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end must be >= start",
        )
    if (end - start).days > 31:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Range capped at 31 days",
        )
    rows = schedule_service.get_schedules_for_range(
        db, current_user.company_id, start, end
    )
    return ScheduleRangeResponse(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        schedules=[_schedule_to_response(r) for r in rows],
    )


@router.get(
    "/schedule/{schedule_date}",
    response_model=ScheduleStateResponse,
    dependencies=[Depends(require_permission("delivery.view"))],
)
def get_schedule(
    schedule_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleStateResponse:
    """Read the schedule state for one date. Lazy — returns state=
    `not_created` if no row exists (nobody's touched this date yet)."""
    row = schedule_service.get_schedule_state(
        db, current_user.company_id, schedule_date
    )
    if row is None:
        return _placeholder_response(schedule_date)
    return _schedule_to_response(row)


# ── Schedule state mutations ───────────────────────────────────────────


@router.post(
    "/schedule/{schedule_date}/ensure",
    response_model=ScheduleStateResponse,
    dependencies=[Depends(require_permission("delivery.view"))],
)
def ensure_schedule_endpoint(
    schedule_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleStateResponse:
    """Lazy-create the schedule row in draft state if it doesn't
    exist. Idempotent — returns existing row unchanged if present.
    Used by the frontend when the dispatcher opens a day for edit
    and needs a row to hang state transitions on."""
    row = schedule_service.ensure_schedule(
        db, current_user.company_id, schedule_date
    )
    return _schedule_to_response(row)


@router.post(
    "/schedule/{schedule_date}/finalize",
    response_model=ScheduleStateResponse,
    dependencies=[Depends(require_permission("delivery.finalize_schedule"))],
)
def finalize_schedule_endpoint(
    schedule_date: date,
    body: FinalizeRequest | None = None,  # noqa: ARG001 — reserved for future
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleStateResponse:
    """Explicit finalize. Stamps `finalized_at` + `finalized_by_
    user_id` from the auth context + `auto_finalized=False`."""
    row = schedule_service.finalize_schedule(
        db,
        current_user.company_id,
        schedule_date,
        user_id=current_user.id,
        auto=False,
    )
    return _schedule_to_response(row)


@router.post(
    "/schedule/{schedule_date}/revert",
    response_model=ScheduleStateResponse,
    dependencies=[Depends(require_permission("delivery.finalize_schedule"))],
)
def revert_schedule_endpoint(
    schedule_date: date,
    body: RevertRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScheduleStateResponse:
    """Explicit revert to draft. Stamps `last_reverted_at` +
    `last_revert_reason`. Returns a `not_created` response if no
    row exists (nothing to revert).

    Note: the auto-revert on delivery-edit is wired in
    `delivery_service.update_delivery` — this endpoint exists for
    dispatcher-initiated reverts (e.g. "I finalized early, let me
    fix something and refinalize").
    """
    reason = body.reason if body else None
    row = schedule_service.revert_to_draft(
        db, current_user.company_id, schedule_date, reason=reason
    )
    if row is None:
        return _placeholder_response(schedule_date)
    return _schedule_to_response(row)


# ── Hole-dug quick-edit ────────────────────────────────────────────────


@router.patch(
    "/delivery/{delivery_id}/hole-dug",
    response_model=HoleDugResponse,
    dependencies=[Depends(require_permission("delivery.edit_hole_dug"))],
)
def update_hole_dug_status(
    delivery_id: str,
    body: HoleDugRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HoleDugResponse:
    """Quick-edit hole-dug status from the Monitor card. If the
    delivery's requested_date is on a finalized schedule, the edit
    triggers a revert (handled inside the service)."""
    delivery = (
        db.query(Delivery)
        .filter(
            Delivery.id == delivery_id,
            Delivery.company_id == current_user.company_id,
        )
        .first()
    )
    if delivery is None:
        # Existence-hiding — cross-tenant + not-found both return 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Delivery not found")

    # Capture schedule state BEFORE the service call so we can report
    # "did this edit revert the schedule?" accurately in the response.
    reverted = False
    if delivery.requested_date is not None:
        pre_state = schedule_service.get_schedule_state(
            db, delivery.company_id, delivery.requested_date
        )
        if pre_state is not None and pre_state.state == "finalized":
            reverted = True

    schedule_service.set_hole_dug_status(
        db, delivery, body.status, revert_schedule=True
    )

    return HoleDugResponse(
        delivery_id=delivery.id,
        hole_dug_status=delivery.hole_dug_status,
        schedule_reverted=reverted,
        schedule_date=(
            delivery.requested_date.isoformat()
            if delivery.requested_date else None
        ),
    )


# ── Monitor-purpose delivery + driver reads ──────────────────────────
#
# Added alongside the state-machine endpoints because the legacy
# `/delivery/deliveries` list endpoint's DeliveryListItem shape
# doesn't carry `type_config` or `hole_dug_status`, and the Monitor
# card needs both. Purpose-built response keeps the dispatch router
# self-contained + leaves the existing /delivery surface untouched.


class MonitorDeliveryDTO(BaseModel):
    """Delivery shape for the Monitor card. Carries the display
    fields from `type_config` + the scheduling + quick-edit state
    the card renders."""
    id: str
    order_id: str | None = None
    customer_id: str | None = None
    delivery_type: str
    status: str
    priority: str
    requested_date: str | None = None
    scheduled_at: str | None = None
    scheduling_type: str | None = None
    ancillary_fulfillment_status: str | None = None
    direct_ship_status: str | None = None
    assigned_driver_id: str | None = None
    hole_dug_status: str | None = None
    type_config: dict[str, Any] | None = None
    special_instructions: str | None = None


class MonitorDriverDTO(BaseModel):
    """Driver shape for the Monitor lanes + quick-edit assign picker."""
    id: str
    license_number: str | None = None
    license_class: str | None = None
    active: bool
    display_name: str | None = None


@router.get(
    "/deliveries",
    response_model=list[MonitorDeliveryDTO],
    dependencies=[Depends(require_permission("delivery.view"))],
)
def list_monitor_deliveries(
    start: date = Query(..., description="Inclusive start date"),
    end: date = Query(..., description="Inclusive end date"),
    scheduling_type: Literal["kanban", "ancillary", "direct_ship"] | None = Query(
        None,
        description="Filter by scheduling_type. Null = all three.",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MonitorDeliveryDTO]:
    """Monitor delivery read. Returns deliveries within the date range
    with full display context. Date range capped at 31 days.

    Tenant-scoped via current_user.company_id. No cross-tenant leakage
    possible — the filter is unconditional.
    """
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end must be >= start",
        )
    if (end - start).days > 31:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Range capped at 31 days",
        )

    q = db.query(Delivery).filter(
        Delivery.company_id == current_user.company_id,
        Delivery.requested_date >= start,
        Delivery.requested_date <= end,
    )
    if scheduling_type is not None:
        q = q.filter(Delivery.scheduling_type == scheduling_type)

    rows = q.order_by(
        Delivery.requested_date.asc(),
        Delivery.scheduled_at.asc().nulls_last(),
    ).all()

    return [
        MonitorDeliveryDTO(
            id=r.id,
            order_id=r.order_id,
            customer_id=r.customer_id,
            delivery_type=r.delivery_type,
            status=r.status,
            priority=r.priority,
            requested_date=r.requested_date.isoformat() if r.requested_date else None,
            scheduled_at=r.scheduled_at.isoformat() if r.scheduled_at else None,
            scheduling_type=r.scheduling_type,
            ancillary_fulfillment_status=r.ancillary_fulfillment_status,
            direct_ship_status=r.direct_ship_status,
            assigned_driver_id=r.assigned_driver_id,
            hole_dug_status=r.hole_dug_status,
            type_config=r.type_config,
            special_instructions=r.special_instructions,
        )
        for r in rows
    ]


@router.get(
    "/drivers",
    response_model=list[MonitorDriverDTO],
    dependencies=[Depends(require_permission("delivery.view"))],
)
def list_monitor_drivers(
    active_only: bool = Query(True, description="Hide inactive drivers"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MonitorDriverDTO]:
    """Driver roster for Monitor lanes + quick-edit picker. Resolves
    display_name from either employee_id → users OR portal_user_id →
    portal_users (matching the Phase 8e.2 dual-identity pattern).
    """
    q = db.query(Driver).filter(Driver.company_id == current_user.company_id)
    if active_only:
        q = q.filter(Driver.active.is_(True))
    drivers = q.all()

    # Name resolution — two-lookup pattern for dual identity.
    out: list[MonitorDriverDTO] = []
    from app.models.user import User as _User

    for d in drivers:
        display_name = None
        if d.employee_id:
            emp = db.query(_User).filter(_User.id == d.employee_id).first()
            if emp:
                display_name = (
                    f"{emp.first_name or ''} {emp.last_name or ''}".strip() or None
                )
        if display_name is None and d.portal_user_id:
            # PortalUser is the new identity path (Phase 8e.2). Attempt
            # to resolve; fall through gracefully if unavailable.
            try:
                from app.models.portal_user import PortalUser  # noqa
                pu = db.query(PortalUser).filter(
                    PortalUser.id == d.portal_user_id
                ).first()
                if pu:
                    display_name = (
                        f"{pu.first_name or ''} {pu.last_name or ''}".strip() or None
                    )
            except Exception:
                pass

        out.append(MonitorDriverDTO(
            id=d.id,
            license_number=d.license_number,
            license_class=d.license_class,
            active=d.active,
            display_name=display_name,
        ))

    return out
