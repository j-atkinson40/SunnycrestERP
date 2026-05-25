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
        """v1 task substrate B3 (B3.D) — outbound dispatch wire.

        When a customer_communication_task transitions to the configured
        dispatch state (`metadata.dispatch_on_state`, default 'done'),
        send the outbound email via the canonical delivery_service per
        D-7 substrate. Required metadata for dispatch:
          • outbound_template_key  : str — registered document template
          • outbound_to_email      : str
        Optional metadata: outbound_to_name, outbound_template_context,
        outbound_subject_override, outbound_reply_to, outbound_from_name.

        When metadata is missing/incomplete, the plugin logs + skips —
        backward-compat with callers that didn't supply outbound_* fields.
        """
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
        dispatch_on_state = meta.get("dispatch_on_state") or "done"
        if to_state != dispatch_on_state:
            return

        template_key = meta.get("outbound_template_key")
        to_email = meta.get("outbound_to_email")
        if not (template_key and to_email):
            # Configured for outbound but missing required keys — log + skip.
            if meta.get("outbound_response") or template_key:
                logger.info(
                    "customer_communication_task: outbound dispatch on td=%s "
                    "skipped — required metadata missing (template_key=%s, "
                    "to_email=%s)",
                    td.id, bool(template_key), bool(to_email),
                )
            return

        try:
            from app.services.delivery.delivery_service import (
                send_email_with_template,
            )

            send_email_with_template(
                db,
                company_id=vi.company_id,
                to_email=to_email,
                to_name=meta.get("outbound_to_name"),
                template_key=template_key,
                template_context=meta.get("outbound_template_context") or {},
                subject_override=meta.get("outbound_subject_override"),
                reply_to=meta.get("outbound_reply_to"),
                from_name=meta.get("outbound_from_name"),
                caller_module="customer_communication_task.on_status_change",
                metadata={
                    "task_details_id": td.id,
                    "vault_item_id": vi.id,
                },
            )
            logger.info(
                "customer_communication_task outbound dispatched "
                "(td_id=%s template=%s to=%s)",
                td.id, template_key, to_email,
            )
        except Exception:
            logger.exception(
                "customer_communication_task outbound dispatch failed "
                "(td_id=%s template=%s)",
                td.id, template_key,
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
