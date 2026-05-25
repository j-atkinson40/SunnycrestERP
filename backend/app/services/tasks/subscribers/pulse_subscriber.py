"""Pulse invalidator subscriber.

v1 task substrate B3: invalidates the Pulse composition cache for the
affected user on task lifecycle events. The Pulse `_build_tasks_item`
read (B3 Item 1) is now substrate-backed; cached compositions go stale
when an assignment lands or a status flips.

Cache invalidation is best-effort + sync: `composition_cache.invalidate_for_user`
returns the evicted count and never raises (its own try/except guards
the Redis path). Subscriber registry's try/except is a second layer.

Event types: task_created, task_assigned, task_status_changed,
task_completed, task_cancelled.

State doc §5.7; build prompt §7.1 / B3.B.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _resolve_assignee_user_id(db: Session, task_details_id: str) -> str | None:
    td = (
        db.query(TaskDetails)
        .filter(TaskDetails.id == task_details_id)
        .first()
    )
    if td is None:
        return None
    return td.assignee_user_id


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """Invalidate the user's Pulse composition cache entries."""
    td_id = payload.get("task_details_id")
    if td_id is None:
        return

    user_id = payload.get("assignee_user_id")
    if not user_id:
        user_id = _resolve_assignee_user_id(db, td_id)

    if not user_id:
        logger.debug(
            "pulse_invalidator: no user_id resolvable for td=%s — skipping",
            td_id,
        )
        return

    try:
        from app.services.pulse import composition_cache

        evicted = composition_cache.invalidate_for_user(user_id)
        logger.debug(
            "pulse_invalidator: evicted %d cache entries for user %s",
            evicted, user_id,
        )
    except Exception:
        logger.exception(
            "pulse_invalidator: invalidate_for_user failed (user=%s td=%s)",
            user_id, td_id,
        )


register_subscriber(
    "pulse_invalidator",
    _handle,
    event_types=(
        "task_created",
        "task_assigned",
        "task_status_changed",
        "task_completed",
        "task_cancelled",
    ),
)
