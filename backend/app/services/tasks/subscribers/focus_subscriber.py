"""Focus session integration subscriber.

v1 task substrate B3: when a task transitions to a terminal state
(`done` or `cancelled`), close any open Focus sessions linked to the
task via `focus_sessions.task_id` (r108 column).

The reverse direction — populating `focus_sessions.task_id` on session
creation — is wired in `focus_session_service.create_or_resume_session`
when a `task_id` kwarg is supplied (B3 Item 5).

`focus_session_service.close_session` is idempotent on already-closed
sessions; safe to call against rows that another path already closed.

Event types: task_completed, task_cancelled.

State doc §5.7; build prompt §7.5 / B3.B.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """Close focus sessions linked to the completed task."""
    td_id = payload.get("task_details_id")
    if td_id is None:
        return

    td = (
        db.query(TaskDetails)
        .filter(TaskDetails.id == td_id)
        .first()
    )
    if td is None:
        return

    try:
        from app.models.focus_session import FocusSession
        from app.services.focus.focus_session_service import close_session
    except ImportError:
        return

    # vault_item_id is the canonical "task id" carried on focus_sessions
    # because r108 declared focus_sessions.task_id → vault_items.id.
    task_id = td.vault_item_id
    if not task_id:
        return

    try:
        sessions = (
            db.query(FocusSession)
            .filter(FocusSession.task_id == task_id)
            .filter(FocusSession.is_active.is_(True))
            .all()
        )
    except Exception:
        # focus_sessions.task_id column missing or ORM mapping not yet
        # extended — degrade quietly. (B3 ships the column + ORM
        # mapping; pre-deploy + during partial migration, this is safe.)
        logger.exception(
            "focus_closer: focus_sessions query failed (task_id=%s) — skipping",
            task_id,
        )
        return

    closed = 0
    for session in sessions:
        try:
            close_session(db, session)
            closed += 1
        except Exception:
            logger.exception(
                "focus_closer: close_session failed (session_id=%s)",
                session.id,
            )
    if closed:
        logger.debug(
            "focus_closer: closed %d focus session(s) for task %s",
            closed, task_id,
        )


register_subscriber(
    "focus_closer",
    _handle,
    event_types=("task_completed", "task_cancelled"),
)
