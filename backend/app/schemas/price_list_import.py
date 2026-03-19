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
    # Conditional pricing
    extracted_price_with_vault: Decimal | None = None
    extracted_price_standalone: Decimal | None = None
    has_conditional_pricing: bool = False
    is_bundle_price_variant: bool = False
    price_variant_type: str | None = None
    # Charge matching
    charge_category: str | None = None
    charge_key_suggestion: str | None = None
    charge_match_type: str | None = None
    matched_charge_id: str | None = None
    matched_charge_name: str | None = None
    charge_key_to_use: str | None = None
    pricing_type_suggestion: str | None = None
    enable_on_import: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceListItemUpdate(BaseModel):
    action: str | None = None
    final_product_name: str | None = None
    final_price: Decimal | None = None
    final_sku: str | None = None
    matched_template_id: str | None = None
    # Conditional pricing
    has_conditional_pricing: bool | None = None
    extracted_price_with_vault: Decimal | None = None
    extracted_price_standalone: Decimal | None = None
    # Charge fields
    charge_match_type: str | None = None
    matched_charge_id: str | None = None
    charge_key_to_use: str | None = None
    pricing_type_suggestion: str | None = None
    enable_on_import: bool | None = None


class PriceListConfirmResponse(BaseModel):
    import_id: str
    products_created: int
    products_skipped: int
    charges_created: int = 0
    charges_updated: int = 0
