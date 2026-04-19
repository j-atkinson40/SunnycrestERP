"""Signing notification emails — Phase D-4.

Routes through the existing EmailService + managed email.signing_*
templates. Every notification sent writes a `notification_sent`
signature_event with meta_json.notification_type for audit trail.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.company import Company
from app.models.signature import SignatureEnvelope, SignatureParty
from app.models.user import User
from app.services.documents import document_renderer

logger = logging.getLogger(__name__)


def _signer_url(token: str) -> str:
    """Public signer URL — token is the sole auth mechanism."""
    base = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
    return f"{base.rstrip('/')}/sign/{token}"


def _get_company_name(db: Session, envelope: SignatureEnvelope) -> str:
    company = (
        db.query(Company).filter_by(id=envelope.company_id).first()
    )
    return company.name if company else "Bridgeable"


def _get_sender_name(db: Session, envelope: SignatureEnvelope) -> str:
    user = (
        db.query(User).filter_by(id=envelope.created_by_user_id).first()
    )
    if user:
        full = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full or user.email
    return "Bridgeable"


def _render_email(
    db: Session,
    template_key: str,
    context: dict[str, Any],
    *,
    company_id: str,
) -> tuple[str, str | None]:
    """Render through the managed email template. Returns (body, subject).
    Subject falls back to a sensible default if the template has none."""
    result = document_renderer.render_html(
        db,
        template_key=template_key,
        context=context,
        company_id=company_id,
    )
    body = (
        result.rendered_content
        if isinstance(result.rendered_content, str)
        else result.rendered_content.decode("utf-8")
    )
    return body, result.rendered_subject


def _record_notification_event(
    db: Session,
    envelope: SignatureEnvelope,
    party: SignatureParty | None,
    notification_type: str,
    success: bool,
    message_id: str | None = None,
    error: str | None = None,
) -> None:
    from app.services.signing.signature_service import record_event

    meta: dict[str, Any] = {
        "notification_type": notification_type,
        "success": success,
    }
    if message_id:
        meta["message_id"] = message_id
    if error:
        meta["error"] = error[:500]
    record_event(
        db,
        envelope_id=envelope.id,
        event_type="notification_sent" if success else "notification_failed",
        party_id=party.id if party else None,
        meta=meta,
    )


def _send(
    db: Session,
    *,
    envelope: SignatureEnvelope,
    party: SignatureParty | None,
    to_email: str,
    template_key: str,
    context: dict[str, Any],
    notification_type: str,
    attachments: list[dict[str, Any]] | None = None,
    from_name: str | None = None,
) -> None:
    """Shared send helper — routes through DeliveryService (D-7) so
    every signing notification lands in `document_deliveries` with
    full linkage to the signature envelope."""
    from app.services.delivery import delivery_service

    # Convert any legacy base64 attachment dicts to AttachmentInput
    atts: list[delivery_service.AttachmentInput] = []
    import base64 as _b64

    for a in attachments or []:
        content = a.get("content")
        if isinstance(content, str):
            try:
                content = _b64.b64decode(content)
            except Exception:
                content = content.encode("utf-8")
        atts.append(
            delivery_service.AttachmentInput(
                filename=a.get("filename", "attachment"),
                content_type=a.get(
                    "content_type", "application/octet-stream"
                ),
                content=content or b"",
            )
        )

    # Determine the document to attach — for completion emails, attach
    # both the signed document AND certificate. notification_type
    # "completed" caller already builds the attachment list above, but
    # we also link the envelope's document_id so the DeliveryService
    # auto-attaches (avoids double-attach for completion by only
    # passing document_id when no explicit attachments were provided).
    document_id = envelope.document_id if not atts else None

    delivery = delivery_service.send(
        db,
        delivery_service.SendParams(
            company_id=envelope.company_id,
            channel="email",
            recipient=delivery_service.RecipientInput(
                type="email_address",
                value=to_email,
                name=party.display_name if party else None,
            ),
            document_id=document_id,
            template_key=template_key,
            template_context=context,
            subject=context.get("subject") or envelope.subject,
            attachments=atts,
            from_name=from_name,
            caller_module=f"signing.notification_service.{notification_type}",
            caller_signature_envelope_id=envelope.id,
        ),
    )

    ok = delivery.status in ("sent", "delivered")
    _record_notification_event(
        db,
        envelope,
        party,
        notification_type=notification_type,
        success=ok,
        message_id=delivery.provider_message_id,
        error=None if ok else (delivery.error_message or "Delivery failed"),
    )
    if ok and party is not None:
        party.notification_sent_count = (party.notification_sent_count or 0) + 1
        party.last_notification_sent_at = datetime.now(timezone.utc)


def send_invite(
    db: Session,
    envelope: SignatureEnvelope,
    party: SignatureParty,
) -> None:
    """Envelope sent (or turn advanced in sequential) — invite party to sign."""
    company_name = _get_company_name(db, envelope)
    sender_name = _get_sender_name(db, envelope)
    context = {
        "subject": f"Please sign: {envelope.subject}",
        "company_name": company_name,
        "sender_name": sender_name,
        "signer_name": party.display_name,
        "signer_role": party.role.replace("_", " ").title(),
        "signer_url": _signer_url(party.signer_token),
        "envelope_subject": envelope.subject,
        "envelope_description": envelope.description,
        "expires_at": (
            envelope.expires_at.strftime("%B %-d, %Y")
            if envelope.expires_at
            else "in 30 days"
        ),
    }
    _send(
        db,
        envelope=envelope,
        party=party,
        to_email=party.email,
        template_key="email.signing_invite",
        context=context,
        notification_type="invite",
        from_name=f"{sender_name} via Bridgeable",
    )


def send_completed(
    db: Session,
    envelope: SignatureEnvelope,
    party: SignatureParty,
) -> None:
    """Envelope fully signed — notify a party with signed PDF + certificate."""
    import base64

    company_name = _get_company_name(db, envelope)
    context = {
        "subject": f"Completed: {envelope.subject}",
        "company_name": company_name,
        "signer_name": party.display_name,
        "envelope_subject": envelope.subject,
    }

    attachments: list[dict[str, Any]] = []
    # Attach the current document version (now with signatures) + certificate
    try:
        from app.models.canonical_document import Document
        from app.services import legacy_r2_client

        doc = db.query(Document).filter_by(id=envelope.document_id).first()
        if doc is not None:
            try:
                pdf_bytes = legacy_r2_client.download_bytes(doc.storage_key)
                attachments.append(
                    {
                        "filename": f"Signed - {envelope.subject}.pdf",
                        "content": base64.b64encode(pdf_bytes).decode(),
                    }
                )
            except Exception:
                pass
        if envelope.certificate_document_id:
            cert = (
                db.query(Document)
                .filter_by(id=envelope.certificate_document_id)
                .first()
            )
            if cert is not None:
                try:
                    cert_bytes = legacy_r2_client.download_bytes(
                        cert.storage_key
                    )
                    attachments.append(
                        {
                            "filename": (
                                f"Certificate - {envelope.subject}.pdf"
                            ),
                            "content": base64.b64encode(cert_bytes).decode(),
                        }
                    )
                except Exception:
                    pass
    except Exception:
        pass

    _send(
        db,
        envelope=envelope,
        party=party,
        to_email=party.email,
        template_key="email.signing_completed",
        context=context,
        notification_type="completed",
        attachments=attachments or None,
    )


def send_declined(
    db: Session,
    envelope: SignatureEnvelope,
    decliner: SignatureParty,
) -> None:
    """Party declined — notify envelope creator."""
    creator = (
        db.query(User).filter_by(id=envelope.created_by_user_id).first()
    )
    if creator is None or not creator.email:
        return
    company_name = _get_company_name(db, envelope)
    context = {
        "subject": f"Declined: {envelope.subject}",
        "company_name": company_name,
        "envelope_subject": envelope.subject,
        "decliner_name": decliner.display_name,
        "decliner_role": decliner.role.replace("_", " ").title(),
        "decline_reason": decliner.decline_reason or "No reason provided",
    }
    _send(
        db,
        envelope=envelope,
        party=None,
        to_email=creator.email,
        template_key="email.signing_declined",
        context=context,
        notification_type="declined",
    )


def send_voided(
    db: Session,
    envelope: SignatureEnvelope,
    party: SignatureParty,
) -> None:
    """Envelope voided — notify a pending party."""
    company_name = _get_company_name(db, envelope)
    context = {
        "subject": f"Cancelled: {envelope.subject}",
        "company_name": company_name,
        "signer_name": party.display_name,
        "envelope_subject": envelope.subject,
        "void_reason": envelope.void_reason or "",
    }
    _send(
        db,
        envelope=envelope,
        party=party,
        to_email=party.email,
        template_key="email.signing_voided",
        context=context,
        notification_type="voided",
    )
