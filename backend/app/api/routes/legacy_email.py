"""Legacy email API — settings, domain verification, send proof, FH config."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.legacy_email_settings import LegacyEmailSettings, LegacyFHEmailConfig
from app.models.user import User
from app.services.legacy_email_service import (
    get_or_create_email_settings,
    send_proof_email,
)

router = APIRouter()


class EmailSettingsUpdate(BaseModel):
    sender_tier: str | None = None
    reply_to_email: str | None = None
    custom_from_email: str | None = None
    custom_from_name: str | None = None
    proof_email_subject: str | None = None
    proof_email_body: str | None = None
    print_email_subject: str | None = None
    use_invoice_branding: bool | None = None
    header_color: str | None = None
    logo_url: str | None = None


class FHConfigUpdate(BaseModel):
    recipients: list[dict]
    custom_subject: str | None = None
    custom_notes: str | None = None


class SendProofRequest(BaseModel):
    recipients: list[str] | None = None
    custom_notes: str | None = None
    preview: bool = False


class VerifyDomainRequest(BaseModel):
    email: str


# ── Email settings ────────────────────────────────────────────────────────────

@router.get("/email/settings")
def get_email_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_or_create_email_settings(db, current_user.company_id)
    return {
        "sender_tier": s.sender_tier,
        "reply_to_email": s.reply_to_email,
        "custom_from_email": s.custom_from_email,
        "custom_from_name": s.custom_from_name,
        "domain_verified": s.domain_verified,
        "proof_email_subject": s.proof_email_subject,
        "proof_email_body": s.proof_email_body,
        "print_email_subject": s.print_email_subject,
        "use_invoice_branding": s.use_invoice_branding,
        "header_color": s.header_color,
        "logo_url": s.logo_url,
    }


@router.patch("/email/settings")
def update_email_settings(
    data: EmailSettingsUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    s = get_or_create_email_settings(db, current_user.company_id)
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(s, field, val)
    s.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"updated": True}


# ── Domain verification ───────────────────────────────────────────────────────

@router.post("/email/verify-domain")
def verify_domain(
    data: VerifyDomainRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Initiate domain verification via Resend API."""
    domain = data.email.split("@")[1] if "@" in data.email else data.email

    try:
        import resend
        result = resend.Domains.create({"name": domain})
        domain_id = result.get("id", "")
        records = result.get("records", [])

        s = get_or_create_email_settings(db, current_user.company_id)
        s.custom_from_email = data.email
        s.resend_domain_id = domain_id
        s.domain_verified = False
        s.sender_tier = "custom"
        db.commit()

        return {
            "domain_id": domain_id,
            "records": records,
            "message": "Add these DNS records to verify your domain",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Resend API error: {e}")


@router.get("/email/verify-domain/status")
def check_domain_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_or_create_email_settings(db, current_user.company_id)
    if not s.resend_domain_id:
        return {"verified": False, "status": "no_domain"}

    try:
        import resend
        result = resend.Domains.get(s.resend_domain_id)
        status = result.get("status", "pending")
        verified = status == "verified"

        if verified and not s.domain_verified:
            s.domain_verified = True
            db.commit()

        return {"verified": verified, "status": status}
    except Exception as e:
        return {"verified": False, "status": f"error: {e}"}


# ── FH email config ──────────────────────────────────────────────────────────

@router.get("/fh-config/{customer_id}")
def get_fh_config(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = db.query(LegacyFHEmailConfig).filter(
        LegacyFHEmailConfig.company_id == current_user.company_id,
        LegacyFHEmailConfig.customer_id == customer_id,
    ).first()
    if not config:
        return {"recipients": [], "custom_subject": None, "custom_notes": None}
    return {
        "recipients": config.recipients or [],
        "custom_subject": config.custom_subject,
        "custom_notes": config.custom_notes,
    }


@router.post("/fh-config/{customer_id}")
def upsert_fh_config(
    customer_id: str,
    data: FHConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = db.query(LegacyFHEmailConfig).filter(
        LegacyFHEmailConfig.company_id == current_user.company_id,
        LegacyFHEmailConfig.customer_id == customer_id,
    ).first()
    if config:
        config.recipients = data.recipients
        config.custom_subject = data.custom_subject
        config.custom_notes = data.custom_notes
        config.updated_at = datetime.now(timezone.utc)
    else:
        config = LegacyFHEmailConfig(
            id=str(uuid.uuid4()),
            company_id=current_user.company_id,
            customer_id=customer_id,
            recipients=data.recipients,
            custom_subject=data.custom_subject,
            custom_notes=data.custom_notes,
        )
        db.add(config)
    db.commit()
    return {"saved": True}


# ── Send proof email ──────────────────────────────────────────────────────────

@router.post("/studio/{legacy_id}/send-proof-email")
def send_legacy_proof_email(
    legacy_id: str,
    data: SendProofRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = send_proof_email(
            db, current_user.company_id, legacy_id,
            recipient_override=data.recipients,
            custom_notes=data.custom_notes,
            preview_only=data.preview,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/studio/{legacy_id}/proof-email-preview")
def preview_proof_email(
    legacy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = send_proof_email(
            db, current_user.company_id, legacy_id,
            preview_only=True,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
