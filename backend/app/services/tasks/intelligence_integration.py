"""v1 task substrate B3 — Intelligence integration helper.

Per build prompt §7.6: Intelligence observations should fire
`create_task_with_provenance(provenance_kind='intelligence_observation',
...)` instead of firing notifications directly. Notification dispatch
happens via the notification_dispatcher subscriber (Decision C
metadata-presence routing established in B2).

**Surface status at B3 ship:** the codebase has no Intelligence-layer
service that fires notifications directly today (grep of
`backend/app/services/intelligence/` returns zero `create_notification`
/ `notify_users_with_permission` callers). This helper is the canonical
entry point for *future* Intelligence consumers — when an intelligence
observation surface needs operator attention, it calls
`create_intelligence_observation_task(...)` and the substrate handles
the rest (audit, notification dispatch via subscriber, lifecycle).

Parity discipline carries from B2 producer-site refactor:
  • Notification recipient cohort + payload shape determined by
    metadata.notification_permission_key (Decision C); behavior
    identical to producer-direct dispatch via the helper.
  • Idempotency via composite key
    (intelligence_observation / observation_ref_type /
     observation_ref_id / event_kind).

Future Intelligence producers should adopt this helper; the helper
itself is a thin wrapper around `create_task_with_provenance` with
intelligence-specific defaults (provenance_kind, task_type_key='anomaly_resolution_task').
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.services.tasks.service import create_task_with_provenance


def create_intelligence_observation_task(
    db: Session,
    *,
    company_id: str,
    observation_ref_type: str,
    observation_ref_id: str,
    event_kind: str,
    title: str,
    description: str | None = None,
    task_type_key: str = "anomaly_resolution_task",
    notification_permission_key: str | None = None,
    notification_category: str | None = None,
    notification_link: str | None = None,
    assignee_user_id: str | None = None,
    priority: str | None = None,
    created_by_user_id: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> TaskDetails:
    """Materialize an Intelligence observation as a substrate task.

    Equivalent to a producer-direct call to
    `notify_users_with_permission(...)` pre-B3 — but the task substrate
    handles persistence + lifecycle + notification dispatch as a
    by-product. Notification recipients + payload reproduce parity per
    B2 Decision C.

    Args:
      observation_ref_type: type of the entity the observation is about
        (e.g., 'agent_anomaly', 'cross_system_insight', 'financial_health_score').
      observation_ref_id: id of that entity (UUID-shaped string).
      event_kind: stable per-observation-type discriminator
        (e.g., 'anomaly.high_severity', 'insight.fired').
      notification_permission_key: cohort-routing key consumed by the
        notification_dispatcher subscriber. Mandatory for
        cohort-allowlist task_types per B2.
      assignee_user_id: direct-user override (skips cohort routing).

    Returns the created (or existing-on-idempotent-hit) TaskDetails row.
    """
    metadata: dict[str, Any] = dict(extra_metadata or {})
    metadata["task_type_key"] = task_type_key
    if notification_permission_key:
        metadata["notification_permission_key"] = notification_permission_key
    if notification_category:
        metadata["notification_category"] = notification_category
    if notification_link:
        metadata["notification_link"] = notification_link

    return create_task_with_provenance(
        db,
        company_id=company_id,
        provenance_kind="intelligence_observation",
        provenance_ref_type=observation_ref_type,
        provenance_ref_id=observation_ref_id,
        event_kind=event_kind,
        task_type_key=task_type_key,
        title=title,
        description=description,
        created_by_user_id=created_by_user_id,
        assignee_user_id=assignee_user_id,
        priority=priority,
        metadata=metadata,
    )


__all__ = ["create_intelligence_observation_task"]
