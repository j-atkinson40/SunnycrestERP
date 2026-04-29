"""Operational-action affordance service —
Phase W-4b Layer 1 Step 4c.

Per BRIDGEABLE_MASTER §3.26.15.17 + DESIGN_LANGUAGE §14.9.5: emails
carry **operational-action affordances** that bind email content to
platform operations. The canonical case shipping in Step 4c is
``quote_approval`` — a non-Bridgeable customer (funeral home recipient
of a manufacturer-sent quote) approves/rejects/requests-changes on a
quote without ever leaving the email surface or being asked to sign
into a Bridgeable portal.

**kill-the-portal canonical pattern:**
  - Bridgeable recipient → inline action affordance directly in the
    thread detail view (authenticated; identity already known)
  - Non-Bridgeable recipient → magic-link contextual surface
    (token-authenticated; tenant-branded; mobile-first)
  - **Both paths** commit through this single service so the audit
    log + Quote state propagation logic stays canonical.

**Action shape (canonical per §3.26.15.17):**

.. code-block:: json

   {
     "action_type": "quote_approval",
     "action_target_type": "quote",
     "action_target_id": "<quote UUID>",
     "action_metadata": {
       "quote_amount": 12500.00,
       "quote_line_items": [...],
       "expires_at": "2026-05-15T17:00:00Z"
     },
     "action_status": "pending",
     "action_completed_at": null,
     "action_completed_by": null,
     "action_completion_metadata": null
   }

Status flow: ``pending`` → ``approved`` | ``rejected`` |
``changes_requested`` (terminal). Re-commit on a terminal action
returns 409 — actions are single-shot per §3.26.15.17 discipline.

**Token canon (§3.26.15.17 + §14.9.5):**
  - 7-day expiry from email send time
  - 256-bit URL-safe via ``secrets.token_urlsafe(32)`` (matches
    ``signing/token_service.py`` precedent)
  - Single-action authorization (token unlocks one action_idx in one
    message; cannot navigate beyond contextual surface)
  - Token consumption on action commit (``consumed_at`` stamped)
  - Audit log entry per click + commit (kill-the-portal discipline)

**State propagation:**
  - approve → Quote.status = "accepted"
  - reject → Quote.status = "rejected"
  - request_changes → Quote.status retained as "sent" (no terminal
    state change; commits the action with completion_metadata
    capturing the requested-changes note for operator visibility,
    intelligence stream synthesis later)
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_primitive import EmailMessage
from app.models.quote import Quote
from app.services.email.account_service import (
    EmailAccountError,
    _audit,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Canonical vocabulary
# ─────────────────────────────────────────────────────────────────────


# Currently shipping ``quote_approval`` — the canonical kill-the-portal
# case. Future actions (cremation_authorization, vault_dispatch, etc.)
# extend this set per §3.26.15.17 — Step 4c locks the schema by
# building all infrastructure against this single action_type so the
# extension path stays narrow.
ACTION_TYPES = ("quote_approval",)

ACTION_OUTCOMES_QUOTE_APPROVAL = (
    "approve",
    "reject",
    "request_changes",
)

# action_status values stored on the action object inside
# ``email_messages.message_payload.actions[]``
ACTION_STATUSES = (
    "pending",
    "approved",
    "rejected",
    "changes_requested",
)

# Token canonical expiry per §3.26.15.17
TOKEN_TTL_DAYS = 7


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class ActionError(EmailAccountError):
    http_status = 400


class ActionNotFound(EmailAccountError):
    http_status = 404


class ActionAlreadyCompleted(EmailAccountError):
    http_status = 409


class ActionTokenInvalid(EmailAccountError):
    http_status = 401


class ActionTokenExpired(EmailAccountError):
    http_status = 410


class ActionTokenAlreadyConsumed(EmailAccountError):
    http_status = 409


# ─────────────────────────────────────────────────────────────────────
# Token storage — uses ``email_action_tokens`` table from r66
# ─────────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_action_token() -> str:
    """Generate a 256-bit URL-safe token.

    Same shape as ``signing.token_service.generate_signer_token`` —
    ``secrets.token_urlsafe(32)`` produces 43-char base64, URL-safe,
    no padding/slashes. Cryptographically resistant to brute-force.
    """
    return secrets.token_urlsafe(32)


def issue_action_token(
    db: Session,
    *,
    tenant_id: str,
    message_id: str,
    action_idx: int,
    action_type: str,
    recipient_email: str,
    ttl_days: int = TOKEN_TTL_DAYS,
) -> str:
    """Insert an ``email_action_tokens`` row + return the raw token.

    Called from outbound_service when a message with operational
    actions is sent to non-Bridgeable recipients. Token embeds in the
    rendered email body as the magic-link URL.

    The DB row is the source of truth — we don't sign the token JWT-
    style because we want a server-side revocation surface (operator
    can void a token via ``revoked_at`` if recipient claims compromise).
    """
    if action_type not in ACTION_TYPES:
        raise ActionError(f"Unknown action_type: {action_type}")

    token = generate_action_token()
    expires_at = _now() + timedelta(days=ttl_days)

    # Use raw SQL to avoid coupling to a model class — we keep the
    # token table thin per §3.26.15.17 (single-purpose, no business
    # logic stored on the row beyond the trace fields).
    db.execute(
        _INSERT_ACTION_TOKEN_SQL,
        {
            "token": token,
            "tenant_id": tenant_id,
            "message_id": message_id,
            "action_idx": action_idx,
            "action_type": action_type,
            "recipient_email": recipient_email.lower().strip(),
            "expires_at": expires_at,
        },
    )
    db.flush()
    return token


def lookup_action_token(
    db: Session, *, token: str
) -> dict[str, Any]:
    """Return the action-token row for the given raw token.

    Raises ``ActionTokenInvalid`` if not found, ``ActionTokenExpired``
    if past TTL, ``ActionTokenAlreadyConsumed`` if previously consumed
    or revoked. Stamps ``last_clicked_at`` + increments
    ``click_count`` on every successful lookup so we have audit
    visibility into multi-click patterns.

    Returns dict shape: ``{token, tenant_id, message_id, action_idx,
    action_type, recipient_email, expires_at, consumed_at, revoked_at,
    click_count}``.
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

    # Stamp click — visibility into clicked-but-not-acted patterns
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


# Raw SQL avoids creating a dedicated SQLAlchemy model just for a
# server-side ledger table that has no relationships outside the
# service. Pattern matches signing/token_service which similarly avoids
# a model-layer bloat.
from sqlalchemy import text  # noqa: E402

_INSERT_ACTION_TOKEN_SQL = text(
    """
    INSERT INTO email_action_tokens (
        token, tenant_id, message_id, action_idx, action_type,
        recipient_email, expires_at, click_count
    ) VALUES (
        :token, :tenant_id, :message_id, :action_idx, :action_type,
        :recipient_email, :expires_at, 0
    )
    """
)

_SELECT_ACTION_TOKEN_SQL = text(
    """
    SELECT token, tenant_id, message_id, action_idx, action_type,
           recipient_email, expires_at, consumed_at, revoked_at,
           click_count, last_clicked_at, created_at
    FROM email_action_tokens
    WHERE token = :token
    """
)

_UPDATE_ACTION_TOKEN_CLICK_SQL = text(
    """
    UPDATE email_action_tokens
    SET click_count = click_count + 1, last_clicked_at = :now
    WHERE token = :token
    """
)

_UPDATE_ACTION_TOKEN_CONSUME_SQL = text(
    """
    UPDATE email_action_tokens
    SET consumed_at = :now
    WHERE token = :token
    """
)


# ─────────────────────────────────────────────────────────────────────
# Action shape helpers
# ─────────────────────────────────────────────────────────────────────


def build_quote_approval_action(
    *,
    quote: Quote,
) -> dict[str, Any]:
    """Build a canonical quote_approval action object from a Quote.

    Caller embeds this in ``message_payload.actions[]`` before send.
    Snapshot of quote total + line-item count + expiry — keeps the
    affordance self-contained (recipient sees the at-the-time-of-send
    figures even if the quote later mutates).
    """
    line_items = []
    for line in (quote.lines or []):
        line_items.append(
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
            }
        )

    metadata: dict[str, Any] = {
        "quote_number": quote.number,
        "quote_amount": str(quote.total),
        "quote_subtotal": str(quote.subtotal),
        "quote_tax_amount": str(quote.tax_amount),
        "quote_line_items": line_items,
        "customer_name": quote.customer_name,
    }
    if quote.expiry_date:
        metadata["expires_at"] = quote.expiry_date.isoformat()

    return {
        "action_type": "quote_approval",
        "action_target_type": "quote",
        "action_target_id": quote.id,
        "action_metadata": metadata,
        "action_status": "pending",
        "action_completed_at": None,
        "action_completed_by": None,
        "action_completion_metadata": None,
    }


def get_message_actions(message: EmailMessage) -> list[dict[str, Any]]:
    """Return the actions array from a message_payload, defaulting to []."""
    payload = message.message_payload or {}
    actions = payload.get("actions")
    if not isinstance(actions, list):
        return []
    return actions


def get_action_at_index(
    message: EmailMessage, action_idx: int
) -> dict[str, Any]:
    """Get a specific action by index. Raises ActionNotFound if missing."""
    actions = get_message_actions(message)
    if action_idx < 0 or action_idx >= len(actions):
        raise ActionNotFound(
            f"Action index {action_idx} not found on message {message.id}"
        )
    return actions[action_idx]


# ─────────────────────────────────────────────────────────────────────
# Action commit — single canonical entry point
# ─────────────────────────────────────────────────────────────────────


def commit_action(
    db: Session,
    *,
    message: EmailMessage,
    action_idx: int,
    outcome: str,
    actor_user_id: str | None,
    actor_email: str | None,
    completion_note: str | None = None,
    auth_method: str = "bridgeable",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Commit an action outcome — atomic.

    Both the inline-action endpoint (Bridgeable user) AND the magic-
    link surface (token-authenticated non-Bridgeable user) call this.

    Args:
      message: The EmailMessage containing the action in message_payload.
      action_idx: Index into message_payload.actions[].
      outcome: One of ACTION_OUTCOMES_QUOTE_APPROVAL — "approve" /
        "reject" / "request_changes".
      actor_user_id: Bridgeable user id when auth_method="bridgeable",
        else None.
      actor_email: Recipient email when auth_method="magic_link",
        else None (user_id captures Bridgeable identity).
      completion_note: Free-text note (required for "request_changes").
      auth_method: "bridgeable" | "magic_link" — drives audit log
        attribution.

    Returns the updated action object (with stamped completion fields).

    Raises:
      ActionAlreadyCompleted (409) if action.action_status is terminal.
      ActionError (400) on outcome/note validation issues.
    """
    action = get_action_at_index(message, action_idx)

    if action["action_status"] != "pending":
        raise ActionAlreadyCompleted(
            f"Action already in terminal state '{action['action_status']}'."
        )

    if action["action_type"] != "quote_approval":
        raise ActionError(
            f"Unsupported action_type for commit: {action['action_type']}"
        )

    if outcome not in ACTION_OUTCOMES_QUOTE_APPROVAL:
        raise ActionError(
            f"Unknown outcome '{outcome}'. "
            f"Expected one of {ACTION_OUTCOMES_QUOTE_APPROVAL}."
        )

    if outcome == "request_changes" and not (completion_note or "").strip():
        raise ActionError(
            "completion_note is required when outcome is 'request_changes'."
        )

    # 1. Resolve target Quote — must belong to message tenant.
    target_id = action.get("action_target_id")
    if not target_id:
        raise ActionError("Action is missing action_target_id.")

    quote = (
        db.query(Quote)
        .filter(
            Quote.id == target_id, Quote.company_id == message.tenant_id
        )
        .first()
    )
    if not quote:
        raise ActionNotFound(
            f"Quote {target_id} not found in tenant scope."
        )

    # 2. Map outcome → action_status + Quote.status propagation.
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

    if outcome == "approve":
        new_action_status = "approved"
        quote.status = "accepted"
    elif outcome == "reject":
        new_action_status = "rejected"
        quote.status = "rejected"
    elif outcome == "request_changes":
        new_action_status = "changes_requested"
        # Quote.status NOT changed — request_changes is a non-terminal
        # operator signal per §3.26.15.17. Operator follows up with
        # revised quote; new send creates a new action token.
    else:
        raise ActionError(f"Unhandled outcome: {outcome}")

    now = _now()

    # 3. Update the action object inside message_payload.actions[].
    # JSONB columns require explicit replacement of the dict; mutating
    # the nested dict in place doesn't trigger SQLAlchemy dirty tracking
    # on the parent. We rebuild the actions list with the updated entry.
    payload = dict(message.message_payload or {})
    actions = list(payload.get("actions") or [])
    updated_action = dict(actions[action_idx])
    updated_action["action_status"] = new_action_status
    updated_action["action_completed_at"] = now.isoformat()
    updated_action["action_completed_by"] = actor_user_id or actor_email
    updated_action["action_completion_metadata"] = completion_metadata
    actions[action_idx] = updated_action
    payload["actions"] = actions
    message.message_payload = payload

    # Quote audit fields
    quote.modified_at = now
    if actor_user_id:
        quote.modified_by = actor_user_id

    db.flush()

    # 4. Audit log per §3.26.15.8 — metadata only, never body content.
    _audit(
        db,
        tenant_id=message.tenant_id,
        actor_user_id=actor_user_id,
        action="action_committed",
        entity_type="email_message",
        entity_id=message.id,
        changes={
            "action_idx": action_idx,
            "action_type": "quote_approval",
            "outcome": outcome,
            "auth_method": auth_method,
            "quote_id": quote.id,
            "quote_status_after": quote.status,
            "actor_email": (
                (actor_email or "").lower().strip() or None
            ),
            "has_completion_note": bool(completion_note),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    logger.info(
        "email_action_committed message_id=%s action_idx=%s outcome=%s "
        "auth_method=%s quote_id=%s",
        message.id,
        action_idx,
        outcome,
        auth_method,
        quote.id,
    )
    return updated_action


# ─────────────────────────────────────────────────────────────────────
# Magic-link URL building
# ─────────────────────────────────────────────────────────────────────


def build_magic_link_url(*, base_url: str, token: str) -> str:
    """Compose the public magic-link URL embedded in outbound email.

    Public route ``/email/actions/{token}`` resolves to a tenant-
    branded contextual surface (frontend handles routing). Caller
    supplies ``base_url`` from tenant config or platform default.
    """
    base = base_url.rstrip("/")
    return f"{base}/email/actions/{token}"
