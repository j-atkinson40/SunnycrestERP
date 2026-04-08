"""Auth failure responder — auto-fix tier.

Transient auth failures (expired JWT, bad session) self-heal when the user
re-authenticates.  If the same tenant has 5+ auth failures in 1 hour, the
responder escalates it as a potential breach signal.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.base import IncidentResponder

logger = logging.getLogger(__name__)

BREACH_THRESHOLD = 5
BREACH_WINDOW_HOURS = 1


class AuthResponder(IncidentResponder):
    category = "auth"
    resolution_tier = "auto_fix"

    def handle(self, db: Session, incident: PlatformIncident) -> bool:
        from app.services.platform.platform_health_service import (
            calculate_tenant_health,
            create_notification,
            resolve_incident,
        )

        # Check frequency for the same tenant in the last hour
        cutoff = datetime.now(timezone.utc) - timedelta(hours=BREACH_WINDOW_HOURS)
        recent_auth_failures = (
            db.query(PlatformIncident)
            .filter(
                PlatformIncident.category == "auth",
                PlatformIncident.tenant_id == incident.tenant_id,
                PlatformIncident.created_at >= cutoff,
            )
            .count()
        )

        if recent_auth_failures >= BREACH_THRESHOLD:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    f"{recent_auth_failures} auth failures in 1 hour — "
                    "potential breach signal. Escalating for manual review."
                ),
                status="escalated",
            )
            create_notification(
                db=db,
                title="Auth anomaly detected",
                body=(
                    f"{recent_auth_failures} auth failures in 1 hour "
                    f"for tenant {incident.tenant_id}. "
                    "Manual review recommended."
                ),
                level="critical",
                tenant_id=incident.tenant_id,
                incident_id=str(incident.id),
            )
            return False

        # Transient auth failure — resolve
        resolve_incident(
            db=db,
            incident_id=str(incident.id),
            resolution_action=(
                "Auto-fix: transient auth failure. Session will self-heal "
                "on next user request. No action required."
            ),
            status="resolved",
        )

        if incident.tenant_id:
            calculate_tenant_health(db=db, tenant_id=incident.tenant_id)

        return True
