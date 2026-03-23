"""Announcement API routes.

Endpoints for creating, listing, reading, and dismissing company announcements.
Includes safety notice endpoints for acknowledgment tracking and compliance.
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
    content_type: str = "announcement"  # announcement, note, safety_notice
    target_type: str = "everyone"
    target_value: str | None = None
    target_employee_ids: list[str] | None = None
    pin_to_top: bool = False
    expires_at: datetime | None = None
    # Safety notice fields
    safety_category: str | None = None
    requires_acknowledgment: bool = False
    is_compliance_relevant: bool = False
    document_url: str | None = None
    document_filename: str | None = None
    linked_equipment_id: str | None = None
    linked_incident_id: str | None = None
    linked_training_id: str | None = None
    acknowledgment_deadline: datetime | None = None


class AnnouncementOut(BaseModel):
    id: str
    title: str
    body: str | None = None
    priority: str
    content_type: str = "announcement"
    pin_to_top: bool = False
    created_at: str | None = None
    expires_at: str | None = None
    created_by_name: str | None = None
    is_read: bool = False
    is_dismissed: bool = False
    # Safety notice fields
    safety_category: str | None = None
    requires_acknowledgment: bool = False
    is_compliance_relevant: bool = False
    document_url: str | None = None
    document_filename: str | None = None
    acknowledgment_deadline: str | None = None
    is_acknowledged: bool = False


class AnnouncementManageOut(BaseModel):
    id: str
    title: str
    body: str | None = None
    priority: str
    content_type: str = "announcement"
    target_type: str
    target_value: str | None = None
    target_employee_ids: list[str] | None = None
    pin_to_top: bool = False
    is_active: bool = True
    expires_at: str | None = None
    created_at: str | None = None
    created_by_name: str | None = None
    safety_category: str | None = None
    requires_acknowledgment: bool = False
    is_compliance_relevant: bool = False
    document_url: str | None = None
    document_filename: str | None = None
    acknowledgment_deadline: str | None = None


class AnnouncementPermissionOut(BaseModel):
    can_create: bool
    can_mark_compliance: bool = False


class AcknowledgeRequest(BaseModel):
    note: str | None = None


class SafetyNoticeDetailOut(BaseModel):
    notice_id: str
    title: str
    safety_category: str | None = None
    total_targeted: int
    acknowledged_count: int
    employees: list[dict]


class ComplianceImpactOut(BaseModel):
    score_impact: float
    gaps: list[dict]


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


@router.post("/{announcement_id}/acknowledge")
def acknowledge(
    announcement_id: str,
    body: AcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge a safety notice."""
    from app.services.announcement_service import acknowledge_safety_notice
    acknowledge_safety_notice(db, current_user.id, announcement_id, body.note)
    return {"status": "ok"}


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
    from app.models.employee_profile import EmployeeProfile
    from app.services.functional_area_service import get_active_areas_for_employee, get_areas_for_tenant

    can_create = can_user_create_announcements(db, current_user)
    can_compliance = False
    if can_create:
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()
        areas = (profile.functional_areas or []) if profile else []
        try:
            tenant_areas = get_areas_for_tenant(db, current_user.company_id)
        except Exception:
            tenant_areas = []
        active = get_active_areas_for_employee(areas, tenant_areas) if areas else []
        # Admin role check
        from app.models.role import Role
        role = db.query(Role).filter(Role.id == current_user.role_id).first()
        is_admin = bool(role and role.is_system and role.slug == "admin")
        can_compliance = is_admin or "safety_compliance" in active or "full_admin" in active

    return AnnouncementPermissionOut(can_create=can_create, can_mark_compliance=can_compliance)


@router.get("/safety-notices", response_model=list[AnnouncementManageOut])
def list_safety_notices(
    category: str | None = None,
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List safety notices for the safety module view."""
    from app.services.announcement_service import get_safety_notices
    notices = get_safety_notices(db, current_user.company_id, category, status_filter)
    results = []
    for ann in notices:
        results.append(AnnouncementManageOut(
            id=ann.id, title=ann.title, body=ann.body, priority=ann.priority,
            content_type=ann.content_type, target_type=ann.target_type,
            target_value=ann.target_value, target_employee_ids=ann.target_employee_ids,
            pin_to_top=ann.pin_to_top, is_active=ann.is_active,
            expires_at=ann.expires_at.isoformat() if ann.expires_at else None,
            created_at=ann.created_at.isoformat() if ann.created_at else None,
            created_by_name=(f"{ann.created_by.first_name} {ann.created_by.last_name}" if ann.created_by else "Unknown"),
            safety_category=ann.safety_category,
            requires_acknowledgment=ann.requires_acknowledgment,
            is_compliance_relevant=ann.is_compliance_relevant,
            document_url=ann.document_url, document_filename=ann.document_filename,
            acknowledgment_deadline=ann.acknowledgment_deadline.isoformat() if ann.acknowledgment_deadline else None,
        ))
    return results


@router.get("/safety-notices/{announcement_id}/status", response_model=SafetyNoticeDetailOut)
def get_notice_status(
    announcement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed acknowledgment status for a safety notice."""
    from app.services.announcement_service import get_notice_acknowledgment_status
    result = get_notice_acknowledgment_status(db, announcement_id, current_user.company_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail="Notice not found")
    return SafetyNoticeDetailOut(**result)


@router.get("/compliance-impact", response_model=ComplianceImpactOut)
def get_compliance_impact(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get safety notice compliance score impact."""
    from app.services.announcement_service import get_safety_notice_compliance_impact
    result = get_safety_notice_compliance_impact(db, current_user.company_id)
    return ComplianceImpactOut(**result)


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
            content_type=ann.content_type,
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
            safety_category=ann.safety_category,
            requires_acknowledgment=ann.requires_acknowledgment,
            is_compliance_relevant=ann.is_compliance_relevant,
            document_url=ann.document_url,
            document_filename=ann.document_filename,
            acknowledgment_deadline=ann.acknowledgment_deadline.isoformat() if ann.acknowledgment_deadline else None,
        ))
    return results


@router.post("/", response_model=AnnouncementManageOut, status_code=status.HTTP_201_CREATED)
def create_new_announcement(
    body: AnnouncementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new company announcement or safety notice."""
    if not can_user_create_announcements(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission",
        )

    if body.content_type not in ("announcement", "note", "safety_notice"):
        raise HTTPException(status_code=400, detail="Invalid content_type")
    if body.priority not in ("info", "warning", "critical"):
        raise HTTPException(status_code=400, detail="Invalid priority")
    if body.target_type not in ("everyone", "functional_area", "employee_type", "specific_employees"):
        raise HTTPException(status_code=400, detail="Invalid target_type")

    # Validate safety notice specific fields
    valid_categories = ("procedure", "equipment_alert", "osha_reminder", "incident_followup", "training_assignment", "toolbox_talk")
    if body.content_type == "safety_notice":
        if body.safety_category and body.safety_category not in valid_categories:
            raise HTTPException(status_code=400, detail="Invalid safety_category")

    ann = create_announcement(
        db=db, user=current_user, title=body.title, body=body.body,
        priority=body.priority, content_type=body.content_type,
        target_type=body.target_type, target_value=body.target_value,
        target_employee_ids=body.target_employee_ids, pin_to_top=body.pin_to_top,
        expires_at=body.expires_at, safety_category=body.safety_category,
        requires_acknowledgment=body.requires_acknowledgment,
        is_compliance_relevant=body.is_compliance_relevant,
        document_url=body.document_url, document_filename=body.document_filename,
        linked_equipment_id=body.linked_equipment_id,
        linked_incident_id=body.linked_incident_id,
        linked_training_id=body.linked_training_id,
        acknowledgment_deadline=body.acknowledgment_deadline,
    )

    return AnnouncementManageOut(
        id=ann.id, title=ann.title, body=ann.body, priority=ann.priority,
        content_type=ann.content_type, target_type=ann.target_type,
        target_value=ann.target_value, target_employee_ids=ann.target_employee_ids,
        pin_to_top=ann.pin_to_top, is_active=ann.is_active,
        expires_at=ann.expires_at.isoformat() if ann.expires_at else None,
        created_at=ann.created_at.isoformat() if ann.created_at else None,
        created_by_name=f"{current_user.first_name} {current_user.last_name}",
        safety_category=ann.safety_category,
        requires_acknowledgment=ann.requires_acknowledgment,
        is_compliance_relevant=ann.is_compliance_relevant,
        document_url=ann.document_url, document_filename=ann.document_filename,
        acknowledgment_deadline=ann.acknowledgment_deadline.isoformat() if ann.acknowledgment_deadline else None,
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
