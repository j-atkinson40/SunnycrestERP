from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.qc import QCInspection
from app.models.user import User
from app.schemas.qc import (
    CompleteInspectionRequest,
    DashboardStats,
    DefectTypeCreate,
    DefectTypeResponse,
    DispositionCreate,
    DispositionResponse,
    InspectionCreate,
    InspectionListItem,
    InspectionListResponse,
    InspectionResponse,
    MediaCreate,
    MediaResponse,
    ReworkCreate,
    ReworkResponse,
    StepCreate,
    StepResponse,
    StepResultResponse,
    StepResultUpdate,
    StepUpdate,
    TemplateCreate,
    TemplateResponse,
)
from app.services.qc_service import (
    add_step,
    complete_inspection,
    complete_rework,
    create_defect_type,
    create_disposition,
    create_inspection,
    create_media,
    create_rework_record,
    create_template,
    delete_step,
    get_dashboard_stats,
    get_inspection,
    get_item_qc_history,
    get_qc_summary,
    get_template,
    list_defect_types,
    list_inspections,
    list_templates,
    update_step,
    update_step_result,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _inspection_to_response(inspection: QCInspection) -> dict:
    """Convert a QCInspection ORM object to a full response dict."""
    data = InspectionResponse.model_validate(inspection).model_dump()
    if inspection.inspector:
        data["inspector_name"] = (
            f"{inspection.inspector.first_name} {inspection.inspector.last_name}"
        )
    # Enrich step results
    step_results = []
    for sr in inspection.step_results:
        sr_data = StepResultResponse.model_validate(sr).model_dump()
        if sr.step:
            sr_data["step"] = StepResponse.model_validate(sr.step).model_dump()
        if sr.defect_type:
            sr_data["defect_type"] = DefectTypeResponse.model_validate(
                sr.defect_type
            ).model_dump()
        step_results.append(sr_data)
    data["step_results"] = step_results
    # Enrich disposition
    if inspection.disposition:
        disp_data = DispositionResponse.model_validate(
            inspection.disposition
        ).model_dump()
        if inspection.disposition.decider:
            disp_data["decided_by_name"] = (
                f"{inspection.disposition.decider.first_name} "
                f"{inspection.disposition.decider.last_name}"
            )
        data["disposition"] = disp_data
    # Media
    data["media"] = [
        MediaResponse.model_validate(m).model_dump() for m in inspection.media
    ]
    return data


def _inspection_to_list_item(inspection: QCInspection) -> dict:
    """Convert a QCInspection ORM object to a list item dict."""
    data = InspectionListItem.model_validate(inspection).model_dump()
    if inspection.inspector:
        data["inspector_name"] = (
            f"{inspection.inspector.first_name} {inspection.inspector.last_name}"
        )
    if hasattr(inspection, "template") and inspection.template:
        data["template_name"] = inspection.template.template_name
    # Populate step counts if step_results are loaded
    if hasattr(inspection, "step_results") and inspection.step_results:
        data["step_count"] = len(inspection.step_results)
        data["pass_count"] = sum(
            1 for sr in inspection.step_results if sr.result == "pass"
        )
        data["fail_count"] = sum(
            1 for sr in inspection.step_results if sr.result == "fail"
        )
    return data


# ---------------------------------------------------------------------------
# Template endpoints
# ---------------------------------------------------------------------------


@router.get("/templates")
def list_templates_endpoint(
    product_category: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """List inspection templates."""
    result = list_templates(
        db,
        current_user.company_id,
        product_category=product_category,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [
            TemplateResponse.model_validate(t).model_dump()
            for t in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/templates/{template_id}")
def get_template_endpoint(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """Get a single template with steps."""
    template = get_template(db, template_id, current_user.company_id)
    return TemplateResponse.model_validate(template).model_dump()


@router.post("/templates", status_code=201)
def create_template_endpoint(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.create")),
):
    """Create a new inspection template."""
    template = create_template(db, current_user.company_id, data)
    return TemplateResponse.model_validate(template).model_dump()


@router.get("/templates/{template_id}/steps")
def list_template_steps_endpoint(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """Get all steps for a template."""
    template = get_template(db, template_id, current_user.company_id)
    return [
        StepResponse.model_validate(s).model_dump() for s in template.steps
    ]


# ---------------------------------------------------------------------------
# Inspection endpoints
# ---------------------------------------------------------------------------


@router.get("/inspections")
def list_inspections_endpoint(
    status: str | None = Query(None),
    product_category: str | None = Query(None),
    search: str | None = Query(None),
    inspector_id: str | None = Query(None),
    inventory_item_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """List inspections with optional filters."""
    result = list_inspections(
        db,
        current_user.company_id,
        inspection_status=status,
        product_category=product_category,
        search=search,
        inspector_id=inspector_id,
        inventory_item_id=inventory_item_id,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [
            _inspection_to_list_item(i) for i in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/inspections/{inspection_id}")
def get_inspection_endpoint(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """Get a single inspection with all details."""
    inspection = get_inspection(db, inspection_id, current_user.company_id)
    return _inspection_to_response(inspection)


@router.post("/inspections", status_code=201)
def create_inspection_endpoint(
    data: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.create")),
):
    """Create a new inspection."""
    inspection = create_inspection(
        db, current_user.company_id, data, current_user.id
    )
    return _inspection_to_response(inspection)


@router.patch("/inspections/{inspection_id}/steps/{step_id}")
def update_step_result_endpoint(
    inspection_id: str,
    step_id: str,
    data: StepResultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """Update the result for a specific step in an inspection."""
    step_result = update_step_result(
        db, inspection_id, step_id, current_user.company_id, data
    )
    return StepResultResponse.model_validate(step_result).model_dump()


@router.post("/inspections/{inspection_id}/complete")
def complete_inspection_endpoint(
    inspection_id: str,
    data: CompleteInspectionRequest = CompleteInspectionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """Finalize an inspection."""
    inspection = complete_inspection(
        db, inspection_id, current_user.company_id, data.overall_notes
    )
    return _inspection_to_response(inspection)


@router.post("/inspections/{inspection_id}/disposition", status_code=201)
def create_disposition_endpoint(
    inspection_id: str,
    data: DispositionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.edit")),
):
    """Record a disposition decision for an inspection."""
    disposition = create_disposition(
        db, inspection_id, current_user.company_id, data, current_user.id
    )
    disp_data = DispositionResponse.model_validate(disposition).model_dump()
    return disp_data


@router.post("/inspections/{inspection_id}/rework", status_code=201)
def create_rework_endpoint(
    inspection_id: str,
    data: ReworkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.edit")),
):
    """Create a rework record for an inspection."""
    rework = create_rework_record(
        db, inspection_id, current_user.company_id, data
    )
    return ReworkResponse.model_validate(rework).model_dump()


@router.post("/rework/{rework_id}/complete")
def complete_rework_endpoint(
    rework_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.edit")),
):
    """Complete a rework record and create re-inspection."""
    rework = complete_rework(
        db, rework_id, current_user.company_id, current_user.id
    )
    return ReworkResponse.model_validate(rework).model_dump()


# ---------------------------------------------------------------------------
# Media endpoint
# ---------------------------------------------------------------------------


@router.post("/media", status_code=201)
def create_media_endpoint(
    data: MediaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.create")),
):
    """Upload/register a QC media record."""
    media = create_media(db, current_user.company_id, data)
    return MediaResponse.model_validate(media).model_dump()


# ---------------------------------------------------------------------------
# Defect types
# ---------------------------------------------------------------------------


@router.get("/defect-types")
def list_defect_types_endpoint(
    product_category: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """List defect types."""
    defects = list_defect_types(
        db, current_user.company_id, product_category=product_category
    )
    return [DefectTypeResponse.model_validate(d).model_dump() for d in defects]


# ---------------------------------------------------------------------------
# Dashboard & Stats
# ---------------------------------------------------------------------------


@router.get("/stats/dashboard")
def dashboard_stats_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """Get QC dashboard stats."""
    return get_dashboard_stats(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Item history
# ---------------------------------------------------------------------------


@router.get("/items/{inventory_item_id}/history")
def item_qc_history_endpoint(
    inventory_item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """Get QC inspection history for a specific inventory item."""
    inspections = get_item_qc_history(
        db, inventory_item_id, current_user.company_id
    )
    return [_inspection_to_list_item(i) for i in inspections]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports/summary")
def qc_summary_report_endpoint(
    product_category: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("qc.view")),
):
    """Get QC summary report."""
    return get_qc_summary(
        db,
        current_user.company_id,
        product_category=product_category,
        date_from=date_from,
        date_to=date_to,
    )
