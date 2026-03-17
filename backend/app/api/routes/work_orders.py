"""Work Order & Production Management API routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module
from app.database import get_db
from app.models.user import User
from app.services import work_order_service as svc

router = APIRouter(
    dependencies=[Depends(require_module("work_orders"))],
)


# ---------------------------------------------------------------------------
# Request / Response schemas (inline for simplicity)
# ---------------------------------------------------------------------------


class WorkOrderCreate(BaseModel):
    product_id: str
    product_variant_id: str | None = None
    quantity_ordered: int
    trigger_type: str = "manual"
    needed_by_date: date | None = None
    priority: str = "standard"
    notes: str | None = None


class PriorityUpdate(BaseModel):
    priority: str


class CancelRequest(BaseModel):
    reason: str


class ReceiveRequest(BaseModel):
    location: str


class PourEventCreate(BaseModel):
    pour_date: date
    pour_time: str | None = None
    crew_notes: str | None = None
    cure_schedule_id: str | None = None
    work_order_items: list[dict] = Field(
        ...,
        description="List of {work_order_id, quantity_in_this_pour}",
    )


class CompletePourRequest(BaseModel):
    mix_design_id: str | None = None
    design_strength_psi: int | None = None
    water_cement_ratio: float | None = None
    slump_inches: float | None = None
    air_content_percent: float | None = None
    ambient_temp_f: int | None = None
    concrete_temp_f: int | None = None
    yield_cubic_yards: float | None = None
    notes: str | None = None


class CureReleaseRequest(BaseModel):
    override_reason: str | None = None


class MixDesignCreate(BaseModel):
    mix_design_code: str
    name: str
    design_strength_psi: int
    cement_type: str | None = None
    description: str | None = None
    npca_approved: bool = False
    cure_schedule_id: str | None = None


class MixDesignUpdate(BaseModel):
    mix_design_code: str | None = None
    name: str | None = None
    design_strength_psi: int | None = None
    cement_type: str | None = None
    description: str | None = None
    npca_approved: bool | None = None
    cure_schedule_id: str | None = None
    is_active: bool | None = None


class CureScheduleCreate(BaseModel):
    name: str
    description: str | None = None
    duration_hours: int
    minimum_strength_release_percent: int = 70
    temperature_adjusted: bool = False
    notes: str | None = None
    is_default: bool = False


class CureScheduleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_hours: int | None = None
    minimum_strength_release_percent: int | None = None
    temperature_adjusted: bool | None = None
    notes: str | None = None
    is_default: bool | None = None


class ReplenishmentRuleCreate(BaseModel):
    product_id: str
    product_variant_id: str | None = None
    minimum_stock_quantity: int
    target_stock_quantity: int
    is_active: bool = True


class ReplenishmentRuleUpdate(BaseModel):
    product_id: str | None = None
    product_variant_id: str | None = None
    minimum_stock_quantity: int | None = None
    target_stock_quantity: int | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Work Order list & create (no path params — must come before {wo_id})
# ---------------------------------------------------------------------------


@router.get("/")
def list_work_orders(
    status: str | None = None,
    trigger_type: str | None = None,
    product_id: str | None = None,
    priority: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List work orders with optional filters."""
    return svc.list_work_orders(
        db,
        current_user.company_id,
        status=status,
        trigger_type=trigger_type,
        product_id=product_id,
        priority=priority,
        page=page,
        per_page=per_page,
    )


@router.post("/", status_code=201)
def create_work_order(
    data: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new manual work order."""
    return svc.create_work_order(
        db,
        current_user.company_id,
        data.model_dump(exclude_none=True),
        current_user.id,
    )


@router.get("/production-board")
def production_board(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Foreman's production board: active WOs grouped by status."""
    return svc.get_production_board(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Pour Event endpoints (literal paths — must come before {wo_id})
# ---------------------------------------------------------------------------


@router.get("/pour-events")
def list_pour_events(
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List pour events with optional status filter."""
    return svc.list_pour_events(
        db, current_user.company_id, status=status, page=page, per_page=per_page
    )


@router.post("/pour-events", status_code=201)
def create_pour_event(
    data: PourEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a pour event linked to work orders."""
    pe_data = data.model_dump(exclude={"work_order_items"})
    return svc.create_pour_event(
        db,
        current_user.company_id,
        pe_data,
        data.work_order_items,
        current_user.id,
    )


@router.get("/pour-events/cure-board")
def cure_board(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cure board: all curing pour events with progress info."""
    return svc.get_cure_board(db, current_user.company_id)


@router.get("/pour-events/{pe_id}")
def get_pour_event(
    pe_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get pour event detail with linked WOs and batch ticket."""
    return svc.get_pour_event(db, current_user.company_id, pe_id)


@router.patch("/pour-events/{pe_id}/start")
def start_pour(
    pe_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a pour event (planned -> in_progress)."""
    return svc.start_pour(db, current_user.company_id, pe_id)


@router.patch("/pour-events/{pe_id}/complete")
def complete_pour(
    pe_id: str,
    data: CompletePourRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete a pour with batch ticket data (transitions to curing)."""
    return svc.complete_pour(
        db, current_user.company_id, pe_id, data.model_dump(exclude_none=True)
    )


@router.patch("/pour-events/{pe_id}/release")
def release_from_cure(
    pe_id: str,
    data: CureReleaseRequest = CureReleaseRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Release a pour event from curing. Override reason required if early."""
    return svc.release_from_cure(
        db, current_user.company_id, pe_id, data.override_reason
    )


# ---------------------------------------------------------------------------
# Mix Design endpoints (literal paths — must come before {wo_id})
# ---------------------------------------------------------------------------


@router.get("/mix-designs")
def list_mix_designs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all mix designs."""
    return svc.list_mix_designs(db, current_user.company_id)


@router.post("/mix-designs", status_code=201)
def create_mix_design(
    data: MixDesignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new mix design."""
    return svc.create_mix_design(
        db, current_user.company_id, data.model_dump(exclude_none=True)
    )


@router.put("/mix-designs/{md_id}")
def update_mix_design(
    md_id: str,
    data: MixDesignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a mix design."""
    return svc.update_mix_design(
        db, current_user.company_id, md_id, data.model_dump(exclude_none=True)
    )


# ---------------------------------------------------------------------------
# Cure Schedule endpoints (literal paths — must come before {wo_id})
# ---------------------------------------------------------------------------


@router.get("/cure-schedules")
def list_cure_schedules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all cure schedules."""
    return svc.list_cure_schedules(db, current_user.company_id)


@router.post("/cure-schedules", status_code=201)
def create_cure_schedule(
    data: CureScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new cure schedule."""
    return svc.create_cure_schedule(
        db, current_user.company_id, data.model_dump(exclude_none=True)
    )


@router.put("/cure-schedules/{cs_id}")
def update_cure_schedule(
    cs_id: str,
    data: CureScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a cure schedule."""
    return svc.update_cure_schedule(
        db, current_user.company_id, cs_id, data.model_dump(exclude_none=True)
    )


# ---------------------------------------------------------------------------
# Replenishment Rule endpoints (literal paths — must come before {wo_id})
# ---------------------------------------------------------------------------


@router.get("/replenishment-rules")
def list_replenishment_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all stock replenishment rules."""
    return svc.list_replenishment_rules(db, current_user.company_id)


@router.post("/replenishment-rules", status_code=201)
def create_replenishment_rule(
    data: ReplenishmentRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new replenishment rule."""
    return svc.create_replenishment_rule(
        db, current_user.company_id, data.model_dump(exclude_none=True)
    )


@router.put("/replenishment-rules/{rule_id}")
def update_replenishment_rule(
    rule_id: str,
    data: ReplenishmentRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a replenishment rule."""
    return svc.update_replenishment_rule(
        db, current_user.company_id, rule_id, data.model_dump(exclude_none=True)
    )


@router.delete("/replenishment-rules/{rule_id}", status_code=204)
def delete_replenishment_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a replenishment rule."""
    svc.delete_replenishment_rule(db, current_user.company_id, rule_id)


# ---------------------------------------------------------------------------
# Work Order detail & actions (parameterized — must come AFTER literal paths)
# ---------------------------------------------------------------------------


@router.get("/{wo_id}")
def get_work_order(
    wo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get work order detail."""
    return svc.get_work_order(db, current_user.company_id, wo_id)


@router.patch("/{wo_id}/release")
def release_to_production(
    wo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Release a draft work order to production (draft -> open)."""
    return svc.release_to_production(db, current_user.company_id, wo_id)


@router.patch("/{wo_id}/priority")
def update_priority(
    wo_id: str,
    data: PriorityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update work order priority."""
    return svc.update_priority(db, current_user.company_id, wo_id, data.priority)


@router.patch("/{wo_id}/cancel")
def cancel_work_order(
    wo_id: str,
    data: CancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a work order (only if no units produced)."""
    return svc.cancel_work_order(
        db, current_user.company_id, wo_id, data.reason, current_user.id
    )


@router.get("/{wo_id}/products")
def list_wo_products(
    wo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all units produced for a work order."""
    return svc.list_wo_products(db, current_user.company_id, wo_id)


@router.patch("/{wo_id}/products/{product_id}/receive")
def receive_unit(
    wo_id: str,
    product_id: str,
    data: ReceiveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Receive a single unit to inventory (must have passed QC)."""
    return svc.receive_unit(
        db, current_user.company_id, product_id, data.location, current_user.id
    )


@router.post("/{wo_id}/receive-all")
def bulk_receive(
    wo_id: str,
    data: ReceiveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk receive all QC-passed units for a work order."""
    return svc.bulk_receive(
        db, current_user.company_id, wo_id, data.location, current_user.id
    )
