from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import (
    create_user,
    deactivate_user,
    get_user,
    get_users,
    update_user,
)

router = APIRouter()


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = get_users(db, admin.company_id, page, per_page, search)
    return {
        "items": [UserResponse.model_validate(u) for u in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return get_user(db, user_id, admin.company_id)


@router.post("", response_model=UserResponse, status_code=201)
def create(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return create_user(db, data, admin.company_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return update_user(db, user_id, data, admin.company_id)


@router.delete("/{user_id}")
def delete(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    deactivate_user(db, user_id, admin.company_id)
    return {"detail": "User deactivated"}
