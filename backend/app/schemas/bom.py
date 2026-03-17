from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# BOM Line schemas
# ---------------------------------------------------------------------------


class BOMLineCreate(BaseModel):
    component_product_id: str
    quantity: Decimal = Field(..., gt=0)
    unit_of_measure: str
    waste_factor_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    notes: str | None = None
    sort_order: int = 0
    is_optional: bool = False


class BOMLineUpdate(BaseModel):
    id: str | None = None  # existing line id (None = new line to add)
    component_product_id: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_of_measure: str | None = None
    waste_factor_pct: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    sort_order: int | None = None
    is_optional: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class BOMLineResponse(BaseModel):
    id: str
    bom_id: str
    component_product_id: str
    component_product_name: str | None = None
    component_product_sku: str | None = None
    component_unit_cost: Decimal | None = None
    quantity: Decimal
    unit_of_measure: str
    waste_factor_pct: Decimal
    notes: str | None = None
    sort_order: int
    is_optional: bool
    line_cost: Decimal | None = None  # computed: unit_cost * qty * (1 + waste/100)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# BOM schemas
# ---------------------------------------------------------------------------


class BOMCreate(BaseModel):
    product_id: str
    name: str | None = None
    notes: str | None = None
    effective_date: datetime | None = None
    lines: list[BOMLineCreate] = []


class BOMUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None
    effective_date: datetime | None = None
    lines: list[BOMLineUpdate] | None = None  # None = don't touch lines

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class BOMResponse(BaseModel):
    id: str
    company_id: str
    product_id: str
    product_name: str | None = None
    product_sku: str | None = None
    version: int
    name: str | None = None
    status: str
    notes: str | None = None
    effective_date: datetime | None = None
    is_active: bool
    created_by: str | None = None
    created_by_name: str | None = None
    modified_by: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    lines: list[BOMLineResponse] = []
    cost_total: Decimal | None = None

    model_config = {"from_attributes": True}


class BOMListResponse(BaseModel):
    id: str
    company_id: str
    product_id: str
    product_name: str | None = None
    product_sku: str | None = None
    version: int
    name: str | None = None
    status: str
    effective_date: datetime | None = None
    is_active: bool
    created_at: datetime
    line_count: int = 0
    cost_total: Decimal | None = None

    model_config = {"from_attributes": True}


class BOMCloneRequest(BaseModel):
    new_version: int | None = None  # auto-calculated if omitted
