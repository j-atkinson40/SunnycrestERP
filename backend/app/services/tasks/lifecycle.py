"""Task substrate v1 — dual lifecycle state machine.

Two lifecycle shapes per state doc §5.2 + build prompt §5.2:

**Action shape** — interactive tasks requiring operator work:
  created → assigned → in_progress ↔ blocked → done | cancelled

**Reminder shape** — informational tasks requiring acknowledgement only:
  informational → acknowledged | dismissed

Transition guards enforce legal state edges. Illegal transitions raise
`InvalidTransition`. Audit trail writes via existing AuditLog model.

Backward-compat mapping from existing `tasks.status` 5-state machine
(task.py:104-110) lives in `LEGACY_STATUS_MAP` — backfill applies this.

Subscriber registry emission per build prompt §5.2:
- every transition fires `task_status_changed`
- `created → assigned` additionally fires `task_assigned`
- `* → done` additionally fires `task_completed`
- `* → blocked` fires `task_blocked`
- `blocked → *` fires `task_unblocked`
- `* → cancelled` fires `task_cancelled`
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.task_details import (
    ACTION_STATES,
    LIFECYCLE_SHAPES,
    REMINDER_STATES,
    TaskDetails,
)


logger = logging.getLogger(__name__)


# ── Errors ──────────────────────────────────────────────────────────


class LifecycleError(Exception):
    """Base class for lifecycle errors."""
    http_status = 400


class InvalidTransition(LifecycleError):
    """Raised when transition is not in the per-shape transition map."""
    http_status = 400


class TaskDetailsNotFound(LifecycleError):
    http_status = 404


# ── Transition tables (frozen per state doc §5.2) ───────────────────


ACTION_TRANSITIONS: dict[str, set[str]] = {
    "created": {"assigned", "in_progress", "cancelled"},
    "assigned": {"in_progress", "blocked", "done", "cancelled"},
    "in_progress": {"blocked", "done", "cancelled"},
    "blocked": {"in_progress", "cancelled"},
    "done": set(),  # terminal
    "cancelled": set(),  # terminal
}

REMINDER_TRANSITIONS: dict[str, set[str]] = {
    "informational": {"acknowledged", "dismissed"},
    "acknowledged": set(),  # terminal
    "dismissed": set(),  # terminal
}


# Legacy 5-state backward-compat map (existing tasks.status → action shape).
# Backfill applies this. NOTE: "open" with NULL assignee maps to "created"
# instead of "assigned" — backfill handles the assignee-presence branch.
LEGACY_STATUS_MAP: dict[str, str] = {
    "open": "assigned",  # has assignee
    "in_progress": "in_progress",
    "blocked": "blocked",
    "done": "done",
    "cancelled": "cancelled",
}


def legacy_status_to_action_state(
    legacy_status: str, *, has_assignee: bool
) -> str:
    """Map legacy `tasks.status` value into action-shape state.

    `open` with no assignee → 'created'; otherwise per LEGACY_STATUS_MAP.
    """
    if legacy_status == "open" and not has_assignee:
        return "created"
    if legacy_status not in LEGACY_STATUS_MAP:
        # Defensive: unknown legacy status maps to 'created' as a safe
        # default for backfill. Logged warning is the surface.
        logger.warning(
            "legacy_status_to_action_state: unknown status %r, "
            "defaulting to 'created'",
            legacy_status,
        )
        return "created"
    return LEGACY_STATUS_MAP[legacy_status]


# ── Validators ──────────────────────────────────────────────────────


def is_terminal(*, lifecycle_shape: str, state: str) -> bool:
    """True if state has no outgoing transitions."""
    if lifecycle_shape == "action":
        return state in ("done", "cancelled")
    if lifecycle_shape == "reminder":
        return state in ("acknowledged", "dismissed")
    return False


def valid_states_for(lifecycle_shape: str) -> tuple[str, ...]:
    if lifecycle_shape == "action":
        return ACTION_STATES
    if lifecycle_shape == "reminder":
        return REMINDER_STATES
    raise ValueError(f"Unknown lifecycle_shape: {lifecycle_shape!r}")


def validate_transition(
    *,
    lifecycle_shape: str,
    from_state: str,
    to_state: str,
) -> None:
    """Raises InvalidTransition if illegal."""
    if lifecycle_shape not in LIFECYCLE_SHAPES:
        raise InvalidTransition(
            f"Unknown lifecycle_shape: {lifecycle_shape!r}"
        )
    if lifecycle_shape == "action":
        valid_states = ACTION_STATES
        transitions = ACTION_TRANSITIONS
    else:
        valid_states = REMINDER_STATES
        transitions = REMINDER_TRANSITIONS

    if from_state not in valid_states:
        raise InvalidTransition(
            f"Invalid from_state {from_state!r} for shape {lifecycle_shape!r}"
        )
    if to_state not in valid_states:
        raise InvalidTransition(
            f"Invalid to_state {to_state!r} for shape {lifecycle_shape!r}"
        )
    if from_state == to_state:
        return  # idempotent
    allowed = transitions.get(from_state, set())
    if to_state not in allowed:
        raise InvalidTransition(
            f"Cannot transition from {from_state!r} to {to_state!r} "
            f"in shape {lifecycle_shape!r}"
        )


# ── Event emission planning ──────────────────────────────────────────


def events_for_transition(
    *,
    lifecycle_shape: str,
    from_state: str,
    to_state: str,
) -> tuple[str, ...]:
    """Returns event_type tuple emitted for a given transition.

    `task_status_changed` is always emitted. Additional events follow
    build prompt §5.2 mapping.
    """
    events: list[str] = ["task_status_changed"]

    if lifecycle_shape == "action":
        if from_state == "created" and to_state == "assigned":
            events.append("task_assigned")
        if to_state == "done":
            events.append("task_completed")
        if to_state == "blocked":
            events.append("task_blocked")
        if from_state == "blocked" and to_state != "blocked":
            events.append("task_unblocked")
        if to_state == "cancelled":
            events.append("task_cancelled")
    # Reminder transitions do not emit additional events in v1.

    return tuple(events)


# ── Transition application ──────────────────────────────────────────


def apply_transition(
    db: Session,
    *,
    task_details_id: str,
    to_state: str,
    actor_user_id: str | None = None,
    resolution_outcome: str | None = None,
) -> TaskDetails:
    """Transition the task; emit subscriber registry events; write audit row.

    Returns updated TaskDetails. Caller is responsible for commit
    (consistent with rest of services package; transition is a unit
    inside whatever transaction the caller composes).

    NOTE: this function does NOT call db.commit(). Subscribers fire
    synchronously within the same transaction. If commit fails, the
    whole transition reverts.
    """
    td = (
        db.query(TaskDetails)
        .filter(TaskDetails.id == task_details_id)
        .first()
    )
    if td is None:
        raise TaskDetailsNotFound(
            f"TaskDetails {task_details_id} not found"
        )

    from_state = td.current_state
    validate_transition(
        lifecycle_shape=td.lifecycle_shape,
        from_state=from_state,
        to_state=to_state,
    )

    if from_state == to_state:
        return td  # idempotent no-op

    # State change.
    td.current_state = to_state
    if to_state == "done" and td.completed_at is None:
        td.completed_at = datetime.now(timezone.utc)
    if resolution_outcome is not None:
        td.resolution_outcome = resolution_outcome
    td.updated_at = datetime.now(timezone.utc)

    # Audit trail — best-effort.
    try:
        from app.models.vault_item import VaultItem
        vi = (
            db.query(VaultItem)
            .filter(VaultItem.id == td.vault_item_id)
            .first()
        )
        company_id = vi.company_id if vi else None
        if company_id is not None:
            audit = AuditLog(
                company_id=company_id,
                user_id=actor_user_id,
                action="task.transition",
                entity_type="task_details",
                entity_id=td.id,
                changes=json.dumps({
                    "from": from_state,
                    "to": to_state,
                    "resolution_outcome": resolution_outcome,
                }),
            )
            db.add(audit)
    except Exception:
        logger.exception(
            "audit write failed for task transition td_id=%s", td.id
        )

    # Emit events.
    from app.services.tasks.subscribers.registry import emit_event

    events = events_for_transition(
        lifecycle_shape=td.lifecycle_shape,
        from_state=from_state,
        to_state=to_state,
    )
    for ev in events:
        emit_event(
            db,
            event_type=ev,
            task_details_id=td.id,
            actor_user_id=actor_user_id,
            payload={
                "from_state": from_state,
                "to_state": to_state,
                "resolution_outcome": resolution_outcome,
            },
        )

    return td


__all__ = [
    "LifecycleError",
    "InvalidTransition",
    "TaskDetailsNotFound",
    "ACTION_TRANSITIONS",
    "REMINDER_TRANSITIONS",
    "LEGACY_STATUS_MAP",
    "legacy_status_to_action_state",
    "is_terminal",
    "valid_states_for",
    "validate_transition",
    "events_for_transition",
    "apply_transition",
]
