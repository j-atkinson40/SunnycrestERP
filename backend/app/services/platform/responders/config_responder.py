"""Config drift responder — auto-remediate tier.

Detects when a tenant's module configuration has diverged from their assigned
vertical preset and reapplies the preset defaults.  Always creates a
notification so the operator sees what was changed.
"""

import logging

from sqlalchemy.orm import Session

from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.base import IncidentResponder

logger = logging.getLogger(__name__)


class ConfigResponder(IncidentResponder):
    category = "config"
    resolution_tier = "auto_remediate"

    def handle(self, db: Session, incident: PlatformIncident) -> bool:
        from app.models.company import Company
        from app.services.platform.platform_health_service import (
            calculate_tenant_health,
            create_notification,
            resolve_incident,
        )
        from app.services.tenant_module_service import apply_preset_to_tenant

        if not incident.tenant_id:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    "No tenant_id on config incident. "
                    "Cannot determine preset. Escalating."
                ),
                status="escalated",
            )
            return False

        # Load tenant
        tenant = (
            db.query(Company)
            .filter(Company.id == incident.tenant_id)
            .first()
        )

        if not tenant:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    f"Tenant {incident.tenant_id} not found. Escalating."
                ),
                status="escalated",
            )
            return False

        # Get preset name from tenant.vertical column
        preset_name = getattr(tenant, "vertical", None)

        if not preset_name:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    "Tenant has no assigned vertical/preset. "
                    "Cannot reset config. Escalating."
                ),
                status="escalated",
            )
            return False

        # Apply preset defaults — resets module config
        try:
            result = apply_preset_to_tenant(
                db=db,
                tenant_id=incident.tenant_id,
                preset_key=preset_name,
            )
            modules_enabled = result.get("modules_enabled", 0)
            changes_summary = (
                f"{modules_enabled} modules enabled from {preset_name} preset"
            )
        except Exception as e:
            resolve_incident(
                db=db,
                incident_id=str(incident.id),
                resolution_action=(
                    f"Failed to apply preset {preset_name}: {str(e)}. "
                    "Escalating."
                ),
                status="escalated",
            )
            return False

        # Resolve incident
        resolve_incident(
            db=db,
            incident_id=str(incident.id),
            resolution_action=(
                f"Auto-remediate: preset {preset_name} reapplied to "
                f"tenant {incident.tenant_id}. {changes_summary}"
            ),
            status="resolved",
        )

        # Always notify for config changes
        create_notification(
            db=db,
            title=f"Config reset — {preset_name} preset reapplied",
            body=(
                f"Tenant {incident.tenant_id} config drift detected "
                f"and corrected.\n{changes_summary}"
            ),
            level="warning",
            tenant_id=incident.tenant_id,
            incident_id=str(incident.id),
        )

        calculate_tenant_health(db=db, tenant_id=incident.tenant_id)

        return True
