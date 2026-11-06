"""Website Intelligence — scrape results and AI-generated onboarding suggestions."""

import json
import logging
import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException
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
# ⚠️ `GET /website-intelligence/debug-network` WAS DELETED ON 2026-11-06.
# DO NOT REINSTATE IT, AND DO NOT WRITE ANOTHER ONE LIKE IT.
#
# It required no sign-in, took an arbitrary `url`, and ran the full
# intelligence pipeline on it. Per anonymous request that meant: the
# production server fetching whatever address the caller named (SSRF), a
# BILLED Claude call, an outbound probe to api.anthropic.com, and 500 chars
# each of scraped content and traceback returned to the caller. No rate
# limit, no tenant scoping — the execution row logged `company_id=None`.
#
# ⚠️ It also returned `ANTHROPIC_API_KEY[:10]`. That READS like a credential
# leak and is not one — ten characters of an Anthropic key is `sk-ant-api`,
# the public key-type prefix, and the adjacent `api_key_set` boolean already
# said a key existed. Recorded precisely because overstating a finding is
# its own defect.
#
# Deleted rather than gated, as with `POST /auth/register`: a temporary
# diagnostic that no production flow consumes is not a capability worth
# keeping behind a guard. Its own docstring said "Temporary endpoint" and
# "not consumed by production flows", and it had been live long enough to be
# found by a census rather than by anyone needing it.
#
# ⚠️ IF YOU NEED THIS DIAGNOSTIC AGAIN: run the pipeline from a script under
# `railway run`, where it is reachable by an operator and by nobody else. A
# route is the wrong shape for a diagnostic, because a route is reachable
# from the internet by definition.
#
# Pinned by `test_debug_network_is_gone_and_stays_gone`, and by the
# group-0 inventory in the same file, which refuses any route whose path
# looks diagnostic. See
# docs/investigations/2026-11-06-tenant-route-authorization-census.md.
# ---------------------------------------------------------------------------


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
