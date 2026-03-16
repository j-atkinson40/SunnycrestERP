"""Platform admin — manage platform users."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.schemas.platform_auth import (
    PlatformUserCreate,
    PlatformUserResponse,
    PlatformUserUpdate,
)
from app.services.platform_auth_service import create_platform_user

router = APIRouter()


@router.get("/", response_model=list[PlatformUserResponse])
def list_platform_users(
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """List all platform users."""
    return db.query(PlatformUser).order_by(PlatformUser.email).all()


@router.post("/", response_model=PlatformUserResponse, status_code=201)
def create_user(
    data: PlatformUserCreate,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Create a new platform user."""
    try:
        user = create_platform_user(
            db,
            email=data.email,
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
            role=data.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return user


@router.patch("/{user_id}", response_model=PlatformUserResponse)
def update_user(
    user_id: str,
    data: PlatformUserUpdate,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Update a platform user's details."""
    user = db.query(PlatformUser).filter(PlatformUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    if "role" in update_data and update_data["role"] not in (
        "super_admin",
        "support",
        "viewer",
    ):
        raise HTTPException(status_code=400, detail="Invalid role")

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user
