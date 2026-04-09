"""Pydantic schemas for the Urn Sales extension."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# UrnProduct
# ---------------------------------------------------------------------------


class UrnProductCreate(BaseModel):
    name: str
    sku: str | None = None
    source_type: str = "drop_ship"  # stocked | drop_ship
    material: str | None = None
    style: str | None = None
    available_colors: list[str] | None = None
    is_keepsake_set: bool = False
    companion_skus: list[str] | None = None
    engravable: bool = True
    photo_etch_capable: bool = False
    available_fonts: list[str] | None = None
    base_cost: Decimal | None = None
    retail_price: Decimal | None = None
    image_url: str | None = None
    wilbert_catalog_url: str | None = None


class UrnProductUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    material: str | None = None
    style: str | None = None
    available_colors: list[str] | None = None
    is_keepsake_set: bool | None = None
    companion_skus: list[str] | None = None
    engravable: bool | None = None
    photo_etch_capable: bool | None = None
    available_fonts: list[str] | None = None
    base_cost: Decimal | None = None
    retail_price: Decimal | None = None
    image_url: str | None = None
    wilbert_catalog_url: str | None = None
    discontinued: bool | None = None


class UrnInventoryResponse(BaseModel):
    id: str
    qty_on_hand: int
    qty_reserved: int
    reorder_point: int
    reorder_qty: int

    class Config:
        from_attributes = True


class UrnProductResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    sku: str | None = None
    source_type: str
    material: str | None = None
    style: str | None = None
    available_colors: list[str] | None = None
    is_keepsake_set: bool
    companion_skus: list[str] | None = None
    engravable: bool
    photo_etch_capable: bool
    available_fonts: list[str] | None = None
    base_cost: Decimal | None = None
    retail_price: Decimal | None = None
    image_url: str | None = None
    wilbert_catalog_url: str | None = None
    discontinued: bool
    is_active: bool
    inventory: UrnInventoryResponse | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class UrnProductSearchResult(BaseModel):
    id: str
    name: str
    sku: str | None = None
    source_type: str
    material: str | None = None
    style: str | None = None
    retail_price: Decimal | None = None
    image_url: str | None = None
    match_score: float = 0.0
    availability_note: str | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# UrnOrder
# ---------------------------------------------------------------------------


class UrnOrderCreate(BaseModel):
    funeral_home_id: str | None = None
    fh_contact_email: str | None = None
    urn_product_id: str
    quantity: int = 1
    need_by_date: date | None = None
    delivery_method: str | None = None  # with_vault | separate_delivery | will_call
    notes: str | None = None
    # Engraving specs inline (for drop_ship engravable)
    engraving_specs: list["UrnEngravingSpecsUpdate"] | None = None


class UrnOrderFromExtraction(BaseModel):
    """Intake agent / call intelligence payload — all optional except FH."""
    funeral_home_id: str
    fh_contact_email: str | None = None
    urn_product_id: str | None = None
    urn_description: str | None = None  # natural language fallback
    quantity: int | None = 1
    need_by_date: date | None = None
    delivery_method: str | None = None
    decedent_name: str | None = None
    engraving_line_1: str | None = None
    engraving_line_2: str | None = None
    engraving_line_3: str | None = None
    engraving_line_4: str | None = None
    font_selection: str | None = None
    color_selection: str | None = None
    notes: str | None = None
    confidence_scores: dict[str, float] = Field(default_factory=dict)


class UrnEngravingJobResponse(BaseModel):
    id: str
    urn_order_id: str
    piece_label: str
    engraving_line_1: str | None = None
    engraving_line_2: str | None = None
    engraving_line_3: str | None = None
    engraving_line_4: str | None = None
    font_selection: str | None = None
    color_selection: str | None = None
    photo_file_id: str | None = None
    proof_status: str
    proof_file_id: str | None = None
    proof_received_at: datetime | None = None
    fh_approval_token: str | None = None
    fh_approval_token_expires_at: datetime | None = None
    fh_approved_by_name: str | None = None
    fh_approved_at: datetime | None = None
    fh_change_request_notes: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_notes: str | None = None
    resubmission_count: int = 0
    verbal_approval_flagged: bool = False
    submitted_at: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class UrnOrderResponse(BaseModel):
    id: str
    tenant_id: str
    case_id: str | None = None
    funeral_home_id: str | None = None
    funeral_home_name: str | None = None
    fh_contact_email: str | None = None
    urn_product_id: str
    urn_product_name: str | None = None
    fulfillment_type: str
    quantity: int
    need_by_date: date | None = None
    delivery_method: str | None = None
    status: str
    wilbert_order_ref: str | None = None
    tracking_number: str | None = None
    expected_arrival_date: date | None = None
    unit_cost: Decimal | None = None
    unit_retail: Decimal | None = None
    intake_channel: str
    notes: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    engraving_jobs: list[UrnEngravingJobResponse] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Engraving
# ---------------------------------------------------------------------------


class UrnEngravingSpecsUpdate(BaseModel):
    piece_label: str | None = None  # which piece to update
    engraving_line_1: str | None = None
    engraving_line_2: str | None = None
    engraving_line_3: str | None = None
    engraving_line_4: str | None = None
    font_selection: str | None = None
    color_selection: str | None = None
    propagate_to_companions: bool = False


class WilbertFormEntry(BaseModel):
    piece_label: str
    form_fields: dict


class WilbertFormResponse(BaseModel):
    order_id: str
    entries: list[WilbertFormEntry]
    pdf_download_url: str | None = None


class CorrectionSummaryResponse(BaseModel):
    job_id: str
    piece_label: str
    original_specs: dict
    rejection_notes: str | None = None
    fh_change_request_notes: str | None = None
    resubmission_count: int


# ---------------------------------------------------------------------------
# Scheduling board integration
# ---------------------------------------------------------------------------


class AncillaryItemResponse(BaseModel):
    order_id: str
    urn_name: str
    quantity: int
    funeral_home_name: str | None = None
    need_by_date: date | None = None
    status: str


class DropShipFeedItemResponse(BaseModel):
    order_id: str
    urn_name: str
    funeral_home_name: str | None = None
    status: str
    expected_arrival_date: date | None = None
    tracking_number: str | None = None
    wilbert_order_ref: str | None = None


# ---------------------------------------------------------------------------
# Catalog sync
# ---------------------------------------------------------------------------


class CatalogSyncLogResponse(BaseModel):
    id: str
    started_at: datetime
    completed_at: datetime | None = None
    products_added: int
    products_updated: int
    products_discontinued: int
    status: str
    error_message: str | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# FH proof approval (public, token-validated)
# ---------------------------------------------------------------------------


class FHApprovalRequest(BaseModel):
    approved_by_name: str
    approved_by_email: str | None = None


class FHChangeRequest(BaseModel):
    notes: str


# ---------------------------------------------------------------------------
# Tenant settings
# ---------------------------------------------------------------------------


class UrnTenantSettingsUpdate(BaseModel):
    ancillary_window_days: int | None = None
    supplier_lead_days: int | None = None
    fh_approval_token_expiry_days: int | None = None
    proof_email_address: str | None = None
    wilbert_submission_email: str | None = None


class UrnTenantSettingsResponse(BaseModel):
    id: str
    tenant_id: str
    ancillary_window_days: int
    supplier_lead_days: int
    fh_approval_token_expiry_days: int
    proof_email_address: str | None = None
    wilbert_submission_email: str | None = None

    class Config:
        from_attributes = True
