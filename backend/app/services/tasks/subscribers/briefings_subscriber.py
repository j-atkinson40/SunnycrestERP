"""Briefings invalidator subscriber.

v1 task substrate B3: invalidates briefings caches on task lifecycle
events for the affected user(s) so the next briefing read picks up the
substrate-shape change.

Today: no shared briefings cache exists (`briefings/` directory has no
cache layer). The subscriber stays sync + idempotent: it does the work
through the (currently no-op) `_invalidate_for_user` helper. When a
briefings cache lands, point the helper at the cache invalidator
without touching this file's wiring.

Event types listened to: task_created, task_assigned,
task_status_changed, task_completed, task_cancelled.

State doc §5.7; build prompt §7.2 / B3.B.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _invalidate_for_user(user_id: str | None) -> None:
    """Cache-invalidator hook for briefings.

    No briefings cache module exists today (data_sources.py composes
    each briefing fresh per call). This helper is wired so the future
    cache landing site is a one-line edit. Until then, the call is a
    debug-level log so the registry's try/except still gets exercised
    by tests.
    """
    if user_id is None:
        logger.debug("briefings_invalidator: no user_id on payload — skipping")
        return
    # Future briefings cache hook lands here:
    #   from app.services.briefings.cache import invalidate_for_user
    #   invalidate_for_user(user_id)
    logger.debug(
        "briefings_invalidator: would invalidate briefings cache for user %s",
        user_id,
    )


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
    """Invalidate briefings cache for the affected user."""
    td_id = payload.get("task_details_id")
    if td_id is None:
        return

    # Prefer payload-supplied assignee_user_id (set by service.py emit),
    # fall back to DB lookup.
    user_id = payload.get("assignee_user_id")
    if not user_id:
        user_id = _resolve_assignee_user_id(db, td_id)

    _invalidate_for_user(user_id)


register_subscriber(
    "briefings_invalidator",
    _handle,
    event_types=(
        "task_created",
        "task_assigned",
        "task_status_changed",
        "task_completed",
        "task_cancelled",
    ),
)
