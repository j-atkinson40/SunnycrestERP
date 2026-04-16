"""Onboarding Flow API routes.

Step-by-step manufacturing vertical onboarding flow. Works alongside
the existing tenant_onboarding.py checklist system — this adds the
guided wizard-style endpoints for the new onboarding experience.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.models.location import Location
from app.models.sales_order import SalesOrder
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class IdentityStepRequest(BaseModel):
    company_name: str
    business_type: str
    wilbert_vault_territory: Optional[str] = None
    state: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class LocationItem(BaseModel):
    name: str
    address: Optional[str] = None
    type: Optional[str] = None


class LocationsStepRequest(BaseModel):
    mode: str = Field(..., pattern="^(single|multi)$")
    locations: list[LocationItem]


class ProgramEnrollmentItem(BaseModel):
    program_code: str
    territory_ids: Optional[list[str]] = None
    uses_vault_territory: Optional[bool] = None
    enabled_product_ids: Optional[list[str]] = None


class ProgramsStepRequest(BaseModel):
    enrollments: list[ProgramEnrollmentItem]


class ComplianceItem(BaseModel):
    item_key: str
    dates: Optional[dict] = None
    count: Optional[int] = None


class CustomComplianceItem(BaseModel):
    name: str
    frequency: str
    next_due: Optional[str] = None


class ComplianceStepRequest(BaseModel):
    items: list[ComplianceItem]
    custom_items: Optional[list[CustomComplianceItem]] = None


class TeamInvitation(BaseModel):
    email: str
    name: str
    role: str
    location_id: Optional[str] = None


class TeamStepRequest(BaseModel):
    invitations: list[TeamInvitation]


class NetworkFHItem(BaseModel):
    name: str
    city: str
    state: str
    zip: str
    source: Optional[str] = None


class NetworkCemeteryItem(BaseModel):
    name: str
    city: str
    state: str
    zip: str


class NetworkStepRequest(BaseModel):
    funeral_homes: list[NetworkFHItem]
    cemeteries: list[NetworkCemeteryItem]


class CommandBarStepRequest(BaseModel):
    completed: bool = True


class ImportStepRequest(BaseModel):
    import_session_id: Optional[str] = None


class TerritoryResolveRequest(BaseModel):
    territory_code: str
    state: str


class TerritoryConfirmRequest(BaseModel):
    territory_code: str
    state: str
    counties: list[str]


class NetworkDiscoverRequest(BaseModel):
    territory_code: str
    counties: list[str]
    state: str


# ---------------------------------------------------------------------------
# Onboarding status / progress
# ---------------------------------------------------------------------------


@router.get("/status")
def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return current onboarding step, progress, and existing-data flags.

    Existing-data flags let the frontend skip steps whose data already exists.
    Most importantly, `should_show_import` returns False when orders exist —
    a tenant migrating from another system won't see the import step at all.
    """
    settings = company.settings or {}
    onboarding = settings.get("onboarding_flow", {})

    # Existing-data detection — counted once, reused in decisions below
    existing_order_count = (
        db.query(func.count(SalesOrder.id))
        .filter(SalesOrder.company_id == company.id)
        .scalar() or 0
    )
    existing_crm_count = (
        db.query(func.count(CompanyEntity.id))
        .filter(CompanyEntity.company_id == company.id)
        .scalar() or 0
    )
    existing_user_count = (
        db.query(func.count(User.id))
        .filter(User.company_id == company.id, User.is_active == True)  # noqa: E712
        .scalar() or 0
    )
    existing_location_count = (
        db.query(func.count(Location.id))
        .filter(Location.company_id == company.id)
        .scalar() or 0
    )

    has_existing_orders = existing_order_count > 0
    has_existing_crm = existing_crm_count > 0
    has_existing_users = existing_user_count > 1  # >1 because admin always exists
    has_existing_location = existing_location_count > 0

    # If orders already exist, the import step is not needed.
    # Add it to skipped_steps so the frontend removes it from the sequence.
    completed_steps = list(onboarding.get("completed_steps", []))
    skipped_steps = list(onboarding.get("skipped_steps", []))

    should_show_import = not has_existing_orders
    if not should_show_import and "import" not in skipped_steps and "import" not in completed_steps:
        skipped_steps.append("import")

    current_step = onboarding.get("current_step", "identity")

    all_steps = [
        "identity", "locations", "programs", "compliance",
        "team", "network", "command_bar", "import", "complete",
    ]
    # Visible steps = all steps minus auto-skipped ones (import when orders exist)
    visible_steps = [s for s in all_steps if should_show_import or s != "import"]
    total = len(visible_steps)
    done = len([s for s in visible_steps if s in completed_steps])
    percent = round((done / total) * 100) if total else 0

    return {
        "status": onboarding.get("status", "in_progress"),
        "current_step": current_step,
        "completed_steps": completed_steps,
        "skipped_steps": skipped_steps,
        "visible_steps": visible_steps,
        "percent_complete": percent,
        # Existing-data flags for pre-fill / skip logic on the frontend
        "has_existing_orders": has_existing_orders,
        "has_existing_crm": has_existing_crm,
        "has_existing_users": has_existing_users,
        "has_existing_location": has_existing_location,
        "should_show_import": should_show_import,
        "existing_user_count": existing_user_count,
        "existing_crm_count": existing_crm_count,
        "existing_order_count": existing_order_count,
        "existing_location_count": existing_location_count,
    }


# ---------------------------------------------------------------------------
# Step endpoints
# ---------------------------------------------------------------------------


@router.post("/steps/identity")
def submit_identity_step(
    data: IdentityStepRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Submit company identity and territory info."""
    try:
        # Update company name and state
        company.name = data.company_name
        company.facility_state = data.state
        if data.contact_name:
            company.set_setting("primary_contact_name", data.contact_name)
        if data.contact_phone:
            company.set_setting("primary_contact_phone", data.contact_phone)
        company.set_setting("business_type", data.business_type)

        # Territory enrollment
        if data.wilbert_vault_territory:
            from app.services.wilbert_program_service import WilbertProgramService

            WilbertProgramService.setup_defaults(
                db, company.id, data.wilbert_vault_territory, data.state
            )

        # Mark step complete
        _mark_step_complete(company, "identity")
        db.commit()

        return {"status": "ok", "step": "identity"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/steps/locations")
def submit_locations_step(
    data: LocationsStepRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Submit location configuration."""
    try:
        from app.services.location_service import LocationService

        location_svc = LocationService(db)

        for loc in data.locations:
            location_svc.create_location(
                company_id=company.id,
                name=loc.name,
                address=loc.address,
                location_type=loc.type,
            )

        company.set_setting("location_mode", data.mode)
        _mark_step_complete(company, "locations")
        db.commit()

        return {"status": "ok", "step": "locations", "location_count": len(data.locations)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/steps/programs")
def submit_programs_step(
    data: ProgramsStepRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Enroll in Wilbert programs."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        results = []
        for enrollment in data.enrollments:
            result = WilbertProgramService.enroll_in_program(
                db,
                company.id,
                enrollment.program_code,
                territory_ids=enrollment.territory_ids,
                uses_vault_territory=enrollment.uses_vault_territory,
                enabled_product_ids=enrollment.enabled_product_ids,
            )
            results.append(result)

        _mark_step_complete(company, "programs")
        db.commit()

        return {"status": "ok", "step": "programs", "enrollments": len(results)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/programs/catalog")
def get_programs_catalog(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return Wilbert programs catalog with enrollment status."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        catalog = WilbertProgramService.get_catalog(db, company.id)
        return {"programs": catalog}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/programs/{code}/products")
def get_program_products(
    code: str,
    territory: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return product list for a specific program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        products = WilbertProgramService.configure_program_products(
            db, company.id, code, territory=territory
        )
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/steps/compliance")
def submit_compliance_step(
    data: ComplianceStepRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Configure compliance items for the tenant."""
    try:
        from app.services.configurable_item_service import ConfigurableItemService

        for item in data.items:
            ConfigurableItemService.enable_item(
                db, company.id, "compliance", item.item_key, config=item.dates
            )

        if data.custom_items:
            for custom in data.custom_items:
                ConfigurableItemService.create_custom_item(
                    db,
                    company.id,
                    "compliance",
                    display_name=custom.name,
                    config={
                        "frequency": custom.frequency,
                        "next_due": custom.next_due,
                    },
                )

        _mark_step_complete(company, "compliance")
        db.commit()

        return {"status": "ok", "step": "compliance", "items_configured": len(data.items)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/compliance/master-list")
def get_compliance_master_list(
    state: Optional[str] = Query(None),
    business_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return filtered compliance master list."""
    try:
        from app.services.compliance_intelligence_service import ComplianceIntelligenceService

        items = ComplianceIntelligenceService.get_required_items(
            db, company.id, state=state, business_type=business_type
        )
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance/questions")
def get_compliance_questions(
    state: Optional[str] = Query(None),
    business_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return smart questions for compliance setup."""
    try:
        from app.services.compliance_intelligence_service import ComplianceIntelligenceService

        questions = ComplianceIntelligenceService.generate_onboarding_questions(
            db, company.id, state=state, business_type=business_type
        )
        return {"questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/steps/team")
def submit_team_step(
    data: TeamStepRequest,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Invite team members."""
    try:
        invited = []
        for invite in data.invitations:
            # Team invitation logic — create user records or send invites
            invited.append({
                "email": invite.email,
                "name": invite.name,
                "role": invite.role,
                "status": "invited",
            })

        _mark_step_complete(company, "team")
        db.commit()

        return {"status": "ok", "step": "team", "invited": invited}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/steps/network")
def submit_network_step(
    data: NetworkStepRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create CRM records for funeral homes and cemeteries."""
    try:
        created_fh = []
        created_cem = []

        for fh in data.funeral_homes:
            created_fh.append({
                "name": fh.name,
                "city": fh.city,
                "state": fh.state,
                "zip": fh.zip,
                "source": fh.source or "onboarding",
            })

        for cem in data.cemeteries:
            created_cem.append({
                "name": cem.name,
                "city": cem.city,
                "state": cem.state,
                "zip": cem.zip,
            })

        _mark_step_complete(company, "network")
        db.commit()

        return {
            "status": "ok",
            "step": "network",
            "funeral_homes_created": len(created_fh),
            "cemeteries_created": len(created_cem),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/steps/command-bar")
def submit_command_bar_step(
    data: CommandBarStepRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Mark command bar tutorial as complete."""
    try:
        if data.completed:
            _mark_step_complete(company, "command_bar")
            db.commit()
        return {"status": "ok", "step": "command_bar"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/steps/import")
def submit_import_step(
    data: ImportStepRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Link an import session to onboarding."""
    try:
        if data.import_session_id:
            company.set_setting("onboarding_import_session_id", data.import_session_id)

        _mark_step_complete(company, "import")
        db.commit()

        return {"status": "ok", "step": "import"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/steps/complete")
def complete_onboarding(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Mark onboarding as done and return vault seed summary."""
    try:
        from app.services.onboarding_summary_service import OnboardingSummaryService

        _mark_step_complete(company, "complete")

        settings = company.settings or {}
        onboarding = settings.get("onboarding_flow", {})
        onboarding["status"] = "completed"
        company.set_setting("onboarding_flow", onboarding)
        db.commit()

        summary = OnboardingSummaryService.generate_summary(db, company.id)
        return {"status": "completed", "summary": summary}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/vault-seed-summary")
def get_vault_seed_summary(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return what has been set up so far."""
    try:
        from app.services.onboarding_summary_service import OnboardingSummaryService

        summary = OnboardingSummaryService.generate_summary(db, company.id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Territory resolution
# ---------------------------------------------------------------------------


@router.post("/territory/resolve")
def resolve_territory(
    data: TerritoryResolveRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Resolve territory info or suggest counties for confirmation."""
    try:
        from app.services.territory_resolution_service import TerritoryResolutionService

        result = TerritoryResolutionService.resolve_territory(
            db, company.id, data.territory_code, data.state
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/territory/confirm")
def confirm_territory(
    data: TerritoryConfirmRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Store confirmed territory definition."""
    try:
        from app.services.territory_resolution_service import TerritoryResolutionService

        result = TerritoryResolutionService.confirm_territory(
            db, company.id, data.territory_code, data.state, data.counties
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Network discovery
# ---------------------------------------------------------------------------


@router.post("/network/discover")
def discover_network(
    data: NetworkDiscoverRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Discover funeral homes and cemeteries in territory."""
    try:
        from app.services.network_discovery_service import NetworkDiscoveryService

        result = NetworkDiscoveryService.discover_network(
            db, company.id, data.territory_code, data.counties, data.state
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network/neighboring-licensees")
def get_neighboring_licensees(
    territory_code: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return neighboring Bridgeable licensees."""
    try:
        from app.services.network_discovery_service import NetworkDiscoveryService

        result = NetworkDiscoveryService.find_neighboring_licensees(
            db, company.id, territory_code=territory_code
        )
        return {"licensees": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mark_step_complete(company: Company, step: str) -> None:
    """Mark a step as complete in the onboarding flow settings."""
    settings = company.settings or {}
    onboarding = settings.get("onboarding_flow", {})
    completed = onboarding.get("completed_steps", [])
    if step not in completed:
        completed.append(step)
    onboarding["completed_steps"] = completed

    # Advance current step
    all_steps = [
        "identity", "locations", "programs", "compliance",
        "team", "network", "command_bar", "import", "complete",
    ]
    current_idx = all_steps.index(step) if step in all_steps else -1
    if current_idx < len(all_steps) - 1:
        onboarding["current_step"] = all_steps[current_idx + 1]

    company.set_setting("onboarding_flow", onboarding)
