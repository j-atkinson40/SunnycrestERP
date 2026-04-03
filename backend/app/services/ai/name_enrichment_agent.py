"""Name enrichment agent — finds shorthand names and suggests complete professional names."""

import json
import logging
import time
import uuid as _uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.ai_name_suggestion import AiNameSuggestion
from app.models.company_entity import CompanyEntity
from app.services import ai_settings_service

logger = logging.getLogger(__name__)

CEMETERY_SUFFIXES = ["cemetery", "memorial gardens", "memorial park", "burial ground", "memorial", "gardens", "lawn", "park", "mausoleum"]
FH_SUFFIXES = ["funeral home", "funeral chapel", "funeral service", "funeral parlor", "mortuary", "chapels", "chapel", "cremation service", "cremation services", "funeral & cremation", "memorial home", "& sons", "& son", "& daughters"]


def is_shorthand_name(name: str, customer_type: str | None) -> bool:
    """Check if a name appears incomplete for its type. Only checks cemeteries and funeral homes."""
    if customer_type not in ("cemetery", "funeral_home"):
        return False

    name_lower = name.lower().strip()
    if len(name_lower) < 3:
        return False

    if customer_type == "cemetery":
        return not any(s in name_lower for s in CEMETERY_SUFFIXES)
    elif customer_type == "funeral_home":
        return not any(s in name_lower for s in FH_SUFFIXES)

    return False


def enrich_company_name(db: Session, entity: CompanyEntity, use_google_places: bool = True) -> AiNameSuggestion | None:
    """Try to find the complete professional name for a shorthand company name."""
    if getattr(entity, "customer_type", None) not in ("cemetery", "funeral_home"):
        return None

    if not is_shorthand_name(entity.name, entity.customer_type):
        return None

    # Check for existing pending or rejected suggestion
    existing = db.query(AiNameSuggestion).filter(
        AiNameSuggestion.master_company_id == entity.id,
        AiNameSuggestion.status.in_(["pending", "rejected"]),
    ).first()
    if existing:
        return None

    suggested_name = None
    confidence = Decimal("0")
    source = None
    source_details = {}
    suggested_fields: dict = {}

    # Google Places lookup
    if use_google_places:
        try:
            from app.config import settings as app_settings
            api_key = app_settings.GOOGLE_PLACES_API_KEY
            if api_key:
                suffix = "Cemetery" if entity.customer_type == "cemetery" else "Funeral Home"
                query = f"{entity.name} {suffix} {entity.city or ''} {entity.state or ''}".strip()

                import httpx
                resp = httpx.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json",
                    params={"query": query, "key": api_key},
                    timeout=10,
                )
                data = resp.json()
                results = data.get("results", [])

                ai_settings_service.track_usage(db, entity.company_id, "google_places")

                if results:
                    place = results[0]
                    google_name = place.get("name", "")

                    # Verify it's not the exact same shorthand name
                    if google_name.lower().strip() != entity.name.lower().strip():
                        suggested_name = google_name
                        confidence = Decimal("0.88")
                        source = "google_places"
                        source_details = {
                            "place_id": place.get("place_id"),
                            "google_name": google_name,
                            "google_types": place.get("types", []),
                        }

                        # Get address from place
                        addr = place.get("formatted_address", "")
                        if addr:
                            parts = addr.split(",")
                            if len(parts) >= 2:
                                suggested_fields["address_line1"] = parts[0].strip()
                                city_state = parts[1].strip() if len(parts) > 1 else ""
                                if city_state:
                                    suggested_fields["city"] = city_state.split(" ")[0] if " " in city_state else city_state

                        # Try Place Details for phone/website
                        try:
                            detail_resp = httpx.get(
                                "https://maps.googleapis.com/maps/api/place/details/json",
                                params={
                                    "place_id": place["place_id"],
                                    "fields": "formatted_phone_number,website",
                                    "key": api_key,
                                },
                                timeout=10,
                            )
                            detail_data = detail_resp.json().get("result", {})
                            if detail_data.get("formatted_phone_number"):
                                suggested_fields["phone"] = detail_data["formatted_phone_number"]
                            if detail_data.get("website"):
                                suggested_fields["website"] = detail_data["website"]
                            ai_settings_service.track_usage(db, entity.company_id, "google_places")
                        except Exception:
                            pass

        except Exception:
            logger.exception("Google Places lookup failed for %s", entity.name)

    # Claude fallback
    if not suggested_name or confidence < Decimal("0.70"):
        try:
            from app.services.ai_service import call_anthropic
            suffix_type = "cemetery" if entity.customer_type == "cemetery" else "funeral home"
            prompt = f"""A precast concrete manufacturer has a {suffix_type} in their CRM with the shorthand name "{entity.name}".
Location: {entity.city or 'unknown'}, {entity.state or 'unknown'}

What is the most likely complete professional name? Add "Cemetery", "Memorial Gardens", "Funeral Home" etc as appropriate.
Return JSON only: {{"suggested_name": "...", "confidence": 0.0-1.0, "reasoning": "..."}}"""

            response = call_anthropic(prompt, max_tokens=100)
            if response:
                claude_data = json.loads(response)
                claude_name = claude_data.get("suggested_name", "")
                claude_conf = float(claude_data.get("confidence", 0.5))

                if claude_name and claude_name.lower() != entity.name.lower():
                    if not suggested_name:
                        suggested_name = claude_name
                        confidence = Decimal(str(round(claude_conf * 0.85, 3)))
                        source = "claude_inference"
                        source_details = {"reasoning": claude_data.get("reasoning", "")}
                    elif claude_name.lower() == suggested_name.lower():
                        # Claude agrees with Google — boost confidence
                        confidence = min(Decimal("0.99"), confidence + Decimal("0.07"))
                        source_details["claude_agrees"] = True
        except Exception:
            logger.exception("Claude name inference failed for %s", entity.name)

    if not suggested_name or suggested_name.lower() == entity.name.lower():
        return None

    suggestion = AiNameSuggestion(
        id=str(_uuid.uuid4()),
        tenant_id=entity.company_id,
        master_company_id=entity.id,
        current_name=entity.name,
        current_city=entity.city,
        current_state=entity.state,
        current_address=entity.address_line1,
        suggested_name=suggested_name,
        suggested_address_line1=suggested_fields.get("address_line1"),
        suggested_city=suggested_fields.get("city"),
        suggested_state=suggested_fields.get("state"),
        suggested_zip=suggested_fields.get("zip"),
        suggested_phone=suggested_fields.get("phone"),
        suggested_website=suggested_fields.get("website"),
        suggestion_source=source,
        google_places_id=source_details.get("place_id"),
        confidence=confidence,
        source_details=source_details,
    )
    db.add(suggestion)
    return suggestion


def run_name_enrichment(db: Session, tenant_id: str) -> dict:
    """Run name enrichment agent for all shorthand-named cemeteries and funeral homes."""
    stats = {"processed": 0, "suggestions_created": 0, "errors": 0, "by_type": {"cemetery": 0, "funeral_home": 0}}

    # Ensure table exists
    try:
        db.execute(text("SELECT 1 FROM ai_name_suggestions LIMIT 0"))
    except Exception:
        db.rollback()
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_name_suggestions (
                id VARCHAR(36) PRIMARY KEY, tenant_id VARCHAR(36) NOT NULL,
                master_company_id VARCHAR(36) NOT NULL, current_name VARCHAR(500) NOT NULL,
                current_city VARCHAR(200), current_state VARCHAR(100), current_address VARCHAR(500),
                suggested_name VARCHAR(500), suggested_address_line1 VARCHAR(500),
                suggested_city VARCHAR(200), suggested_state VARCHAR(100), suggested_zip VARCHAR(20),
                suggested_phone VARCHAR(50), suggested_website VARCHAR(500),
                suggestion_source VARCHAR(30), google_places_id VARCHAR(200),
                confidence DECIMAL(4,3), source_details JSONB,
                status VARCHAR(20) DEFAULT 'pending', reviewed_by VARCHAR(36),
                reviewed_at TIMESTAMPTZ, applied_name VARCHAR(500),
                created_at TIMESTAMPTZ DEFAULT now())
        """))
        db.commit()

    companies = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == tenant_id,
            CompanyEntity.customer_type.in_(["cemetery", "funeral_home"]),
            CompanyEntity.is_active == True,
        )
        .order_by(CompanyEntity.name)
        .all()
    )

    for company in companies:
        try:
            result = enrich_company_name(db, company, use_google_places=True)
            stats["processed"] += 1
            if result:
                stats["suggestions_created"] += 1
                stats["by_type"][company.customer_type or "other"] = stats["by_type"].get(company.customer_type or "other", 0) + 1

            if stats["processed"] % 50 == 0:
                db.commit()
                logger.info("Name enrichment: %d processed, %d suggestions", stats["processed"], stats["suggestions_created"])

            time.sleep(0.2)  # Rate limit
        except Exception:
            stats["errors"] += 1
            logger.exception("Name enrichment failed for %s", company.name)

    db.commit()
    return stats
