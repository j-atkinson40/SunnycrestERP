"""Website suggestion service — generates and manages onboarding suggestions."""

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.website_intelligence import (
    TenantWebsiteIntelligence,
    WebsiteIntelligenceSuggestion,
)

logger = logging.getLogger(__name__)

# Confidence thresholds by suggestion type
THRESHOLDS = {
    "extension_recommendation": 0.70,
    "vault_line": 0.75,
    "npca_status": 0.85,
    "spring_burial": 0.80,
    "product_line": 0.70,
}


def _confidence_label(score: float) -> str:
    """Return human-readable confidence label."""
    if score >= 0.85:
        return "High confidence"
    if score >= 0.70:
        return "Likely"
    return "Possible"


def _create_suggestion(
    db: Session,
    tenant_id: str,
    suggestion_type: str,
    key: str,
    label: str,
    confidence: float,
    evidence: str | None = None,
) -> WebsiteIntelligenceSuggestion:
    """Create a single suggestion record."""
    suggestion = WebsiteIntelligenceSuggestion(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        suggestion_type=suggestion_type,
        suggestion_key=key,
        suggestion_label=label,
        confidence=Decimal(str(round(confidence, 2))),
        evidence=evidence,
        status="pending",
    )
    db.add(suggestion)
    return suggestion


def generate_suggestions(
    db: Session, tenant_id: str, analysis_result: dict
) -> list[WebsiteIntelligenceSuggestion]:
    """Generate suggestion records from analysis results."""
    suggestions: list[WebsiteIntelligenceSuggestion] = []

    # Product lines
    for item in analysis_result.get("product_lines", []):
        conf = item.get("confidence", 0)
        if conf >= THRESHOLDS["product_line"]:
            s = _create_suggestion(
                db, tenant_id, "product_line",
                key=item["name"].lower().replace(" ", "_"),
                label=item["name"],
                confidence=conf,
                evidence=item.get("evidence"),
            )
            suggestions.append(s)

    # Vault lines
    for item in analysis_result.get("vault_lines", []):
        conf = item.get("confidence", 0)
        if conf >= THRESHOLDS["vault_line"]:
            s = _create_suggestion(
                db, tenant_id, "vault_line",
                key=item["name"].lower().replace(" ", "_"),
                label=item["name"],
                confidence=conf,
                evidence=item.get("evidence"),
            )
            suggestions.append(s)

    # NPCA certification
    npca = analysis_result.get("npca_certified", {})
    if npca.get("detected") and npca.get("confidence", 0) >= THRESHOLDS["npca_status"]:
        s = _create_suggestion(
            db, tenant_id, "npca_status",
            key="npca_certified",
            label="NPCA Certified",
            confidence=npca["confidence"],
            evidence=npca.get("evidence"),
        )
        suggestions.append(s)

    # Spring burials
    spring = analysis_result.get("spring_burials", {})
    if spring.get("detected") and spring.get("confidence", 0) >= THRESHOLDS["spring_burial"]:
        s = _create_suggestion(
            db, tenant_id, "spring_burial",
            key="spring_burial_program",
            label="Spring Burial Program",
            confidence=spring["confidence"],
            evidence=spring.get("evidence"),
        )
        suggestions.append(s)

    # Urn categories
    for item in analysis_result.get("urn_categories", []):
        conf = item.get("confidence", 0)
        if conf >= THRESHOLDS["product_line"]:
            s = _create_suggestion(
                db, tenant_id, "product_line",
                key=f"urn_{item['name'].lower().replace(' ', '_')}",
                label=item["name"],
                confidence=conf,
                evidence=item.get("evidence"),
            )
            suggestions.append(s)

    # Extension recommendations from AI
    for item in analysis_result.get("recommended_extensions", []):
        conf = item.get("confidence", 0)
        if conf >= THRESHOLDS["extension_recommendation"]:
            s = _create_suggestion(
                db, tenant_id, "extension_recommendation",
                key=item["key"],
                label=f"Enable {item['key'].replace('_', ' ').title()}",
                confidence=conf,
                evidence=item.get("reason"),
            )
            suggestions.append(s)

    db.flush()
    return suggestions


def get_suggestions(db: Session, tenant_id: str) -> list[WebsiteIntelligenceSuggestion]:
    """Get all suggestions for a tenant."""
    return (
        db.query(WebsiteIntelligenceSuggestion)
        .filter(WebsiteIntelligenceSuggestion.tenant_id == tenant_id)
        .order_by(WebsiteIntelligenceSuggestion.confidence.desc())
        .all()
    )


def update_suggestion(
    db: Session, suggestion_id: str, status: str
) -> WebsiteIntelligenceSuggestion:
    """Accept or dismiss a suggestion."""
    suggestion = (
        db.query(WebsiteIntelligenceSuggestion)
        .filter(WebsiteIntelligenceSuggestion.id == suggestion_id)
        .first()
    )
    if not suggestion:
        raise ValueError(f"Suggestion {suggestion_id} not found")

    now = datetime.now(timezone.utc)
    suggestion.status = status
    if status == "accepted":
        suggestion.accepted_at = now
    elif status == "dismissed":
        suggestion.dismissed_at = now

    db.flush()
    return suggestion


def get_suggestions_for_extension(
    db: Session, tenant_id: str, extension_key: str
) -> list[WebsiteIntelligenceSuggestion]:
    """Get accepted suggestions relevant to a specific extension."""
    return (
        db.query(WebsiteIntelligenceSuggestion)
        .filter(
            WebsiteIntelligenceSuggestion.tenant_id == tenant_id,
            WebsiteIntelligenceSuggestion.status == "accepted",
            WebsiteIntelligenceSuggestion.suggestion_key == extension_key,
        )
        .all()
    )


def get_intelligence(db: Session, tenant_id: str) -> TenantWebsiteIntelligence | None:
    """Get the full intelligence record for a tenant."""
    return (
        db.query(TenantWebsiteIntelligence)
        .filter(TenantWebsiteIntelligence.tenant_id == tenant_id)
        .first()
    )


def mark_applied(db: Session, tenant_id: str) -> None:
    """Mark suggestions as applied to onboarding."""
    intel = get_intelligence(db, tenant_id)
    if intel:
        intel.applied_to_onboarding = True
        intel.tenant_confirmed_at = datetime.now(timezone.utc)
        db.flush()
