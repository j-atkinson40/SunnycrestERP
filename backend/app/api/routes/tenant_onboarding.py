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
    DataImportCreate,
    DataImportUpdate,
    HelpDismissalCreate,
    IntegrationSetupCreate,
    IntegrationSetupUpdate,
    ProductTemplateImportRequest,
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
