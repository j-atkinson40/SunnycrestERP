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

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    return register_user(db, data, company)


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
):
    return {
        **UserResponse.model_validate(current_user).model_dump(),
        "company": CompanyResponse.model_validate(company).model_dump(),
    }
