"""Tasks API — Phase 5.

Six endpoints under `/api/v1/tasks/*`. Tenant-scoped via
`get_current_user`. Soft-delete via is_active=false (NOT physical
delete) — matches the codebase convention.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.task import Task
from app.models.user import User
from app.services.task_service import (
    InvalidInput,
    InvalidTransition,
    TaskError,
    TaskNotFound,
    cancel_task,
    complete_task,
    create_task,
    get_task,
    list_tasks,
    soft_delete_task,
    update_task,
)

router = APIRouter()


# ── Pydantic shapes ──────────────────────────────────────────────────


class _TaskResponse(BaseModel):
    id: str
    company_id: str
    title: str
    description: str | None
    assignee_user_id: str | None
    created_by_user_id: str | None
    priority: Literal["low", "normal", "high", "urgent"]
    due_date: date | None
    due_datetime: datetime | None
    status: Literal["open", "in_progress", "blocked", "done", "cancelled"]
    completed_at: datetime | None
    related_entity_type: str | None
    related_entity_id: str | None
    metadata_json: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class _CreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    assignee_user_id: str | None = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_date: date | None = None
    due_datetime: datetime | None = None
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    metadata_json: dict[str, Any] | None = None


class _UpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    assignee_user_id: str | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    due_date: date | None = None
    due_datetime: datetime | None = None
    status: Literal["open", "in_progress", "blocked", "done", "cancelled"] | None = None
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    metadata_json: dict[str, Any] | None = None


# ── Helpers ──────────────────────────────────────────────────────────


def _to_response(t: Task) -> _TaskResponse:
    return _TaskResponse(
        id=t.id,
        company_id=t.company_id,
        title=t.title,
        description=t.description,
        assignee_user_id=t.assignee_user_id,
        created_by_user_id=t.created_by_user_id,
        priority=t.priority,  # type: ignore[arg-type]
        due_date=t.due_date,
        due_datetime=t.due_datetime,
        status=t.status,  # type: ignore[arg-type]
        completed_at=t.completed_at,
        related_entity_type=t.related_entity_type,
        related_entity_id=t.related_entity_id,
        metadata_json=t.metadata_json or {},
        is_active=t.is_active,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _translate(exc: TaskError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=str(exc))


# ── Routes ───────────────────────────────────────────────────────────


@router.get("", response_model=list[_TaskResponse])
def list_endpoint(
    status: str | None = Query(default=None),
    assignee_user_id: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    due_before: date | None = Query(default=None),
    due_after: date | None = Query(default=None),
    related_entity_type: str | None = Query(default=None),
    related_entity_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[_TaskResponse]:
    """List tasks with optional filters. Sorted by priority → due
    date → created_at."""
    tasks = list_tasks(
        db,
        company_id=current_user.company_id,
        status=status,
        assignee_user_id=assignee_user_id,
        priority=priority,
        due_before=due_before,
        due_after=due_after,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        limit=limit,
    )
    return [_to_response(t) for t in tasks]


@router.post("", response_model=_TaskResponse, status_code=201)
def create_endpoint(
    body: _CreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _TaskResponse:
    try:
        t = create_task(
            db,
            company_id=current_user.company_id,
            title=body.title,
            created_by_user_id=current_user.id,
            description=body.description,
            assignee_user_id=body.assignee_user_id,
            priority=body.priority,
            due_date=body.due_date,
            due_datetime=body.due_datetime,
            related_entity_type=body.related_entity_type,
            related_entity_id=body.related_entity_id,
            metadata_json=body.metadata_json,
        )
    except TaskError as exc:
        raise _translate(exc) from exc
    return _to_response(t)


@router.get("/{task_id}", response_model=_TaskResponse)
def get_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _TaskResponse:
    try:
        t = get_task(db, company_id=current_user.company_id, task_id=task_id)
    except TaskError as exc:
        raise _translate(exc) from exc
    return _to_response(t)


@router.patch("/{task_id}", response_model=_TaskResponse)
def update_endpoint(
    task_id: str,
    body: _UpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _TaskResponse:
    try:
        t = update_task(
            db,
            company_id=current_user.company_id,
            task_id=task_id,
            **body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except InvalidTransition as exc:
        # Surface transition rule violations as 409 (conflict with
        # current state) rather than a generic 400.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidInput as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TaskError as exc:
        raise _translate(exc) from exc
    return _to_response(t)


@router.delete("/{task_id}")
def delete_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Soft-delete (sets is_active=False). 200 with body, matching
    saved_views + spaces deletion convention."""
    try:
        soft_delete_task(
            db, company_id=current_user.company_id, task_id=task_id
        )
    except TaskError as exc:
        raise _translate(exc) from exc
    return {"status": "deleted", "id": task_id}


@router.post("/{task_id}/complete", response_model=_TaskResponse)
def complete_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _TaskResponse:
    try:
        t = complete_task(
            db, company_id=current_user.company_id, task_id=task_id
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskError as exc:
        raise _translate(exc) from exc
    return _to_response(t)


# Not used by the spec but matches FH approval conventions elsewhere —
# exposed for symmetry with /complete.
@router.post("/{task_id}/cancel", response_model=_TaskResponse)
def cancel_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _TaskResponse:
    try:
        t = cancel_task(
            db, company_id=current_user.company_id, task_id=task_id
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskError as exc:
        raise _translate(exc) from exc
    return _to_response(t)
