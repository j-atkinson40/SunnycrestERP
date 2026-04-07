"""Sales & AR routes — Quotes, Sales Orders, Invoices, Customer Payments, AR Aging."""

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission, get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.sales import (
    ARAgingReport,
    CustomerPaymentCreate,
    CustomerPaymentResponse,
    InvoiceCreate,
    InvoiceResponse,
    InvoiceUpdate,
    PaginatedCustomerPayments,
    PaginatedInvoices,
    PaginatedQuotes,
    PaginatedSalesOrders,
    PaymentImportResult,
    QuoteCreate,
    QuoteResponse,
    QuoteUpdate,
    SalesOrderCreate,
    SalesOrderResponse,
    SalesOrderUpdate,
    SalesStats,
)
from app.services import sales_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _quote_to_response(q) -> dict:
    data = {
        "id": q.id,
        "company_id": q.company_id,
        "number": q.number,
        "customer_id": q.customer_id,
        "customer_name": q.customer.name if q.customer else None,
        "status": q.status,
        "quote_date": q.quote_date,
        "expiry_date": q.expiry_date,
        "payment_terms": q.payment_terms,
        "subtotal": q.subtotal,
        "tax_rate": q.tax_rate,
        "tax_amount": q.tax_amount,
        "total": q.total,
        "notes": q.notes,
        "created_by": q.created_by,
        "created_by_name": (
            f"{q.creator.first_name or ''} {q.creator.last_name or ''}".strip()
            or q.creator.email
        )
        if q.creator
        else None,
        "created_at": q.created_at,
        "modified_at": q.modified_at,
        "lines": [
            {
                "id": ln.id,
                "quote_id": ln.quote_id,
                "product_id": ln.product_id,
                "product_name": ln.product.name if ln.product else None,
                "description": ln.description,
                "quantity": ln.quantity,
                "unit_price": ln.unit_price,
                "line_total": ln.line_total,
                "sort_order": ln.sort_order,
            }
            for ln in (q.lines or [])
        ],
    }
    return data


def _order_to_response(o) -> dict:
    data = {
        "id": o.id,
        "company_id": o.company_id,
        "number": o.number,
        "customer_id": o.customer_id,
        "customer_name": o.customer.name if o.customer else None,
        "quote_id": o.quote_id,
        "status": o.status,
        "order_date": o.order_date,
        "required_date": o.required_date,
        "shipped_date": o.shipped_date,
        "payment_terms": o.payment_terms,
        "subtotal": o.subtotal,
        "tax_rate": o.tax_rate,
        "tax_amount": o.tax_amount,
        "total": o.total,
        "ship_to_name": o.ship_to_name,
        "ship_to_address": o.ship_to_address,
        "notes": o.notes,
        "created_by": o.created_by,
        "created_by_name": (
            f"{o.creator.first_name or ''} {o.creator.last_name or ''}".strip()
            or o.creator.email
        )
        if o.creator
        else None,
        "created_at": o.created_at,
        "modified_at": o.modified_at,
        "lines": [
            {
                "id": ln.id,
                "sales_order_id": ln.sales_order_id,
                "product_id": ln.product_id,
                "product_name": ln.product.name if ln.product else None,
                "description": ln.description,
                "quantity": ln.quantity,
                "quantity_shipped": ln.quantity_shipped,
                "unit_price": ln.unit_price,
                "line_total": ln.line_total,
                "sort_order": ln.sort_order,
                "has_conditional_pricing": ln.product.has_conditional_pricing if ln.product else False,
                "is_call_office": ln.product.is_call_office if ln.product else False,
                "price_without_our_product": ln.product.price_without_our_product if ln.product else None,
            }
            for ln in (o.lines or [])
        ],
    }
    return data


def _invoice_to_response(inv) -> dict:
    data = {
        "id": inv.id,
        "company_id": inv.company_id,
        "number": inv.number,
        "customer_id": inv.customer_id,
        "customer_name": inv.customer.name if inv.customer else None,
        "sales_order_id": inv.sales_order_id,
        "status": inv.status,
        "invoice_date": inv.invoice_date,
        "due_date": inv.due_date,
        "payment_terms": inv.payment_terms,
        "subtotal": inv.subtotal,
        "tax_rate": inv.tax_rate,
        "tax_amount": inv.tax_amount,
        "total": inv.total,
        "amount_paid": inv.amount_paid,
        "balance_remaining": inv.balance_remaining,
        "notes": inv.notes,
        "created_by": inv.created_by,
        "created_by_name": (
            f"{inv.creator.first_name or ''} {inv.creator.last_name or ''}".strip()
            or inv.creator.email
        )
        if inv.creator
        else None,
        "created_at": inv.created_at,
        "modified_at": inv.modified_at,
        "lines": [
            {
                "id": ln.id,
                "invoice_id": ln.invoice_id,
                "product_id": ln.product_id,
                "product_name": ln.product.name if ln.product else None,
                "description": ln.description,
                "quantity": ln.quantity,
                "unit_price": ln.unit_price,
                "line_total": ln.line_total,
                "sort_order": ln.sort_order,
            }
            for ln in (inv.lines or [])
        ],
    }
    return data


def _payment_to_response(pmt) -> dict:
    data = {
        "id": pmt.id,
        "company_id": pmt.company_id,
        "customer_id": pmt.customer_id,
        "customer_name": pmt.customer.name if pmt.customer else None,
        "payment_date": pmt.payment_date,
        "total_amount": pmt.total_amount,
        "payment_method": pmt.payment_method,
        "reference_number": pmt.reference_number,
        "notes": pmt.notes,
        "created_by": pmt.created_by,
        "created_by_name": (
            f"{pmt.creator.first_name or ''} {pmt.creator.last_name or ''}".strip()
            or pmt.creator.email
        )
        if pmt.creator
        else None,
        "created_at": pmt.created_at,
        "modified_at": pmt.modified_at,
        "applications": [
            {
                "id": app.id,
                "payment_id": app.payment_id,
                "invoice_id": app.invoice_id,
                "invoice_number": app.invoice.number if app.invoice else None,
                "amount_applied": app.amount_applied,
            }
            for app in (pmt.applications or [])
        ],
    }
    return data


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=SalesStats)
def sales_stats(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    return sales_service.get_sales_stats(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


@router.get("/quotes", response_model=PaginatedQuotes)
def list_quotes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    customer_id: str | None = None,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    result = sales_service.get_quotes(
        db, current_user.company_id, page, per_page, status, customer_id
    )
    result["items"] = [_quote_to_response(q) for q in result["items"]]
    return result


@router.post("/quotes", response_model=QuoteResponse, status_code=201)
def create_quote(
    data: QuoteCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_quote")),
):
    quote = sales_service.create_quote(
        db, current_user.company_id, current_user.id, data
    )
    return _quote_to_response(quote)


@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
def get_quote(
    quote_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    quote = sales_service.get_quote(db, current_user.company_id, quote_id)
    return _quote_to_response(quote)


@router.patch("/quotes/{quote_id}", response_model=QuoteResponse)
def update_quote(
    quote_id: str,
    data: QuoteUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_quote")),
):
    quote = sales_service.update_quote(
        db, current_user.company_id, current_user.id, quote_id, data
    )
    return _quote_to_response(quote)


@router.post(
    "/quotes/{quote_id}/convert",
    response_model=SalesOrderResponse,
    status_code=201,
)
def convert_quote(
    quote_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_order")),
):
    order = sales_service.convert_quote_to_order(
        db, current_user.company_id, current_user.id, quote_id
    )
    return _order_to_response(order)


# ---------------------------------------------------------------------------
# Sales Orders
# ---------------------------------------------------------------------------


@router.get("/orders", response_model=PaginatedSalesOrders)
def list_sales_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    customer_id: str | None = None,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    result = sales_service.get_sales_orders(
        db, current_user.company_id, page, per_page, status, customer_id
    )
    result["items"] = [_order_to_response(o) for o in result["items"]]
    return result


@router.post("/orders", response_model=SalesOrderResponse, status_code=201)
def create_sales_order(
    data: SalesOrderCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_order")),
):
    order = sales_service.create_sales_order(
        db, current_user.company_id, current_user.id, data
    )
    return _order_to_response(order)


@router.get("/orders/{order_id}", response_model=SalesOrderResponse)
def get_sales_order(
    order_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    order = sales_service.get_sales_order(db, current_user.company_id, order_id)
    return _order_to_response(order)


@router.patch("/orders/{order_id}", response_model=SalesOrderResponse)
def update_sales_order(
    order_id: str,
    data: SalesOrderUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.update_order")),
):
    order = sales_service.update_sales_order(
        db, current_user.company_id, current_user.id, order_id, data
    )
    return _order_to_response(order)


@router.post(
    "/orders/{order_id}/invoice",
    response_model=InvoiceResponse,
    status_code=201,
)
def invoice_from_order(
    order_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    invoice = sales_service.create_invoice_from_order(
        db, current_user.company_id, current_user.id, order_id
    )
    return _invoice_to_response(invoice)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@router.get("/invoices", response_model=PaginatedInvoices)
def list_invoices(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    customer_id: str | None = None,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    result = sales_service.get_invoices(
        db, current_user.company_id, page, per_page, status, customer_id
    )
    result["items"] = [_invoice_to_response(inv) for inv in result["items"]]
    return result


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    data: InvoiceCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    invoice = sales_service.create_invoice(
        db, current_user.company_id, current_user.id, data
    )
    return _invoice_to_response(invoice)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    invoice = sales_service.get_invoice(db, current_user.company_id, invoice_id)
    return _invoice_to_response(invoice)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: str,
    data: InvoiceUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    invoice = sales_service.update_invoice(
        db, current_user.company_id, current_user.id, invoice_id, data
    )
    return _invoice_to_response(invoice)


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceResponse)
def void_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.void")),
):
    invoice = sales_service.void_invoice(
        db, current_user.company_id, current_user.id, invoice_id
    )
    return _invoice_to_response(invoice)


# ---------------------------------------------------------------------------
# Customer Payments
# ---------------------------------------------------------------------------


@router.get("/payments", response_model=PaginatedCustomerPayments)
def list_payments(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    customer_id: str | None = None,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    result = sales_service.get_customer_payments(
        db, current_user.company_id, page, per_page, customer_id
    )
    result["items"] = [_payment_to_response(p) for p in result["items"]]
    return result


@router.post(
    "/payments", response_model=CustomerPaymentResponse, status_code=201
)
def create_payment(
    data: CustomerPaymentCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.record_payment")),
):
    payment = sales_service.create_customer_payment(
        db, current_user.company_id, current_user.id, data
    )
    return _payment_to_response(payment)


@router.post("/payments/scan-check")
async def scan_check(
    file: UploadFile,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(get_current_user),
):
    """Scan a check image and extract payment information using Claude Vision."""
    return await sales_service.scan_check_image(db, file, current_user.company_id)


@router.post("/payments/suggest-application")
def suggest_payment_application(
    data: dict,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(get_current_user),
):
    """Suggest invoice applications for a given payment amount."""
    return sales_service.suggest_payment_application(
        db,
        customer_id=data.get("customer_id"),
        amount=data.get("amount"),
        payment_date=data.get("payment_date"),
        company_id=current_user.company_id,
    )


@router.post("/payments/import", response_model=PaymentImportResult)
async def import_payments_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.record_payment")),
):
    content = await file.read()
    result = sales_service.import_sage_payments_from_csv(
        db, content, current_user.company_id, actor_id=current_user.id
    )
    return result


@router.get("/payments/{payment_id}")
def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    """Get a single payment with its applications."""
    return sales_service.get_payment_detail(db, payment_id, current_user.company_id)


@router.post("/payments/{payment_id}/void")
def void_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.record_payment")),
):
    """Void a payment and reverse all applications."""
    return sales_service.void_payment(db, payment_id, current_user.company_id, current_user.id)


@router.post("/invoices/{invoice_id}/honor-discount")
def honor_discount(
    invoice_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.record_payment")),
):
    """Retroactively apply early payment discount to a partially-paid invoice."""
    return sales_service.honor_early_payment_discount(db, invoice_id, current_user.company_id)


@router.get("/invoices/{invoice_id}/payments")
def get_invoice_payments(
    invoice_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    """Get payment history for a specific invoice."""
    return sales_service.get_invoice_payment_history(db, invoice_id, current_user.company_id)


# ---------------------------------------------------------------------------
# AR Aging
# ---------------------------------------------------------------------------


@router.get("/aging", response_model=ARAgingReport)
def ar_aging(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    return sales_service.get_ar_aging(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Invoice review queue — draft invoices awaiting morning approval
# ---------------------------------------------------------------------------


@router.get("/invoices/review")
def get_invoice_review_queue(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.view")),
):
    """Return all draft invoices pending review, exceptions first."""
    from app.services.draft_invoice_service import get_review_queue
    return get_review_queue(db, current_user.company_id)


@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    """Approve a single draft invoice — posts it to AR (status → 'sent')."""
    from app.services.draft_invoice_service import approve_invoice as _approve
    invoice = _approve(db, current_user.company_id, invoice_id, current_user.id)
    return {"id": invoice.id, "number": invoice.number, "status": invoice.status}


@router.post("/invoices/approve-batch")
def approve_invoices_batch(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    """Approve all draft review invoices with no exceptions (bulk action).

    Invoices with driver exceptions are left for individual review.
    """
    from app.services.draft_invoice_service import approve_all_no_exceptions
    return approve_all_no_exceptions(db, current_user.company_id, current_user.id)


# ---------------------------------------------------------------------------
# Invoice Settings
# ---------------------------------------------------------------------------


@router.get("/invoice-settings")
def get_invoice_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    """Return invoice PDF settings for this tenant (with defaults filled in)."""
    from app.services.invoice_settings_service import get_invoice_settings as _get
    return _get(db, current_user.company_id)


@router.patch("/invoice-settings")
def update_invoice_settings(
    updates: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    """Merge updates into invoice settings."""
    from app.services.invoice_settings_service import update_invoice_settings as _update
    return _update(db, current_user.company_id, updates)


# ---------------------------------------------------------------------------
# Invoice Preview / PDF
# ---------------------------------------------------------------------------


@router.get("/invoices/{invoice_id}/preview")
def preview_invoice(
    invoice_id: str,
    format: str = "pdf",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    """Generate and return invoice as HTML or PDF.

    ?format=html  — Returns rendered HTML (for browser preview).
    ?format=pdf   — Returns PDF bytes inline (opens in browser PDF viewer).
    """
    from fastapi.responses import HTMLResponse, Response
    from app.services.pdf_generation_service import generate_invoice_pdf, generate_invoice_html

    if format == "html":
        html = generate_invoice_html(db, invoice_id, current_user.company_id)
        return HTMLResponse(content=html)

    pdf_bytes = generate_invoice_pdf(db, invoice_id, current_user.company_id)
    if pdf_bytes is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="PDF generation unavailable — WeasyPrint not installed")

    # Fetch invoice number for filename
    from app.models.invoice import Invoice
    inv = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.company_id == current_user.company_id,
    ).first()
    filename = f"Invoice-{inv.number}.pdf" if inv else "Invoice.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Manual Invoice Send
# ---------------------------------------------------------------------------


@router.post("/invoices/{invoice_id}/send")
def send_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    """Manually generate PDF and send invoice email regardless of delivery preference."""
    from app.services.pdf_generation_service import generate_invoice_pdf
    from app.services.email_service import email_service
    from app.models.invoice import Invoice
    from app.models.customer import Customer
    import logging
    from datetime import datetime, timezone

    _log = logging.getLogger(__name__)

    inv = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.company_id == current_user.company_id,
    ).first()
    if not inv:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Invoice not found")

    customer = db.query(Customer).filter(Customer.id == inv.customer_id).first()
    to_email = (customer.billing_email or customer.email) if customer else None
    if not to_email:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Customer has no email address configured")

    pdf_bytes = generate_invoice_pdf(db, invoice_id, current_user.company_id)
    if pdf_bytes is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="PDF generation unavailable")

    from app.models.company import Company
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    company_name = company.name if company else "Your supplier"

    result = email_service.send_invoice_email(
        to_email=to_email,
        to_name=customer.name if customer else "",
        company_name=company_name,
        invoice_number=inv.number,
        invoice_date=inv.invoice_date.strftime("%B %d, %Y"),
        due_date=inv.due_date.strftime("%B %d, %Y"),
        total_amount=f"${inv.total:,.2f}",
        balance_due=f"${inv.balance_remaining:,.2f}",
        deceased_name=inv.deceased_name,
        pdf_attachment=pdf_bytes,
        reply_to=company.email if company else None,
    )

    if result.get("success"):
        now = datetime.now(timezone.utc)
        inv.sent_at = now
        inv.sent_to_email = to_email
        if inv.status == "draft":
            inv.status = "sent"
        db.commit()
        _log.info("Invoice %s manually sent to %s", inv.number, to_email)
        return {"success": True, "sent_to": to_email}

    return {"success": False, "error": "Email delivery failed"}


# ---------------------------------------------------------------------------
# Template Preview (for onboarding wizard)
# ---------------------------------------------------------------------------


@router.get("/invoice-templates/preview")
def template_preview(
    template: str = Query("professional"),
    format: str = Query("pdf"),
    options: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Render a sample invoice preview for the given template key.

    ?template=professional|clean_minimal|modern|custom
    ?format=pdf|html
    ?options=JSON string of invoice_settings overrides (optional)
    """
    import json as _json
    from fastapi.responses import HTMLResponse, Response
    from app.services.pdf_generation_service import (
        generate_template_preview_html,
        generate_template_preview_pdf,
    )

    VALID_TEMPLATES = {"professional", "clean_minimal", "modern", "custom"}
    if template not in VALID_TEMPLATES:
        template = "professional"

    overrides: dict | None = None
    if options:
        try:
            overrides = _json.loads(options)
        except Exception:
            overrides = None

    cache_key = f"{current_user.company_id}:{template}:{options or ''}"

    if format == "html":
        html = generate_template_preview_html(
            db, current_user.company_id, template, overrides
        )
        return HTMLResponse(content=html)

    pdf_bytes = generate_template_preview_pdf(
        db, current_user.company_id, template, overrides, cache_key=cache_key
    )
    if pdf_bytes is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="PDF generation unavailable — WeasyPrint not installed",
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="Preview-{template}.pdf"'},
    )


@router.get("/invoice-templates/preview-debug")
def preview_debug(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Debug endpoint — returns raw error from preview generation."""
    import traceback
    import os
    from app.services.pdf_generation_service import _build_preview_context, _get_jinja_env, _TEMPLATE_DIR
    result = {}
    result["template_dir"] = _TEMPLATE_DIR
    result["template_dir_exists"] = os.path.isdir(_TEMPLATE_DIR)
    try:
        result["template_files"] = os.listdir(_TEMPLATE_DIR)
    except Exception as e:
        result["template_files_error"] = str(e)
    try:
        ctx = _build_preview_context(db, current_user.company_id)
        result["context_keys"] = list(ctx.keys())
    except Exception as e:
        result["context_error"] = traceback.format_exc()
        return result
    try:
        env = _get_jinja_env()
        tpl = env.get_template("professional.html")
        html = tpl.render(**ctx)
        result["html_length"] = len(html)
        result["html_preview"] = html[:200]
    except Exception as e:
        result["html_error"] = traceback.format_exc()
    return result


@router.post("/invoices/analyze-existing-template")
async def analyze_existing_template(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("ar.create_invoice")),
):
    """Analyze an uploaded invoice PDF and generate a matching HTML template.

    Note: Requires pdfplumber + Claude vision. Returns 501 if unavailable.
    """
    from fastapi import HTTPException
    raise HTTPException(
        status_code=501,
        detail="Invoice template analysis is not yet available. Please choose one of the three built-in templates.",
    )


# ---------------------------------------------------------------------------
# Logo upload endpoint
# ---------------------------------------------------------------------------


@router.post("/company/logo-upload")
async def upload_company_logo(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.edit")),
):
    """Upload a company logo. Stores the file and updates company.logo_url.

    Accepts: .png, .jpg, .jpeg, .svg, .webp
    On Railway: stored at /app/static/logos/. Otherwise falls back to base64 data URL.
    """
    import base64
    import os
    from fastapi import HTTPException
    from app.models.company import Company

    ALLOWED = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
    _, ext = os.path.splitext((file.filename or "").lower())
    if ext not in ALLOWED:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed. Use: {', '.join(ALLOWED)}")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Try to save to static directory
    static_dir = "/app/static/logos"
    logo_url: str | None = None

    if os.path.isdir("/app/static"):
        os.makedirs(static_dir, exist_ok=True)
        safe_name = f"{current_user.company_id}{ext}"
        path = os.path.join(static_dir, safe_name)
        with open(path, "wb") as f:
            f.write(content)
        logo_url = f"/static/logos/{safe_name}"
    else:
        # Fallback: store as base64 data URL in settings_json
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".svg": "image/svg+xml", ".webp": "image/webp"}.get(ext, "image/png")
        b64 = base64.b64encode(content).decode()
        logo_url = f"data:{mime};base64,{b64}"

    company.logo_url = logo_url
    db.commit()

    return {"logo_url": logo_url}


# ---------------------------------------------------------------------------
# Company branding settings endpoint
# ---------------------------------------------------------------------------


@router.get("/company/branding")
def get_company_branding(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.edit")),
):
    """Return current branding settings for the company branding wizard."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        return {}

    return {
        "logo_url": company.logo_url,
        "website": company.website,
        "detected_logo_url": company.get_setting("detected_logo_url"),
        "detected_logo_confidence": company.get_setting("detected_logo_confidence"),
        "detected_primary_color": company.get_setting("detected_primary_color"),
        "detected_secondary_color": company.get_setting("detected_secondary_color"),
        "detected_colors": company.get_setting("detected_colors") or [],
    }


@router.patch("/company/branding")
def update_company_branding(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.edit")),
):
    """Save confirmed logo URL and brand colors to company record."""
    from app.models.company import Company
    from app.services.invoice_settings_service import update_invoice_settings

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Company not found")

    if "logo_url" in data:
        company.logo_url = data["logo_url"]
    if "website" in data:
        company.website = data["website"]

    # Save colors to invoice settings
    color_updates: dict = {}
    if "primary_color" in data:
        color_updates["primary_color"] = data["primary_color"]
    if "secondary_color" in data:
        color_updates["secondary_color"] = data["secondary_color"]
    if color_updates:
        update_invoice_settings(db, current_user.company_id, color_updates)

    db.commit()
    return {"success": True}

