"""Briefings invalidator subscriber.

v1.0: no-op (briefings don't yet read task substrate).
v1.5: invalidates briefings cache on task_created / task_completed.

State doc §5.7; build prompt §5.3.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """v1.0: no-op. v1.5: invalidate briefings cache for affected user."""
    logger.debug(
        "briefings_invalidator observed event %r (v1.0 no-op)",
        payload.get("event_type"),
    )


register_subscriber(
    "briefings_invalidator",
    _handle,
    event_types=("task_created", "task_completed", "task_cancelled"),
)
