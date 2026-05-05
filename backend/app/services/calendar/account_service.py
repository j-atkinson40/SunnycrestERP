"""CalendarAccount service layer — Phase W-4b Layer 1 Calendar Step 1.

CRUD for ``CalendarAccount`` + ``CalendarAccountAccess`` with access
control helpers used by every endpoint that touches account-scoped
data (future inbox / send / sync routes consult ``user_has_access``
before reading or mutating).

Mirrors ``app.services.email.account_service`` shape verbatim — same
error class hierarchy, same access-rank discipline, same audit log
helper, same tenant-isolation pattern.

**Cross-tenant masking inheritance hooks** are present at every read
path for forward-compat — accounts return a ``serialized_for(user)``
shape that's a thin pass-through in Step 1 but plugs in §3.25.x
masking enforcement in subsequent steps without caller changes.

**Audit log discipline (§3.26.16.8):** every CRUD operation writes a
row to ``calendar_audit_log``. The Calendar primitive maintains its
own audit channel distinct from the general ``audit_logs`` table
because calendar events have calendar-specific shape (account_id
linkage, provider context). Subsequent steps may consolidate.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    ACCESS_LEVELS,
    ACCOUNT_TYPES,
    PROVIDER_TYPES,
    CalendarAccount,
    CalendarAccountAccess,
    CalendarAuditLog,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class CalendarAccountError(Exception):
    """Base error for calendar account operations.

    ``http_status`` is the suggested HTTP response code; route handlers
    translate via the existing convention used across the codebase.
    """

    http_status: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CalendarAccountNotFound(CalendarAccountError):
    http_status = 404


class CalendarAccountConflict(CalendarAccountError):
    http_status = 409


class CalendarAccountValidation(CalendarAccountError):
    http_status = 400


class CalendarAccountPermissionDenied(CalendarAccountError):
    http_status = 403


# ─────────────────────────────────────────────────────────────────────
# Access level rank (string → int) for access control comparisons
# ─────────────────────────────────────────────────────────────────────


_ACCESS_RANK = {"read": 1, "read_write": 2, "admin": 3}


def _rank(level: str) -> int:
    return _ACCESS_RANK.get(level, 0)


# ─────────────────────────────────────────────────────────────────────
# Audit logging helper (§3.26.16.8)
# ─────────────────────────────────────────────────────────────────────


def _audit(
    db: Session,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    changes: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CalendarAuditLog:
    """Append a row to ``calendar_audit_log``.

    Uses ``db.flush()`` (not commit) so the audit row commits atomically
    with the caller's business operation — same pattern as Email
    primitive's ``_audit`` helper + the platform-wide
    ``audit_service.log_action``.
    """
    entry = CalendarAuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    db.flush()
    return entry


# ─────────────────────────────────────────────────────────────────────
# CRUD: CalendarAccount
# ─────────────────────────────────────────────────────────────────────


def create_account(
    db: Session,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    account_type: str,
    display_name: str,
    primary_email_address: str,
    provider_type: str,
    provider_config: dict[str, Any] | None = None,
    default_event_timezone: str = "America/New_York",
    is_default: bool = False,
) -> CalendarAccount:
    """Create a new CalendarAccount.

    Validation:
      - account_type must be one of ACCOUNT_TYPES
      - provider_type must be one of PROVIDER_TYPES
      - (tenant_id, primary_email_address) unique among active accounts
      - if is_default=True, demotes any other default in the same tenant

    Side effects:
      - Audit log entry: action='account_created'.

    Per Email r63 precedent, sync_state bootstrap is **not** required at
    Step 1 because Step 2 ships sync activation; until then the
    CalendarAccount row is the entire substrate. Step 2 will add a
    ``calendar_account_sync_state`` table + bootstrap-on-create hook
    matching the Email pattern.
    """
    if account_type not in ACCOUNT_TYPES:
        raise CalendarAccountValidation(
            f"account_type must be one of {ACCOUNT_TYPES}, got {account_type!r}"
        )
    if provider_type not in PROVIDER_TYPES:
        raise CalendarAccountValidation(
            f"provider_type must be one of {PROVIDER_TYPES}, got {provider_type!r}"
        )
    if not primary_email_address or "@" not in primary_email_address:
        raise CalendarAccountValidation(
            f"primary_email_address must be a valid email, got {primary_email_address!r}"
        )

    # Uniqueness pre-check (the partial unique index also catches this).
    existing = (
        db.query(CalendarAccount)
        .filter(
            CalendarAccount.tenant_id == tenant_id,
            CalendarAccount.primary_email_address == primary_email_address,
            CalendarAccount.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise CalendarAccountConflict(
            f"An active CalendarAccount with primary_email_address "
            f"{primary_email_address!r} already exists in this tenant."
        )

    # Demote any other default if this one is_default=True.
    if is_default:
        db.query(CalendarAccount).filter(
            CalendarAccount.tenant_id == tenant_id,
            CalendarAccount.is_default.is_(True),
        ).update({"is_default": False})

    account = CalendarAccount(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        account_type=account_type,
        display_name=display_name,
        primary_email_address=primary_email_address,
        provider_type=provider_type,
        provider_config=provider_config or {},
        default_event_timezone=default_event_timezone,
        is_default=is_default,
        created_by_user_id=actor_user_id,
    )
    db.add(account)
    db.flush()

    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="account_created",
        entity_type="calendar_account",
        entity_id=account.id,
        changes={
            "account_type": account_type,
            "primary_email_address": primary_email_address,
            "provider_type": provider_type,
            "is_default": is_default,
        },
    )
    db.flush()
    return account


def get_account(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
) -> CalendarAccount:
    """Fetch a single CalendarAccount, tenant-scoped.

    Raises ``CalendarAccountNotFound`` (HTTP 404) if the account doesn't
    exist OR exists in a different tenant — existence-hiding to prevent
    cross-tenant id enumeration.
    """
    account = (
        db.query(CalendarAccount)
        .filter(
            CalendarAccount.id == account_id,
            CalendarAccount.tenant_id == tenant_id,
        )
        .first()
    )
    if not account:
        raise CalendarAccountNotFound(
            f"CalendarAccount {account_id!r} not found."
        )
    return account


def list_accounts_for_tenant(
    db: Session,
    *,
    tenant_id: str,
    include_inactive: bool = False,
) -> list[CalendarAccount]:
    """List all CalendarAccount rows in a tenant.

    Tenant admins call this; per-user filter uses
    ``list_accounts_for_user``.
    """
    query = db.query(CalendarAccount).filter(
        CalendarAccount.tenant_id == tenant_id
    )
    if not include_inactive:
        query = query.filter(CalendarAccount.is_active.is_(True))
    return query.order_by(CalendarAccount.created_at.desc()).all()


def list_accounts_for_user(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
) -> list[CalendarAccount]:
    """List accounts the user has any access to.

    Joins on ``calendar_account_access`` with ``revoked_at IS NULL``.
    Returns empty list if the user has no grants.
    """
    accounts = (
        db.query(CalendarAccount)
        .join(
            CalendarAccountAccess,
            CalendarAccountAccess.account_id == CalendarAccount.id,
        )
        .filter(
            CalendarAccount.tenant_id == tenant_id,
            CalendarAccount.is_active.is_(True),
            CalendarAccountAccess.user_id == user_id,
            CalendarAccountAccess.revoked_at.is_(None),
        )
        .order_by(CalendarAccount.created_at.desc())
        .all()
    )
    return accounts


def update_account(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
    actor_user_id: str | None,
    display_name: str | None = None,
    default_event_timezone: str | None = None,
    is_default: bool | None = None,
    is_active: bool | None = None,
    outbound_enabled: bool | None = None,
    provider_config_patch: dict[str, Any] | None = None,
) -> CalendarAccount:
    """Patch a CalendarAccount.

    Only the supplied fields are updated. Provider type + primary email
    + account type are immutable post-create — to "change provider"
    create a new account + revoke the old.

    If is_default=True is supplied, demotes any other default first.
    """
    account = get_account(db, account_id=account_id, tenant_id=tenant_id)

    changes: dict[str, Any] = {}

    if display_name is not None and display_name != account.display_name:
        changes["display_name"] = {
            "old": account.display_name,
            "new": display_name,
        }
        account.display_name = display_name

    if (
        default_event_timezone is not None
        and default_event_timezone != account.default_event_timezone
    ):
        changes["default_event_timezone"] = {
            "old": account.default_event_timezone,
            "new": default_event_timezone,
        }
        account.default_event_timezone = default_event_timezone

    if is_default is not None and is_default != account.is_default:
        if is_default:
            db.query(CalendarAccount).filter(
                CalendarAccount.tenant_id == tenant_id,
                CalendarAccount.id != account.id,
                CalendarAccount.is_default.is_(True),
            ).update({"is_default": False})
        changes["is_default"] = {
            "old": account.is_default,
            "new": is_default,
        }
        account.is_default = is_default

    if is_active is not None and is_active != account.is_active:
        changes["is_active"] = {
            "old": account.is_active,
            "new": is_active,
        }
        account.is_active = is_active

    if outbound_enabled is not None and outbound_enabled != account.outbound_enabled:
        changes["outbound_enabled"] = {
            "old": account.outbound_enabled,
            "new": outbound_enabled,
        }
        account.outbound_enabled = outbound_enabled

    if provider_config_patch:
        merged = dict(account.provider_config or {})
        merged.update(provider_config_patch)
        # Avoid logging credential keys verbatim — patch keys only.
        changes["provider_config_keys_patched"] = sorted(
            provider_config_patch.keys()
        )
        account.provider_config = merged

    if not changes:
        # No-op patch — return as-is without an audit row.
        return account

    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="account_updated",
        entity_type="calendar_account",
        entity_id=account.id,
        changes=changes,
    )
    db.flush()
    return account


def delete_account(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
    actor_user_id: str | None,
) -> None:
    """Soft-delete a CalendarAccount by setting is_active=False.

    Per Email r63 precedent: account row + its events + attendees +
    audit log all stay for audit compliance. Subsequent reads filter
    by is_active=True by default.
    """
    account = get_account(db, account_id=account_id, tenant_id=tenant_id)
    if not account.is_active:
        # Idempotent — already deleted.
        return

    account.is_active = False
    # If this was the default account, clear the flag — admin must
    # promote a replacement.
    was_default = account.is_default
    if account.is_default:
        account.is_default = False

    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="account_deleted",
        entity_type="calendar_account",
        entity_id=account.id,
        changes={"was_default": was_default},
    )
    db.flush()


# ─────────────────────────────────────────────────────────────────────
# Access scope management
# ─────────────────────────────────────────────────────────────────────


def grant_access(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
    user_id: str,
    access_level: str,
    actor_user_id: str | None,
) -> CalendarAccountAccess:
    """Grant or upgrade a user's access to a calendar account.

    If the user already has an active grant on this account, the
    existing grant is updated to the new access_level (idempotent
    upgrade-or-downgrade behavior). If not, a new grant is created.

    Returns the active grant row.
    """
    if access_level not in ACCESS_LEVELS:
        raise CalendarAccountValidation(
            f"access_level must be one of {ACCESS_LEVELS}, got {access_level!r}"
        )

    # Validate the account exists in this tenant.
    account = get_account(db, account_id=account_id, tenant_id=tenant_id)

    existing = (
        db.query(CalendarAccountAccess)
        .filter(
            CalendarAccountAccess.account_id == account.id,
            CalendarAccountAccess.user_id == user_id,
            CalendarAccountAccess.revoked_at.is_(None),
        )
        .first()
    )

    if existing:
        if existing.access_level == access_level:
            # Idempotent no-op — no audit row.
            return existing
        prev_level = existing.access_level
        existing.access_level = access_level
        db.flush()
        _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="access_updated",
            entity_type="calendar_account_access",
            entity_id=existing.id,
            changes={
                "account_id": account.id,
                "user_id": user_id,
                "access_level": {"old": prev_level, "new": access_level},
            },
        )
        db.flush()
        return existing

    grant = CalendarAccountAccess(
        id=str(uuid.uuid4()),
        account_id=account.id,
        user_id=user_id,
        tenant_id=tenant_id,
        access_level=access_level,
        granted_by_user_id=actor_user_id,
    )
    db.add(grant)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="access_granted",
        entity_type="calendar_account_access",
        entity_id=grant.id,
        changes={
            "account_id": account.id,
            "user_id": user_id,
            "access_level": access_level,
        },
    )
    db.flush()
    return grant


def revoke_access(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
    user_id: str,
    actor_user_id: str | None,
) -> bool:
    """Revoke a user's access on a calendar account.

    Soft-revoke via ``revoked_at`` timestamp. Returns True if a grant
    was revoked, False if the user had no active grant (idempotent).
    """
    # Validate the account exists in this tenant.
    get_account(db, account_id=account_id, tenant_id=tenant_id)

    grant = (
        db.query(CalendarAccountAccess)
        .filter(
            CalendarAccountAccess.account_id == account_id,
            CalendarAccountAccess.user_id == user_id,
            CalendarAccountAccess.revoked_at.is_(None),
        )
        .first()
    )
    if not grant:
        return False

    from datetime import datetime, timezone

    grant.revoked_at = datetime.now(timezone.utc)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="access_revoked",
        entity_type="calendar_account_access",
        entity_id=grant.id,
        changes={
            "account_id": account_id,
            "user_id": user_id,
            "previous_access_level": grant.access_level,
        },
    )
    db.flush()
    return True


def list_access_grants_for_account(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
    include_revoked: bool = False,
) -> list[CalendarAccountAccess]:
    """List all access grants on a calendar account."""
    # Validate the account exists in this tenant.
    get_account(db, account_id=account_id, tenant_id=tenant_id)

    query = db.query(CalendarAccountAccess).filter(
        CalendarAccountAccess.account_id == account_id
    )
    if not include_revoked:
        query = query.filter(CalendarAccountAccess.revoked_at.is_(None))
    return query.order_by(CalendarAccountAccess.granted_at.desc()).all()


# ─────────────────────────────────────────────────────────────────────
# Access control predicate
# ─────────────────────────────────────────────────────────────────────


def user_has_access(
    db: Session,
    *,
    account_id: str,
    user_id: str,
    minimum_level: str = "read",
) -> bool:
    """Return True if the user holds at least ``minimum_level`` on the
    given calendar account.

    Used by every endpoint that touches account-scoped data; future
    inbox / send / sync routes call this before reading or mutating.
    """
    grant = (
        db.query(CalendarAccountAccess)
        .filter(
            CalendarAccountAccess.account_id == account_id,
            CalendarAccountAccess.user_id == user_id,
            CalendarAccountAccess.revoked_at.is_(None),
        )
        .first()
    )
    if not grant:
        return False
    return _rank(grant.access_level) >= _rank(minimum_level)
