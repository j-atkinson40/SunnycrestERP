"""Anomalies widget — Phase W-3a foundation widget service.

Surfaces real production anomaly data from the existing
`agent_anomalies` table (Phase 1 accounting agent infrastructure +
extensions). Per Phase W-3a spec: real data over stub — every Wilbert
licensee tenant running accounting agents has unresolved anomalies
that this widget surfaces directly. Phase W-5 (Intelligence-detected
anomalies) extends the data source rather than replacing the widget.

Tenant isolation discipline (CRITICAL — load-bearing for security):
  - `AgentAnomaly` has no direct `company_id` column. Tenant scoping
    flows through the `agent_job_id` FK → `AgentJob.tenant_id`.
  - Every query in this service explicitly joins AgentJob and filters
    `AgentJob.tenant_id == user.company_id`.
  - The acknowledge endpoint re-validates tenant ownership BEFORE
    mutating; an anomaly_id from another tenant returns 404 (not 403,
    to avoid leaking existence).

Severity vocabulary per `app.schemas.agent.AnomalySeverity`:
  - `critical` (most severe; status-error token / terracotta)
  - `warning` (middle; status-warning token / terracotta-muted)
  - `info` (informational; status-info token)

The widget UI uses "Acknowledge" as the user-facing verb; the data
model action is `resolved=true` + optional `resolution_note`. Audit
log entry records `action="anomaly_resolved"` for accuracy at the
data layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.user import User


# Severity sort order — critical first, warning, info last.
_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def get_anomalies(
    db: Session,
    *,
    user: User,
    severity_filter: Optional[str] = None,
    limit: int = 20,
    include_resolved: bool = False,
) -> dict:
    """Return unresolved anomalies for the user's tenant, severity-sorted.

    Tenant scoping: filter via AgentJob.tenant_id == user.company_id.
    The join is the load-bearing security gate — without it, anomaly
    rows could be returned across tenants.

    Args:
      severity_filter: optional "critical" | "warning" | "info" — if
        set, only that severity is returned.
      limit: max rows; defaults to 20 (cap at 200 for performance).
      include_resolved: if True, returns resolved anomalies too. Default
        False — the widget's primary mode is "what needs attention now."

    Returns:
      {
        "anomalies": [
          {
            id, severity, anomaly_type, description, entity_type,
            entity_id, amount, source_agent_job_id, source_agent_type,
            created_at, resolved, resolved_by, resolved_at,
            resolution_note,
          },
          ...
        ],
        "total_unresolved": int,  # all severities, ignores filter
        "critical_count": int,    # count of unresolved critical
      }
    """
    if user.company_id is None:
        return {
            "anomalies": [],
            "total_unresolved": 0,
            "critical_count": 0,
        }

    capped_limit = max(1, min(int(limit or 20), 200))

    base = (
        db.query(AgentAnomaly, AgentJob)
        .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
        .filter(AgentJob.tenant_id == user.company_id)
    )

    # Resolved filter — default to unresolved-only.
    if not include_resolved:
        base = base.filter(AgentAnomaly.resolved.is_(False))

    if severity_filter:
        base = base.filter(AgentAnomaly.severity == severity_filter)

    # Severity-sort: critical first → warning → info, then by
    # created_at desc within each severity bucket. Postgres
    # `CASE WHEN ... THEN n` keeps the ordering deterministic without
    # a Python-side sort that would defeat LIMIT pushdown.
    from sqlalchemy import case

    severity_order = case(
        (AgentAnomaly.severity == "critical", 0),
        (AgentAnomaly.severity == "warning", 1),
        (AgentAnomaly.severity == "info", 2),
        else_=3,
    )
    rows = (
        base.order_by(severity_order, desc(AgentAnomaly.created_at))
        .limit(capped_limit)
        .all()
    )

    # Total unresolved across all severities — ignores severity_filter
    # for the global count chip.
    total_unresolved = (
        db.query(AgentAnomaly)
        .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentAnomaly.resolved.is_(False),
        )
        .count()
    )
    critical_count = (
        db.query(AgentAnomaly)
        .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentAnomaly.resolved.is_(False),
            AgentAnomaly.severity == "critical",
        )
        .count()
    )

    return {
        "anomalies": [
            _serialize_anomaly(anomaly, job) for (anomaly, job) in rows
        ],
        "total_unresolved": total_unresolved,
        "critical_count": critical_count,
    }


def resolve_anomaly(
    db: Session,
    *,
    user: User,
    anomaly_id: str,
    resolution_note: Optional[str] = None,
) -> AgentAnomaly | None:
    """Mark a single anomaly resolved (the widget's "Acknowledge" action).

    Tenant-scoped: returns None when the anomaly_id belongs to a
    different tenant or doesn't exist (caller surfaces 404). Avoids
    distinguishing "not found" from "wrong tenant" to prevent
    existence leakage.

    Idempotent: re-acknowledging an already-resolved anomaly is a
    no-op write that returns the existing row. Audit log entry written
    on every state-flip (the FIRST resolve); not on re-acknowledge
    no-ops.
    """
    if user.company_id is None:
        return None

    row = (
        db.query(AgentAnomaly, AgentJob)
        .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
        .filter(
            AgentAnomaly.id == anomaly_id,
            AgentJob.tenant_id == user.company_id,
        )
        .first()
    )
    if row is None:
        return None

    anomaly, _job = row

    if anomaly.resolved:
        # Idempotent re-ack — no state change, no audit log entry.
        return anomaly

    # State flip + audit log entry. Use a try/except around the audit
    # call so an audit-log failure doesn't block the resolve (mirrors
    # the V-1d notification-service defensive pattern).
    anomaly.resolved = True
    anomaly.resolved_by = user.id
    anomaly.resolved_at = datetime.now(timezone.utc)
    if resolution_note is not None:
        anomaly.resolution_note = resolution_note

    db.commit()
    db.refresh(anomaly)

    try:
        from app.services import audit_service

        audit_service.log_action(
            db,
            company_id=user.company_id,
            action="anomaly_resolved",
            entity_type="agent_anomaly",
            entity_id=anomaly.id,
            user_id=user.id,
            changes={
                "resolved": {"old": False, "new": True},
                "resolution_note": {
                    "old": None,
                    "new": resolution_note,
                },
            },
        )
        db.commit()
    except Exception:
        # Best-effort audit logging — don't roll back the state flip
        # if audit fails (alarms in the audit log surface the gap;
        # the anomaly is correctly resolved either way).
        import logging

        logging.getLogger(__name__).exception(
            "Failed to write audit log for anomaly resolve %s",
            anomaly.id,
        )
        try:
            db.rollback()
        except Exception:
            pass

    return anomaly


def _serialize_anomaly(anomaly: AgentAnomaly, job: AgentJob) -> dict:
    """Widget-consumable shape for an anomaly row."""
    return {
        "id": anomaly.id,
        "severity": anomaly.severity,
        "anomaly_type": anomaly.anomaly_type,
        "description": anomaly.description,
        "entity_type": anomaly.entity_type,
        "entity_id": anomaly.entity_id,
        "amount": str(anomaly.amount) if anomaly.amount is not None else None,
        "source_agent_job_id": anomaly.agent_job_id,
        "source_agent_type": getattr(job, "job_type", None),
        "created_at": anomaly.created_at,
        "resolved": anomaly.resolved,
        "resolved_by": anomaly.resolved_by,
        "resolved_at": anomaly.resolved_at,
        "resolution_note": anomaly.resolution_note,
    }
