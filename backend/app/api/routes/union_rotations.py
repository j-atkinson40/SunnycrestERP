"""Union rotation list CRUD endpoints + member management + history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_extension, require_permission
from app.models.user import User
from app.schemas.disinterment import (
    RotationListCreate,
    RotationListUpdate,
    RotationMemberReorder,
    RotationMemberToggle,
)
from app.services import union_rotation_service as svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


@router.get("")
def list_rotation_lists(
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("union_rotations.view")),
):
    """List all rotation lists for the tenant."""
    return svc.list_rotation_lists(db, current_user.company_id)


@router.post("", status_code=201)
def create_rotation_list(
    data: RotationListCreate,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("union_rotations.manage")),
):
    """Create a new rotation list."""
    lst = svc.create_rotation_list(db, current_user.company_id, data)
    return {
        "id": lst.id,
        "name": lst.name,
        "trigger_type": lst.trigger_type,
        "assignment_mode": lst.assignment_mode,
    }


@router.patch("/{list_id}")
def update_rotation_list(
    list_id: str,
    data: RotationListUpdate,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("union_rotations.manage")),
):
    """Update a rotation list."""
    lst = svc.update_rotation_list(db, list_id, current_user.company_id, data)
    return {"id": lst.id, "name": lst.name, "active": lst.active}


@router.delete("/{list_id}", status_code=204)
def delete_rotation_list(
    list_id: str,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("union_rotations.manage")),
):
    """Soft-delete a rotation list."""
    svc.soft_delete_rotation_list(db, list_id, current_user.company_id)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{list_id}/members")
def get_members(
    list_id: str,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("union_rotations.view")),
):
    """Get members of a rotation list with rotation order."""
    return svc.get_members(db, list_id, current_user.company_id)


@router.put("/{list_id}/members")
def replace_members(
    list_id: str,
    data: RotationMemberReorder,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("union_rotations.manage")),
):
    """Replace full member order (drag-drop save)."""
    return svc.replace_members(db, list_id, current_user.company_id, data.members)


@router.patch("/{list_id}/members/{member_id}")
def toggle_member(
    list_id: str,
    member_id: str,
    data: RotationMemberToggle,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("union_rotations.manage")),
):
    """Toggle a member's active/inactive status."""
    return svc.toggle_member_active(
        db, list_id, member_id, current_user.company_id, data.active
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/{list_id}/history")
def get_history(
    list_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _mod: User = Depends(require_extension("disinterment_management")),
    current_user: User = Depends(require_permission("union_rotations.view")),
):
    """Assignment history for a rotation list."""
    return svc.get_assignment_history(
        db, list_id, current_user.company_id, page, per_page
    )
