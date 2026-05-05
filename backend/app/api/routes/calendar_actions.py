"""Calendar primitive operational-action affordance API —
Phase W-4b Layer 1 Step 4.

Two surfaces — same canonical commit logic underneath (parallel to
Email Step 4c ``email_actions.py`` shape post-Path-B substrate
consolidation):

  - **Inline action** (Bridgeable user, authenticated):
      ``POST /api/v1/calendar-events/{event_id}/actions/{action_idx}/commit``
    Acts on a Calendar action attached to an event in the user's
    tenant. Authorization comes from session/JWT.

  - **Magic-link** (non-Bridgeable recipient, token-authenticated):
      ``GET /api/v1/calendar/actions/{token}``       → action details
      ``POST /api/v1/calendar/actions/{token}/commit`` → commit outcome
    Public routes; token IS the auth. Token = single-action
    authorization; cannot navigate beyond contextual surface.

Both paths route through ``calendar_action_service.commit_action``
which dispatches to the registered ActionTypeDescriptor.commit_handler
for the action's action_type. State propagation per §3.26.16.18 +
audit per §3.26.15.8 happens inside the handler.

Per canon §3.26.16.17 + §14.10.5 — kill-the-portal discipline:
external recipients never enter a Bridgeable login flow; the
magic-link surface shows tenant-branded chrome + the canonical
action without exposing unrelated platform navigation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.calendar_primitive import CalendarEvent
from app.models.user import User
from app.services.calendar import calendar_action_service
from app.services.calendar.calendar_action_service import (
    ActionAlreadyCompleted,
    ActionError,
    ActionNotFound,
    ActionTokenAlreadyConsumed,
    ActionTokenExpired,
    ActionTokenInvalid,
    CrossPrimitiveTokenMismatch,
    PlatformActionError,
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
            "One of 'accept', 'reject', 'counter_propose' per §3.26.16.17"
        ),
    )
    completion_note: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Free-text note. Required when outcome='counter_propose' "
            "(per §3.26.16.17 + §3.26.16.20 iterative-negotiation pattern)."
        ),
    )
    counter_proposed_start_at: str | None = Field(
        default=None,
        description=(
            "ISO datetime — required when outcome='counter_propose'. "
            "Carries the proposed counter-time per §3.26.16.20."
        ),
    )
    counter_proposed_end_at: str | None = Field(
        default=None,
        description="ISO datetime — required when outcome='counter_propose'.",
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
            "Updated entity status post-commit (e.g. CalendarEvent.status, "
            "FHCase.service_date as ISO). Surfaces to UI for instant "
            "feedback without re-fetch."
        ),
    )
    counter_action_idx: int | None = Field(
        default=None,
        description=(
            "If outcome='counter_propose', the action_idx of the new "
            "chained action appended to event.action_payload per "
            "§3.26.16.20 iterative-negotiation pattern."
        ),
    )
    pairing_id: str | None = Field(
        default=None,
        description=(
            "If commit affected a cross_tenant_event_pairing, the pairing "
            "id for follow-on bilateral state propagation."
        ),
    )


class MagicLinkActionDetails(BaseModel):
    """Public surface response — magic-link landing page rendering data.

    Per §3.26.11.9 magic-link participant scope canonical: default
    lockdown — only the action's contextual surface visible (tenant
    identity + action details + Accept/Decline/Propose-alternative
    affordances). NO Bridgeable navigation; NO inbox; NO other events.
    """

    tenant_name: str
    tenant_brand_color: str | None
    organizer_name: str | None
    event_subject: str | None
    event_start_at: str
    event_end_at: str
    event_location: str | None
    action_idx: int
    action_type: str
    action_target_type: str
    action_target_id: str
    action_metadata: dict
    action_status: str
    recipient_email: str
    expires_at: str
    consumed: bool
    cascade_impact: dict | None = Field(
        default=None,
        description=(
            "Per §14.10.5 reschedule flow visual canon — when "
            "action_type='event_reschedule_proposal', the cascade impact "
            "disclosure ({linked_entity_count, paired_cross_tenant_count, "
            "...}) for surface rendering."
        ),
    )


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
            CrossPrimitiveTokenMismatch,
            PlatformActionError,
        ),
    ):
        return HTTPException(
            status_code=exc.http_status, detail=exc.message
        )
    raise exc


def _client_ip(request: Request) -> str | None:
    """Honor X-Forwarded-For first (Cloudflare/Railway proxy chain)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return None


def _parse_iso_optional(value: str | None) -> "datetime | None":
    if value is None:
        return None
    from datetime import datetime as _dt

    try:
        return _dt.fromisoformat(value)
    except ValueError as exc:
        raise ActionError(
            f"Invalid ISO datetime: {value!r} ({exc})"
        ) from exc


# ─────────────────────────────────────────────────────────────────────
# Inline action surface — Bridgeable users (authenticated)
# ─────────────────────────────────────────────────────────────────────


inline_router = APIRouter()


@inline_router.post(
    "/{event_id}/actions/{action_idx}/commit",
    response_model=CommitActionResponse,
)
def commit_inline_action(
    event_id: str,
    action_idx: int,
    request: CommitActionRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Commit a Calendar action from the authenticated event-detail surface.

    Authorization: caller's tenant must own the event. Cross-tenant
    callers get a 404 (existence-hiding).
    """
    event = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.id == event_id,
            CalendarEvent.tenant_id == current_user.company_id,
        )
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    try:
        counter_start = _parse_iso_optional(request.counter_proposed_start_at)
        counter_end = _parse_iso_optional(request.counter_proposed_end_at)
        result = calendar_action_service.commit_action(
            db,
            event=event,
            action_idx=action_idx,
            outcome=request.outcome,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            completion_note=request.completion_note,
            auth_method="bridgeable",
            ip_address=_client_ip(http_request),
            user_agent=http_request.headers.get("user-agent"),
            counter_proposed_start_at=counter_start,
            counter_proposed_end_at=counter_end,
        )
    except (
        ActionError,
        ActionNotFound,
        ActionAlreadyCompleted,
    ) as exc:
        raise _translate(exc) from exc

    db.commit()

    updated = result.updated_action
    return CommitActionResponse(
        action_idx=action_idx,
        action_type=updated["action_type"],
        action_status=updated["action_status"],
        action_completed_at=updated.get("action_completed_at"),
        action_target_type=updated["action_target_type"],
        action_target_id=updated["action_target_id"],
        target_status=result.target_status,
        counter_action_idx=result.counter_action_idx,
        pairing_id=result.pairing_id,
    )


# ─────────────────────────────────────────────────────────────────────
# Magic-link surface — public, token-authenticated
# ─────────────────────────────────────────────────────────────────────


public_router = APIRouter()


@public_router.get(
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
        landing page renders "already responded" terminal state)

    Successful lookups stamp ``last_clicked_at`` + increment
    ``click_count`` so we have audit visibility into multi-click
    patterns.

    For consumed/revoked tokens we still return action details (with
    consumed=True) so the surface can render an honest "already
    responded" terminal state instead of a generic error.
    """
    consumed = False
    try:
        token_row = calendar_action_service.lookup_action_token(
            db, token=token
        )
    except ActionTokenAlreadyConsumed:
        token_row = calendar_action_service.lookup_token_row_raw(
            db, token=token
        )
        if token_row is None:
            raise _translate(
                ActionTokenInvalid("Token not found.")
            ) from None
        consumed = True
    except (ActionTokenInvalid, ActionTokenExpired) as exc:
        raise _translate(exc) from exc

    # Calendar-only route — defensive cross-primitive guard.
    if token_row.get("linked_entity_type") != "calendar_event":
        raise HTTPException(
            status_code=400,
            detail=(
                "This token is not for a calendar action. "
                "Use the appropriate primitive's surface to act on it."
            ),
        )

    event = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.id == token_row["linked_entity_id"])
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Associated event no longer exists.",
        )

    try:
        action = calendar_action_service.get_action_at_index(
            event, token_row["action_idx"]
        )
    except ActionNotFound as exc:
        raise _translate(exc) from exc

    # Resolve tenant branding (best-effort; fail open with defaults).
    from app.models.company import Company

    tenant = (
        db.query(Company).filter(Company.id == token_row["tenant_id"]).first()
    )
    tenant_name = tenant.name if tenant else "Bridgeable"
    tenant_brand: str | None = None
    if tenant:
        portal_settings = (tenant.settings or {}).get("portal") or {}
        tenant_brand = portal_settings.get("brand_color")

    # Per §14.10.5 reschedule flow: cascade impact disclosure for
    # event_reschedule_proposal action_type.
    cascade_impact = None
    if action["action_type"] == "event_reschedule_proposal":
        # Read from action_metadata first (caller may have pre-computed);
        # fall back to live computation.
        metadata = action.get("action_metadata") or {}
        cascade_impact = metadata.get("cascade_impact") or (
            calendar_action_service.compute_reschedule_cascade(db, event)
        )

    # Audit log — magic-link viewed (no actor user_id; recipient_email
    # is attribution).
    from app.services.email.account_service import _audit as _email_audit
    from app.services.calendar.account_service import _audit as _calendar_audit

    _calendar_audit(
        db,
        tenant_id=token_row["tenant_id"],
        actor_user_id=None,
        action="calendar_magic_link_viewed",
        entity_type="calendar_event",
        entity_id=event.id,
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
        organizer_name=(
            (action.get("action_metadata") or {}).get("proposing_tenant_name")
        ),
        event_subject=event.subject,
        event_start_at=event.start_at.isoformat(),
        event_end_at=event.end_at.isoformat(),
        event_location=event.location,
        action_idx=token_row["action_idx"],
        action_type=action["action_type"],
        action_target_type=action["action_target_type"],
        action_target_id=action["action_target_id"],
        action_metadata=action.get("action_metadata") or {},
        action_status=action["action_status"],
        recipient_email=token_row["recipient_email"],
        expires_at=token_row["expires_at"].isoformat(),
        consumed=consumed,
        cascade_impact=cascade_impact,
    )


@public_router.post(
    "/actions/{token}/commit", response_model=CommitActionResponse
)
def commit_magic_link_action(
    token: str,
    request: CommitActionRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """Commit a Calendar action via a magic-link token.

    Token consumption is atomic with the action commit — both happen
    in the same DB transaction so a partial failure leaves neither
    side stale.

    On success the platform_action_tokens row is marked consumed_at,
    preventing re-use of the same token. Recipient who clicks the
    link again sees the consumed=True terminal state on the GET
    surface.
    """
    try:
        token_row = calendar_action_service.lookup_action_token(
            db, token=token
        )
    except (
        ActionTokenInvalid,
        ActionTokenExpired,
        ActionTokenAlreadyConsumed,
    ) as exc:
        raise _translate(exc) from exc

    if token_row.get("linked_entity_type") != "calendar_event":
        raise HTTPException(
            status_code=400,
            detail="This token is not for a calendar action.",
        )

    event = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.id == token_row["linked_entity_id"])
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Associated event no longer exists.",
        )

    try:
        counter_start = _parse_iso_optional(request.counter_proposed_start_at)
        counter_end = _parse_iso_optional(request.counter_proposed_end_at)
        result = calendar_action_service.commit_action(
            db,
            event=event,
            action_idx=token_row["action_idx"],
            outcome=request.outcome,
            actor_user_id=None,
            actor_email=token_row["recipient_email"],
            completion_note=request.completion_note,
            auth_method="magic_link",
            ip_address=_client_ip(http_request),
            user_agent=http_request.headers.get("user-agent"),
            counter_proposed_start_at=counter_start,
            counter_proposed_end_at=counter_end,
        )
    except (
        ActionError,
        ActionNotFound,
        ActionAlreadyCompleted,
    ) as exc:
        raise _translate(exc) from exc

    # Consume token atomically with commit.
    calendar_action_service.consume_action_token(db, token=token)
    db.commit()

    updated = result.updated_action
    return CommitActionResponse(
        action_idx=token_row["action_idx"],
        action_type=updated["action_type"],
        action_status=updated["action_status"],
        action_completed_at=updated.get("action_completed_at"),
        action_target_type=updated["action_target_type"],
        action_target_id=updated["action_target_id"],
        target_status=result.target_status,
        counter_action_idx=result.counter_action_idx,
        pairing_id=result.pairing_id,
    )
