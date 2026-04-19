"""DeliveryService orchestrator — Phase D-7.

Every email / SMS / future-channel send flows through `send()`. Creates
a `DocumentDelivery` row per attempt, resolves content (via managed
template or caller-supplied body), dispatches to the channel, writes
back provider results, and handles inline retry for retryable errors.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.canonical_document import Document
from app.models.document_delivery import DocumentDelivery
from app.services import legacy_r2_client
from app.services.delivery import (
    Attachment,
    ChannelSendRequest,
    Recipient,
    UnknownChannelError,
    get_channel,
)

logger = logging.getLogger(__name__)


# ── Input shapes ─────────────────────────────────────────────────────


@dataclass
class RecipientInput:
    """User-facing recipient spec. Matches the DeliveryChannel Recipient
    shape but exposed at the DeliveryService input boundary."""

    type: str  # email_address | phone_number | user_id | contact_id
    value: str
    name: str | None = None


@dataclass
class AttachmentInput:
    filename: str
    content_type: str
    content: bytes


@dataclass
class SendParams:
    """All args for a send. Dataclass so tests + the /resend endpoint
    can round-trip params cleanly."""

    company_id: str
    channel: str  # "email" | "sms"
    recipient: RecipientInput
    document_id: str | None = None
    subject: str | None = None
    template_key: str | None = None
    template_context: dict[str, Any] | None = None
    body: str | None = None
    body_html: str | None = None
    attachments: list[AttachmentInput] = field(default_factory=list)
    reply_to: str | None = None
    from_name: str | None = None
    caller_module: str | None = None
    caller_workflow_run_id: str | None = None
    caller_workflow_step_id: str | None = None
    caller_intelligence_execution_id: str | None = None
    caller_signature_envelope_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3


class DeliveryError(Exception):
    """Raised only for programmer errors (missing content, unknown
    channel, etc). Send failures DON'T raise — they return a
    `DocumentDelivery` row with status=failed so admin UI can show
    them."""

    def __init__(self, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status


# ── Content resolution ──────────────────────────────────────────────


def _resolve_content(
    db: Session,
    params: SendParams,
) -> tuple[str, str | None, str | None]:
    """Return (body, body_html, subject). If template_key, render via
    DocumentRenderer (email templates → HTML; text templates → plain).
    Otherwise use caller-supplied body / body_html / subject verbatim."""
    if params.template_key:
        from app.services.documents import document_renderer

        result = document_renderer.render_html(
            db,
            template_key=params.template_key,
            context=params.template_context or {},
            company_id=params.company_id,
        )
        body_html = (
            result.rendered_content
            if isinstance(result.rendered_content, str)
            else result.rendered_content.decode("utf-8")
        )
        # For email, plain body can be a text-stripped variant; for
        # now pass the HTML in both slots — EmailChannel uses HTML.
        body = body_html
        subject = params.subject or result.rendered_subject
        return body, body_html, subject

    if params.body is None and params.body_html is None:
        raise DeliveryError(
            "Either `template_key` or `body` / `body_html` must be provided"
        )

    body = params.body or (params.body_html or "")
    return body, params.body_html, params.subject


# ── Attachment resolution ───────────────────────────────────────────


def _resolve_attachments(
    db: Session,
    params: SendParams,
    channel,
    document: Document | None,
) -> list[Attachment]:
    """Combine user-supplied attachments with an auto-fetch of the
    Document PDF when `document_id` set AND channel supports
    attachments. For SMS-like channels, skip the document attachment
    (body renderer should include a link instead)."""
    result: list[Attachment] = [
        Attachment(
            filename=a.filename,
            content_type=a.content_type,
            content=a.content,
        )
        for a in params.attachments
    ]
    if document is None or not channel.supports_attachments():
        return result

    # Fetch the document bytes from R2 (best-effort — on failure we
    # still send without the attachment and log).
    try:
        pdf_bytes = legacy_r2_client.download_bytes(document.storage_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Delivery attachment fetch failed for doc %s: %s",
            document.id,
            exc,
        )
        return result

    filename_base = (
        (document.title or document.document_type or "document")
        .replace("/", "-")
        .replace("\\", "-")
    )[:200]
    result.insert(
        0,
        Attachment(
            filename=f"{filename_base}.pdf",
            content_type=document.mime_type or "application/pdf",
            content=pdf_bytes,
        ),
    )
    return result


# ── Main entry point ────────────────────────────────────────────────


def send(
    db: Session,
    params: SendParams,
) -> DocumentDelivery:
    """Send a message through the chosen channel. Always returns a
    `DocumentDelivery` row; never raises on send failure — check
    `.status` to see if it succeeded.

    Raises `DeliveryError` only for programmer errors (unknown
    channel, missing content).
    """
    # Validate channel + resolve implementation
    try:
        channel = get_channel(params.channel)
    except UnknownChannelError as exc:
        raise DeliveryError(str(exc), http_status=400)

    # Resolve Document (for attachment + linkage)
    document: Document | None = None
    if params.document_id:
        document = (
            db.query(Document)
            .filter(
                Document.id == params.document_id,
                Document.company_id == params.company_id,
            )
            .first()
        )
        if document is None:
            raise DeliveryError(
                "document_id not found or not visible to this tenant",
                http_status=404,
            )

    # Resolve content (templates render here; direct body pass-through)
    body, body_html, subject = _resolve_content(db, params)

    # Resolve attachments
    attachments = _resolve_attachments(db, params, channel, document)

    # Create the delivery row (status=pending) before dispatch
    delivery = DocumentDelivery(
        id=str(uuid.uuid4()),
        company_id=params.company_id,
        document_id=params.document_id,
        channel=params.channel,
        recipient_type=params.recipient.type,
        recipient_value=params.recipient.value,
        recipient_name=params.recipient.name,
        subject=subject,
        body_preview=body[:500] if body else None,
        template_key=params.template_key,
        status="pending",
        provider=getattr(channel, "provider", None),
        max_retries=params.max_retries,
        caller_module=params.caller_module,
        caller_workflow_run_id=params.caller_workflow_run_id,
        caller_workflow_step_id=params.caller_workflow_step_id,
        caller_intelligence_execution_id=params.caller_intelligence_execution_id,
        caller_signature_envelope_id=params.caller_signature_envelope_id,
        metadata_json=params.metadata or None,
    )
    db.add(delivery)
    db.flush()

    # Dispatch with inline retry on retryable errors
    channel_request = ChannelSendRequest(
        recipient=Recipient(
            type=params.recipient.type,
            value=params.recipient.value,
            name=params.recipient.name,
        ),
        subject=subject,
        body=body,
        body_html=body_html,
        attachments=attachments or None,
        reply_to=params.reply_to,
        from_name=params.from_name,
        metadata=dict(params.metadata) if params.metadata else {},
    )

    attempt = 0
    while True:
        attempt += 1
        delivery.status = "sending"
        db.flush()

        try:
            result = channel.send(channel_request)
        except Exception as exc:  # noqa: BLE001
            # Channel raised — treat as retryable network-ish error
            result = None
            exc_msg = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Channel.send raised on attempt %d: %s", attempt, exc_msg
            )
            if attempt <= params.max_retries:
                delivery.retry_count = attempt
                db.flush()
                continue
            _mark_failed(
                delivery,
                error_message=exc_msg,
                error_code="UNHANDLED_EXCEPTION",
                provider_response=None,
            )
            db.flush()
            return delivery

        if result.success:
            now = datetime.now(timezone.utc)
            delivery.status = "sent"
            delivery.sent_at = now
            delivery.provider_message_id = result.provider_message_id
            delivery.provider_response = result.provider_response
            delivery.retry_count = attempt - 1  # successful attempt count
            db.flush()
            return delivery

        # Failure
        if result.retryable and attempt <= params.max_retries:
            delivery.retry_count = attempt
            delivery.error_message = result.error_message
            delivery.error_code = result.error_code
            delivery.provider_response = result.provider_response
            db.flush()
            continue

        # Non-retryable OR retries exhausted → terminal
        # Stubs (like SMS) return success=False, retryable=False —
        # use status="rejected" for those so admin UI distinguishes
        # "provider refused" from "something broke".
        terminal_status = "rejected" if result.error_code == "NOT_IMPLEMENTED" else "failed"
        delivery.status = terminal_status
        delivery.failed_at = datetime.now(timezone.utc)
        delivery.error_message = result.error_message
        delivery.error_code = result.error_code
        delivery.provider_response = result.provider_response
        delivery.retry_count = attempt - 1 if attempt > 1 else 0
        db.flush()
        return delivery


def _mark_failed(
    delivery: DocumentDelivery,
    *,
    error_message: str,
    error_code: str,
    provider_response: dict[str, Any] | None,
) -> None:
    delivery.status = "failed"
    delivery.failed_at = datetime.now(timezone.utc)
    delivery.error_message = error_message[:2000] if error_message else None
    delivery.error_code = error_code
    if provider_response is not None:
        delivery.provider_response = provider_response


# ── Convenience builders for migrated callers ────────────────────────


def send_email_with_template(
    db: Session,
    *,
    company_id: str,
    to_email: str,
    to_name: str | None = None,
    template_key: str,
    template_context: dict[str, Any],
    document_id: str | None = None,
    subject_override: str | None = None,
    reply_to: str | None = None,
    from_name: str | None = None,
    caller_module: str,
    caller_signature_envelope_id: str | None = None,
    caller_workflow_run_id: str | None = None,
    caller_intelligence_execution_id: str | None = None,
) -> DocumentDelivery:
    """Shortcut used by migrated email callers (signing notifications,
    statement emails, etc.). Encapsulates the recipient wrap."""
    return send(
        db,
        SendParams(
            company_id=company_id,
            channel="email",
            recipient=RecipientInput(
                type="email_address", value=to_email, name=to_name
            ),
            document_id=document_id,
            template_key=template_key,
            template_context=template_context,
            subject=subject_override,
            reply_to=reply_to,
            from_name=from_name,
            caller_module=caller_module,
            caller_signature_envelope_id=caller_signature_envelope_id,
            caller_workflow_run_id=caller_workflow_run_id,
            caller_intelligence_execution_id=caller_intelligence_execution_id,
        ),
    )


def send_email_raw(
    db: Session,
    *,
    company_id: str,
    to_email: str,
    subject: str,
    body_html: str,
    to_name: str | None = None,
    attachments: list[AttachmentInput] | None = None,
    reply_to: str | None = None,
    from_name: str | None = None,
    caller_module: str,
) -> DocumentDelivery:
    """Shortcut for emails that build HTML inline (e.g. invoice emails
    that mix static branding with dynamic highlight boxes). Still goes
    through the channel + audit trail."""
    return send(
        db,
        SendParams(
            company_id=company_id,
            channel="email",
            recipient=RecipientInput(
                type="email_address", value=to_email, name=to_name
            ),
            subject=subject,
            body=body_html,
            body_html=body_html,
            attachments=attachments or [],
            reply_to=reply_to,
            from_name=from_name,
            caller_module=caller_module,
        ),
    )
