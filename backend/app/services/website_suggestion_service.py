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
    """Generate suggestion records from analysis results.

    Only generates suggestions for things that are genuinely optional —
    not obvious defaults. All Wilbert manufacturers sell burial vaults
    and urn vaults, so those are never suggested. The base manufacturing
    preset already includes vault ordering, so that's not suggested either.
    """
    suggestions: list[WebsiteIntelligenceSuggestion] = []

    # Skip list — things that are obvious for all Wilbert manufacturers
    # and should never appear as suggestions
    SKIP_PRODUCT_LINES = {
        "wilbert_burial_vaults", "burial_vaults", "wilbert_cremation_urn_vaults",
        "urn_vaults", "cremation_urn_vaults", "vaults", "burial_vault",
        "wilbert_products", "precast_products",
    }
    SKIP_VAULT_LINES = True  # All specific vault lines are handled by the catalog builder

    # Product line extensions — only suggest non-obvious product lines
    # (Redi-Rock, Rosetta, Wastewater are optional and worth suggesting)
    SUGGEST_EXTENSIONS = {
        "redi_rock": "Enable Redi-Rock Retaining Walls",
        "redi-rock": "Enable Redi-Rock Retaining Walls",
        "redi-rock_retaining_walls": "Enable Redi-Rock Retaining Walls",
        "rosetta": "Enable Rosetta Hardscapes",
        "rosetta_hardscapes": "Enable Rosetta Hardscapes",
        "wastewater": "Enable Wastewater Treatment Products",
        "wastewater_treatment": "Enable Wastewater Treatment Products",
        "septic": "Enable Wastewater Treatment Products",
    }

    for item in analysis_result.get("product_lines", []):
        conf = item.get("confidence", 0)
        if conf < THRESHOLDS["product_line"]:
            continue
        key = item["name"].lower().replace(" ", "_")
        # Skip obvious defaults
        if key in SKIP_PRODUCT_LINES:
            continue
        # Map to extension recommendations if applicable
        ext_label = None
        ext_key = None
        for match_key, label in SUGGEST_EXTENSIONS.items():
            if match_key in key:
                ext_label = label
                ext_key = match_key.replace("-", "_").split("_")[0]  # normalize to redi_rock, rosetta, wastewater
                break
        if ext_label:
            # Normalize extension keys
            if "redi" in ext_key:
                ext_key = "redi_rock"
            elif "rosetta" in ext_key:
                ext_key = "rosetta_hardscapes"
            elif "waste" in ext_key or "septic" in ext_key:
                ext_key = "wastewater_treatment"
            s = _create_suggestion(
                db, tenant_id, "extension_recommendation",
                key=ext_key,
                label=ext_label,
                confidence=conf,
                evidence=item.get("evidence"),
            )
            suggestions.append(s)

    # DO NOT generate vault line suggestions — all specific vault lines
    # are handled by the catalog builder, not the review screen

    # NPCA — only generate as an extension enable, not a certification claim
    npca = analysis_result.get("npca_certified", {})
    if npca.get("detected") and npca.get("confidence", 0) >= THRESHOLDS["npca_status"]:
        s = _create_suggestion(
            db, tenant_id, "extension_recommendation",
            key="npca_audit_prep",
            label="Enable NPCA Audit Prep",
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
            label="Enable Spring Burial Tracking",
            confidence=spring["confidence"],
            evidence=spring.get("evidence"),
        )
        suggestions.append(s)

    # DO NOT generate urn category suggestions — urns are handled
    # by the catalog builder urn step, not the review screen

    # Extension recommendations from AI analysis
    for item in analysis_result.get("recommended_extensions", []):
        conf = item.get("confidence", 0)
        if conf < THRESHOLDS["extension_recommendation"]:
            continue
        key = item.get("key", "")
        # Skip if we already added this extension above
        existing_keys = {s.suggestion_key for s in suggestions}
        if key in existing_keys:
            continue
        # Skip vault-related extensions — already covered
        if any(skip in key for skip in ["burial", "vault", "urn"]):
            continue
        s = _create_suggestion(
            db, tenant_id, "extension_recommendation",
            key=key,
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
