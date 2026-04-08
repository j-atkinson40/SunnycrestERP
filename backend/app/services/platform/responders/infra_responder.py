"""Infrastructure failure responder — auto-fix tier.

DB connection drops, Railway restarts, and network blips are usually transient.
By the time the dispatcher runs (every 15 min) infra has likely recovered.
A lightweight DB probe confirms health; repeated failures escalate.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.base import IncidentResponder

logger = logging.getLogger(__name__)

ESCALATION_THRESHOLD = 3
ESCALATION_WINDOW_HOURS = 2


class InfraResponder(IncidentResponder):
    category = "infra"
    resolution_tier = "auto_fix"

    def handle(self, db: Session, incident: PlatformIncident) -> bool:
        from app.services.platform.platform_health_service import (
            calculate_all_tenant_health,
            calculate_tenant_health,
            create_notification,
            resolve_incident,
        )

        # Check frequency
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ESCALATION_WINDOW_HOURS)
        recent_infra = (
            db.query(PlatformIncident)
            .filter(
                PlatformIncident.category == "infra",
                PlatformIncident.created_at >= cutoff,
                PlatformIncident.id != incident.id,
            )
            .count()
        )

        if recent_infra >= ESCALATION_THRESHOLD:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    f"{recent_infra + 1} infra failures in 2 hours — "
                    "escalating, persistent instability detected."
                ),
                status="escalated",
            )
            create_notification(
                db=db,
                title="Persistent infrastructure instability",
                body=(
                    f"{recent_infra + 1} infrastructure failures in 2 hours. "
                    "Platform may be unstable."
                ),
                level="critical",
                tenant_id=incident.tenant_id,
                incident_id=str(incident.id),
            )
            return False

        # Probe DB
        probe_passed = False
        probe_error = ""
        try:
            db.execute(text("SELECT 1"))
            probe_passed = True
        except Exception as e:
            probe_error = str(e)

        if not probe_passed:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    f"DB probe failed: {probe_error}. "
                    "Infrastructure still unhealthy. Escalating."
                ),
                status="escalated",
            )
            create_notification(
                db=db,
                title="Infrastructure probe failed",
                body=(
                    "DB health check failed during incident response. "
                    "Manual intervention may be required."
                ),
                level="critical",
                tenant_id=incident.tenant_id,
                incident_id=str(incident.id),
            )
            return False

        # Probe passed — infra recovered
        resolve_incident(
            db=db,
            incident_id=str(incident.id),
            resolution_action=(
                "Auto-fix: infrastructure recovered. "
                "DB probe passed. Transient failure resolved."
            ),
            status="resolved",
        )

        if incident.tenant_id:
            calculate_tenant_health(db=db, tenant_id=incident.tenant_id)
        else:
            calculate_all_tenant_health(db=db)

        return True
