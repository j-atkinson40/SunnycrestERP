"""Task service — CRUD + lifecycle transitions.

Owner of the Task entity. Keeps business rules (status transitions,
assignee validation, soft-delete semantics) out of the API route.

Status transitions allowed:
    open          → in_progress | blocked | done | cancelled
    in_progress   → blocked | done | cancelled
    blocked       → in_progress | cancelled
    done          → (terminal; cannot unwind without admin intent)
    cancelled     → (terminal)

`complete(task)` is a convenience for `status=done, completed_at=now`.

Tenant isolation is the caller's responsibility — routes scope by
`current_user.company_id`; services trust the caller.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query, Session

from app.models.task import TASK_PRIORITIES, TASK_STATUSES, Task


class TaskError(Exception):
    http_status = 400


class TaskNotFound(TaskError):
    http_status = 404


class InvalidTransition(TaskError):
    http_status = 400


class InvalidInput(TaskError):
    http_status = 400


# ── Transition rules ────────────────────────────────────────────────

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "blocked", "done", "cancelled"},
    "in_progress": {"blocked", "done", "cancelled", "open"},
    "blocked": {"in_progress", "cancelled", "open"},
    "done": set(),        # terminal
    "cancelled": set(),   # terminal
}


# ── Queries ─────────────────────────────────────────────────────────


def list_tasks(
    db: Session,
    *,
    company_id: str,
    status: str | None = None,
    assignee_user_id: str | None = None,
    priority: str | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    include_inactive: bool = False,
    limit: int = 100,
) -> list[Task]:
    q: Query[Task] = db.query(Task).filter(Task.company_id == company_id)
    if not include_inactive:
        q = q.filter(Task.is_active.is_(True))
    if status is not None:
        q = q.filter(Task.status == status)
    if assignee_user_id is not None:
        q = q.filter(Task.assignee_user_id == assignee_user_id)
    if priority is not None:
        q = q.filter(Task.priority == priority)
    if due_before is not None:
        q = q.filter(
            or_(Task.due_date <= due_before, Task.due_datetime <= datetime.combine(due_before, datetime.min.time(), tzinfo=timezone.utc))
        )
    if due_after is not None:
        q = q.filter(
            or_(Task.due_date >= due_after, Task.due_datetime >= datetime.combine(due_after, datetime.min.time(), tzinfo=timezone.utc))
        )
    if related_entity_type is not None and related_entity_id is not None:
        q = q.filter(
            and_(
                Task.related_entity_type == related_entity_type,
                Task.related_entity_id == related_entity_id,
            )
        )
    # Priority sort: urgent > high > normal > low
    priority_rank = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    tasks = q.all()
    tasks.sort(
        key=lambda t: (
            priority_rank.get(t.priority, 4),
            t.due_date or date.max,
            t.created_at or datetime.max.replace(tzinfo=timezone.utc),
        )
    )
    return tasks[:limit]


def get_task(db: Session, *, company_id: str, task_id: str) -> Task:
    task = (
        db.query(Task)
        .filter(Task.company_id == company_id, Task.id == task_id)
        .first()
    )
    if task is None:
        raise TaskNotFound(f"Task {task_id} not found")
    return task


# ── Mutations ───────────────────────────────────────────────────────


def create_task(
    db: Session,
    *,
    company_id: str,
    title: str,
    created_by_user_id: str | None,
    description: str | None = None,
    assignee_user_id: str | None = None,
    priority: str = "normal",
    due_date: date | None = None,
    due_datetime: datetime | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> Task:
    _validate_priority(priority)
    title = (title or "").strip()
    if not title:
        raise InvalidInput("title is required")
    task = Task(
        id=str(uuid.uuid4()),
        company_id=company_id,
        title=title,
        description=description,
        assignee_user_id=assignee_user_id,
        created_by_user_id=created_by_user_id,
        priority=priority,
        due_date=due_date,
        due_datetime=due_datetime,
        status="open",
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        metadata_json=dict(metadata_json or {}),
        is_active=True,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    *,
    company_id: str,
    task_id: str,
    **patch: Any,
) -> Task:
    task = get_task(db, company_id=company_id, task_id=task_id)
    allowed_fields = {
        "title",
        "description",
        "assignee_user_id",
        "priority",
        "due_date",
        "due_datetime",
        "status",
        "related_entity_type",
        "related_entity_id",
        "metadata_json",
    }
    for k, v in patch.items():
        if k not in allowed_fields or v is None:
            continue
        if k == "priority":
            _validate_priority(v)
        if k == "status":
            _validate_status_transition(task.status, v)
            if v == "done" and task.completed_at is None:
                task.completed_at = datetime.now(timezone.utc)
        setattr(task, k, v)
    db.commit()
    db.refresh(task)
    return task


def complete_task(
    db: Session, *, company_id: str, task_id: str
) -> Task:
    return update_task(
        db,
        company_id=company_id,
        task_id=task_id,
        status="done",
    )


def cancel_task(
    db: Session, *, company_id: str, task_id: str
) -> Task:
    return update_task(
        db,
        company_id=company_id,
        task_id=task_id,
        status="cancelled",
    )


def soft_delete_task(
    db: Session, *, company_id: str, task_id: str
) -> None:
    task = get_task(db, company_id=company_id, task_id=task_id)
    task.is_active = False
    db.commit()


# ── Validators ──────────────────────────────────────────────────────


def _validate_priority(priority: str) -> None:
    if priority not in TASK_PRIORITIES:
        raise InvalidInput(
            f"priority must be one of {TASK_PRIORITIES}, got {priority!r}"
        )


def _validate_status_transition(current: str, target: str) -> None:
    if target not in TASK_STATUSES:
        raise InvalidInput(
            f"status must be one of {TASK_STATUSES}, got {target!r}"
        )
    if current == target:
        return  # idempotent — no transition
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransition(
            f"Cannot transition task from {current!r} to {target!r}"
        )


__all__ = [
    "list_tasks",
    "get_task",
    "create_task",
    "update_task",
    "complete_task",
    "cancel_task",
    "soft_delete_task",
    "TaskError",
    "TaskNotFound",
    "InvalidTransition",
    "InvalidInput",
]
