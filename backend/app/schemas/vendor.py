from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Vendor Contact schemas
# ---------------------------------------------------------------------------


class VendorContactCreate(BaseModel):
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    is_primary: bool = False


class VendorContactUpdate(BaseModel):
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


class VendorContactResponse(BaseModel):
    id: str
    vendor_id: str
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Vendor Note schemas
# ---------------------------------------------------------------------------


class VendorNoteCreate(BaseModel):
    note_type: str = "general"
    content: str = Field(..., min_length=1)


class VendorNoteResponse(BaseModel):
    id: str
    vendor_id: str
    note_type: str
    content: str
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Vendor schemas
# ---------------------------------------------------------------------------


class VendorCreate(BaseModel):
    name: str = Field(..., min_length=1)
    account_number: str | None = None
    email: str | None = None
    phone: str | None = None
    fax: str | None = None
    contact_name: str | None = None
    website: str | None = None
    # Address
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = "US"
    # Purchasing info
    payment_terms: str | None = None
    vendor_status: str = "active"
    lead_time_days: int | None = None
    minimum_order: Decimal | None = None
    # Other
    tax_id: str | None = None
    notes: str | None = None
    sage_vendor_id: str | None = None


class VendorUpdate(BaseModel):
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
    payment_terms: str | None = None
    vendor_status: str | None = None
    lead_time_days: int | None = None
    minimum_order: Decimal | None = None
    tax_id: str | None = None
    notes: str | None = None
    sage_vendor_id: str | None = None
    is_active: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class VendorResponse(BaseModel):
    id: str
    company_id: str
    name: str
    account_number: str | None = None
    email: str | None = None
    phone: str | None = None
    fax: str | None = None
    contact_name: str | None = None
    website: str | None = None
    # Address
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    # Purchasing info
    payment_terms: str | None = None
    vendor_status: str
    lead_time_days: int | None = None
    minimum_order: Decimal | None = None
    # Other
    tax_id: str | None = None
    notes: str | None = None
    sage_vendor_id: str | None = None
    # Meta
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Nested
    contacts: list[VendorContactResponse] = []
    recent_notes: list[VendorNoteResponse] = []

    model_config = {"from_attributes": True}


class VendorListItem(BaseModel):
    """Lighter schema for list views — no nested contacts/notes."""

    id: str
    name: str
    account_number: str | None = None
    email: str | None = None
    phone: str | None = None
    contact_name: str | None = None
    city: str | None = None
    state: str | None = None
    vendor_status: str
    payment_terms: str | None = None
    lead_time_days: int | None = None
    minimum_order: Decimal | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedVendors(BaseModel):
    items: list[VendorListItem]
    total: int
    page: int
    per_page: int


class VendorStats(BaseModel):
    total_vendors: int
    active_vendors: int
    on_hold: int


# ---------------------------------------------------------------------------
# CSV Import schemas
# ---------------------------------------------------------------------------


class VendorImportResultRow(BaseModel):
    row: int
    message: str


class VendorImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[VendorImportResultRow]
