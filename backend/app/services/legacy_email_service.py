"""Legacy email service — sender config, proof emails, domain verification."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.legacy_email_settings import LegacyEmailSettings, LegacyFHEmailConfig
from app.models.legacy_proof import LegacyProof
from app.models.customer import Customer

logger = logging.getLogger(__name__)


# ── Settings helpers ─────────────────────────────────────────────────────────

def get_or_create_email_settings(db: Session, company_id: str) -> LegacyEmailSettings:
    settings = db.query(LegacyEmailSettings).filter(LegacyEmailSettings.company_id == company_id).first()
    if not settings:
        settings = LegacyEmailSettings(id=str(uuid.uuid4()), company_id=company_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def get_fh_email_config(db: Session, company_id: str, customer_id: str) -> LegacyFHEmailConfig | None:
    return db.query(LegacyFHEmailConfig).filter(
        LegacyFHEmailConfig.company_id == company_id,
        LegacyFHEmailConfig.customer_id == customer_id,
    ).first()


# ── Sender config ────────────────────────────────────────────────────────────

def get_sender_config(db: Session, company_id: str) -> dict:
    """Get the from/reply-to config based on sender tier."""
    from app.models.company import Company

    settings = get_or_create_email_settings(db, company_id)
    company = db.query(Company).filter(Company.id == company_id).first()
    company_name = company.name if company else "Bridgeable"

    if settings.sender_tier == "custom" and settings.domain_verified and settings.custom_from_email:
        return {
            "from_email": settings.custom_from_email,
            "from_name": settings.custom_from_name or company_name,
            "reply_to": None,
        }

    return {
        "from_email": "legacies@mail.getbridgeable.com",
        "from_name": company_name,
        "reply_to": settings.reply_to_email or None,
    }


def send_email(db: Session, company_id: str, to_addresses: list[str], subject: str, html_body: str, attachments: list | None = None) -> str:
    """Send email through DeliveryService (D-7) — routes to the
    registered email channel (Resend today, native email tomorrow).

    Every call lands in `document_deliveries` for audit.
    `to_addresses` is a list of recipients; we create one delivery row
    per recipient and return the first successful message id for
    backward compat with the legacy return shape.
    """
    from app.services.delivery import delivery_service

    sender = get_sender_config(db, company_id)
    from_name = sender["from_name"]
    reply_to = sender["reply_to"]

    # Convert legacy attachments (list of {filename, content}) to typed
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

    last_message_id = ""
    for addr in to_addresses:
        delivery = delivery_service.send(
            db,
            delivery_service.SendParams(
                company_id=company_id,
                channel="email",
                recipient=delivery_service.RecipientInput(
                    type="email_address", value=addr
                ),
                subject=subject,
                body=html_body,
                body_html=html_body,
                attachments=atts,
                reply_to=reply_to,
                from_name=from_name,
                caller_module="legacy_email_service.send_email",
            ),
        )
        if delivery.provider_message_id:
            last_message_id = delivery.provider_message_id
    return last_message_id


# ── Proof email ──────────────────────────────────────────────────────────────

def _substitute_vars(template: str, proof: LegacyProof, customer_name: str = "", deadline: str = "") -> str:
    return (
        template
        .replace("{name}", proof.inscription_name or "")
        .replace("{dates}", proof.inscription_dates or "")
        .replace("{additional}", proof.inscription_additional or "")
        .replace("{print_name}", proof.print_name or "Custom")
        .replace("{funeral_home}", customer_name)
        .replace("{service_date}", proof.service_date.strftime("%B %-d, %Y") if proof.service_date else "")
        .replace("{deadline}", deadline)
    )


def build_proof_email_html(
    proof: LegacyProof,
    company_name: str,
    header_color: str = "#0F2137",
    logo_url: str | None = None,
    custom_notes: str | None = None,
    watermark_enabled: bool = False,
    *,
    company_id: str | None = None,
) -> str:
    """Build the proof email HTML via the managed `email.legacy_proof`
    template (Phase D-2)."""
    from app.services.documents import document_renderer

    # The logo_html chunk is structural HTML — keep building it here;
    # the template accepts it as a |safe variable. Tenants can override
    # the whole template if they want a different logo layout.
    logo_html = (
        f'<img src="{logo_url}" alt="{company_name}" '
        f'style="max-width:200px;max-height:60px">'
        if logo_url
        else (
            f'<h1 style="margin:0;font-size:24px;font-weight:700;color:#fff">'
            f"{company_name}</h1>"
        )
    )

    service_date_str = (
        proof.service_date.strftime("%B %-d, %Y")
        if proof.service_date
        else ""
    )

    result = document_renderer.render_html(
        None,
        template_key="email.legacy_proof",
        context={
            "company_name": company_name,
            "header_color": header_color,
            "logo_html": logo_html,
            "proof_url": proof.proof_url or "",
            "inscription_name": proof.inscription_name or "",
            "inscription_dates": proof.inscription_dates or "",
            "inscription_additional": proof.inscription_additional or "",
            "print_name": proof.print_name or "",
            "service_date": service_date_str,
            "custom_notes": custom_notes or "",
            "watermark_enabled": bool(watermark_enabled),
        },
        company_id=company_id,
    )
    content = result.rendered_content
    return content if isinstance(content, str) else content.decode("utf-8")


def send_proof_email(
    db: Session,
    company_id: str,
    legacy_proof_id: str,
    recipient_override: list[str] | None = None,
    custom_notes: str | None = None,
    preview_only: bool = False,
) -> dict:
    """Send proof email to funeral home. Returns {html} if preview, {sent_to, message_id} if sent."""
    from app.models.company import Company
    from app.services.legacy_watermark import apply_watermark
    from app.services.legacy_delivery import get_or_create_settings as get_delivery_settings

    proof = db.query(LegacyProof).filter(LegacyProof.id == legacy_proof_id).first()
    if not proof:
        raise ValueError("Legacy proof not found")

    company = db.query(Company).filter(Company.id == company_id).first()
    company_name = company.name if company else "Bridgeable"

    email_settings = get_or_create_email_settings(db, company_id)
    delivery_settings = get_delivery_settings(db, company_id)

    # Get branding
    header_color = "#0F2137"
    logo = None
    if email_settings.use_invoice_branding:
        # Use company branding if available
        if hasattr(company, "logo_url") and company.logo_url:
            logo = company.logo_url
    else:
        header_color = email_settings.header_color or "#0F2137"
        logo = email_settings.logo_url

    # Build HTML
    html = build_proof_email_html(
        proof, company_name, header_color, logo, custom_notes,
        watermark_enabled=delivery_settings.watermark_enabled if delivery_settings else False,
        company_id=company_id,
    )

    if preview_only:
        return {"html": html}

    # Determine recipients — try CRM contacts first, then legacy JSONB
    if recipient_override:
        recipients = recipient_override
    elif proof.customer_id:
        recipients = []
        # 1) CRM contacts with receives_legacy_proofs flag
        customer_for_lookup = db.query(Customer).filter(Customer.id == proof.customer_id).first()
        if customer_for_lookup and customer_for_lookup.master_company_id:
            try:
                from app.services.crm.contact_service import get_proof_recipients
                recipients = get_proof_recipients(db, customer_for_lookup.master_company_id, company_id)
            except Exception:
                pass
        # 2) Fallback to legacy FH email config JSONB
        if not recipients:
            fh_config = get_fh_email_config(db, company_id, proof.customer_id)
            if fh_config and fh_config.recipients:
                recipients = [r["email"] for r in fh_config.recipients if r.get("email")]
        if not recipients:
            raise ValueError("No recipients configured for this funeral home")
    else:
        raise ValueError("No funeral home associated — specify recipients manually")

    # Resolve subject
    from app.utils.company_name_resolver import resolve_customer_name
    customer = db.query(Customer).filter(Customer.id == proof.customer_id).first() if proof.customer_id else None
    customer_name = resolve_customer_name(customer) if customer else ""

    subject = _substitute_vars(
        email_settings.proof_email_subject or "Legacy Proof — {name}",
        proof, customer_name,
    )

    # Attachments — proof JPEG with optional watermark
    attachments = []
    if proof.proof_url:
        try:
            from app.services import legacy_r2_client as r2
            proof_key = proof.proof_url.rsplit("/", 1)[-1]
            proof_bytes = r2.download_bytes(f"output/{proof.order_id or proof.id}/{proof_key}")

            if delivery_settings and delivery_settings.watermark_enabled:
                proof_bytes = apply_watermark(
                    proof_bytes,
                    watermark_enabled=True,
                    watermark_text=delivery_settings.watermark_text or "PROOF",
                    watermark_opacity=float(delivery_settings.watermark_opacity or 0.3),
                    watermark_position=delivery_settings.watermark_position or "center",
                )

            import base64
            attachments.append({
                "filename": f"Legacy Proof - {proof.inscription_name or 'Proof'}.jpg",
                "content": base64.b64encode(proof_bytes).decode(),
            })
        except Exception as e:
            logger.warning("Could not attach proof JPEG: %s", e)

    message_id = send_email(db, company_id, recipients, subject, html, attachments or None)

    # Update proof record
    proof.proof_emailed_at = datetime.now(timezone.utc)
    proof.proof_emailed_to = [{"email": r} for r in recipients]
    if proof.status == "proof_generated":
        proof.status = "proof_sent"
    db.commit()

    # CRM activity log
    try:
        from app.services.crm.activity_log_service import log_system_event
        log_system_event(
            db, company_id, None,
            activity_type="legacy_proof",
            title=f"Legacy proof sent — {proof.print_name}, RE: {proof.inscription_name or 'Unknown'}",
            related_legacy_proof_id=proof.id,
            customer_id=proof.customer_id,
        )
        db.commit()
    except Exception:
        pass

    return {"sent_to": recipients, "message_id": message_id}
