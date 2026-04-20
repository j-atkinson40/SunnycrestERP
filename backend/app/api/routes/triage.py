"""Triage API — Phase 5.

Nine endpoints under `/api/v1/triage/*`. All user-scoped via
`get_current_user`. Session state in `triage_sessions`; queue
configs loaded from vault items via `triage.registry`.

Response shapes are thin Pydantic mirrors of the
`TriageQueueConfig` + summary types in
`app.services.triage.types`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.triage import (
    NoPendingItems,
    TriageError,
    apply_action,
    end_session,
    get_config,
    get_session,
    list_queues_for_user,
    next_item,
    queue_count,
    snooze_item,
    start_session,
)

router = APIRouter()


# ── Pydantic shapes ──────────────────────────────────────────────────


class _QueueSummary(BaseModel):
    queue_id: str
    queue_name: str
    description: str
    item_entity_type: str
    display_order: int
    schema_version: str


class _QueueConfigResponse(BaseModel):
    """Full config returned by GET /queues/{id}. Uses dict payload
    (not nested typed models) for API compactness — frontend
    validates via TypeScript types locally."""

    queue_id: str
    queue_name: str
    config: dict[str, Any]  # TriageQueueConfig.to_dict()


class _ItemResponse(BaseModel):
    entity_type: str
    entity_id: str
    title: str
    subtitle: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class _SessionResponse(BaseModel):
    session_id: str
    queue_id: str
    user_id: str
    started_at: datetime
    ended_at: datetime | None = None
    items_processed_count: int
    items_approved_count: int
    items_rejected_count: int
    items_snoozed_count: int
    current_item_id: str | None = None


class _ApplyActionRequest(BaseModel):
    action_id: str
    reason: str | None = None
    reason_code: str | None = None
    note: str | None = None
    payload: dict[str, Any] | None = None


class _ApplyActionResponse(BaseModel):
    status: Literal["applied", "skipped", "errored"]
    message: str
    next_item_id: str | None = None
    audit_log_id: str | None = None
    playwright_log_id: str | None = None
    workflow_run_id: str | None = None


class _SnoozeRequest(BaseModel):
    # Either an ISO datetime or an offset-hours shorthand.
    wake_at: datetime | None = None
    offset_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    reason: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────


def _translate(exc: TriageError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=str(exc))


def _session_to_response(session) -> _SessionResponse:
    return _SessionResponse(
        session_id=session.id,
        queue_id=session.queue_id,
        user_id=session.user_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        items_processed_count=session.items_processed_count,
        items_approved_count=session.items_approved_count,
        items_rejected_count=session.items_rejected_count,
        items_snoozed_count=session.items_snoozed_count,
        current_item_id=session.current_item_id,
    )


# ── Routes ───────────────────────────────────────────────────────────


@router.get("/queues", response_model=list[_QueueSummary])
def list_queues_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[_QueueSummary]:
    """Queues visible to the current user."""
    configs = list_queues_for_user(db, user=current_user)
    return [
        _QueueSummary(
            queue_id=c.queue_id,
            queue_name=c.queue_name,
            description=c.description,
            item_entity_type=c.item_entity_type,
            display_order=c.display_order,
            schema_version=c.schema_version,
        )
        for c in configs
    ]


@router.get("/queues/{queue_id}", response_model=_QueueConfigResponse)
def get_queue_endpoint(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _QueueConfigResponse:
    try:
        config = get_config(
            db, company_id=current_user.company_id, queue_id=queue_id
        )
    except TriageError as exc:
        raise _translate(exc) from exc
    return _QueueConfigResponse(
        queue_id=config.queue_id,
        queue_name=config.queue_name,
        config=config.to_dict(),
    )


@router.get("/queues/{queue_id}/count", response_model=dict)
def queue_count_endpoint(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Pending item count — used by briefings (Phase 6) + sidebar badges."""
    try:
        count = queue_count(
            db, user=current_user, queue_id=queue_id
        )
    except TriageError as exc:
        raise _translate(exc) from exc
    return {"queue_id": queue_id, "count": count}


@router.post(
    "/queues/{queue_id}/sessions",
    response_model=_SessionResponse,
    status_code=201,
)
def start_session_endpoint(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SessionResponse:
    try:
        session = start_session(db, user=current_user, queue_id=queue_id)
    except TriageError as exc:
        raise _translate(exc) from exc
    return _session_to_response(session)


@router.get("/sessions/{session_id}", response_model=_SessionResponse)
def get_session_endpoint(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SessionResponse:
    try:
        session = get_session(db, session_id=session_id, user=current_user)
    except TriageError as exc:
        raise _translate(exc) from exc
    return _session_to_response(session)


@router.post("/sessions/{session_id}/next", response_model=_ItemResponse)
def next_item_endpoint(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _ItemResponse:
    import time as _t_time
    from app.services import arc_telemetry as _arc_t
    _t0 = _t_time.perf_counter()
    _errored = False
    try:
        item = next_item(
            db, session_id=session_id, user=current_user
        )
    except NoPendingItems:
        raise HTTPException(status_code=204, detail="No pending items")
    except TriageError as exc:
        _errored = True
        raise _translate(exc) from exc
    finally:
        _arc_t.record(
            "triage_next_item",
            (_t_time.perf_counter() - _t0) * 1000.0,
            errored=_errored,
        )
    return _ItemResponse(
        entity_type=item.entity_type,
        entity_id=item.entity_id,
        title=item.title,
        subtitle=item.subtitle,
        extras=item.extras,
    )


@router.post(
    "/sessions/{session_id}/items/{item_id}/action",
    response_model=_ApplyActionResponse,
)
def apply_action_endpoint(
    session_id: str,
    item_id: str,
    body: _ApplyActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _ApplyActionResponse:
    import time as _t_time
    from app.services import arc_telemetry as _arc_t
    _t0 = _t_time.perf_counter()
    _errored = False
    try:
        result = apply_action(
            db,
            session_id=session_id,
            item_id=item_id,
            action_id=body.action_id,
            user=current_user,
            reason=body.reason,
            reason_code=body.reason_code,
            note=body.note,
            payload=body.payload,
        )
    except TriageError as exc:
        _errored = True
        raise _translate(exc) from exc
    finally:
        _arc_t.record(
            "triage_apply_action",
            (_t_time.perf_counter() - _t0) * 1000.0,
            errored=_errored,
        )
    return _ApplyActionResponse(
        status=result.status,
        message=result.message,
        next_item_id=result.next_item_id,
        audit_log_id=result.audit_log_id,
        playwright_log_id=result.playwright_log_id,
        workflow_run_id=result.workflow_run_id,
    )


@router.post(
    "/sessions/{session_id}/items/{item_id}/snooze",
    response_model=_ApplyActionResponse,
)
def snooze_endpoint(
    session_id: str,
    item_id: str,
    body: _SnoozeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _ApplyActionResponse:
    if body.wake_at is None and body.offset_hours is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either wake_at (ISO datetime) or offset_hours.",
        )
    wake_at = body.wake_at or (
        datetime.now(timezone.utc) + timedelta(hours=body.offset_hours or 24)
    )
    try:
        result = snooze_item(
            db,
            session_id=session_id,
            item_id=item_id,
            user=current_user,
            wake_at=wake_at,
            reason=body.reason,
        )
    except TriageError as exc:
        raise _translate(exc) from exc
    return _ApplyActionResponse(
        status=result.status,
        message=result.message,
        next_item_id=result.next_item_id,
    )


@router.post("/sessions/{session_id}/end", response_model=_SessionResponse)
def end_session_endpoint(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SessionResponse:
    try:
        summary = end_session(
            db, session_id=session_id, user=current_user
        )
    except TriageError as exc:
        raise _translate(exc) from exc
    return _SessionResponse(
        session_id=summary.session_id,
        queue_id=summary.queue_id,
        user_id=summary.user_id,
        started_at=summary.started_at,
        ended_at=summary.ended_at,
        items_processed_count=summary.items_processed_count,
        items_approved_count=summary.items_approved_count,
        items_rejected_count=summary.items_rejected_count,
        items_snoozed_count=summary.items_snoozed_count,
        current_item_id=summary.current_item_id,
    )
