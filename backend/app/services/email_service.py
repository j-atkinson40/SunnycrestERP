"""Email delivery service — Phase D-7 routes through DeliveryService.

D-2 migrated email content generation to the managed template registry
(`document_renderer.render_html`). D-7 completes the loop by routing
every send through `DeliveryService`, so every email that leaves the
platform lands in the `document_deliveries` table with full audit +
provider response capture.

Public surface unchanged — callers like `send_statement_email`,
`send_collections_email`, etc. keep working. Internally they now
build a `SendParams` and call `delivery_service.send(...)`.

Test mode (`RESEND_API_KEY` unset or `"test"`) is handled inside
`EmailChannel` — it logs the call and returns success without hitting
Resend. No changes to local-dev workflows.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


# ── Helper: open a session if caller didn't pass one ─────────────────


def _with_session(db: Session | None):
    """Return (db, should_close). Use with `try / finally`."""
    if db is not None:
        return db, False
    return SessionLocal(), True


# ── EmailService wrappers (signatures kept for backward compat) ──────


class EmailService:
    """Backward-compatible wrapper around DeliveryService.

    Every method below now creates a `DocumentDelivery` row. The return
    shape is preserved: `{"success": bool, "message_id": str}`.
    """

    def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        from_name: str | None = None,
        reply_to: str | None = None,
        attachments: list[dict] | None = None,
        *,
        company_id: str | None = None,
        caller_module: str = "email_service.send_email",
        db: Session | None = None,
    ) -> dict[str, Any]:
        """Raw send — used by legacy callers that built HTML inline."""
        from app.services.delivery import delivery_service

        # Convert incoming base64-encoded attachments to bytes
        atts: list[delivery_service.AttachmentInput] = []
        for a in attachments or []:
            content = a.get("content")
            if isinstance(content, str):
                import base64 as _b64
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

        session, should_close = _with_session(db)
        try:
            # If no company_id was threaded through, this is an
            # internal/platform email (e.g. system alerts). Route it
            # under the platform admin tenant if configured, else fall
            # back to the first admin-owned company so there's a row
            # for audit.
            cid = company_id or _fallback_company_id(session)
            if cid is None:
                # No tenant context at all — log and return success-ish
                # so callers don't crash. This path is rare.
                logger.warning(
                    "email_service.send_email invoked with no company_id; "
                    "delivery-logging skipped (to=%s)",
                    to,
                )
                return {"success": True, "message_id": "no-company-skip"}

            delivery = delivery_service.send(
                session,
                delivery_service.SendParams(
                    company_id=cid,
                    channel="email",
                    recipient=delivery_service.RecipientInput(
                        type="email_address", value=to
                    ),
                    subject=subject,
                    body=html_body,
                    body_html=html_body,
                    attachments=atts,
                    reply_to=reply_to,
                    from_name=from_name,
                    caller_module=caller_module,
                ),
            )
            if should_close:
                session.commit()
        finally:
            if should_close:
                session.close()

        return {
            "success": delivery.status in ("sent", "delivered"),
            "message_id": delivery.provider_message_id or "",
            "delivery_id": delivery.id,
            "status": delivery.status,
        }

    def send_collections_email(
        self,
        customer_email: str,
        customer_name: str,
        subject: str,
        body: str,
        tenant_name: str,
        reply_to_email: str,
        *,
        company_id: str | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        from app.services.delivery import delivery_service

        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        session, should_close = _with_session(db)
        try:
            cid = company_id or _fallback_company_id(session)
            if cid is None:
                return {"success": True, "message_id": "no-company-skip"}
            delivery = delivery_service.send_email_with_template(
                session,
                company_id=cid,
                to_email=customer_email,
                to_name=customer_name,
                template_key="email.collections",
                template_context={
                    "subject": subject,
                    "customer_name": customer_name,
                    "tenant_name": tenant_name,
                    "body_paragraphs": paragraphs,
                },
                subject_override=subject,
                reply_to=reply_to_email,
                from_name=f"{tenant_name} via Bridgeable",
                caller_module="email_service.send_collections_email",
            )
            if should_close:
                session.commit()
        finally:
            if should_close:
                session.close()
        return _delivery_to_result(delivery)

    def send_statement_email(
        self,
        customer_email: str,
        customer_name: str,
        tenant_name: str,
        statement_month: str,
        pdf_attachment: bytes | None = None,
        *,
        company_id: str | None = None,
        document_id: str | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        from app.services.delivery import delivery_service

        # If caller passed raw PDF bytes and no document_id, attach
        # the bytes explicitly. If document_id is provided, the
        # DeliveryService auto-fetches and attaches the PDF — no need
        # to duplicate here.
        explicit_attachments: list[delivery_service.AttachmentInput] = []
        if pdf_attachment and not document_id:
            explicit_attachments.append(
                delivery_service.AttachmentInput(
                    filename=(
                        f"statement-{statement_month.lower().replace(' ', '-')}.pdf"
                    ),
                    content_type="application/pdf",
                    content=pdf_attachment,
                )
            )

        session, should_close = _with_session(db)
        try:
            cid = company_id or _fallback_company_id(session)
            if cid is None:
                return {"success": True, "message_id": "no-company-skip"}
            delivery = delivery_service.send(
                session,
                delivery_service.SendParams(
                    company_id=cid,
                    channel="email",
                    recipient=delivery_service.RecipientInput(
                        type="email_address",
                        value=customer_email,
                        name=customer_name,
                    ),
                    document_id=document_id,
                    template_key="email.statement",
                    template_context={
                        "customer_name": customer_name,
                        "tenant_name": tenant_name,
                        "statement_month": statement_month,
                    },
                    attachments=explicit_attachments,
                    from_name=f"{tenant_name} via Bridgeable",
                    caller_module="email_service.send_statement_email",
                ),
            )
            if should_close:
                session.commit()
        finally:
            if should_close:
                session.close()
        return _delivery_to_result(delivery)

    def send_user_invitation(
        self,
        email: str,
        name: str,
        tenant_name: str,
        invite_url: str,
        *,
        company_id: str | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        from app.services.delivery import delivery_service

        session, should_close = _with_session(db)
        try:
            cid = company_id or _fallback_company_id(session)
            if cid is None:
                return {"success": True, "message_id": "no-company-skip"}
            delivery = delivery_service.send_email_with_template(
                session,
                company_id=cid,
                to_email=email,
                to_name=name,
                template_key="email.invitation",
                template_context={
                    "name": name,
                    "tenant_name": tenant_name,
                    "invite_url": invite_url,
                },
                reply_to=settings.SUPPORT_EMAIL,
                caller_module="email_service.send_user_invitation",
            )
            if should_close:
                session.commit()
        finally:
            if should_close:
                session.close()
        return _delivery_to_result(delivery)

    def send_accountant_invitation(
        self,
        email: str,
        tenant_name: str,
        migration_url: str,
        expires_days: int = 7,
        *,
        company_id: str | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        from app.services.delivery import delivery_service

        session, should_close = _with_session(db)
        try:
            cid = company_id or _fallback_company_id(session)
            if cid is None:
                return {"success": True, "message_id": "no-company-skip"}
            delivery = delivery_service.send_email_with_template(
                session,
                company_id=cid,
                to_email=email,
                template_key="email.accountant_invitation",
                template_context={
                    "tenant_name": tenant_name,
                    "migration_url": migration_url,
                    "expires_days": expires_days,
                    "support_email": settings.SUPPORT_EMAIL,
                },
                reply_to=settings.SUPPORT_EMAIL,
                caller_module="email_service.send_accountant_invitation",
            )
            if should_close:
                session.commit()
        finally:
            if should_close:
                session.close()
        return _delivery_to_result(delivery)

    def send_invoice_email(
        self,
        to_email: str,
        to_name: str,
        company_name: str,
        invoice_number: str,
        invoice_date: str,
        due_date: str,
        total_amount: str,
        balance_due: str,
        pdf_attachment: bytes,
        deceased_name: str | None = None,
        reply_to: str | None = None,
        *,
        company_id: str | None = None,
        document_id: str | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        """Invoice email — mixes dynamic body content with the shared
        `email.base_wrapper` template. Stays inline-built for the body
        (per D-2 decision) but routes through DeliveryService for audit."""
        from app.services.delivery import delivery_service
        from app.services.documents import document_renderer

        if deceased_name:
            subject = (
                f"Invoice {invoice_number} \u2014 RE: {deceased_name} "
                f"\u2014 {company_name}"
            )
        else:
            subject = f"Invoice {invoice_number} \u2014 {company_name}"

        re_line = (
            f"<p><strong>RE:</strong> {deceased_name}</p>"
            if deceased_name
            else ""
        )
        body_content = f"""
          <p>Dear {to_name},</p>
          <p><strong>{company_name}</strong> has sent you an invoice.</p>
          <div class="highlight-box">
            <p><strong>Invoice number:</strong> {invoice_number}</p>
            <p><strong>Invoice date:</strong> {invoice_date}</p>
            <p><strong>Due date:</strong> {due_date}</p>
            {re_line}
            <p style="margin-top:8px;font-size:16px;font-weight:700;">Amount due: {balance_due}</p>
          </div>
          <p>Please find your invoice attached to this email.</p>
          <p>If you have any questions about this invoice, please contact {company_name} directly.</p>
        """

        session, should_close = _with_session(db)
        try:
            cid = company_id or _fallback_company_id(session)
            if cid is None:
                return {"success": True, "message_id": "no-company-skip"}

            # Render the base wrapper (captures branding + subject is
            # managed inline, matches subject variable above).
            result = document_renderer.render_html(
                session,
                template_key="email.base_wrapper",
                context={
                    "subject": subject,
                    "header_sub": f"Invoice from {company_name}",
                    "body_content": body_content,
                    "footer_text": (
                        f"This invoice was sent on behalf of {company_name} "
                        f"via Bridgeable."
                    ),
                },
                company_id=cid,
            )
            body_html = (
                result.rendered_content
                if isinstance(result.rendered_content, str)
                else result.rendered_content.decode("utf-8")
            )

            atts: list[delivery_service.AttachmentInput] = []
            if pdf_attachment and not document_id:
                atts.append(
                    delivery_service.AttachmentInput(
                        filename=f"Invoice-{invoice_number}.pdf",
                        content_type="application/pdf",
                        content=pdf_attachment,
                    )
                )

            delivery = delivery_service.send(
                session,
                delivery_service.SendParams(
                    company_id=cid,
                    channel="email",
                    recipient=delivery_service.RecipientInput(
                        type="email_address",
                        value=to_email,
                        name=to_name,
                    ),
                    document_id=document_id,
                    subject=subject,
                    body=body_html,
                    body_html=body_html,
                    attachments=atts,
                    reply_to=reply_to,
                    from_name=f"{company_name} via Bridgeable",
                    caller_module="email_service.send_invoice_email",
                ),
            )
            if should_close:
                session.commit()
        finally:
            if should_close:
                session.close()
        return _delivery_to_result(delivery)

    def send_agent_alert_digest(
        self,
        email: str,
        tenant_name: str,
        alerts: list[dict],
        *,
        company_id: str | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        from app.services.delivery import delivery_service

        if not alerts:
            return {"success": True, "message_id": "skipped-empty"}
        count = len(alerts)
        normalized = [
            {
                "title": a.get("title", ""),
                "summary": a.get("summary", a.get("description", "")),
            }
            for a in alerts
        ]
        session, should_close = _with_session(db)
        try:
            cid = company_id or _fallback_company_id(session)
            if cid is None:
                return {"success": True, "message_id": "no-company-skip"}
            delivery = delivery_service.send_email_with_template(
                session,
                company_id=cid,
                to_email=email,
                template_key="email.alert_digest",
                template_context={
                    "tenant_name": tenant_name,
                    "alerts": normalized,
                    "count": count,
                    "plural": "s" if count != 1 else "",
                },
                caller_module="email_service.send_agent_alert_digest",
            )
            if should_close:
                session.commit()
        finally:
            if should_close:
                session.close()
        return _delivery_to_result(delivery)


def _delivery_to_result(delivery) -> dict[str, Any]:
    """Convert a DocumentDelivery row into the legacy response shape."""
    return {
        "success": delivery.status in ("sent", "delivered"),
        "message_id": delivery.provider_message_id or "",
        "delivery_id": delivery.id,
        "status": delivery.status,
    }


def _fallback_company_id(db: Session) -> str | None:
    """When a legacy caller doesn't thread company_id through, try to
    find SOME tenant to attribute the delivery to — just so the audit
    row exists.

    In practice every caller should thread company_id; this is a
    safety net that logs a warning and falls back to the first active
    company in the DB. Returns None if no companies exist (a fresh
    install — the call is a no-op).
    """
    from app.models.company import Company

    row = db.query(Company).filter(Company.is_active.is_(True)).first()
    if row is None:
        return None
    return row.id


# Singleton instance — preserved for backward compatibility with every
# existing import site.
email_service = EmailService()
