"""customer_communication_task — communications cascade task type.

Per build prompt §5.5 item 4:
- lifecycle_shape: action
- routing_mode: direct_user
- priority: normal
- visibility: operator_internal (v2 family-portal extension uses
  different visibility values)

Hook on `done`:
- writes outbound communication if metadata.outbound_response is set
  (v1.5 communications cascade wires this; v1.0 substrate ships the hook
  as a logging-only stub).

Used by classification/dispatch (v1.5 wiring) + future communications
cascade work.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.models.vault_item import VaultItem
from app.services.tasks.plugins.type_behaviors import (
    register_task_type_behavior,
)


logger = logging.getLogger(__name__)


class CustomerCommunicationTaskBehavior:
    task_type_key = "customer_communication_task"
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
        if to_state != "done":
            return
        td = (
            db.query(TaskDetails)
            .filter(TaskDetails.id == task_details_id)
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
        meta = vi.metadata_json or {}
        outbound = meta.get("outbound_response")
        if outbound:
            # v1.0: logging-only stub. v1.5 communications cascade
            # wires actual outbound dispatch through delivery_service.
            logger.info(
                "customer_communication_task done with outbound_response "
                "set (td_id=%s); v1.5 will dispatch.",
                td.id,
            )

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
            "task_type": "customer_communication_task",
            "current_state": td.current_state,
            "priority": td.priority,
            "due_date": td.due_date.isoformat() if td.due_date else None,
        }


register_task_type_behavior(CustomerCommunicationTaskBehavior())
