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

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.delivery import Delivery
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
