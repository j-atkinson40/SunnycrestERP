"""Safety Training System service.

Monthly training program, toolbox talks, and OSHA 300 log management.
"""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.osha_300_entry import OSHA300Entry
from app.models.safety_incident import SafetyIncident
from app.models.safety_training_topic import SafetyTrainingTopic
from app.models.tenant_training_schedule import TenantTrainingSchedule
from app.models.toolbox_talk import ToolboxTalk
from app.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Training Schedule
# ---------------------------------------------------------------------------


def initialize_annual_schedule(
    db: Session, tenant_id: str, year: int
) -> list[TenantTrainingSchedule]:
    """Create training schedule records for all 12 months. Idempotent."""
    existing = (
        db.query(TenantTrainingSchedule)
        .filter(
            TenantTrainingSchedule.tenant_id == tenant_id,
            TenantTrainingSchedule.year == year,
        )
        .count()
    )
    if existing > 0:
        return []

    topics = (
        db.query(SafetyTrainingTopic)
        .order_by(SafetyTrainingTopic.month_number)
        .all()
    )
    records = []
    for topic in topics:
        schedule = TenantTrainingSchedule(
            tenant_id=tenant_id,
            year=year,
            month_number=topic.month_number,
            topic_id=topic.id,
            status="upcoming",
        )
        db.add(schedule)
        records.append(schedule)
    db.commit()
    return records


def get_training_schedule(
    db: Session, tenant_id: str, year: int
) -> list[dict]:
    """Get the annual training calendar with topic details."""
    schedules = (
        db.query(TenantTrainingSchedule)
        .filter(
            TenantTrainingSchedule.tenant_id == tenant_id,
            TenantTrainingSchedule.year == year,
        )
        .order_by(TenantTrainingSchedule.month_number)
        .all()
    )

    topic_ids = [s.topic_id for s in schedules]
    topics = {
        t.id: t
        for t in db.query(SafetyTrainingTopic)
        .filter(SafetyTrainingTopic.id.in_(topic_ids))
        .all()
    } if topic_ids else {}

    user_ids = [s.posted_by for s in schedules if s.posted_by]
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    now = datetime.now(timezone.utc)
    current_month = now.month

    results = []
    for s in schedules:
        topic = topics.get(s.topic_id)
        posted_user = users.get(s.posted_by) if s.posted_by else None

        effective_status = s.status
        if s.status in ("upcoming", "reminder_sent") and s.month_number < current_month and s.year <= now.year:
            effective_status = "overdue"

        results.append({
            "id": s.id,
            "year": s.year,
            "month_number": s.month_number,
            "status": effective_status,
            "topic_id": s.topic_id,
            "topic_key": topic.topic_key if topic else None,
            "topic_title": topic.title if topic else None,
            "osha_standard": topic.osha_standard if topic else None,
            "osha_standard_label": topic.osha_standard_label if topic else None,
            "is_high_risk": topic.is_high_risk if topic else False,
            "suggested_duration_minutes": topic.suggested_duration_minutes if topic else 30,
            "target_roles": topic.target_roles if topic else [],
            "key_points": topic.key_points if topic else [],
            "discussion_questions": topic.discussion_questions if topic else [],
            "pdf_filename_template": topic.pdf_filename_template if topic else None,
            "description": topic.description if topic else None,
            "announcement_id": s.announcement_id,
            "posted_by_name": (
                f"{posted_user.first_name} {posted_user.last_name}"
                if posted_user
                else None
            ),
            "posted_at": s.posted_at.isoformat() if s.posted_at else None,
            "completion_rate": float(s.completion_rate) if s.completion_rate else None,
            "notes": s.notes,
        })
    return results


def get_schedule_detail(
    db: Session, schedule_id: str, tenant_id: str
) -> dict | None:
    """Get a single training schedule entry with full topic details."""
    schedule = (
        db.query(TenantTrainingSchedule)
        .filter(
            TenantTrainingSchedule.id == schedule_id,
            TenantTrainingSchedule.tenant_id == tenant_id,
        )
        .first()
    )
    if not schedule:
        return None

    topic = (
        db.query(SafetyTrainingTopic)
        .filter(SafetyTrainingTopic.id == schedule.topic_id)
        .first()
    )
    if not topic:
        return None

    return {
        "id": schedule.id,
        "year": schedule.year,
        "month_number": schedule.month_number,
        "status": schedule.status,
        "topic": {
            "id": topic.id,
            "topic_key": topic.topic_key,
            "title": topic.title,
            "description": topic.description,
            "osha_standard": topic.osha_standard,
            "osha_standard_label": topic.osha_standard_label,
            "suggested_duration_minutes": topic.suggested_duration_minutes,
            "target_roles": topic.target_roles,
            "key_points": topic.key_points,
            "discussion_questions": topic.discussion_questions,
            "pdf_filename_template": topic.pdf_filename_template,
            "is_high_risk": topic.is_high_risk,
        },
        "announcement_id": schedule.announcement_id,
        "posted_at": schedule.posted_at.isoformat() if schedule.posted_at else None,
        "completion_rate": (
            float(schedule.completion_rate) if schedule.completion_rate else None
        ),
        "notes": schedule.notes,
    }


def post_training(
    db: Session,
    schedule_id: str,
    tenant_id: str,
    user_id: str,
    announcement_id: str,
) -> TenantTrainingSchedule | None:
    """Mark a training as posted (linked to a safety notice announcement)."""
    schedule = (
        db.query(TenantTrainingSchedule)
        .filter(
            TenantTrainingSchedule.id == schedule_id,
            TenantTrainingSchedule.tenant_id == tenant_id,
        )
        .first()
    )
    if not schedule:
        return None

    schedule.status = "posted"
    schedule.announcement_id = announcement_id
    schedule.posted_by = user_id
    schedule.posted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(schedule)
    return schedule


# ---------------------------------------------------------------------------
# Toolbox Talks
# ---------------------------------------------------------------------------


def create_toolbox_talk(
    db: Session,
    tenant_id: str,
    conducted_by: str,
    topic_title: str,
    topic_category: str = "other",
    conducted_at: datetime | None = None,
    description: str | None = None,
    duration_minutes: int | None = None,
    attendees: list[str] | None = None,
    attendees_external: list[str] | None = None,
    linked_training_topic_id: str | None = None,
    notes: str | None = None,
) -> ToolboxTalk:
    """Create a toolbox talk record."""
    count = len(attendees or []) + len(attendees_external or [])
    talk = ToolboxTalk(
        tenant_id=tenant_id,
        conducted_by=conducted_by,
        conducted_at=conducted_at or datetime.now(timezone.utc),
        topic_title=topic_title,
        topic_category=topic_category,
        description=description,
        duration_minutes=duration_minutes,
        attendees=attendees,
        attendees_external=attendees_external,
        attendee_count=count,
        linked_training_topic_id=linked_training_topic_id,
        notes=notes,
    )
    db.add(talk)
    db.commit()
    db.refresh(talk)
    return talk


def list_toolbox_talks(
    db: Session, tenant_id: str, limit: int = 50
) -> list[dict]:
    """List recent toolbox talks."""
    talks = (
        db.query(ToolboxTalk)
        .filter(ToolboxTalk.tenant_id == tenant_id)
        .order_by(ToolboxTalk.conducted_at.desc())
        .limit(limit)
        .all()
    )
    user_ids = list({t.conducted_by for t in talks})
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    results = []
    for t in talks:
        conductor = users.get(t.conducted_by)
        results.append({
            "id": t.id,
            "topic_title": t.topic_title,
            "topic_category": t.topic_category,
            "conducted_at": t.conducted_at.isoformat() if t.conducted_at else None,
            "conducted_by_name": (
                f"{conductor.first_name} {conductor.last_name}"
                if conductor
                else "Unknown"
            ),
            "attendee_count": t.attendee_count,
            "attendees": t.attendees,
            "attendees_external": t.attendees_external,
            "duration_minutes": t.duration_minutes,
            "description": t.description,
            "notes": t.notes,
            "linked_training_topic_id": t.linked_training_topic_id,
        })
    return results


# ---------------------------------------------------------------------------
# OSHA 300 Log
# ---------------------------------------------------------------------------


def create_osha_300_from_incident(
    db: Session, incident_id: str
) -> OSHA300Entry | None:
    """Auto-create an OSHA 300 entry from a recordable incident."""
    incident = (
        db.query(SafetyIncident).filter(SafetyIncident.id == incident_id).first()
    )
    if not incident or not incident.osha_recordable:
        return None

    existing = (
        db.query(OSHA300Entry)
        .filter(OSHA300Entry.incident_id == incident_id)
        .first()
    )
    if existing:
        return existing

    year = incident.incident_date.year

    last = (
        db.query(func.max(OSHA300Entry.entry_number))
        .filter(
            OSHA300Entry.tenant_id == incident.company_id,
            OSHA300Entry.year == year,
        )
        .scalar()
    )
    entry_number = (last or 0) + 1

    classification = "other_recordable"
    if incident.days_away_from_work and incident.days_away_from_work > 0:
        classification = "days_away"
    elif incident.days_on_restricted_duty and incident.days_on_restricted_duty > 0:
        classification = "restricted_work"

    employee_name = "Unknown"
    if incident.involved_employee_id:
        emp = db.query(User).filter(User.id == incident.involved_employee_id).first()
        if emp:
            employee_name = f"{emp.first_name} {emp.last_name}"

    entry = OSHA300Entry(
        tenant_id=incident.company_id,
        incident_id=incident_id,
        year=year,
        entry_number=entry_number,
        employee_name=employee_name,
        date_of_injury=incident.incident_date,
        location=incident.location,
        description=(incident.description[:500] if incident.description else None),
        classification=classification,
        days_away=incident.days_away_from_work,
        days_restricted=incident.days_on_restricted_duty,
        injury_type=incident.injury_type or "injury",
        is_auto_populated=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_osha_300(db: Session, tenant_id: str, year: int) -> list[dict]:
    """Get OSHA 300 log entries for a year."""
    entries = (
        db.query(OSHA300Entry)
        .filter(OSHA300Entry.tenant_id == tenant_id, OSHA300Entry.year == year)
        .order_by(OSHA300Entry.entry_number)
        .all()
    )
    return [
        {
            "id": e.id,
            "entry_number": e.entry_number,
            "employee_name": e.employee_name,
            "employee_job_title": e.employee_job_title,
            "date_of_injury": str(e.date_of_injury),
            "location": e.location,
            "description": e.description,
            "classification": e.classification,
            "days_away": e.days_away,
            "days_restricted": e.days_restricted,
            "injury_type": e.injury_type,
            "privacy_case": e.privacy_case,
            "is_auto_populated": e.is_auto_populated,
            "reviewed_by": e.reviewed_by,
            "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
            "incident_id": e.incident_id,
        }
        for e in entries
    ]


def get_osha_300a_summary(db: Session, tenant_id: str, year: int) -> dict:
    """Generate OSHA 300A annual summary."""
    entries = (
        db.query(OSHA300Entry)
        .filter(OSHA300Entry.tenant_id == tenant_id, OSHA300Entry.year == year)
        .all()
    )

    total = len(entries)
    pending_review = sum(
        1 for e in entries if e.is_auto_populated and not e.reviewed_at
    )

    return {
        "year": year,
        "total_cases": total,
        "deaths": sum(1 for e in entries if e.classification == "death"),
        "days_away_cases": sum(1 for e in entries if e.classification == "days_away"),
        "restricted_cases": sum(
            1 for e in entries if e.classification == "restricted_work"
        ),
        "other_cases": sum(
            1
            for e in entries
            if e.classification in ("other_recordable", "transfer")
        ),
        "total_days_away": sum(e.days_away or 0 for e in entries),
        "total_days_restricted": sum(e.days_restricted or 0 for e in entries),
        "injury_count": sum(1 for e in entries if e.injury_type == "injury"),
        "skin_disorder_count": sum(
            1 for e in entries if e.injury_type == "skin_disorder"
        ),
        "respiratory_count": sum(
            1 for e in entries if e.injury_type == "respiratory"
        ),
        "poisoning_count": sum(1 for e in entries if e.injury_type == "poisoning"),
        "hearing_loss_count": sum(
            1 for e in entries if e.injury_type == "hearing_loss"
        ),
        "other_illness_count": sum(1 for e in entries if e.injury_type == "other"),
        "pending_review": pending_review,
    }


def review_osha_300_entry(
    db: Session, entry_id: str, tenant_id: str, reviewer_id: str
) -> bool:
    """Mark an OSHA 300 entry as reviewed."""
    entry = (
        db.query(OSHA300Entry)
        .filter(OSHA300Entry.id == entry_id, OSHA300Entry.tenant_id == tenant_id)
        .first()
    )
    if not entry:
        return False
    entry.reviewed_by = reviewer_id
    entry.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return True


def create_osha_300_manual(
    db: Session,
    tenant_id: str,
    year: int,
    employee_name: str,
    date_of_injury: date,
    description: str | None = None,
    location: str | None = None,
    classification: str = "other_recordable",
    days_away: int | None = None,
    days_restricted: int | None = None,
    injury_type: str = "injury",
    employee_job_title: str | None = None,
    privacy_case: bool = False,
) -> OSHA300Entry:
    """Manually create an OSHA 300 entry."""
    last = (
        db.query(func.max(OSHA300Entry.entry_number))
        .filter(OSHA300Entry.tenant_id == tenant_id, OSHA300Entry.year == year)
        .scalar()
    )
    entry_number = (last or 0) + 1

    entry = OSHA300Entry(
        tenant_id=tenant_id,
        year=year,
        entry_number=entry_number,
        employee_name=employee_name,
        employee_job_title=employee_job_title,
        date_of_injury=date_of_injury,
        location=location,
        description=description,
        classification=classification,
        days_away=days_away,
        days_restricted=days_restricted,
        injury_type=injury_type,
        privacy_case=privacy_case,
        is_auto_populated=False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
