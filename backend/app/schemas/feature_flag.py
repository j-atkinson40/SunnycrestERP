"""Pydantic schemas for feature flags."""

from datetime import datetime

from pydantic import BaseModel, Field


class FeatureFlagResponse(BaseModel):
    id: str
    key: str
    name: str
    description: str | None = None
    category: str
    default_enabled: bool
    is_global: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TenantFlagOverride(BaseModel):
    tenant_id: str
    tenant_name: str
    enabled: bool
    notes: str | None = None
    updated_at: datetime | None = None


class FeatureFlagDetail(FeatureFlagResponse):
    overrides: list[TenantFlagOverride] = []


class TenantFeatureFlagSet(BaseModel):
    enabled: bool
    notes: str | None = None


class TenantFeatureFlagResponse(BaseModel):
    id: str
    tenant_id: str
    flag_id: str
    flag_key: str
    enabled: bool
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class FeatureFlagCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    category: str = "general"
    default_enabled: bool = False
    is_global: bool = False


class FeatureFlagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    default_enabled: bool | None = None
    is_global: bool | None = None


class BulkFlagSet(BaseModel):
    tenant_ids: list[str]
    enabled: bool


class UserFeatureFlags(BaseModel):
    """Flat dict of flag_key -> enabled for the current user's tenant."""
    flags: dict[str, bool]


class FlagAuditLogResponse(BaseModel):
    id: str
    tenant_id: str
    flag_key: str
    action: str
    endpoint: str | None = None
    user_id: str | None = None
    details: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaginatedFlagAuditLogs(BaseModel):
    items: list[FlagAuditLogResponse]
    total: int
    page: int
    per_page: int


class TenantFlagMatrix(BaseModel):
    """Matrix view: for each flag, which tenants have overrides."""
    flags: list[FeatureFlagResponse]
    tenants: list[dict]  # {id, name}
    overrides: dict[str, dict[str, bool]]  # flag_id -> {tenant_id -> enabled}
