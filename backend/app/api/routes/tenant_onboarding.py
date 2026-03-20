"""Tenant Onboarding API routes.

Provides onboarding checklist, guided scenarios, product library import,
data imports, integration setup, and contextual help for new tenants.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.services import tenant_onboarding_service
from app.schemas.tenant_onboarding import (
    CheckInCallSchedule,
    ChecklistItemUpdate,
    CrossTenantPreferences,
    DataImportCreate,
    DataImportUpdate,
    HelpDismissalCreate,
    IntegrationSetupCreate,
    IntegrationSetupUpdate,
    ProductTemplateImportRequest,
    SchedulingBoardConfig,
    ScenarioAdvance,
    WhiteGloveRequest,
)

router = APIRouter()


@router.get("/debug-init")
def debug_init_checklist(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Debug: try to initialize checklist and return any errors as 200."""
    import traceback
    try:
        preset = getattr(company, "vertical", None) or "manufacturing"
        result = tenant_onboarding_service.initialize_checklist(db, company.id, preset)
        return {"status": "ok", "preset": preset, "checklist_id": getattr(result, "id", None)}
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)[:500]}",
            "traceback": traceback.format_exc()[-1500:],
        }


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------


@router.get("/checklist")
def get_checklist(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get the tenant's onboarding checklist with all items."""
    result = tenant_onboarding_service.get_checklist(db, company.id)
    if not result:
        raise HTTPException(status_code=404, detail="Onboarding checklist not found")
    return result


@router.post("/checklist/initialize", status_code=201)
def initialize_checklist(
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Initialize onboarding checklist (admin only). Usually auto-called during tenant creation."""
    preset = getattr(company, "vertical", None) or "manufacturing"
    return tenant_onboarding_service.initialize_checklist(db, company.id, preset)


@router.patch("/checklist/items/{item_key}")
def update_checklist_item(
    item_key: str,
    data: ChecklistItemUpdate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update a checklist item (skip, mark in_progress, etc.)."""
    if data.skipped:
        return tenant_onboarding_service.skip_item(db, company.id, item_key)
    if data.status == "in_progress":
        return tenant_onboarding_service.update_item_status(
            db, company.id, item_key, "in_progress"
        )
    raise HTTPException(status_code=400, detail="No valid update provided")


@router.post("/checklist/items/{item_key}/complete")
def complete_checklist_item(
    item_key: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Manually mark a checklist item as complete (for items without automatic triggers)."""
    return tenant_onboarding_service.check_completion(db, company.id, item_key)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@router.get("/scenarios")
def list_scenarios(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all scenarios for this tenant."""
    return tenant_onboarding_service.list_scenarios(db, company.id)


@router.get("/scenarios/{scenario_key}")
def get_scenario(
    scenario_key: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get a scenario with all its steps."""
    result = tenant_onboarding_service.get_scenario(db, company.id, scenario_key)
    if not result:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return result


@router.post("/scenarios/{scenario_key}/start")
def start_scenario(
    scenario_key: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Start a scenario walkthrough."""
    return tenant_onboarding_service.start_scenario(db, company.id, scenario_key)


@router.post("/scenarios/{scenario_key}/advance")
def advance_scenario(
    scenario_key: str,
    data: ScenarioAdvance,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Advance to the next step in a scenario."""
    return tenant_onboarding_service.advance_scenario(
        db, company.id, scenario_key, data.step_key, data.result
    )


# ---------------------------------------------------------------------------
# Product Catalog Templates
# ---------------------------------------------------------------------------


@router.get("/product-library")
def get_product_library(
    preset: str | None = Query(None),
    category: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get product catalog templates for the starter library."""
    return tenant_onboarding_service.get_product_library(
        db, company.id, preset=preset, category=category
    )


@router.post("/product-library/import", status_code=201)
def import_products(
    data: ProductTemplateImportRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Import selected product templates as real products."""
    return tenant_onboarding_service.import_product_templates(
        db, company.id, data.template_ids, current_user.id
    )


# ---------------------------------------------------------------------------
# Data Imports
# ---------------------------------------------------------------------------


@router.post("/imports", status_code=201)
def create_import(
    data: DataImportCreate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Start a new data import session."""
    return tenant_onboarding_service.create_import(
        db, company.id, data.model_dump(exclude_none=True), current_user.id
    )


@router.get("/imports")
def list_imports(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all import sessions for this tenant."""
    return tenant_onboarding_service.list_imports(db, company.id)


@router.get("/imports/{import_id}")
def get_import(
    import_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get details of a data import session."""
    result = tenant_onboarding_service.get_import(db, company.id, import_id)
    if not result:
        raise HTTPException(status_code=404, detail="Import session not found")
    return result


@router.patch("/imports/{import_id}")
def update_import(
    import_id: str,
    data: DataImportUpdate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update an import session (field mapping, status, etc.)."""
    result = tenant_onboarding_service.update_import(
        db, company.id, import_id, data.model_dump(exclude_none=True)
    )
    if not result:
        raise HTTPException(status_code=404, detail="Import session not found")
    return result


@router.post("/imports/{import_id}/preview")
def preview_import(
    import_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Generate a preview of the import data."""
    result = tenant_onboarding_service.preview_import(db, company.id, import_id)
    if not result:
        raise HTTPException(status_code=404, detail="Import session not found")
    return result


@router.post("/imports/{import_id}/execute")
def execute_import(
    import_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Execute the import."""
    return tenant_onboarding_service.execute_import(
        db, company.id, import_id, current_user.id
    )


@router.post("/imports/white-glove", status_code=201)
def request_white_glove(
    data: WhiteGloveRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Request white-glove import assistance."""
    return tenant_onboarding_service.request_white_glove(
        db, company.id, data.model_dump(exclude_none=True), current_user.id
    )


# ---------------------------------------------------------------------------
# Integration Setup
# ---------------------------------------------------------------------------


@router.get("/integrations")
def list_integrations(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List integration setup status."""
    return tenant_onboarding_service.list_integrations(db, company.id)


@router.post("/integrations", status_code=201)
def create_integration(
    data: IntegrationSetupCreate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Start integration setup flow."""
    return tenant_onboarding_service.create_integration(
        db, company.id, data.model_dump(exclude_none=True), current_user.id
    )


@router.patch("/integrations/{integration_id}")
def update_integration(
    integration_id: str,
    data: IntegrationSetupUpdate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update integration setup (acknowledge briefing, approve sandbox, etc.)."""
    result = tenant_onboarding_service.update_integration(
        db, company.id, integration_id, data.model_dump(exclude_none=True)
    )
    if not result:
        raise HTTPException(status_code=404, detail="Integration setup not found")
    return result


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


@router.post("/help/dismiss")
def dismiss_help(
    data: HelpDismissalCreate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Dismiss a help tooltip or panel."""
    return tenant_onboarding_service.dismiss_help(
        db, company.id, current_user.id, data.help_key
    )


@router.get("/help/dismissed")
def get_dismissed_help(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get list of dismissed help keys for the current user."""
    return tenant_onboarding_service.get_dismissed_help(
        db, company.id, current_user.id
    )


# ---------------------------------------------------------------------------
# Check-in Call
# ---------------------------------------------------------------------------


@router.post("/check-in-call", status_code=201)
def schedule_check_in(
    data: CheckInCallSchedule,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Record check-in call scheduling decision."""
    return tenant_onboarding_service.schedule_check_in(
        db, company.id, data.model_dump(exclude_none=True), current_user.id
    )


# ---------------------------------------------------------------------------
# Scheduling Board Setup
# ---------------------------------------------------------------------------


@router.post("/scheduling-board/configure")
def configure_scheduling_board(
    data: SchedulingBoardConfig,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Save scheduling board configuration and mark checklist item complete."""
    company.set_setting("scheduling_board_driver_count", data.driver_count)
    company.set_setting("scheduling_board_saturday_handling", data.saturday_handling)
    company.set_setting("scheduling_board_lead_time", data.lead_time)
    if data.lead_time_custom_days is not None:
        company.set_setting("scheduling_board_lead_time_custom_days", data.lead_time_custom_days)
    company.set_setting("scheduling_board_configured", True)
    db.commit()

    # Mark onboarding item complete
    try:
        tenant_onboarding_service.check_completion(db, company.id, "setup_scheduling_board")
    except Exception:
        pass  # Item may not exist if checklist wasn't initialized

    return {"status": "ok", "settings": {
        "driver_count": data.driver_count,
        "saturday_handling": data.saturday_handling,
        "lead_time": data.lead_time,
        "lead_time_custom_days": data.lead_time_custom_days,
    }}


@router.get("/scheduling-board/config")
def get_scheduling_board_config(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    """Get current scheduling board configuration."""
    return {
        "driver_count": company.get_setting("scheduling_board_driver_count", 2),
        "saturday_handling": company.get_setting("scheduling_board_saturday_handling", "normal"),
        "lead_time": company.get_setting("scheduling_board_lead_time", "2_business_days"),
        "lead_time_custom_days": company.get_setting("scheduling_board_lead_time_custom_days"),
        "configured": company.get_setting("scheduling_board_configured", False),
    }


# ---------------------------------------------------------------------------
# Cross-Tenant Preferences
# ---------------------------------------------------------------------------


@router.post("/cross-tenant-preferences")
def save_cross_tenant_preferences(
    data: CrossTenantPreferences,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Save cross-tenant network preferences and manage extension installs."""
    from app.services import extension_service

    company.set_setting("delivery_notifications_enabled", data.delivery_notifications_enabled)
    company.set_setting("cemetery_delivery_notifications", data.cemetery_delivery_notifications)
    company.set_setting("allow_portal_spring_burial_requests", data.allow_portal_spring_burial_requests)
    company.set_setting("accept_legacy_print_submissions", data.accept_legacy_print_submissions)
    # Driver status milestones
    company.set_setting("milestone_scheduled_enabled", data.milestone_scheduled_enabled)
    company.set_setting("milestone_on_my_way_enabled", data.milestone_on_my_way_enabled)
    company.set_setting("milestone_arrived_enabled", data.milestone_arrived_enabled)
    company.set_setting("milestone_delivered_enabled", data.milestone_delivered_enabled)
    company.set_setting("cross_tenant_preferences_configured", True)
    db.commit()

    # Install/enable extensions based on preferences
    if data.delivery_notifications_enabled:
        try:
            ext_def = extension_service.get_extension(db, "funeral_home_coordination")
            te = extension_service.get_tenant_extension(db, company.id, "funeral_home_coordination")
            if ext_def and not te:
                extension_service.install_extension(db, company.id, "funeral_home_coordination")
            elif te and not te.enabled:
                te.enabled = True
                te.status = "active" if not ext_def.setup_required else "pending_setup"
                db.commit()
        except Exception:
            pass
    else:
        te = extension_service.get_tenant_extension(db, company.id, "funeral_home_coordination")
        if te and te.enabled:
            te.enabled = False
            te.status = "disabled"
            db.commit()

    if data.accept_legacy_print_submissions:
        try:
            ext_def = extension_service.get_extension(db, "legacy_print_generator")
            te = extension_service.get_tenant_extension(db, company.id, "legacy_print_generator")
            if ext_def and not te:
                extension_service.install_extension(db, company.id, "legacy_print_generator")
            elif te and not te.enabled:
                te.enabled = True
                te.status = "active"
                db.commit()
        except Exception:
            pass
    else:
        te = extension_service.get_tenant_extension(db, company.id, "legacy_print_generator")
        if te and te.enabled:
            te.enabled = False
            te.status = "disabled"
            db.commit()

    # Mark onboarding item complete only if delivery area is also configured
    delivery_area_configured = company.get_setting("delivery_area_configured", False)
    if delivery_area_configured:
        try:
            tenant_onboarding_service.check_completion(db, company.id, "configure_cross_tenant")
        except Exception:
            pass

    return {"status": "ok", "preferences": data.model_dump()}


@router.get("/cross-tenant-preferences")
def get_cross_tenant_preferences(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    """Get current cross-tenant network preferences."""
    return {
        "delivery_notifications_enabled": company.get_setting("delivery_notifications_enabled", True),
        "cemetery_delivery_notifications": company.get_setting("cemetery_delivery_notifications", True),
        "allow_portal_spring_burial_requests": company.get_setting("allow_portal_spring_burial_requests", True),
        "accept_legacy_print_submissions": company.get_setting("accept_legacy_print_submissions", True),
        "cross_tenant_preferences_configured": company.get_setting("cross_tenant_preferences_configured", False),
        "spring_burials_enabled": company.get_setting("spring_burials_enabled", False),
        # Driver status milestones
        "milestone_scheduled_enabled": company.get_setting("milestone_scheduled_enabled", True),
        "milestone_on_my_way_enabled": company.get_setting("milestone_on_my_way_enabled", True),
        "milestone_arrived_enabled": company.get_setting("milestone_arrived_enabled", True),
        "milestone_delivered_enabled": company.get_setting("milestone_delivered_enabled", True),
        # Delivery area
        "delivery_area_configured": company.get_setting("delivery_area_configured", False),
        "facility_state": company.facility_state,
    }
