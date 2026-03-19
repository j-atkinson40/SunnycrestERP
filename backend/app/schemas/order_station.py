"""Pydantic schemas for the Order Entry Station."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Quick Quote Templates
# ---------------------------------------------------------------------------


class QuickQuoteTemplateResponse(BaseModel):
    id: str
    template_name: str
    display_label: str
    display_description: str | None = None
    icon: str | None = None
    product_line: str
    sort_order: int
    is_active: bool
    is_system_template: bool
    line_items: list[dict] | None = None
    variable_fields: list[dict] | None = None
    slide_over_width: int
    primary_action: str
    quote_template_key: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Quote creation from order station
# ---------------------------------------------------------------------------


class CreateQuoteRequest(BaseModel):
    template_id: str | None = None
    customer_name: str
    customer_id: str | None = None
    product_line: str
    line_items: list[dict]
    permit_number: str | None = None
    permit_jurisdiction: str | None = None
    installation_address: str | None = None
    installation_city: str | None = None
    installation_state: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    notes: str | None = None
    delivery_charge: float | None = None


class QuoteResponse(BaseModel):
    id: str
    quote_number: str
    customer_name: str | None = None
    product_line: str | None = None
    total: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateQuoteStatusRequest(BaseModel):
    status: str  # sent, declined, expired


# ---------------------------------------------------------------------------
# Activity feed
# ---------------------------------------------------------------------------


class OrderStationActivityResponse(BaseModel):
    todays_orders: list[dict]
    pending_quotes: list[dict]
    recent_orders: list[dict]
    spring_burial_count: int
    pending_quote_count: int
    pending_quote_value: float
    flags: list[dict]
