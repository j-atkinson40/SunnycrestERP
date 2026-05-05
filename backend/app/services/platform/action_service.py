"""Generic platform action substrate.

Per Calendar Step 1 discovery Q1 confirmation + §3.26.16.17 Phase B
Q13 refinement direction note: substrate consolidation prevents
architectural fragmentation across primitives.

This module owns:
  - Token CRUD against ``platform_action_tokens`` (polymorphic
    ``linked_entity_type`` + ``linked_entity_id``)
  - Generic ``commit_action`` that dispatches to per-action_type
    ``commit_handler`` callable resolved from
    ``app.services.platform.action_registry``
  - Generic error class hierarchy (subclassed by primitive-specific
    facades for HTTP-status mapping continuity)

**Email primitive's ``email_action_service.py`` is now a backwards-compat
facade** (re-exports symbols + retains email-specific helpers like
``build_quote_approval_action`` + ``ACTION_OUTCOMES_QUOTE_APPROVAL``).
Per Q3 confirmed pre-build: zero import-path churn for existing
Step 4c callers.

**Cross-primitive isolation**: ``commit_action`` validates that the
caller-supplied ``linked_entity_type`` matches the action_type's owning
primitive (e.g. quote_approval requires linked_entity_type='email_message').
Cross-primitive token consumption is rejected (returns 400 at the
HTTP layer).

**Token canon (parallel §3.26.15.17 + §14.9.5)**:
  - 7-day default TTL (per-action_type override possible via TOKEN_TTL_DAYS)
  - 256-bit URL-safe via ``secrets.token_urlsafe(32)``
  - Single-action authorization (token unlocks one action_idx in one
    linked entity; cannot navigate beyond contextual surface)
  - Token consumption on action commit (``consumed_at`` stamped)
  - Audit log entry per click + commit (kill-the-portal discipline)
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.platform.action_registry import (
    ActionRegistryError,
    PRIMITIVE_LINKED_ENTITY_TYPES,
    expected_linked_entity_type,
    get_action_type,
    is_registered,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Canonical defaults
# ─────────────────────────────────────────────────────────────────────

# Canonical 7-day TTL per §3.26.15.17 + §3.26.16.17 magic-link expiry
TOKEN_TTL_DAYS = 7


# ─────────────────────────────────────────────────────────────────────
# Errors — generic substrate (Email facade re-subclasses these for
# backwards compat with Step 4c imports + HTTP status mapping).
# ─────────────────────────────────────────────────────────────────────


class PlatformActionError(Exception):
    """Base error for platform action substrate operations.

    Subclasses carry an ``http_status`` attribute consumed by route
    handlers + facade modules. Mirrors Email primitive ``EmailAccountError``
    pattern.
    """

    http_status: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ActionError(PlatformActionError):
    http_status = 400


class ActionNotFound(PlatformActionError):
    http_status = 404


class ActionAlreadyCompleted(PlatformActionError):
    http_status = 409


class ActionTokenInvalid(PlatformActionError):
    http_status = 401


class ActionTokenExpired(PlatformActionError):
    http_status = 410


class ActionTokenAlreadyConsumed(PlatformActionError):
    http_status = 409


class CrossPrimitiveTokenMismatch(PlatformActionError):
    """Raised when a token's linked_entity_type doesn't match the
    expected value for its action_type's owning primitive.

    Example: quote_approval (Email primitive) being submitted against
    a token with linked_entity_type='calendar_event'. Cross-primitive
    isolation safeguard.
    """

    http_status = 400


# ─────────────────────────────────────────────────────────────────────
# Time helpers
# ─────────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────
# Token CRUD — raw SQL against platform_action_tokens
# ─────────────────────────────────────────────────────────────────────
#
# Pattern matches signing.token_service + r66 precedent: avoid creating
# a SQLAlchemy model for a thin server-side ledger table that has no
# relationships outside the service. Single-purpose ledger; raw SQL
# keeps the surface narrow.


def generate_action_token() -> str:
    """Generate a 256-bit URL-safe token.

    ``secrets.token_urlsafe(32)`` produces 43-char base64, URL-safe,
    no padding/slashes. Cryptographically resistant to brute-force.
    Same shape as ``signing.token_service.generate_signer_token`` +
    Email r66 precedent.
    """
    return secrets.token_urlsafe(32)


def issue_action_token(
    db: Session,
    *,
    tenant_id: str,
    linked_entity_type: str,
    linked_entity_id: str,
    action_idx: int,
    action_type: str,
    recipient_email: str,
    ttl_days: int = TOKEN_TTL_DAYS,
) -> str:
    """Insert a ``platform_action_tokens`` row + return the raw token.

    Args:
        tenant_id: Caller's tenant — every token row tenant-scoped.
        linked_entity_type: One of the four canonical primitive values
            ('email_message', 'calendar_event', 'sms_message',
            'phone_call'). Validated against the registry's expected
            value for the action_type's primitive.
        linked_entity_id: PK of the linked entity (e.g. EmailMessage.id,
            CalendarEvent.id). No FK enforced at DB layer per §3.26.16.18
            (audit canon — soft-delete via revoked_at, not hard CASCADE).
        action_idx: Index into the linked entity's actions list.
        action_type: Registered action_type. Validated via registry.
        recipient_email: Magic-link recipient email (lowercased + stripped).
        ttl_days: Token TTL in days. Default 7 per §3.26.15.17 +
            §3.26.16.17 canonical magic-link expiry.

    Raises:
        ActionError: action_type not registered OR linked_entity_type
            doesn't match action_type's owning primitive.

    Returns the raw token string (caller embeds in outbound message
    body as the magic-link URL; DB row is the source of truth for
    revocation + audit).
    """
    # Registry-driven action_type validation — replaces tuple check.
    if not is_registered(action_type):
        raise ActionError(f"Unknown action_type: {action_type}")

    expected = expected_linked_entity_type(action_type)
    if linked_entity_type != expected:
        raise CrossPrimitiveTokenMismatch(
            f"action_type={action_type!r} requires linked_entity_type="
            f"{expected!r}; got {linked_entity_type!r}."
        )

    # CHECK constraint at DB level enforces the 4-value enum; this
    # service-layer pre-check provides a friendlier error than raw
    # PG constraint-violation.
    if linked_entity_type not in PRIMITIVE_LINKED_ENTITY_TYPES.values():
        raise ActionError(
            f"linked_entity_type must be one of "
            f"{sorted(PRIMITIVE_LINKED_ENTITY_TYPES.values())}; "
            f"got {linked_entity_type!r}."
        )

    token = generate_action_token()
    expires_at = _now() + timedelta(days=ttl_days)

    db.execute(
        _INSERT_ACTION_TOKEN_SQL,
        {
            "token": token,
            "tenant_id": tenant_id,
            "linked_entity_type": linked_entity_type,
            "linked_entity_id": linked_entity_id,
            "action_idx": action_idx,
            "action_type": action_type,
            "recipient_email": recipient_email.lower().strip(),
            "expires_at": expires_at,
        },
    )
    db.flush()
    return token


def lookup_action_token(db: Session, *, token: str) -> dict[str, Any]:
    """Return the action-token row for the given raw token.

    Stamps ``last_clicked_at`` + increments ``click_count`` on every
    successful lookup so we have audit visibility into multi-click
    patterns.

    Raises:
        ActionTokenInvalid (401): token not found.
        ActionTokenAlreadyConsumed (409): consumed_at OR revoked_at set.
        ActionTokenExpired (410): expires_at < now().

    Returns dict shape: ``{token, tenant_id, linked_entity_type,
    linked_entity_id, action_idx, action_type, recipient_email,
    expires_at, consumed_at, revoked_at, click_count, last_clicked_at,
    created_at}``.
    """
    row = db.execute(
        _SELECT_ACTION_TOKEN_SQL, {"token": token}
    ).mappings().first()

    if not row:
        raise ActionTokenInvalid("Token not found.")
    if row["revoked_at"] is not None:
        raise ActionTokenAlreadyConsumed("Token has been revoked.")
    if row["consumed_at"] is not None:
        raise ActionTokenAlreadyConsumed("Token already consumed.")
    if row["expires_at"] < _now():
        raise ActionTokenExpired("Token has expired.")

    db.execute(
        _UPDATE_ACTION_TOKEN_CLICK_SQL,
        {"token": token, "now": _now()},
    )
    db.flush()
    return dict(row)


def consume_action_token(db: Session, *, token: str) -> None:
    """Mark token as consumed. Called atomically with action commit."""
    db.execute(
        _UPDATE_ACTION_TOKEN_CONSUME_SQL,
        {"token": token, "now": _now()},
    )
    db.flush()


def lookup_token_row_raw(
    db: Session, *, token: str
) -> dict[str, Any] | None:
    """Lookup token row without state validation.

    Used by the magic-link contextual surface to render terminal
    "already consumed" / "revoked" states honestly rather than 410'ing
    on the recipient. Returns None when token doesn't exist.
    """
    row = db.execute(
        _SELECT_ACTION_TOKEN_SQL, {"token": token}
    ).mappings().first()
    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────
# Generic commit dispatcher
# ─────────────────────────────────────────────────────────────────────


def commit_action(
    db: Session,
    *,
    action: dict[str, Any],
    outcome: str,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_note: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    **handler_kwargs: Any,
) -> dict[str, Any]:
    """Generic action-commit dispatcher.

    Validates outcome + completion_note discipline against the
    ActionTypeDescriptor; dispatches to the descriptor's
    ``commit_handler`` callable for primitive-specific state
    propagation.

    Args:
        action: Action dict (from message_payload.actions[] or
            equivalent). Must carry ``action_type`` + ``action_status``
            + ``action_target_id``.
        outcome: Caller-supplied outcome. Must be in descriptor.outcomes.
        actor_user_id: Bridgeable user id (auth_method='bridgeable').
        actor_email: Recipient email (auth_method='magic_link').
        auth_method: 'bridgeable' | 'magic_link' | other primitive-
            specific values (e.g. 'sms_keyword_reply' per §3.26.17.18).
        completion_note: Required when outcome is in
            descriptor.requires_completion_note. Free text.
        ip_address / user_agent: Captured for audit trail per §3.26.15.8.
        **handler_kwargs: Additional kwargs forwarded to
            descriptor.commit_handler. Primitive-specific (e.g. Email
            facade passes ``message=EmailMessage`` so the quote_approval
            handler can mutate message.message_payload).

    Returns the updated action dict (with stamped completion fields).

    Raises:
        ActionAlreadyCompleted (409): action already in terminal state.
        ActionError (400): validation failure.
    """
    if action.get("action_status") != "pending":
        raise ActionAlreadyCompleted(
            f"Action already in terminal state "
            f"{action.get('action_status')!r}."
        )

    action_type = action.get("action_type")
    if not action_type:
        raise ActionError("Action is missing action_type.")
    descriptor = get_action_type(action_type)

    if outcome not in descriptor.outcomes:
        raise ActionError(
            f"Unknown outcome {outcome!r} for action_type "
            f"{action_type!r}. Expected one of {descriptor.outcomes}."
        )

    if (
        outcome in descriptor.requires_completion_note
        and not (completion_note or "").strip()
    ):
        raise ActionError(
            f"completion_note is required when outcome is {outcome!r}."
        )

    # Build canonical completion_metadata captured at every commit.
    completion_metadata: dict[str, Any] = {
        "outcome": outcome,
        "auth_method": auth_method,
    }
    if completion_note:
        completion_metadata["note"] = completion_note
    if actor_email:
        completion_metadata["actor_email"] = actor_email.lower().strip()
    if ip_address:
        completion_metadata["ip_address"] = ip_address
    if user_agent:
        completion_metadata["user_agent"] = user_agent[:512]

    # Dispatch to primitive-specific handler.
    return descriptor.commit_handler(
        db,
        action=action,
        outcome=outcome,
        descriptor=descriptor,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        auth_method=auth_method,
        completion_note=completion_note,
        completion_metadata=completion_metadata,
        ip_address=ip_address,
        user_agent=user_agent,
        **handler_kwargs,
    )


# ─────────────────────────────────────────────────────────────────────
# Magic-link URL building
# ─────────────────────────────────────────────────────────────────────


def build_magic_link_url(
    *,
    base_url: str,
    token: str,
    primitive_path: str = "email",
) -> str:
    """Compose the public magic-link URL for a given primitive.

    Args:
        base_url: Tenant or platform base URL (e.g. https://app.getbridgeable.com).
        token: Raw action token.
        primitive_path: Route prefix per primitive — 'email' for
            Email primitive (canonical r66 path); 'calendar' for
            Calendar Step 4; 'sms' for SMS Step 4; 'phone' for
            Phone Step 4. Defaults to 'email' for backwards compat
            with existing Email r66 callers.

    Returns the full magic-link URL: ``{base}/{primitive_path}/actions/{token}``.
    """
    base = base_url.rstrip("/")
    return f"{base}/{primitive_path}/actions/{token}"


# ─────────────────────────────────────────────────────────────────────
# Raw SQL constants — match r66 shape, retargeted to platform_action_tokens
# with polymorphic linked_entity columns.
# ─────────────────────────────────────────────────────────────────────


_INSERT_ACTION_TOKEN_SQL = text(
    """
    INSERT INTO platform_action_tokens (
        token, tenant_id, linked_entity_type, linked_entity_id,
        action_idx, action_type, recipient_email, expires_at,
        click_count
    ) VALUES (
        :token, :tenant_id, :linked_entity_type, :linked_entity_id,
        :action_idx, :action_type, :recipient_email, :expires_at,
        0
    )
    """
)

_SELECT_ACTION_TOKEN_SQL = text(
    """
    SELECT token, tenant_id, linked_entity_type, linked_entity_id,
           action_idx, action_type, recipient_email, expires_at,
           consumed_at, revoked_at, click_count, last_clicked_at,
           created_at
    FROM platform_action_tokens
    WHERE token = :token
    """
)

_UPDATE_ACTION_TOKEN_CLICK_SQL = text(
    """
    UPDATE platform_action_tokens
    SET click_count = click_count + 1, last_clicked_at = :now
    WHERE token = :token
    """
)

_UPDATE_ACTION_TOKEN_CONSUME_SQL = text(
    """
    UPDATE platform_action_tokens
    SET consumed_at = :now
    WHERE token = :token
    """
)
