"""Impersonation service — allows platform admins to act as tenant users."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import create_impersonation_token
from app.models.company import Company
from app.models.impersonation_session import ImpersonationSession
from app.models.platform_user import PlatformUser
from app.models.role import Role
from app.models.user import User

logger = logging.getLogger(__name__)


def start_impersonation(
    db: Session,
    platform_user: PlatformUser,
    tenant_id: str,
    user_id: str | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    ttl_minutes: int = 30,
) -> dict:
    """Create an impersonation session and return a short-lived tenant token.

    Args:
        db: Database session.
        platform_user: The authenticated platform admin.
        tenant_id: The tenant (company) to impersonate.
        user_id: Specific tenant user to impersonate. If ``None``,
                 the tenant's first admin user is used.
        reason: Optional reason for audit purposes.
        ip_address: Client IP for audit logging.
        ttl_minutes: Token lifetime (default 30).

    Returns:
        Dict with ``access_token``, ``session_id``, tenant/user metadata.
    """
    # Validate tenant exists
    tenant = db.query(Company).filter(Company.id == tenant_id).first()
    if not tenant:
        raise ValueError("Tenant not found")

    # Find the target user
    if user_id:
        target_user = (
            db.query(User)
            .filter(User.id == user_id, User.company_id == tenant_id, User.is_active == True)
            .first()
        )
        if not target_user:
            raise ValueError("Target user not found or inactive in this tenant")
    else:
        # Find the first admin user in the tenant
        target_user = (
            db.query(User)
            .join(Role, User.role_id == Role.id)
            .filter(
                User.company_id == tenant_id,
                User.is_active == True,
                Role.slug == "admin",
                Role.is_system == True,
            )
            .first()
        )
        if not target_user:
            raise ValueError("No active admin user found in this tenant")

    # Create the impersonation session record
    session = ImpersonationSession(
        platform_user_id=platform_user.id,
        tenant_id=tenant_id,
        impersonated_user_id=target_user.id,
        ip_address=ip_address,
        reason=reason,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Generate a short-lived impersonation token
    token = create_impersonation_token(
        {
            "sub": target_user.id,
            "company_id": tenant_id,
            "platform_user_id": platform_user.id,
            "session_id": session.id,
        },
        ttl_minutes=ttl_minutes,
    )

    logger.info(
        "Platform user %s (%s) started impersonation of user %s in tenant %s",
        platform_user.id,
        platform_user.email,
        target_user.id,
        tenant_id,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant_slug": tenant.slug if hasattr(tenant, "slug") else tenant.id,
        "tenant_name": tenant.name,
        "impersonated_user_id": target_user.id,
        "impersonated_user_name": f"{target_user.first_name} {target_user.last_name}",
        "expires_in_minutes": ttl_minutes,
        "session_id": session.id,
    }


def end_impersonation(
    db: Session,
    session_id: str,
    platform_user_id: str,
) -> ImpersonationSession:
    """End an active impersonation session.

    Args:
        db: Database session.
        session_id: The impersonation session ID.
        platform_user_id: The platform user ending the session (must match).

    Returns:
        Updated impersonation session.
    """
    session = (
        db.query(ImpersonationSession)
        .filter(
            ImpersonationSession.id == session_id,
            ImpersonationSession.platform_user_id == platform_user_id,
        )
        .first()
    )
    if not session:
        raise ValueError("Impersonation session not found")
    if session.ended_at:
        raise ValueError("Session already ended")

    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)

    logger.info(
        "Platform user %s ended impersonation session %s (%d actions)",
        platform_user_id,
        session_id,
        session.actions_performed,
    )

    return session


def list_impersonation_sessions(
    db: Session,
    *,
    platform_user_id: str | None = None,
    tenant_id: str | None = None,
    active_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List impersonation sessions with optional filters."""
    query = db.query(ImpersonationSession)

    if platform_user_id:
        query = query.filter(
            ImpersonationSession.platform_user_id == platform_user_id
        )
    if tenant_id:
        query = query.filter(ImpersonationSession.tenant_id == tenant_id)
    if active_only:
        query = query.filter(ImpersonationSession.ended_at.is_(None))

    sessions = (
        query.order_by(ImpersonationSession.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for s in sessions:
        row = {
            "id": s.id,
            "platform_user_id": s.platform_user_id,
            "platform_user_name": None,
            "tenant_id": s.tenant_id,
            "tenant_name": None,
            "impersonated_user_id": s.impersonated_user_id,
            "impersonated_user_name": None,
            "ip_address": s.ip_address,
            "actions_performed": s.actions_performed,
            "reason": s.reason,
            "started_at": s.started_at,
            "ended_at": s.ended_at,
        }
        if s.platform_user:
            row["platform_user_name"] = (
                f"{s.platform_user.first_name} {s.platform_user.last_name}"
            )
        if s.tenant:
            row["tenant_name"] = s.tenant.name
        if s.impersonated_user:
            row["impersonated_user_name"] = (
                f"{s.impersonated_user.first_name} {s.impersonated_user.last_name}"
            )
        results.append(row)

    return results
