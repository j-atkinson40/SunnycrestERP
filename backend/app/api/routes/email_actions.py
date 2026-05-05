"""Operational-action affordance API — Phase W-4b Layer 1 Step 4c.

Two surfaces — same canonical commit logic underneath:

  - **Inline action** (Bridgeable user, authenticated):
      ``POST /api/v1/email/messages/{message_id}/actions/{action_idx}/commit``
    Acts on a quote_approval action attached to a message in the user's
    tenant. Authorization comes from session/JWT.

  - **Magic-link** (non-Bridgeable recipient, token-authenticated):
      ``GET /api/v1/email/actions/{token}``      → action details
      ``POST /api/v1/email/actions/{token}/commit`` → commit outcome
    Public routes; token IS the auth. Token = single-action authorization;
    cannot navigate beyond contextual surface.

Both paths route through ``email_action_service.commit_action`` which
handles state propagation + audit + Quote.status updates atomically.

Per canon §3.26.15.17 + §14.9.5 — kill-the-portal discipline: external
recipients never enter a Bridgeable login flow; the magic-link surface
shows tenant-branded chrome + the canonical action without exposing
unrelated platform navigation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.email_primitive import EmailMessage
from app.models.user import User
from app.services.email import email_action_service
from app.services.email.email_action_service import (
    ActionAlreadyCompleted,
    ActionError,
    ActionNotFound,
    ActionTokenAlreadyConsumed,
    ActionTokenExpired,
    ActionTokenInvalid,
)

logger = logging.getLogger(__name__)


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic shapes
# ─────────────────────────────────────────────────────────────────────


class CommitActionRequest(BaseModel):
    outcome: str = Field(
        ...,
        description=(
            "One of 'approve', 'reject', 'request_changes' for quote_approval"
        ),
    )
    completion_note: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Free-text note. Required when outcome='request_changes'."
        ),
    )


class CommitActionResponse(BaseModel):
    action_idx: int
    action_type: str
    action_status: str
    action_completed_at: str | None
    action_target_type: str
    action_target_id: str
    target_status: str | None = Field(
        default=None,
        description=(
            "Updated entity status (e.g., Quote.status) post-commit. "
            "Surfaces to the UI for instant feedback without re-fetch."
        ),
    )


class MagicLinkActionDetails(BaseModel):
    """Public surface response — what the magic-link landing page renders.

    No tenant identifying info beyond what's needed to render the
    contextual surface (tenant name + brand color + the single action).
    No thread context, no other messages, no inbox — single-action
    authorization per §3.26.15.17.
    """

    tenant_name: str
    tenant_brand_color: str | None
    sender_name: str | None
    sender_email: str
    subject: str | None
    sent_at: str | None
    action_idx: int
    action_type: str
    action_target_type: str
    action_target_id: str
    action_metadata: dict
    action_status: str
    recipient_email: str
    expires_at: str
    consumed: bool


# ─────────────────────────────────────────────────────────────────────
# Error translation
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (
            ActionError,
            ActionNotFound,
            ActionAlreadyCompleted,
            ActionTokenInvalid,
            ActionTokenExpired,
            ActionTokenAlreadyConsumed,
        ),
    ):
        return HTTPException(
            status_code=exc.http_status, detail=exc.message
        )
    raise exc


# ─────────────────────────────────────────────────────────────────────
# Inline action surface — Bridgeable users
# ─────────────────────────────────────────────────────────────────────


@router.post(
    "/messages/{message_id}/actions/{action_idx}/commit",
    response_model=CommitActionResponse,
)
def commit_inline_action(
    message_id: str,
    action_idx: int,
    request: CommitActionRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Commit an action from the authenticated thread-detail surface.

    Authorization: caller's tenant must own the message. Cross-tenant
    callers get a 404 (existence-hiding).
    """
    message = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.id == message_id,
            EmailMessage.tenant_id == current_user.company_id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    try:
        updated = email_action_service.commit_action(
            db,
            message=message,
            action_idx=action_idx,
            outcome=request.outcome,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            completion_note=request.completion_note,
            auth_method="bridgeable",
            ip_address=_client_ip(http_request),
            user_agent=http_request.headers.get("user-agent"),
        )
    except (
        ActionError,
        ActionNotFound,
        ActionAlreadyCompleted,
    ) as exc:
        raise _translate(exc) from exc

    db.commit()

    target_status = _resolve_target_status(db, updated)
    return CommitActionResponse(
        action_idx=action_idx,
        action_type=updated["action_type"],
        action_status=updated["action_status"],
        action_completed_at=updated.get("action_completed_at"),
        action_target_type=updated["action_target_type"],
        action_target_id=updated["action_target_id"],
        target_status=target_status,
    )


# ─────────────────────────────────────────────────────────────────────
# Magic-link surface — public, token-authenticated
# ─────────────────────────────────────────────────────────────────────


@router.get(
    "/actions/{token}", response_model=MagicLinkActionDetails
)
def get_magic_link_action(
    token: str,
    db: Session = Depends(get_db),
):
    """Return the contextual-surface render details for a magic-link.

    Public route. No authentication header required — the token IS the
    auth. Token validation includes:
      - Existence (401 ActionTokenInvalid)
      - Not expired (410 ActionTokenExpired)
      - Not consumed/revoked (409 ActionTokenAlreadyConsumed —
        landing page renders "already approved" terminal state)

    Successful lookups stamp ``last_clicked_at`` + increment
    ``click_count`` so we have audit visibility into multi-click
    patterns (e.g., recipient clicks link multiple times to verify
    before deciding).

    For consumed/revoked tokens we still return action details (with
    consumed=True) so the surface can render an honest "already
    completed" state instead of a generic error — better UX for the
    recipient who clicks an old email.
    """
    try:
        token_row = email_action_service.lookup_action_token(
            db, token=token
        )
        consumed = False
    except ActionTokenAlreadyConsumed:
        # Re-fetch row to render terminal "already consumed" state
        # via the substrate's bypass-validation helper (r70 substrate
        # consolidation — replaces inline raw SQL against the renamed
        # platform_action_tokens table).
        token_row = email_action_service.lookup_token_row_raw(
            db, token=token
        )
        if token_row is None:
            raise _translate(
                ActionTokenInvalid("Token not found.")
            ) from None
        consumed = True
    except (ActionTokenInvalid, ActionTokenExpired) as exc:
        raise _translate(exc) from exc

    # Token row carries linked_entity_type + linked_entity_id post-r70.
    # Email primitive paths only honor email_message linkage; reject
    # cross-primitive token-and-route mismatch defensively.
    if token_row.get("linked_entity_type") not in (None, "email_message"):
        raise HTTPException(
            status_code=400,
            detail=(
                "This token is not for an email action. "
                "Use the appropriate primitive's surface to act on it."
            ),
        )

    message = (
        db.query(EmailMessage)
        .filter(EmailMessage.id == token_row["linked_entity_id"])
        .first()
    )
    if not message:
        raise HTTPException(
            status_code=404, detail="Associated message no longer exists."
        )

    action = email_action_service.get_action_at_index(
        message, token_row["action_idx"]
    )

    # Resolve tenant branding (best-effort; fail open with defaults)
    from app.models.company import Company

    tenant = (
        db.query(Company).filter(Company.id == token_row["tenant_id"]).first()
    )
    tenant_name = tenant.name if tenant else "Bridgeable"
    tenant_brand = None
    if tenant:
        portal_settings = (tenant.settings or {}).get("portal") or {}
        tenant_brand = portal_settings.get("brand_color")

    # Audit log this view (no actor user_id — magic-link recipient is
    # not a Bridgeable user; recipient_email is the attribution).
    from app.services.email.account_service import _audit

    _audit(
        db,
        tenant_id=token_row["tenant_id"],
        actor_user_id=None,
        action="magic_link_viewed",
        entity_type="email_message",
        entity_id=message.id,
        changes={
            "action_idx": token_row["action_idx"],
            "action_type": token_row["action_type"],
            "recipient_email": token_row["recipient_email"],
            "click_count": token_row.get("click_count", 0),
            "consumed": consumed,
        },
    )
    db.commit()

    return MagicLinkActionDetails(
        tenant_name=tenant_name,
        tenant_brand_color=tenant_brand,
        sender_name=message.sender_name,
        sender_email=message.sender_email,
        subject=message.subject,
        sent_at=(message.sent_at.isoformat() if message.sent_at else None),
        action_idx=token_row["action_idx"],
        action_type=action["action_type"],
        action_target_type=action["action_target_type"],
        action_target_id=action["action_target_id"],
        action_metadata=action.get("action_metadata") or {},
        action_status=action["action_status"],
        recipient_email=token_row["recipient_email"],
        expires_at=token_row["expires_at"].isoformat(),
        consumed=consumed,
    )


@router.post(
    "/actions/{token}/commit", response_model=CommitActionResponse
)
def commit_magic_link_action(
    token: str,
    request: CommitActionRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """Commit an action via a magic-link token.

    Token consumption is atomic with the action commit — both happen
    in the same DB transaction so a partial failure leaves neither
    side stale.

    On success the email_action_tokens row is marked consumed_at,
    preventing re-use of the same token. Recipient who clicks the
    link again sees the consumed=True terminal state on the GET
    surface.
    """
    try:
        token_row = email_action_service.lookup_action_token(
            db, token=token
        )
    except (
        ActionTokenInvalid,
        ActionTokenExpired,
        ActionTokenAlreadyConsumed,
    ) as exc:
        raise _translate(exc) from exc

    message = (
        db.query(EmailMessage)
        .filter(EmailMessage.id == token_row["linked_entity_id"])
        .first()
    )
    if not message:
        raise HTTPException(
            status_code=404, detail="Associated message no longer exists."
        )

    # Action_idx on token must match the request — prevent token
    # being used for a different action via parameter manipulation.
    try:
        updated = email_action_service.commit_action(
            db,
            message=message,
            action_idx=token_row["action_idx"],
            outcome=request.outcome,
            actor_user_id=None,
            actor_email=token_row["recipient_email"],
            completion_note=request.completion_note,
            auth_method="magic_link",
            ip_address=_client_ip(http_request),
            user_agent=http_request.headers.get("user-agent"),
        )
    except (
        ActionError,
        ActionNotFound,
        ActionAlreadyCompleted,
    ) as exc:
        raise _translate(exc) from exc

    # Consume token atomically with commit
    email_action_service.consume_action_token(db, token=token)
    db.commit()

    target_status = _resolve_target_status(db, updated)
    return CommitActionResponse(
        action_idx=token_row["action_idx"],
        action_type=updated["action_type"],
        action_status=updated["action_status"],
        action_completed_at=updated.get("action_completed_at"),
        action_target_type=updated["action_target_type"],
        action_target_id=updated["action_target_id"],
        target_status=target_status,
    )


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _client_ip(request: Request) -> str | None:
    # Honor X-Forwarded-For first (Cloudflare/Railway proxy chain),
    # then direct client.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # Comma-separated chain — the client is the leftmost.
        return fwd.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return None


def _resolve_target_status(
    db: Session, action: dict
) -> str | None:
    """Best-effort lookup of the target entity's current status post-commit.

    Surfaces back to the UI so the caller can render the new state
    without an extra fetch.
    """
    target_type = action.get("action_target_type")
    target_id = action.get("action_target_id")
    if target_type == "quote" and target_id:
        from app.models.quote import Quote

        quote = (
            db.query(Quote.status).filter(Quote.id == target_id).first()
        )
        if quote:
            return quote[0]
    return None
