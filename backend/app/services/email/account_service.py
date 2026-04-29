"""EmailAccount service layer — Phase W-4b Layer 1 Step 1.

CRUD for ``EmailAccount`` + ``EmailAccountAccess`` with access control
helpers used by every endpoint that touches account-scoped data
(future inbox / send / sync routes consult ``user_has_access`` before
reading or mutating).

**Cross-tenant masking inheritance hooks** are present at every read
path for forward-compat — accounts return a ``serialized_for(user)``
shape that's a thin pass-through in Step 1 but plugs in the §3.25.x
masking enforcement in subsequent steps without caller changes.

**Audit log discipline (§3.26.15.8):** every CRUD operation writes a
row to ``email_audit_log``. The Email primitive maintains its own
audit channel distinct from the general ``audit_logs`` table because
email events have email-specific shape (account_id linkage, provider
context). Subsequent steps may consolidate.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.email_primitive import (
    ACCESS_LEVELS,
    ACCOUNT_TYPES,
    PROVIDER_TYPES,
    EmailAccount,
    EmailAccountAccess,
    EmailAccountSyncState,
    EmailAuditLog,
)
from app.services.email.providers import get_provider_class

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class EmailAccountError(Exception):
    """Base error for email account operations.

    ``http_status`` is the suggested HTTP response code; route handlers
    translate via the existing convention used across the codebase.
    """

    http_status: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmailAccountNotFound(EmailAccountError):
    http_status = 404


class EmailAccountConflict(EmailAccountError):
    http_status = 409


class EmailAccountValidation(EmailAccountError):
    http_status = 400


class EmailAccountPermissionDenied(EmailAccountError):
    http_status = 403


# ─────────────────────────────────────────────────────────────────────
# Access level rank (string → int) for access control comparisons
# ─────────────────────────────────────────────────────────────────────


_ACCESS_RANK = {"read": 1, "read_write": 2, "admin": 3}


def _rank(level: str) -> int:
    return _ACCESS_RANK.get(level, 0)


# ─────────────────────────────────────────────────────────────────────
# Audit logging helper (§3.26.15.8)
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
) -> EmailAuditLog:
    """Append a row to ``email_audit_log``.

    Uses ``db.flush()`` (not commit) so the audit row commits atomically
    with the caller's business operation — same pattern as
    ``app.services.audit_service.log_action``.
    """
    entry = EmailAuditLog(
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
# CRUD: EmailAccount
# ─────────────────────────────────────────────────────────────────────


def create_account(
    db: Session,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    account_type: str,
    display_name: str,
    email_address: str,
    provider_type: str,
    provider_config: dict[str, Any] | None = None,
    signature_html: str | None = None,
    reply_to_override: str | None = None,
    is_default: bool = False,
) -> EmailAccount:
    """Create a new EmailAccount.

    Validation:
      - account_type must be one of ACCOUNT_TYPES
      - provider_type must be one of PROVIDER_TYPES
      - (tenant_id, email_address) unique among active accounts
      - if is_default=True, demotes any other default in the same tenant

    Side effects:
      - Creates an EmailAccountSyncState row pointing at the new account
        with ``sync_status='pending'`` (Step 2 transitions to 'syncing'
        on first sync).
      - Audit log entry: action='account_created'.
    """
    if account_type not in ACCOUNT_TYPES:
        raise EmailAccountValidation(
            f"account_type must be one of {ACCOUNT_TYPES}, got {account_type!r}"
        )
    if provider_type not in PROVIDER_TYPES:
        raise EmailAccountValidation(
            f"provider_type must be one of {PROVIDER_TYPES}, got {provider_type!r}"
        )
    if not email_address or "@" not in email_address:
        raise EmailAccountValidation(
            f"email_address must be a valid email, got {email_address!r}"
        )

    # Uniqueness pre-check (the partial unique index also catches this).
    existing = (
        db.query(EmailAccount)
        .filter(
            EmailAccount.tenant_id == tenant_id,
            EmailAccount.email_address == email_address,
            EmailAccount.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise EmailAccountConflict(
            f"An active EmailAccount with email_address {email_address!r} "
            f"already exists in this tenant."
        )

    # Demote any other default if this one is_default=True.
    if is_default:
        db.query(EmailAccount).filter(
            EmailAccount.tenant_id == tenant_id,
            EmailAccount.is_default.is_(True),
        ).update({"is_default": False})

    account = EmailAccount(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        account_type=account_type,
        display_name=display_name,
        email_address=email_address,
        provider_type=provider_type,
        provider_config=provider_config or {},
        signature_html=signature_html,
        reply_to_override=reply_to_override,
        is_default=is_default,
        created_by_user_id=actor_user_id,
    )
    db.add(account)
    db.flush()

    # Bootstrap sync state row.
    sync_state = EmailAccountSyncState(
        id=str(uuid.uuid4()),
        account_id=account.id,
        sync_status="pending",
    )
    db.add(sync_state)

    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="account_created",
        entity_type="email_account",
        entity_id=account.id,
        changes={
            "account_type": account_type,
            "email_address": email_address,
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
) -> EmailAccount:
    """Fetch a single EmailAccount, tenant-scoped.

    Raises ``EmailAccountNotFound`` (HTTP 404) if the account doesn't
    exist OR exists in a different tenant — existence-hiding to prevent
    cross-tenant id enumeration.
    """
    account = (
        db.query(EmailAccount)
        .filter(
            EmailAccount.id == account_id,
            EmailAccount.tenant_id == tenant_id,
        )
        .first()
    )
    if not account:
        raise EmailAccountNotFound(f"EmailAccount {account_id!r} not found.")
    return account


def list_accounts_for_tenant(
    db: Session,
    *,
    tenant_id: str,
    include_inactive: bool = False,
) -> list[EmailAccount]:
    """List all EmailAccount rows in a tenant.

    Tenant admins call this; per-user filter uses ``list_accounts_for_user``.
    """
    query = db.query(EmailAccount).filter(EmailAccount.tenant_id == tenant_id)
    if not include_inactive:
        query = query.filter(EmailAccount.is_active.is_(True))
    return query.order_by(EmailAccount.created_at.desc()).all()


def list_accounts_for_user(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
) -> list[EmailAccount]:
    """List accounts the user has any access to.

    Joins on ``email_account_access`` with ``revoked_at IS NULL``.
    Returns empty list if the user has no grants.
    """
    accounts = (
        db.query(EmailAccount)
        .join(EmailAccountAccess, EmailAccountAccess.account_id == EmailAccount.id)
        .filter(
            EmailAccount.tenant_id == tenant_id,
            EmailAccount.is_active.is_(True),
            EmailAccountAccess.user_id == user_id,
            EmailAccountAccess.revoked_at.is_(None),
        )
        .order_by(EmailAccount.created_at.desc())
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
    signature_html: str | None = None,
    reply_to_override: str | None = None,
    is_default: bool | None = None,
    is_active: bool | None = None,
    provider_config_patch: dict[str, Any] | None = None,
) -> EmailAccount:
    """Partial-update an EmailAccount.

    Only fields that are not None get patched. ``is_default=True``
    demotes other defaults in the same tenant. ``is_active=False``
    soft-disables the account; the sync state stays for audit.
    ``provider_config_patch`` MERGES into existing provider_config —
    pass an empty dict to leave unchanged, or specific keys to update.
    """
    account = get_account(db, account_id=account_id, tenant_id=tenant_id)
    changes: dict[str, dict[str, Any]] = {}

    if display_name is not None and display_name != account.display_name:
        changes["display_name"] = {"old": account.display_name, "new": display_name}
        account.display_name = display_name
    if signature_html is not None and signature_html != account.signature_html:
        changes["signature_html"] = {
            "old_present": account.signature_html is not None,
            "new_present": True,
        }
        account.signature_html = signature_html
    if reply_to_override is not None and reply_to_override != account.reply_to_override:
        changes["reply_to_override"] = {
            "old": account.reply_to_override,
            "new": reply_to_override,
        }
        account.reply_to_override = reply_to_override
    if is_default is not None and is_default != account.is_default:
        if is_default:
            db.query(EmailAccount).filter(
                EmailAccount.tenant_id == tenant_id,
                EmailAccount.is_default.is_(True),
                EmailAccount.id != account.id,
            ).update({"is_default": False})
        changes["is_default"] = {"old": account.is_default, "new": is_default}
        account.is_default = is_default
    if is_active is not None and is_active != account.is_active:
        changes["is_active"] = {"old": account.is_active, "new": is_active}
        account.is_active = is_active
    if provider_config_patch:
        merged = dict(account.provider_config or {})
        merged.update(provider_config_patch)
        # Note: tokens / credentials get encrypted at rest in Step 2;
        # Step 1 stores plaintext placeholders only.
        changes["provider_config_keys_changed"] = sorted(provider_config_patch.keys())
        account.provider_config = merged

    if changes:
        account.updated_at = datetime.now(timezone.utc)
        _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="account_updated",
            entity_type="email_account",
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
    """Soft-delete an EmailAccount via ``is_active=False``.

    Hard-delete is not exposed: the audit trail (and any future
    threads/messages persisted under this account) must be preserved.
    """
    account = get_account(db, account_id=account_id, tenant_id=tenant_id)
    account.is_active = False
    account.is_default = False
    account.updated_at = datetime.now(timezone.utc)

    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="account_deleted",
        entity_type="email_account",
        entity_id=account.id,
    )

    # Best-effort: invoke the provider's disconnect() so any external
    # subscription resources are released. Provider stubs are no-ops
    # in Step 1; real implementations land in Step 2.
    try:
        provider_cls = get_provider_class(account.provider_type)
        provider = provider_cls(account.provider_config)
        provider.disconnect()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "EmailAccount.disconnect() failed for account_id=%s: %s",
            account.id,
            exc,
        )

    db.flush()


# ─────────────────────────────────────────────────────────────────────
# CRUD: EmailAccountAccess
# ─────────────────────────────────────────────────────────────────────


def grant_access(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
    user_id: str,
    access_level: str,
    actor_user_id: str | None,
) -> EmailAccountAccess:
    """Grant a user access to an EmailAccount at the given level.

    Idempotent for an already-active grant at the SAME level (returns
    the existing row). If an active grant exists at a DIFFERENT level,
    UPDATES the level and writes an audit row. If a previously-revoked
    grant exists, creates a fresh row (audit trail stays linear).
    """
    if access_level not in ACCESS_LEVELS:
        raise EmailAccountValidation(
            f"access_level must be one of {ACCESS_LEVELS}, got {access_level!r}"
        )

    # Verify account is in caller's tenant.
    get_account(db, account_id=account_id, tenant_id=tenant_id)

    active = (
        db.query(EmailAccountAccess)
        .filter(
            EmailAccountAccess.account_id == account_id,
            EmailAccountAccess.user_id == user_id,
            EmailAccountAccess.revoked_at.is_(None),
        )
        .first()
    )
    if active:
        if active.access_level == access_level:
            return active
        old_level = active.access_level
        active.access_level = access_level
        _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="access_level_changed",
            entity_type="email_account_access",
            entity_id=active.id,
            changes={
                "account_id": account_id,
                "user_id": user_id,
                "old": old_level,
                "new": access_level,
            },
        )
        db.flush()
        return active

    grant = EmailAccountAccess(
        id=str(uuid.uuid4()),
        account_id=account_id,
        user_id=user_id,
        access_level=access_level,
        granted_by_user_id=actor_user_id,
    )
    db.add(grant)
    try:
        db.flush()
    except IntegrityError as exc:
        # Race against concurrent grant; surface as conflict.
        db.rollback()
        raise EmailAccountConflict(
            f"Race detected granting access (account_id={account_id}, "
            f"user_id={user_id}). Retry."
        ) from exc

    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="access_granted",
        entity_type="email_account_access",
        entity_id=grant.id,
        changes={
            "account_id": account_id,
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
    """Revoke a user's access to an EmailAccount.

    Returns True if a row was revoked, False if the user had no active
    grant (idempotent — no error). Stamps ``revoked_at`` rather than
    deleting the row so the audit trail is preserved.
    """
    # Verify account is in caller's tenant.
    get_account(db, account_id=account_id, tenant_id=tenant_id)

    grant = (
        db.query(EmailAccountAccess)
        .filter(
            EmailAccountAccess.account_id == account_id,
            EmailAccountAccess.user_id == user_id,
            EmailAccountAccess.revoked_at.is_(None),
        )
        .first()
    )
    if not grant:
        return False

    grant.revoked_at = datetime.now(timezone.utc)
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="access_revoked",
        entity_type="email_account_access",
        entity_id=grant.id,
        changes={
            "account_id": account_id,
            "user_id": user_id,
            "access_level_at_revoke": grant.access_level,
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
) -> list[EmailAccountAccess]:
    """List access grants on an account.

    Used by the Settings → Email Accounts UI to render the access list.
    """
    # Verify account is in caller's tenant (404 if not).
    get_account(db, account_id=account_id, tenant_id=tenant_id)

    query = db.query(EmailAccountAccess).filter(
        EmailAccountAccess.account_id == account_id
    )
    if not include_revoked:
        query = query.filter(EmailAccountAccess.revoked_at.is_(None))
    return query.order_by(EmailAccountAccess.granted_at.desc()).all()


# ─────────────────────────────────────────────────────────────────────
# Access control verification
# ─────────────────────────────────────────────────────────────────────


def user_has_access(
    db: Session,
    *,
    account_id: str,
    user_id: str,
    required_level: str = "read",
) -> bool:
    """Return True if the user has at-least ``required_level`` on the
    account.

    Levels are ranked: read (1) < read_write (2) < admin (3). A user
    with ``read_write`` passes ``required_level='read'`` but not
    ``required_level='admin'``.

    Returns False if no active grant exists. Tenant scoping is enforced
    by virtue of how grants are created (a grant ties a user to an
    account, both of which live in the same tenant) — but callers
    SHOULD also verify the account is in the user's tenant before
    consulting this helper.
    """
    if required_level not in ACCESS_LEVELS:
        raise EmailAccountValidation(
            f"required_level must be one of {ACCESS_LEVELS}, got {required_level!r}"
        )

    grant = (
        db.query(EmailAccountAccess)
        .filter(
            EmailAccountAccess.account_id == account_id,
            EmailAccountAccess.user_id == user_id,
            EmailAccountAccess.revoked_at.is_(None),
        )
        .first()
    )
    if not grant:
        return False
    return _rank(grant.access_level) >= _rank(required_level)


def require_access(
    db: Session,
    *,
    account_id: str,
    user_id: str,
    tenant_id: str,
    required_level: str = "read",
) -> EmailAccount:
    """Verify the user has at-least ``required_level`` on the account
    AND that the account is in the user's tenant.

    Returns the EmailAccount on success. Raises ``EmailAccountNotFound``
    (404) if the account doesn't exist in the tenant — existence-hiding
    against id enumeration. Raises ``EmailAccountPermissionDenied``
    (403) if the account exists but the user lacks the required level.
    """
    account = get_account(db, account_id=account_id, tenant_id=tenant_id)
    if not user_has_access(
        db, account_id=account_id, user_id=user_id, required_level=required_level
    ):
        raise EmailAccountPermissionDenied(
            f"User {user_id!r} lacks {required_level!r} access on "
            f"account {account_id!r}."
        )
    return account
