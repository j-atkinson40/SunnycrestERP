from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Fee Rate Config schemas
# ---------------------------------------------------------------------------


class FeeRateConfigCreate(BaseModel):
    transaction_type: str = Field(
        ..., description="order, invoice, payment, case_transfer"
    )
    fee_type: str = Field(
        default="transaction_percent",
        description="transaction_percent, flat_fee, subscription_addon",
    )
    rate: Decimal = Field(default=Decimal("0.0000"))
    min_fee: Decimal = Field(default=Decimal("0.00"))
    max_fee: Decimal | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None


class FeeRateConfigUpdate(BaseModel):
    rate: Decimal | None = None
    min_fee: Decimal | None = None
    max_fee: Decimal | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None


class FeeRateConfigResponse(BaseModel):
    id: str
    transaction_type: str
    fee_type: str
    rate: Decimal
    min_fee: Decimal
    max_fee: Decimal | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Platform Fee schemas
# ---------------------------------------------------------------------------


class PlatformFeeResponse(BaseModel):
    id: str
    network_transaction_id: str
    fee_rate_config_id: str | None = None
    fee_type: str
    rate: Decimal
    base_amount: Decimal
    calculated_amount: Decimal
    currency: str
    status: str
    collected_at: datetime | None = None
    waived_by: str | None = None
    waived_reason: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedFees(BaseModel):
    items: list[PlatformFeeResponse]
    total: int
    page: int
    per_page: int


class WaiveFeeRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)


class FeeStats(BaseModel):
    total_fees: int
    pending_amount: Decimal
    collected_amount: Decimal
    waived_amount: Decimal
    total_revenue: Decimal
