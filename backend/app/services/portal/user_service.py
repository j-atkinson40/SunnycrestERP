"""Portal user service — Workflow Arc Phase 8e.2.

Admin-driven CRUD for portal users + driver-resolution helper.

Scope for Phase 8e.2 — minimum viable:
  - `invite_portal_user` (admin invites a driver; generates invite
    token, emails the user via D-7, stores `invited_by_user_id`)
  - `resolve_driver_for_portal_user` (portal endpoint helper — maps
    portal_user.id → Driver row via the drivers.portal_user_id FK)

Full admin UI + list/edit/deactivate/reset-password/unlock endpoints
ship in Phase 8e.2.1 alongside the /settings/portal-users page.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.driver import Driver
from app.models.portal_user import PortalUser
from app.models.user import User


def invite_portal_user(
    db: Session,
    *,
    company: Company,
    inviter: User,
    email: str,
    first_name: str,
    last_name: str,
    assigned_space_id: str | None,
    invite_ttl_hours: int = 72,
) -> tuple[PortalUser, str]:
    """Create a portal user in invited state. Returns (user,
    invite_token). Caller is responsible for emailing the token.

    The user is created with `hashed_password=None` — they set it
    via the invite link's first-password-set flow (which uses the
    recovery-token mechanism for convenience; Phase 8e.2.1 can
    split the two token types if needed).

    Raises ValueError on duplicate email within the company.
    """
    # Normalize + dedupe check.
    email_clean = email.lower().strip()
    existing = (
        db.query(PortalUser)
        .filter(
            PortalUser.company_id == company.id,
            PortalUser.email == email_clean,
        )
        .first()
    )
    if existing is not None:
        raise ValueError(
            f"A portal user with email {email!r} already exists for "
            f"this tenant."
        )

    invite_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    portal_user = PortalUser(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email=email_clean,
        hashed_password=None,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        assigned_space_id=assigned_space_id,
        is_active=True,
        invited_by_user_id=inviter.id,
        # Use recovery_token here since invite and first-password-set
        # share the same flow in 8e.2. Phase 8e.2.1 may split.
        recovery_token=invite_token,
        recovery_token_expires_at=now + timedelta(hours=invite_ttl_hours),
    )
    db.add(portal_user)
    db.commit()
    db.refresh(portal_user)
    return portal_user, invite_token


def resolve_driver_for_portal_user(
    db: Session, *, portal_user: PortalUser
) -> Driver | None:
    """Given a portal user, find the Driver row that maps to them
    via `drivers.portal_user_id`. Returns None if no driver row
    links to this portal user yet (admin hasn't wired them up).

    Tenant-scoped defense-in-depth: also filters on company_id even
    though portal_user.company_id is already trusted.
    """
    return (
        db.query(Driver)
        .filter(
            Driver.portal_user_id == portal_user.id,
            Driver.company_id == portal_user.company_id,
            Driver.active.is_(True),
        )
        .first()
    )
