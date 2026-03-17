"""Safety Management service — core CRUD and business logic."""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.safety_program import SafetyProgram
from app.models.safety_training import (
    SafetyTrainingRequirement,
    SafetyTrainingEvent,
    EmployeeTrainingRecord,
)
from app.models.safety_inspection import (
    SafetyInspection,
    SafetyInspectionItem,
    SafetyInspectionResult,
    SafetyInspectionTemplate,
)
from app.models.safety_chemical import SafetyChemical
from app.models.safety_incident import SafetyIncident
from app.models.safety_loto import SafetyLotoProcedure
from app.models.safety_alert import SafetyAlert
from app.models.user import User

logger = logging.getLogger(__name__)


# ---- helpers ----

def _parse_json(val: str | None) -> list | dict | None:
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None

def _dump_json(val) -> str | None:
    if val is None:
        return None
    return json.dumps(val)


# ============================================================
# Safety Programs
# ============================================================

def list_programs(db: Session, company_id: str, status: str | None = None):
    q = db.query(SafetyProgram).filter(SafetyProgram.company_id == company_id)
    if status:
        q = q.filter(SafetyProgram.status == status)
    programs = q.order_by(SafetyProgram.program_name).all()
    for p in programs:
        p.applicable_job_roles = _parse_json(p.applicable_job_roles)
    return programs

def get_program(db: Session, company_id: str, program_id: str):
    p = db.query(SafetyProgram).filter(
        SafetyProgram.id == program_id,
        SafetyProgram.company_id == company_id,
    ).first()
    if p:
        p.applicable_job_roles = _parse_json(p.applicable_job_roles)
    return p

def create_program(db: Session, company_id: str, data) -> SafetyProgram:
    program = SafetyProgram(
        id=str(uuid.uuid4()),
        company_id=company_id,
        program_name=data.program_name,
        osha_standard=data.osha_standard,
        osha_standard_code=data.osha_standard_code,
        description=data.description,
        content=data.content,
        status=data.status,
        applicable_job_roles=_dump_json(data.applicable_job_roles),
        version=1,
    )
    db.add(program)
    db.commit()
    db.refresh(program)
    program.applicable_job_roles = _parse_json(program.applicable_job_roles)
    return program

def update_program(db: Session, company_id: str, program_id: str, data) -> SafetyProgram | None:
    program = db.query(SafetyProgram).filter(
        SafetyProgram.id == program_id,
        SafetyProgram.company_id == company_id,
    ).first()
    if not program:
        return None
    # If content changed, bump version
    content_changed = False
    for field in ["program_name", "osha_standard", "osha_standard_code", "description", "content", "status"]:
        val = getattr(data, field, None)
        if val is not None:
            if field == "content" and val != program.content:
                content_changed = True
            setattr(program, field, val)
    if data.applicable_job_roles is not None:
        program.applicable_job_roles = _dump_json(data.applicable_job_roles)
    if content_changed:
        program.version = (program.version or 0) + 1
    program.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(program)
    program.applicable_job_roles = _parse_json(program.applicable_job_roles)
    return program

def review_program(db: Session, company_id: str, program_id: str, reviewer_id: str) -> SafetyProgram | None:
    program = db.query(SafetyProgram).filter(
        SafetyProgram.id == program_id,
        SafetyProgram.company_id == company_id,
    ).first()
    if not program:
        return None
    now = datetime.now(timezone.utc)
    program.last_reviewed_at = now
    program.next_review_due_at = now + timedelta(days=365)
    program.reviewed_by = reviewer_id
    program.status = "active"
    program.updated_at = now
    db.commit()
    db.refresh(program)
    program.applicable_job_roles = _parse_json(program.applicable_job_roles)
    return program


# ============================================================
# Training Requirements
# ============================================================

def list_training_requirements(db: Session, company_id: str):
    reqs = db.query(SafetyTrainingRequirement).filter(
        SafetyTrainingRequirement.company_id == company_id,
    ).order_by(SafetyTrainingRequirement.training_topic).all()
    for r in reqs:
        r.applicable_roles = _parse_json(r.applicable_roles)
    return reqs

def create_training_requirement(db: Session, company_id: str, data) -> SafetyTrainingRequirement:
    req = SafetyTrainingRequirement(
        id=str(uuid.uuid4()),
        company_id=company_id,
        training_topic=data.training_topic,
        osha_standard_code=data.osha_standard_code,
        applicable_roles=_dump_json(data.applicable_roles),
        initial_training_required=data.initial_training_required,
        refresher_frequency_months=data.refresher_frequency_months,
        new_hire_deadline_days=data.new_hire_deadline_days,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    req.applicable_roles = _parse_json(req.applicable_roles)
    return req


# ============================================================
# Training Events
# ============================================================

def list_training_events(db: Session, company_id: str, training_type: str | None = None, limit: int = 50, offset: int = 0):
    q = db.query(SafetyTrainingEvent).filter(SafetyTrainingEvent.company_id == company_id)
    if training_type:
        q = q.filter(SafetyTrainingEvent.training_type == training_type)
    total = q.count()
    events = q.order_by(SafetyTrainingEvent.training_date.desc()).offset(offset).limit(limit).all()
    return events, total

def get_training_event(db: Session, company_id: str, event_id: str):
    return db.query(SafetyTrainingEvent).filter(
        SafetyTrainingEvent.id == event_id,
        SafetyTrainingEvent.company_id == company_id,
    ).first()

def create_training_event(db: Session, company_id: str, data, created_by: str) -> SafetyTrainingEvent:
    event = SafetyTrainingEvent(
        id=str(uuid.uuid4()),
        company_id=company_id,
        training_topic=data.training_topic,
        osha_standard_code=data.osha_standard_code,
        training_type=data.training_type,
        trainer_name=data.trainer_name,
        trainer_type=data.trainer_type,
        training_date=data.training_date,
        duration_minutes=data.duration_minutes,
        content_summary=data.content_summary,
        training_materials_url=data.training_materials_url,
        created_by=created_by,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def record_attendees(db: Session, company_id: str, event_id: str, employee_ids: list[str], completion_status: str = "attended") -> list[EmployeeTrainingRecord]:
    records = []
    for eid in employee_ids:
        rec = EmployeeTrainingRecord(
            id=str(uuid.uuid4()),
            company_id=company_id,
            employee_id=eid,
            training_event_id=event_id,
            completion_status=completion_status,
        )
        db.add(rec)
        records.append(rec)
    db.commit()
    for r in records:
        db.refresh(r)
    return records

def get_employee_training_history(db: Session, company_id: str, employee_id: str):
    """Return all training records for an employee with event details."""
    records = (
        db.query(EmployeeTrainingRecord, SafetyTrainingEvent)
        .join(SafetyTrainingEvent, EmployeeTrainingRecord.training_event_id == SafetyTrainingEvent.id)
        .filter(
            EmployeeTrainingRecord.company_id == company_id,
            EmployeeTrainingRecord.employee_id == employee_id,
        )
        .order_by(SafetyTrainingEvent.training_date.desc())
        .all()
    )
    result = []
    for rec, evt in records:
        rec.training_topic = evt.training_topic
        result.append(rec)
    return result

def get_training_gaps(db: Session, company_id: str):
    """Compare training requirements against records to find gaps."""
    reqs = db.query(SafetyTrainingRequirement).filter(
        SafetyTrainingRequirement.company_id == company_id,
    ).all()

    # Get all users for this company
    users = db.query(User).filter(User.company_id == company_id, User.is_active == True).all()

    gaps = []
    today = date.today()

    for req in reqs:
        roles = _parse_json(req.applicable_roles) or []
        for user in users:
            # Check if user's role matches (simplified — "All Employees" matches everyone)
            if "All Employees" not in roles:
                # In a real implementation, match against employee's job role
                continue

            # Find most recent training record for this topic
            latest = (
                db.query(EmployeeTrainingRecord)
                .join(SafetyTrainingEvent, EmployeeTrainingRecord.training_event_id == SafetyTrainingEvent.id)
                .filter(
                    EmployeeTrainingRecord.company_id == company_id,
                    EmployeeTrainingRecord.employee_id == user.id,
                    SafetyTrainingEvent.training_topic == req.training_topic,
                    EmployeeTrainingRecord.completion_status.in_(["attended", "passed"]),
                )
                .order_by(SafetyTrainingEvent.training_date.desc())
                .first()
            )

            if latest is None:
                gaps.append({
                    "employee_id": user.id,
                    "employee_name": f"{user.first_name} {user.last_name}",
                    "required_training": req.training_topic,
                    "osha_standard_code": req.osha_standard_code,
                    "status": "missing",
                    "expiry_date": None,
                    "days_overdue": None,
                })
            elif req.refresher_frequency_months and latest.expiry_date:
                if latest.expiry_date < today:
                    gaps.append({
                        "employee_id": user.id,
                        "employee_name": f"{user.first_name} {user.last_name}",
                        "required_training": req.training_topic,
                        "osha_standard_code": req.osha_standard_code,
                        "status": "expired",
                        "expiry_date": latest.expiry_date,
                        "days_overdue": (today - latest.expiry_date).days,
                    })
                elif latest.expiry_date <= today + timedelta(days=30):
                    gaps.append({
                        "employee_id": user.id,
                        "employee_name": f"{user.first_name} {user.last_name}",
                        "required_training": req.training_topic,
                        "osha_standard_code": req.osha_standard_code,
                        "status": "expiring_soon",
                        "expiry_date": latest.expiry_date,
                        "days_overdue": None,
                    })

    return gaps


# ============================================================
# Inspection Templates
# ============================================================

def list_inspection_templates(db: Session, company_id: str, active_only: bool = True):
    q = db.query(SafetyInspectionTemplate).filter(SafetyInspectionTemplate.company_id == company_id)
    if active_only:
        q = q.filter(SafetyInspectionTemplate.active == True)
    return q.order_by(SafetyInspectionTemplate.template_name).all()

def get_inspection_template(db: Session, company_id: str, template_id: str):
    return db.query(SafetyInspectionTemplate).filter(
        SafetyInspectionTemplate.id == template_id,
        SafetyInspectionTemplate.company_id == company_id,
    ).first()

def create_inspection_template(db: Session, company_id: str, data) -> SafetyInspectionTemplate:
    template = SafetyInspectionTemplate(
        id=str(uuid.uuid4()),
        company_id=company_id,
        template_name=data.template_name,
        inspection_type=data.inspection_type,
        equipment_type=data.equipment_type,
        frequency_days=data.frequency_days,
        description=data.description,
    )
    db.add(template)
    db.flush()

    if data.items:
        for item_data in data.items:
            item = SafetyInspectionItem(
                id=str(uuid.uuid4()),
                template_id=template.id,
                company_id=company_id,
                item_order=item_data.item_order,
                item_text=item_data.item_text,
                response_type=item_data.response_type,
                required=item_data.required,
                failure_action=item_data.failure_action,
                osha_reference=item_data.osha_reference,
            )
            db.add(item)

    db.commit()
    db.refresh(template)
    return template


# ============================================================
# Inspections
# ============================================================

def list_inspections(db: Session, company_id: str, status: str | None = None, template_id: str | None = None, limit: int = 50, offset: int = 0):
    q = db.query(SafetyInspection).filter(SafetyInspection.company_id == company_id)
    if status:
        q = q.filter(SafetyInspection.status == status)
    if template_id:
        q = q.filter(SafetyInspection.template_id == template_id)
    total = q.count()
    inspections = q.order_by(SafetyInspection.inspection_date.desc()).offset(offset).limit(limit).all()
    # attach template name and inspector name
    for insp in inspections:
        tmpl = db.query(SafetyInspectionTemplate.template_name).filter(SafetyInspectionTemplate.id == insp.template_id).first()
        insp.template_name = tmpl[0] if tmpl else None
        user = db.query(User.first_name, User.last_name).filter(User.id == insp.inspector_id).first()
        insp.inspector_name = f"{user[0]} {user[1]}" if user else None
    return inspections, total

def get_inspection(db: Session, company_id: str, inspection_id: str):
    insp = db.query(SafetyInspection).filter(
        SafetyInspection.id == inspection_id,
        SafetyInspection.company_id == company_id,
    ).first()
    if not insp:
        return None
    tmpl = db.query(SafetyInspectionTemplate.template_name).filter(SafetyInspectionTemplate.id == insp.template_id).first()
    insp.template_name = tmpl[0] if tmpl else None
    user = db.query(User.first_name, User.last_name).filter(User.id == insp.inspector_id).first()
    insp.inspector_name = f"{user[0]} {user[1]}" if user else None
    # attach result items with their item info
    for r in insp.results:
        item = db.query(SafetyInspectionItem).filter(SafetyInspectionItem.id == r.item_id).first()
        if item:
            r.item_text = item.item_text
            r.item_order = item.item_order
            r.response_type = item.response_type
            r.required = item.required
        r.photo_urls = _parse_json(r.photo_urls)
    insp.results.sort(key=lambda r: r.item_order or 0)
    return insp

def start_inspection(db: Session, company_id: str, data, inspector_id: str) -> SafetyInspection:
    """Create inspection from template and pre-populate result rows for each item."""
    inspection = SafetyInspection(
        id=str(uuid.uuid4()),
        company_id=company_id,
        template_id=data.template_id,
        equipment_id=data.equipment_id,
        equipment_identifier=data.equipment_identifier,
        inspector_id=inspector_id,
        inspection_date=data.inspection_date,
        status="in_progress",
        notes=data.notes,
    )
    db.add(inspection)
    db.flush()

    items = db.query(SafetyInspectionItem).filter(
        SafetyInspectionItem.template_id == data.template_id,
        SafetyInspectionItem.company_id == company_id,
    ).order_by(SafetyInspectionItem.item_order).all()

    for item in items:
        result = SafetyInspectionResult(
            id=str(uuid.uuid4()),
            inspection_id=inspection.id,
            item_id=item.id,
            company_id=company_id,
        )
        db.add(result)

    db.commit()
    db.refresh(inspection)
    return inspection

def update_inspection_result(db: Session, company_id: str, inspection_id: str, item_id: str, data) -> SafetyInspectionResult | None:
    result = db.query(SafetyInspectionResult).filter(
        SafetyInspectionResult.inspection_id == inspection_id,
        SafetyInspectionResult.item_id == item_id,
        SafetyInspectionResult.company_id == company_id,
    ).first()
    if not result:
        return None
    if data.result is not None:
        result.result = data.result
    if data.finding_notes is not None:
        result.finding_notes = data.finding_notes
    result.corrective_action_required = data.corrective_action_required
    if data.corrective_action_description is not None:
        result.corrective_action_description = data.corrective_action_description
    if data.corrective_action_due_date is not None:
        result.corrective_action_due_date = data.corrective_action_due_date
    if data.photo_urls is not None:
        result.photo_urls = _dump_json(data.photo_urls)
    db.commit()
    db.refresh(result)
    result.photo_urls = _parse_json(result.photo_urls)
    return result

def complete_inspection(db: Session, company_id: str, inspection_id: str) -> SafetyInspection | None:
    inspection = db.query(SafetyInspection).filter(
        SafetyInspection.id == inspection_id,
        SafetyInspection.company_id == company_id,
    ).first()
    if not inspection:
        return None

    # Determine overall result based on results
    results = db.query(SafetyInspectionResult).filter(
        SafetyInspectionResult.inspection_id == inspection_id,
    ).all()

    has_findings = any(r.corrective_action_required for r in results)
    has_failures = any(r.result and r.result.lower() in ("fail", "no") for r in results)

    if has_failures:
        inspection.overall_result = "fail"
        inspection.status = "completed_with_findings"
    elif has_findings:
        inspection.overall_result = "pass_with_findings"
        inspection.status = "completed_with_findings"
    else:
        inspection.overall_result = "pass"
        inspection.status = "completed"

    inspection.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inspection)
    return inspection

def complete_corrective_action(db: Session, company_id: str, inspection_id: str, result_id: str, completed_by: str) -> SafetyInspectionResult | None:
    result = db.query(SafetyInspectionResult).filter(
        SafetyInspectionResult.id == result_id,
        SafetyInspectionResult.inspection_id == inspection_id,
        SafetyInspectionResult.company_id == company_id,
    ).first()
    if not result:
        return None
    result.corrective_action_completed_at = datetime.now(timezone.utc)
    result.corrective_action_completed_by = completed_by
    db.commit()
    db.refresh(result)
    return result

def get_overdue_inspections(db: Session, company_id: str):
    """Find inspections overdue based on template frequency."""
    templates = db.query(SafetyInspectionTemplate).filter(
        SafetyInspectionTemplate.company_id == company_id,
        SafetyInspectionTemplate.active == True,
        SafetyInspectionTemplate.frequency_days.isnot(None),
    ).all()

    overdue = []
    today = date.today()

    for tmpl in templates:
        last = (
            db.query(func.max(SafetyInspection.inspection_date))
            .filter(
                SafetyInspection.template_id == tmpl.id,
                SafetyInspection.company_id == company_id,
                SafetyInspection.status.in_(["completed", "completed_with_findings"]),
            )
            .scalar()
        )

        if last is None:
            overdue.append({
                "template_id": tmpl.id,
                "template_name": tmpl.template_name,
                "equipment_type": tmpl.equipment_type,
                "frequency_days": tmpl.frequency_days,
                "last_inspection_date": None,
                "days_overdue": tmpl.frequency_days,  # never done
            })
        else:
            next_due = last + timedelta(days=tmpl.frequency_days)
            if next_due < today:
                overdue.append({
                    "template_id": tmpl.id,
                    "template_name": tmpl.template_name,
                    "equipment_type": tmpl.equipment_type,
                    "frequency_days": tmpl.frequency_days,
                    "last_inspection_date": last,
                    "days_overdue": (today - next_due).days,
                })

    return sorted(overdue, key=lambda x: x["days_overdue"], reverse=True)


# ============================================================
# Chemicals / SDS
# ============================================================

def list_chemicals(db: Session, company_id: str, active_only: bool = True, hazard_class: str | None = None):
    q = db.query(SafetyChemical).filter(SafetyChemical.company_id == company_id)
    if active_only:
        q = q.filter(SafetyChemical.active == True)
    if hazard_class:
        q = q.filter(SafetyChemical.hazard_class.contains(hazard_class))
    chemicals = q.order_by(SafetyChemical.chemical_name).all()
    for c in chemicals:
        c.hazard_class = _parse_json(c.hazard_class)
        c.ppe_required = _parse_json(c.ppe_required)
    return chemicals

def get_chemical(db: Session, company_id: str, chemical_id: str):
    c = db.query(SafetyChemical).filter(
        SafetyChemical.id == chemical_id,
        SafetyChemical.company_id == company_id,
    ).first()
    if c:
        c.hazard_class = _parse_json(c.hazard_class)
        c.ppe_required = _parse_json(c.ppe_required)
    return c

def create_chemical(db: Session, company_id: str, data) -> SafetyChemical:
    sds_review_due = None
    if data.sds_date:
        sds_review_due = date(data.sds_date.year + 3, data.sds_date.month, data.sds_date.day)

    chemical = SafetyChemical(
        id=str(uuid.uuid4()),
        company_id=company_id,
        chemical_name=data.chemical_name,
        manufacturer=data.manufacturer,
        product_number=data.product_number,
        cas_number=data.cas_number,
        location=data.location,
        quantity_on_hand=data.quantity_on_hand,
        unit_of_measure=data.unit_of_measure,
        hazard_class=_dump_json(data.hazard_class),
        ppe_required=_dump_json(data.ppe_required),
        sds_url=data.sds_url,
        sds_date=data.sds_date,
        sds_review_due_at=sds_review_due,
    )
    db.add(chemical)
    db.commit()
    db.refresh(chemical)
    chemical.hazard_class = _parse_json(chemical.hazard_class)
    chemical.ppe_required = _parse_json(chemical.ppe_required)
    return chemical

def update_chemical(db: Session, company_id: str, chemical_id: str, data) -> SafetyChemical | None:
    chemical = db.query(SafetyChemical).filter(
        SafetyChemical.id == chemical_id,
        SafetyChemical.company_id == company_id,
    ).first()
    if not chemical:
        return None
    for field in ["chemical_name", "manufacturer", "product_number", "cas_number", "location", "quantity_on_hand", "unit_of_measure", "sds_url", "sds_date", "active"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(chemical, field, val)
    if data.hazard_class is not None:
        chemical.hazard_class = _dump_json(data.hazard_class)
    if data.ppe_required is not None:
        chemical.ppe_required = _dump_json(data.ppe_required)
    if data.sds_date:
        chemical.sds_review_due_at = date(data.sds_date.year + 3, data.sds_date.month, data.sds_date.day)
    chemical.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(chemical)
    chemical.hazard_class = _parse_json(chemical.hazard_class)
    chemical.ppe_required = _parse_json(chemical.ppe_required)
    return chemical

def get_outdated_sds(db: Session, company_id: str):
    """Chemicals with SDS over 3 years old."""
    today = date.today()
    return db.query(SafetyChemical).filter(
        SafetyChemical.company_id == company_id,
        SafetyChemical.active == True,
        SafetyChemical.sds_review_due_at < today,
    ).order_by(SafetyChemical.sds_review_due_at).all()


# ============================================================
# Incidents
# ============================================================

def _determine_osha_recordable(medical_treatment: str, days_away: int, days_restricted: int) -> bool:
    """OSHA recordability determination based on treatment type."""
    if medical_treatment in ("medical_treatment", "hospitalization", "fatality"):
        return True
    if days_away > 0 or days_restricted > 0:
        return True
    return False

def _next_300_case_number(db: Session, company_id: str, year: int) -> int:
    """Get next sequential OSHA 300 case number for the year."""
    max_num = db.query(func.max(SafetyIncident.osha_300_case_number)).filter(
        SafetyIncident.company_id == company_id,
        SafetyIncident.osha_recordable == True,
        func.extract("year", SafetyIncident.incident_date) == year,
    ).scalar()
    return (max_num or 0) + 1

def create_incident(db: Session, company_id: str, data, reported_by: str) -> SafetyIncident:
    osha_recordable = _determine_osha_recordable(
        data.medical_treatment,
        0,  # days_away not known at initial report
        0,
    )
    case_number = None
    if osha_recordable:
        case_number = _next_300_case_number(db, company_id, data.incident_date.year)

    incident = SafetyIncident(
        id=str(uuid.uuid4()),
        company_id=company_id,
        incident_type=data.incident_type,
        incident_date=data.incident_date,
        incident_time=data.incident_time,
        location=data.location,
        involved_employee_id=data.involved_employee_id,
        witnesses=data.witnesses,
        description=data.description,
        immediate_cause=data.immediate_cause,
        body_part_affected=data.body_part_affected,
        injury_type=data.injury_type,
        medical_treatment=data.medical_treatment,
        osha_recordable=osha_recordable,
        osha_300_case_number=case_number,
        reported_by=reported_by,
        status="reported",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident

def list_incidents(db: Session, company_id: str, incident_type: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0):
    q = db.query(SafetyIncident).filter(SafetyIncident.company_id == company_id)
    if incident_type:
        q = q.filter(SafetyIncident.incident_type == incident_type)
    if status:
        q = q.filter(SafetyIncident.status == status)
    total = q.count()
    incidents = q.order_by(SafetyIncident.incident_date.desc()).offset(offset).limit(limit).all()
    # Attach employee name
    for inc in incidents:
        if inc.involved_employee_id:
            user = db.query(User.first_name, User.last_name).filter(User.id == inc.involved_employee_id).first()
            inc.involved_employee_name = f"{user[0]} {user[1]}" if user else None
    return incidents, total

def get_incident(db: Session, company_id: str, incident_id: str):
    inc = db.query(SafetyIncident).filter(
        SafetyIncident.id == incident_id,
        SafetyIncident.company_id == company_id,
    ).first()
    if inc and inc.involved_employee_id:
        user = db.query(User.first_name, User.last_name).filter(User.id == inc.involved_employee_id).first()
        inc.involved_employee_name = f"{user[0]} {user[1]}" if user else None
    return inc

def update_incident(db: Session, company_id: str, incident_id: str, data) -> SafetyIncident | None:
    inc = db.query(SafetyIncident).filter(
        SafetyIncident.id == incident_id,
        SafetyIncident.company_id == company_id,
    ).first()
    if not inc:
        return None
    for field in ["incident_type", "location", "involved_employee_id", "witnesses", "description", "immediate_cause", "root_cause", "body_part_affected", "injury_type", "medical_treatment", "days_away_from_work", "days_on_restricted_duty", "investigated_by", "corrective_actions"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(inc, field, val)
    # Re-evaluate OSHA recordability
    inc.osha_recordable = _determine_osha_recordable(
        inc.medical_treatment, inc.days_away_from_work, inc.days_on_restricted_duty
    )
    if inc.osha_recordable and not inc.osha_300_case_number:
        inc.osha_300_case_number = _next_300_case_number(db, company_id, inc.incident_date.year)
    inc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inc)
    return inc

def close_incident(db: Session, company_id: str, incident_id: str) -> SafetyIncident | None:
    inc = db.query(SafetyIncident).filter(
        SafetyIncident.id == incident_id,
        SafetyIncident.company_id == company_id,
    ).first()
    if not inc:
        return None
    inc.status = "closed"
    inc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inc)
    return inc

def get_osha_300_log(db: Session, company_id: str, year: int):
    """Generate OSHA 300 log entries for the given year."""
    incidents = db.query(SafetyIncident).filter(
        SafetyIncident.company_id == company_id,
        SafetyIncident.osha_recordable == True,
        func.extract("year", SafetyIncident.incident_date) == year,
    ).order_by(SafetyIncident.osha_300_case_number).all()

    entries = []
    for inc in incidents:
        emp_name = ""
        job_title = ""
        if inc.involved_employee_id:
            user = db.query(User).filter(User.id == inc.involved_employee_id).first()
            if user:
                emp_name = f"{user.first_name} {user.last_name}"
        entries.append({
            "case_number": inc.osha_300_case_number,
            "employee_name": emp_name,
            "job_title": job_title,
            "incident_date": inc.incident_date,
            "location": inc.location,
            "description": inc.description,
            "injury_type": inc.injury_type,
            "days_away_from_work": inc.days_away_from_work,
            "days_on_restricted_duty": inc.days_on_restricted_duty,
            "medical_treatment": inc.medical_treatment,
            "incident_type": inc.incident_type,
        })
    return entries

def get_osha_300a_summary(db: Session, company_id: str, year: int):
    """Generate OSHA 300A annual summary."""
    incidents = db.query(SafetyIncident).filter(
        SafetyIncident.company_id == company_id,
        SafetyIncident.osha_recordable == True,
        func.extract("year", SafetyIncident.incident_date) == year,
    ).all()

    return {
        "year": year,
        "total_cases": len(incidents),
        "total_deaths": sum(1 for i in incidents if i.medical_treatment == "fatality"),
        "total_days_away": sum(i.days_away_from_work for i in incidents),
        "total_days_restricted": sum(i.days_on_restricted_duty for i in incidents),
        "total_other_recordable": sum(1 for i in incidents if i.medical_treatment == "medical_treatment"),
        "injury_count": sum(1 for i in incidents if i.incident_type == "injury"),
        "skin_disorder_count": 0,
        "respiratory_count": 0,
        "poisoning_count": 0,
        "hearing_loss_count": 0,
        "other_illness_count": sum(1 for i in incidents if i.incident_type == "illness"),
    }


# ============================================================
# LOTO Procedures
# ============================================================

def list_loto(db: Session, company_id: str, active_only: bool = True):
    q = db.query(SafetyLotoProcedure).filter(SafetyLotoProcedure.company_id == company_id)
    if active_only:
        q = q.filter(SafetyLotoProcedure.active == True)
    procedures = q.order_by(SafetyLotoProcedure.machine_name).all()
    for p in procedures:
        p.energy_sources = _parse_json(p.energy_sources) or []
        p.ppe_required = _parse_json(p.ppe_required)
        p.steps = _parse_json(p.steps) or []
        p.authorized_employees = _parse_json(p.authorized_employees)
        p.affected_employees = _parse_json(p.affected_employees)
    return procedures

def get_loto(db: Session, company_id: str, loto_id: str):
    p = db.query(SafetyLotoProcedure).filter(
        SafetyLotoProcedure.id == loto_id,
        SafetyLotoProcedure.company_id == company_id,
    ).first()
    if p:
        p.energy_sources = _parse_json(p.energy_sources) or []
        p.ppe_required = _parse_json(p.ppe_required)
        p.steps = _parse_json(p.steps) or []
        p.authorized_employees = _parse_json(p.authorized_employees)
        p.affected_employees = _parse_json(p.affected_employees)
    return p

def create_loto(db: Session, company_id: str, data) -> SafetyLotoProcedure:
    proc = SafetyLotoProcedure(
        id=str(uuid.uuid4()),
        company_id=company_id,
        machine_name=data.machine_name,
        machine_location=data.machine_location,
        machine_id=data.machine_id,
        procedure_number=data.procedure_number,
        energy_sources=_dump_json([s.model_dump() for s in data.energy_sources]),
        ppe_required=_dump_json(data.ppe_required),
        steps=_dump_json([s.model_dump() for s in data.steps]),
        estimated_time_minutes=data.estimated_time_minutes,
        authorized_employees=_dump_json(data.authorized_employees),
        affected_employees=_dump_json(data.affected_employees),
    )
    db.add(proc)
    db.commit()
    db.refresh(proc)
    proc.energy_sources = _parse_json(proc.energy_sources) or []
    proc.steps = _parse_json(proc.steps) or []
    proc.ppe_required = _parse_json(proc.ppe_required)
    proc.authorized_employees = _parse_json(proc.authorized_employees)
    proc.affected_employees = _parse_json(proc.affected_employees)
    return proc

def update_loto(db: Session, company_id: str, loto_id: str, data) -> SafetyLotoProcedure | None:
    proc = db.query(SafetyLotoProcedure).filter(
        SafetyLotoProcedure.id == loto_id,
        SafetyLotoProcedure.company_id == company_id,
    ).first()
    if not proc:
        return None
    for field in ["machine_name", "machine_location", "machine_id", "procedure_number", "estimated_time_minutes", "active"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(proc, field, val)
    if data.energy_sources is not None:
        proc.energy_sources = _dump_json([s.model_dump() for s in data.energy_sources])
    if data.ppe_required is not None:
        proc.ppe_required = _dump_json(data.ppe_required)
    if data.steps is not None:
        proc.steps = _dump_json([s.model_dump() for s in data.steps])
    if data.authorized_employees is not None:
        proc.authorized_employees = _dump_json(data.authorized_employees)
    if data.affected_employees is not None:
        proc.affected_employees = _dump_json(data.affected_employees)
    proc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(proc)
    proc.energy_sources = _parse_json(proc.energy_sources) or []
    proc.steps = _parse_json(proc.steps) or []
    proc.ppe_required = _parse_json(proc.ppe_required)
    proc.authorized_employees = _parse_json(proc.authorized_employees)
    proc.affected_employees = _parse_json(proc.affected_employees)
    return proc

def review_loto(db: Session, company_id: str, loto_id: str) -> SafetyLotoProcedure | None:
    proc = db.query(SafetyLotoProcedure).filter(
        SafetyLotoProcedure.id == loto_id,
        SafetyLotoProcedure.company_id == company_id,
    ).first()
    if not proc:
        return None
    now = datetime.now(timezone.utc)
    proc.last_reviewed_at = now
    proc.next_review_due_at = now + timedelta(days=365)
    proc.updated_at = now
    db.commit()
    db.refresh(proc)
    proc.energy_sources = _parse_json(proc.energy_sources) or []
    proc.steps = _parse_json(proc.steps) or []
    proc.ppe_required = _parse_json(proc.ppe_required)
    proc.authorized_employees = _parse_json(proc.authorized_employees)
    proc.affected_employees = _parse_json(proc.affected_employees)
    return proc


# ============================================================
# Alerts
# ============================================================

def list_alerts(db: Session, company_id: str, active_only: bool = True):
    q = db.query(SafetyAlert).filter(SafetyAlert.company_id == company_id)
    if active_only:
        q = q.filter(SafetyAlert.resolved_at.is_(None))
    return q.order_by(
        SafetyAlert.severity.desc(),
        SafetyAlert.due_date,
    ).all()

def acknowledge_alert(db: Session, company_id: str, alert_id: str, user_id: str) -> SafetyAlert | None:
    alert = db.query(SafetyAlert).filter(
        SafetyAlert.id == alert_id,
        SafetyAlert.company_id == company_id,
    ).first()
    if not alert:
        return None
    alert.acknowledged_by = user_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


# ============================================================
# Compliance Score
# ============================================================

def calculate_compliance_score(db: Session, company_id: str) -> dict:
    """Calculate real-time safety compliance score across all categories."""
    today = date.today()
    categories = []

    # 1. Written programs (20%)
    programs = db.query(SafetyProgram).filter(SafetyProgram.company_id == company_id, SafetyProgram.status == "active").all()
    programs_total = max(len(programs), 1)
    programs_current = sum(1 for p in programs if p.next_review_due_at and p.next_review_due_at.date() >= today)
    program_gaps = [f"Program '{p.program_name}' review overdue" for p in programs if p.next_review_due_at and p.next_review_due_at.date() < today]
    categories.append({
        "category": "Written Safety Programs",
        "weight": 0.20,
        "score": (programs_current / programs_total) * 100 if programs_total else 100,
        "max_score": 100,
        "items_total": programs_total,
        "items_compliant": programs_current,
        "gaps": program_gaps,
    })

    # 2. Employee training (25%)
    gaps = get_training_gaps(db, company_id)
    total_requirements = max(len(gaps) + 1, 1)  # simplified
    categories.append({
        "category": "Employee Training",
        "weight": 0.25,
        "score": max(0, 100 - (len(gaps) * 10)),
        "max_score": 100,
        "items_total": total_requirements,
        "items_compliant": total_requirements - len(gaps),
        "gaps": [f"{g['employee_name']}: {g['required_training']} ({g['status']})" for g in gaps[:10]],
    })

    # 3. Inspections current (20%)
    overdue = get_overdue_inspections(db, company_id)
    templates = db.query(SafetyInspectionTemplate).filter(
        SafetyInspectionTemplate.company_id == company_id,
        SafetyInspectionTemplate.active == True,
        SafetyInspectionTemplate.frequency_days.isnot(None),
    ).count()
    templates_total = max(templates, 1)
    categories.append({
        "category": "Safety Inspections",
        "weight": 0.20,
        "score": ((templates_total - len(overdue)) / templates_total) * 100 if templates_total else 100,
        "max_score": 100,
        "items_total": templates_total,
        "items_compliant": templates_total - len(overdue),
        "gaps": [f"{o['template_name']} overdue by {o['days_overdue']} days" for o in overdue[:10]],
    })

    # 4. SDS library (15%)
    total_chemicals = db.query(SafetyChemical).filter(SafetyChemical.company_id == company_id, SafetyChemical.active == True).count()
    outdated = db.query(SafetyChemical).filter(
        SafetyChemical.company_id == company_id,
        SafetyChemical.active == True,
        SafetyChemical.sds_review_due_at < today,
    ).count()
    total_chem = max(total_chemicals, 1)
    categories.append({
        "category": "SDS Library",
        "weight": 0.15,
        "score": ((total_chem - outdated) / total_chem) * 100 if total_chem else 100,
        "max_score": 100,
        "items_total": total_chem,
        "items_compliant": total_chem - outdated,
        "gaps": [],
    })

    # 5. Incident investigations (10%)
    open_incidents = db.query(SafetyIncident).filter(
        SafetyIncident.company_id == company_id,
        SafetyIncident.status != "closed",
        SafetyIncident.incident_date < today - timedelta(days=30),
    ).count()
    total_incidents = db.query(SafetyIncident).filter(SafetyIncident.company_id == company_id).count()
    total_inc = max(total_incidents, 1)
    categories.append({
        "category": "Incident Investigations",
        "weight": 0.10,
        "score": ((total_inc - open_incidents) / total_inc) * 100 if total_inc else 100,
        "max_score": 100,
        "items_total": total_inc,
        "items_compliant": total_inc - open_incidents,
        "gaps": [],
    })

    # 6. LOTO procedures (10%)
    loto_procs = db.query(SafetyLotoProcedure).filter(
        SafetyLotoProcedure.company_id == company_id,
        SafetyLotoProcedure.active == True,
    ).all()
    loto_total = max(len(loto_procs), 1)
    loto_current = sum(1 for p in loto_procs if p.next_review_due_at and p.next_review_due_at >= datetime.now(timezone.utc))
    categories.append({
        "category": "LOTO Procedures",
        "weight": 0.10,
        "score": (loto_current / loto_total) * 100 if loto_total else 100,
        "max_score": 100,
        "items_total": loto_total,
        "items_compliant": loto_current,
        "gaps": [],
    })

    # Calculate weighted overall score
    overall = sum(c["score"] * c["weight"] for c in categories)

    return {
        "overall_score": round(overall, 1),
        "categories": categories,
        "generated_at": datetime.now(timezone.utc),
    }
