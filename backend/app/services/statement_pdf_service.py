"""Customer statement PDF rendering via the Documents layer.

Phase D-1. The backend/app/templates/statements/ Jinja templates were
previously orphaned — they existed on disk but no code invoked them.
`email_service._statement_html()` builds an inline Python f-string email
body instead.

This service wires the templates up via DocumentRenderer. A call
produces a canonical Document row with the rendered PDF in R2.

D-2 is the phase where email_service is migrated to use these
Documents as attachments instead of building inline HTML. For D-1 the
two paths coexist — admins who call `generate_statement_document()`
get a Document; the existing email-with-inline-HTML path keeps working
unchanged.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.customer import Customer
from app.models.statement import CustomerStatement
from app.services import statement_service
from app.services.documents import document_renderer
from app.services.documents.template_loader import _TEMPLATE_REGISTRY

logger = logging.getLogger(__name__)


# ── Template variant resolution ─────────────────────────────────────────
# A tenant may have a preferred statement template (modern, professional,
# clean_minimal). In D-1 we default to "professional"; D-2 adds a
# tenant-setting lookup.
DEFAULT_STATEMENT_VARIANT = "professional"


def _resolve_template_key(company: Company, override: str | None = None) -> str:
    """Pick the statement template variant to use for this tenant."""
    variant = (override or DEFAULT_STATEMENT_VARIANT).strip()
    key = f"statement.{variant}"
    if key not in _TEMPLATE_REGISTRY:
        return f"statement.{DEFAULT_STATEMENT_VARIANT}"
    return key


def _fmt_money(value) -> str:
    try:
        return f"${Decimal(str(value)):,.2f}"
    except Exception:
        return "$0.00"


def _fmt_date(d) -> str:
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%B %d, %Y")
    return str(d)


def _build_context(
    db: Session,
    stmt: CustomerStatement,
    customer: Customer,
    company: Company,
) -> dict:
    """Assemble the Jinja context the statement templates expect.

    Variables referenced by the templates: customer_name, billing_address,
    company_name, company_email, company_phone, company_logo_url,
    primary_color, statement_date, period_start, period_end, opening_balance,
    charges_total, payments_total, finance_charges_total, closing_balance,
    invoices (list of dicts with number, invoice_date, due_date, status,
    status_label, total, amount_paid, balance), plus a few settings fields
    (payment_terms_text, finance_charge_text, early_payment_text,
    remit_to_name).
    """
    period_start = date(stmt.statement_period_year, stmt.statement_period_month, 1)
    if stmt.statement_period_month == 12:
        period_end = date(stmt.statement_period_year + 1, 1, 1)
    else:
        period_end = date(
            stmt.statement_period_year, stmt.statement_period_month + 1, 1
        )

    # Invoices this period — reuse statement_service logic so numbers
    # match what the statement ledger reports.
    invoices_raw = statement_service.get_period_invoices(
        db,
        stmt.customer_id,
        stmt.statement_period_month,
        stmt.statement_period_year,
    )
    invoices = [
        {
            "number": i.get("number") or i.get("invoice_number") or "",
            "invoice_date": _fmt_date(i.get("invoice_date")),
            "due_date": _fmt_date(i.get("due_date")),
            "status": i.get("status") or "",
            "status_label": (i.get("status") or "").replace("_", " ").title(),
            "total": _fmt_money(i.get("total") or 0),
            "amount_paid": _fmt_money(i.get("amount_paid") or 0),
            "balance": _fmt_money(
                (i.get("total") or Decimal(0))
                - (i.get("amount_paid") or Decimal(0))
            ),
        }
        for i in invoices_raw
    ]

    # Company branding — pulled from settings JSON if present, with
    # safe fallbacks. These mirror what the invoice context uses so
    # templates share the same branding contract.
    settings = (company.settings_json or {}) if hasattr(company, "settings_json") else {}
    primary_color = settings.get("invoice_primary_color") or "#1a4b84"
    company_logo_url = settings.get("invoice_logo_url") or ""

    return {
        "customer_name": customer.name or "",
        "billing_address": getattr(customer, "billing_address", "") or "",
        "company_name": company.name or "",
        "company_email": getattr(company, "email", "") or "",
        "company_phone": getattr(company, "phone", "") or "",
        "company_logo_url": company_logo_url,
        "primary_color": primary_color,
        "statement_date": _fmt_date(date.today()),
        "period_start": _fmt_date(period_start),
        "period_end": _fmt_date(period_end),
        "opening_balance": _fmt_money(stmt.previous_balance or 0),
        "charges_total": _fmt_money(stmt.new_charges or 0),
        "payments_total": _fmt_money(stmt.payments_received or 0),
        "finance_charges_total": _fmt_money(0),  # D-2: wire to finance_charge_service
        "closing_balance": _fmt_money(stmt.balance_due or 0),
        "invoices": invoices,
        # Settings-sourced static text — D-2 makes these tenant-configurable
        "payment_terms_text": settings.get("statement_payment_terms") or "Net 30",
        "finance_charge_text": settings.get("statement_finance_charge_text") or "",
        "early_payment_text": settings.get("statement_early_payment_text") or "",
        "remit_to_name": settings.get("remit_to_name") or company.name or "",
    }


def generate_statement_document(
    db: Session,
    customer_statement_id: str,
    tenant_id: str,
    variant: str | None = None,
):
    """Render a customer statement to PDF via the Documents layer.

    Returns the Document row, or None if the statement isn't found.
    Raises DocumentRenderError on template / PDF / R2 failure.

    For D-1 this is an independent entry point — the email-sending path
    in email_service doesn't call it yet. Admins and programmatic
    consumers can invoke this to get a Document they can then download
    or attach.
    """
    stmt = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.id == customer_statement_id,
            CustomerStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if stmt is None:
        return None

    customer = db.query(Customer).filter(Customer.id == stmt.customer_id).first()
    company = db.query(Company).filter(Company.id == tenant_id).first()
    if customer is None or company is None:
        logger.warning(
            "Cannot render statement %s — missing customer or company",
            customer_statement_id,
        )
        return None

    context = _build_context(db, stmt, customer, company)
    template_key = _resolve_template_key(company, variant)

    title = (
        f"Statement — {customer.name} — "
        f"{stmt.statement_period_year}-{stmt.statement_period_month:02d}"
    )

    doc = document_renderer.render(
        db,
        template_key=template_key,
        context=context,
        document_type="statement",
        title=title,
        company_id=tenant_id,
        entity_type="customer_statement",
        entity_id=customer_statement_id,
        customer_statement_id=customer_statement_id,
        caller_module="statement_pdf_service.generate_statement_document",
    )

    # Mirror the new storage location onto the CustomerStatement so the
    # existing list endpoint's `statement_pdf_url` field has something
    # useful post-render. D-2 replaces this with a formal Document FK.
    from app.services import legacy_r2_client

    stmt.statement_pdf_url = legacy_r2_client.get_public_url(doc.storage_key)
    db.flush()

    return doc
