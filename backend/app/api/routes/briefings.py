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


@router.get("/action-items")
def get_action_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return structured actionable items for the morning briefing.

    Unlike the AI-generated briefing text, these are real database records
    with entity IDs so the frontend can render action buttons (View, Pay,
    Send, Approve, etc.).
    """
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    from sqlalchemy import func
    from app.models.invoice import Invoice
    from app.models.sales_order import SalesOrder
    from app.models.customer import Customer
    from app.models.delivery import Delivery

    company_id = current_user.company_id
    today = date.today()
    now = datetime.now(timezone.utc)

    # 1. Orders due today (deliveries scheduled for today)
    orders_due_today = []
    try:
        deliveries = (
            db.query(Delivery)
            .filter(
                Delivery.company_id == company_id,
                Delivery.requested_date == today,
                Delivery.status != "cancelled",
            )
            .all()
        )
        for d in deliveries:
            customer_name = None
            if d.customer_id:
                cust = db.query(Customer.name).filter(Customer.id == d.customer_id).first()
                customer_name = cust[0] if cust else None

            # Try to get order details
            order_number = None
            deceased_name = None
            cemetery_name = None
            service_time = None
            order_id = None
            if d.sales_order_id:
                order = db.query(SalesOrder).filter(SalesOrder.id == d.sales_order_id).first()
                if order:
                    order_id = order.id
                    order_number = order.number
                    deceased_name = getattr(order, "deceased_name", None)
                    service_time = str(order.service_time) if getattr(order, "service_time", None) else None
                    if getattr(order, "cemetery", None):
                        cemetery_name = order.cemetery.name

            orders_due_today.append({
                "delivery_id": d.id,
                "order_id": order_id,
                "order_number": order_number,
                "customer_name": customer_name,
                "deceased_name": deceased_name,
                "cemetery_name": cemetery_name,
                "service_time": service_time,
                "status": d.status,
                "priority": d.priority,
                "assigned_driver_id": d.assigned_driver_id,
            })
    except Exception as e:
        logger.warning("Error fetching orders due today: %s", e)

    # 2. Overdue invoices
    overdue_invoices = []
    try:
        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == company_id,
                Invoice.status.in_(["sent", "partial", "overdue", "open"]),
                Invoice.due_date < now,
            )
            .order_by(Invoice.due_date.asc())
            .limit(10)
            .all()
        )
        for inv in invoices:
            remaining = float(inv.total - inv.amount_paid) if inv.total and inv.amount_paid is not None else float(inv.total or 0)
            if remaining <= 0:
                continue
            days_overdue = (now - inv.due_date).days if inv.due_date else 0
            customer_name = None
            customer_id = inv.customer_id
            if customer_id:
                cust = db.query(Customer.name).filter(Customer.id == customer_id).first()
                customer_name = cust[0] if cust else None

            overdue_invoices.append({
                "id": inv.id,
                "number": inv.number,
                "customer_id": customer_id,
                "customer_name": customer_name,
                "total": str(inv.total),
                "amount_paid": str(inv.amount_paid or 0),
                "balance_remaining": f"{remaining:.2f}",
                "days_overdue": days_overdue,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "has_email": bool(
                    db.query(Customer.email)
                    .filter(Customer.id == customer_id)
                    .first()
                ) if customer_id else False,
            })
    except Exception as e:
        logger.warning("Error fetching overdue invoices: %s", e)

    # 3. Draft invoices pending review
    draft_invoices = []
    try:
        drafts = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == company_id,
                Invoice.status == "draft",
            )
            .order_by(Invoice.created_at.desc())
            .limit(10)
            .all()
        )
        for inv in drafts:
            customer_name = None
            if inv.customer_id:
                cust = db.query(Customer.name).filter(Customer.id == inv.customer_id).first()
                customer_name = cust[0] if cust else None

            draft_invoices.append({
                "id": inv.id,
                "number": inv.number,
                "customer_name": customer_name,
                "total": str(inv.total),
                "has_exceptions": bool(getattr(inv, "has_exceptions", False)),
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            })
    except Exception as e:
        logger.warning("Error fetching draft invoices: %s", e)

    # 4. KB recommendation
    kb_recommendation = None
    try:
        from app.models.kb_document import KBDocument
        doc_count = db.query(func.count(KBDocument.id)).filter(
            KBDocument.tenant_id == company_id,
            KBDocument.is_active == True,  # noqa: E712
        ).scalar() or 0
        if doc_count < 3:
            kb_recommendation = {"show": True, "document_count": doc_count}
    except Exception:
        pass

    return {
        "orders_due_today": orders_due_today,
        "overdue_invoices": overdue_invoices,
        "draft_invoices": draft_invoices,
        "kb_recommendation": kb_recommendation,
    }


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


# ═════════════════════════════════════════════════════════════════════
# Phase 6 — /v2 endpoints. Coexist with legacy endpoints above.
# Legacy keeps running; new surfaces use /v2/*.
# ═════════════════════════════════════════════════════════════════════


from datetime import datetime as _dt_v2, timezone as _tz_v2
from fastapi import Query  # noqa: E402
from app.models.briefing import Briefing, BRIEFING_TYPES as _BRIEFING_TYPES
from app.services.briefings import (  # noqa: E402
    BriefingPreferences as _BriefingPrefs,
    collect_data_for_evening_briefing,
    collect_data_for_morning_briefing,
    deliver_briefing as _deliver,
    generate_evening_briefing,
    generate_morning_briefing,
    get_preferences as _get_prefs,
    seed_preferences_for_user as _seed_prefs,
    update_preferences as _update_prefs,
)


class BriefingV2Out(BaseModel):
    id: str
    briefing_type: str
    generated_at: str
    delivered_at: str | None = None
    delivery_channels: list[str] = []
    narrative_text: str
    structured_sections: dict = {}
    active_space_id: str | None = None
    active_space_name: str | None = None
    role_slug: str | None = None
    generation_duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    read_at: str | None = None
    created_at: str


class BriefingV2PrefsOut(BaseModel):
    morning_enabled: bool
    morning_delivery_time: str
    morning_channels: list[str]
    morning_sections: list[str]
    evening_enabled: bool
    evening_delivery_time: str
    evening_channels: list[str]
    evening_sections: list[str]


class BriefingV2PrefsUpdate(BaseModel):
    morning_enabled: bool | None = None
    morning_delivery_time: str | None = None
    morning_channels: list[str] | None = None
    morning_sections: list[str] | None = None
    evening_enabled: bool | None = None
    evening_delivery_time: str | None = None
    evening_channels: list[str] | None = None
    evening_sections: list[str] | None = None


class BriefingV2GenerateRequest(BaseModel):
    briefing_type: str  # "morning" | "evening"
    deliver: bool = False


def _to_v2_out(b: Briefing) -> BriefingV2Out:
    return BriefingV2Out(
        id=b.id,
        briefing_type=b.briefing_type,
        generated_at=b.generated_at.isoformat() if b.generated_at else "",
        delivered_at=b.delivered_at.isoformat() if b.delivered_at else None,
        delivery_channels=b.delivery_channels or [],
        narrative_text=b.narrative_text,
        structured_sections=b.structured_sections or {},
        active_space_id=b.active_space_id,
        active_space_name=b.active_space_name,
        role_slug=b.role_slug,
        generation_duration_ms=b.generation_duration_ms,
        input_tokens=b.input_tokens,
        output_tokens=b.output_tokens,
        read_at=b.read_at.isoformat() if b.read_at else None,
        created_at=b.created_at.isoformat() if b.created_at else "",
    )


@router.get("/v2", response_model=list[BriefingV2Out])
def list_briefings_v2(
    briefing_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's briefings (most recent first)."""
    q = db.query(Briefing).filter(Briefing.user_id == current_user.id)
    if briefing_type:
        if briefing_type not in _BRIEFING_TYPES:
            raise HTTPException(status_code=400, detail="Unknown briefing_type")
        q = q.filter(Briefing.briefing_type == briefing_type)
    rows = q.order_by(Briefing.generated_at.desc()).limit(limit).all()
    return [_to_v2_out(b) for b in rows]


@router.get("/v2/latest", response_model=BriefingV2Out | None)
def latest_briefing_v2(
    briefing_type: str = Query(default="morning"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most-recent briefing of the requested type, or null."""
    if briefing_type not in _BRIEFING_TYPES:
        raise HTTPException(status_code=400, detail="Unknown briefing_type")
    row = (
        db.query(Briefing)
        .filter(
            Briefing.user_id == current_user.id,
            Briefing.briefing_type == briefing_type,
        )
        .order_by(Briefing.generated_at.desc())
        .first()
    )
    return _to_v2_out(row) if row else None


@router.get("/v2/preferences", response_model=BriefingV2PrefsOut)
def get_preferences_v2(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's briefing preferences. Seeds defaults
    (with legacy disabled_briefing_items translation) on first access."""
    prefs = _seed_prefs(db, current_user)
    return BriefingV2PrefsOut(**prefs.model_dump())


@router.patch("/v2/preferences", response_model=BriefingV2PrefsOut)
def update_preferences_v2(
    body: BriefingV2PrefsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Patch-update preferences. Validates via Pydantic; unknown fields 422."""
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    try:
        prefs = _update_prefs(db, current_user, updates)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid preferences: {e}") from e
    return BriefingV2PrefsOut(**prefs.model_dump())


@router.post("/v2/generate", response_model=BriefingV2Out)
def generate_briefing_v2(
    body: BriefingV2GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """On-demand generation (bypasses the every-15-min sweep).

    Creates a Briefing row. If `deliver=true`, ALSO dispatches via the
    user's configured delivery channels. Otherwise the briefing is
    in-app-only. Always returns the generated row.
    """
    btype = body.briefing_type
    if btype not in _BRIEFING_TYPES:
        raise HTTPException(status_code=400, detail="Unknown briefing_type")

    # On-demand generate REPLACES today's briefing of this type. The
    # daily unique index enforces one-per-day per type, and the user
    # explicitly asked to regenerate, so we delete the existing row
    # before creating the fresh one. Post-arc cleanup: rename this
    # endpoint to /v2/regenerate to signal intent more clearly.
    from sqlalchemy import func as _fn
    existing_today = (
        db.query(Briefing)
        .filter(
            Briefing.user_id == current_user.id,
            Briefing.briefing_type == btype,
            _fn.date(Briefing.generated_at) == _dt_v2.now(_tz_v2.utc).date(),
        )
        .all()
    )
    for row in existing_today:
        db.delete(row)
    if existing_today:
        db.commit()

    prefs = _seed_prefs(db, current_user)
    if btype == "morning":
        ctx = collect_data_for_morning_briefing(
            db, current_user, requested_sections=prefs.morning_sections
        )
        generated = generate_morning_briefing(db, current_user, ctx)
        channels = prefs.morning_channels if body.deliver else ["in_app"]
    else:
        ctx = collect_data_for_evening_briefing(
            db, current_user, requested_sections=prefs.evening_sections
        )
        generated = generate_evening_briefing(db, current_user, ctx)
        channels = prefs.evening_channels if body.deliver else ["in_app"]

    briefing = Briefing(
        company_id=current_user.company_id,
        user_id=current_user.id,
        briefing_type=btype,
        generated_at=_dt_v2.now(_tz_v2.utc),
        delivery_channels=[],
        narrative_text=generated.narrative_text,
        structured_sections=generated.structured_sections.model_dump(),
        active_space_id=generated.active_space_id,
        active_space_name=generated.active_space_name,
        role_slug=generated.role_slug,
        generation_context=generated.generation_context,
        generation_duration_ms=generated.generation_duration_ms,
        intelligence_cost_usd=generated.intelligence_cost_usd,
        input_tokens=generated.input_tokens,
        output_tokens=generated.output_tokens,
    )
    db.add(briefing)
    db.commit()
    db.refresh(briefing)
    try:
        _deliver(db, briefing, channels=channels)
    except Exception:
        logger.exception("Briefing delivery failed post-generate (non-fatal)")
    return _to_v2_out(briefing)


@router.get("/v2/{briefing_id}", response_model=BriefingV2Out)
def get_briefing_v2(
    briefing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a specific briefing — tenant-scoped."""
    row = (
        db.query(Briefing)
        .filter(
            Briefing.id == briefing_id,
            Briefing.user_id == current_user.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Briefing not found")
    return _to_v2_out(row)


@router.post("/v2/{briefing_id}/mark-read", response_model=BriefingV2Out)
def mark_read_v2(
    briefing_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stamp read_at on the briefing (idempotent — second call is a no-op)."""
    row = (
        db.query(Briefing)
        .filter(
            Briefing.id == briefing_id,
            Briefing.user_id == current_user.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Briefing not found")
    if row.read_at is None:
        row.read_at = _dt_v2.now(_tz_v2.utc)
        db.commit()
        db.refresh(row)
    return _to_v2_out(row)
