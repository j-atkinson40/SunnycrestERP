"""Pydantic schemas for Vendor Payments."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentApplicationCreate(BaseModel):
    bill_id: str
    amount_applied: Decimal


class PaymentApplicationResponse(BaseModel):
    id: str
    payment_id: str
    bill_id: str
    bill_number: str | None = None
    amount_applied: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class VendorPaymentCreate(BaseModel):
    vendor_id: str
    payment_date: str  # ISO date
    total_amount: Decimal
    payment_method: str  # check|ach|credit_card|cash|wire
    reference_number: str | None = None
    notes: str | None = None
    applications: list[PaymentApplicationCreate]


class VendorPaymentResponse(BaseModel):
    id: str
    company_id: str
    vendor_id: str
    vendor_name: str | None = None
    payment_date: datetime
    total_amount: Decimal
    payment_method: str
    reference_number: str | None = None
    notes: str | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    applications: list[PaymentApplicationResponse] = []

    model_config = {"from_attributes": True}


class VendorPaymentListItem(BaseModel):
    id: str
    vendor_id: str
    vendor_name: str | None = None
    payment_date: datetime
    total_amount: Decimal
    payment_method: str
    reference_number: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedVendorPayments(BaseModel):
    items: list[VendorPaymentListItem]
    total: int
    page: int
    per_page: int
