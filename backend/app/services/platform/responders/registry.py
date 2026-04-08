"""Responder registry — maps incident types to their auto-fix handlers.

Add one line per new responder type.
"""

from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.background_job_responder import (
    BackgroundJobResponder,
)
from app.services.platform.responders.base import IncidentResponder

RESPONDER_REGISTRY: list[IncidentResponder] = [
    BackgroundJobResponder(),
]


def get_responder_for(incident: PlatformIncident) -> IncidentResponder | None:
    """Return the first responder that can handle the incident, or None."""
    for responder in RESPONDER_REGISTRY:
        if responder.can_handle(incident):
            return responder
    return None
