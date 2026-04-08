"""Incident dispatcher — scans pending auto_fix / auto_remediate incidents
and routes them to the appropriate responder.

Called every 15 minutes by the scheduler.
"""

import logging

from sqlalchemy.orm import Session

from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.registry import get_responder_for

logger = logging.getLogger(__name__)


def dispatch_pending_incidents(db: Session) -> dict:
    """Find all pending auto-fixable incidents and attempt to resolve them.

    Returns a summary dict for logging.
    """
    pending = (
        db.query(PlatformIncident)
        .filter(
            PlatformIncident.resolution_status == "pending",
            PlatformIncident.resolution_tier.in_(["auto_fix", "auto_remediate"]),
        )
        .order_by(PlatformIncident.created_at.asc())
        .all()
    )

    results = {
        "total": len(pending),
        "resolved": 0,
        "escalated": 0,
        "no_handler": 0,
        "errors": 0,
    }

    for incident in pending:
        responder = get_responder_for(incident)

        if not responder:
            results["no_handler"] += 1
            continue

        success = responder.safe_handle(db, incident)

        if success:
            results["resolved"] += 1
        else:
            # Check if the responder escalated it
            db.refresh(incident)
            if incident.resolution_status == "escalated":
                results["escalated"] += 1
            else:
                results["errors"] += 1

    return results
