"""Calendar outbound orchestration — Phase W-4b Layer 1 Calendar Step 3.

End-to-end send pipeline: validate → resolve organizer + attendees →
compose VCALENDAR via itip_compose → call provider.send_event → persist
``provider_event_id`` + flip event.status when committing from
tentative → audit log. Single canonical entry points at ``send_event``
+ ``cancel_event`` (the API endpoints + future composition surface
both call these).

**Per canon §3.26.16.5 + §3.26.14.14.5 drafted-not-auto-sent discipline**:
  - Events drafted with `status="tentative"` require an explicit `send`
    commit before iTIP propagation.
  - Auto-confirmation rules per §3.26.16.18 only auto-flip `status`
    to "confirmed" when conditions met (internal-only, no cross-tenant
    or external attendees).
  - Operator agency preserved: state-change-generated events default
    to "tentative" + manual review unless auto-confirmation applies.

**Audit log discipline (§3.26.16.8)**: every outbound write logs
``event_sent`` (success) / ``event_send_failed`` (failure) / ``event_cancelled``
(cancellation). Body content NEVER logged; metadata only (recipient
count, provider, status). Recipient email addresses logged in
cleartext for operational visibility per §3.26.16.8 transparency
discipline.

**Provider routing**: same dispatch pattern as inbound — get_provider_class
+ send_event via account.provider_type. OAuth tokens injected at
runtime (not persisted in account_config) per Step 2 + Step 3 token
refresh discipline. Local provider's send_event is a functional no-op
per Q4 architectural decision.

**Mirrors Email r65 outbound_service shape verbatim** (subject
normalization helpers + send orchestration + audit log).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventInstanceOverride,
)
from app.models.user import User
from app.services.calendar import oauth_service
from app.services.calendar.account_service import (
    CalendarAccountError,
    CalendarAccountNotFound,
    CalendarAccountPermissionDenied,
    CalendarAccountValidation,
    _audit,
    user_has_access,
)
from app.services.calendar.itip_compose import (
    compose_cancel,
    compose_request,
)
from app.services.calendar.providers import get_provider_class

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class OutboundError(CalendarAccountError):
    http_status = 400


class OutboundProviderError(CalendarAccountError):
    http_status = 502


class OutboundDisabled(CalendarAccountError):
    http_status = 409


# ─────────────────────────────────────────────────────────────────────
# Send orchestration
# ─────────────────────────────────────────────────────────────────────


def send_event(
    db: Session,
    *,
    event: CalendarEvent,
    sender: User,
    organizer_email: str | None = None,
    organizer_name: str | None = None,
    embed_magic_links: bool = True,
    magic_link_action_type: str | None = None,
    magic_link_base_url: str | None = None,
) -> dict:
    """Commit a drafted event + propagate iTIP REQUEST per §3.26.16.5 Path 1.

    Args:
        db: SQLAlchemy session (caller commits).
        event: CalendarEvent to send. Must be in this caller's tenant.
            Status flips from "tentative" → "confirmed" on success.
            Already-confirmed events can be re-sent (re-issues iTIP
            REQUEST with current attendees + content).
        sender: User performing the send (audit actor + permission
            check via user_has_access requiring read_write+).
        organizer_email: optional override for ORGANIZER mailto. Defaults
            to the account's primary_email_address.
        organizer_name: optional display name for the organizer.
        embed_magic_links: per Q5 confirmed pre-build — default-on with
            opt-out. When True (default), each non-Bridgeable attendee
            on this event gets a platform_action_token issued + a
            magic-link URL composed; tokens are tied to the first
            pending action in event.action_payload['actions'] OR the
            caller-supplied magic_link_action_type if no actions
            present. Set False to suppress magic-link embedding for
            internal-only sends or when caller has already issued
            tokens out-of-band.
        magic_link_action_type: optional canonical action_type to use
            when event.action_payload has no pending actions but the
            caller wants tokens issued. Must be one of the 5 Calendar
            action_types per §3.26.16.17.
        magic_link_base_url: optional override for magic-link URL host
            (e.g. tenant-branded subdomain). Defaults to platform's
            FRONTEND_URL config.

    Returns dict with: ``status``, ``event_id``, ``provider_event_id``,
    ``recipient_count``, ``magic_links`` (list of {recipient_email,
    token, url} for each non-Bridgeable attendee that received a
    magic-link; empty list when embed_magic_links=False).

    Raises:
        OutboundDisabled: account.outbound_enabled is False
        CalendarAccountPermissionDenied: sender lacks read_write+ access
        OutboundProviderError: provider rejected the send
        OutboundError: validation or persistence failed
    """
    # 1. Resolve account + authorization.
    account = event.account
    if account is None:
        # Defensive: relationship may be unloaded.
        account = (
            db.query(CalendarAccount)
            .filter(CalendarAccount.id == event.account_id)
            .first()
        )
    if account is None:
        raise CalendarAccountNotFound(
            f"CalendarAccount {event.account_id!r} not found"
        )

    if not user_has_access(
        db,
        account_id=account.id,
        user_id=sender.id,
        minimum_level="read_write",
    ):
        raise CalendarAccountPermissionDenied(
            f"User {sender.id!r} lacks read_write access on calendar "
            f"account {account.id!r}; cannot send."
        )

    # 2. account.outbound_enabled gate per §3.26.16.5 outbound discipline.
    if not account.outbound_enabled:
        raise OutboundDisabled(
            f"Account {account.id!r} has outbound_enabled=False — tenant "
            "admin must enable outbound on the account first."
        )

    if event.status == "cancelled":
        raise OutboundError(
            f"Cannot send cancelled event {event.id!r}; create a new "
            "event instead."
        )

    # 3. Resolve organizer + attendees.
    org_email = (
        organizer_email
        or account.primary_email_address
    )
    org_name = organizer_name or account.display_name

    attendees = list(_load_attendees(db, event_id=event.id))

    # 3a. Step 4 — magic-link token issuance for non-Bridgeable
    # attendees per §3.26.16.17 + §14.10.5 magic-link contextual
    # surface. Per Q5 confirmed pre-build: default-on with
    # embed_magic_links=False opt-out.
    magic_links: list[dict[str, str]] = []
    if embed_magic_links:
        magic_links = _issue_magic_links_for_external_attendees(
            db,
            event=event,
            attendees=attendees,
            magic_link_action_type=magic_link_action_type,
            magic_link_base_url=magic_link_base_url,
        )

    # 4. Compose VCALENDAR per §3.26.16.5 Path 1.
    # SEQUENCE = 0 for first send; subsequent updates increment.
    # Step 3 ships first-send (sequence=0) only; update path (PATCH +
    # sequence > 0) ships at Step 3.1.
    sequence = 0
    vcalendar_text = compose_request(
        event,
        organizer_email=org_email,
        organizer_name=org_name,
        sequence=sequence,
        attendees=attendees,
    )

    # 5. Inject runtime credentials into provider_config (not persisted).
    runtime_config = dict(account.provider_config or {})
    if account.provider_type in ("google_calendar", "msgraph"):
        try:
            access_token = oauth_service.ensure_fresh_token(
                db, account=account
            )
            runtime_config["access_token"] = access_token
        except oauth_service.OAuthAuthError as exc:
            raise OutboundProviderError(
                f"OAuth token refresh failed: {exc}. Operator must "
                "reconnect the account."
            ) from exc

    # 6. Call provider.
    provider_cls = get_provider_class(account.provider_type)
    provider = provider_cls(
        runtime_config,
        db_session=db,
        account_id=account.id,
    )
    try:
        result = provider.send_event(
            vcalendar_text=vcalendar_text,
            method="REQUEST",
        )
    finally:
        try:
            provider.disconnect()
        except Exception:  # noqa: BLE001
            pass

    if not result.success:
        # Audit failure before raising.
        _audit(
            db,
            tenant_id=account.tenant_id,
            actor_user_id=sender.id,
            action="event_send_failed",
            entity_type="calendar_event",
            entity_id=event.id,
            changes={
                "account_id": account.id,
                "provider_type": account.provider_type,
                "recipient_count": len(attendees),
                "subject_length": len(event.subject or ""),
                "error_message": (result.error_message or "")[:300],
                "error_retryable": result.error_retryable,
            },
        )
        db.flush()
        raise OutboundProviderError(
            result.error_message or f"{account.provider_type} send failed"
        )

    # 7. Persist provider_event_id + flip status to confirmed.
    if result.provider_event_id and not event.provider_event_id:
        event.provider_event_id = result.provider_event_id
    if event.status == "tentative":
        event.status = "confirmed"
    db.flush()

    # 8. Audit success.
    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=sender.id,
        action="event_sent",
        entity_type="calendar_event",
        entity_id=event.id,
        changes={
            "account_id": account.id,
            "provider_type": account.provider_type,
            "method": "REQUEST",
            "sequence": sequence,
            "recipient_count": len(attendees),
            "provider_event_id": result.provider_event_id,
            "recipients": [a.email_address for a in attendees],
            "magic_links_issued": len(magic_links),
        },
    )
    db.flush()

    return {
        "status": "sent",
        "event_id": event.id,
        "provider_event_id": result.provider_event_id,
        "recipient_count": len(attendees),
        "magic_links": magic_links,
    }


def cancel_event(
    db: Session,
    *,
    event: CalendarEvent,
    sender: User,
    organizer_email: str | None = None,
    organizer_name: str | None = None,
) -> dict:
    """Cancel an event + propagate iTIP CANCEL per §3.26.16.5 Path 2.

    Per RFC 5546: STATUS=CANCELLED + sequence increment. Step 3 ships
    sequence=1 default (first send was sequence=0); caller may override
    if multiple updates preceded cancellation.

    Sets event.status = "cancelled" + writes audit row. The event row
    is NOT soft-deleted (is_active stays true) — preserves audit trail
    + RFC 5545 STATUS=CANCELLED tombstone semantics.
    """
    account = event.account or (
        db.query(CalendarAccount)
        .filter(CalendarAccount.id == event.account_id)
        .first()
    )
    if account is None:
        raise CalendarAccountNotFound(
            f"CalendarAccount {event.account_id!r} not found"
        )

    if not user_has_access(
        db,
        account_id=account.id,
        user_id=sender.id,
        minimum_level="read_write",
    ):
        raise CalendarAccountPermissionDenied(
            f"User {sender.id!r} lacks read_write access on calendar "
            f"account {account.id!r}; cannot cancel."
        )

    if not account.outbound_enabled:
        raise OutboundDisabled(
            f"Account {account.id!r} has outbound_enabled=False"
        )

    if event.status == "cancelled":
        # Idempotent — already cancelled, no-op.
        return {
            "status": "already_cancelled",
            "event_id": event.id,
        }

    org_email = organizer_email or account.primary_email_address
    org_name = organizer_name or account.display_name

    attendees = list(_load_attendees(db, event_id=event.id))

    # Compose iTIP CANCEL per §3.26.16.5 Path 2.
    sequence = 1  # First update post-original = sequence 1
    vcalendar_text = compose_cancel(
        event,
        organizer_email=org_email,
        organizer_name=org_name,
        sequence=sequence,
        attendees=attendees,
    )

    runtime_config = dict(account.provider_config or {})
    if account.provider_type in ("google_calendar", "msgraph"):
        try:
            access_token = oauth_service.ensure_fresh_token(
                db, account=account
            )
            runtime_config["access_token"] = access_token
        except oauth_service.OAuthAuthError as exc:
            raise OutboundProviderError(
                f"OAuth token refresh failed: {exc}"
            ) from exc

    provider_cls = get_provider_class(account.provider_type)
    provider = provider_cls(
        runtime_config,
        db_session=db,
        account_id=account.id,
    )
    try:
        result = provider.send_event(
            vcalendar_text=vcalendar_text,
            method="CANCEL",
        )
    finally:
        try:
            provider.disconnect()
        except Exception:  # noqa: BLE001
            pass

    if not result.success:
        _audit(
            db,
            tenant_id=account.tenant_id,
            actor_user_id=sender.id,
            action="event_cancel_failed",
            entity_type="calendar_event",
            entity_id=event.id,
            changes={
                "account_id": account.id,
                "provider_type": account.provider_type,
                "error_message": (result.error_message or "")[:300],
            },
        )
        db.flush()
        raise OutboundProviderError(
            result.error_message or f"{account.provider_type} cancel failed"
        )

    # Flip event.status = "cancelled".
    event.status = "cancelled"
    db.flush()

    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=sender.id,
        action="event_cancelled",
        entity_type="calendar_event",
        entity_id=event.id,
        changes={
            "account_id": account.id,
            "provider_type": account.provider_type,
            "method": "CANCEL",
            "sequence": sequence,
            "recipient_count": len(attendees),
            "recipients": [a.email_address for a in attendees],
        },
    )
    db.flush()

    return {
        "status": "cancelled",
        "event_id": event.id,
        "recipient_count": len(attendees),
    }


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _load_attendees(
    db: Session, *, event_id: str
) -> Iterable[CalendarEventAttendee]:
    """Load attendees for an event ordered by first_seen_at."""
    return (
        db.query(CalendarEventAttendee)
        .filter(CalendarEventAttendee.event_id == event_id)
        .order_by(CalendarEventAttendee.first_seen_at)
        .all()
    )


# ─────────────────────────────────────────────────────────────────────
# Step 4 — magic-link token issuance for non-Bridgeable attendees
# ─────────────────────────────────────────────────────────────────────


def _issue_magic_links_for_external_attendees(
    db: Session,
    *,
    event: CalendarEvent,
    attendees: list[CalendarEventAttendee],
    magic_link_action_type: str | None,
    magic_link_base_url: str | None,
) -> list[dict[str, str]]:
    """Per Q5 confirmed pre-build: default-on magic-link issuance hook.

    Issues a platform_action_token for every external (non-Bridgeable)
    attendee bound to a pending action in
    ``event.action_payload['actions']`` (or to a caller-supplied
    ``magic_link_action_type`` if no actions present).

    Per §3.26.11.9 magic-link participant scope canonical: external
    attendees who shouldn't have full platform access get magic-link
    URLs scoped to ONE action.

    **Non-Bridgeable detection**: ``CalendarEventAttendee.is_internal``
    is the canonical discriminator. ``is_internal=False`` attendees
    receive magic-links; ``is_internal=True`` attendees do not (they
    have full Bridgeable access via the inline action affordance).

    **Action resolution**: prefers the FIRST pending action in
    ``event.action_payload['actions']``. Caller can override via
    ``magic_link_action_type`` when issuing tokens for an action that
    hasn't been appended to action_payload yet (rare; mainly used by
    counter-proposal chaining where the new action is appended just
    before send).

    Returns list of {recipient_email, token, url, action_idx,
    action_type} for each external attendee that received a magic-link.
    Empty list if no external attendees OR no pending actions.
    """
    # Local import to avoid circular dependency (calendar package init
    # imports calendar_action_service which imports outbound_service).
    from app.services.calendar import calendar_action_service
    from app.config import settings as _settings

    # Resolve target action_idx + action_type.
    actions = calendar_action_service.get_event_actions(event)
    pending_actions: list[tuple[int, dict]] = [
        (idx, a) for idx, a in enumerate(actions)
        if a.get("action_status") == "pending"
    ]

    target_action_idx: int | None = None
    target_action_type: str | None = None
    if pending_actions:
        # Prefer first pending action.
        idx, action = pending_actions[0]
        target_action_idx = idx
        target_action_type = action["action_type"]
    elif magic_link_action_type:
        # Caller wants tokens issued against a specific action_type
        # without a pre-appended action shape (e.g. counter-proposal
        # chaining bridge). Synthesize idx=0 — caller is responsible
        # for appending the action shape pre-send.
        target_action_idx = 0
        target_action_type = magic_link_action_type

    if target_action_type is None or target_action_idx is None:
        # No actions to embed magic-links against; opt-out.
        return []

    if target_action_type not in calendar_action_service.ACTION_TYPES:
        # Caller supplied an invalid action_type.
        logger.warning(
            "outbound_service: magic_link_action_type=%r is not one of "
            "the 5 canonical Calendar action_types; skipping magic-link "
            "issuance.",
            target_action_type,
        )
        return []

    # Resolve magic-link base URL — caller override or platform default.
    base_url = magic_link_base_url or getattr(
        _settings, "FRONTEND_URL", None
    ) or "https://app.getbridgeable.com"

    issued: list[dict[str, str]] = []
    for attendee in attendees:
        # Skip Bridgeable-internal attendees per §3.26.11.9 (they have
        # full platform access via inline action affordance).
        if attendee.is_internal:
            continue

        token = calendar_action_service.issue_action_token(
            db,
            tenant_id=event.tenant_id,
            event_id=event.id,
            action_idx=target_action_idx,
            action_type=target_action_type,
            recipient_email=attendee.email_address,
        )
        url = calendar_action_service.build_magic_link_url(
            base_url=base_url,
            token=token,
            primitive_path="calendar",
        )
        issued.append(
            {
                "recipient_email": attendee.email_address,
                "token": token,
                "url": url,
                "action_idx": str(target_action_idx),
                "action_type": target_action_type,
            }
        )

    return issued
