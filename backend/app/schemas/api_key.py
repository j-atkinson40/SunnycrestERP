from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)
    expires_at: datetime | None = None


class ApiKeyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    scopes: list[str] | None = None
    rate_limit_per_minute: int | None = Field(None, ge=1, le=10000)
    expires_at: datetime | None = None
    is_active: bool | None = None


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit_per_minute: int
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    """Returned only on creation — includes the full key (shown once)."""

    id: str
    name: str
    key: str  # Full key — only shown once
    key_prefix: str
    scopes: list[str]
    rate_limit_per_minute: int
    expires_at: datetime | None
    created_at: datetime


class ApiKeyUsageResponse(BaseModel):
    hour: datetime
    request_count: int
    error_count: int


class ApiKeyUsageSummary(BaseModel):
    api_key_id: str
    name: str
    key_prefix: str
    total_requests_24h: int
    total_errors_24h: int
    last_used_at: datetime | None
    hourly: list[ApiKeyUsageResponse]


# Available scopes
AVAILABLE_SCOPES = [
    "customers.read",
    "customers.write",
    "products.read",
    "products.write",
    "inventory.read",
    "inventory.write",
    "vendors.read",
    "vendors.write",
    "purchase_orders.read",
    "purchase_orders.write",
    "vendor_bills.read",
    "vendor_bills.write",
    "vendor_payments.read",
    "vendor_payments.write",
    "sage_exports.read",
    "sage_exports.write",
    "sync_logs.read",
]
