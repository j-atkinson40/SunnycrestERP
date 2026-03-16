"""Platform admin authentication routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.schemas.platform_auth import (
    PlatformLoginRequest,
    PlatformRefreshRequest,
    PlatformTokenResponse,
    PlatformUserResponse,
)
from app.services.platform_auth_service import (
    login_platform_user,
    refresh_platform_tokens,
)

router = APIRouter()


@router.post("/login", response_model=PlatformTokenResponse)
def platform_login(
    data: PlatformLoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate a platform admin user."""
    try:
        result = login_platform_user(db, data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return result


@router.post("/refresh", response_model=PlatformTokenResponse)
def platform_refresh(
    data: PlatformRefreshRequest,
    db: Session = Depends(get_db),
):
    """Refresh platform admin tokens."""
    try:
        result = refresh_platform_tokens(db, data.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return result


@router.get("/me", response_model=PlatformUserResponse)
def platform_me(
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Get the authenticated platform user's info."""
    return current_user
