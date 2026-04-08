"""API contract violation responder — escalate tier.

API contract mismatches (frontend/backend schema drift after deploy) cannot
be auto-fixed.  This responder creates a structured escalation with as much
detail as possible extracted from the incident context, then creates a
notification for the operator dashboard.
"""

import logging
import re

from sqlalchemy.orm import Session

from app.models.platform_incident import PlatformIncident
from app.services.platform.responders.base import IncidentResponder

logger = logging.getLogger(__name__)


class ApiContractResponder(IncidentResponder):
    category = "api_contract"
    resolution_tier = "escalate"

    def can_handle(self, incident: PlatformIncident) -> bool:
        """API contract responder handles escalate-tier incidents too,
        but ONLY for the api_contract category."""
        return (
            incident.category == self.category
            and incident.resolution_status == "pending"
        )

    def handle(self, db: Session, incident: PlatformIncident) -> bool:
        from app.services.platform.platform_health_service import (
            calculate_tenant_health,
            create_notification,
            resolve_incident,
        )

        # ── Extract route info from context or error message ─────────
        ctx = incident.context or {}
        route = ctx.get("route") or ctx.get("endpoint") or ""
        method = ctx.get("method", "").upper()
        status_code = ctx.get("status_code", "")
        expected_schema = ctx.get("expected_schema", "")
        actual_response = ctx.get("actual_response", "")

        # Try to extract route from error message if not in context
        if not route and incident.error_message:
            route_match = re.search(
                r"(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)",
                incident.error_message,
            )
            if route_match:
                method = method or route_match.group(1)
                route = route or route_match.group(2)

        # Build structured details
        details_parts = []
        if method and route:
            details_parts.append(f"Endpoint: {method} {route}")
        elif route:
            details_parts.append(f"Endpoint: {route}")
        if status_code:
            details_parts.append(f"Status: {status_code}")
        if expected_schema:
            details_parts.append(
                f"Expected: {str(expected_schema)[:200]}"
            )
        if actual_response:
            details_parts.append(
                f"Actual: {str(actual_response)[:200]}"
            )

        details = "\n".join(details_parts) if details_parts else "No details"

        # ── Escalate with structured info ────────────────────────────
        resolve_incident(
            db=db,
            incident_id=str(incident.id),
            resolution_action=(
                f"API contract violation escalated.\n{details}\n"
                "Manual fix required — frontend/backend schema mismatch."
            ),
            status="escalated",
        )

        # ── Always notify ────────────────────────────────────────────
        notification_body = (
            f"API contract mismatch detected.\n{details}\n"
            f"Error: {(incident.error_message or '')[:300]}"
        )

        create_notification(
            db=db,
            title=f"API contract violation — {method} {route}" if route
            else "API contract violation detected",
            body=notification_body,
            level="critical",
            tenant_id=incident.tenant_id,
            incident_id=str(incident.id),
        )

        if incident.tenant_id:
            calculate_tenant_health(db=db, tenant_id=incident.tenant_id)

        return False  # Escalations always return False
