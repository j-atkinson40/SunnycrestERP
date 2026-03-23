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
