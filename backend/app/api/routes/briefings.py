"""Morning Briefing API routes.

Endpoints for fetching, refreshing, and configuring per-employee daily briefings.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.employee_profile import EmployeeProfile
from app.models.user import User
from app.services.briefing_service import (
    PRIMARY_CAPABLE_AREAS,
    determine_primary_area,
    get_briefing_for_employee,
    refresh_briefing_for_employee,
)
from app.services.functional_area_service import (
    get_active_areas_for_employee,
    get_areas_for_tenant,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BriefingItemOut(BaseModel):
    number: int
    text: str
    priority: str
    related_entity_type: str | None = None
    related_entity_hint: str | None = None


class BriefingResponse(BaseModel):
    content: str | None = None
    items: list[BriefingItemOut] = []
    tier: str | None = None
    primary_area: str | None = None
    was_cached: bool = False
    generated_at: str | None = None
    briefing_date: str | None = None
    reason: str | None = None
    token_usage: dict | None = None
    duration_ms: int | None = None


class BriefingSettingsOut(BaseModel):
    briefing_enabled: bool
    primary_area: str | None = None
    primary_area_override: str | None = None
    available_primary_areas: list[str] = []


class BriefingSettingsUpdate(BaseModel):
    briefing_enabled: bool | None = None
    briefing_primary_area_override: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_employee_profile(db: Session, user: User) -> EmployeeProfile | None:
    return (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.user_id == user.id)
        .first()
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/briefing", response_model=BriefingResponse)
def get_briefing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's morning briefing (cached or fresh)."""
    profile = _get_employee_profile(db, current_user)

    if not profile:
        return BriefingResponse(content=None, reason="no_profile")

    if not profile.briefing_enabled:
        return BriefingResponse(content=None, reason="disabled")

    if not profile.functional_areas and current_user.track != "production_delivery":
        return BriefingResponse(content=None, reason="no_functional_areas")

    try:
        tenant_areas = get_areas_for_tenant(db, current_user.company_id)
    except Exception:
        tenant_areas = []

    try:
        result = get_briefing_for_employee(
            db, current_user, profile, tenant_areas
        )
    except Exception as e:
        logger.error("Error generating briefing for user %s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate briefing. Please try again.",
        )

    if result is None:
        return BriefingResponse(content=None, reason="no_primary_area")

    return BriefingResponse(
        content=result.get("content"),
        items=[BriefingItemOut(**item) for item in result.get("items", [])],
        tier=result.get("tier"),
        primary_area=result.get("primary_area"),
        was_cached=result.get("was_cached", False),
        generated_at=result.get("generated_at"),
        briefing_date=result.get("briefing_date"),
        token_usage=result.get("token_usage"),
        duration_ms=result.get("duration_ms"),
    )


@router.post("/briefing/refresh", response_model=BriefingResponse)
def refresh_briefing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Force-regenerate today's briefing (deletes cache)."""
    profile = _get_employee_profile(db, current_user)

    if not profile:
        return BriefingResponse(content=None, reason="no_profile")

    if not profile.briefing_enabled:
        return BriefingResponse(content=None, reason="disabled")

    if not profile.functional_areas and current_user.track != "production_delivery":
        return BriefingResponse(content=None, reason="no_functional_areas")

    try:
        tenant_areas = get_areas_for_tenant(db, current_user.company_id)
    except Exception:
        tenant_areas = []

    try:
        result = refresh_briefing_for_employee(
            db, current_user, profile, tenant_areas
        )
    except Exception as e:
        logger.error("Error refreshing briefing for user %s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh briefing. Please try again.",
        )

    if result is None:
        return BriefingResponse(content=None, reason="no_primary_area")

    return BriefingResponse(
        content=result.get("content"),
        items=[BriefingItemOut(**item) for item in result.get("items", [])],
        tier=result.get("tier"),
        primary_area=result.get("primary_area"),
        was_cached=result.get("was_cached", False),
        generated_at=result.get("generated_at"),
        briefing_date=result.get("briefing_date"),
        token_usage=result.get("token_usage"),
        duration_ms=result.get("duration_ms"),
    )


@router.get("/briefing/settings", response_model=BriefingSettingsOut)
def get_briefing_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's briefing configuration."""
    profile = _get_employee_profile(db, current_user)

    if not profile:
        return BriefingSettingsOut(briefing_enabled=True)

    try:
        tenant_areas = get_areas_for_tenant(db, current_user.company_id)
    except Exception:
        tenant_areas = []

    active_areas = get_active_areas_for_employee(
        profile.functional_areas, tenant_areas
    )
    available_primary = [a for a in active_areas if a in PRIMARY_CAPABLE_AREAS]
    if "full_admin" in active_areas:
        available_primary.append("full_admin")

    # Determine current effective primary
    effective_primary = (
        profile.briefing_primary_area_override
        or determine_primary_area(active_areas, tenant_areas)
    )

    return BriefingSettingsOut(
        briefing_enabled=profile.briefing_enabled,
        primary_area=effective_primary,
        primary_area_override=profile.briefing_primary_area_override,
        available_primary_areas=available_primary,
    )


@router.put("/briefing/settings", response_model=BriefingSettingsOut)
def update_briefing_settings(
    body: BriefingSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's briefing preferences."""
    profile = _get_employee_profile(db, current_user)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found. Please contact an admin.",
        )

    try:
        tenant_areas = get_areas_for_tenant(db, current_user.company_id)
    except Exception:
        tenant_areas = []

    active_areas = get_active_areas_for_employee(
        profile.functional_areas, tenant_areas
    )

    # Validate override area
    if body.briefing_primary_area_override is not None:
        override = body.briefing_primary_area_override
        if override != "":
            valid_areas = [a for a in active_areas if a in PRIMARY_CAPABLE_AREAS]
            if "full_admin" in active_areas:
                valid_areas.append("full_admin")
            if override not in valid_areas:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid primary area override. Valid options: {valid_areas}",
                )
            profile.briefing_primary_area_override = override
        else:
            # Empty string clears the override
            profile.briefing_primary_area_override = None

    if body.briefing_enabled is not None:
        profile.briefing_enabled = body.briefing_enabled

    profile.modified_by = current_user.id
    db.commit()
    db.refresh(profile)

    # Return updated settings
    available_primary = [a for a in active_areas if a in PRIMARY_CAPABLE_AREAS]
    if "full_admin" in active_areas:
        available_primary.append("full_admin")

    effective_primary = (
        profile.briefing_primary_area_override
        or determine_primary_area(active_areas, tenant_areas)
    )

    return BriefingSettingsOut(
        briefing_enabled=profile.briefing_enabled,
        primary_area=effective_primary,
        primary_area_override=profile.briefing_primary_area_override,
        available_primary_areas=available_primary,
    )
