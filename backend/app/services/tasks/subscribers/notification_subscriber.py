"""Notification dispatcher subscriber — v1.5 (c) refactor (B2).

Listens for task_created / task_assigned events emitted by
`create_task_with_provenance` and dispatches notifications. Replaces
the producer-site direct dispatch pattern across the 8 (c) producer
sites: producers now create a task; this subscriber delivers the
notification post-event.

Routing discriminator (Decision C, operator-locked):

- If `event_payload.metadata.notification_permission_key` is present →
  cohort routing via `notify_users_with_permission(...)`.
- Otherwise →
  - Defensive raise if `task_type_key` is in the cohort-allowlist
    (review_approval_task, scheduled_recurring_task,
    customer_communication_task, anomaly_resolution_task) — those task
    types are cohort-routed and must carry a permission_key.
  - Direct-user dispatch via `create_notification(user_id=assignee_user_id, ...)`
    when an assignee is present.
  - If no assignee + no permission_key → informational, skip with log.

The legacy `notify_users_with_permission` helper at
`notification_service.py:155` is unchanged — substrate just calls it
on the producer's behalf.

State doc §5.7; build prompt §5.3; B2 architectural locks A/B/C/D.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.models.vault_item import VaultItem
from app.services.tasks.subscribers.registry import register_subscriber


logger = logging.getLogger(__name__)


# Task types whose canonical dispatch grain is a cohort (permission-gated
# fan-out), NOT a direct user. If a task of one of these types arrives
# at the subscriber without `metadata.notification_permission_key`, that
# producer is misconfigured — defensive raise so the failure surfaces
# (registry's try/except logs the error + continues for the rest of the
# dispatch pipeline).
COHORT_ALLOWLIST: frozenset[str] = frozenset({
    "review_approval_task",
    "scheduled_recurring_task",
    "customer_communication_task",
    "anomaly_resolution_task",
})


def _link_for_task(task_details_id: str, metadata: dict[str, Any]) -> str:
    """Resolve a destination URL for the notification.

    Producer-supplied `metadata.notification_link` wins; otherwise the
    default task surface route is used (full task-surface routing wires
    in a later arc; this placeholder is correct for v1.5).
    """
    link = metadata.get("notification_link") if isinstance(metadata, dict) else None
    if isinstance(link, str) and link:
        return link
    return f"/tasks/{task_details_id}"


def _category_for_task(metadata: dict[str, Any]) -> str | None:
    """Producer-supplied category from metadata; None if absent."""
    if isinstance(metadata, dict):
        cat = metadata.get("notification_category")
        if isinstance(cat, str) and cat:
            return cat
    return None


def _message_for_task(td: TaskDetails, vi: VaultItem, metadata: dict[str, Any]) -> str:
    """Compose the notification body. Producer-supplied message wins."""
    if isinstance(metadata, dict):
        msg = metadata.get("notification_message")
        if isinstance(msg, str) and msg:
            return msg
    return vi.description or vi.title or ""


def _handle(db: Session, payload: dict[str, Any]) -> None:
    """Dispatch a notification triggered by task_created or task_assigned.

    Lookup the task_details + vault_item rows, read metadata, branch on
    Decision C discriminator, dispatch.
    """
    td_id = payload.get("task_details_id")
    if td_id is None:
        return

    td = (
        db.query(TaskDetails)
        .filter(TaskDetails.id == td_id)
        .first()
    )
    if td is None:
        logger.debug(
            "notification_subscriber: task_details %s not found — skipping",
            td_id,
        )
        return

    vi = (
        db.query(VaultItem)
        .filter(VaultItem.id == td.vault_item_id)
        .first()
    )
    if vi is None:
        logger.debug(
            "notification_subscriber: vault_item for td %s not found — skipping",
            td_id,
        )
        return

    metadata: dict[str, Any] = vi.metadata_json or {}
    task_type_key: str = (metadata.get("task_type_key") or "").strip()
    permission_key = metadata.get("notification_permission_key")
    if isinstance(permission_key, str):
        permission_key = permission_key.strip() or None
    else:
        permission_key = None

    actor_user_id = payload.get("actor_user_id")
    title = vi.title or ""
    message = _message_for_task(td, vi, metadata)
    link = _link_for_task(td.id, metadata)
    category = _category_for_task(metadata)
    notification_type = metadata.get("notification_type") if isinstance(metadata, dict) else None
    if not isinstance(notification_type, str) or not notification_type:
        notification_type = "info"
    severity = metadata.get("notification_severity") if isinstance(metadata, dict) else None
    source_reference_type = metadata.get("notification_source_reference_type") if isinstance(metadata, dict) else None
    source_reference_id = metadata.get("notification_source_reference_id") if isinstance(metadata, dict) else None
    if not isinstance(source_reference_type, str) or not source_reference_type:
        source_reference_type = "task_details"
    if not isinstance(source_reference_id, str) or not source_reference_id:
        source_reference_id = td.id

    # Import here to avoid circular import at module load.
    from app.services import notification_service

    # ── Decision C: cohort routing when permission_key present.
    if permission_key:
        notification_service.notify_users_with_permission(
            db,
            company_id=vi.company_id,
            permission_key=permission_key,
            title=title,
            message=message,
            type=notification_type,
            category=category,
            link=link,
            actor_user_id=actor_user_id,
            severity=severity if isinstance(severity, str) else None,
            source_reference_type=source_reference_type,
            source_reference_id=source_reference_id,
        )
        return

    # ── No permission_key — defensive assertion for cohort-allowlist types.
    if task_type_key in COHORT_ALLOWLIST:
        msg = (
            f"notification_subscriber: task_type_key {task_type_key!r} is "
            f"cohort-routed but metadata.notification_permission_key is "
            f"absent (task_details_id={td.id}). Producer site is "
            f"misconfigured."
        )
        logger.error(msg)
        raise ValueError(msg)

    # ── Direct-user routing.
    if td.assignee_user_id:
        # Lock 3 self-suppression: don't notify the actor when actor == assignee.
        if actor_user_id is not None and actor_user_id == td.assignee_user_id:
            logger.debug(
                "notification_subscriber: self-assignment suppression "
                "(actor==assignee=%s) — skipping",
                actor_user_id,
            )
            return
        notification_service.create_notification(
            db,
            company_id=vi.company_id,
            user_id=td.assignee_user_id,
            title=title,
            message=message,
            type=notification_type,
            category=category,
            link=link,
            actor_id=actor_user_id,
            severity=severity if isinstance(severity, str) else None,
            source_reference_type=source_reference_type,
            source_reference_id=source_reference_id,
        )
        return

    # ── No assignee + no permission_key + non-cohort task_type:
    # informational task with no clear recipient. Log + skip; the task
    # row + audit row already exist via the substrate.
    logger.debug(
        "notification_subscriber: no assignee + no permission_key for "
        "task_type %s (td=%s) — informational; no notification dispatched",
        task_type_key or "<unknown>",
        td.id,
    )


# Listen for the two events that map to notification dispatch in v1.5.
register_subscriber(
    "notification_dispatcher",
    _handle,
    event_types=(
        "task_created",
        "task_assigned",
    ),
)
