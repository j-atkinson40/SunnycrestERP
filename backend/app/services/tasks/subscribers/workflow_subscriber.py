"""Workflow integration subscriber.

v1.0: no-op (workflow node types for tasks not yet registered).
v1.5: resumes workflow runs paused at `wait_for_task_completion` nodes
when their dependent task transitions to done or cancelled.

State doc §5.7; build prompt §5.3.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """v1.0: no-op. v1.5: resume waiting workflow runs."""
    logger.debug(
        "workflow_subscriber observed event %r (v1.0 no-op)",
        payload.get("event_type"),
    )


register_subscriber(
    "workflow_resumer",
    _handle,
    event_types=("task_completed", "task_cancelled"),
)
