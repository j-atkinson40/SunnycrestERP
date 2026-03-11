from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inventory Item schemas
# ---------------------------------------------------------------------------


class InventoryItemResponse(BaseModel):
    id: str
    company_id: str
    product_id: str
    product_name: str | None = None
    product_sku: str | None = None
    category_name: str | None = None
    quantity_on_hand: int
    reorder_point: int | None = None
    reorder_quantity: int | None = None
    location: str | None = None
    last_counted_at: datetime | None = None
    is_low_stock: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedInventoryItems(BaseModel):
    items: list[InventoryItemResponse]
    total: int
    page: int
    per_page: int


class InventorySettingsUpdate(BaseModel):
    reorder_point: int | None = None
    reorder_quantity: int | None = None
    location: str | None = None


# ---------------------------------------------------------------------------
# Stock operation schemas
# ---------------------------------------------------------------------------


class ReceiveStockRequest(BaseModel):
    quantity: int = Field(..., gt=0, description="Quantity to receive (must be positive)")
    reference: str | None = None
    notes: str | None = None


class AdjustStockRequest(BaseModel):
    new_quantity: int = Field(..., ge=0, description="New stock quantity (must be >= 0)")
    reference: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Transaction schemas
# ---------------------------------------------------------------------------


class InventoryTransactionResponse(BaseModel):
    id: str
    product_id: str
    product_name: str | None = None
    transaction_type: str
    quantity_change: int
    quantity_after: int
    reference: str | None = None
    notes: str | None = None
    created_by: str | None = None
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTransactions(BaseModel):
    items: list[InventoryTransactionResponse]
    total: int
    page: int
    per_page: int
