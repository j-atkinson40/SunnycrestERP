"""Schemas for the Urn Catalog Manager (Wilbert import)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UrnImportItem(BaseModel):
    wilbert_sku: str
    name: str
    wholesale_cost: float
    selling_price: float | None = None
    category: str | None = None
    size: str | None = None


class UrnBulkImportRequest(BaseModel):
    urns: list[UrnImportItem]
    markup_percent: float | None = None
    rounding: str = "1.00"  # "0.01", "0.50", "1.00", "5.00"


class UrnImportResponse(BaseModel):
    created: int
    updated: int
    total: int
    errors: list[dict] = []


class UrnProductResponse(BaseModel):
    id: str
    name: str
    wilbert_sku: str | None
    wholesale_cost: float | None
    price: float | None  # selling price
    markup_percent: float | None
    category: str | None
    source: str | None
    is_active: bool
    created_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class UrnCatalogStats(BaseModel):
    active_count: int
    inactive_count: int
    imported_count: int
    last_import_at: datetime | None


class UrnCreateRequest(BaseModel):
    name: str
    wilbert_sku: str | None = None
    wholesale_cost: float | None = None
    price: float | None = None
    markup_percent: float | None = None
    category: str | None = None
    description: str | None = None
