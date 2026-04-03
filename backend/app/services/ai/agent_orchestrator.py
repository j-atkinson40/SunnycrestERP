"""AI Agent Orchestrator — runs all background AI agents nightly/weekly."""

import logging
import uuid as _uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import ai_settings_service

logger = logging.getLogger(__name__)


def _log_run(db: Session, tenant_id: str, agent_name: str, started: datetime, records: int, summary: dict | None, error: str | None = None):
    """Log an agent run."""
    try:
        db.execute(text(
            "INSERT INTO ai_agent_runs (id, tenant_id, agent_name, started_at, completed_at, status, records_processed, results_summary, error_message) "
            "VALUES (:id, :tid, :name, :start, :end, :status, :rec, :summary, :err)"
        ), {
            "id": str(_uuid.uuid4()), "tid": tenant_id, "name": agent_name,
            "start": started, "end": datetime.now(timezone.utc),
            "status": "error" if error else "complete",
            "rec": records, "summary": str(summary) if summary else None, "err": error,
        })
    except Exception:
        logger.exception("Failed to log agent run")


def _ensure_agent_tables(db: Session) -> None:
    """Create agent tables if they don't exist."""
    tables = [
        """CREATE TABLE IF NOT EXISTS duplicate_reviews (
            id VARCHAR(36) PRIMARY KEY, tenant_id VARCHAR(36) NOT NULL,
            company_id_a VARCHAR(36) NOT NULL, company_id_b VARCHAR(36) NOT NULL,
            similarity_score DECIMAL(4,3), claude_confidence DECIMAL(4,3),
            claude_reasoning TEXT, status VARCHAR(20) DEFAULT 'pending',
            resolved_by VARCHAR(36), resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now())""",
        """CREATE TABLE IF NOT EXISTS ai_upsell_insights (
            id VARCHAR(36) PRIMARY KEY, tenant_id VARCHAR(36) NOT NULL,
            master_company_id VARCHAR(36), insight_type VARCHAR(50),
            description TEXT, generated_at TIMESTAMPTZ DEFAULT now(),
            dismissed BOOLEAN DEFAULT false, dismissed_at TIMESTAMPTZ,
            converted BOOLEAN DEFAULT false, converted_at TIMESTAMPTZ)""",
        """CREATE TABLE IF NOT EXISTS ai_rescue_drafts (
            id VARCHAR(36) PRIMARY KEY, tenant_id VARCHAR(36) NOT NULL,
            master_company_id VARCHAR(36), subject TEXT, body TEXT,
            generated_at TIMESTAMPTZ DEFAULT now(), status VARCHAR(20) DEFAULT 'pending',
            sent_at TIMESTAMPTZ, sent_by VARCHAR(36), edited_body TEXT)""",
        """CREATE TABLE IF NOT EXISTS ai_agent_runs (
            id VARCHAR(36) PRIMARY KEY, tenant_id VARCHAR(36) NOT NULL,
            agent_name VARCHAR(100), started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
            status VARCHAR(20), records_processed INTEGER,
            results_summary JSONB, error_message TEXT)""",
    ]
    for sql in tables:
        try:
            db.execute(text(sql))
        except Exception:
            db.rollback()
    # Add relationship score columns if missing
    for col in [
        "ALTER TABLE manufacturer_company_profiles ADD COLUMN IF NOT EXISTS relationship_score INTEGER",
        "ALTER TABLE manufacturer_company_profiles ADD COLUMN IF NOT EXISTS relationship_score_breakdown JSONB",
        "ALTER TABLE manufacturer_company_profiles ADD COLUMN IF NOT EXISTS relationship_score_calculated_at TIMESTAMPTZ",
    ]:
        try:
            db.execute(text(col))
        except Exception:
            db.rollback()
    try:
        db.commit()
    except Exception:
        db.rollback()


def run_nightly_agents(db: Session, tenant_id: str) -> dict:
    """Run all nightly AI agents for a tenant."""
    _ensure_agent_tables(db)
    results = {}

    agents = [
        ("duplicate_detection", duplicate_detection_agent),
        ("auto_enrichment", auto_enrichment_agent),
        ("relationship_scoring", relationship_scoring_agent),
        ("upsell_detector", upsell_detector_agent),
        ("account_rescue", account_rescue_agent),
    ]

    for name, func in agents:
        started = datetime.now(timezone.utc)
        try:
            result = func(db, tenant_id)
            results[name] = result
            db.commit()
            _log_run(db, tenant_id, name, started, result.get("processed", 0), result)
            db.commit()
        except Exception as e:
            db.rollback()  # Critical: clear failed transaction state
            logger.exception("Agent %s failed for tenant %s", name, tenant_id)
            results[name] = {"error": str(e)}
            try:
                _log_run(db, tenant_id, name, started, 0, None, str(e))
                db.commit()
            except Exception:
                db.rollback()

    db.commit()
    return results


def run_weekly_agents(db: Session, tenant_id: str) -> dict:
    """Run weekly AI agents."""
    results = {}
    for name, func in [("relationship_scoring", relationship_scoring_agent)]:
        started = datetime.now(timezone.utc)
        try:
            result = func(db, tenant_id)
            results[name] = result
            _log_run(db, tenant_id, name, started, result.get("processed", 0), result)
        except Exception as e:
            results[name] = {"error": str(e)}
            _log_run(db, tenant_id, name, started, 0, None, str(e))
    db.commit()
    return results


# ── Individual Agents ────────────────────────────────────────────────────────

def duplicate_detection_agent(db: Session, tenant_id: str) -> dict:
    """Find potential duplicate company records."""
    if not ai_settings_service.is_enabled(db, tenant_id, "duplicate_detection"):
        return {"skipped": True}

    try:
        rows = db.execute(text("""
            SELECT a.id as id_a, a.name as name_a, b.id as id_b, b.name as name_b,
                   SIMILARITY(a.name, b.name) as score
            FROM company_entities a
            JOIN company_entities b ON a.id < b.id AND a.company_id = b.company_id
                AND SIMILARITY(a.name, b.name) > 0.75
            WHERE a.company_id = :tid AND a.is_active = true AND b.is_active = true
            LIMIT 20
        """), {"tid": tenant_id}).fetchall()
    except Exception:
        rows = []

    created = 0
    for row in rows:
        existing = db.execute(text(
            "SELECT id FROM duplicate_reviews WHERE tenant_id = :tid AND company_id_a = :a AND company_id_b = :b"
        ), {"tid": tenant_id, "a": row.id_a, "b": row.id_b}).fetchone()
        if not existing:
            db.execute(text(
                "INSERT INTO duplicate_reviews (id, tenant_id, company_id_a, company_id_b, similarity_score) "
                "VALUES (:id, :tid, :a, :b, :score)"
            ), {"id": str(_uuid.uuid4()), "tid": tenant_id, "a": row.id_a, "b": row.id_b, "score": float(row.score)})
            created += 1

    return {"processed": len(rows), "duplicates_found": created}


def auto_enrichment_agent(db: Session, tenant_id: str) -> dict:
    """Fill missing company data from Google Places."""
    if not ai_settings_service.is_enabled(db, tenant_id, "auto_enrichment"):
        return {"skipped": True}

    from app.models.company_entity import CompanyEntity
    companies = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == tenant_id,
            CompanyEntity.is_active == True,
            CompanyEntity.google_places_id.is_(None),
        )
        .filter(
            (CompanyEntity.phone.is_(None)) | (CompanyEntity.website.is_(None))
        )
        .limit(20)
        .all()
    )

    enriched = 0
    for company in companies:
        try:
            from app.config import settings as app_settings
            api_key = app_settings.GOOGLE_PLACES_API_KEY
            if not api_key:
                break

            import httpx, time
            query = f"{company.name} {company.city or ''} {company.state or ''}"
            resp = httpx.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": query, "key": api_key},
                timeout=10,
            )
            data = resp.json()
            results = data.get("results", [])

            if results:
                place = results[0]
                company.google_places_id = place.get("place_id")
                if not company.phone and place.get("formatted_phone_number"):
                    company.phone = place["formatted_phone_number"]
                    enriched += 1
                if not company.website and place.get("website"):
                    company.website = place["website"]
                    enriched += 1

            ai_settings_service.track_usage(db, tenant_id, "google_places")
            time.sleep(0.2)
        except Exception:
            logger.exception("Enrichment failed for %s", company.name)

    return {"processed": len(companies), "enriched": enriched}


def relationship_scoring_agent(db: Session, tenant_id: str) -> dict:
    """Calculate relationship strength scores."""
    if not ai_settings_service.is_enabled(db, tenant_id, "relationship_scoring"):
        return {"skipped": True}

    from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
    profiles = db.query(ManufacturerCompanyProfile).filter(
        ManufacturerCompanyProfile.company_id == tenant_id,
    ).all()

    scored = 0
    for profile in profiles:
        try:
            # Simple scoring based on available data
            score_parts = {}

            # Order consistency (30%)
            if profile.order_count_12mo and profile.order_count_12mo > 0:
                score_parts["consistency"] = min(100, profile.order_count_12mo * 8)
            else:
                score_parts["consistency"] = 10

            # Payment reliability (25%)
            if profile.avg_days_to_pay_recent:
                days = float(profile.avg_days_to_pay_recent)
                score_parts["payment"] = max(10, 100 - (days * 2))
            else:
                score_parts["payment"] = 50

            # Growth (15%)
            if profile.total_revenue_12mo and profile.total_revenue_12mo > 0:
                score_parts["growth"] = min(100, float(profile.total_revenue_12mo) / 500)
            else:
                score_parts["growth"] = 20

            # Loyalty (10%)
            from app.models.company_entity import CompanyEntity
            entity = db.query(CompanyEntity).filter(CompanyEntity.id == profile.master_company_id).first()
            if entity and getattr(entity, "first_order_year", None):
                years = datetime.now().year - entity.first_order_year
                score_parts["loyalty"] = min(100, years * 15)
            else:
                score_parts["loyalty"] = 20

            # Communication (20%) - based on activity count
            try:
                activity_count = db.execute(text(
                    "SELECT COUNT(*) FROM activity_log WHERE master_company_id = :cid"
                ), {"cid": profile.master_company_id}).scalar() or 0
                score_parts["communication"] = min(100, activity_count * 15)
            except Exception:
                score_parts["communication"] = 20

            final = int(
                score_parts["consistency"] * 0.30 +
                score_parts["payment"] * 0.25 +
                score_parts["communication"] * 0.20 +
                score_parts["growth"] * 0.15 +
                score_parts["loyalty"] * 0.10
            )

            profile.relationship_score = min(100, max(0, final))
            profile.relationship_score_breakdown = score_parts
            profile.relationship_score_calculated_at = datetime.now(timezone.utc)
            scored += 1
        except Exception:
            logger.exception("Scoring failed for %s", profile.master_company_id)

    return {"processed": len(profiles), "scored": scored}


def upsell_detector_agent(db: Session, tenant_id: str) -> dict:
    """Detect upsell opportunities."""
    if not ai_settings_service.is_enabled(db, tenant_id, "upsell_detector"):
        return {"skipped": True}

    # Simple: find high-volume customers (placeholder for deeper analysis)
    from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
    from app.models.company_entity import CompanyEntity

    profiles = (
        db.query(ManufacturerCompanyProfile, CompanyEntity)
        .join(CompanyEntity, ManufacturerCompanyProfile.master_company_id == CompanyEntity.id)
        .filter(
            ManufacturerCompanyProfile.company_id == tenant_id,
            ManufacturerCompanyProfile.order_count_12mo >= 10,
        )
        .all()
    )

    insights_created = 0
    for profile, entity in profiles:
        # Check if insight already exists
        existing = db.execute(text(
            "SELECT id FROM ai_upsell_insights WHERE tenant_id = :tid AND master_company_id = :cid AND dismissed = false"
        ), {"tid": tenant_id, "cid": entity.id}).fetchone()
        if existing:
            continue

        description = f"{entity.name} has {profile.order_count_12mo} orders in 12 months (${float(profile.total_revenue_12mo or 0):,.0f} revenue). Consider discussing volume pricing or additional product lines."
        db.execute(text(
            "INSERT INTO ai_upsell_insights (id, tenant_id, master_company_id, insight_type, description) "
            "VALUES (:id, :tid, :cid, 'volume_opportunity', :desc)"
        ), {"id": str(_uuid.uuid4()), "tid": tenant_id, "cid": entity.id, "desc": description})
        insights_created += 1

    return {"processed": len(profiles), "insights_created": insights_created}


def account_rescue_agent(db: Session, tenant_id: str) -> dict:
    """Draft outreach emails for at-risk accounts."""
    if not ai_settings_service.is_enabled(db, tenant_id, "account_rescue"):
        return {"skipped": True}

    from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
    from app.models.company_entity import CompanyEntity

    at_risk = (
        db.query(ManufacturerCompanyProfile, CompanyEntity)
        .join(CompanyEntity, ManufacturerCompanyProfile.master_company_id == CompanyEntity.id)
        .filter(
            ManufacturerCompanyProfile.company_id == tenant_id,
            ManufacturerCompanyProfile.health_score == "at_risk",
        )
        .limit(5)
        .all()
    )

    drafts_created = 0
    for profile, entity in at_risk:
        # Check if draft already exists
        existing = db.execute(text(
            "SELECT id FROM ai_rescue_drafts WHERE tenant_id = :tid AND master_company_id = :cid AND status = 'pending'"
        ), {"tid": tenant_id, "cid": entity.id}).fetchone()
        if existing:
            continue

        reasons = profile.health_reasons or []
        reason = reasons[0] if reasons else "No recent orders"

        # Generate draft with Claude
        try:
            from app.services.ai_service import call_anthropic
            prompt = f"""Draft a short, friendly check-in email from a small precast concrete manufacturer to a customer who hasn't ordered recently. Warm tone, not salesy. 3-4 sentences max.

Customer: {entity.name}
Type: {getattr(entity, 'customer_type', 'customer')}
Reason flagged: {reason}

Return JSON: {{"subject": "...", "body": "..."}}"""

            response = call_anthropic(prompt, max_tokens=150)
            if response:
                import json
                data = json.loads(response)
                db.execute(text(
                    "INSERT INTO ai_rescue_drafts (id, tenant_id, master_company_id, subject, body) "
                    "VALUES (:id, :tid, :cid, :subj, :body)"
                ), {"id": str(_uuid.uuid4()), "tid": tenant_id, "cid": entity.id,
                    "subj": data.get("subject", "Checking in"), "body": data.get("body", "")})
                drafts_created += 1
        except Exception:
            logger.exception("Rescue draft failed for %s", entity.name)

    return {"processed": len(at_risk), "drafts_created": drafts_created}
