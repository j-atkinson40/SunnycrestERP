"""Pydantic schemas for Vendor Bills."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Bill Lines
# ---------------------------------------------------------------------------


class BillLineCreate(BaseModel):
    po_line_id: str | None = None
    description: str
    quantity: Decimal | None = None
    unit_cost: Decimal | None = None
    amount: Decimal
    expense_category: str | None = None
    sort_order: int = 0


class BillLineResponse(BaseModel):
    id: str
    bill_id: str
    po_line_id: str | None = None
    description: str
    quantity: Decimal | None = None
    unit_cost: Decimal | None = None
    amount: Decimal
    expense_category: str | None = None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Vendor Bill
# ---------------------------------------------------------------------------


class VendorBillCreate(BaseModel):
    vendor_id: str
    vendor_invoice_number: str | None = None
    po_id: str | None = None
    bill_date: str  # ISO date
    due_date: str | None = None  # auto-calculated if omitted
    subtotal: Decimal | None = None
    tax_amount: Decimal = Decimal("0.00")
    total: Decimal | None = None
    payment_terms: str | None = None
    notes: str | None = None
    lines: list[BillLineCreate] = []

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class VendorBillUpdate(BaseModel):
    vendor_id: str | None = None
    vendor_invoice_number: str | None = None
    po_id: str | None = None
    bill_date: str | None = None
    due_date: str | None = None
    tax_amount: Decimal | None = None
    payment_terms: str | None = None
    notes: str | None = None
    lines: list[BillLineCreate] | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class VendorBillResponse(BaseModel):
    id: str
    company_id: str
    number: str
    vendor_id: str
    vendor_name: str | None = None
    vendor_invoice_number: str | None = None
    po_id: str | None = None
    po_number: str | None = None
    status: str
    bill_date: datetime
    due_date: datetime
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    amount_paid: Decimal
    balance_remaining: Decimal
    payment_terms: str | None = None
    notes: str | None = None
    approved_by: str | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    lines: list[BillLineResponse] = []

    model_config = {"from_attributes": True}


class VendorBillListItem(BaseModel):
    id: str
    number: str
    vendor_id: str
    vendor_name: str | None = None
    vendor_invoice_number: str | None = None
    status: str
    bill_date: datetime
    due_date: datetime
    total: Decimal
    amount_paid: Decimal
    balance_remaining: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedVendorBills(BaseModel):
    items: list[VendorBillListItem]
    total: int
    page: int
    per_page: int
