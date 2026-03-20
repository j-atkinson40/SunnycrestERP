"""Schemas for the Extension Catalog system."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Enums as string literals ──


class ExtensionCatalogItem(BaseModel):
    """Single extension in the catalog — includes tenant install status."""

    id: str
    extension_key: str
    name: str  # display_name
    tagline: str | None = None
    description: str | None = None
    section: str = "core"
    category: str = "workflow"
    publisher: str = "first_party"
    applicable_verticals: list[str] = []
    default_enabled_for: list[str] = []
    access_model: str = "included"
    required_plan_tier: str | None = None
    addon_price_monthly: Decimal | None = None
    status: str = "active"
    version: str = "1.0.0"
    screenshots: list[dict] = []
    feature_bullets: list[str] = []
    setup_required: bool = False
    is_customer_requested: bool = False
    notify_me_count: int = 0
    sort_order: int = 100

    # Tenant-specific fields — merged in by the API
    installed: bool = False
    install_status: str | None = None  # active, disabled, pending_setup
    tenant_config: dict | None = None
    enabled_at: datetime | None = None
    enabled_by: str | None = None
    version_at_install: str | None = None

    model_config = {"from_attributes": True}


class ExtensionDetailResponse(ExtensionCatalogItem):
    """Full detail including config schema for setup wizard."""

    config_schema: dict = {}
    setup_config_schema: dict = {}
    hooks_registered: list[str] = []
    module_key: str = ""
    requested_by_tenant_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InstallResponse(BaseModel):
    """Response from installing an extension."""

    extension_key: str
    status: str  # active or pending_setup
    setup_config_schema: dict | None = None
    message: str


class ConfigureRequest(BaseModel):
    """Submit configuration wizard output."""

    configuration: dict


class ExtensionRegistryCreate(BaseModel):
    """Platform admin — create a new extension in the registry."""

    extension_key: str
    module_key: str = "core"
    display_name: str
    tagline: str | None = None
    description: str | None = None
    section: str = "core"
    category: str = "workflow"
    applicable_verticals: list[str] = Field(default_factory=lambda: ["all"])
    default_enabled_for: list[str] = Field(default_factory=list)
    access_model: str = "included"
    required_plan_tier: str | None = None
    addon_price_monthly: Decimal | None = None
    status: str = "active"
    version: str = "1.0.0"
    screenshots: list[dict] = Field(default_factory=list)
    feature_bullets: list[str] = Field(default_factory=list)
    setup_required: bool = False
    setup_config_schema: dict | None = None
    config_schema: dict | None = None
    hooks_registered: list[str] = Field(default_factory=list)
    sort_order: int = 100
    is_customer_requested: bool = False
    requested_by_tenant_id: str | None = None


class ExtensionRegistryUpdate(BaseModel):
    """Platform admin — update extension metadata."""

    display_name: str | None = None
    tagline: str | None = None
    description: str | None = None
    section: str | None = None
    category: str | None = None
    applicable_verticals: list[str] | None = None
    default_enabled_for: list[str] | None = None
    access_model: str | None = None
    required_plan_tier: str | None = None
    addon_price_monthly: Decimal | None = None
    status: str | None = None
    version: str | None = None
    screenshots: list[dict] | None = None
    feature_bullets: list[str] | None = None
    setup_required: bool | None = None
    setup_config_schema: dict | None = None
    config_schema: dict | None = None
    hooks_registered: list[str] | None = None
    sort_order: int | None = None
    is_customer_requested: bool | None = None
    module_key: str | None = None


class NotifyRequestResponse(BaseModel):
    extension_key: str
    notify_me_count: int
    message: str


class DemandSignalItem(BaseModel):
    """Admin view — coming_soon extension with notify interest."""

    id: str
    extension_key: str
    name: str
    section: str = "core"
    category: str
    tagline: str | None = None
    notify_me_count: int
    tenant_names: list[str] = []
    status: str


class ExtensionActivityLogItem(BaseModel):
    id: str
    tenant_id: str
    extension_id: str
    action: str
    performed_by: str | None = None
    details: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class InstalledExtensionInfo(BaseModel):
    """For the /me endpoint — lightweight extension info."""

    extension_key: str
    status: str  # active, pending_setup
    version: str | None = None
    configuration: dict | None = None
