from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProductionLogEntryCreate(BaseModel):
    log_date: date | None = None  # defaults to today
    product_id: str
    quantity_produced: int
    mix_design_id: str | None = None
    batch_count: int | None = None
    notes: str | None = None
    entry_method: str = "manual"


class ProductionLogEntryUpdate(BaseModel):
    quantity_produced: int | None = None
    mix_design_id: str | None = None
    mix_design_name: str | None = None
    batch_count: int | None = None
    notes: str | None = None


class ProductionLogEntryResponse(BaseModel):
    id: str
    tenant_id: str
    log_date: date
    product_id: str
    product_name: str
    quantity_produced: int
    mix_design_id: str | None
    mix_design_name: str | None
    batch_count: int | None
    notes: str | None
    entered_by: str
    entry_method: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductionLogSummaryResponse(BaseModel):
    id: str
    summary_date: date
    total_units_produced: int
    products_produced: list[dict] | None

    model_config = ConfigDict(from_attributes=True)


class DailyTotalResponse(BaseModel):
    date: date
    total_units: int
    entry_count: int
    entries: list[ProductionLogEntryResponse]
