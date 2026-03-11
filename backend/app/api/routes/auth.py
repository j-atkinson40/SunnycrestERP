from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.company import CompanyResponse
from app.schemas.user import UserResponse
from app.services.auth_service import login_user, refresh_tokens, register_user
from app.services.permission_service import get_user_permissions

router = APIRouter()


def _user_to_response(user: User) -> dict:
    """Convert a User model to a response dict with role info."""
    data = UserResponse.model_validate(user).model_dump()
    if user.role_obj:
        data["role_name"] = user.role_obj.name
        data["role_slug"] = user.role_obj.slug
    return data


@router.post("/register", status_code=201)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    user = register_user(db, data, company)
    # Eagerly load the role_obj for the response
    db.refresh(user)
    return _user_to_response(user)


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    return login_user(db, data, company)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    data: RefreshRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    return refresh_tokens(db, data.refresh_token, company)


@router.get("/me")
def me(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    permissions = sorted(get_user_permissions(current_user, db))
    user_data = _user_to_response(current_user)
    return {
        **user_data,
        "permissions": permissions,
        "company": CompanyResponse.model_validate(company).model_dump(),
    }
