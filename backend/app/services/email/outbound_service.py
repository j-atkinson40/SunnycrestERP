"""Outbound message orchestration — Phase W-4b Layer 1 Step 3.

End-to-end send pipeline: validate → build envelope → call provider
→ persist Message → update thread → audit log. Single canonical entry
point at ``send_message`` (the API endpoint + future composition
surface both call this).

**Per canon §3.26.15.5 + §3.26.15.13** the outbound message:
  - Stored as ``EmailMessage(direction="outbound")`` immediately on
    successful provider send (deduplication on later inbound sync of
    Sent folder via ``provider_message_id`` partial unique index)
  - Thread continuity preserved via ``in_reply_to_message_id`` FK +
    RFC 5322 ``In-Reply-To`` header on the wire
  - Subject normalization preserves thread on subject change (we
    never tweak subject ourselves on reply — caller-supplied subject
    is the wire-level subject)
  - Send-from-account defaults handled by caller (Step 4 composition
    UX picks the canonical "account that received original" per
    §3.26.15.13; Step 3 accepts whatever account_id the caller
    supplies)

**Audit log discipline (§3.26.15.8)**: every outbound send writes a
``email_audit_log`` row with action=``message_sent`` containing actor
+ tenant + account + thread + recipient_count + provider + status.
Body content NEVER logged (compliance baseline). Recipient addresses
ARE logged in cleartext for operational visibility — flag as audit-
restricted at retention time per privacy posture.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_primitive import (
    EmailAccount,
    EmailMessage,
    EmailParticipant,
    EmailThread,
    MessageParticipant,
)
from app.models.user import User
from app.services.email import oauth_service
from app.services.email.account_service import (
    EmailAccountError,
    EmailAccountNotFound,
    EmailAccountPermissionDenied,
    EmailAccountValidation,
    _audit,
    user_has_access,
)
from app.services.email.crypto import decrypt_credentials
from app.services.email.providers import get_provider_class

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class OutboundError(EmailAccountError):
    http_status = 400


class OutboundProviderError(EmailAccountError):
    http_status = 502


class OutboundDisabled(EmailAccountError):
    http_status = 409


class OutboundThreadNotFound(EmailAccountError):
    http_status = 404


# ─────────────────────────────────────────────────────────────────────
# Subject normalization — Re:/Fwd: prefix logic per §3.26.15.13
# ─────────────────────────────────────────────────────────────────────


def reply_subject(original_subject: str | None) -> str:
    """Build the canonical subject for a reply.

    Idempotent: ``Re: foo`` stays ``Re: foo`` (no double-prefixing).
    Empty/None original yields ``Re: `` (caller can treat as default).
    """
    base = (original_subject or "").strip()
    if base.lower().startswith("re:"):
        return base
    return f"Re: {base}".rstrip()


def forward_subject(original_subject: str | None) -> str:
    """Build the canonical subject for a forward.

    Idempotent: ``Fwd: foo`` stays ``Fwd: foo``. ``Re: foo`` becomes
    ``Fwd: Re: foo`` (preserves the reply-tree marker per RFC 5322).
    """
    base = (original_subject or "").strip()
    if base.lower().startswith("fwd:") or base.lower().startswith("fw:"):
        return base
    return f"Fwd: {base}".rstrip()


# ─────────────────────────────────────────────────────────────────────
# Send orchestration
# ─────────────────────────────────────────────────────────────────────


def send_message(
    db: Session,
    *,
    account: EmailAccount,
    sender: User,
    to: list[tuple[str, str | None]],
    subject: str,
    body_text: str | None = None,
    body_html: str | None = None,
    cc: list[tuple[str, str | None]] | None = None,
    bcc: list[tuple[str, str | None]] | None = None,
    thread_id: str | None = None,
    in_reply_to_message_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    action_tokens: list[str] | None = None,
) -> EmailMessage:
    """Send an outbound message + persist + audit.

    Args:
        account: EmailAccount to send through. Caller is responsible
            for confirming this is in the sender's tenant.
        sender: User performing the send (audit actor).
        to / cc / bcc: lists of (email_address, display_name).
        subject: wire-level subject; caller applies Re:/Fwd: prefix
            via ``reply_subject`` / ``forward_subject`` helpers.
        thread_id: when supplied, message attaches to existing thread
            (caller already validated existence + tenant scope).
            When None, a new thread is created.
        in_reply_to_message_id: FK to EmailMessage being replied to —
            populates ``EmailMessage.in_reply_to_message_id`` + the
            wire-level In-Reply-To header.
        attachments: list of dicts with keys ``filename``, ``bytes``,
            ``maintype``, ``subtype``. Bytes are passed through to
            the provider; never persisted as part of audit log.
        actions: optional list of operational-action affordance objects
            per §3.26.15.17 (Step 4c). Stored on
            ``EmailMessage.message_payload.actions``. Callers building
            a quote_approval action use
            ``email_action_service.build_quote_approval_action``.
        action_tokens: optional list parallel to ``actions`` — magic-
            link tokens (already embedded in body_html by caller) that
            this function persists as ``email_action_tokens`` rows
            for the primary (first ``to``) recipient. Length must
            match ``actions`` if both are supplied. None entries are
            permitted (action present but no magic-link token —
            Bridgeable-only recipients use the inline-action endpoint).

    Returns the persisted ``EmailMessage`` row.

    Raises:
        OutboundDisabled: account.outbound_enabled is False
        EmailAccountPermissionDenied: sender lacks read_write+ access
        OutboundProviderError: provider rejected the send
        OutboundError: validation or persistence failed
    """
    # 1. Authorization: read_write or admin required (read-only users
    # can't send through shared accounts).
    if not user_has_access(
        db,
        account_id=account.id,
        user_id=sender.id,
        required_level="read_write",
    ):
        raise EmailAccountPermissionDenied(
            f"User {sender.id!r} lacks read_write access on "
            f"account {account.id!r}; cannot send."
        )

    # 2. account.outbound_enabled gate
    if not account.outbound_enabled:
        raise OutboundDisabled(
            f"Account {account.id!r} has outbound_enabled=False — "
            "tenant admin must enable outbound on the account first."
        )

    if not to:
        raise OutboundError("At least one recipient required.")

    cc = cc or []
    bcc = bcc or []
    attachments = attachments or []
    actions = actions or []
    action_tokens = action_tokens or []
    if actions and action_tokens and len(actions) != len(action_tokens):
        raise OutboundError(
            "actions and action_tokens must have matching length when both "
            "supplied."
        )

    # 3. Resolve thread context
    thread: EmailThread | None = None
    parent_message: EmailMessage | None = None

    if in_reply_to_message_id:
        parent_message = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.id == in_reply_to_message_id,
                EmailMessage.tenant_id == account.tenant_id,
            )
            .first()
        )
        if not parent_message:
            raise OutboundThreadNotFound(
                f"in_reply_to_message_id {in_reply_to_message_id!r} not "
                "found in this tenant."
            )
        thread = parent_message.thread

    if thread_id and not thread:
        thread = (
            db.query(EmailThread)
            .filter(
                EmailThread.id == thread_id,
                EmailThread.tenant_id == account.tenant_id,
            )
            .first()
        )
        if not thread:
            raise OutboundThreadNotFound(
                f"thread_id {thread_id!r} not found in this tenant."
            )

    if thread is None:
        thread = EmailThread(
            id=str(uuid.uuid4()),
            tenant_id=account.tenant_id,
            account_id=account.id,
            subject=subject,
            participants_summary=[],
            first_message_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
            message_count=0,
        )
        db.add(thread)
        db.flush()

    # 4. Inject runtime credentials into provider_config (not persisted).
    runtime_config = dict(account.provider_config or {})

    if account.provider_type in ("gmail", "msgraph"):
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
    elif account.provider_type == "imap":
        creds = decrypt_credentials(account.encrypted_credentials)
        if not creds.get("imap_password"):
            raise OutboundProviderError(
                "IMAP/SMTP password not stored — operator must reconnect."
            )
        runtime_config["imap_password"] = creds["imap_password"]
    elif account.provider_type == "transactional":
        # TransactionalSendOnlyProvider needs db + company_id (deliberate
        # documented hack confined to that provider — see provider docs).
        runtime_config["__db__"] = db
        runtime_config["__company_id__"] = account.tenant_id

    # 5. Call provider
    provider_cls = get_provider_class(account.provider_type)
    provider = provider_cls(runtime_config)
    in_reply_to_provider_id = (
        parent_message.provider_message_id if parent_message else None
    )
    try:
        result = provider.send_message(
            from_address=account.email_address,
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            in_reply_to_provider_id=in_reply_to_provider_id,
            attachments=attachments,
        )
    finally:
        try:
            provider.disconnect()
        except Exception:  # noqa: BLE001
            pass

    if not result.success:
        # Audit failure before raising
        _audit(
            db,
            tenant_id=account.tenant_id,
            actor_user_id=sender.id,
            action="message_send_failed",
            entity_type="email_account",
            entity_id=account.id,
            changes={
                "thread_id": thread.id,
                "provider_type": account.provider_type,
                "recipient_count": len(to) + len(cc) + len(bcc),
                "subject_length": len(subject or ""),
                "error_message": (result.error_message or "")[:300],
                "error_retryable": result.error_retryable,
            },
        )
        db.flush()
        raise OutboundProviderError(
            result.error_message or f"{account.provider_type} send failed"
        )

    # 6. Persist outbound EmailMessage
    message = EmailMessage(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        tenant_id=account.tenant_id,
        account_id=account.id,
        provider_message_id=result.provider_message_id,
        in_reply_to_message_id=parent_message.id if parent_message else None,
        sender_email=account.email_address.lower(),
        sender_name=account.display_name,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        sent_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        direction="outbound",
        is_draft=False,
        is_internal_only=False,
        message_payload={
            "provider": account.provider_type,
            "provider_thread_id": result.provider_thread_id,
            # Step 4c — operational-action affordances per §3.26.15.17.
            # Empty list when no actions attached. Tokens NEVER stored
            # in message_payload (they live in email_action_tokens
            # table; payload only carries the action shape + status).
            "actions": list(actions),
        },
        entity_references=[],
    )
    db.add(message)
    db.flush()

    # 6.5. Persist action tokens (Step 4c). Caller pre-generated tokens
    # + embedded the magic-link URLs in the body before provider send;
    # we stamp the token rows now that message exists (FK requirement).
    if actions and action_tokens:
        # Magic-link tokens are issued for the primary (first) ``to``
        # recipient — the canonical "external approver" per
        # §3.26.15.17. cc/bcc do not get tokens (cannot approve).
        primary_recipient = to[0][0] if to else None
        if primary_recipient:
            from app.services.email.email_action_service import (
                ACTION_TYPES,
            )

            for action_idx, (action, token) in enumerate(
                zip(actions, action_tokens)
            ):
                if not token:
                    continue
                action_type = action.get("action_type")
                if action_type not in ACTION_TYPES:
                    raise OutboundError(
                        f"Unknown action_type: {action_type}"
                    )
                from app.services.email.email_action_service import (
                    _INSERT_ACTION_TOKEN_SQL,
                    TOKEN_TTL_DAYS,
                )

                expires_at = datetime.now(timezone.utc) + timedelta(
                    days=TOKEN_TTL_DAYS
                )
                db.execute(
                    _INSERT_ACTION_TOKEN_SQL,
                    {
                        "token": token,
                        "tenant_id": account.tenant_id,
                        "message_id": message.id,
                        "action_idx": action_idx,
                        "action_type": action_type,
                        "recipient_email": primary_recipient.lower().strip(),
                        "expires_at": expires_at,
                    },
                )
            db.flush()

    # 7. Resolve participants + create MessageParticipant rows. We
    # walk From + To/Cc/Bcc; reusing the inbound-side participant
    # resolution semantics for consistency.
    from app.services.email.ingestion import _resolve_participant

    def _link(role: str, pairs: list[tuple[str, str | None]]) -> None:
        for position, (addr, name) in enumerate(pairs):
            if not addr:
                continue
            participant, _ = _resolve_participant(
                db,
                thread_id=thread.id,
                email_address=addr,
                display_name=name,
                current_tenant_id=account.tenant_id,
            )
            db.add(
                MessageParticipant(
                    id=str(uuid.uuid4()),
                    message_id=message.id,
                    participant_id=participant.id,
                    role=role,
                    position=position,
                )
            )

    _link("from", [(account.email_address, account.display_name)])
    _link("to", to)
    _link("cc", cc)
    _link("bcc", bcc)
    db.flush()

    # 8. Update thread denormalized fields
    thread.message_count = (thread.message_count or 0) + 1
    thread.last_message_at = message.sent_at
    if not thread.first_message_at:
        thread.first_message_at = message.sent_at
    summary = list(thread.participants_summary or [])
    if account.email_address.lower() not in summary:
        summary.append(account.email_address.lower())
    for addr, _ in to + cc:
        addr_lower = addr.lower()
        if addr_lower not in summary:
            summary.append(addr_lower)
    if len(summary) > 25:
        summary = summary[-25:]
    thread.participants_summary = summary
    db.flush()

    # 9. Audit log
    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=sender.id,
        action="message_sent",
        entity_type="email_message",
        entity_id=message.id,
        changes={
            "thread_id": thread.id,
            "account_id": account.id,
            "provider_type": account.provider_type,
            "provider_message_id": result.provider_message_id,
            "recipient_count": len(to) + len(cc) + len(bcc),
            "to": [a for a, _ in to],
            "cc": [a for a, _ in cc],
            # Body content deliberately omitted per §3.26.15.8
            # (audit metadata only). Subject length captured as a
            # sanity signal without leaking content.
            "subject_length": len(subject or ""),
            "in_reply_to_message_id": (
                parent_message.id if parent_message else None
            ),
            "is_reply": parent_message is not None,
        },
    )
    db.flush()

    return message
