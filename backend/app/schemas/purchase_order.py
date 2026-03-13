"""Pydantic schemas for Purchase Orders."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------


class POLineCreate(BaseModel):
    product_id: str | None = None
    description: str
    quantity_ordered: Decimal
    unit_cost: Decimal
    sort_order: int = 0


class POLineUpdate(BaseModel):
    id: str | None = None  # existing line id (None = new line)
    product_id: str | None = None
    description: str | None = None
    quantity_ordered: Decimal | None = None
    unit_cost: Decimal | None = None
    sort_order: int | None = None


class POLineResponse(BaseModel):
    id: str
    po_id: str
    product_id: str | None = None
    product_name: str | None = None
    description: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    unit_cost: Decimal
    line_total: Decimal
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Receiving
# ---------------------------------------------------------------------------


class ReceiveLineItem(BaseModel):
    po_line_id: str
    quantity_received: Decimal


class ReceivePayload(BaseModel):
    lines: list[ReceiveLineItem]


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------


class PurchaseOrderCreate(BaseModel):
    vendor_id: str
    order_date: str | None = None  # ISO date string, defaults to today
    expected_date: str | None = None
    shipping_address: str | None = None
    tax_amount: Decimal = Decimal("0.00")
    notes: str | None = None
    lines: list[POLineCreate] = []

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class PurchaseOrderUpdate(BaseModel):
    vendor_id: str | None = None
    order_date: str | None = None
    expected_date: str | None = None
    shipping_address: str | None = None
    tax_amount: Decimal | None = None
    notes: str | None = None
    lines: list[POLineUpdate] | None = None  # if provided, replaces all lines

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class PurchaseOrderResponse(BaseModel):
    id: str
    company_id: str
    number: str
    vendor_id: str
    vendor_name: str | None = None
    status: str
    order_date: datetime
    expected_date: datetime | None = None
    shipping_address: str | None = None
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    notes: str | None = None
    sent_at: datetime | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    lines: list[POLineResponse] = []

    model_config = {"from_attributes": True}


class PurchaseOrderListItem(BaseModel):
    id: str
    number: str
    vendor_id: str
    vendor_name: str | None = None
    status: str
    order_date: datetime
    expected_date: datetime | None = None
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedPurchaseOrders(BaseModel):
    items: list[PurchaseOrderListItem]
    total: int
    page: int
    per_page: int


class POStats(BaseModel):
    total_pos: int
    draft: int
    sent: int
    partial: int
    received: int
    closed: int
