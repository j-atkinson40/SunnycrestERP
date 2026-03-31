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

        line_items.append({
            "description": line.description or "",
            "quantity": int(line.quantity) if line.quantity == int(line.quantity) else float(line.quantity),
            "unit_price": _fmt_currency(line.unit_price),
            "line_total": _fmt_currency(line.line_total),
            "is_zero_price": float(line.unit_price or 0) == 0.0,
            "is_placer": is_placer,
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


def generate_invoice_pdf(db: Session, invoice_id: str, company_id: str) -> bytes | None:
    """Render invoice to PDF bytes. Returns None if WeasyPrint unavailable."""
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        logger.warning("WeasyPrint not available — cannot generate PDF for invoice %s", invoice_id)
        return None

    html_content = generate_invoice_html(db, invoice_id, company_id)

    try:
        pdf_bytes: bytes = HTML(
            string=html_content,
            base_url=_TEMPLATE_DIR,
        ).write_pdf()
        return pdf_bytes
    except Exception as exc:
        logger.error("PDF generation failed for invoice %s: %s", invoice_id, exc)
        return None
