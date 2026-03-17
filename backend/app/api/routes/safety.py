"""Safety Management API routes."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.safety import (
    AlertResponse,
    ChemicalCreate,
    ChemicalResponse,
    ChemicalUpdate,
    ComplianceScoreResponse,
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
    InspectionCreate,
    InspectionResponse,
    InspectionResultResponse,
    InspectionResultUpdate,
    InspectionTemplateCreate,
    InspectionTemplateResponse,
    InspectionTemplateUpdate,
    LOTOCreate,
    LOTOResponse,
    LOTOUpdate,
    OSHA300AEntry,
    OSHA300Entry,
    OverdueInspection,
    SafetyProgramCreate,
    SafetyProgramResponse,
    SafetyProgramUpdate,
    TrainingEventCreate,
    TrainingEventResponse,
    TrainingGap,
    TrainingRecordBulkCreate,
    TrainingRecordCreate,
    TrainingRecordResponse,
    TrainingRequirementCreate,
    TrainingRequirementResponse,
)
from app.services import safety_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Safety Programs
# ---------------------------------------------------------------------------


@router.get("/programs", response_model=list[SafetyProgramResponse])
def list_programs(
    status: str | None = None,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List safety programs, optionally filtered by status."""
    return safety_service.list_programs(db, company.id, status=status)


@router.post("/programs", response_model=SafetyProgramResponse, status_code=201)
def create_program(
    data: SafetyProgramCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Create a new safety program."""
    return safety_service.create_program(db, company.id, data)


@router.get("/programs/{program_id}", response_model=SafetyProgramResponse)
def get_program(
    program_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get a single safety program."""
    program = safety_service.get_program(db, company.id, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


@router.put("/programs/{program_id}", response_model=SafetyProgramResponse)
def update_program(
    program_id: str,
    data: SafetyProgramUpdate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Update a safety program."""
    program = safety_service.update_program(db, company.id, program_id, data)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


@router.post("/programs/{program_id}/review", response_model=SafetyProgramResponse)
def review_program(
    program_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Record a review of a safety program."""
    program = safety_service.review_program(
        db, company.id, program_id, current_user.id
    )
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


# ---------------------------------------------------------------------------
# Training Requirements
# ---------------------------------------------------------------------------


@router.get("/training/requirements", response_model=list[TrainingRequirementResponse])
def list_training_requirements(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List all training requirements."""
    return safety_service.list_training_requirements(db, company.id)


@router.post(
    "/training/requirements",
    response_model=TrainingRequirementResponse,
    status_code=201,
)
def create_training_requirement(
    data: TrainingRequirementCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Create a new training requirement."""
    return safety_service.create_training_requirement(db, company.id, data)


# ---------------------------------------------------------------------------
# Training Events
# ---------------------------------------------------------------------------


@router.get("/training")
def list_training_events(
    training_type: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List training events with optional type filter."""
    events, total = safety_service.list_training_events(
        db, company.id, training_type=training_type, limit=limit, offset=offset
    )
    return {"items": events, "total": total}


@router.post("/training", response_model=TrainingEventResponse, status_code=201)
def create_training_event(
    data: TrainingEventCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Create a new training event."""
    return safety_service.create_training_event(
        db, company.id, data, created_by=current_user.id
    )


@router.post(
    "/training/{event_id}/attendees", response_model=list[TrainingRecordResponse]
)
def record_attendees(
    event_id: str,
    data: TrainingRecordBulkCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Record attendees for a training event."""
    return safety_service.record_attendees(
        db, company.id, event_id, data.employee_ids, data.completion_status
    )


@router.get(
    "/training/employee/{employee_id}", response_model=list[TrainingRecordResponse]
)
def get_employee_training(
    employee_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get training history for a specific employee."""
    return safety_service.get_employee_training_history(db, company.id, employee_id)


@router.get("/training/gaps", response_model=list[TrainingGap])
def get_training_gaps(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get training gaps across all employees."""
    return safety_service.get_training_gaps(db, company.id)


# ---------------------------------------------------------------------------
# Inspection Templates
# ---------------------------------------------------------------------------


@router.get("/inspection-templates", response_model=list[InspectionTemplateResponse])
def list_inspection_templates(
    active_only: bool = True,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List inspection templates."""
    return safety_service.list_inspection_templates(
        db, company.id, active_only=active_only
    )


@router.post(
    "/inspection-templates",
    response_model=InspectionTemplateResponse,
    status_code=201,
)
def create_inspection_template(
    data: InspectionTemplateCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Create a new inspection template."""
    return safety_service.create_inspection_template(db, company.id, data)


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------


@router.post("/inspections", response_model=InspectionResponse, status_code=201)
def start_inspection(
    data: InspectionCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Start a new safety inspection."""
    return safety_service.start_inspection(
        db, company.id, data, inspector_id=current_user.id
    )


@router.get("/inspections")
def list_inspections(
    status: str | None = None,
    template_id: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List inspections with optional filters."""
    inspections, total = safety_service.list_inspections(
        db,
        company.id,
        status=status,
        template_id=template_id,
        limit=limit,
        offset=offset,
    )
    return {"items": inspections, "total": total}


@router.get("/inspections/overdue", response_model=list[OverdueInspection])
def get_overdue_inspections(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get list of overdue inspections."""
    return safety_service.get_overdue_inspections(db, company.id)


@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
def get_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get a single inspection with all details."""
    inspection = safety_service.get_inspection(db, company.id, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection


@router.patch(
    "/inspections/{inspection_id}/items/{item_id}",
    response_model=InspectionResultResponse,
)
def update_inspection_result(
    inspection_id: str,
    item_id: str,
    data: InspectionResultUpdate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Update a specific inspection result item."""
    result = safety_service.update_inspection_result(
        db, company.id, inspection_id, item_id, data
    )
    if not result:
        raise HTTPException(status_code=404, detail="Inspection result not found")
    return result


@router.post(
    "/inspections/{inspection_id}/complete", response_model=InspectionResponse
)
def complete_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Mark an inspection as complete."""
    inspection = safety_service.complete_inspection(db, company.id, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection


@router.post(
    "/inspections/{inspection_id}/corrective-actions/{result_id}/complete"
)
def complete_corrective_action(
    inspection_id: str,
    result_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Mark a corrective action as completed."""
    result = safety_service.complete_corrective_action(
        db, company.id, inspection_id, result_id, current_user.id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return {"status": "completed"}


# ---------------------------------------------------------------------------
# Chemicals / SDS
# ---------------------------------------------------------------------------


@router.get("/chemicals", response_model=list[ChemicalResponse])
def list_chemicals(
    active_only: bool = True,
    hazard_class: str | None = None,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List chemicals, optionally filtered by status and hazard class."""
    return safety_service.list_chemicals(
        db, company.id, active_only=active_only, hazard_class=hazard_class
    )


@router.post("/chemicals", response_model=ChemicalResponse, status_code=201)
def create_chemical(
    data: ChemicalCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Create a new chemical record."""
    return safety_service.create_chemical(db, company.id, data)


@router.put("/chemicals/{chemical_id}", response_model=ChemicalResponse)
def update_chemical(
    chemical_id: str,
    data: ChemicalUpdate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Update a chemical record."""
    chemical = safety_service.update_chemical(db, company.id, chemical_id, data)
    if not chemical:
        raise HTTPException(status_code=404, detail="Chemical not found")
    return chemical


@router.get("/chemicals/outdated", response_model=list[ChemicalResponse])
def get_outdated_sds(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get chemicals with outdated SDS documents."""
    chemicals = safety_service.get_outdated_sds(db, company.id)
    for c in chemicals:
        c.hazard_class = safety_service._parse_json(c.hazard_class)
        c.ppe_required = safety_service._parse_json(c.ppe_required)
    return chemicals


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


@router.post("/incidents", response_model=IncidentResponse, status_code=201)
def create_incident(
    data: IncidentCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Report a new safety incident."""
    return safety_service.create_incident(
        db, company.id, data, reported_by=current_user.id
    )


@router.get("/incidents")
def list_incidents(
    incident_type: str | None = None,
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List incidents with optional filters."""
    incidents, total = safety_service.list_incidents(
        db,
        company.id,
        incident_type=incident_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"items": incidents, "total": total}


@router.get("/incidents/osha-300", response_model=list[OSHA300Entry])
def get_osha_300_log(
    year: int | None = None,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get OSHA 300 log entries for a given year."""
    yr = year or date.today().year
    return safety_service.get_osha_300_log(db, company.id, yr)


@router.get("/incidents/osha-300a", response_model=OSHA300AEntry)
def get_osha_300a_summary(
    year: int | None = None,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get OSHA 300A annual summary for a given year."""
    yr = year or date.today().year - 1
    return safety_service.get_osha_300a_summary(db, company.id, yr)


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get a single incident with full details."""
    incident = safety_service.get_incident(db, company.id, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
def update_incident(
    incident_id: str,
    data: IncidentUpdate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Update an incident record."""
    incident = safety_service.update_incident(db, company.id, incident_id, data)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/incidents/{incident_id}/close", response_model=IncidentResponse)
def close_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Close an incident investigation."""
    incident = safety_service.close_incident(db, company.id, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


# ---------------------------------------------------------------------------
# LOTO Procedures
# ---------------------------------------------------------------------------


@router.get("/loto", response_model=list[LOTOResponse])
def list_loto(
    active_only: bool = True,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List lockout/tagout procedures."""
    return safety_service.list_loto(db, company.id, active_only=active_only)


@router.post("/loto", response_model=LOTOResponse, status_code=201)
def create_loto(
    data: LOTOCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.create")),
):
    """Create a new LOTO procedure."""
    return safety_service.create_loto(db, company.id, data)


@router.get("/loto/{loto_id}", response_model=LOTOResponse)
def get_loto(
    loto_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Get a single LOTO procedure."""
    proc = safety_service.get_loto(db, company.id, loto_id)
    if not proc:
        raise HTTPException(status_code=404, detail="LOTO procedure not found")
    return proc


@router.put("/loto/{loto_id}", response_model=LOTOResponse)
def update_loto(
    loto_id: str,
    data: LOTOUpdate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Update a LOTO procedure."""
    proc = safety_service.update_loto(db, company.id, loto_id, data)
    if not proc:
        raise HTTPException(status_code=404, detail="LOTO procedure not found")
    return proc


@router.post("/loto/{loto_id}/review", response_model=LOTOResponse)
def review_loto(
    loto_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Record a review of a LOTO procedure."""
    proc = safety_service.review_loto(db, company.id, loto_id)
    if not proc:
        raise HTTPException(status_code=404, detail="LOTO procedure not found")
    return proc


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(
    active_only: bool = True,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """List safety alerts."""
    return safety_service.list_alerts(db, company.id, active_only=active_only)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.edit")),
):
    """Acknowledge a safety alert."""
    alert = safety_service.acknowledge_alert(
        db, company.id, alert_id, current_user.id
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


# ---------------------------------------------------------------------------
# Compliance Score
# ---------------------------------------------------------------------------


@router.get("/compliance-score", response_model=ComplianceScoreResponse)
def get_compliance_score(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
    current_user: User = Depends(require_permission("safety.view")),
):
    """Calculate and return the overall safety compliance score."""
    return safety_service.calculate_compliance_score(db, company.id)
