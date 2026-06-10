"""JCF decision-bounded closure subscriber (JCF-1).

Rides the SAME task-completion event family as focus_subscriber (a
SIBLING subscriber — the registry dispatches both; focus_subscriber is
untouched per the JCF-1 STOP discipline). When the task a coordination
Focus instance is bound to completes or cancels, close the instance —
which auto-revokes every active FocusShare (the decision-bounded expiry:
the Hopkins director's access ends when the job does).

Registered at import time; activated by the side-effect import in
app.services.tasks.__init__ (the established subscriber pattern).
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
        # Mirror focus_subscriber's tolerance: derive via task_details when
        # the payload carries only the details id.
        td_id = payload.get("task_details_id")
        if td_id is None:
            return
        from app.models.task_details import TaskDetails

        td = db.query(TaskDetails).filter(TaskDetails.id == td_id).first()
        if td is None:
            return
        vault_item_id = td.vault_item_id

    from app.models.coordination_focus import CoordinationFocusInstance
    from app.services.coordination_focus import close_instance

    instances = (
        db.query(CoordinationFocusInstance)
        .filter(
            CoordinationFocusInstance.task_id == vault_item_id,
            CoordinationFocusInstance.status == "active",
        )
        .all()
    )
    for instance in instances:
        revoked = close_instance(db, instance, actor_user_id=None)
        logger.info(
            "[jcf_subscriber] closed instance %s (task %s); auto-revoked %d share(s)",
            instance.id,
            vault_item_id,
            revoked,
        )


register_subscriber(
    "jcf_closer",
    _handle,
    event_types=_TERMINAL_EVENTS,
)
