"""Price list PDF generation — renders price list versions to PDF via WeasyPrint.

Uses Jinja2 templates at backend/app/templates/price_lists/.
Falls back gracefully if WeasyPrint is not installed.
"""

from __future__ import annotations

import logging
import os
from collections import OrderedDict
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.price_list_item import PriceListItem
from app.models.price_list_template import PriceListTemplate
from app.models.price_list_version import PriceListVersion

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates", "price_lists")


def _get_jinja_env():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )


def _fmt_price(value) -> str:
    if value is None:
        return "—"
    try:
        return f"${Decimal(str(value)):,.2f}"
    except Exception:
        return "—"


def _fmt_date(dt) -> str:
    if dt is None:
        return ""
    try:
        if hasattr(dt, "strftime"):
            return dt.strftime("%B %d, %Y")
    except Exception:
        pass
    return str(dt)


def get_or_create_default_template(db: Session, tenant_id: str) -> PriceListTemplate:
    """Return the default template, creating one if none exists."""
    import uuid
    tpl = db.query(PriceListTemplate).filter(
        PriceListTemplate.tenant_id == tenant_id,
        PriceListTemplate.is_default == True,  # noqa: E712
    ).first()
    if not tpl:
        tpl = PriceListTemplate(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name="Default Price List",
            is_default=True,
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
    return tpl


def get_templates(db: Session, tenant_id: str) -> list[PriceListTemplate]:
    return (
        db.query(PriceListTemplate)
        .filter(PriceListTemplate.tenant_id == tenant_id)
        .order_by(PriceListTemplate.name)
        .all()
    )


def get_template(db: Session, tenant_id: str, template_id: str) -> PriceListTemplate | None:
    return db.query(PriceListTemplate).filter(
        PriceListTemplate.tenant_id == tenant_id,
        PriceListTemplate.id == template_id,
    ).first()


def save_template(db: Session, tenant_id: str, data: dict) -> PriceListTemplate:
    import uuid
    template_id = data.get("id")
    if template_id:
        tpl = get_template(db, tenant_id, template_id)
        if not tpl:
            raise ValueError("Template not found")
    else:
        tpl = PriceListTemplate(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
        )
        db.add(tpl)

    for field in (
        "name", "is_default", "layout_type", "columns",
        "show_product_codes", "show_descriptions", "show_notes",
        "show_category_headers", "logo_position", "primary_color",
        "font_family", "header_text", "footer_text",
        "show_effective_date", "show_page_numbers",
        "show_contractor_price", "show_homeowner_price",
    ):
        if field in data:
            setattr(tpl, field, data[field])

    # If setting as default, unset others
    if data.get("is_default"):
        db.query(PriceListTemplate).filter(
            PriceListTemplate.tenant_id == tenant_id,
            PriceListTemplate.id != tpl.id,
        ).update({"is_default": False})

    db.commit()
    db.refresh(tpl)
    return tpl


def delete_template(db: Session, tenant_id: str, template_id: str) -> bool:
    tpl = get_template(db, tenant_id, template_id)
    if not tpl:
        return False
    db.delete(tpl)
    db.commit()
    return True


def _build_context(
    db: Session,
    version: PriceListVersion,
    template: PriceListTemplate,
    tenant_id: str,
) -> dict[str, Any]:
    """Build the Jinja2 context for rendering a price list PDF."""
    company = db.query(Company).filter(Company.id == tenant_id).first()

    items = (
        db.query(PriceListItem)
        .filter(
            PriceListItem.version_id == version.id,
            PriceListItem.is_active == True,  # noqa: E712
        )
        .order_by(PriceListItem.display_order)
        .all()
    )

    # Group items by category
    grouped: dict[str, list[dict]] = OrderedDict()
    for item in items:
        cat = item.category or "General"
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append({
            "product_name": item.product_name,
            "product_code": item.product_code,
            "description": item.description,
            "standard_price_fmt": _fmt_price(item.standard_price),
            "contractor_price_fmt": _fmt_price(item.contractor_price),
            "homeowner_price_fmt": _fmt_price(item.homeowner_price),
            "unit": item.unit or "each",
            "notes": item.notes,
        })

    return {
        "title": version.label or f"Price List v{version.version_number}",
        "company_name": company.name if company else "",
        "effective_date": _fmt_date(version.effective_date),
        "version_label": f"Version {version.version_number}",
        "grouped_items": grouped,
        "primary_color": template.primary_color or "#000000",
        "font_family": template.font_family or "helvetica",
        "show_product_codes": template.show_product_codes,
        "show_descriptions": template.show_descriptions,
        "show_notes": template.show_notes,
        "show_category_headers": template.show_category_headers,
        "show_effective_date": template.show_effective_date,
        "show_page_numbers": template.show_page_numbers,
        "show_contractor_price": template.show_contractor_price,
        "show_homeowner_price": template.show_homeowner_price,
        "header_text": template.header_text,
        "footer_text": template.footer_text,
    }


def generate_price_list_pdf(
    db: Session,
    tenant_id: str,
    version_id: str,
    template_id: str | None = None,
) -> bytes | None:
    """Generate a PDF for a price list version. Returns bytes or None on failure."""
    version = db.query(PriceListVersion).filter(
        PriceListVersion.id == version_id,
        PriceListVersion.tenant_id == tenant_id,
    ).first()
    if not version:
        return None

    if template_id:
        template = get_template(db, tenant_id, template_id)
    else:
        template = get_or_create_default_template(db, tenant_id)
    if not template:
        return None

    ctx = _build_context(db, version, template, tenant_id)
    layout = template.layout_type or "grouped"
    template_file = f"{layout}.html"

    try:
        env = _get_jinja_env()
        html = env.get_template(template_file).render(**ctx)
    except Exception:
        logger.exception("Failed to render price list template")
        return None

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes
    except ImportError:
        logger.warning("WeasyPrint not installed — cannot generate PDF")
        return None
    except Exception:
        logger.exception("WeasyPrint PDF generation failed")
        return None


def generate_price_list_html_preview(
    db: Session,
    tenant_id: str,
    version_id: str,
    template_id: str | None = None,
) -> str | None:
    """Generate HTML preview (no PDF) for the template builder UI."""
    version = db.query(PriceListVersion).filter(
        PriceListVersion.id == version_id,
        PriceListVersion.tenant_id == tenant_id,
    ).first()
    if not version:
        return None

    if template_id:
        template = get_template(db, tenant_id, template_id)
    else:
        template = get_or_create_default_template(db, tenant_id)
    if not template:
        return None

    ctx = _build_context(db, version, template, tenant_id)
    layout = template.layout_type or "grouped"

    try:
        env = _get_jinja_env()
        return env.get_template(f"{layout}.html").render(**ctx)
    except Exception:
        logger.exception("Failed to render price list HTML preview")
        return None
