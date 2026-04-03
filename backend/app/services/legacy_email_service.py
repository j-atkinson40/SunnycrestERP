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
    """Send email via Resend API."""
    try:
        import resend
        sender = get_sender_config(db, company_id)
        from_str = f"{sender['from_name']} <{sender['from_email']}>"

        params: dict = {
            "from": from_str,
            "to": to_addresses,
            "subject": subject,
            "html": html_body,
        }
        if sender["reply_to"]:
            params["reply_to"] = sender["reply_to"]
        if attachments:
            params["attachments"] = attachments

        result = resend.Emails.send(params)
        return result.get("id", "")
    except Exception as e:
        logger.exception("Failed to send legacy email: %s", e)
        raise


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
) -> str:
    """Build the proof email HTML."""
    details = []
    if proof.inscription_name:
        details.append(f"<tr><td style='color:#64748B;padding:4px 12px 4px 0'>Name</td><td style='font-weight:600'>{proof.inscription_name}</td></tr>")
    if proof.inscription_dates:
        details.append(f"<tr><td style='color:#64748B;padding:4px 12px 4px 0'>Dates</td><td>{proof.inscription_dates}</td></tr>")
    if proof.inscription_additional:
        details.append(f"<tr><td style='color:#64748B;padding:4px 12px 4px 0'>Additional</td><td>{proof.inscription_additional}</td></tr>")
    if proof.print_name:
        details.append(f"<tr><td style='color:#64748B;padding:4px 12px 4px 0'>Print</td><td>{proof.print_name}</td></tr>")
    if proof.service_date:
        details.append(f"<tr><td style='color:#64748B;padding:4px 12px 4px 0'>Service</td><td>{proof.service_date.strftime('%B %-d, %Y')}</td></tr>")

    logo_html = f'<img src="{logo_url}" alt="{company_name}" style="max-width:200px;max-height:60px">' if logo_url else f'<h1 style="margin:0;font-size:24px;font-weight:700;color:#fff">{company_name}</h1>'

    notes_html = ""
    if custom_notes:
        notes_html = f'<div style="background:#F1F5F9;border-radius:8px;padding:16px;margin-top:20px"><p style="font-size:13px;color:#64748B;margin:0 0 4px">Note from {company_name}:</p><p style="font-size:14px;color:#1a1a1a;margin:0">{custom_notes}</p></div>'

    watermark_note = ""
    if watermark_enabled:
        watermark_note = '<p style="font-size:12px;color:#94A3B8;margin-top:16px"><em>The watermark will not appear on the final printed vault.</em></p>'

    proof_img = f'<img src="{proof.proof_url}" alt="Legacy Proof" style="width:100%;max-width:600px;border-radius:8px;border:1px solid #E2E8F0">' if proof.proof_url else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F8FAFC;font-family:Arial,Helvetica,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFC"><tr><td align="center" style="padding:24px 16px">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
<tr><td style="background:{header_color};padding:24px 32px;border-radius:12px 12px 0 0">{logo_html}<p style="margin:8px 0 0;font-size:14px;color:rgba(255,255,255,0.7)">Legacy Proof</p></td></tr>
<tr><td style="background:#fff;padding:32px;border:1px solid #E2E8F0;border-top:none;border-radius:0 0 12px 12px">
<p style="font-size:15px;color:#475569;line-height:1.6;margin:0 0 24px">Please find the legacy proof below for your review.</p>
{proof_img}
<table style="width:100%;margin-top:24px;font-size:14px;color:#1a1a1a">{''.join(details)}</table>
{notes_html}
<p style="font-size:14px;color:#475569;line-height:1.6;margin-top:24px">Please review the proof and reply to this email with any corrections or your approval.</p>
{watermark_note}
</td></tr>
<tr><td style="padding:24px;text-align:center"><p style="font-size:12px;color:#94A3B8;margin:0">{company_name}<br>Sent via Bridgeable</p></td></tr>
</table>
</td></tr></table>
</body></html>"""


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
