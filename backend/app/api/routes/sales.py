"""Sales & AR routes — Quotes, Sales Orders, Invoices, Customer Payments, AR Aging."""

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
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
    current_user: User = Depends(require_permission("ar.create_order")),
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
