from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.company import CompanyRegisterRequest


def register_company(db: Session, data: CompanyRegisterRequest) -> dict:
    """Register a new company and its first admin user."""
    existing_company = (
        db.query(Company).filter(Company.slug == data.company_slug).first()
    )
    if existing_company:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company slug already taken",
        )

    company = Company(name=data.company_name, slug=data.company_slug)
    db.add(company)
    db.flush()

    existing_user = (
        db.query(User)
        .filter(User.email == data.email, User.company_id == company.id)
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=Role.ADMIN,
        company_id=company.id,
    )
    db.add(user)
    db.commit()
    db.refresh(company)
    db.refresh(user)

    return {"company": company, "user": user}


def register_user(db: Session, data: RegisterRequest, company: Company) -> User:
    """Register a user within an existing company."""
    existing = (
        db.query(User)
        .filter(User.email == data.email, User.company_id == company.id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered in this company",
        )

    # First user in this company becomes admin
    company_user_count = (
        db.query(User).filter(User.company_id == company.id).count()
    )
    role = Role.ADMIN if company_user_count == 0 else Role.EMPLOYEE

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=role,
        company_id=company.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, data: LoginRequest, company: Company) -> TokenResponse:
    """Login scoped to a specific company."""
    user = (
        db.query(User)
        .filter(User.email == data.email, User.company_id == company.id)
        .first()
    )
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token_data = {"sub": user.id, "company_id": company.id}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


def refresh_tokens(
    db: Session, refresh_token: str, company: Company
) -> TokenResponse:
    """Refresh tokens scoped to a specific company."""
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = payload.get("sub")
        token_company_id = payload.get("company_id")
        if not user_id or token_company_id != company.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == company.id)
        .first()
    )
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    token_data = {"sub": user.id, "company_id": company.id}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
