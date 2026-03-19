"""Charge Library schemas — request/response models for fees and surcharges."""

from pydantic import BaseModel, ConfigDict


class ChargeLibraryItemResponse(BaseModel):
    id: str
    charge_key: str
    charge_name: str
    category: str
    description: str | None
    is_enabled: bool
    is_system: bool
    pricing_type: str
    fixed_amount: float | None
    per_mile_rate: float | None
    free_radius_miles: float | None
    zone_config: list[dict] | None
    guidance_min: float | None
    guidance_max: float | None
    variable_placeholder: str | None
    auto_suggest: bool
    auto_suggest_trigger: str | None
    invoice_label: str | None
    sort_order: int
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class ChargeLibraryItemUpdate(BaseModel):
    charge_key: str
    is_enabled: bool = False
    pricing_type: str = "variable"
    fixed_amount: float | None = None
    per_mile_rate: float | None = None
    free_radius_miles: float | None = None
    zone_config: list[dict] | None = None
    guidance_min: float | None = None
    guidance_max: float | None = None
    variable_placeholder: str | None = None
    auto_suggest: bool = False
    auto_suggest_trigger: str | None = None
    invoice_label: str | None = None
    notes: str | None = None


class ChargeLibraryBulkSaveRequest(BaseModel):
    charges: list[ChargeLibraryItemUpdate]


class ChargeLibraryItemCreate(BaseModel):
    charge_name: str
    category: str = "other"
    description: str | None = None
    pricing_type: str = "variable"
    fixed_amount: float | None = None
    invoice_label: str | None = None
