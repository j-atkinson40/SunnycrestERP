"""Books Review Arc B B-4 — reconciliation flag returner.

Rides the SAME task-completion event family as jcf_subscriber (a sibling; the
registry dispatches both). When the Task an "Ask someone" flag created completes
(or is cancelled — the question is done either way), return the parked exception:
the flag's returned_at is stamped and the exception's flag_id cleared, so the SAME
exception reopens with its park history intact.

This is a HOOK, not a sweep — no scheduler. Registered at import time; activated
by the side-effect import in app.services.tasks.__init__.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.tasks.subscribers.registry import register_subscriber

logger = logging.getLogger(__name__)

_TERMINAL_EVENTS = ("task_completed", "task_cancelled")


def _handle(db: Session, payload: dict[str, Any]) -> None:
    vault_item_id = payload.get("vault_item_id")
    if vault_item_id is None:
        # Same tolerance as jcf_subscriber — derive via task_details when the
        # payload carries only the details id.
        td_id = payload.get("task_details_id")
        if td_id is None:
            return
        from app.models.task_details import TaskDetails

        td = db.query(TaskDetails).filter(TaskDetails.id == td_id).first()
        if td is None:
            return
        vault_item_id = td.vault_item_id

    from app.services.reconciliation_flags import return_flags_on_task_completed

    n = return_flags_on_task_completed(db, vault_item_id)
    if n:
        logger.info(
            "[reconciliation_flag] returned %d parked exception(s) on task %s",
            n, vault_item_id,
        )


register_subscriber(
    "reconciliation_flag_returner",
    _handle,
    event_types=_TERMINAL_EVENTS,
)
