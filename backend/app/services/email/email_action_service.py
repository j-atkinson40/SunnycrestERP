"""Email primitive action-token facade —
Phase W-4b Layer 1 Step 4c (post-substrate-consolidation).

Per Calendar Step 1 discovery Q3 confirmation: this module remains
the canonical import surface for Email primitive callers (Step 4c
routes, outbound_service, tests, demo seed). Internally it re-exports
the generic substrate from ``app.services.platform.action_service``
+ retains email-specific helpers (``build_quote_approval_action``,
Quote state propagation handler, ``ACTION_OUTCOMES_QUOTE_APPROVAL``
constant).

**Pre-substrate-consolidation behavior preserved verbatim**:
  - ``commit_action(db, *, message, action_idx, outcome, ...)`` —
    same signature; quote_approval state propagation unchanged
  - ``issue_action_token(db, *, tenant_id, message_id, action_idx,
    action_type, recipient_email, ttl_days)`` — keeps message_id
    kwarg; internally maps to linked_entity_type='email_message' +
    linked_entity_id=message_id
  - ``lookup_action_token`` / ``consume_action_token`` /
    ``generate_action_token`` — re-exported from substrate
  - ``ACTION_TYPES`` / ``TOKEN_TTL_DAYS`` /
    ``ACTION_OUTCOMES_QUOTE_APPROVAL`` / ``ACTION_STATUSES`` —
    constants preserved

**Per BRIDGEABLE_MASTER §3.26.15.17 + DESIGN_LANGUAGE §14.9.5**:
emails carry **operational-action affordances** that bind email
content to platform operations. The canonical case shipping in Step 4c
is ``quote_approval`` — a non-Bridgeable customer (funeral home
recipient of a manufacturer-sent quote) approves/rejects/requests-
changes on a quote without ever leaving the email surface or being
asked to sign into a Bridgeable portal.

**kill-the-portal canonical pattern:**
  - Bridgeable recipient → inline action affordance directly in the
    thread detail view (authenticated; identity already known)
  - Non-Bridgeable recipient → magic-link contextual surface
    (token-authenticated; tenant-branded; mobile-first)
  - **Both paths** commit through this single service so the audit
    log + Quote state propagation logic stays canonical.

**Action shape (canonical per §3.26.15.17)** lives in
``email_messages.message_payload.actions[]``:

.. code-block:: json

   {
     "action_type": "quote_approval",
     "action_target_type": "quote",
     "action_target_id": "<quote UUID>",
     "action_metadata": {...},
     "action_status": "pending",
     "action_completed_at": null,
     "action_completed_by": null,
     "action_completion_metadata": null
   }

Status flow: ``pending`` → ``approved`` | ``rejected`` |
``changes_requested`` (terminal). Re-commit on a terminal action
returns 409 — actions are single-shot per §3.26.15.17 discipline.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_primitive import EmailMessage
from app.models.quote import Quote
from app.services.email.account_service import _audit
from app.services.platform.action_registry import (
    ActionTypeDescriptor,
    register_action_type,
)
from app.services.platform.action_service import (
    # Generic errors re-exported for backwards compat with Step 4c
    # imports (route handlers + outbound_service + test fixtures).
    ActionAlreadyCompleted,
    ActionError,
    ActionNotFound,
    ActionTokenAlreadyConsumed,
    ActionTokenExpired,
    ActionTokenInvalid,
    CrossPrimitiveTokenMismatch,
    PlatformActionError,
    # Generic substrate functions re-exported.
    TOKEN_TTL_DAYS,
    build_magic_link_url,
    consume_action_token,
    generate_action_token,
    lookup_action_token,
    lookup_token_row_raw,
)
from app.services.platform.action_service import (
    issue_action_token as _platform_issue_action_token,
)
from app.services.platform.action_service import (
    commit_action as _platform_commit_action,
)
from app.services.platform.action_service import (
    _INSERT_ACTION_TOKEN_SQL,  # re-export for Step 4c outbound_service
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Email-specific canonical vocabulary (preserved from r66 / Step 4c)
# ─────────────────────────────────────────────────────────────────────

# Per §3.26.15.17: ``quote_approval`` is the September scope canonical
# action_type; future actions deferred per §3.26.7.5 architectural
# restraint discipline.
ACTION_TYPES = ("quote_approval",)

ACTION_OUTCOMES_QUOTE_APPROVAL = (
    "approve",
    "reject",
    "request_changes",
)

# action_status values stored on the action object inside
# email_messages.message_payload.actions[]
ACTION_STATUSES = (
    "pending",
    "approved",
    "rejected",
    "changes_requested",
)


# ─────────────────────────────────────────────────────────────────────
# Action shape helpers (Email primitive scope)
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
# Email-specific token issuance facade — preserves r66 signature
# (message_id kwarg) while routing through the generic substrate.
# ─────────────────────────────────────────────────────────────────────


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
    """Issue an action token for an email message.

    Backwards-compat shim — keeps the r66 signature with ``message_id``
    kwarg. Internally maps to ``linked_entity_type='email_message'`` +
    ``linked_entity_id=message_id`` against the generic substrate.

    Existing callers (outbound_service, tests, demo seed) continue
    invoking ``issue_action_token(db, tenant_id=..., message_id=...,
    ...)`` unchanged.
    """
    return _platform_issue_action_token(
        db,
        tenant_id=tenant_id,
        linked_entity_type="email_message",
        linked_entity_id=message_id,
        action_idx=action_idx,
        action_type=action_type,
        recipient_email=recipient_email,
        ttl_days=ttl_days,
    )


# ─────────────────────────────────────────────────────────────────────
# Email-specific commit facade — Quote state propagation handler
# registered against ``quote_approval`` action_type.
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
    """Commit an Email primitive action outcome — atomic.

    Backwards-compat facade preserving r66 / Step 4c signature.
    Resolves the action from ``message.message_payload.actions[idx]``
    + dispatches through the generic substrate's
    ``commit_action`` to the registered ``quote_approval`` handler.

    Args:
      message: EmailMessage carrying the action in message_payload.
      action_idx: Index into message_payload.actions[].
      outcome: One of ACTION_OUTCOMES_QUOTE_APPROVAL.
      actor_user_id: Bridgeable user id when auth_method="bridgeable".
      actor_email: Recipient email when auth_method="magic_link".
      completion_note: Free-text note (required for "request_changes").
      auth_method: "bridgeable" | "magic_link".

    Returns the updated action object with stamped completion fields.

    Raises:
      ActionAlreadyCompleted (409) if action already terminal.
      ActionError (400) on outcome/note validation issues.
    """
    action = get_action_at_index(message, action_idx)
    return _platform_commit_action(
        db,
        action=action,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        auth_method=auth_method,
        completion_note=completion_note,
        ip_address=ip_address,
        user_agent=user_agent,
        # Email-specific kwargs forwarded to the registered
        # quote_approval handler:
        message=message,
        action_idx=action_idx,
    )


# ─────────────────────────────────────────────────────────────────────
# quote_approval commit handler — registered against the central
# registry. Reproduces r66 / Step 4c state propagation verbatim:
#   approve → Quote.status = "accepted"
#   reject → Quote.status = "rejected"
#   request_changes → Quote.status retained as "sent"; commits the
#     action with completion_metadata capturing the requested-changes
#     note for operator visibility.
# ─────────────────────────────────────────────────────────────────────


def _commit_handler_quote_approval(
    db: Session,
    *,
    action: dict[str, Any],
    outcome: str,
    descriptor: ActionTypeDescriptor,
    actor_user_id: str | None,
    actor_email: str | None,
    auth_method: str,
    completion_metadata: dict[str, Any],
    completion_note: str | None,
    ip_address: str | None,
    user_agent: str | None,
    # Email-specific kwargs forwarded by facade.
    message: EmailMessage,
    action_idx: int,
    **_: Any,
) -> dict[str, Any]:
    """quote_approval commit handler — Quote state propagation + audit log.

    Reproduces r66 / Step 4c behavior verbatim. Registered against
    the central registry via ``register_action_type``; dispatched by
    the generic substrate's ``commit_action``.
    """
    from datetime import datetime, timezone

    # 1. Resolve target Quote — must belong to message's tenant.
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

    now = datetime.now(timezone.utc)

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

    # 4. Quote audit fields.
    quote.modified_at = now
    if actor_user_id:
        quote.modified_by = actor_user_id

    db.flush()

    # 5. Audit log per §3.26.15.8 — metadata only, never body content.
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
# Side-effect registration — runs at module import time so the central
# registry is populated when Email package imports this module via
# its __init__. Idempotent per registry semantics.
# ─────────────────────────────────────────────────────────────────────

register_action_type(
    ActionTypeDescriptor(
        action_type="quote_approval",
        primitive="email",
        target_entity_type="quote",
        outcomes=ACTION_OUTCOMES_QUOTE_APPROVAL,
        # request_changes is terminal at the action level (action_status
        # transitions to "changes_requested"); operator follows up
        # with a fresh action token.
        terminal_outcomes=ACTION_OUTCOMES_QUOTE_APPROVAL,
        requires_completion_note=("request_changes",),
        commit_handler=_commit_handler_quote_approval,
    )
)


# ─────────────────────────────────────────────────────────────────────
# Public exports — preserved verbatim for Step 4c backwards compat.
# ─────────────────────────────────────────────────────────────────────

__all__ = [
    # Email-specific canonical vocabulary
    "ACTION_TYPES",
    "ACTION_OUTCOMES_QUOTE_APPROVAL",
    "ACTION_STATUSES",
    "TOKEN_TTL_DAYS",
    # Email-specific helpers
    "build_quote_approval_action",
    "get_message_actions",
    "get_action_at_index",
    # Token CRUD facade
    "issue_action_token",
    "lookup_action_token",
    "consume_action_token",
    "lookup_token_row_raw",
    "generate_action_token",
    # Commit facade
    "commit_action",
    # Magic-link URL helper
    "build_magic_link_url",
    # Errors (re-exported from substrate)
    "PlatformActionError",
    "ActionError",
    "ActionNotFound",
    "ActionAlreadyCompleted",
    "ActionTokenInvalid",
    "ActionTokenExpired",
    "ActionTokenAlreadyConsumed",
    "CrossPrimitiveTokenMismatch",
    # Raw SQL constant — preserved for outbound_service caller backwards compat
    "_INSERT_ACTION_TOKEN_SQL",
]
