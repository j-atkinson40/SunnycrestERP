"""review_approval_task — approval-gate cohort task type.

Per build prompt §5.5 item 2:
- lifecycle_shape: action
- routing_mode: direct_user
- priority: normal (escalated to 'high' if due_date < 48h at creation —
  callers compute + pass; this plugin doesn't auto-bump on read)
- visibility: operator_internal

Hook on `done`:
- writes resolution_outcome derived from metadata.outcome (approved /
  rejected); falls back to "completed".

Used by 5 of 8 (c) producer sites (social_service_certificate, base_agent
month_end_close, catalog_fetch, safety_program, workflow_engine review).
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


class ReviewApprovalTaskBehavior:
    task_type_key = "review_approval_task"
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
        if td is None or td.resolution_outcome is not None:
            return  # already set by caller
        vi = (
            db.query(VaultItem)
            .filter(VaultItem.id == td.vault_item_id)
            .first()
        )
        if vi is None:
            return
        meta = vi.metadata_json or {}
        outcome = meta.get("outcome")
        if outcome in ("approved", "rejected"):
            td.resolution_outcome = outcome
        else:
            td.resolution_outcome = "completed"

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
            "task_type": "review_approval_task",
            "current_state": td.current_state,
            "priority": td.priority,
            "due_date": td.due_date.isoformat() if td.due_date else None,
            "resolution_outcome": td.resolution_outcome,
        }


register_task_type_behavior(ReviewApprovalTaskBehavior())
