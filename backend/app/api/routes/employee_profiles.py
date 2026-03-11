from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.employee_profile import EmployeeProfile
from app.models.user import User
from app.schemas.employee_profile import (
    EmployeeProfileAdminUpdate,
    EmployeeProfileResponse,
    EmployeeProfileUpdate,
)
from app.services import employee_profile_service
from app.services.permission_service import user_has_permission
from app.services.user_service import get_user

router = APIRouter()


def _profile_to_response(profile: EmployeeProfile) -> dict:
    """Convert profile model to response dict, resolving department_name."""
    data = EmployeeProfileResponse.model_validate(profile).model_dump()
    data["department_name"] = (
        profile.department_obj.name if profile.department_obj else None
    )
    return data


# --- Self-access routes (any authenticated user) ---


@router.get("/me")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any authenticated user can view their own profile."""
    profile = employee_profile_service.get_or_create_profile(db, current_user.id)
    response = _profile_to_response(profile)
    # Strip notes if user doesn't have view_notes permission
    if not user_has_permission(current_user, db, "employees.view_notes"):
        response.pop("notes", None)
    return response


@router.patch("/me")
def update_my_profile(
    data: EmployeeProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any authenticated user can edit their own basic profile fields."""
    profile = employee_profile_service.update_profile(
        db,
        current_user.id,
        data,
        actor_id=current_user.id,
        company_id=current_user.company_id,
    )
    response = _profile_to_response(profile)
    if not user_has_permission(current_user, db, "employees.view_notes"):
        response.pop("notes", None)
    return response


# --- Admin routes (requires employees.view / employees.edit) ---


@router.get("/{user_id}")
def get_employee_profile(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view")),
):
    """View any employee's profile (requires employees.view permission)."""
    # Verify user belongs to same company
    target_user = get_user(db, user_id, current_user.company_id)
    profile = employee_profile_service.get_or_create_profile(db, target_user.id)
    response = _profile_to_response(profile)
    if not user_has_permission(current_user, db, "employees.view_notes"):
        response.pop("notes", None)
    return response


@router.patch("/{user_id}")
def update_employee_profile(
    user_id: str,
    data: EmployeeProfileAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    """Edit any employee's profile (requires employees.edit permission)."""
    target_user = get_user(db, user_id, current_user.company_id)
    profile = employee_profile_service.update_profile(
        db,
        target_user.id,
        data,
        actor_id=current_user.id,
        company_id=current_user.company_id,
    )
    return _profile_to_response(profile)
