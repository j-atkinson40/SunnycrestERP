"""generic_task — catch-all task type behavior plugin.

Default behaviors throughout per build prompt §5.5 item 1:
- lifecycle_shape: action
- routing_mode: direct_user
- priority: normal
- visibility: operator_internal

No hooks beyond defaults.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.tasks.plugins.type_behaviors import (
    register_task_type_behavior,
)


class GenericTaskBehavior:
    task_type_key = "generic_task"
    default_lifecycle_shape = "action"
    default_routing_mode = "direct_user"
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
        return  # no-op

    def render_default_payload(
        self,
        db: Session,
        *,
        task_details_id: str,
    ) -> dict[str, Any]:
        from app.models.task_details import TaskDetails

        td = (
            db.query(TaskDetails)
            .filter(TaskDetails.id == task_details_id)
            .first()
        )
        if td is None:
            return {}
        return {
            "task_details_id": td.id,
            "current_state": td.current_state,
            "priority": td.priority,
            "due_date": td.due_date.isoformat() if td.due_date else None,
        }


register_task_type_behavior(GenericTaskBehavior())
