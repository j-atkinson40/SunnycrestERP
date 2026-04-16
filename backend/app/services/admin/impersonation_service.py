"""Admin impersonation service — generates scoped impersonation tokens and logs sessions."""

from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.admin_impersonation_session import AdminImpersonationSession
from app.models.company import Company
from app.models.platform_user import PlatformUser
from app.models.user import User


IMPERSONATION_TOKEN_MINUTES = 60


def start_impersonation(
    db: Session,
    admin: PlatformUser,
    tenant_id: str,
    impersonated_user_id: str,
    reason: str | None = None,
    source_ip: str | None = None,
    environment: str = "production",
) -> dict:
    """Create impersonation session + scoped token. Tenant user is not notified."""
    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        raise ValueError("Tenant not found")

    user = (
        db.query(User)
        .filter(User.id == impersonated_user_id, User.company_id == tenant_id)
        .first()
    )
    if not user:
        raise ValueError("Target user does not belong to tenant")

    session = AdminImpersonationSession(
        admin_user_id=admin.id,
        tenant_id=tenant_id,
        impersonated_user_id=impersonated_user_id,
        reason=reason,
        source_ip=source_ip,
        environment=environment,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Issue a tenant-realm token marked as impersonation.
    # Tenant endpoints accept it; the impersonation marker allows UI banners.
    expires = datetime.now(timezone.utc) + timedelta(minutes=IMPERSONATION_TOKEN_MINUTES)
    payload = {
        "sub": user.id,
        "company_id": company.id,
        "type": "access",
        "realm": "tenant",
        "exp": expires,
        "impersonation": True,
        "impersonation_session_id": session.id,
        "admin_user_id": admin.id,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return {
        "session_id": session.id,
        "token": token,
        "tenant_slug": company.slug,
        "company_name": company.name,
        "impersonated_user_email": user.email,
        "expires_at": expires.isoformat(),
    }


def end_impersonation(db: Session, session_id: str, admin: PlatformUser) -> AdminImpersonationSession:
    session = (
        db.query(AdminImpersonationSession)
        .filter(
            AdminImpersonationSession.id == session_id,
            AdminImpersonationSession.admin_user_id == admin.id,
            AdminImpersonationSession.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not session:
        raise ValueError("Active impersonation session not found")
    session.ended_at = datetime.now(timezone.utc)
    session.is_active = False
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, limit: int = 50) -> list[AdminImpersonationSession]:
    return (
        db.query(AdminImpersonationSession)
        .order_by(AdminImpersonationSession.started_at.desc())
        .limit(limit)
        .all()
    )
