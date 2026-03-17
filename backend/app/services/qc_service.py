import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
import sqlalchemy as sa
from sqlalchemy import case, func, extract
from sqlalchemy.orm import Session, joinedload

from app.models.qc import (
    QCDefectType,
    QCDisposition,
    QCInspection,
    QCInspectionStep,
    QCInspectionTemplate,
    QCMedia,
    QCReworkRecord,
    QCStepResult,
)
from app.models.inventory_item import InventoryItem
from app.schemas.qc import (
    DefectTypeCreate,
    DispositionCreate,
    InspectionCreate,
    MediaCreate,
    ReworkCreate,
    StepCreate,
    StepResultUpdate,
    StepUpdate,
    TemplateCreate,
)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def list_templates(
    db: Session,
    company_id: str,
    product_category: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Return paginated list of active inspection templates."""
    query = db.query(QCInspectionTemplate).filter(
        QCInspectionTemplate.company_id == company_id,
        QCInspectionTemplate.is_active.is_(True),
    )
    if product_category:
        query = query.filter(
            QCInspectionTemplate.product_category == product_category
        )

    total = query.count()
    templates = (
        query.options(joinedload(QCInspectionTemplate.steps))
        .order_by(QCInspectionTemplate.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": templates,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def create_template(
    db: Session,
    company_id: str,
    data: TemplateCreate,
) -> QCInspectionTemplate:
    """Create a new inspection template, optionally with steps."""
    now = datetime.now(timezone.utc)
    template = QCInspectionTemplate(
        id=str(uuid.uuid4()),
        company_id=company_id,
        product_category=data.product_category,
        template_name=data.template_name,
        description=data.description,
        wilbert_warranty_compliant=data.wilbert_warranty_compliant,
        created_at=now,
        updated_at=now,
    )
    db.add(template)
    db.flush()

    if data.steps:
        for step_data in data.steps:
            step = QCInspectionStep(
                id=str(uuid.uuid4()),
                template_id=template.id,
                company_id=company_id,
                step_name=step_data.step_name,
                step_order=step_data.step_order,
                inspection_type=step_data.inspection_type,
                description=step_data.description,
                pass_criteria=step_data.pass_criteria,
                photo_required=step_data.photo_required,
                required=step_data.required,
                created_at=now,
            )
            db.add(step)

    db.commit()
    db.refresh(template)
    return _get_template_with_steps(db, template.id, company_id)


def get_template(
    db: Session, template_id: str, company_id: str
) -> QCInspectionTemplate:
    """Get a single template with steps."""
    return _get_template_with_steps(db, template_id, company_id)


def _get_template_with_steps(
    db: Session, template_id: str, company_id: str
) -> QCInspectionTemplate:
    template = (
        db.query(QCInspectionTemplate)
        .options(joinedload(QCInspectionTemplate.steps))
        .filter(
            QCInspectionTemplate.id == template_id,
            QCInspectionTemplate.company_id == company_id,
            QCInspectionTemplate.is_active.is_(True),
        )
        .first()
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection template not found",
        )
    return template


def add_step(
    db: Session,
    template_id: str,
    company_id: str,
    data: StepCreate,
) -> QCInspectionStep:
    """Add a step to an existing template."""
    _get_template_with_steps(db, template_id, company_id)

    step = QCInspectionStep(
        id=str(uuid.uuid4()),
        template_id=template_id,
        company_id=company_id,
        step_name=data.step_name,
        step_order=data.step_order,
        inspection_type=data.inspection_type,
        description=data.description,
        pass_criteria=data.pass_criteria,
        photo_required=data.photo_required,
        required=data.required,
        created_at=datetime.now(timezone.utc),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def update_step(
    db: Session,
    step_id: str,
    template_id: str,
    company_id: str,
    data: StepUpdate,
) -> QCInspectionStep:
    """Update an existing inspection step."""
    _get_template_with_steps(db, template_id, company_id)

    step = (
        db.query(QCInspectionStep)
        .filter(
            QCInspectionStep.id == step_id,
            QCInspectionStep.template_id == template_id,
        )
        .first()
    )
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection step not found",
        )

    if data.step_name is not None:
        step.step_name = data.step_name
    if data.step_order is not None:
        step.step_order = data.step_order
    if data.inspection_type is not None:
        step.inspection_type = data.inspection_type
    if data.description is not None:
        step.description = data.description
    if data.pass_criteria is not None:
        step.pass_criteria = data.pass_criteria
    if data.photo_required is not None:
        step.photo_required = data.photo_required
    if data.required is not None:
        step.required = data.required

    db.commit()
    db.refresh(step)
    return step


def delete_step(
    db: Session,
    step_id: str,
    template_id: str,
    company_id: str,
) -> None:
    """Hard-delete an inspection step."""
    _get_template_with_steps(db, template_id, company_id)

    step = (
        db.query(QCInspectionStep)
        .filter(
            QCInspectionStep.id == step_id,
            QCInspectionStep.template_id == template_id,
        )
        .first()
    )
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection step not found",
        )
    db.delete(step)
    db.commit()


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------


def create_inspection(
    db: Session,
    company_id: str,
    data: InspectionCreate,
    inspector_id: str,
) -> QCInspection:
    """Create a new inspection and pre-populate step results as pending."""
    template = _get_template_with_steps(db, data.template_id, company_id)

    now = datetime.now(timezone.utc)
    inspection = QCInspection(
        id=str(uuid.uuid4()),
        company_id=company_id,
        inventory_item_id=data.inventory_item_id,
        template_id=template.id,
        product_category=template.product_category,
        product_type=data.product_type,
        inspector_id=inspector_id,
        status="pending",
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(inspection)
    db.flush()

    # Pre-populate step results
    for step in template.steps:
        step_result = QCStepResult(
            id=str(uuid.uuid4()),
            inspection_id=inspection.id,
            step_id=step.id,
            company_id=company_id,
            result="pending",
            created_at=now,
        )
        db.add(step_result)

    db.commit()
    return _get_inspection_full(db, inspection.id, company_id)


def get_inspection(
    db: Session, inspection_id: str, company_id: str
) -> QCInspection:
    """Get a single inspection with all related data."""
    return _get_inspection_full(db, inspection_id, company_id)


def _get_inspection_full(
    db: Session, inspection_id: str, company_id: str
) -> QCInspection:
    inspection = (
        db.query(QCInspection)
        .options(
            joinedload(QCInspection.inspector),
            joinedload(QCInspection.step_results)
            .joinedload(QCStepResult.step),
            joinedload(QCInspection.step_results)
            .joinedload(QCStepResult.defect_type),
            joinedload(QCInspection.disposition)
            .joinedload(QCDisposition.decider),
            joinedload(QCInspection.media),
        )
        .filter(
            QCInspection.id == inspection_id,
            QCInspection.company_id == company_id,
        )
        .first()
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )
    return inspection


def list_inspections(
    db: Session,
    company_id: str,
    inspection_status: str | None = None,
    product_category: str | None = None,
    search: str | None = None,
    inspector_id: str | None = None,
    inventory_item_id: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Return paginated list of inspections with optional filters."""
    query = db.query(QCInspection).filter(
        QCInspection.company_id == company_id,
    )
    if inspection_status:
        query = query.filter(QCInspection.status == inspection_status)
    if product_category:
        query = query.filter(
            QCInspection.product_category == product_category
        )
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            sa.or_(
                QCInspection.product_category.ilike(search_pattern),
                QCInspection.product_type.ilike(search_pattern),
                QCInspection.certificate_number.ilike(search_pattern),
            )
        )
    if inspector_id:
        query = query.filter(QCInspection.inspector_id == inspector_id)
    if inventory_item_id:
        query = query.filter(
            QCInspection.inventory_item_id == inventory_item_id
        )

    total = query.count()
    inspections = (
        query.options(
            joinedload(QCInspection.inspector),
            joinedload(QCInspection.template),
            joinedload(QCInspection.step_results),
        )
        .order_by(QCInspection.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .unique()
        .all()
    )
    return {
        "items": inspections,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def update_step_result(
    db: Session,
    inspection_id: str,
    step_id: str,
    company_id: str,
    data: StepResultUpdate,
) -> QCStepResult:
    """Update the result for a specific step in an inspection."""
    inspection = (
        db.query(QCInspection)
        .filter(
            QCInspection.id == inspection_id,
            QCInspection.company_id == company_id,
        )
        .first()
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    if inspection.status in ("passed", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update step results on a completed inspection",
        )

    step_result = (
        db.query(QCStepResult)
        .filter(
            QCStepResult.inspection_id == inspection_id,
            QCStepResult.step_id == step_id,
        )
        .first()
    )
    if not step_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step result not found",
        )

    step_result.result = data.result
    step_result.notes = data.notes
    step_result.defect_type_id = data.defect_type_id
    step_result.defect_severity = data.defect_severity

    # Auto-transition inspection to in_progress
    if inspection.status == "pending":
        inspection.status = "in_progress"
        inspection.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(step_result)
    return step_result


def _calculate_inspection_status(
    db: Session, inspection_id: str
) -> str:
    """Calculate the inspection status based on step results.

    Rules:
    - Any step fail with critical severity -> failed
    - Any step fail with major severity -> failed
    - Only minor fails -> conditional_pass
    - All pass or na -> passed
    """
    results = (
        db.query(QCStepResult)
        .filter(QCStepResult.inspection_id == inspection_id)
        .all()
    )

    has_minor_fail = False

    for r in results:
        if r.result == "fail":
            if r.defect_severity == "critical":
                return "failed"
            if r.defect_severity == "major":
                return "failed"
            # minor or unspecified
            has_minor_fail = True

    if has_minor_fail:
        return "conditional_pass"

    return "passed"


def complete_inspection(
    db: Session,
    inspection_id: str,
    company_id: str,
    overall_notes: str | None = None,
) -> QCInspection:
    """Finalize an inspection: calculate status, generate certificate, update inventory."""
    inspection = (
        db.query(QCInspection)
        .filter(
            QCInspection.id == inspection_id,
            QCInspection.company_id == company_id,
        )
        .first()
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    if inspection.status in ("passed", "failed", "conditional_pass"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspection is already completed",
        )

    # Check all required steps have been answered
    pending_required = (
        db.query(QCStepResult)
        .join(QCInspectionStep, QCStepResult.step_id == QCInspectionStep.id)
        .filter(
            QCStepResult.inspection_id == inspection_id,
            QCStepResult.result == "pending",
            QCInspectionStep.required.is_(True),
        )
        .count()
    )
    if pending_required > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{pending_required} required step(s) still pending",
        )

    now = datetime.now(timezone.utc)
    calculated_status = _calculate_inspection_status(db, inspection_id)
    inspection.status = calculated_status
    inspection.completed_at = now
    inspection.updated_at = now

    if overall_notes is not None:
        inspection.overall_notes = overall_notes

    # Generate certificate number for passed or conditional_pass
    if calculated_status in ("passed", "conditional_pass"):
        inspection.certificate_number = _generate_certificate_number(
            db, company_id
        )

    # Update inventory item qc_status if linked
    if inspection.inventory_item_id:
        inv_item = (
            db.query(InventoryItem)
            .filter(InventoryItem.id == inspection.inventory_item_id)
            .first()
        )
        if inv_item:
            inv_item.qc_status = calculated_status

    db.commit()
    return _get_inspection_full(db, inspection_id, company_id)


def _generate_certificate_number(db: Session, company_id: str) -> str:
    """Generate QC-YYYY-#### certificate number."""
    year = datetime.now(timezone.utc).year
    prefix = f"QC-{year}-"

    max_cert = (
        db.query(func.max(QCInspection.certificate_number))
        .filter(
            QCInspection.company_id == company_id,
            QCInspection.certificate_number.like(f"{prefix}%"),
        )
        .scalar()
    )
    if max_cert:
        seq = int(max_cert.split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


# ---------------------------------------------------------------------------
# Disposition
# ---------------------------------------------------------------------------


def create_disposition(
    db: Session,
    inspection_id: str,
    company_id: str,
    data: DispositionCreate,
    actor_id: str,
) -> QCDisposition:
    """Record a disposition decision for a failed/conditional inspection."""
    inspection = (
        db.query(QCInspection)
        .filter(
            QCInspection.id == inspection_id,
            QCInspection.company_id == company_id,
        )
        .first()
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    existing = (
        db.query(QCDisposition)
        .filter(QCDisposition.inspection_id == inspection_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Disposition already recorded for this inspection",
        )

    now = datetime.now(timezone.utc)
    disposition = QCDisposition(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        company_id=company_id,
        decided_by=actor_id,
        disposition=data.disposition,
        disposition_notes=data.disposition_notes,
        rework_instructions=data.rework_instructions,
        decided_at=now,
    )
    db.add(disposition)

    # If disposition overrides to conditional_pass, update inspection status
    if data.disposition == "conditional_pass":
        inspection.status = "conditional_pass"
        inspection.updated_at = now
        if not inspection.certificate_number:
            inspection.certificate_number = _generate_certificate_number(
                db, company_id
            )

    # Update status to rework_required if disposition is rework
    if data.disposition == "rework":
        inspection.status = "rework_required"
        inspection.updated_at = now

    db.commit()
    db.refresh(disposition)
    return disposition


def get_disposition(
    db: Session, inspection_id: str, company_id: str
) -> QCDisposition:
    """Get the disposition for an inspection."""
    disposition = (
        db.query(QCDisposition)
        .options(joinedload(QCDisposition.decider))
        .filter(
            QCDisposition.inspection_id == inspection_id,
            QCDisposition.company_id == company_id,
        )
        .first()
    )
    if not disposition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disposition not found",
        )
    return disposition


# ---------------------------------------------------------------------------
# Rework
# ---------------------------------------------------------------------------


def create_rework_record(
    db: Session,
    inspection_id: str,
    company_id: str,
    data: ReworkCreate,
) -> QCReworkRecord:
    """Create a rework record for a failed inspection."""
    inspection = (
        db.query(QCInspection)
        .filter(
            QCInspection.id == inspection_id,
            QCInspection.company_id == company_id,
        )
        .first()
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    rework = QCReworkRecord(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        original_inspection_id=inspection_id,
        company_id=company_id,
        rework_description=data.rework_description,
    )
    db.add(rework)

    # Set inspection status to rework_required
    inspection.status = "rework_required"
    inspection.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(rework)
    return rework


def complete_rework(
    db: Session,
    rework_id: str,
    company_id: str,
    actor_id: str,
    notes: str | None = None,
) -> QCReworkRecord:
    """Mark rework as complete and create a new re-inspection."""
    rework = (
        db.query(QCReworkRecord)
        .filter(
            QCReworkRecord.id == rework_id,
            QCReworkRecord.company_id == company_id,
        )
        .first()
    )
    if not rework:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rework record not found",
        )

    if rework.rework_completed_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rework already completed",
        )

    original_inspection = (
        db.query(QCInspection)
        .filter(QCInspection.id == rework.original_inspection_id)
        .first()
    )
    if not original_inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original inspection not found",
        )

    now = datetime.now(timezone.utc)
    rework.rework_completed_by = actor_id
    rework.rework_completed_at = now

    # Create a new inspection for re-inspection
    re_inspection_data = InspectionCreate(
        inventory_item_id=original_inspection.inventory_item_id,
        template_id=original_inspection.template_id,
        product_type=original_inspection.product_type,
    )
    re_inspection = create_inspection(
        db, company_id, re_inspection_data, actor_id
    )

    rework.re_inspection_id = re_inspection.id
    db.commit()
    db.refresh(rework)
    return rework


# ---------------------------------------------------------------------------
# Defect Types
# ---------------------------------------------------------------------------


def list_defect_types(
    db: Session,
    company_id: str,
    product_category: str | None = None,
) -> list[QCDefectType]:
    """List active defect types, optionally filtered by product category."""
    query = db.query(QCDefectType).filter(
        QCDefectType.company_id == company_id,
        QCDefectType.is_active.is_(True),
    )
    if product_category:
        query = query.filter(
            QCDefectType.product_category == product_category
        )
    return query.order_by(QCDefectType.defect_name).all()


def create_defect_type(
    db: Session,
    company_id: str,
    data: DefectTypeCreate,
) -> QCDefectType:
    """Create a new defect type."""
    defect_type = QCDefectType(
        id=str(uuid.uuid4()),
        company_id=company_id,
        defect_name=data.defect_name,
        product_category=data.product_category,
        default_severity=data.default_severity,
        default_disposition=data.default_disposition,
        description=data.description,
    )
    db.add(defect_type)
    db.commit()
    db.refresh(defect_type)
    return defect_type


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


def create_media(
    db: Session,
    company_id: str,
    data: MediaCreate,
) -> QCMedia:
    """Create a QC media record."""
    # Verify inspection exists and belongs to company
    inspection = (
        db.query(QCInspection)
        .filter(
            QCInspection.id == data.inspection_id,
            QCInspection.company_id == company_id,
        )
        .first()
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    now = datetime.now(timezone.utc)
    media = QCMedia(
        id=str(uuid.uuid4()),
        step_result_id=data.step_result_id,
        inspection_id=data.inspection_id,
        company_id=company_id,
        file_url=data.file_url,
        caption=data.caption,
        captured_at=data.captured_at or now,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def get_dashboard_stats(db: Session, company_id: str) -> dict:
    """Return counts for the QC dashboard."""
    from datetime import date as _date

    today_start = datetime.combine(
        _date.today(), datetime.min.time()
    ).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(
        _date.today(), datetime.max.time()
    ).replace(tzinfo=timezone.utc)

    base = [QCInspection.company_id == company_id]

    pending_count = (
        db.query(func.count(QCInspection.id))
        .filter(*base, QCInspection.status == "pending")
        .scalar()
        or 0
    )
    in_progress_count = (
        db.query(func.count(QCInspection.id))
        .filter(*base, QCInspection.status == "in_progress")
        .scalar()
        or 0
    )
    failed_today_count = (
        db.query(func.count(QCInspection.id))
        .filter(
            *base,
            QCInspection.status == "failed",
            QCInspection.completed_at >= today_start,
            QCInspection.completed_at <= today_end,
        )
        .scalar()
        or 0
    )
    passed_today_count = (
        db.query(func.count(QCInspection.id))
        .filter(
            *base,
            QCInspection.status.in_(["passed", "conditional_pass"]),
            QCInspection.completed_at >= today_start,
            QCInspection.completed_at <= today_end,
        )
        .scalar()
        or 0
    )
    rework_pending_count = (
        db.query(func.count(QCInspection.id))
        .filter(*base, QCInspection.status == "rework_required")
        .scalar()
        or 0
    )

    return {
        "pending_count": pending_count,
        "in_progress_count": in_progress_count,
        "failed_today_count": failed_today_count,
        "passed_today_count": passed_today_count,
        "rework_pending_count": rework_pending_count,
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def get_qc_summary(
    db: Session,
    company_id: str,
    product_category: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """Generate QC summary report with pass rate, defect frequency, etc."""
    base_filter = [QCInspection.company_id == company_id]
    if product_category:
        base_filter.append(
            QCInspection.product_category == product_category
        )
    if date_from:
        base_filter.append(QCInspection.created_at >= date_from)
    if date_to:
        base_filter.append(QCInspection.created_at <= date_to)

    # Completed inspections only
    completed_filter = base_filter + [
        QCInspection.status.in_(
            ["passed", "failed", "conditional_pass", "rework_required"]
        )
    ]

    total = (
        db.query(func.count(QCInspection.id))
        .filter(*completed_filter)
        .scalar()
        or 0
    )

    if total == 0:
        return {
            "total_inspections": 0,
            "pass_rate": 0.0,
            "fail_rate": 0.0,
            "conditional_pass_rate": 0.0,
            "rework_rate": 0.0,
            "rework_success_rate": 0.0,
            "avg_time_in_qc_minutes": None,
            "defect_frequency": [],
            "inspector_performance": [],
        }

    status_counts = dict(
        db.query(QCInspection.status, func.count(QCInspection.id))
        .filter(*completed_filter)
        .group_by(QCInspection.status)
        .all()
    )

    passed = status_counts.get("passed", 0)
    failed = status_counts.get("failed", 0)
    conditional = status_counts.get("conditional_pass", 0)
    rework_req = status_counts.get("rework_required", 0)

    # Rework success rate
    total_reworks = (
        db.query(func.count(QCReworkRecord.id))
        .join(
            QCInspection,
            QCReworkRecord.original_inspection_id == QCInspection.id,
        )
        .filter(QCInspection.company_id == company_id)
        .scalar()
        or 0
    )
    successful_reworks = (
        db.query(func.count(QCReworkRecord.id))
        .join(
            QCInspection,
            QCReworkRecord.re_inspection_id == QCInspection.id,
        )
        .filter(
            QCInspection.company_id == company_id,
            QCInspection.status.in_(["passed", "conditional_pass"]),
        )
        .scalar()
        or 0
    )
    rework_success_rate = (
        (successful_reworks / total_reworks * 100) if total_reworks > 0 else 0.0
    )

    # Avg time in QC (started_at to completed_at)
    avg_duration = (
        db.query(
            func.avg(
                extract(
                    "epoch",
                    QCInspection.completed_at - QCInspection.started_at,
                )
            )
        )
        .filter(
            *completed_filter,
            QCInspection.started_at.isnot(None),
            QCInspection.completed_at.isnot(None),
        )
        .scalar()
    )
    avg_minutes = round(avg_duration / 60, 1) if avg_duration else None

    # Defect frequency
    defect_rows = (
        db.query(
            QCDefectType.defect_name,
            QCDefectType.product_category,
            QCStepResult.defect_severity,
            func.count(QCStepResult.id),
        )
        .join(QCDefectType, QCStepResult.defect_type_id == QCDefectType.id)
        .join(QCInspection, QCStepResult.inspection_id == QCInspection.id)
        .filter(
            QCInspection.company_id == company_id,
            QCStepResult.result == "fail",
        )
        .group_by(
            QCDefectType.defect_name,
            QCDefectType.product_category,
            QCStepResult.defect_severity,
        )
        .order_by(func.count(QCStepResult.id).desc())
        .all()
    )
    defect_frequency = [
        {
            "defect_name": row[0],
            "product_category": row[1],
            "severity": row[2] or "unknown",
            "count": row[3],
        }
        for row in defect_rows
    ]

    # Inspector performance
    from app.models.user import User

    inspector_rows = (
        db.query(
            QCInspection.inspector_id,
            User.first_name,
            User.last_name,
            func.count(QCInspection.id),
            func.sum(
                case(
                    (QCInspection.status == "passed", 1),
                    else_=0,
                )
            ),
            func.sum(
                case(
                    (QCInspection.status == "failed", 1),
                    else_=0,
                )
            ),
            func.avg(
                extract(
                    "epoch",
                    QCInspection.completed_at - QCInspection.started_at,
                )
            ),
        )
        .join(User, QCInspection.inspector_id == User.id)
        .filter(*completed_filter)
        .group_by(
            QCInspection.inspector_id,
            User.first_name,
            User.last_name,
        )
        .all()
    )

    inspector_performance = []
    for row in inspector_rows:
        avg_dur = round(row[6] / 60, 1) if row[6] else None
        inspector_performance.append(
            {
                "inspector_id": row[0],
                "inspector_name": f"{row[1]} {row[2]}",
                "total_inspections": row[3],
                "pass_count": row[4] or 0,
                "fail_count": row[5] or 0,
                "avg_duration_minutes": avg_dur,
            }
        )

    return {
        "total_inspections": total,
        "pass_rate": round(passed / total * 100, 1),
        "fail_rate": round(failed / total * 100, 1),
        "conditional_pass_rate": round(conditional / total * 100, 1),
        "rework_rate": round(rework_req / total * 100, 1),
        "rework_success_rate": round(rework_success_rate, 1),
        "avg_time_in_qc_minutes": avg_minutes,
        "defect_frequency": defect_frequency,
        "inspector_performance": inspector_performance,
    }


def get_item_qc_history(
    db: Session,
    inventory_item_id: str,
    company_id: str,
) -> list[QCInspection]:
    """Get all inspections for a specific inventory item."""
    inspections = (
        db.query(QCInspection)
        .options(
            joinedload(QCInspection.inspector),
            joinedload(QCInspection.disposition),
        )
        .filter(
            QCInspection.inventory_item_id == inventory_item_id,
            QCInspection.company_id == company_id,
        )
        .order_by(QCInspection.created_at.desc())
        .all()
    )
    return inspections
