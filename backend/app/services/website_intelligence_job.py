"""Website intelligence job — orchestrates scrape -> analyze -> suggest pipeline."""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.models.website_intelligence import TenantWebsiteIntelligence
from app.services.website_analysis_service import analyze_website_content
from app.services.website_scraper_service import scrape_website, extract_branding
from app.services.website_suggestion_service import generate_suggestions

logger = logging.getLogger(__name__)

# Haiku pricing per 1M tokens (approximate)
HAIKU_INPUT_COST_PER_M = 0.80
HAIKU_OUTPUT_COST_PER_M = 4.00


def _estimate_cost(input_tokens: int, output_tokens: int) -> Decimal:
    """Estimate API cost in USD."""
    cost = (input_tokens / 1_000_000) * HAIKU_INPUT_COST_PER_M + (
        output_tokens / 1_000_000
    ) * HAIKU_OUTPUT_COST_PER_M
    return Decimal(str(round(cost, 4)))


def run_website_intelligence(db_session, tenant_id: str, url: str) -> None:
    """Orchestrate the full scrape -> analyze -> suggest pipeline.

    Accepts either a live Session or None (creates its own).
    Must complete within 90 seconds.
    """
    own_session = db_session is None
    db = db_session or SessionLocal()

    try:
        # 1. Update status to in_progress
        intel = (
            db.query(TenantWebsiteIntelligence)
            .filter(TenantWebsiteIntelligence.tenant_id == tenant_id)
            .first()
        )
        if not intel:
            logger.error(f"No intelligence record for tenant {tenant_id}")
            return

        intel.scrape_status = "in_progress"
        intel.scrape_started_at = datetime.now(timezone.utc)
        intel.error_message = None
        db.commit()

        # 2. Scrape
        logger.info(f"Scraping website for tenant {tenant_id}: {url}")
        scrape_result = scrape_website(url)
        intel.raw_content = scrape_result["raw_content"]
        intel.pages_scraped = json.dumps(scrape_result["pages_scraped"])
        db.commit()

        # 3. Analyze
        logger.info(f"Analyzing website content for tenant {tenant_id}")
        analysis = analyze_website_content(scrape_result["raw_content"])
        intel.analysis_result = json.dumps(analysis["analysis"])
        intel.input_tokens = analysis["input_tokens"]
        intel.output_tokens = analysis["output_tokens"]
        intel.estimated_cost = _estimate_cost(
            analysis["input_tokens"], analysis["output_tokens"]
        )

        # Extract confidence scores
        analysis_data = analysis["analysis"]
        scores = {}
        if "npca_certified" in analysis_data:
            scores["npca"] = analysis_data["npca_certified"].get("confidence", 0)
        if "spring_burials" in analysis_data:
            scores["spring_burials"] = analysis_data["spring_burials"].get("confidence", 0)
        intel.confidence_scores = json.dumps(scores)
        db.commit()

        # 4. Generate suggestions
        logger.info(f"Generating suggestions for tenant {tenant_id}")
        generate_suggestions(db, tenant_id, analysis_data)

        # 4b. Extract branding from homepage HTML
        try:
            homepage_html = intel.raw_content or ""
            # raw_content is text-stripped; re-fetch just the homepage for branding
            # (scrape_website already fetched it; use stored pages to get raw HTML)
            import requests as _req
            _resp = _req.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
            branding = extract_branding(_resp.text, url)
            logger.info(
                f"Branding extracted for tenant {tenant_id}: "
                f"logo={branding['logo_url']} conf={branding['logo_confidence']:.2f} "
                f"primary={branding['primary_color']}"
            )

            from app.models.company import Company
            company = db.query(Company).filter(Company.id == tenant_id).first()
            if company:
                # Only store detected logo if company doesn't already have one set
                if branding["logo_url"] and not company.logo_url:
                    company.set_setting("detected_logo_url", branding["logo_url"])
                    company.set_setting("detected_logo_confidence", branding["logo_confidence"])
                if branding["primary_color"]:
                    company.set_setting("detected_primary_color", branding["primary_color"])
                if branding["secondary_color"]:
                    company.set_setting("detected_secondary_color", branding["secondary_color"])
                if branding["colors_found"]:
                    company.set_setting("detected_colors", branding["colors_found"])
                db.commit()
        except Exception as _be:
            logger.warning(f"Branding extraction failed for tenant {tenant_id}: {_be}")

        # 5. Mark completed
        intel.scrape_status = "completed"
        intel.scrape_completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"Website intelligence complete for tenant {tenant_id}: "
            f"{intel.input_tokens} in / {intel.output_tokens} out tokens"
        )

    except Exception as e:
        import traceback
        full_error = f"{type(e).__name__}: {e}"
        # Include the cause chain
        cause = e.__cause__ or e.__context__
        if cause:
            full_error += f" | Caused by: {type(cause).__name__}: {cause}"
            cause2 = cause.__cause__ or cause.__context__
            if cause2:
                full_error += f" | Root: {type(cause2).__name__}: {cause2}"
        logger.error(f"Website intelligence failed for tenant {tenant_id}: {full_error}")
        logger.error(traceback.format_exc())
        try:
            intel = (
                db.query(TenantWebsiteIntelligence)
                .filter(TenantWebsiteIntelligence.tenant_id == tenant_id)
                .first()
            )
            if intel:
                intel.scrape_status = "failed"
                intel.error_message = full_error[:2000]
                intel.scrape_completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            logger.error("Failed to update error status")

    finally:
        if own_session:
            db.close()
