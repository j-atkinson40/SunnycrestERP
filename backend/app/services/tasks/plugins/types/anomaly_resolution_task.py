"""anomaly_resolution_task — AgentAnomaly producer task type.

Per build prompt §5.5 item 5:
- lifecycle_shape: action
- routing_mode: direct_user
- priority: high
- visibility: operator_internal

Hook on `done`:
- updates AgentAnomaly.is_resolved=True via existing service path,
  when provenance_ref_type='agent_anomaly'. v1.0 ships the hook as a
  best-effort write; v1.5 (c) refactor activates this path against
  three of base_agent's four producers (cash_receipts, ar_collections,
  expense_categorization).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.services.tasks.plugins.type_behaviors import (
    register_task_type_behavior,
)


logger = logging.getLogger(__name__)


class AnomalyResolutionTaskBehavior:
    task_type_key = "anomaly_resolution_task"
    default_lifecycle_shape = "action"
    default_routing_mode = "direct_user"
    default_priority = "high"
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
        if td is None or td.provenance_ref_type != "agent_anomaly":
            return
        # Best-effort write to mark the linked anomaly resolved.
        try:
            from app.models.agent_anomaly import AgentAnomaly
            anomaly = (
                db.query(AgentAnomaly)
                .filter(AgentAnomaly.id == td.provenance_ref_id)
                .first()
            )
            if anomaly is not None and hasattr(anomaly, "is_resolved"):
                anomaly.is_resolved = True
        except Exception:
            logger.exception(
                "anomaly_resolution_task done-hook failed for "
                "td_id=%s ref_id=%s",
                td.id, td.provenance_ref_id,
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
            "task_type": "anomaly_resolution_task",
            "current_state": td.current_state,
            "priority": td.priority,
            "provenance_ref_id": td.provenance_ref_id,
        }


register_task_type_behavior(AnomalyResolutionTaskBehavior())
