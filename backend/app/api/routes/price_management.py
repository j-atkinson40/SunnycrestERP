"""Price management API — versions, increases, PDF templates, email settings."""

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────────────────

class PriceIncreasePreview(BaseModel):
    increase_type: str = "percentage"  # percentage | flat | manual
    increase_value: float | None = None
    effective_date: date
    product_ids: list[str] | None = None
    category_id: str | None = None
    manual_prices: dict | None = None
    label: str | None = None
    notes: str | None = None


class PriceIncreaseApply(PriceIncreasePreview):
    pass


class VersionAction(BaseModel):
    action: str  # "schedule" | "activate" | "delete"


class TemplateUpdate(BaseModel):
    id: str | None = None
    name: str = "Default Price List"
    is_default: bool = False
    layout_type: str = "grouped"
    columns: int = 1
    show_product_codes: bool = True
    show_descriptions: bool = True
    show_notes: bool = True
    show_category_headers: bool = True
    logo_position: str = "top-left"
    primary_color: str = "#000000"
    font_family: str = "helvetica"
    header_text: str | None = None
    footer_text: str | None = None
    show_effective_date: bool = True
    show_page_numbers: bool = True
    show_contractor_price: bool = False
    show_homeowner_price: bool = False


class EmailSettingsUpdate(BaseModel):
    sending_mode: str | None = None
    from_name: str | None = None
    reply_to_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password_encrypted: str | None = None
    smtp_use_tls: bool | None = None
    smtp_from_email: str | None = None
    invoice_bcc_email: str | None = None
    price_list_bcc_email: str | None = None


class RoundingSettingsUpdate(BaseModel):
    rounding_mode: str = "none"
    accept_manufacturer_updates: bool = False


class SendPriceListRequest(BaseModel):
    version_id: str
    template_id: str | None = None
    recipients: list[dict]  # [{"email": "...", "name": "..."}]
    custom_message: str | None = None


# ── Version endpoints ────────────────────────────────────────────────────

@router.get("/versions")
def list_versions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all price list versions for the tenant."""
    try:
        from app.services.price_increase_service import get_versions
        versions = get_versions(db, current_user.company_id)
        return [_serialize_version(v) for v in versions]
    except Exception:
        logger.exception("Failed to list versions")
        return []


@router.get("/versions/{version_id}")
def get_version_detail(
    version_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.price_increase_service import get_version
    v = get_version(db, current_user.company_id, version_id)
    if not v:
        raise HTTPException(404, "Version not found")
    return _serialize_version(v)


@router.get("/versions/{version_id}/items")
def list_version_items(
    version_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.price_increase_service import get_version_items
    items = get_version_items(db, current_user.company_id, version_id)
    return [_serialize_item(i) for i in items]


@router.post("/versions/{version_id}/action")
def version_action(
    version_id: str,
    body: VersionAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.price_increase_service import (
        activate_version,
        delete_version,
        schedule_version,
    )
    try:
        if body.action == "schedule":
            v = schedule_version(db, current_user.company_id, version_id)
            return _serialize_version(v)
        elif body.action == "activate":
            v = activate_version(db, current_user.company_id, version_id, current_user.id)
            return _serialize_version(v)
        elif body.action == "delete":
            ok = delete_version(db, current_user.company_id, version_id)
            if not ok:
                raise HTTPException(400, "Cannot delete — only draft versions can be deleted")
            return {"ok": True}
        else:
            raise HTTPException(400, f"Unknown action: {body.action}")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Price increase ───────────────────────────────────────────────────────

@router.post("/increase/preview")
def preview_increase(
    body: PriceIncreasePreview,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview price changes without saving."""
    from app.services.price_increase_service import calculate_price_increase
    try:
        return calculate_price_increase(
            db, current_user.company_id,
            increase_type=body.increase_type,
            increase_value=Decimal(str(body.increase_value)) if body.increase_value else None,
            effective_date=body.effective_date,
            product_ids=body.product_ids,
            category_id=body.category_id,
            manual_prices=body.manual_prices,
            label=body.label,
            notes=body.notes,
        )
    except Exception as e:
        logger.exception("Preview failed")
        raise HTTPException(500, str(e))


@router.post("/increase/apply")
def apply_increase(
    body: PriceIncreaseApply,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a draft version with the calculated prices."""
    from app.services.price_increase_service import apply_price_increase
    try:
        version = apply_price_increase(
            db, current_user.company_id, current_user.id,
            increase_type=body.increase_type,
            increase_value=Decimal(str(body.increase_value)) if body.increase_value else None,
            effective_date=body.effective_date,
            product_ids=body.product_ids,
            category_id=body.category_id,
            manual_prices=body.manual_prices,
            label=body.label,
            notes=body.notes,
        )
        return _serialize_version(version)
    except Exception as e:
        logger.exception("Apply failed")
        raise HTTPException(500, str(e))


# ── Current prices (from products table) ─────────────────────────────────

@router.get("/current-prices")
def list_current_prices(
    search: str | None = Query(None),
    category_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List current product prices from the products table."""
    from app.models.product import Product
    q = db.query(Product).filter(
        Product.company_id == current_user.company_id,
        Product.is_active == True,  # noqa: E712
    )
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (Product.name.ilike(pattern)) | (Product.sku.ilike(pattern))
        )
    if category_id:
        q = q.filter(Product.category_id == category_id)

    products = q.order_by(Product.name).limit(500).all()
    return [{
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "price": str(p.price) if p.price else None,
        "cost_price": str(p.cost_price) if p.cost_price else None,
        "unit": p.unit_of_measure or "each",
        "category_id": p.category_id,
        "category_name": p.category.name if p.category_id and hasattr(p, "category") and p.category else None,
        "is_active": p.is_active,
    } for p in products]


# ── Rounding settings ────────────────────────────────────────────────────

@router.get("/settings/rounding")
def get_rounding_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from app.services.price_increase_service import get_or_create_settings
        s = get_or_create_settings(db, current_user.company_id)
        return {
            "rounding_mode": s.rounding_mode,
            "accept_manufacturer_updates": s.accept_manufacturer_updates,
        }
    except Exception as e:
        logger.exception("Failed to load rounding settings")
        return {"rounding_mode": "none", "accept_manufacturer_updates": False}


@router.put("/settings/rounding")
def update_rounding_settings(
    body: RoundingSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from app.services.price_increase_service import update_settings
        s = update_settings(db, current_user.company_id, body.model_dump())
        return {
            "rounding_mode": s.rounding_mode,
            "accept_manufacturer_updates": s.accept_manufacturer_updates,
        }
    except Exception as e:
        logger.exception("Failed to update rounding settings")
        raise HTTPException(500, str(e))


# ── PDF Templates ────────────────────────────────────────────────────────

@router.get("/templates")
def list_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from app.services.price_list_pdf_service import get_templates
        templates = get_templates(db, current_user.company_id)
        return [_serialize_template(t) for t in templates]
    except Exception:
        logger.exception("Failed to load templates")
        return []


@router.post("/templates")
def create_or_update_template(
    body: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.price_list_pdf_service import save_template
    try:
        tpl = save_template(db, current_user.company_id, body.model_dump())
        return _serialize_template(tpl)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/templates/{template_id}")
def remove_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.price_list_pdf_service import delete_template
    ok = delete_template(db, current_user.company_id, template_id)
    if not ok:
        raise HTTPException(404, "Template not found")
    return {"ok": True}


# ── PDF generation ───────────────────────────────────────────────────────

@router.get("/versions/{version_id}/pdf")
def download_pdf(
    version_id: str,
    template_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.price_list_pdf_service import generate_price_list_pdf
    pdf = generate_price_list_pdf(db, current_user.company_id, version_id, template_id)
    if not pdf:
        raise HTTPException(500, "PDF generation failed")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="price-list-{version_id[:8]}.pdf"'},
    )


@router.get("/versions/{version_id}/preview-html")
def preview_html(
    version_id: str,
    template_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.price_list_pdf_service import generate_price_list_html_preview
    html = generate_price_list_html_preview(db, current_user.company_id, version_id, template_id)
    if not html:
        raise HTTPException(500, "Preview generation failed")
    return Response(content=html, media_type="text/html")


# ── Email settings ───────────────────────────────────────────────────────

@router.get("/settings/email")
def get_email_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from app.services.platform_email_service import get_or_create_email_settings
        s = get_or_create_email_settings(db, current_user.company_id)
        return _serialize_email_settings(s)
    except Exception:
        logger.exception("Failed to load email settings")
        return {
            "id": "", "sending_mode": "platform", "from_name": None,
            "reply_to_email": None, "smtp_host": None, "smtp_port": 587,
            "smtp_username": None, "smtp_use_tls": True, "smtp_from_email": None,
            "smtp_verified": False, "smtp_verified_at": None,
            "invoice_bcc_email": None, "price_list_bcc_email": None,
        }


@router.put("/settings/email")
def save_email_settings(
    body: EmailSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.platform_email_service import update_email_settings
    s = update_email_settings(db, current_user.company_id, body.model_dump(exclude_none=True))
    return _serialize_email_settings(s)


@router.post("/settings/email/verify-smtp")
def test_smtp(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.platform_email_service import verify_smtp
    return verify_smtp(db, current_user.company_id)


# ── Email send history ───────────────────────────────────────────────────

@router.get("/email-sends")
def list_email_sends(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    email_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from app.services.platform_email_service import get_email_sends
        sends = get_email_sends(db, current_user.company_id, limit, offset, email_type)
    except Exception:
        logger.exception("Failed to load email sends")
        return []
    return [{
        "id": s.id,
        "email_type": s.email_type,
        "to_email": s.to_email,
        "to_name": s.to_name,
        "subject": s.subject,
        "status": s.status,
        "error_message": s.error_message,
        "sent_at": s.sent_at.isoformat() if s.sent_at else None,
        "attachment_name": s.attachment_name,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in sends]


# ── Send price list ──────────────────────────────────────────────────────

@router.post("/send-price-list")
def send_price_list(
    body: SendPriceListRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate PDF and send to multiple recipients."""
    from app.models.company import Company
    from app.services.platform_email_service import send_price_list_email
    from app.services.price_increase_service import get_version
    from app.services.price_list_pdf_service import generate_price_list_pdf

    version = get_version(db, current_user.company_id, body.version_id)
    if not version:
        raise HTTPException(404, "Version not found")

    pdf = generate_price_list_pdf(db, current_user.company_id, body.version_id, body.template_id)
    if not pdf:
        raise HTTPException(500, "PDF generation failed")

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    company_name = company.name if company else "Your Company"

    results = []
    for r in body.recipients:
        email = r.get("email", "")
        name = r.get("name")
        if not email:
            continue
        res = send_price_list_email(
            db, current_user.company_id, current_user.id,
            to_email=email,
            to_name=name,
            company_name=company_name,
            version_id=body.version_id,
            version_label=version.label or f"v{version.version_number}",
            effective_date=version.effective_date.isoformat() if version.effective_date else "",
            pdf_bytes=pdf,
            custom_message=body.custom_message,
        )
        results.append({"email": email, "success": res.get("success", False)})

    sent = sum(1 for r in results if r["success"])
    return {"sent": sent, "total": len(results), "results": results}


# ── Serializers ──────────────────────────────────────────────────────────

def _serialize_version(v) -> dict:
    return {
        "id": v.id,
        "version_number": v.version_number,
        "label": v.label,
        "notes": v.notes,
        "status": v.status,
        "effective_date": v.effective_date.isoformat() if v.effective_date else None,
        "activated_at": v.activated_at.isoformat() if v.activated_at else None,
        "created_by_user_id": v.created_by_user_id,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _serialize_item(i) -> dict:
    return {
        "id": i.id,
        "product_name": i.product_name,
        "product_code": i.product_code,
        "category": i.category,
        "description": i.description,
        "standard_price": str(i.standard_price) if i.standard_price is not None else None,
        "contractor_price": str(i.contractor_price) if i.contractor_price is not None else None,
        "homeowner_price": str(i.homeowner_price) if i.homeowner_price is not None else None,
        "previous_standard_price": str(i.previous_standard_price) if i.previous_standard_price is not None else None,
        "unit": i.unit,
        "notes": i.notes,
        "display_order": i.display_order,
        "is_active": i.is_active,
    }


def _serialize_template(t) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "is_default": t.is_default,
        "layout_type": t.layout_type,
        "columns": t.columns,
        "show_product_codes": t.show_product_codes,
        "show_descriptions": t.show_descriptions,
        "show_notes": t.show_notes,
        "show_category_headers": t.show_category_headers,
        "logo_position": t.logo_position,
        "primary_color": t.primary_color,
        "font_family": t.font_family,
        "header_text": t.header_text,
        "footer_text": t.footer_text,
        "show_effective_date": t.show_effective_date,
        "show_page_numbers": t.show_page_numbers,
        "show_contractor_price": t.show_contractor_price,
        "show_homeowner_price": t.show_homeowner_price,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _serialize_email_settings(s) -> dict:
    return {
        "id": s.id,
        "sending_mode": s.sending_mode,
        "from_name": s.from_name,
        "reply_to_email": s.reply_to_email,
        "smtp_host": s.smtp_host,
        "smtp_port": s.smtp_port,
        "smtp_username": s.smtp_username,
        "smtp_use_tls": s.smtp_use_tls,
        "smtp_from_email": s.smtp_from_email,
        "smtp_verified": s.smtp_verified,
        "smtp_verified_at": s.smtp_verified_at.isoformat() if s.smtp_verified_at else None,
        "invoice_bcc_email": s.invoice_bcc_email,
        "price_list_bcc_email": s.price_list_bcc_email,
    }
