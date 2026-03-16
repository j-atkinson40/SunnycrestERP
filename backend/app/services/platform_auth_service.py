"""Authentication service for platform-level admin users."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.platform_user import PlatformUser
from app.schemas.platform_auth import PlatformLoginRequest

logger = logging.getLogger(__name__)

REALM = "platform"


def login_platform_user(
    db: Session, data: PlatformLoginRequest
) -> dict:
    """Authenticate a platform user and return JWT tokens."""
    user = (
        db.query(PlatformUser)
        .filter(PlatformUser.email == data.email)
        .first()
    )
    if not user or not verify_password(data.password, user.hashed_password):
        raise ValueError("Invalid email or password")
    if not user.is_active:
        raise ValueError("Account is deactivated")

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token_data = {"sub": user.id}
    return {
        "access_token": create_access_token(token_data, realm=REALM),
        "refresh_token": create_refresh_token(token_data, realm=REALM),
        "token_type": "bearer",
    }


def refresh_platform_tokens(db: Session, refresh_token: str) -> dict:
    """Refresh platform JWT tokens."""
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise ValueError("Invalid refresh token")

    if payload.get("type") != "refresh" or payload.get("realm") != REALM:
        raise ValueError("Invalid refresh token")

    user_id = payload.get("sub")
    user = db.query(PlatformUser).filter(PlatformUser.id == user_id).first()
    if not user or not user.is_active:
        raise ValueError("User not found or inactive")

    token_data = {"sub": user.id}
    return {
        "access_token": create_access_token(token_data, realm=REALM),
        "refresh_token": create_refresh_token(token_data, realm=REALM),
        "token_type": "bearer",
    }


def get_or_create_initial_admin(
    db: Session,
    email: str,
    password: str,
    first_name: str = "Platform",
    last_name: str = "Admin",
) -> PlatformUser:
    """Idempotent seed — creates the initial super admin if it doesn't exist."""
    existing = (
        db.query(PlatformUser).filter(PlatformUser.email == email).first()
    )
    if existing:
        return existing

    admin = PlatformUser(
        email=email,
        hashed_password=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role="super_admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Created initial platform admin: %s", email)
    return admin


def create_platform_user(
    db: Session,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: str = "support",
) -> PlatformUser:
    """Create a new platform user."""
    existing = (
        db.query(PlatformUser).filter(PlatformUser.email == email).first()
    )
    if existing:
        raise ValueError(f"Email {email} already exists")

    if role not in ("super_admin", "support", "viewer"):
        raise ValueError(f"Invalid role: {role}")

    user = PlatformUser(
        email=email,
        hashed_password=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
