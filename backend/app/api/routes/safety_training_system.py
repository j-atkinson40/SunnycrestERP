"""Safety Training System API routes.

Monthly training program, toolbox talks, and OSHA 300 log management.
"""

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.user import User
from app.services.safety_training_system_service import (
    create_osha_300_from_incident,
    create_osha_300_manual,
    create_toolbox_talk,
    get_osha_300a_summary,
    get_schedule_detail,
    get_training_schedule,
    initialize_annual_schedule,
    list_osha_300,
    list_toolbox_talks,
    post_training,
    review_osha_300_entry,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TrainingPostRequest(BaseModel):
    announcement_id: str


class ToolboxTalkCreate(BaseModel):
    topic_title: str
    topic_category: str = "other"
    conducted_at: datetime | None = None
    description: str | None = None
    duration_minutes: int | None = None
    attendees: list[str] | None = None
    attendees_external: list[str] | None = None
    linked_training_topic_id: str | None = None
    notes: str | None = None


class OSHA300ManualCreate(BaseModel):
    employee_name: str
    date_of_injury: date
    description: str | None = None
    location: str | None = None
    classification: str = "other_recordable"
    days_away: int | None = None
    days_restricted: int | None = None
    injury_type: str = "injury"
    employee_job_title: str | None = None
    privacy_case: bool = False


# ---------------------------------------------------------------------------
# Training Schedule Endpoints
# ---------------------------------------------------------------------------


@router.get("/training/schedule")
def get_schedule(
    year: int = Query(default=None),
    current_user: User = Depends(require_permission("safety.view")),
    db: Session = Depends(get_db),
):
    """Get annual training calendar."""
    if year is None:
        year = date.today().year
    return get_training_schedule(db, current_user.company_id, year)


@router.get("/training/schedule/{schedule_id}")
def get_schedule_entry(
    schedule_id: str,
    current_user: User = Depends(require_permission("safety.view")),
    db: Session = Depends(get_db),
):
    """Get a single schedule entry with full topic details."""
    result = get_schedule_detail(db, schedule_id, current_user.company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Schedule entry not found")
    return result


@router.post("/training/schedule/initialize")
def init_schedule(
    year: int = Query(default=None),
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Initialize annual training schedule for the current year."""
    if year is None:
        year = date.today().year
    records = initialize_annual_schedule(db, current_user.company_id, year)
    return {"created": len(records), "year": year}


@router.post("/training/schedule/{schedule_id}/post")
def mark_training_posted(
    schedule_id: str,
    body: TrainingPostRequest,
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Mark a training as posted (linked to a safety notice announcement)."""
    result = post_training(
        db, schedule_id, current_user.company_id, current_user.id, body.announcement_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Schedule entry not found")
    return {"status": "ok", "schedule_id": schedule_id}


# ---------------------------------------------------------------------------
# Toolbox Talk Endpoints
# ---------------------------------------------------------------------------


@router.get("/toolbox-talks")
def get_toolbox_talks(
    current_user: User = Depends(require_permission("safety.view")),
    db: Session = Depends(get_db),
):
    """List recent toolbox talks."""
    return list_toolbox_talks(db, current_user.company_id)


@router.post("/toolbox-talks", status_code=status.HTTP_201_CREATED)
def create_talk(
    body: ToolboxTalkCreate,
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Create a toolbox talk record."""
    talk = create_toolbox_talk(
        db=db,
        tenant_id=current_user.company_id,
        conducted_by=current_user.id,
        topic_title=body.topic_title,
        topic_category=body.topic_category,
        conducted_at=body.conducted_at,
        description=body.description,
        duration_minutes=body.duration_minutes,
        attendees=body.attendees,
        attendees_external=body.attendees_external,
        linked_training_topic_id=body.linked_training_topic_id,
        notes=body.notes,
    )
    return {"id": talk.id, "status": "created"}


# ---------------------------------------------------------------------------
# OSHA 300 Log Endpoints
# ---------------------------------------------------------------------------


@router.get("/osha-300/entries")
def get_osha_300_entries(
    year: int = Query(default=None),
    current_user: User = Depends(require_permission("safety.view")),
    db: Session = Depends(get_db),
):
    """Get OSHA 300 log entries for a year."""
    if year is None:
        year = date.today().year
    return list_osha_300(db, current_user.company_id, year)


@router.post("/osha-300/entries", status_code=status.HTTP_201_CREATED)
def create_osha_300_entry(
    body: OSHA300ManualCreate,
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Manually create an OSHA 300 entry."""
    entry = create_osha_300_manual(
        db=db,
        tenant_id=current_user.company_id,
        year=body.date_of_injury.year,
        employee_name=body.employee_name,
        date_of_injury=body.date_of_injury,
        description=body.description,
        location=body.location,
        classification=body.classification,
        days_away=body.days_away,
        days_restricted=body.days_restricted,
        injury_type=body.injury_type,
        employee_job_title=body.employee_job_title,
        privacy_case=body.privacy_case,
    )
    return {"id": entry.id, "entry_number": entry.entry_number}


@router.get("/osha-300/summary")
def get_osha_300_summary(
    year: int = Query(default=None),
    current_user: User = Depends(require_permission("safety.view")),
    db: Session = Depends(get_db),
):
    """Get OSHA 300A annual summary."""
    if year is None:
        year = date.today().year
    return get_osha_300a_summary(db, current_user.company_id, year)


@router.post("/osha-300/entries/{entry_id}/review")
def review_entry(
    entry_id: str,
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Mark an OSHA 300 entry as reviewed."""
    success = review_osha_300_entry(
        db, entry_id, current_user.company_id, current_user.id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"status": "ok"}


@router.post("/osha-300/from-incident/{incident_id}")
def create_from_incident(
    incident_id: str,
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Auto-create OSHA 300 entry from a recordable incident."""
    entry = create_osha_300_from_incident(db, incident_id)
    if not entry:
        raise HTTPException(
            status_code=400,
            detail="Incident not found or not OSHA recordable",
        )
    return {"id": entry.id, "entry_number": entry.entry_number}


# ---------------------------------------------------------------------------
# Training Document Management
# ---------------------------------------------------------------------------


class TrainingDocOut(BaseModel):
    topic_key: str
    source: str  # "platform" or "tenant"
    filename: str
    url: str
    uploaded_at: str | None = None
    uploaded_by_name: str | None = None
    notes: str | None = None


class TrainingDocUpload(BaseModel):
    topic_key: str
    filename: str
    file_url: str
    file_size_bytes: int | None = None
    notes: str | None = None


@router.get("/training/documents")
def list_training_documents(
    current_user: User = Depends(require_permission("safety.view")),
    db: Session = Depends(get_db),
):
    """List all 12 training topics with their current document (tenant or platform default)."""
    from app.models.safety_training_topic import SafetyTrainingTopic
    from app.models.tenant_training_doc import TenantTrainingDoc

    topics = db.query(SafetyTrainingTopic).order_by(SafetyTrainingTopic.month_number).all()
    tenant_docs = {
        d.topic_key: d
        for d in db.query(TenantTrainingDoc).filter(
            TenantTrainingDoc.tenant_id == current_user.company_id,
            TenantTrainingDoc.is_active == True,
        ).all()
    }

    user_ids = [d.uploaded_by for d in tenant_docs.values() if d.uploaded_by]
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    results = []
    for topic in topics:
        tenant_doc = tenant_docs.get(topic.topic_key)
        if tenant_doc:
            uploader = users.get(tenant_doc.uploaded_by) if tenant_doc.uploaded_by else None
            results.append(TrainingDocOut(
                topic_key=topic.topic_key,
                source="tenant",
                filename=tenant_doc.filename,
                url=tenant_doc.file_url,
                uploaded_at=tenant_doc.uploaded_at.isoformat() if tenant_doc.uploaded_at else None,
                uploaded_by_name=f"{uploader.first_name} {uploader.last_name}" if uploader else None,
                notes=tenant_doc.notes,
            ))
        else:
            default_filename = f"safety_training_{str(topic.month_number).zfill(2)}_{topic.topic_key}.pdf"
            results.append(TrainingDocOut(
                topic_key=topic.topic_key,
                source="platform",
                filename=default_filename,
                url=f"/static/safety-templates/{default_filename}",
            ))
    return results


@router.get("/training/documents/{topic_key}")
def get_training_document(
    topic_key: str,
    current_user: User = Depends(require_permission("safety.view")),
    db: Session = Depends(get_db),
):
    """Get the current training document for a specific topic."""
    from app.models.safety_training_topic import SafetyTrainingTopic
    from app.models.tenant_training_doc import TenantTrainingDoc

    topic = db.query(SafetyTrainingTopic).filter(SafetyTrainingTopic.topic_key == topic_key).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    tenant_doc = db.query(TenantTrainingDoc).filter(
        TenantTrainingDoc.tenant_id == current_user.company_id,
        TenantTrainingDoc.topic_key == topic_key,
        TenantTrainingDoc.is_active == True,
    ).first()

    if tenant_doc:
        return TrainingDocOut(
            topic_key=topic_key, source="tenant", filename=tenant_doc.filename,
            url=tenant_doc.file_url,
            uploaded_at=tenant_doc.uploaded_at.isoformat() if tenant_doc.uploaded_at else None,
            notes=tenant_doc.notes,
        )

    default_filename = f"safety_training_{str(topic.month_number).zfill(2)}_{topic.topic_key}.pdf"
    return TrainingDocOut(
        topic_key=topic_key, source="platform", filename=default_filename,
        url=f"/static/safety-templates/{default_filename}",
    )


@router.post("/training/documents", status_code=status.HTTP_201_CREATED)
def upload_training_document(
    body: TrainingDocUpload,
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Upload a tenant-specific training document to replace the platform default."""
    from app.models.tenant_training_doc import TenantTrainingDoc

    db.query(TenantTrainingDoc).filter(
        TenantTrainingDoc.tenant_id == current_user.company_id,
        TenantTrainingDoc.topic_key == body.topic_key,
        TenantTrainingDoc.is_active == True,
    ).update({"is_active": False})

    doc = TenantTrainingDoc(
        tenant_id=current_user.company_id, topic_key=body.topic_key,
        filename=body.filename, file_url=body.file_url,
        file_size_bytes=body.file_size_bytes, uploaded_by=current_user.id,
        notes=body.notes,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "status": "uploaded"}


@router.delete("/training/documents/{topic_key}")
def revert_training_document(
    topic_key: str,
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Revert to platform default by deactivating the tenant document."""
    from app.models.tenant_training_doc import TenantTrainingDoc

    updated = db.query(TenantTrainingDoc).filter(
        TenantTrainingDoc.tenant_id == current_user.company_id,
        TenantTrainingDoc.topic_key == topic_key,
        TenantTrainingDoc.is_active == True,
    ).update({"is_active": False})
    db.commit()
    if not updated:
        raise HTTPException(status_code=404, detail="No tenant document found")
    return {"status": "reverted"}


# ---------------------------------------------------------------------------
# Facility Details & Personalized PDF Generation
# ---------------------------------------------------------------------------


class FacilityDetailsUpdate(BaseModel):
    facility_details: dict


class GenerateResult(BaseModel):
    generated: list[str]
    skipped: list[str]


@router.get("/training/facility-details")
def get_facility_details(
    current_user: User = Depends(require_permission("safety.view")),
    db: Session = Depends(get_db),
):
    """Get the tenant's facility details for PDF personalization."""
    from app.api.company_resolver import get_current_company
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return {
        "facility_details": company.get_setting("safety_facility_details", {}),
        "doc_preference": company.get_setting("safety_training_doc_preference"),
        "setup_complete": company.get_setting("safety_training_setup_complete", False),
        "pdfs_generated_at": company.get_setting("safety_pdfs_generated_at"),
    }


@router.put("/training/facility-details")
def save_facility_details(
    body: FacilityDetailsUpdate,
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Save facility details for PDF personalization."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.set_setting("safety_facility_details", body.facility_details)
    db.commit()
    return {"status": "ok"}


@router.post("/training/generate-personalized-pdfs")
def generate_personalized_pdfs(
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Generate personalized PDFs for all topics using facility details.

    Replaces placeholder text in platform defaults with tenant-specific info.
    Skips topics with manually uploaded documents.
    """
    import json
    import os
    import subprocess

    from app.models.company import Company
    from app.models.safety_training_topic import SafetyTrainingTopic
    from app.models.tenant_training_doc import TenantTrainingDoc

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    details = company.get_setting("safety_facility_details", {})
    details["company_name"] = details.get("company_name") or company.name

    topics = db.query(SafetyTrainingTopic).order_by(SafetyTrainingTopic.month_number).all()

    # Find manually uploaded docs (not personalized defaults)
    manual_keys = {
        d.topic_key
        for d in db.query(TenantTrainingDoc).filter(
            TenantTrainingDoc.tenant_id == company.id,
            TenantTrainingDoc.is_active == True,
            TenantTrainingDoc.is_personalized_default == False,
        ).all()
    }

    # Output directory for this tenant
    output_base = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "static", "tenant-pdfs", company.id,
    )
    os.makedirs(output_base, exist_ok=True)

    generated = []
    skipped = []

    # Find the generation script
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "..", "scripts", "generate_safety_training_pdfs.py",
    )

    for topic in topics:
        if topic.topic_key in manual_keys:
            skipped.append(topic.title)
            continue

        output_filename = f"safety_training_{str(topic.month_number).zfill(2)}_{topic.topic_key}.pdf"
        output_path = os.path.join(output_base, output_filename)

        # Call the generation script with details
        params = json.dumps({
            "topic_key": topic.topic_key,
            "output_path": output_path,
            "details": details,
        })

        try:
            subprocess.run(
                ["python", script_path, params],
                capture_output=True, text=True, timeout=30,
            )
        except Exception as exc:
            logger.warning("PDF generation failed for %s: %s", topic.topic_key, exc)
            continue

        # Determine URL path
        file_url = f"/static/tenant-pdfs/{company.id}/{output_filename}"

        # Upsert tenant doc record
        existing = db.query(TenantTrainingDoc).filter(
            TenantTrainingDoc.tenant_id == company.id,
            TenantTrainingDoc.topic_key == topic.topic_key,
            TenantTrainingDoc.is_active == True,
            TenantTrainingDoc.is_personalized_default == True,
        ).first()

        if existing:
            existing.file_url = file_url
            existing.filename = output_filename
            existing.notes = f"Auto-generated with facility details"
        else:
            # Deactivate any old personalized defaults
            db.query(TenantTrainingDoc).filter(
                TenantTrainingDoc.tenant_id == company.id,
                TenantTrainingDoc.topic_key == topic.topic_key,
                TenantTrainingDoc.is_personalized_default == True,
            ).update({"is_active": False})

            doc = TenantTrainingDoc(
                tenant_id=company.id,
                topic_key=topic.topic_key,
                filename=output_filename,
                file_url=file_url,
                is_personalized_default=True,
                is_active=True,
                uploaded_by=current_user.id,
                notes="Auto-generated with facility details",
            )
            db.add(doc)

        generated.append(topic.title)

    from datetime import timezone
    company.set_setting("safety_pdfs_generated_at", datetime.now(timezone.utc).isoformat())
    company.set_setting("safety_training_doc_preference", "platform_defaults")
    db.commit()

    return GenerateResult(generated=generated, skipped=skipped)


@router.post("/training/complete-setup")
def complete_safety_training_setup(
    current_user: User = Depends(require_permission("safety.create")),
    db: Session = Depends(get_db),
):
    """Mark safety training setup as complete."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.set_setting("safety_training_setup_complete", True)
    db.commit()

    from app.services.onboarding_hooks import on_safety_training_configured
    on_safety_training_configured(db, company.id)

    return {"status": "ok"}
