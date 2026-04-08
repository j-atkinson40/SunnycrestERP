"""Base class for incident responders.

Subclasses set `category` and `resolution_tier` to declare which incidents
they handle, then implement `handle()` with the fix logic.  `safe_handle()`
wraps `handle()` so a responder crash never propagates.
"""

import logging

from sqlalchemy.orm import Session

from app.models.platform_incident import PlatformIncident

logger = logging.getLogger(__name__)


class IncidentResponder:
    """Abstract base for auto-fix / auto-remediate responders."""

    category: str | None = None
    resolution_tier: str | None = None

    def can_handle(self, incident: PlatformIncident) -> bool:
        """Return True if this responder knows how to handle the incident."""
        return (
            incident.category == self.category
            and incident.resolution_tier == self.resolution_tier
            and incident.resolution_status == "pending"
        )

    def handle(self, db: Session, incident: PlatformIncident) -> bool:
        """Attempt to resolve the incident.  Return True if resolved."""
        raise NotImplementedError

    def safe_handle(self, db: Session, incident: PlatformIncident) -> bool:
        """Wrap handle() — never raises, self-reports failures."""
        try:
            return self.handle(db, incident)
        except Exception as e:
            logger.error(
                f"Responder {self.__class__.__name__} failed for "
                f"incident {incident.id}: {e}",
                exc_info=True,
            )
            try:
                from app.services.platform.platform_health_service import (
                    log_incident,
                )

                log_incident(
                    db=db,
                    category="background_job",
                    severity="medium",
                    source="background_job",
                    error_message=(
                        f"Responder {self.__class__.__name__} failed for "
                        f"incident {incident.id}: {str(e)}"
                    ),
                    tenant_id=incident.tenant_id,
                    context={"original_incident_id": str(incident.id)},
                )
            except Exception:
                pass
            return False
