from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Import-level schemas
# ---------------------------------------------------------------------------


class PriceListImportResponse(BaseModel):
    id: str
    tenant_id: str
    file_name: str
    file_url: str | None = None
    file_type: str
    file_size_bytes: int | None = None
    status: str
    items_extracted: int
    items_matched_high_confidence: int
    items_matched_low_confidence: int
    items_unmatched: int
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Item-level schemas
# ---------------------------------------------------------------------------


class PriceListImportItemResponse(BaseModel):
    id: str
    import_id: str
    raw_text: str | None = None
    extracted_name: str
    extracted_price: Decimal | None = None
    extracted_sku: str | None = None
    match_status: str
    matched_template_id: str | None = None
    matched_template_name: str | None = None
    match_confidence: Decimal | None = None
    match_reasoning: str | None = None
    final_product_name: str
    final_price: Decimal | None = None
    final_sku: str | None = None
    action: str
    product_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceListItemUpdate(BaseModel):
    action: str | None = None
    final_product_name: str | None = None
    final_price: Decimal | None = None
    final_sku: str | None = None
    matched_template_id: str | None = None


class PriceListConfirmResponse(BaseModel):
    import_id: str
    products_created: int
    products_skipped: int
