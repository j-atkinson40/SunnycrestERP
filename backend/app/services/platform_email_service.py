"""Platform email service — extends base email with tenant SMTP and audit logging.

Sending modes:
- "platform" (default) — uses Resend via the existing EmailService
- "smtp" — uses tenant's own SMTP server

All sends are logged in the email_sends table for audit purposes.
"""

import base64
import logging
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_send import EmailSend
from app.models.platform_email_settings import PlatformEmailSettings
from app.services.email_service import EmailService, _wrap_html

logger = logging.getLogger(__name__)


# ── Settings CRUD ────────────────────────────────────────────────────────

def get_email_settings(db: Session, tenant_id: str) -> PlatformEmailSettings | None:
    return db.query(PlatformEmailSettings).filter(
        PlatformEmailSettings.tenant_id == tenant_id
    ).first()


def get_or_create_email_settings(db: Session, tenant_id: str) -> PlatformEmailSettings:
    s = get_email_settings(db, tenant_id)
    if not s:
        s = PlatformEmailSettings(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def update_email_settings(db: Session, tenant_id: str, data: dict) -> PlatformEmailSettings:
    s = get_or_create_email_settings(db, tenant_id)
    allowed = (
        "sending_mode", "from_name", "reply_to_email",
        "smtp_host", "smtp_port", "smtp_username", "smtp_password_encrypted",
        "smtp_use_tls", "smtp_from_email",
        "invoice_bcc_email", "price_list_bcc_email",
    )
    for key in allowed:
        if key in data:
            setattr(s, key, data[key])
    db.commit()
    db.refresh(s)
    return s


def verify_smtp(db: Session, tenant_id: str) -> dict:
    """Test the SMTP connection. Returns {"success": bool, "error": str?}."""
    s = get_email_settings(db, tenant_id)
    if not s or not s.smtp_host:
        return {"success": False, "error": "SMTP not configured"}

    try:
        if s.smtp_use_tls:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10)

        if s.smtp_username and s.smtp_password_encrypted:
            server.login(s.smtp_username, s.smtp_password_encrypted)
        server.quit()

        s.smtp_verified = True
        s.smtp_verified_at = datetime.now(timezone.utc)
        db.commit()
        return {"success": True}
    except Exception as exc:
        s.smtp_verified = False
        db.commit()
        return {"success": False, "error": str(exc)}


# ── Audit logging ────────────────────────────────────────────────────────

def _log_email_send(
    db: Session,
    tenant_id: str,
    user_id: str | None,
    email_type: str,
    to_email: str,
    to_name: str | None,
    subject: str | None,
    status: str,
    error_message: str | None = None,
    attachment_type: str | None = None,
    attachment_name: str | None = None,
    reference_id: str | None = None,
    reference_type: str | None = None,
) -> EmailSend:
    send = EmailSend(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        sent_by_user_id=user_id,
        email_type=email_type,
        to_email=to_email,
        to_name=to_name,
        subject=subject,
        status=status,
        error_message=error_message,
        attachment_type=attachment_type,
        attachment_name=attachment_name,
        reference_id=reference_id,
        reference_type=reference_type,
        sent_at=datetime.now(timezone.utc) if status == "sent" else None,
    )
    db.add(send)
    db.commit()
    return send


def get_email_sends(
    db: Session,
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
    email_type: str | None = None,
) -> list[EmailSend]:
    q = db.query(EmailSend).filter(EmailSend.tenant_id == tenant_id)
    if email_type:
        q = q.filter(EmailSend.email_type == email_type)
    return q.order_by(EmailSend.created_at.desc()).offset(offset).limit(limit).all()


# ── SMTP sending ─────────────────────────────────────────────────────────

def _send_via_smtp(
    settings_obj: PlatformEmailSettings,
    to_email: str,
    subject: str,
    html_body: str,
    attachments: list[dict] | None = None,
) -> dict[str, Any]:
    """Send via tenant SMTP. Returns {"success": bool, "error"?: str}."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{settings_obj.from_name or 'Bridgeable'} <{settings_obj.smtp_from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        if settings_obj.reply_to_email:
            msg["Reply-To"] = settings_obj.reply_to_email

        msg.attach(MIMEText(html_body, "html"))

        if attachments:
            for att in attachments:
                part = MIMEApplication(
                    base64.b64decode(att["content"]) if isinstance(att["content"], str) else att["content"],
                    Name=att.get("filename", "attachment"),
                )
                part["Content-Disposition"] = f'attachment; filename="{att.get("filename", "attachment")}"'
                msg.attach(part)

        if settings_obj.smtp_use_tls:
            server = smtplib.SMTP(settings_obj.smtp_host, settings_obj.smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP(settings_obj.smtp_host, settings_obj.smtp_port, timeout=15)

        if settings_obj.smtp_username and settings_obj.smtp_password_encrypted:
            server.login(settings_obj.smtp_username, settings_obj.smtp_password_encrypted)

        server.sendmail(msg["From"], [to_email], msg.as_string())
        server.quit()
        return {"success": True}
    except Exception as exc:
        logger.error("SMTP send failed to %s: %s", to_email, exc)
        return {"success": False, "error": str(exc)}


# ── Unified send ─────────────────────────────────────────────────────────

_platform_email_service = EmailService()


def send_tenant_email(
    db: Session,
    tenant_id: str,
    to_email: str,
    subject: str,
    html_body: str,
    user_id: str | None = None,
    email_type: str = "general",
    to_name: str | None = None,
    attachments: list[dict] | None = None,
    reference_id: str | None = None,
    reference_type: str | None = None,
    attachment_name: str | None = None,
) -> dict[str, Any]:
    """Send an email using the tenant's configured method, with audit logging."""
    es = get_email_settings(db, tenant_id)

    if es and es.sending_mode == "smtp" and es.smtp_verified and es.smtp_host:
        result = _send_via_smtp(es, to_email, subject, html_body, attachments)
    else:
        from_name = (es.from_name if es else None) or None
        reply_to = (es.reply_to_email if es else None) or None
        result = _platform_email_service.send_email(
            to=to_email,
            subject=subject,
            html_body=html_body,
            from_name=from_name,
            reply_to=reply_to,
            attachments=attachments,
            company_id=tenant_id,
            db=db,
        )

    status = "sent" if result.get("success") else "failed"
    _log_email_send(
        db, tenant_id, user_id, email_type, to_email, to_name, subject,
        status=status,
        error_message=result.get("error"),
        attachment_type="pdf" if attachments else None,
        attachment_name=attachment_name,
        reference_id=reference_id,
        reference_type=reference_type,
    )

    return result


# ── Price list email ─────────────────────────────────────────────────────

def _price_list_html(
    company_name: str,
    recipient_name: str | None,
    version_label: str,
    effective_date: str,
    custom_message: str | None = None,
) -> str:
    greeting = f"Dear {recipient_name}," if recipient_name else "Dear Valued Customer,"
    msg_block = f"<p>{custom_message}</p>" if custom_message else ""
    body_content = f"""
      <p>{greeting}</p>
      <p><strong>{company_name}</strong> has published an updated price list.</p>
      <div class="highlight-box">
        <p><strong>Version:</strong> {version_label}</p>
        <p><strong>Effective date:</strong> {effective_date}</p>
      </div>
      {msg_block}
      <p>Please find the updated price list attached to this email as a PDF.</p>
      <p>If you have any questions about pricing, please contact {company_name} directly.</p>
    """
    return _wrap_html(
        subject=f"Updated Price List — {company_name}",
        header_sub=f"Price Update from {company_name}",
        body_content=body_content,
        footer_text=f"This price list was sent on behalf of {company_name} via Bridgeable.",
    )


def send_price_list_email(
    db: Session,
    tenant_id: str,
    user_id: str,
    to_email: str,
    to_name: str | None,
    company_name: str,
    version_id: str,
    version_label: str,
    effective_date: str,
    pdf_bytes: bytes,
    custom_message: str | None = None,
) -> dict[str, Any]:
    """Send a price list PDF to a recipient."""
    subject = f"Updated Price List — {company_name}"
    html = _price_list_html(company_name, to_name, version_label, effective_date, custom_message)

    attachments = [{
        "filename": f"Price-List-{version_label.replace(' ', '-')}.pdf",
        "content": base64.b64encode(pdf_bytes).decode(),
        "content_type": "application/pdf",
    }]

    return send_tenant_email(
        db, tenant_id, to_email, subject, html,
        user_id=user_id,
        email_type="price_list",
        to_name=to_name,
        attachments=attachments,
        reference_id=version_id,
        reference_type="price_list_version",
        attachment_name=attachments[0]["filename"],
    )
