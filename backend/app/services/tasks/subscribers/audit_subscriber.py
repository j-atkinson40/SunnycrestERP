"""Audit writer subscriber.

Writes audit_log rows on every task event. Active in v1.0.

Note: lifecycle.apply_transition already writes a `task.transition`
audit row directly. This subscriber covers task_created (which happens
in the service-layer creator, not in apply_transition) + serves as a
safety net for any direct emit_event calls.

State doc §5.7; build prompt §5.3.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.task_details import TaskDetails
from app.models.vault_item import VaultItem
from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """Write an audit_log row for the event."""
    event_type = payload.get("event_type")
    td_id = payload.get("task_details_id")
    if td_id is None:
        return

    try:
        td = (
            db.query(TaskDetails)
            .filter(TaskDetails.id == td_id)
            .first()
        )
        if td is None:
            return
        vi = (
            db.query(VaultItem)
            .filter(VaultItem.id == td.vault_item_id)
            .first()
        )
        if vi is None:
            return

        # task.transition is written by lifecycle.apply_transition
        # directly; skip here to avoid double-write.
        if event_type == "task_status_changed":
            return

        audit = AuditLog(
            company_id=vi.company_id,
            user_id=payload.get("actor_user_id"),
            action=f"task.{event_type}",
            entity_type="task_details",
            entity_id=td.id,
            changes=json.dumps({
                k: v for k, v in payload.items()
                if k not in ("event_type", "task_details_id")
            }),
        )
        db.add(audit)
    except Exception:
        logger.exception(
            "audit_subscriber failed for event %s td_id=%s",
            event_type, td_id,
        )


register_subscriber("audit_writer", _handle)
