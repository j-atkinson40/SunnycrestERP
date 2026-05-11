"""Website Intelligence — scrape results and AI-generated onboarding suggestions."""

import json
import logging
import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.models.user import User
from app.models.website_intelligence import (
    TenantWebsiteIntelligence,
    WebsiteIntelligenceSuggestion,
)
from app.schemas.website_intelligence import (
    SuggestionResponse,
    SuggestionUpdateRequest,
    WebsiteIntelligenceResponse,
)
from app.services.website_suggestion_service import (
    get_intelligence,
    get_suggestions,
    get_suggestions_for_extension,
    mark_applied,
    update_suggestion,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "High confidence"
    if score >= 0.70:
        return "Likely"
    return "Possible"


def _suggestion_to_response(s: WebsiteIntelligenceSuggestion) -> dict:
    return {
        "id": s.id,
        "suggestion_type": s.suggestion_type,
        "suggestion_key": s.suggestion_key,
        "suggestion_label": s.suggestion_label,
        "confidence": float(s.confidence),
        "evidence": s.evidence,
        "status": s.status,
        "confidence_label": _confidence_label(float(s.confidence)),
    }


def _intel_to_response(
    intel: TenantWebsiteIntelligence,
    suggestions: list[WebsiteIntelligenceSuggestion],
) -> dict:
    analysis = intel.analysis_dict
    return {
        "id": intel.id,
        "tenant_id": intel.tenant_id,
        "website_url": intel.website_url,
        "scrape_status": intel.scrape_status,
        "error_message": intel.error_message,
        "analysis_result": analysis if analysis else None,
        "suggestions": [_suggestion_to_response(s) for s in suggestions],
        "summary": analysis.get("summary") if analysis else None,
        "applied_to_onboarding": intel.applied_to_onboarding,
        "input_tokens": intel.input_tokens,
        "output_tokens": intel.output_tokens,
        "estimated_cost": float(intel.estimated_cost) if intel.estimated_cost else None,
        "created_at": intel.created_at,
    }


# ---------------------------------------------------------------------------
# Tenant-facing routes
# ---------------------------------------------------------------------------


@router.get("/website-intelligence")
def get_tenant_intelligence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get website intelligence and suggestions for the current tenant."""
    intel = get_intelligence(db, current_user.company_id)
    if not intel:
        raise HTTPException(status_code=404, detail="No website intelligence found")

    suggestions = get_suggestions(db, current_user.company_id)
    return _intel_to_response(intel, suggestions)


@router.patch("/website-intelligence/suggestions/{suggestion_id}")
def update_tenant_suggestion(
    suggestion_id: str,
    data: SuggestionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept or dismiss a suggestion."""
    if data.status not in ("accepted", "dismissed"):
        raise HTTPException(status_code=400, detail="Status must be 'accepted' or 'dismissed'")

    # Verify suggestion belongs to tenant
    suggestion = (
        db.query(WebsiteIntelligenceSuggestion)
        .filter(
            WebsiteIntelligenceSuggestion.id == suggestion_id,
            WebsiteIntelligenceSuggestion.tenant_id == current_user.company_id,
        )
        .first()
    )
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    updated = update_suggestion(db, suggestion_id, data.status)
    db.commit()
    return _suggestion_to_response(updated)


@router.post("/website-intelligence/mark-applied")
def mark_intelligence_applied(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark suggestions as shown/applied to tenant onboarding."""
    mark_applied(db, current_user.company_id)
    db.commit()
    return {"status": "ok"}


@router.get("/website-intelligence/suggestions/extension/{extension_key}")
def get_extension_suggestions(
    extension_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get accepted suggestions relevant to a specific extension."""
    suggestions = get_suggestions_for_extension(
        db, current_user.company_id, extension_key
    )
    return [_suggestion_to_response(s) for s in suggestions]


# ---------------------------------------------------------------------------
# Network diagnostic (temporary)
# ---------------------------------------------------------------------------


@router.get("/website-intelligence/debug-network")
def debug_network(
    url: str = Query(..., description="URL to scrape for diagnostic purposes (required, no default)"),
    db: Session = Depends(get_db),
):
    """Temporary endpoint: run the FULL intelligence pipeline synchronously.

    R-8.4: URL must be supplied by the caller — no hardcoded tenant-named
    default. Diagnostic endpoint; not consumed by production flows.
    """
    import traceback
    results = {"requested_url": url}

    # Test 1: Scrape
    try:
        from app.services.website_scraper_service import scrape_website
        scrape_result = scrape_website(url)
        results["scrape"] = f"OK: {len(scrape_result['pages_scraped'])} pages, {len(scrape_result['raw_content'])} chars"
        results["scrape_preview"] = scrape_result["raw_content"][:500]
    except Exception as e:
        results["scrape"] = f"FAILED: {type(e).__name__}: {e}"
        results["scrape_traceback"] = traceback.format_exc()[-500:]
        return results

    # Test 1b: Can we reach api.anthropic.com?
    try:
        import requests as _req
        r = _req.get("https://api.anthropic.com", timeout=10)
        results["anthropic_network"] = f"OK: {r.status_code}"
    except Exception as e:
        root = e
        while root.__cause__ or root.__context__:
            root = root.__cause__ or root.__context__
        results["anthropic_network"] = f"FAILED: {type(root).__name__}: {root}"

    # Test 1c: Check API key
    from app.config import settings
    results["api_key_set"] = bool(settings.ANTHROPIC_API_KEY)
    results["api_key_prefix"] = settings.ANTHROPIC_API_KEY[:10] + "..." if settings.ANTHROPIC_API_KEY else "EMPTY"

    # Test 2: Analyze
    try:
        from app.services.website_analysis_service import analyze_website_content
        # Diagnostic endpoint — no tenant scoping; execution row logs with company_id=None
        analysis = analyze_website_content(db, scrape_result["raw_content"])
        results["analyze"] = f"OK: {analysis['input_tokens']} in / {analysis['output_tokens']} out tokens"
        results["analysis_keys"] = list(analysis["analysis"].keys()) if isinstance(analysis["analysis"], dict) else str(type(analysis["analysis"]))
        # Show vault lines
        a = analysis["analysis"]
        results["vault_lines"] = a.get("vault_lines", "not found")
        results["product_lines"] = a.get("product_lines", "not found")
        results["summary"] = a.get("summary", "not found")
    except Exception as e:
        results["analyze"] = f"FAILED: {type(e).__name__}: {e}"
        results["analyze_traceback"] = traceback.format_exc()[-500:]
        return results

    # Test 3: DB write test
    try:
        from app.database import SessionLocal
        from app.models.website_intelligence import TenantWebsiteIntelligence
        db = SessionLocal()
        # Just test we can query the table
        count = db.query(TenantWebsiteIntelligence).count()
        db.close()
        results["db_table"] = f"OK: {count} records in tenant_website_intelligence"
    except Exception as e:
        results["db_table"] = f"FAILED: {type(e).__name__}: {e}"

    return results


# ---------------------------------------------------------------------------
# Admin routes (platform admin only)
# ---------------------------------------------------------------------------


@router.get("/admin/website-intelligence/{tenant_id}")
def admin_get_intelligence(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support")),
    db: Session = Depends(get_db),
):
    """Full intelligence view for a tenant (admin)."""
    intel = get_intelligence(db, tenant_id)
    if not intel:
        raise HTTPException(status_code=404, detail="No website intelligence found")

    suggestions = get_suggestions(db, tenant_id)
    return _intel_to_response(intel, suggestions)


@router.post("/admin/website-intelligence/{tenant_id}/rescrape")
def admin_rescrape(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Re-run website scrape for a tenant."""
    intel = get_intelligence(db, tenant_id)
    if not intel:
        raise HTTPException(status_code=404, detail="No website intelligence found")

    # Clear old suggestions
    db.query(WebsiteIntelligenceSuggestion).filter(
        WebsiteIntelligenceSuggestion.tenant_id == tenant_id,
    ).delete()

    intel.scrape_status = "pending"
    intel.error_message = None
    intel.applied_to_onboarding = False
    db.commit()

    # Run in background thread
    def _background_scrape():
        from app.services.website_intelligence_job import run_website_intelligence

        run_website_intelligence(None, tenant_id, intel.website_url)

    thread = threading.Thread(target=_background_scrape, daemon=True)
    thread.start()

    return {"status": "rescrape_started", "tenant_id": tenant_id}


@router.post("/admin/website-intelligence/{tenant_id}/clear")
def admin_clear_suggestions(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Reset all suggestions for a tenant."""
    deleted = (
        db.query(WebsiteIntelligenceSuggestion)
        .filter(WebsiteIntelligenceSuggestion.tenant_id == tenant_id)
        .delete()
    )
    intel = get_intelligence(db, tenant_id)
    if intel:
        intel.applied_to_onboarding = False
        intel.tenant_confirmed_at = None
    db.commit()
    return {"status": "cleared", "suggestions_deleted": deleted}
