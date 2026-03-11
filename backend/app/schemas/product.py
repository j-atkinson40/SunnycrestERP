from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Product Category schemas
# ---------------------------------------------------------------------------


class ProductCategoryCreate(BaseModel):
    name: str
    description: str | None = None
    parent_id: str | None = None


class ProductCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class ProductCategoryResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Price Tier schemas
# ---------------------------------------------------------------------------


class PriceTierCreate(BaseModel):
    min_quantity: int = Field(..., ge=1)
    price: Decimal
    label: str | None = None


class PriceTierUpdate(BaseModel):
    min_quantity: int | None = Field(None, ge=1)
    price: Decimal | None = None
    label: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class PriceTierResponse(BaseModel):
    id: str
    product_id: str
    min_quantity: int
    price: Decimal
    label: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Product schemas
# ---------------------------------------------------------------------------


class ProductCreate(BaseModel):
    name: str
    sku: str | None = None
    description: str | None = None
    category_id: str | None = None
    price: Decimal | None = None
    cost_price: Decimal | None = None
    unit_of_measure: str | None = None
    image_url: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    description: str | None = None
    category_id: str | None = None
    price: Decimal | None = None
    cost_price: Decimal | None = None
    unit_of_measure: str | None = None
    image_url: str | None = None
    is_active: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class ProductResponse(BaseModel):
    id: str
    company_id: str
    category_id: str | None = None
    category_name: str | None = None
    name: str
    sku: str | None = None
    description: str | None = None
    price: Decimal | None = None
    cost_price: Decimal | None = None
    unit_of_measure: str | None = None
    image_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    price_tiers: list[PriceTierResponse] = []

    model_config = {"from_attributes": True}


class PaginatedProducts(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# CSV Import schemas
# ---------------------------------------------------------------------------


class ImportResultRow(BaseModel):
    row: int
    message: str


class ImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[ImportResultRow]
