from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.password import ResetPasswordRequest
from app.schemas.role import UserPermissionOverrideRequest, UserPermissionOverridesResponse
from app.schemas.user import (
    PinResetRequest,
    PinRetrieveResponse,
    UserBulkCreate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.permission_service import get_user_permissions
from app.services.role_service import get_user_permission_overrides, set_user_permission_overrides
from app.services.user_service import (
    create_user,
    create_users_bulk,
    deactivate_user,
    get_user,
    get_user_pin,
    get_users,
    reset_user_password,
    reset_user_pin,
    suggest_username,
    update_user,
)

router = APIRouter()


def _user_to_response(user: User) -> dict:
    """Convert a User model to a response dict with role info."""
    data = UserResponse.model_validate(user).model_dump()
    if user.role_obj:
        data["role_name"] = user.role_obj.name
        data["role_slug"] = user.role_obj.slug
    # Include profile summary if loaded
    if hasattr(user, "profile") and user.profile:
        data["phone"] = user.profile.phone
        data["position"] = user.profile.position
        data["department"] = (
            user.profile.department_obj.name
            if user.profile.department_obj
            else None
        )
    return data


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view")),
):
    result = get_users(db, current_user.company_id, page, per_page, search)
    return {
        "items": [_user_to_response(u) for u in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/suggest-username")
def suggest_uname(
    first_name: str = Query(...),
    last_name: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.create")),
):
    username = suggest_username(db, first_name, last_name, current_user.company_id)
    return {"username": username}


@router.get("/{user_id}")
def read_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view")),
):
    user = get_user(db, user_id, current_user.company_id)
    return _user_to_response(user)


@router.post("/bulk", status_code=201)
def create_bulk(
    data: UserBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.create")),
):
    result = create_users_bulk(
        db, data.users, current_user.company_id, actor_id=current_user.id
    )
    return result


@router.post("", status_code=201)
def create(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.create")),
):
    user = create_user(db, data, current_user.company_id, actor_id=current_user.id)
    db.refresh(user)
    return _user_to_response(user)


@router.patch("/{user_id}")
def update(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    user = update_user(db, user_id, data, current_user.company_id, actor_id=current_user.id)
    db.refresh(user)
    return _user_to_response(user)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    reset_user_password(
        db, user_id, data.new_password, current_user.company_id, actor_id=current_user.id
    )
    return {"detail": "Password reset successfully"}


@router.delete("/{user_id}")
def delete(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.delete")),
):
    deactivate_user(db, user_id, current_user.company_id, actor_id=current_user.id)
    return {"detail": "User deactivated"}


@router.get("/{user_id}/permissions", response_model=UserPermissionOverridesResponse)
def get_user_perms(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view")),
):
    user = get_user(db, user_id, current_user.company_id)
    effective = sorted(get_user_permissions(user, db))
    overrides = get_user_permission_overrides(db, user_id)
    return {
        "effective_permissions": effective,
        "overrides": [
            {"permission_key": o.permission_key, "granted": o.granted}
            for o in overrides
        ],
    }


@router.put("/{user_id}/permissions")
def set_user_perms(
    user_id: str,
    data: list[UserPermissionOverrideRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    overrides = [{"permission_key": d.permission_key, "granted": d.granted} for d in data]
    set_user_permission_overrides(db, user_id, overrides, current_user.company_id)
    return {"detail": "Permission overrides updated"}


@router.post("/{user_id}/reset-pin")
def reset_pin(
    user_id: str,
    data: PinResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    reset_user_pin(
        db, user_id, data.new_pin, current_user.company_id, actor_id=current_user.id
    )
    return {"detail": "PIN reset successfully"}


@router.get("/{user_id}/pin", response_model=PinRetrieveResponse)
def retrieve_pin(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    pin = get_user_pin(db, user_id, current_user.company_id)
    return {"pin": pin}
