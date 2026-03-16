"""Pydantic schemas for the Sales / Accounts Receivable system."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Quote Lines
# ---------------------------------------------------------------------------


class QuoteLineCreate(BaseModel):
    product_id: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    sort_order: int = 0


class QuoteLineResponse(BaseModel):
    id: str
    quote_id: str
    product_id: str | None = None
    product_name: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    sort_order: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


class QuoteCreate(BaseModel):
    customer_id: str
    quote_date: datetime
    expiry_date: datetime
    payment_terms: str | None = None
    tax_rate: Decimal = Decimal("0.00")
    notes: str | None = None
    lines: list[QuoteLineCreate] = []


class QuoteUpdate(BaseModel):
    status: str | None = None
    expiry_date: datetime | None = None
    payment_terms: str | None = None
    notes: str | None = None


class QuoteResponse(BaseModel):
    id: str
    company_id: str
    number: str
    customer_id: str
    customer_name: str | None = None
    status: str
    quote_date: datetime
    expiry_date: datetime
    payment_terms: str | None = None
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal
    notes: str | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    lines: list[QuoteLineResponse] = []

    class Config:
        from_attributes = True


class PaginatedQuotes(BaseModel):
    items: list[QuoteResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Sales Order Lines
# ---------------------------------------------------------------------------


class SalesOrderLineCreate(BaseModel):
    product_id: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    sort_order: int = 0


class SalesOrderLineResponse(BaseModel):
    id: str
    sales_order_id: str
    product_id: str | None = None
    product_name: str | None = None
    description: str
    quantity: Decimal
    quantity_shipped: Decimal
    unit_price: Decimal
    line_total: Decimal
    sort_order: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Sales Orders
# ---------------------------------------------------------------------------


class SalesOrderCreate(BaseModel):
    customer_id: str
    quote_id: str | None = None
    order_date: datetime
    required_date: datetime | None = None
    payment_terms: str | None = None
    tax_rate: Decimal = Decimal("0.00")
    ship_to_name: str | None = None
    ship_to_address: str | None = None
    notes: str | None = None
    lines: list[SalesOrderLineCreate] = []


class SalesOrderUpdate(BaseModel):
    status: str | None = None
    required_date: datetime | None = None
    shipped_date: datetime | None = None
    notes: str | None = None


class SalesOrderResponse(BaseModel):
    id: str
    company_id: str
    number: str
    customer_id: str
    customer_name: str | None = None
    quote_id: str | None = None
    status: str
    order_date: datetime
    required_date: datetime | None = None
    shipped_date: datetime | None = None
    payment_terms: str | None = None
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal
    ship_to_name: str | None = None
    ship_to_address: str | None = None
    notes: str | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    lines: list[SalesOrderLineResponse] = []

    class Config:
        from_attributes = True


class PaginatedSalesOrders(BaseModel):
    items: list[SalesOrderResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Invoice Lines
# ---------------------------------------------------------------------------


class InvoiceLineCreate(BaseModel):
    product_id: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    sort_order: int = 0


class InvoiceLineResponse(BaseModel):
    id: str
    invoice_id: str
    product_id: str | None = None
    product_name: str | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    sort_order: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


class InvoiceCreate(BaseModel):
    customer_id: str
    sales_order_id: str | None = None
    invoice_date: datetime
    due_date: datetime
    payment_terms: str | None = None
    tax_rate: Decimal = Decimal("0.00")
    notes: str | None = None
    lines: list[InvoiceLineCreate] = []


class InvoiceUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class InvoiceResponse(BaseModel):
    id: str
    company_id: str
    number: str
    customer_id: str
    customer_name: str | None = None
    sales_order_id: str | None = None
    status: str
    invoice_date: datetime
    due_date: datetime
    payment_terms: str | None = None
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal
    amount_paid: Decimal
    balance_remaining: Decimal
    notes: str | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    lines: list[InvoiceLineResponse] = []

    class Config:
        from_attributes = True


class PaginatedInvoices(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Payment Applications
# ---------------------------------------------------------------------------


class PaymentApplicationCreate(BaseModel):
    invoice_id: str
    amount_applied: Decimal


class PaymentApplicationResponse(BaseModel):
    id: str
    payment_id: str
    invoice_id: str
    invoice_number: str | None = None
    amount_applied: Decimal

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Customer Payments
# ---------------------------------------------------------------------------


class CustomerPaymentCreate(BaseModel):
    customer_id: str
    payment_date: datetime
    total_amount: Decimal
    payment_method: str
    reference_number: str | None = None
    notes: str | None = None
    applications: list[PaymentApplicationCreate] = []


class CustomerPaymentResponse(BaseModel):
    id: str
    company_id: str
    customer_id: str
    customer_name: str | None = None
    payment_date: datetime
    total_amount: Decimal
    payment_method: str
    reference_number: str | None = None
    notes: str | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    applications: list[PaymentApplicationResponse] = []

    class Config:
        from_attributes = True


class PaginatedCustomerPayments(BaseModel):
    items: list[CustomerPaymentResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# AR Aging Report
# ---------------------------------------------------------------------------


class ARAgingBucket(BaseModel):
    current: Decimal = Decimal("0.00")
    days_1_30: Decimal = Decimal("0.00")
    days_31_60: Decimal = Decimal("0.00")
    days_61_90: Decimal = Decimal("0.00")
    days_over_90: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")


class ARAgingCustomer(BaseModel):
    customer_id: str
    customer_name: str
    account_number: str | None = None
    buckets: ARAgingBucket


class ARAgingReport(BaseModel):
    company_summary: ARAgingBucket
    customers: list[ARAgingCustomer]


# ---------------------------------------------------------------------------
# Sales Stats
# ---------------------------------------------------------------------------


class SalesStats(BaseModel):
    total_quotes: int = 0
    open_quotes: int = 0
    total_orders: int = 0
    open_orders: int = 0
    total_invoices: int = 0
    outstanding_invoices: int = 0
    total_ar_outstanding: Decimal = Decimal("0.00")


# ---------------------------------------------------------------------------
# Payment Import
# ---------------------------------------------------------------------------


class PaymentImportResultRow(BaseModel):
    row: int
    message: str


class PaymentImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[PaymentImportResultRow]
