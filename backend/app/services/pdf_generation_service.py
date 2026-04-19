"""PDF generation service — renders invoice HTML templates to PDF via WeasyPrint.

Falls back gracefully (returns None) if WeasyPrint is not installed.
Uses Jinja2 for templating with templates at backend/app/templates/invoices/.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Template directory — relative to this file
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates", "invoices")


def _get_jinja_env():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )


def _fmt_currency(value) -> str:
    try:
        return f"${Decimal(str(value)):,.2f}"
    except Exception:
        return "$0.00"


def _fmt_date(dt) -> str:
    if dt is None:
        return ""
    try:
        if hasattr(dt, "strftime"):
            return dt.strftime("%B %d, %Y")
    except Exception:
        pass
    return str(dt)


def _fmt_date_short(dt) -> str:
    if dt is None:
        return ""
    try:
        if hasattr(dt, "strftime"):
            return dt.strftime("%m/%d/%Y")
    except Exception:
        pass
    return str(dt)


def _build_context(db: Session, invoice_id: str, company_id: str) -> dict[str, Any] | None:
    """Load all data needed to render an invoice template."""
    from sqlalchemy.orm import joinedload
    from app.models.invoice import Invoice, InvoiceLine
    from app.models.customer import Customer
    from app.models.company import Company
    from app.models.sales_order import SalesOrder
    from app.models.cemetery import Cemetery
    from app.services.invoice_settings_service import get_invoice_settings, build_terms_text

    inv = (
        db.query(Invoice)
        .options(joinedload(Invoice.lines))
        .filter(Invoice.id == invoice_id, Invoice.company_id == company_id)
        .first()
    )
    if not inv:
        logger.error("Invoice %s not found for company %s", invoice_id, company_id)
        return None

    company = db.query(Company).filter(Company.id == company_id).first()
    customer = db.query(Customer).filter(Customer.id == inv.customer_id).first()

    # Load sales order for cemetery / service date
    order: SalesOrder | None = None
    cemetery_name: str | None = None
    service_date_str: str | None = None
    order_number: str | None = None

    if inv.sales_order_id:
        order = db.query(SalesOrder).filter(SalesOrder.id == inv.sales_order_id).first()
        if order:
            order_number = order.number
            service_date_str = _fmt_date_short(order.scheduled_date) if order.scheduled_date else None
            if order.cemetery_id:
                cem = db.query(Cemetery).filter(Cemetery.id == order.cemetery_id).first()
                cemetery_name = cem.name if cem else None

    # Invoice settings
    settings = get_invoice_settings(db, company_id)

    # Company address
    addr_parts = [
        company.address_street if company else None,
        f"{company.address_city}, {company.address_state} {company.address_zip}"
        if company and (company.address_city or company.address_state)
        else None,
    ]
    company_address = "\n".join(p for p in addr_parts if p)

    # Billing address
    if customer:
        bill_parts = [
            customer.billing_address_line1 or customer.address_line1,
            customer.billing_address_line2 or customer.address_line2,
        ]
        bill_city = customer.billing_city or customer.city
        bill_state = customer.billing_state or customer.state
        bill_zip = customer.billing_zip or customer.zip_code
        if bill_city or bill_state:
            bill_parts.append(f"{bill_city or ''}, {bill_state or ''} {bill_zip or ''}".strip(", "))
        billing_address = "\n".join(p for p in bill_parts if p)
    else:
        billing_address = ""

    # Remit-to
    remit_name = settings.get("remit_to_name") or (company.company_legal_name or company.name if company else "")
    remit_address = settings.get("remit_to_address") or company_address

    # Terms texts
    terms = build_terms_text(settings, company)

    # Line items
    line_items = []
    for line in (inv.lines or []):
        try:
            product = db.query(__import__("app.models.product", fromlist=["Product"]).Product).filter_by(id=line.product_id).first() if line.product_id else None
            is_placer = getattr(product, "is_placer", False) if product else False
        except Exception:
            is_placer = False

        # Personalization details for this line
        pers_lines = []
        pers_data = getattr(line, "personalization_data", None)
        if pers_data and isinstance(pers_data, list):
            for p in pers_data:
                ptype = p.get("type", "")
                if ptype == "legacy_standard":
                    pers_lines.append(f"Legacy Series\u2122 \u2014 {p.get('print_name', '')}")
                elif ptype == "legacy_custom":
                    pers_lines.append("Legacy Custom Series\u2122")
                elif ptype == "lifes_reflections":
                    pers_lines.append(f"Life's Reflections\u00AE \u2014 {p.get('symbol', '')}")
                elif ptype == "nameplate":
                    pers_lines.append("Nameplate")
                elif ptype == "cover_emblem":
                    pers_lines.append("Cover Emblem (from stock)")
                # Add inscription lines
                if ptype != "cover_emblem":
                    for field in ("inscription_name", "inscription_dates", "inscription_additional"):
                        val = p.get(field)
                        if val:
                            pers_lines.append(val)

        line_items.append({
            "description": line.description or "",
            "quantity": int(line.quantity) if line.quantity == int(line.quantity) else float(line.quantity),
            "unit_price": _fmt_currency(line.unit_price),
            "line_total": _fmt_currency(line.line_total),
            "is_zero_price": float(line.unit_price or 0) == 0.0,
            "is_placer": is_placer,
            "personalization_lines": pers_lines,
        })

    return {
        # Company
        "company_name": company.name if company else "",
        "company_legal_name": (company.company_legal_name or company.name) if company else "",
        "company_address": company_address,
        "company_phone": company.phone if company else "",
        "company_email": company.email if company else "",
        "company_website": "",
        "company_logo_url": company.logo_url if company else "",
        "primary_color": settings["primary_color"],
        "secondary_color": settings["secondary_color"],
        # Invoice
        "invoice_number": inv.number,
        "invoice_date": _fmt_date(inv.invoice_date),
        "due_date": _fmt_date(inv.due_date),
        "payment_terms": inv.payment_terms or "",
        # Customer / bill-to
        "customer_name": customer.name if customer else "",
        "billing_address": billing_address,
        "billing_contact": (customer.billing_contact_name or customer.contact_name or "") if customer else "",
        "billing_email": (customer.billing_email or customer.email or "") if customer else "",
        # Service details
        "deceased_name": inv.deceased_name or "",
        "cemetery_name": cemetery_name or "",
        "service_date": service_date_str or "",
        "order_number": order_number or "",
        # Line items
        "line_items": line_items,
        # Totals
        "subtotal": _fmt_currency(inv.subtotal),
        "tax_amount": _fmt_currency(inv.tax_amount),
        "tax_rate": float(inv.tax_rate) * 100 if inv.tax_rate else 0.0,
        "total": _fmt_currency(inv.total),
        "amount_paid": _fmt_currency(inv.amount_paid),
        "balance_due": _fmt_currency(inv.balance_remaining),
        "has_tax": float(inv.tax_amount or 0) > 0,
        "has_payments": float(inv.amount_paid or 0) > 0,
        # Settings toggles
        "show_deceased_name": settings["show_deceased_name"] and bool(inv.deceased_name),
        "show_payment_terms": settings["show_payment_terms"],
        "show_early_payment_discount": settings["show_early_payment_discount"],
        "show_finance_charge_notice": settings["show_finance_charge_notice"],
        "show_cemetery_on_invoice": settings["show_cemetery_on_invoice"] and bool(cemetery_name),
        "show_service_date": settings["show_service_date"] and bool(service_date_str),
        "show_order_number": settings["show_order_number"] and bool(order_number),
        "show_phone": settings["show_phone"],
        "show_email": settings["show_email"],
        "show_website": settings["show_website"],
        "show_remittance_stub": settings["show_remittance_stub"],
        # Terms text
        **terms,
        "custom_footer_text": settings.get("custom_footer_text") or "",
        # Remit-to
        "remit_to_name": remit_name,
        "remit_to_address": remit_address,
        # Template
        "template_key": settings["template_key"],
    }


def generate_invoice_html(db: Session, invoice_id: str, company_id: str) -> str:
    """Render invoice as HTML string."""
    context = _build_context(db, invoice_id, company_id)
    if not context:
        return "<html><body><p>Invoice not found.</p></body></html>"

    template_key = context.get("template_key", "professional")
    try:
        env = _get_jinja_env()
        template = env.get_template(f"{template_key}.html")
        return template.render(**context)
    except Exception as exc:
        logger.error("Invoice HTML render failed for %s: %s", invoice_id, exc)
        # Fallback to professional
        try:
            env = _get_jinja_env()
            template = env.get_template("professional.html")
            context["template_key"] = "professional"
            return template.render(**context)
        except Exception as exc2:
            logger.error("Fallback render also failed: %s", exc2)
            return "<html><body><p>Invoice render error.</p></body></html>"


_PREVIEW_CACHE: dict[str, bytes] = {}  # simple in-process cache


def _build_preview_context(db: Session, company_id: str, settings_overrides: dict | None = None) -> dict[str, Any]:
    """Build template context using company data + sample invoice data."""
    from datetime import date, timedelta
    from app.models.company import Company
    from app.services.invoice_settings_service import get_invoice_settings, build_terms_text

    company = db.query(Company).filter(Company.id == company_id).first()
    settings = get_invoice_settings(db, company_id)
    if settings_overrides:
        settings = {**settings, **settings_overrides}

    today = date.today()
    due = today + timedelta(days=30)

    addr_parts = []
    if company:
        if company.address_street:
            addr_parts.append(company.address_street)
        city_line = ", ".join(filter(None, [company.address_city, company.address_state]))
        if city_line:
            if company.address_zip:
                city_line += f" {company.address_zip}"
            addr_parts.append(city_line)
    company_address = "\n".join(addr_parts)

    remit_name = settings.get("remit_to_name") or (company.company_legal_name or company.name if company else "")
    remit_address = settings.get("remit_to_address") or company_address
    terms = build_terms_text(settings, company)

    # Use detected colors if no custom ones set yet
    primary = settings["primary_color"]
    secondary = settings["secondary_color"]
    if company and primary == "#1B4F8A":
        det = company.get_setting("detected_primary_color")
        if det:
            primary = det
    if company and secondary == "#2D9B8A":
        det = company.get_setting("detected_secondary_color")
        if det:
            secondary = det

    logo = company.logo_url if company else ""
    if not logo and company:
        logo = company.get_setting("detected_logo_url") or ""

    return {
        "company_name": company.name if company else "Your Company",
        "company_legal_name": (company.company_legal_name or company.name) if company else "Your Company",
        "company_address": company_address,
        "company_phone": (company.phone or company.company_phone or "") if company else "",
        "company_email": (company.email or "") if company else "",
        "company_website": (company.website or "") if company else "",
        "company_logo_url": logo,
        "primary_color": primary,
        "secondary_color": secondary,
        # Sample invoice
        "invoice_number": "PREVIEW-001",
        "invoice_date": today.strftime("%B %d, %Y"),
        "due_date": due.strftime("%B %d, %Y"),
        "payment_terms": "Net 30",
        # Sample customer
        "customer_name": "Johnson Funeral Home",
        "billing_address": "123 Main Street\nSomewhere, NY 13021",
        "billing_contact": "Robert Johnson",
        "billing_email": "billing@johnsonfh.com",
        # Service details
        "deceased_name": "Smith, John",
        "cemetery_name": "Oak Hill Cemetery",
        "service_date": today.strftime("%m/%d/%Y"),
        "order_number": "SO-2026-0042",
        # Line items
        "line_items": [
            {"description": "Monticello Vault", "quantity": 1, "unit_price": "$1,405.00", "line_total": "$1,405.00", "is_zero_price": False, "is_placer": False},
            {"description": "Full Equipment", "quantity": 1, "unit_price": "$300.00", "line_total": "$300.00", "is_zero_price": False, "is_placer": False},
            {"description": "Vault Placer", "quantity": 1, "unit_price": "$0.00", "line_total": "$0.00", "is_zero_price": True, "is_placer": True},
        ],
        # Totals
        "subtotal": "$1,705.00",
        "tax_amount": "$0.00",
        "tax_rate": 0.0,
        "total": "$1,705.00",
        "amount_paid": "$0.00",
        "balance_due": "$1,705.00",
        "has_tax": False,
        "has_payments": False,
        # Toggles from settings
        "show_deceased_name": settings.get("show_deceased_name", True),
        "show_payment_terms": settings.get("show_payment_terms", True),
        "show_early_payment_discount": settings.get("show_early_payment_discount", True),
        "show_finance_charge_notice": settings.get("show_finance_charge_notice", True),
        "show_cemetery_on_invoice": settings.get("show_cemetery_on_invoice", True),
        "show_service_date": settings.get("show_service_date", True),
        "show_order_number": settings.get("show_order_number", True),
        "show_phone": settings.get("show_phone", True),
        "show_email": settings.get("show_email", True),
        "show_website": settings.get("show_website", False),
        "show_remittance_stub": settings.get("show_remittance_stub", False),
        **terms,
        "custom_footer_text": settings.get("custom_footer_text") or "",
        "remit_to_name": remit_name,
        "remit_to_address": remit_address,
        "template_key": settings["template_key"],
    }


def generate_template_preview_html(
    db: Session,
    company_id: str,
    template_key: str,
    settings_overrides: dict | None = None,
) -> str:
    """Render a sample invoice as HTML for the given template key."""
    context = _build_preview_context(db, company_id, settings_overrides)
    context["template_key"] = template_key
    try:
        env = _get_jinja_env()
        template = env.get_template(f"{template_key}.html")
        return template.render(**context)
    except Exception as exc:
        logger.error("Preview HTML render failed for template %s: %s", template_key, exc)
        try:
            env = _get_jinja_env()
            return env.get_template("professional.html").render(**context)
        except Exception:
            return "<html><body><p>Preview unavailable.</p></body></html>"


def generate_template_preview_pdf(
    db: Session,
    company_id: str,
    template_key: str,
    settings_overrides: dict | None = None,
    cache_key: str | None = None,
) -> bytes | None:
    """Render a sample invoice as PDF for the given template key."""
    if cache_key and cache_key in _PREVIEW_CACHE:
        return _PREVIEW_CACHE[cache_key]

    try:
        from weasyprint import HTML
    except ImportError:
        return None

    html_content = generate_template_preview_html(db, company_id, template_key, settings_overrides)
    try:
        pdf_bytes: bytes = HTML(string=html_content, base_url=_TEMPLATE_DIR).write_pdf()
        if cache_key:
            _PREVIEW_CACHE[cache_key] = pdf_bytes
            # Evict old entries if cache grows large
            if len(_PREVIEW_CACHE) > 50:
                oldest = next(iter(_PREVIEW_CACHE))
                del _PREVIEW_CACHE[oldest]
        return pdf_bytes
    except Exception as exc:
        logger.error("Preview PDF generation failed for template %s: %s", template_key, exc)
        return None


def generate_invoice_document(
    db: Session, invoice_id: str, company_id: str,
) -> "CanonicalDocument | None":
    """Phase D-1 — render an invoice through the Documents layer.

    Returns the canonical Document row (with storage_key, linkage,
    version metadata). The PDF is persisted to R2.

    Returns None if the invoice can't be loaded. Raises
    DocumentRenderError on template / WeasyPrint / R2 failure —
    callers that want graceful degradation should catch it.
    """
    from app.models.canonical_document import Document as CanonicalDocument
    from app.services.documents import document_renderer

    context = _build_context(db, invoice_id, company_id)
    if not context:
        return None

    template_key_suffix = context.get("template_key") or "professional"
    template_key = f"invoice.{template_key_suffix}"
    # Guard — fall back to professional if an unknown variant slipped in
    from app.services.documents.template_loader import _TEMPLATE_REGISTRY

    if template_key not in _TEMPLATE_REGISTRY:
        template_key = "invoice.professional"

    invoice_number = context.get("invoice_number") or invoice_id[:8]

    return document_renderer.render(
        db,
        template_key=template_key,
        context=context,
        document_type="invoice",
        title=f"Invoice {invoice_number}",
        company_id=company_id,
        entity_type="invoice",
        entity_id=invoice_id,
        invoice_id=invoice_id,
        caller_module="pdf_generation_service.generate_invoice_document",
    )


def generate_invoice_pdf(db: Session, invoice_id: str, company_id: str) -> bytes | None:
    """Legacy API — render invoice to PDF bytes.

    Phase D-1: routes through `generate_invoice_document()`, then fetches
    bytes from R2. Existing callers at routes/sales.py keep working
    verbatim. Returns None on failure to preserve the legacy contract.
    """
    from app.services.documents import document_renderer

    try:
        doc = generate_invoice_document(db, invoice_id, company_id)
    except document_renderer.DocumentRenderError as exc:
        logger.error("Invoice Document render failed for %s: %s", invoice_id, exc)
        return None
    if doc is None:
        return None

    try:
        return document_renderer.download_bytes(doc)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Fetched rendered invoice %s but R2 download failed: %s",
            invoice_id,
            exc,
        )
        return None
