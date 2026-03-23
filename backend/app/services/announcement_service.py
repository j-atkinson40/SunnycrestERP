"""Company Announcements service.

Handles CRUD, targeting logic, and read/dismiss tracking for announcements.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.announcement import Announcement
from app.models.announcement_read import AnnouncementRead
from app.models.employee_profile import EmployeeProfile
from app.models.role import Role
from app.models.user import User

logger = logging.getLogger(__name__)


def can_user_create_announcements(db: Session, user: User) -> bool:
    """Check if user has announcement creation permission."""
    # Admin always can
    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role and role.is_system and role.slug == "admin":
        return True
    # Check employee profile permission
    profile = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.user_id == user.id)
        .first()
    )
    return bool(profile and profile.can_create_announcements)


def get_announcements_for_employee(
    db: Session,
    user: User,
    include_dismissed: bool = False,
) -> list[dict]:
    """Get active, non-expired announcements targeted at this employee.

    Returns announcements sorted: required unacknowledged safety notices first,
    then pinned, then by created_at desc.
    Filters by targeting rules. Excludes dismissed unless include_dismissed=True.
    For safety notices with requires_acknowledgment=True, only hide if
    acknowledgment_type='acknowledged' (regular dismiss does NOT hide them).
    """
    now = datetime.now(timezone.utc)

    # Base query — active, not expired, same company
    query = db.query(Announcement).filter(
        Announcement.company_id == user.company_id,
        Announcement.is_active == True,
        or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
    )

    announcements = query.order_by(
        Announcement.created_at.desc(),
    ).all()

    # Get employee profile for targeting
    profile = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.user_id == user.id)
        .first()
    )
    employee_areas = (profile.functional_areas or []) if profile else []

    # Get read/dismiss records for this user
    read_records = {
        r.announcement_id: r
        for r in db.query(AnnouncementRead)
        .filter(AnnouncementRead.user_id == user.id)
        .all()
    }

    results = []
    for ann in announcements:
        # Check targeting
        if not _matches_target(ann, user, employee_areas):
            continue

        read_record = read_records.get(ann.id)

        # For safety notices with requires_acknowledgment, only hide if acknowledged
        if (
            ann.content_type == "safety_notice"
            and ann.requires_acknowledgment
        ):
            if (
                not include_dismissed
                and read_record
                and read_record.acknowledgment_type == "acknowledged"
            ):
                continue
        else:
            # Normal dismiss logic for regular announcements
            if not include_dismissed and read_record and read_record.dismissed_at:
                continue

        results.append({
            "id": ann.id,
            "title": ann.title,
            "body": ann.body,
            "priority": ann.priority,
            "pin_to_top": ann.pin_to_top,
            "created_at": ann.created_at.isoformat() if ann.created_at else None,
            "expires_at": ann.expires_at.isoformat() if ann.expires_at else None,
            "created_by_name": (
                f"{ann.created_by.first_name} {ann.created_by.last_name}"
                if ann.created_by else "Unknown"
            ),
            "is_read": read_record is not None,
            "is_dismissed": bool(read_record and read_record.dismissed_at),
            "content_type": ann.content_type,
            "safety_category": ann.safety_category,
            "requires_acknowledgment": ann.requires_acknowledgment,
            "is_compliance_relevant": ann.is_compliance_relevant,
            "document_url": ann.document_url,
            "document_filename": ann.document_filename,
            "linked_equipment_id": ann.linked_equipment_id,
            "linked_incident_id": ann.linked_incident_id,
            "linked_training_id": ann.linked_training_id,
            "acknowledgment_deadline": (
                ann.acknowledgment_deadline.isoformat()
                if ann.acknowledgment_deadline else None
            ),
            "is_acknowledged": bool(
                read_record and read_record.acknowledgment_type == "acknowledged"
            ),
        })

    # Sort: required unacknowledged safety notices first, then pinned, then by created_at desc
    def _sort_key(item: dict):
        # 0 = required unacknowledged safety notice (highest priority)
        # 1 = pinned
        # 2 = everything else
        if (
            item["content_type"] == "safety_notice"
            and item["requires_acknowledgment"]
            and not item["is_acknowledged"]
        ):
            tier = 0
        elif item["pin_to_top"]:
            tier = 1
        else:
            tier = 2
        return (tier, item["created_at"] or "")

    results.sort(key=lambda item: (
        _sort_key(item)[0],
        # Reverse created_at within each tier (newest first)
        "" if not item["created_at"] else "".join(
            chr(255 - ord(c)) if c.isdigit() else c for c in item["created_at"]
        ),
    ))

    return results


def _matches_target(
    ann: Announcement,
    user: User,
    employee_areas: list[str],
) -> bool:
    """Check if an announcement targets this employee."""
    if ann.target_type == "everyone":
        return True
    if ann.target_type == "functional_area":
        return ann.target_value in employee_areas
    if ann.target_type == "employee_type":
        return user.track == ann.target_value
    if ann.target_type == "specific_employees":
        ids = ann.target_employee_ids or []
        return user.id in ids
    return False


def create_announcement(
    db: Session,
    user: User,
    title: str,
    body: str | None,
    priority: str = "info",
    target_type: str = "everyone",
    target_value: str | None = None,
    target_employee_ids: list[str] | None = None,
    pin_to_top: bool = False,
    expires_at: datetime | None = None,
    content_type: str = "announcement",
    safety_category: str | None = None,
    requires_acknowledgment: bool = False,
    is_compliance_relevant: bool = False,
    document_url: str | None = None,
    document_filename: str | None = None,
    linked_equipment_id: str | None = None,
    linked_incident_id: str | None = None,
    linked_training_id: str | None = None,
    acknowledgment_deadline: datetime | None = None,
) -> Announcement:
    """Create a new announcement."""
    ann = Announcement(
        company_id=user.company_id,
        created_by_user_id=user.id,
        title=title,
        body=body,
        priority=priority,
        target_type=target_type,
        target_value=target_value,
        target_employee_ids=target_employee_ids,
        pin_to_top=pin_to_top,
        expires_at=expires_at,
        content_type=content_type,
        safety_category=safety_category,
        requires_acknowledgment=requires_acknowledgment,
        is_compliance_relevant=is_compliance_relevant,
        document_url=document_url,
        document_filename=document_filename,
        linked_equipment_id=linked_equipment_id,
        linked_incident_id=linked_incident_id,
        linked_training_id=linked_training_id,
        acknowledgment_deadline=acknowledgment_deadline,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


def mark_announcement_read(db: Session, user_id: str, announcement_id: str) -> None:
    """Mark an announcement as read (creates read record if not exists)."""
    existing = (
        db.query(AnnouncementRead)
        .filter(
            AnnouncementRead.announcement_id == announcement_id,
            AnnouncementRead.user_id == user_id,
        )
        .first()
    )
    if not existing:
        record = AnnouncementRead(
            announcement_id=announcement_id,
            user_id=user_id,
        )
        db.add(record)
        db.commit()


def dismiss_announcement(db: Session, user_id: str, announcement_id: str) -> None:
    """Dismiss an announcement (mark as read + dismissed)."""
    existing = (
        db.query(AnnouncementRead)
        .filter(
            AnnouncementRead.announcement_id == announcement_id,
            AnnouncementRead.user_id == user_id,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.dismissed_at = now
        existing.acknowledgment_type = "dismissed"
    else:
        record = AnnouncementRead(
            announcement_id=announcement_id,
            user_id=user_id,
            dismissed_at=now,
            acknowledgment_type="dismissed",
        )
        db.add(record)
    db.commit()


def acknowledge_safety_notice(
    db: Session, user_id: str, announcement_id: str, note: str | None = None
) -> None:
    """Acknowledge a safety notice (stronger than dismiss)."""
    existing = (
        db.query(AnnouncementRead)
        .filter(
            AnnouncementRead.announcement_id == announcement_id,
            AnnouncementRead.user_id == user_id,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.dismissed_at = now
        existing.acknowledgment_type = "acknowledged"
        existing.acknowledgment_note = note
    else:
        record = AnnouncementRead(
            announcement_id=announcement_id,
            user_id=user_id,
            dismissed_at=now,
            acknowledgment_type="acknowledged",
            acknowledgment_note=note,
        )
        db.add(record)
    db.commit()


def deactivate_announcement(db: Session, announcement_id: str, company_id: str) -> bool:
    """Soft-delete an announcement. Returns True if found and deactivated."""
    ann = (
        db.query(Announcement)
        .filter(
            Announcement.id == announcement_id,
            Announcement.company_id == company_id,
        )
        .first()
    )
    if not ann:
        return False
    ann.is_active = False
    db.commit()
    return True


def get_company_announcements(
    db: Session,
    company_id: str,
    include_inactive: bool = False,
) -> list[Announcement]:
    """Get all announcements for a company (for management UI)."""
    query = db.query(Announcement).filter(
        Announcement.company_id == company_id
    )
    if not include_inactive:
        query = query.filter(Announcement.is_active == True)
    return query.order_by(Announcement.created_at.desc()).all()


def get_safety_notice_compliance_impact(
    db: Session, company_id: str
) -> dict:
    """Calculate compliance score impact from unacknowledged safety notices."""
    now = datetime.now(timezone.utc)

    notices = (
        db.query(Announcement)
        .filter(
            Announcement.company_id == company_id,
            Announcement.content_type == "safety_notice",
            Announcement.is_compliance_relevant == True,
            Announcement.requires_acknowledgment == True,
            Announcement.is_active == True,
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
        )
        .all()
    )

    if not notices:
        return {"score_impact": 0, "gaps": []}

    gaps = []
    for notice in notices:
        # Get targeted employees
        all_users = (
            db.query(User)
            .filter(User.company_id == company_id, User.is_active == True)
            .all()
        )
        profiles = {
            p.user_id: p
            for p in db.query(EmployeeProfile)
            .filter(EmployeeProfile.user_id.in_([u.id for u in all_users]))
            .all()
        }

        targeted = []
        for u in all_users:
            profile = profiles.get(u.id)
            areas = (profile.functional_areas or []) if profile else []
            if _matches_target(notice, u, areas):
                targeted.append(u)

        if not targeted:
            continue

        # Check acknowledgments
        ack_records = (
            db.query(AnnouncementRead)
            .filter(
                AnnouncementRead.announcement_id == notice.id,
                AnnouncementRead.acknowledgment_type == "acknowledged",
            )
            .all()
        )
        ack_ids = {r.user_id for r in ack_records}
        unacked = [u for u in targeted if u.id not in ack_ids]

        if unacked:
            is_overdue = (
                notice.acknowledgment_deadline is not None
                and now > notice.acknowledgment_deadline
            )
            gaps.append({
                "notice_id": notice.id,
                "notice_title": notice.title,
                "category": notice.safety_category,
                "unacknowledged_count": len(unacked),
                "total_targeted": len(targeted),
                "deadline": notice.acknowledgment_deadline.isoformat() if notice.acknowledgment_deadline else None,
                "is_overdue": is_overdue,
            })

    score_impact = 0
    for gap in gaps:
        pct = gap["unacknowledged_count"] / gap["total_targeted"]
        base = pct * 5
        score_impact += base * 2 if gap["is_overdue"] else base

    return {
        "score_impact": min(round(score_impact, 1), 20),
        "gaps": gaps,
    }


def get_safety_notices(
    db: Session,
    company_id: str,
    category: str | None = None,
    status_filter: str | None = None,
) -> list[Announcement]:
    """Get safety notices for the safety module view."""
    query = db.query(Announcement).filter(
        Announcement.company_id == company_id,
        Announcement.content_type == "safety_notice",
    )
    if category:
        query = query.filter(Announcement.safety_category == category)
    if status_filter == "active":
        query = query.filter(Announcement.is_active == True)
    elif status_filter == "requires_acknowledgment":
        query = query.filter(
            Announcement.requires_acknowledgment == True,
            Announcement.is_active == True,
        )
    elif status_filter == "compliance":
        query = query.filter(
            Announcement.is_compliance_relevant == True,
            Announcement.is_active == True,
        )
    return query.order_by(Announcement.created_at.desc()).all()


def get_notice_acknowledgment_status(
    db: Session, announcement_id: str, company_id: str
) -> dict:
    """Get detailed acknowledgment status for a safety notice."""
    notice = (
        db.query(Announcement)
        .filter(Announcement.id == announcement_id, Announcement.company_id == company_id)
        .first()
    )
    if not notice:
        return {"error": "not_found"}

    # Get all targeted employees
    all_users = (
        db.query(User)
        .filter(User.company_id == company_id, User.is_active == True)
        .all()
    )
    profiles = {
        p.user_id: p
        for p in db.query(EmployeeProfile)
        .filter(EmployeeProfile.user_id.in_([u.id for u in all_users]))
        .all()
    }

    targeted = []
    for u in all_users:
        profile = profiles.get(u.id)
        areas = (profile.functional_areas or []) if profile else []
        if _matches_target(notice, u, areas):
            targeted.append(u)

    # Get read records
    reads = {
        r.user_id: r
        for r in db.query(AnnouncementRead)
        .filter(AnnouncementRead.announcement_id == announcement_id)
        .all()
    }

    employees = []
    for u in targeted:
        read = reads.get(u.id)
        employees.append({
            "user_id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "status": "acknowledged" if read and read.acknowledgment_type == "acknowledged" else "pending",
            "acknowledged_at": read.dismissed_at.isoformat() if read and read.acknowledgment_type == "acknowledged" else None,
            "note": read.acknowledgment_note if read else None,
        })

    ack_count = sum(1 for e in employees if e["status"] == "acknowledged")

    return {
        "notice_id": notice.id,
        "title": notice.title,
        "safety_category": notice.safety_category,
        "total_targeted": len(employees),
        "acknowledged_count": ack_count,
        "employees": employees,
    }
