"""Background job failure responder — auto-fix tier.

Detects which scheduled job failed, re-runs it (up to 3 retries in 24 h),
resolves the incident, and recalculates tenant health.

JOB_REGISTRY wrappers are zero-arg callables that create their own DB
sessions, so we call them without passing `db`.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.base import IncidentResponder

logger = logging.getLogger(__name__)

MAX_RETRIES_24H = 3


class BackgroundJobResponder(IncidentResponder):
    category = "background_job"
    resolution_tier = "auto_fix"

    def handle(self, db: Session, incident: PlatformIncident) -> bool:
        from app.scheduler import JOB_REGISTRY
        from app.services.platform.platform_health_service import (
            calculate_all_tenant_health,
            calculate_tenant_health,
            resolve_incident,
        )

        # ── Step 1: identify which job failed ─────────────────────────
        job_name = (incident.context or {}).get("job_name")

        if not job_name:
            for name in JOB_REGISTRY:
                if name in (incident.error_message or ""):
                    job_name = name
                    break

        if not job_name:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    "Could not identify job name from incident. "
                    "Manual review required."
                ),
                status="escalated",
            )
            return False

        # ── Step 2: check retry count ─────────────────────────────────
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_same = (
            db.query(PlatformIncident)
            .filter(
                PlatformIncident.fingerprint == incident.fingerprint,
                PlatformIncident.created_at >= cutoff,
                PlatformIncident.id != incident.id,
            )
            .count()
        )

        if recent_same >= MAX_RETRIES_24H:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    f"Job {job_name} has failed {recent_same + 1} times "
                    f"in 24h. Escalating — auto-retry limit reached."
                ),
                status="escalated",
            )
            return False

        # ── Step 3: re-run the job ────────────────────────────────────
        job_fn = JOB_REGISTRY.get(job_name)

        if not job_fn:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    f"Job {job_name} not found in JOB_REGISTRY. "
                    "Manual review required."
                ),
                status="escalated",
            )
            return False

        # JOB_REGISTRY functions are zero-arg wrappers (create own sessions)
        job_fn()

        # ── Step 4: resolve the incident ──────────────────────────────
        resolve_incident(
            db=db,
            incident_id=str(incident.id),
            resolution_action=(
                f"Auto-fix: job {job_name} re-queued and completed "
                f"successfully (attempt {recent_same + 1} of {MAX_RETRIES_24H})."
            ),
            status="resolved",
        )

        # ── Step 5: recalculate tenant health ─────────────────────────
        if incident.tenant_id:
            calculate_tenant_health(db=db, tenant_id=incident.tenant_id)
        else:
            calculate_all_tenant_health(db=db)

        return True
