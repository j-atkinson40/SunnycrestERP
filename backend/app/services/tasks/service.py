"""Task substrate v1 — service layer + Task façade.

Per build prompt §5.6 + operator additional directive:

- `create_task_with_provenance` — atomic transaction creating both
  VaultItem (item_type='task') + task_details rows in single flush
  cycle. Either both rows or neither — prevents half-created tasks.
- `transition_task` — composes lifecycle.apply_transition + invokes
  on_status_change hooks on registered TaskTypeBehavior.
- Task façade — service-layer abstraction that lets 8 existing Task
  consumers continue working unchanged. v1.0 preserves the existing
  `Task` model + `task_service.py` API; this module is additive.

Operator Lock 1 (Shape A): existing `tasks` table stays as-is. v1.0
adds VaultItem + task_details *alongside* on the `create_task_with_provenance`
path. The legacy `task_service.create_task` keeps writing to the `tasks`
table unchanged (v1.0 is purely additive per phasing §1.8).

The dual-write bridge (legacy Task + new VaultItem/task_details) is
optional in v1.0 and explicitly NOT applied to existing `task_service.create_task`
to preserve the zero-existing-surface-behavior-change invariant. The
backfill script handles legacy task rows. v1.5 (c) refactor flips the
8 producer sites onto `create_task_with_provenance`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import (
    ACTION_STATES,
    LIFECYCLE_SHAPES,
    PROVENANCE_KINDS,
    REMINDER_STATES,
    TASK_DETAILS_PRIORITIES,
    VISIBILITY_VALUES,
    TaskDetails,
)
from app.models.vault_item import VaultItem
from app.services.tasks import lifecycle as lifecycle_mod
from app.services.tasks.plugins.type_behaviors import (
    get_task_type_behavior,
)
from app.services.tasks.subscribers.registry import emit_event
from app.services.vault_service import get_or_create_company_vault


logger = logging.getLogger(__name__)


# ── Errors ──────────────────────────────────────────────────────────


class TaskServiceError(Exception):
    http_status = 400


class DuplicateTaskError(TaskServiceError):
    """Composite-idempotency-key uniqueness violation."""
    http_status = 409


class InvalidTaskInput(TaskServiceError):
    http_status = 400


# ── Validation helpers ──────────────────────────────────────────────


def _validate_creation_inputs(
    *,
    provenance_kind: str,
    task_type_key: str,
    lifecycle_shape: str,
    visibility: str,
    priority: str,
) -> None:
    if provenance_kind not in PROVENANCE_KINDS:
        raise InvalidTaskInput(
            f"provenance_kind must be one of {PROVENANCE_KINDS}, "
            f"got {provenance_kind!r}"
        )
    if lifecycle_shape not in LIFECYCLE_SHAPES:
        raise InvalidTaskInput(
            f"lifecycle_shape must be one of {LIFECYCLE_SHAPES}, "
            f"got {lifecycle_shape!r}"
        )
    if visibility not in VISIBILITY_VALUES:
        raise InvalidTaskInput(
            f"visibility must be one of {VISIBILITY_VALUES}, "
            f"got {visibility!r}"
        )
    if priority not in TASK_DETAILS_PRIORITIES:
        raise InvalidTaskInput(
            f"priority must be one of {TASK_DETAILS_PRIORITIES}, "
            f"got {priority!r}"
        )
    # task_type_key is plugin-registered; we don't reject unknown values
    # because callers may register their own at runtime. Behavior plugin
    # is looked up lazily in this path; a missing plugin uses sensible
    # generic defaults.


def _default_state_for_shape(lifecycle_shape: str) -> str:
    if lifecycle_shape == "action":
        return "created"
    return "informational"


def _idempotency_lookup(
    db: Session,
    *,
    provenance_kind: str,
    provenance_ref_type: str | None,
    provenance_ref_id: str | None,
    event_kind: str,
) -> TaskDetails | None:
    """Returns existing task_details row matching the composite key, or None.

    Honors partial-unique semantics: lookup only fires when
    provenance_ref_id IS NOT NULL.
    """
    if provenance_ref_id is None:
        return None
    return (
        db.query(TaskDetails)
        .filter(
            TaskDetails.provenance_kind == provenance_kind,
            TaskDetails.provenance_ref_type == provenance_ref_type,
            TaskDetails.provenance_ref_id == provenance_ref_id,
            TaskDetails.event_kind == event_kind,
        )
        .first()
    )


# ── Creation (atomic) ───────────────────────────────────────────────


def create_task_with_provenance(
    db: Session,
    *,
    company_id: str,
    provenance_kind: str,
    provenance_ref_type: str | None,
    provenance_ref_id: str | None,
    event_kind: str,
    task_type_key: str,
    title: str,
    description: str | None = None,
    created_by_user_id: str | None = None,
    assignee_user_id: str | None = None,
    assignee_realm: str = "user",
    priority: str | None = None,
    due_date: date | None = None,
    due_datetime: datetime | None = None,
    lifecycle_shape: str | None = None,
    visibility: str | None = None,
    suppression_key: str | None = None,
    metadata: dict[str, Any] | None = None,
    raise_on_duplicate: bool = False,
) -> TaskDetails:
    """Create VaultItem + task_details atomically + emit task_created.

    Atomic: VaultItem + task_details are added to the session in a single
    flush cycle (operator additional directive — both rows or neither).
    Caller is responsible for the surrounding transaction's commit; if
    commit fails, both rows revert together.

    Idempotency: if a task_details row already exists with the same
    composite key (provenance_kind, provenance_ref_type, provenance_ref_id,
    event_kind), the existing row is returned (raise_on_duplicate=False)
    or DuplicateTaskError is raised (raise_on_duplicate=True). The DB-level
    partial-unique index provides a secondary safety net.

    Returns the created (or existing-on-duplicate) TaskDetails row.
    """
    title = (title or "").strip()
    if not title:
        raise InvalidTaskInput("title is required")

    # Resolve defaults from task type behavior plugin if available.
    behavior = get_task_type_behavior(task_type_key)
    if lifecycle_shape is None:
        lifecycle_shape = (
            behavior.default_lifecycle_shape if behavior else "action"
        )
    if priority is None:
        priority = behavior.default_priority if behavior else "normal"
    if visibility is None:
        visibility = (
            behavior.default_visibility if behavior else "operator_internal"
        )

    _validate_creation_inputs(
        provenance_kind=provenance_kind,
        task_type_key=task_type_key,
        lifecycle_shape=lifecycle_shape,
        visibility=visibility,
        priority=priority,
    )

    # Idempotency precheck (subscriber-layer guard; DB partial unique is
    # the canonical safety net).
    existing = _idempotency_lookup(
        db,
        provenance_kind=provenance_kind,
        provenance_ref_type=provenance_ref_type,
        provenance_ref_id=provenance_ref_id,
        event_kind=event_kind,
    )
    if existing is not None:
        if raise_on_duplicate:
            raise DuplicateTaskError(
                f"Task already exists for composite key "
                f"({provenance_kind}, {provenance_ref_type}, "
                f"{provenance_ref_id}, {event_kind})"
            )
        return existing

    # Determine initial state.
    initial_state = _default_state_for_shape(lifecycle_shape)
    if (
        lifecycle_shape == "action"
        and assignee_user_id is not None
        and initial_state == "created"
    ):
        initial_state = "assigned"

    # Materialize metadata payload for the VaultItem.
    metadata_payload: dict[str, Any] = dict(metadata or {})
    metadata_payload.setdefault("task_type_key", task_type_key)

    # Resolve the company vault (creates one if missing).
    vault = get_or_create_company_vault(db, company_id)

    # Atomic create: VaultItem + task_details in a single flush.
    now = datetime.now(timezone.utc)
    vi = VaultItem(
        id=str(uuid.uuid4()),
        vault_id=vault.id,
        company_id=company_id,
        item_type="task",
        title=title,
        description=description,
        visibility="internal",
        status="active",
        source="system_generated",
        source_entity_id=(provenance_ref_id or None),
        created_by=created_by_user_id,
        created_at=now,
        updated_at=now,
        is_active=True,
        metadata_json=metadata_payload,
    )
    td = TaskDetails(
        id=str(uuid.uuid4()),
        vault_item_id=vi.id,
        assignee_realm=assignee_realm,
        assignee_user_id=assignee_user_id,
        lifecycle_shape=lifecycle_shape,
        current_state=initial_state,
        provenance_kind=provenance_kind,
        provenance_ref_type=provenance_ref_type,
        provenance_ref_id=provenance_ref_id,
        event_kind=event_kind,
        visibility=visibility,
        priority=priority,
        due_date=due_date,
        due_datetime=due_datetime,
        assigned_at=now if assignee_user_id else None,
        suppression_key=suppression_key,
        created_at=now,
        updated_at=now,
    )

    db.add(vi)
    db.add(td)
    db.flush()  # Single flush — both rows or neither.

    # Run task-type on_created hook if behavior provides one
    # (scheduled_recurring_task uses this).
    if behavior is not None and hasattr(behavior, "on_created"):
        try:
            behavior.on_created(db, task_details_id=td.id)
        except Exception:
            logger.exception(
                "task_type on_created hook failed: type=%s td_id=%s",
                task_type_key, td.id,
            )

    # Emit task_created. Subscribers fire synchronously; idempotent
    # subscribers (audit_writer) handle correctness.
    emit_event(
        db,
        event_type="task_created",
        task_details_id=td.id,
        actor_user_id=created_by_user_id,
        payload={
            "company_id": company_id,
            "provenance_kind": provenance_kind,
            "provenance_ref_type": provenance_ref_type,
            "provenance_ref_id": provenance_ref_id,
            "event_kind": event_kind,
            "task_type_key": task_type_key,
            "lifecycle_shape": lifecycle_shape,
            "current_state": initial_state,
        },
    )

    # If task was created already-assigned (action shape with assignee),
    # also emit task_assigned.
    if lifecycle_shape == "action" and initial_state == "assigned":
        emit_event(
            db,
            event_type="task_assigned",
            task_details_id=td.id,
            actor_user_id=created_by_user_id,
            payload={
                "assignee_user_id": assignee_user_id,
                "task_type_key": task_type_key,
            },
        )

    return td


# ── Transition (with behavior hook) ─────────────────────────────────


def transition_task(
    db: Session,
    *,
    task_details_id: str,
    to_state: str,
    actor_user_id: str | None = None,
    resolution_outcome: str | None = None,
) -> TaskDetails:
    """Apply lifecycle transition + invoke type-behavior on_status_change.

    Composes lifecycle.apply_transition (state guard + event emission +
    audit write) with the per-task-type behavior hook. Caller commits.
    """
    td = (
        db.query(TaskDetails)
        .filter(TaskDetails.id == task_details_id)
        .first()
    )
    if td is None:
        raise lifecycle_mod.TaskDetailsNotFound(
            f"TaskDetails {task_details_id} not found"
        )

    from_state = td.current_state

    td = lifecycle_mod.apply_transition(
        db,
        task_details_id=task_details_id,
        to_state=to_state,
        actor_user_id=actor_user_id,
        resolution_outcome=resolution_outcome,
    )

    if from_state == to_state:
        return td  # idempotent no-op; no behavior hook

    # Behavior hook — look up task_type_key from the VaultItem metadata.
    vi = (
        db.query(VaultItem)
        .filter(VaultItem.id == td.vault_item_id)
        .first()
    )
    if vi is not None:
        meta = vi.metadata_json or {}
        task_type_key = meta.get("task_type_key")
        if task_type_key:
            behavior = get_task_type_behavior(task_type_key)
            if behavior is not None:
                try:
                    behavior.on_status_change(
                        db,
                        task_details_id=td.id,
                        from_state=from_state,
                        to_state=to_state,
                        actor_user_id=actor_user_id,
                    )
                except Exception:
                    logger.exception(
                        "task_type on_status_change hook failed: "
                        "type=%s td_id=%s",
                        task_type_key, td.id,
                    )

    return td


# ── Read paths ──────────────────────────────────────────────────────


def get_task_details(
    db: Session, *, task_details_id: str
) -> TaskDetails:
    td = (
        db.query(TaskDetails)
        .filter(TaskDetails.id == task_details_id)
        .first()
    )
    if td is None:
        raise lifecycle_mod.TaskDetailsNotFound(
            f"TaskDetails {task_details_id} not found"
        )
    return td


def get_task_details_for_vault_item(
    db: Session, *, vault_item_id: str
) -> TaskDetails | None:
    """Lookup task_details by VaultItem id (1:1 invariant)."""
    return (
        db.query(TaskDetails)
        .filter(TaskDetails.vault_item_id == vault_item_id)
        .first()
    )


def list_task_details_for_company(
    db: Session,
    *,
    company_id: str,
    assignee_user_id: str | None = None,
    current_state: str | None = None,
    lifecycle_shape: str | None = None,
    include_terminal: bool = False,
    limit: int = 100,
) -> list[TaskDetails]:
    """Façade-shaped query reading through VaultItem JOIN task_details.

    Operator directive: default query pattern is join-at-query-time.
    Visibility filter applied at operator level (default v1 read path).
    """
    q = (
        db.query(TaskDetails)
        .join(VaultItem, TaskDetails.vault_item_id == VaultItem.id)
        .filter(VaultItem.company_id == company_id)
        .filter(VaultItem.item_type == "task")
        .filter(VaultItem.is_active.is_(True))
        .filter(
            TaskDetails.visibility.in_(
                ("operator_internal", "operator_assigned")
            )
        )
    )
    if assignee_user_id is not None:
        q = q.filter(TaskDetails.assignee_user_id == assignee_user_id)
    if current_state is not None:
        q = q.filter(TaskDetails.current_state == current_state)
    if lifecycle_shape is not None:
        q = q.filter(TaskDetails.lifecycle_shape == lifecycle_shape)
    if not include_terminal:
        # Exclude terminal states per shape.
        terminal_action = ("done", "cancelled")
        terminal_reminder = ("acknowledged", "dismissed")
        q = q.filter(
            ~TaskDetails.current_state.in_(
                terminal_action + terminal_reminder
            )
        )
    q = q.order_by(TaskDetails.created_at.desc())
    return q.limit(limit).all()


__all__ = [
    "TaskServiceError",
    "DuplicateTaskError",
    "InvalidTaskInput",
    "create_task_with_provenance",
    "transition_task",
    "get_task_details",
    "get_task_details_for_vault_item",
    "list_task_details_for_company",
]
