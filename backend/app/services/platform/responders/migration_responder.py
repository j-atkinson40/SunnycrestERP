"""Migration failure responder — auto-remediate tier.

Attempts `alembic downgrade -1` to roll back the last migration.  Never
attempts a second rollback for the same fingerprint — if the first downgrade
did not resolve the issue, escalation is the only safe path.

Creates critical notifications for every migration incident.
"""

import logging
import subprocess
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.base import IncidentResponder

logger = logging.getLogger(__name__)


class MigrationResponder(IncidentResponder):
    category = "migration"
    resolution_tier = "auto_remediate"

    def handle(self, db: Session, incident: PlatformIncident) -> bool:
        from app.services.platform.platform_health_service import (
            calculate_all_tenant_health,
            create_notification,
            resolve_incident,
        )

        # ── Guard: never rollback same fingerprint twice ─────────────
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        prior_rollback = (
            db.query(PlatformIncident)
            .filter(
                PlatformIncident.fingerprint == incident.fingerprint,
                PlatformIncident.created_at >= cutoff,
                PlatformIncident.id != incident.id,
                PlatformIncident.resolution_action.isnot(None),
                PlatformIncident.resolution_action.contains("downgrade"),
            )
            .first()
        )

        if prior_rollback:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    "Rollback already attempted for this migration. "
                    "Refusing to downgrade again. Escalating."
                ),
                status="escalated",
            )
            create_notification(
                db=db,
                title="Migration rollback refused — repeat failure",
                body=(
                    "A prior rollback for this migration was already attempted. "
                    "Manual intervention required."
                ),
                level="critical",
                tenant_id=incident.tenant_id,
                incident_id=str(incident.id),
            )
            return False

        # ── Attempt alembic downgrade -1 ─────────────────────────────
        try:
            result = subprocess.run(
                ["alembic", "downgrade", "-1"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=None,  # Uses current working directory
            )
            downgrade_success = result.returncode == 0
            downgrade_output = result.stdout or result.stderr
        except subprocess.TimeoutExpired:
            downgrade_success = False
            downgrade_output = "Alembic downgrade timed out after 120 seconds."
        except Exception as e:
            downgrade_success = False
            downgrade_output = str(e)

        if not downgrade_success:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    f"Alembic downgrade -1 failed: "
                    f"{downgrade_output[:500]}. Escalating."
                ),
                status="escalated",
            )
            create_notification(
                db=db,
                title="Migration rollback failed",
                body=(
                    "Automatic alembic downgrade -1 failed. "
                    "Manual intervention required.\n"
                    f"Output: {downgrade_output[:300]}"
                ),
                level="critical",
                tenant_id=incident.tenant_id,
                incident_id=str(incident.id),
            )
            return False

        # ── Downgrade succeeded ──────────────────────────────────────
        resolve_incident(
            db=db,
            incident_id=str(incident.id),
            resolution_action=(
                f"Auto-remediate: alembic downgrade -1 completed. "
                f"Output: {downgrade_output[:300]}"
            ),
            status="resolved",
        )
        create_notification(
            db=db,
            title="Migration rolled back successfully",
            body=(
                "Automatic migration rollback (downgrade -1) succeeded. "
                "Review the migration before re-applying."
            ),
            level="warning",
            tenant_id=incident.tenant_id,
            incident_id=str(incident.id),
        )

        calculate_all_tenant_health(db=db)

        return True
