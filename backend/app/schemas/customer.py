from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Customer Contact schemas
# ---------------------------------------------------------------------------


class CustomerContactCreate(BaseModel):
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    is_primary: bool = False


class CustomerContactUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    is_primary: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class CustomerContactResponse(BaseModel):
    id: str
    customer_id: str
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Customer Note schemas
# ---------------------------------------------------------------------------


class CustomerNoteCreate(BaseModel):
    note_type: str = "general"
    content: str = Field(..., min_length=1)


class CustomerNoteResponse(BaseModel):
    id: str
    customer_id: str
    note_type: str
    content: str
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Customer schemas
# ---------------------------------------------------------------------------


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1)
    account_number: str | None = None
    email: str | None = None
    phone: str | None = None
    fax: str | None = None
    contact_name: str | None = None
    website: str | None = None
    # Shipping address
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = "US"
    # Billing address
    billing_address_line1: str | None = None
    billing_address_line2: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_zip: str | None = None
    billing_country: str | None = None
    # Charge account
    credit_limit: Decimal | None = None
    payment_terms: str | None = None
    account_status: str = "active"
    # Other
    tax_exempt: bool = False
    tax_id: str | None = None
    notes: str | None = None
    sage_customer_id: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    account_number: str | None = None
    email: str | None = None
    phone: str | None = None
    fax: str | None = None
    contact_name: str | None = None
    website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    billing_address_line1: str | None = None
    billing_address_line2: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_zip: str | None = None
    billing_country: str | None = None
    credit_limit: Decimal | None = None
    payment_terms: str | None = None
    account_status: str | None = None
    tax_exempt: bool | None = None
    tax_id: str | None = None
    notes: str | None = None
    sage_customer_id: str | None = None
    is_active: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class CustomerResponse(BaseModel):
    id: str
    company_id: str
    name: str
    account_number: str | None = None
    email: str | None = None
    phone: str | None = None
    fax: str | None = None
    contact_name: str | None = None
    website: str | None = None
    # Shipping
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    # Billing
    billing_address_line1: str | None = None
    billing_address_line2: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_zip: str | None = None
    billing_country: str | None = None
    # Charge account
    credit_limit: Decimal | None = None
    payment_terms: str | None = None
    account_status: str
    current_balance: Decimal
    # Other
    tax_exempt: bool
    tax_id: str | None = None
    notes: str | None = None
    sage_customer_id: str | None = None
    # Meta
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Nested
    contacts: list[CustomerContactResponse] = []
    recent_notes: list[CustomerNoteResponse] = []

    model_config = {"from_attributes": True}


class CustomerListItem(BaseModel):
    """Lighter schema for list views — no nested contacts/notes."""

    id: str
    name: str
    account_number: str | None = None
    email: str | None = None
    phone: str | None = None
    contact_name: str | None = None
    city: str | None = None
    state: str | None = None
    account_status: str
    current_balance: Decimal
    credit_limit: Decimal | None = None
    payment_terms: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedCustomers(BaseModel):
    items: list[CustomerListItem]
    total: int
    page: int
    per_page: int


class CustomerStats(BaseModel):
    total_customers: int
    active_customers: int
    on_hold: int
    suspended: int
    total_outstanding: Decimal
    over_limit_count: int
