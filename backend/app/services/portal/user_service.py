"""Portal user service — Workflow Arcs 8e.2 + 8e.2.1.

Admin-driven CRUD for portal users + driver-resolution helper.

Phase 8e.2 scope (shipped):
  - `invite_portal_user` (admin invites; generates invite token;
    optionally auto-creates Driver row when invited into a driver
    space — see `_is_driver_space_template`)
  - `resolve_driver_for_portal_user` (portal endpoint helper —
    maps portal_user.id → Driver row via drivers.portal_user_id FK)

Phase 8e.2.1 additions:
  - `list_portal_users_for_tenant` with status filter (active,
    pending, locked, inactive)
  - `update_portal_user_profile` (edit name/email/space)
  - `deactivate_portal_user` / `reactivate_portal_user`
  - `unlock_portal_user` (clears locked_until + failed_login_count)
  - `issue_admin_reset_password` (admin-driven token issue)
  - `resend_invite` (re-issue invite token when still pending)
  - Auto-create Driver row on invite into a driver space
  - Separate invite email template (email.portal_invite) distinct
    from password recovery template
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.driver import Driver
from app.models.portal_user import PortalUser
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Auto-create-Driver helper ────────────────────────────────────────
#
# Per Phase 8e.2.1 audit (Q5): auto-create a Driver row ONLY when
# the invited portal user is assigned to a known DRIVER space
# template. Currently the only driver-shaped template ships as
# ("manufacturing", "driver") with `template_id="driver_portal"`.
# Future yard_operator + removal_staff portals won't match this
# predicate and won't get spurious Driver rows.


def _is_driver_space_template(
    db: Session, *, company: Company, space_id: str | None
) -> bool:
    """Return True iff the assigned_space_id matches a space
    seeded from a driver template for the tenant's vertical."""
    if not space_id:
        return False
    # Look up the tenant admin's spaces JSONB to find the space by id.
    from sqlalchemy.orm.attributes import flag_modified  # noqa: F401 (referenced in sibling fns)

    from app.services.spaces import registry as space_reg

    # Scan any tenant user's preferences for the space; pin_types
    # aren't relevant — we care about the space NAME matching a
    # known driver template name.
    users = (
        db.query(User)
        .filter(User.company_id == company.id, User.is_active.is_(True))
        .all()
    )
    for u in users:
        for sp in (u.preferences or {}).get("spaces", []) or []:
            if sp.get("space_id") != space_id:
                continue
            name_lower = (sp.get("name") or "").strip().lower()
            # Driver space template's name is "Driver". Any future
            # operational portal space that should auto-create a
            # Driver row would need explicit registry flagging;
            # today we conservatively match on the literal "driver"
            # space name.
            if name_lower == "driver":
                return True
            return False
    return False


def _maybe_auto_create_driver_row(
    db: Session,
    *,
    company: Company,
    portal_user: PortalUser,
) -> Driver | None:
    """If the portal user is assigned to a driver space, create a
    Driver row linked to them. No-op otherwise. Idempotent: skips
    creation if a Driver already exists with this portal_user_id.
    """
    if not _is_driver_space_template(
        db, company=company, space_id=portal_user.assigned_space_id
    ):
        return None
    existing = (
        db.query(Driver)
        .filter(
            Driver.company_id == company.id,
            Driver.portal_user_id == portal_user.id,
        )
        .first()
    )
    if existing is not None:
        return existing
    driver = Driver(
        id=str(uuid.uuid4()),
        company_id=company.id,
        employee_id=None,  # canonical portal-era: no tenant-user link
        portal_user_id=portal_user.id,
        active=True,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


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
        # Phase 8e.2.1 — invite and recovery still share the same
        # token column (reuse recovery_token for the first-password-
        # set flow). The email template differs (portal_invite vs.
        # portal_password_recovery) but the token plumbing is one
        # field. Consolidation into a single "pending_token" is
        # deferred to post-arc polish.
        recovery_token=invite_token,
        recovery_token_expires_at=now + timedelta(hours=invite_ttl_hours),
    )
    db.add(portal_user)
    db.commit()
    db.refresh(portal_user)

    # Phase 8e.2.1 — auto-create Driver row when invited into a
    # driver space (Q5 audit approval). No-op for other portal
    # spaces. Idempotent.
    _maybe_auto_create_driver_row(
        db, company=company, portal_user=portal_user
    )

    return portal_user, invite_token


# ── Phase 8e.2.1 admin CRUD ─────────────────────────────────────────


PortalUserStatus = Literal["active", "pending", "locked", "inactive"]


@dataclass(frozen=True)
class PortalUserSummary:
    """Flattened shape for the admin list view. Includes derived
    status field + resolved driver_id (if linked)."""

    id: str
    company_id: str
    email: str
    first_name: str
    last_name: str
    assigned_space_id: str | None
    assigned_space_name: str | None
    status: PortalUserStatus
    last_login_at: datetime | None
    driver_id: str | None
    created_at: datetime


def _derive_status(
    portal_user: PortalUser, now: datetime | None = None
) -> PortalUserStatus:
    now = now or datetime.now(timezone.utc)
    if not portal_user.is_active:
        return "inactive"
    if portal_user.locked_until is not None and portal_user.locked_until > now:
        return "locked"
    if portal_user.hashed_password is None:
        return "pending"
    return "active"


def _resolve_space_name(
    db: Session, *, company: Company, space_id: str | None
) -> str | None:
    if not space_id:
        return None
    users = (
        db.query(User)
        .filter(User.company_id == company.id, User.is_active.is_(True))
        .all()
    )
    for u in users:
        for sp in (u.preferences or {}).get("spaces", []) or []:
            if sp.get("space_id") == space_id:
                return sp.get("name")
    return None


def list_portal_users_for_tenant(
    db: Session,
    *,
    company: Company,
    status_filter: PortalUserStatus | None = None,
    space_filter: str | None = None,
) -> list[PortalUserSummary]:
    """List portal users scoped to a tenant with optional status +
    space filters. Admin view."""
    rows = (
        db.query(PortalUser)
        .filter(PortalUser.company_id == company.id)
        .order_by(PortalUser.created_at.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    summaries: list[PortalUserSummary] = []
    for pu in rows:
        status = _derive_status(pu, now)
        if status_filter and status != status_filter:
            continue
        if space_filter and pu.assigned_space_id != space_filter:
            continue
        # Resolve driver link (at most one active driver per portal user).
        driver = (
            db.query(Driver.id)
            .filter(
                Driver.portal_user_id == pu.id,
                Driver.company_id == company.id,
                Driver.active.is_(True),
            )
            .first()
        )
        summaries.append(
            PortalUserSummary(
                id=pu.id,
                company_id=pu.company_id,
                email=pu.email,
                first_name=pu.first_name,
                last_name=pu.last_name,
                assigned_space_id=pu.assigned_space_id,
                assigned_space_name=_resolve_space_name(
                    db, company=company, space_id=pu.assigned_space_id
                ),
                status=status,
                last_login_at=pu.last_login_at,
                driver_id=driver[0] if driver else None,
                created_at=pu.created_at,
            )
        )
    return summaries


def update_portal_user_profile(
    db: Session,
    *,
    company: Company,
    portal_user_id: str,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    assigned_space_id: str | None = None,
) -> PortalUser:
    """Admin edit — name, email, assigned space. Tenant-scoped."""
    pu = (
        db.query(PortalUser)
        .filter(
            PortalUser.id == portal_user_id,
            PortalUser.company_id == company.id,
        )
        .first()
    )
    if pu is None:
        raise ValueError(f"Portal user {portal_user_id} not found")
    if first_name is not None:
        pu.first_name = first_name.strip()
    if last_name is not None:
        pu.last_name = last_name.strip()
    if email is not None:
        email_clean = email.lower().strip()
        # Check collision.
        conflict = (
            db.query(PortalUser)
            .filter(
                PortalUser.company_id == company.id,
                PortalUser.email == email_clean,
                PortalUser.id != pu.id,
            )
            .first()
        )
        if conflict is not None:
            raise ValueError(
                f"Another portal user with email {email_clean!r} exists."
            )
        pu.email = email_clean
    if assigned_space_id is not None:
        pu.assigned_space_id = assigned_space_id
    db.commit()
    db.refresh(pu)
    return pu


def deactivate_portal_user(
    db: Session, *, company: Company, portal_user_id: str
) -> PortalUser:
    pu = _get_portal_user_for_tenant(db, company=company, portal_user_id=portal_user_id)
    pu.is_active = False
    db.commit()
    db.refresh(pu)
    return pu


def reactivate_portal_user(
    db: Session, *, company: Company, portal_user_id: str
) -> PortalUser:
    pu = _get_portal_user_for_tenant(db, company=company, portal_user_id=portal_user_id)
    pu.is_active = True
    db.commit()
    db.refresh(pu)
    return pu


def unlock_portal_user(
    db: Session, *, company: Company, portal_user_id: str
) -> PortalUser:
    """Clear lockout + reset failed-login counter."""
    pu = _get_portal_user_for_tenant(db, company=company, portal_user_id=portal_user_id)
    pu.locked_until = None
    pu.failed_login_count = 0
    db.commit()
    db.refresh(pu)
    return pu


def issue_admin_reset_password(
    db: Session, *, company: Company, portal_user_id: str
) -> tuple[PortalUser, str]:
    """Admin-driven password reset — issues a recovery token.
    Returns (user, token); caller is responsible for emailing."""
    from app.services.portal.auth import issue_recovery_token

    pu = _get_portal_user_for_tenant(db, company=company, portal_user_id=portal_user_id)
    token = issue_recovery_token(db, user=pu)
    return pu, token


def resend_invite(
    db: Session,
    *,
    company: Company,
    portal_user_id: str,
    invite_ttl_hours: int = 72,
) -> tuple[PortalUser, str]:
    """Re-issue the invite token for a portal user still in pending
    state (hashed_password is None). Returns (user, new_token)."""
    pu = _get_portal_user_for_tenant(db, company=company, portal_user_id=portal_user_id)
    if pu.hashed_password is not None:
        raise ValueError(
            "Portal user has already set a password; use reset-password instead."
        )
    token = secrets.token_urlsafe(32)
    pu.recovery_token = token
    pu.recovery_token_expires_at = datetime.now(timezone.utc) + timedelta(
        hours=invite_ttl_hours
    )
    db.commit()
    db.refresh(pu)
    return pu, token


def _get_portal_user_for_tenant(
    db: Session, *, company: Company, portal_user_id: str
) -> PortalUser:
    pu = (
        db.query(PortalUser)
        .filter(
            PortalUser.id == portal_user_id,
            PortalUser.company_id == company.id,
        )
        .first()
    )
    if pu is None:
        raise ValueError(f"Portal user {portal_user_id} not found")
    return pu


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
