"""Schemas for the tenant onboarding system."""

from datetime import datetime

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------


class ChecklistItemUpdate(BaseModel):
    skipped: bool | None = None
    status: str | None = None  # e.g. "in_progress"


class ChecklistItemResponse(BaseModel):
    key: str
    label: str
    status: str
    skipped: bool
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChecklistResponse(BaseModel):
    id: str
    company_id: str
    preset: str
    items: list[ChecklistItemResponse]
    progress_pct: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


class ScenarioAdvance(BaseModel):
    step_key: str
    result: dict | None = None


class ScenarioStepResponse(BaseModel):
    key: str
    title: str
    description: str | None = None
    status: str
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScenarioResponse(BaseModel):
    key: str
    title: str
    description: str | None = None
    steps: list[ScenarioStepResponse]
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Product Library / Templates
# ---------------------------------------------------------------------------


class ProductTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    preset: str
    sku: str | None = None
    description: str | None = None
    default_price: float | None = None

    model_config = {"from_attributes": True}


class ProductTemplateImportRequest(BaseModel):
    template_ids: list[str]


class ProductTemplateImportResponse(BaseModel):
    imported_count: int
    product_ids: list[str]


# ---------------------------------------------------------------------------
# Data Imports
# ---------------------------------------------------------------------------


class DataImportCreate(BaseModel):
    import_type: str  # e.g. "customers", "products", "inventory"
    file_name: str
    file_url: str | None = None
    field_mapping: dict | None = None


class DataImportUpdate(BaseModel):
    field_mapping: dict | None = None
    status: str | None = None
    notes: str | None = None


class DataImportResponse(BaseModel):
    id: str
    company_id: str
    import_type: str
    file_name: str
    status: str
    row_count: int | None = None
    error_count: int | None = None
    field_mapping: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataImportPreviewResponse(BaseModel):
    headers: list[str]
    sample_rows: list[dict]
    suggested_mapping: dict | None = None
    total_rows: int


class WhiteGloveRequest(BaseModel):
    import_type: str
    description: str
    contact_email: str | None = None
    file_url: str | None = None


class WhiteGloveResponse(BaseModel):
    id: str
    status: str
    detail: str


# ---------------------------------------------------------------------------
# Integration Setup
# ---------------------------------------------------------------------------


class IntegrationSetupCreate(BaseModel):
    provider: str  # e.g. "sage_100", "quickbooks"
    config: dict | None = None


class IntegrationSetupUpdate(BaseModel):
    briefing_acknowledged: bool | None = None
    sandbox_approved: bool | None = None
    config: dict | None = None
    status: str | None = None


class IntegrationSetupResponse(BaseModel):
    id: str
    company_id: str
    provider: str
    status: str
    briefing_acknowledged: bool
    sandbox_approved: bool
    config: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Help Dismissals
# ---------------------------------------------------------------------------


class HelpDismissalCreate(BaseModel):
    help_key: str


class HelpDismissalResponse(BaseModel):
    dismissed_keys: list[str]


# ---------------------------------------------------------------------------
# Check-in Call
# ---------------------------------------------------------------------------


class CheckInCallSchedule(BaseModel):
    decision: str  # "schedule", "skip", "later"
    preferred_datetime: datetime | None = None
    notes: str | None = None


class CheckInCallResponse(BaseModel):
    id: str
    decision: str
    preferred_datetime: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Admin Analytics
# ---------------------------------------------------------------------------


class OnboardingAnalyticsResponse(BaseModel):
    total_tenants: int
    completed_count: int
    in_progress_count: int
    avg_completion_pct: float
    avg_days_to_complete: float | None = None
    drop_off_items: list[dict] | None = None


# ---------------------------------------------------------------------------
# Scheduling Board Setup
# ---------------------------------------------------------------------------


class SchedulingBoardConfig(BaseModel):
    driver_count: int = 2
    saturday_handling: str = "normal"  # normal | surcharge | no_delivery
    lead_time: str = "2_business_days"  # same_day | next_business_day | 2_business_days | custom
    lead_time_custom_days: int | None = None


# ---------------------------------------------------------------------------
# Cross-Tenant Preferences
# ---------------------------------------------------------------------------


class CrossTenantPreferences(BaseModel):
    delivery_notifications_enabled: bool = True
    cemetery_delivery_notifications: bool = True
    allow_portal_spring_burial_requests: bool = True
    accept_legacy_print_submissions: bool = True
