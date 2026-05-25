"""scheduled_recurring_task — accounting recurring + aftercare task type.

Per build prompt §5.5 item 3:
- lifecycle_shape: action
- routing_mode: round_robin (load-distributes recurring work)
- priority: normal
- visibility: operator_internal

Hook on `created`:
- populates default due_date based on metadata.recurrence_offset_days
  (e.g., a month-end-close task created on the 1st gets due_date set
  5 days later when metadata.recurrence_offset_days=5).

Used by aftercare_adapter (v1.5 wiring).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.models.vault_item import VaultItem
from app.services.tasks.plugins.type_behaviors import (
    register_task_type_behavior,
)


logger = logging.getLogger(__name__)


class ScheduledRecurringTaskBehavior:
    task_type_key = "scheduled_recurring_task"
    default_lifecycle_shape = "action"
    default_routing_mode = "round_robin"
    default_priority = "normal"
    default_visibility = "operator_internal"

    def on_status_change(
        self,
        db: Session,
        *,
        task_details_id: str,
        from_state: str,
        to_state: str,
        actor_user_id: str | None,
    ) -> None:
        # No status-change side effects; created-hook below handles
        # due-date population. apply_transition uses on_status_change
        # exclusively; the "created" event_type itself is emitted from
        # create_task_with_provenance + invoked via task_created handler
        # if needed.
        return

    def on_created(
        self,
        db: Session,
        *,
        task_details_id: str,
    ) -> None:
        """Populate due_date from metadata.recurrence_offset_days."""
        td = (
            db.query(TaskDetails)
            .filter(TaskDetails.id == task_details_id)
            .first()
        )
        if td is None or td.due_date is not None:
            return
        vi = (
            db.query(VaultItem)
            .filter(VaultItem.id == td.vault_item_id)
            .first()
        )
        if vi is None:
            return
        meta = vi.metadata_json or {}
        offset = meta.get("recurrence_offset_days")
        if isinstance(offset, int) and offset > 0:
            td.due_date = date.today() + timedelta(days=offset)

    def render_default_payload(
        self,
        db: Session,
        *,
        task_details_id: str,
    ) -> dict[str, Any]:
        td = (
            db.query(TaskDetails)
            .filter(TaskDetails.id == task_details_id)
            .first()
        )
        if td is None:
            return {}
        return {
            "task_details_id": td.id,
            "task_type": "scheduled_recurring_task",
            "current_state": td.current_state,
            "priority": td.priority,
            "due_date": td.due_date.isoformat() if td.due_date else None,
        }


register_task_type_behavior(ScheduledRecurringTaskBehavior())
