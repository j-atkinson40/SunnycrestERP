"""Focus session integration subscriber.

v1.0: no-op (focus_sessions.task_id column lands in r108 at v1.5).
v1.5: closes focus_sessions where is_active=true + task_id matches
the completed task.

State doc §5.7; build prompt §5.3.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """v1.0: no-op. v1.5: closes linked focus_sessions on task completion."""
    logger.debug(
        "focus_subscriber observed event %r (v1.0 no-op)",
        payload.get("event_type"),
    )


register_subscriber(
    "focus_closer",
    _handle,
    event_types=("task_completed", "task_cancelled"),
)
