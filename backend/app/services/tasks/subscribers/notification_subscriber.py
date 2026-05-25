"""Notification dispatcher subscriber.

v1.0: registered + observes events but **does NOT dispatch** —
v1.0 keeps (c) direct notification path unchanged. The scaffolding
exists so v1.5 (c) refactor can flip the call sites without
re-architecting the registry.

v1.5: replaces (c) direct dispatch — listens for task_created /
task_assigned and calls `notify_users_with_permission`. Same
downstream function as today; different upstream invocation path.

State doc §5.7; build prompt §5.3.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """v1.0: no-op observer. Logs at debug for traceability.

    v1.5: replace with dispatch through notify_users_with_permission.
    """
    logger.debug(
        "notification_subscriber observed event %r for task_details %s "
        "(v1.0 no-op; v1.5 wires dispatch)",
        payload.get("event_type"),
        payload.get("task_details_id"),
    )


# Listen for events that would dispatch notifications in v1.5.
# v1.0 still receives them, but the handler is a no-op.
register_subscriber(
    "notification_dispatcher",
    _handle,
    event_types=(
        "task_created",
        "task_assigned",
        "task_completed",
        "task_blocked",
    ),
)
