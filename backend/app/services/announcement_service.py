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

    Returns announcements sorted: pinned first, then by created_at desc.
    Filters by targeting rules. Excludes dismissed unless include_dismissed=True.
    """
    now = datetime.now(timezone.utc)

    # Base query — active, not expired, same company
    query = db.query(Announcement).filter(
        Announcement.company_id == user.company_id,
        Announcement.is_active == True,
        or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
    )

    announcements = query.order_by(
        Announcement.pin_to_top.desc(),
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

        # Skip dismissed unless requested
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
        })

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
    if existing:
        existing.dismissed_at = datetime.now(timezone.utc)
    else:
        record = AnnouncementRead(
            announcement_id=announcement_id,
            user_id=user_id,
            dismissed_at=datetime.now(timezone.utc),
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
