"""Social Service Certificate PDF generator — Phase D-2 managed template.

Previously: 200-line inline f-string HTML + direct WeasyPrint call.
Now: routes through `app.services.documents.document_renderer` using the
`pdf.social_service_certificate` managed template (seeded r21).

The legacy `generate_social_service_certificate_pdf()` signature is
preserved so existing callers keep working unchanged; internally it now
builds a Jinja context and calls `document_renderer.render_pdf_bytes()`.
Tenants can override the template by inserting a tenant-scoped row in
`document_templates` with the same template_key.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session


def _build_context(
    certificate_number: str,
    deceased_name: str,
    funeral_home_name: str,
    cemetery_name: str,
    product_name: str,
    product_price: Decimal,
    delivered_at: datetime,
    company_config: dict,
) -> dict:
    """Build the Jinja context for pdf.social_service_certificate."""
    company_name = (
        company_config.get("company_legal_name")
        or company_config.get("name", "")
    )
    street = company_config.get("address_street", "")
    city = company_config.get("address_city", "")
    state = company_config.get("address_state", "")
    zipcode = company_config.get("address_zip", "")
    phone = company_config.get("phone", "")
    email = company_config.get("email", "")

    city_state_zip = ", ".join(filter(None, [city, state])) + (
        f" {zipcode}" if zipcode else ""
    )

    return {
        "certificate_number": certificate_number,
        "deceased_name": deceased_name,
        "funeral_home_name": funeral_home_name,
        "cemetery_name": cemetery_name,
        "product_name": product_name,
        "price_fmt": f"${product_price:,.2f}",
        "date_issued": delivered_at.strftime("%B %d, %Y"),
        "time_of_service": delivered_at.strftime("%-I:%M %p"),
        "company_name": company_name,
        "street": street,
        "city_state_zip": city_state_zip,
        "phone": phone,
        "email": email,
    }


def generate_social_service_certificate_pdf(
    certificate_number: str,
    deceased_name: str,
    funeral_home_name: str,
    cemetery_name: str,
    product_name: str,
    product_price: Decimal,
    delivered_at: datetime,
    company_config: dict,
    *,
    db: Session | None = None,
    company_id: str | None = None,
) -> bytes:
    """Render the certificate as a PDF and return raw bytes.

    D-2: routes through the managed `pdf.social_service_certificate`
    template. Existing positional args preserved for backward compat.
    New kwargs `db` + `company_id` enable tenant-override template
    resolution; when both are omitted, the platform template is used.
    """
    from app.services.documents import document_renderer

    context = _build_context(
        certificate_number,
        deceased_name,
        funeral_home_name,
        cemetery_name,
        product_name,
        product_price,
        delivered_at,
        company_config,
    )
    return document_renderer.render_pdf_bytes(
        db,
        template_key="pdf.social_service_certificate",
        context=context,
        company_id=company_id,
    )


def generate_social_service_certificate_document(
    db: Session,
    *,
    company_id: str,
    certificate_number: str,
    deceased_name: str,
    funeral_home_name: str,
    cemetery_name: str,
    product_name: str,
    product_price: Decimal,
    delivered_at: datetime,
    company_config: dict,
    order_id: str | None = None,
    sales_order_id: str | None = None,
):
    """Canonical entry point — produces a Document row + PDF in R2.

    Preferred over `generate_social_service_certificate_pdf` for new
    callers; the legacy byte-returning function keeps working but does
    NOT persist a Document.
    """
    from app.services.documents import document_renderer

    context = _build_context(
        certificate_number,
        deceased_name,
        funeral_home_name,
        cemetery_name,
        product_name,
        product_price,
        delivered_at,
        company_config,
    )
    return document_renderer.render(
        db,
        template_key="pdf.social_service_certificate",
        context=context,
        document_type="social_service_certificate",
        title=f"Social Service Certificate — {certificate_number}",
        company_id=company_id,
        entity_type="sales_order" if order_id else None,
        entity_id=order_id,
        sales_order_id=sales_order_id or order_id,
        caller_module="social_service_certificate_pdf.generate_social_service_certificate_document",
    )


# Legacy helper — kept because `safety_program_generation_service.py` still
# imports it. Its usage there is being removed alongside the safety program
# migration in this same phase; once that lands, this function is unused.
def _esc(text: str) -> str:
    """HTML-escape a string (legacy helper — Jinja autoescape preferred)."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
