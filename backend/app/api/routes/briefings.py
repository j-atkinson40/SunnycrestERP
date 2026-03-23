"""Morning Briefing API routes.

Endpoints for fetching, refreshing, and configuring per-employee daily briefings.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.company_resolver import get_current_company
from app.database import get_db
from app.models.company import Company
from app.models.employee_briefing import EmployeeBriefing
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


# ---------------------------------------------------------------------------
# Team Intelligence Config Schemas
# ---------------------------------------------------------------------------


class EmployeeBriefingConfigOut(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    display_title: str | None = None
    track: str
    functional_areas: list[str] = []
    primary_area: str | None = None
    primary_area_override: str | None = None
    briefing_enabled: bool = True
    can_create_announcements: bool = False
    console_access: list[str] = []
    disabled_briefing_items: list[str] = []
    disabled_announcement_categories: list[str] = []
    disabled_console_items: list[str] = []


class EmployeeBriefingConfigUpdate(BaseModel):
    briefing_enabled: bool | None = None
    briefing_primary_area_override: str | None = None
    can_create_announcements: bool | None = None


class IntelligenceSettingsUpdate(BaseModel):
    disabled_briefing_items: list[str] | None = None
    disabled_announcement_categories: list[str] | None = None
    disabled_console_items: list[str] | None = None


class TenantBriefingSettingsOut(BaseModel):
    team_intelligence_configured: bool = False
    briefings_enabled_tenant_wide: bool = True
    briefing_delivery_time: str = "08:00"


class TenantBriefingSettingsUpdate(BaseModel):
    briefings_enabled_tenant_wide: bool | None = None
    briefing_delivery_time: str | None = None


class BriefingHistoryOut(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    briefing_date: str
    primary_area: str | None = None
    tier: str | None = None
    generated_content: str | None = None
    items: list[dict] = []
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Team Intelligence Config Endpoints
# ---------------------------------------------------------------------------


@router.get("/team-config", response_model=list[EmployeeBriefingConfigOut])
def get_team_config(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all employees with their briefing configuration."""
    from app.models.user import User as UserModel

    users = (
        db.query(UserModel)
        .filter(
            UserModel.company_id == current_user.company_id,
            UserModel.is_active == True,
        )
        .all()
    )

    try:
        tenant_areas = get_areas_for_tenant(db, current_user.company_id)
    except Exception:
        tenant_areas = []

    results = []
    for u in users:
        profile = _get_employee_profile(db, u)
        fa = (profile.functional_areas or []) if profile else []
        active_areas = get_active_areas_for_employee(fa, tenant_areas) if fa else []

        effective_primary = None
        if profile and profile.briefing_primary_area_override:
            effective_primary = profile.briefing_primary_area_override
        elif active_areas:
            effective_primary = determine_primary_area(active_areas, tenant_areas)
        elif u.track == "production_delivery":
            effective_primary = (
                "driver"
                if (u.console_access or []) and "delivery_console" in (u.console_access or [])
                else "production"
            )

        # Get assistant profile for intelligence settings
        from app.models.assistant_profile import AssistantProfile
        ap = (
            db.query(AssistantProfile)
            .filter(AssistantProfile.user_id == u.id)
            .first()
        )

        results.append(EmployeeBriefingConfigOut(
            user_id=u.id,
            first_name=u.first_name,
            last_name=u.last_name,
            display_title=profile.position if profile else None,
            track=u.track,
            functional_areas=fa,
            primary_area=effective_primary,
            primary_area_override=profile.briefing_primary_area_override if profile else None,
            briefing_enabled=profile.briefing_enabled if profile else True,
            can_create_announcements=profile.can_create_announcements if profile else False,
            console_access=u.console_access or [],
            disabled_briefing_items=ap.disabled_briefing_items or [] if ap else [],
            disabled_announcement_categories=ap.disabled_announcement_categories or [] if ap else [],
            disabled_console_items=ap.disabled_console_items or [] if ap else [],
        ))

    return results


@router.patch("/team-config/{user_id}", response_model=EmployeeBriefingConfigOut)
def update_employee_briefing_config(
    user_id: str,
    body: EmployeeBriefingConfigUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a single employee's briefing configuration."""
    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == current_user.company_id)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = _get_employee_profile(db, target_user)
    if not profile:
        # Auto-create profile if missing
        profile = EmployeeProfile(user_id=target_user.id, created_by=current_user.id)
        db.add(profile)
        db.flush()

    if body.briefing_enabled is not None:
        profile.briefing_enabled = body.briefing_enabled
    if body.briefing_primary_area_override is not None:
        profile.briefing_primary_area_override = body.briefing_primary_area_override or None
    if body.can_create_announcements is not None:
        profile.can_create_announcements = body.can_create_announcements

    profile.modified_by = current_user.id
    db.commit()
    db.refresh(profile)

    try:
        tenant_areas = get_areas_for_tenant(db, current_user.company_id)
    except Exception:
        tenant_areas = []

    fa = profile.functional_areas or []
    active_areas = get_active_areas_for_employee(fa, tenant_areas) if fa else []
    effective_primary = (
        profile.briefing_primary_area_override
        or (determine_primary_area(active_areas, tenant_areas) if active_areas else None)
    )

    return EmployeeBriefingConfigOut(
        user_id=target_user.id,
        first_name=target_user.first_name,
        last_name=target_user.last_name,
        display_title=profile.position,
        track=target_user.track,
        functional_areas=fa,
        primary_area=effective_primary,
        primary_area_override=profile.briefing_primary_area_override,
        briefing_enabled=profile.briefing_enabled,
        can_create_announcements=profile.can_create_announcements,
    )


@router.post("/team-config/complete-setup")
def complete_team_intelligence_setup(
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Mark team intelligence setup as complete."""
    company.set_setting("team_intelligence_configured", True)
    db.commit()

    # Fire onboarding hook
    from app.services.onboarding_hooks import on_team_intelligence_configured

    on_team_intelligence_configured(db, company.id)

    return {"status": "ok"}


@router.get("/tenant-settings", response_model=TenantBriefingSettingsOut)
def get_tenant_briefing_settings(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get tenant-level briefing settings."""
    return TenantBriefingSettingsOut(
        team_intelligence_configured=company.get_setting("team_intelligence_configured", False),
        briefings_enabled_tenant_wide=company.get_setting("briefings_enabled_tenant_wide", True),
        briefing_delivery_time=company.get_setting("briefing_delivery_time", "08:00"),
    )


@router.put("/tenant-settings", response_model=TenantBriefingSettingsOut)
def update_tenant_briefing_settings(
    body: TenantBriefingSettingsUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update tenant-level briefing settings."""
    if body.briefings_enabled_tenant_wide is not None:
        company.set_setting("briefings_enabled_tenant_wide", body.briefings_enabled_tenant_wide)
    if body.briefing_delivery_time is not None:
        company.set_setting("briefing_delivery_time", body.briefing_delivery_time)
    db.commit()

    return TenantBriefingSettingsOut(
        team_intelligence_configured=company.get_setting("team_intelligence_configured", False),
        briefings_enabled_tenant_wide=company.get_setting("briefings_enabled_tenant_wide", True),
        briefing_delivery_time=company.get_setting("briefing_delivery_time", "08:00"),
    )


@router.get("/history", response_model=list[BriefingHistoryOut])
def get_briefing_history(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get recent briefing history (last 7 days) for all employees."""
    from datetime import timedelta

    seven_days_ago = date.today() - timedelta(days=7)

    briefings = (
        db.query(EmployeeBriefing)
        .filter(
            EmployeeBriefing.company_id == current_user.company_id,
            EmployeeBriefing.briefing_date >= seven_days_ago,
        )
        .order_by(EmployeeBriefing.briefing_date.desc(), EmployeeBriefing.created_at.desc())
        .all()
    )

    # Get user names
    user_ids = list(set(b.user_id for b in briefings))
    user_map = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}

    results = []
    for b in briefings:
        u = user_map.get(b.user_id)
        results.append(BriefingHistoryOut(
            user_id=b.user_id,
            first_name=u.first_name if u else "Unknown",
            last_name=u.last_name if u else "",
            briefing_date=str(b.briefing_date),
            primary_area=b.primary_area,
            tier=b.tier,
            generated_content=b.generated_content,
            items=b.parsed_items or [],
            created_at=b.created_at.isoformat() if b.created_at else None,
        ))

    return results


@router.patch("/team-config/{user_id}/intelligence")
def update_intelligence_settings(
    user_id: str,
    body: IntelligenceSettingsUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update per-employee intelligence settings (disabled items/categories)."""
    from app.models.assistant_profile import AssistantProfile

    target_user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == current_user.company_id)
        .first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    ap = db.query(AssistantProfile).filter(AssistantProfile.user_id == user_id).first()
    if not ap:
        ap = AssistantProfile(
            user_id=user_id,
            company_id=current_user.company_id,
        )
        db.add(ap)
        db.flush()

    if body.disabled_briefing_items is not None:
        ap.disabled_briefing_items = body.disabled_briefing_items
    if body.disabled_announcement_categories is not None:
        ap.disabled_announcement_categories = body.disabled_announcement_categories
    if body.disabled_console_items is not None:
        ap.disabled_console_items = body.disabled_console_items

    db.commit()
    return {"status": "ok"}
