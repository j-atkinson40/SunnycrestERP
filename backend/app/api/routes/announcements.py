"""Announcement API routes.

Endpoints for creating, listing, reading, and dismissing company announcements.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.announcement_service import (
    can_user_create_announcements,
    create_announcement,
    deactivate_announcement,
    dismiss_announcement,
    get_announcements_for_employee,
    get_company_announcements,
    mark_announcement_read,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AnnouncementCreate(BaseModel):
    title: str
    body: str | None = None
    priority: str = "info"
    target_type: str = "everyone"
    target_value: str | None = None
    target_employee_ids: list[str] | None = None
    pin_to_top: bool = False
    expires_at: datetime | None = None


class AnnouncementOut(BaseModel):
    id: str
    title: str
    body: str | None = None
    priority: str
    pin_to_top: bool = False
    created_at: str | None = None
    expires_at: str | None = None
    created_by_name: str | None = None
    is_read: bool = False
    is_dismissed: bool = False


class AnnouncementManageOut(BaseModel):
    id: str
    title: str
    body: str | None = None
    priority: str
    target_type: str
    target_value: str | None = None
    target_employee_ids: list[str] | None = None
    pin_to_top: bool = False
    is_active: bool = True
    expires_at: str | None = None
    created_at: str | None = None
    created_by_name: str | None = None


class AnnouncementPermissionOut(BaseModel):
    can_create: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/my", response_model=list[AnnouncementOut])
def get_my_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get announcements targeted at the current employee (for briefing card)."""
    items = get_announcements_for_employee(db, current_user)
    return [AnnouncementOut(**item) for item in items]


@router.post("/{announcement_id}/read")
def mark_read(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an announcement as read."""
    mark_announcement_read(db, current_user.id, announcement_id)
    return {"status": "ok"}


@router.post("/{announcement_id}/dismiss")
def dismiss(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss an announcement from the briefing card."""
    dismiss_announcement(db, current_user.id, announcement_id)
    return {"status": "ok"}


@router.get("/permissions", response_model=AnnouncementPermissionOut)
def get_announcement_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if current user can create announcements."""
    return AnnouncementPermissionOut(
        can_create=can_user_create_announcements(db, current_user)
    )


@router.get("/", response_model=list[AnnouncementManageOut])
def list_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all announcements for the company (management view)."""
    if not can_user_create_announcements(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage announcements",
        )
    announcements = get_company_announcements(db, current_user.company_id, include_inactive=True)
    results = []
    for ann in announcements:
        results.append(AnnouncementManageOut(
            id=ann.id,
            title=ann.title,
            body=ann.body,
            priority=ann.priority,
            target_type=ann.target_type,
            target_value=ann.target_value,
            target_employee_ids=ann.target_employee_ids,
            pin_to_top=ann.pin_to_top,
            is_active=ann.is_active,
            expires_at=ann.expires_at.isoformat() if ann.expires_at else None,
            created_at=ann.created_at.isoformat() if ann.created_at else None,
            created_by_name=(
                f"{ann.created_by.first_name} {ann.created_by.last_name}"
                if ann.created_by else "Unknown"
            ),
        ))
    return results


@router.post("/", response_model=AnnouncementManageOut, status_code=status.HTTP_201_CREATED)
def create_new_announcement(
    body: AnnouncementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new company announcement."""
    if not can_user_create_announcements(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create announcements",
        )

    # Validate
    if body.priority not in ("info", "warning", "critical"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Priority must be info, warning, or critical",
        )
    if body.target_type not in ("everyone", "functional_area", "employee_type", "specific_employees"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid target_type",
        )

    ann = create_announcement(
        db=db,
        user=current_user,
        title=body.title,
        body=body.body,
        priority=body.priority,
        target_type=body.target_type,
        target_value=body.target_value,
        target_employee_ids=body.target_employee_ids,
        pin_to_top=body.pin_to_top,
        expires_at=body.expires_at,
    )

    return AnnouncementManageOut(
        id=ann.id,
        title=ann.title,
        body=ann.body,
        priority=ann.priority,
        target_type=ann.target_type,
        target_value=ann.target_value,
        target_employee_ids=ann.target_employee_ids,
        pin_to_top=ann.pin_to_top,
        is_active=ann.is_active,
        expires_at=ann.expires_at.isoformat() if ann.expires_at else None,
        created_at=ann.created_at.isoformat() if ann.created_at else None,
        created_by_name=f"{current_user.first_name} {current_user.last_name}",
    )


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate (soft-delete) an announcement."""
    if not can_user_create_announcements(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage announcements",
        )

    success = deactivate_announcement(db, announcement_id, current_user.company_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found",
        )
    return {"status": "ok"}
