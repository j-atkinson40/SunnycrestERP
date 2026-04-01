"""Driver announcement endpoints — driver-facing and admin management."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.announcement import Announcement
from app.models.announcement_read import AnnouncementRead
from app.models.user import User

router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────────────────────


class CreateAnnouncementRequest(BaseModel):
    title: str
    body: str
    urgency: str = "normal"  # normal, urgent, safety
    audience: str = "all_drivers"  # all_drivers, specific_drivers
    target_driver_ids: list[str] = []
    expires_at: str | None = None  # ISO datetime


class UpdateAnnouncementRequest(BaseModel):
    is_active: bool | None = None
    expires_at: str | None = None


# ── Urgency mapping to existing Announcement fields ─────────────────────────


def _urgency_to_fields(urgency: str) -> dict:
    if urgency == "safety":
        return {
            "priority": "critical",
            "content_type": "safety_notice",
            "requires_acknowledgment": True,
        }
    elif urgency == "urgent":
        return {
            "priority": "warning",
            "content_type": "announcement",
            "requires_acknowledgment": False,
        }
    return {
        "priority": "info",
        "content_type": "announcement",
        "requires_acknowledgment": False,
    }


def _urgency_from_announcement(ann: Announcement) -> str:
    if ann.content_type == "safety_notice" or ann.priority == "critical":
        return "safety"
    if ann.priority == "warning":
        return "urgent"
    return "normal"


# ── Driver-facing endpoints ──────────────────────────────────────────────────


@router.get("/driver/announcements")
def get_driver_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get active announcements targeted at this driver."""
    now = datetime.now(timezone.utc)

    announcements = (
        db.query(Announcement)
        .filter(
            Announcement.company_id == current_user.company_id,
            Announcement.is_active.is_(True),
            or_(
                Announcement.expires_at.is_(None),
                Announcement.expires_at > now,
            ),
            or_(
                Announcement.target_type == "everyone",
                Announcement.target_employee_ids.contains([current_user.id]),
            ),
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )

    # Check which are acknowledged by this user
    acked_ids = set()
    if announcements:
        ann_ids = [a.id for a in announcements]
        reads = (
            db.query(AnnouncementRead.announcement_id)
            .filter(
                AnnouncementRead.announcement_id.in_(ann_ids),
                AnnouncementRead.user_id == current_user.id,
            )
            .all()
        )
        acked_ids = {r[0] for r in reads}

    result = []
    for ann in announcements:
        urgency = _urgency_from_announcement(ann)
        result.append({
            "id": ann.id,
            "title": ann.title,
            "body": ann.body,
            "urgency": urgency,
            "acknowledged": ann.id in acked_ids,
            "requires_acknowledgment": ann.requires_acknowledgment or False,
            "published_at": ann.created_at.isoformat() if ann.created_at else None,
            "expires_at": ann.expires_at.isoformat() if ann.expires_at else None,
        })

    # Sort: unacked safety first, then urgent, then normal, then acked
    urgency_order = {"safety": 0, "urgent": 1, "normal": 2}
    result.sort(key=lambda a: (
        0 if not a["acknowledged"] else 1,
        urgency_order.get(a["urgency"], 3),
    ))

    return result


@router.post("/driver/announcements/{announcement_id}/acknowledge")
def acknowledge_announcement(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an announcement as acknowledged by this driver."""
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    # Upsert
    existing = (
        db.query(AnnouncementRead)
        .filter(
            AnnouncementRead.announcement_id == announcement_id,
            AnnouncementRead.user_id == current_user.id,
        )
        .first()
    )
    if not existing:
        read = AnnouncementRead(
            id=str(uuid.uuid4()),
            announcement_id=announcement_id,
            user_id=current_user.id,
        )
        db.add(read)
        db.commit()

    return {"acknowledged": True}


# ── Admin endpoints ──────────────────────────────────────────────────────────


@router.get("/admin/announcements")
def list_admin_announcements(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all announcements for the company with ack stats."""
    announcements = (
        db.query(Announcement)
        .filter(Announcement.company_id == current_user.company_id)
        .order_by(Announcement.created_at.desc())
        .limit(50)
        .all()
    )

    result = []
    for ann in announcements:
        # Count acks
        ack_count = (
            db.query(func.count(AnnouncementRead.id))
            .filter(AnnouncementRead.announcement_id == ann.id)
            .scalar()
            or 0
        )

        # Total targeted
        if ann.target_type == "everyone":
            from app.models.driver import Driver
            total_targeted = (
                db.query(func.count(Driver.id))
                .filter(Driver.company_id == current_user.company_id, Driver.active.is_(True))
                .scalar()
                or 0
            )
        else:
            total_targeted = len(ann.target_employee_ids or [])

        result.append({
            "id": ann.id,
            "title": ann.title,
            "body": ann.body,
            "urgency": _urgency_from_announcement(ann),
            "audience": "all_drivers" if ann.target_type == "everyone" else "specific_drivers",
            "target_driver_ids": ann.target_employee_ids or [],
            "is_active": ann.is_active,
            "expires_at": ann.expires_at.isoformat() if ann.expires_at else None,
            "created_at": ann.created_at.isoformat() if ann.created_at else None,
            "ack_count": ack_count,
            "total_targeted": total_targeted,
        })

    return result


@router.post("/admin/announcements", status_code=status.HTTP_201_CREATED)
def create_announcement(
    data: CreateAnnouncementRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new driver announcement."""
    fields = _urgency_to_fields(data.urgency)

    ann = Announcement(
        id=str(uuid.uuid4()),
        company_id=current_user.company_id,
        created_by_user_id=current_user.id,
        title=data.title,
        body=data.body,
        priority=fields["priority"],
        content_type=fields["content_type"],
        requires_acknowledgment=fields["requires_acknowledgment"],
        target_type="everyone" if data.audience == "all_drivers" else "specific_employees",
        target_employee_ids=data.target_driver_ids if data.audience == "specific_drivers" else [],
        expires_at=datetime.fromisoformat(data.expires_at) if data.expires_at else None,
        is_active=True,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)

    return {"id": ann.id, "title": ann.title}


@router.patch("/admin/announcements/{announcement_id}")
def update_announcement(
    announcement_id: str,
    data: UpdateAnnouncementRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate or update expiry."""
    ann = (
        db.query(Announcement)
        .filter(
            Announcement.id == announcement_id,
            Announcement.company_id == current_user.company_id,
        )
        .first()
    )
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if data.is_active is not None:
        ann.is_active = data.is_active
    if data.expires_at is not None:
        ann.expires_at = datetime.fromisoformat(data.expires_at)

    db.commit()
    return {"updated": True}
