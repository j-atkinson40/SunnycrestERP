"""Pydantic schemas for the Onboarding system.

Covers both the legacy employee-onboarding templates/checklists and the newer
tenant-onboarding flow (checklists, scenarios, data imports, integrations,
product templates, white-glove imports, and analytics).
"""

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ===================================================================
# Legacy employee-onboarding schemas (kept for backward compat)
# ===================================================================


class OnboardingTemplateCreate(BaseModel):
    name: str
    items: list[str]  # list of checklist item labels


class OnboardingTemplateUpdate(BaseModel):
    name: str | None = None
    items: list[str] | None = None
    is_active: bool | None = None


class OnboardingTemplateResponse(BaseModel):
    id: str
    company_id: str
    name: str
    items: str  # JSON string in DB; frontend parses it
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OnboardingChecklistAssign(BaseModel):
    user_id: str
    template_id: str


class LegacyChecklistItemUpdate(BaseModel):
    """Update a single legacy checklist item's completed state."""
    item_index: int
    completed: bool


# Keep backward-compatible alias used by legacy onboarding routes.
# New tenant-onboarding code should use the tenant-level ChecklistItemUpdate below.
_LegacyChecklistItemUpdate = LegacyChecklistItemUpdate


class OnboardingChecklistResponse(BaseModel):
    id: str
    company_id: str
    user_id: str
    template_id: str
    items: str  # JSON string with completion state
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===================================================================
# Tenant Onboarding — Checklist
# ===================================================================


class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_key: str
    tier: str
    category: str
    title: str
    description: str | None = None
    estimated_minutes: int
    status: str
    completed_at: datetime | None = None
    completed_by: str | None = None
    action_type: str
    action_target: str | None = None
    sort_order: int
    depends_on: list[str] | None = None


class ChecklistItemUpdate(BaseModel):
    status: str | None = None
    skipped: bool | None = None


class ChecklistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    preset: str
    status: str
    must_complete_percent: int
    overall_percent: int
    check_in_call_offered_at: datetime | None = None
    check_in_call_scheduled: bool
    check_in_call_completed_at: datetime | None = None
    white_glove_import_requested: bool
    white_glove_import_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[ChecklistItemResponse] = []


# ===================================================================
# Tenant Onboarding — Scenarios
# ===================================================================


class ScenarioStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    step_number: int
    title: str
    instruction: str
    target_route: str | None = None
    target_element: str | None = None
    completion_trigger: str | None = None
    hint_text: str | None = None


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario_key: str
    preset: str
    title: str
    description: str | None = None
    estimated_minutes: int
    step_count: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_step: int
    steps: list[ScenarioStepResponse] | None = None


class ScenarioAdvance(BaseModel):
    step_number: int
    trigger_key: str | None = None


# ===================================================================
# Tenant Onboarding — Data Imports
# ===================================================================


class DataImportCreate(BaseModel):
    import_type: str
    source_format: str


class DataImportUpdate(BaseModel):
    status: str | None = None
    field_mapping: dict | None = None
    file_url: str | None = None


class DataImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    import_type: str
    source_format: str
    status: str
    total_records: int
    imported_records: int
    failed_records: int
    field_mapping: str | None = None
    preview_data: str | None = None
    error_log: str | None = None
    file_url: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class FieldMappingRequest(BaseModel):
    source_column: str
    target_field: str


class ImportPreviewResponse(BaseModel):
    preview_rows: list[dict]
    total_records: int
    mapped_fields: list[dict]


# ===================================================================
# Tenant Onboarding — Integration Setups
# ===================================================================


class IntegrationSetupCreate(BaseModel):
    integration_type: str


class IntegrationSetupUpdate(BaseModel):
    status: str | None = None
    briefing_acknowledged: bool | None = None
    sandbox_approved: bool | None = None


class IntegrationSetupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    integration_type: str
    status: str
    briefing_acknowledged_at: datetime | None = None
    sandbox_test_run_at: datetime | None = None
    sandbox_test_approved_at: datetime | None = None
    went_live_at: datetime | None = None
    connection_metadata: str | None = None
    created_at: datetime
    updated_at: datetime


# ===================================================================
# Tenant Onboarding — Help Dismissals
# ===================================================================


class HelpDismissalCreate(BaseModel):
    help_key: str


class HelpDismissalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    help_key: str
    dismissed_at: datetime


# ===================================================================
# Tenant Onboarding — Product Catalog Templates
# ===================================================================


class ProductTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    preset: str
    category: str
    product_name: str
    product_description: str | None = None
    sku_prefix: str | None = None
    default_unit: str | None = None
    is_manufactured: bool
    sort_order: int


class ProductImportItem(BaseModel):
    template_id: str
    price: float | None = None
    sku: str | None = None


class ProductTemplateImportRequest(BaseModel):
    template_ids: list[str]
    products: list[ProductImportItem]


# ===================================================================
# Tenant Onboarding — White Glove
# ===================================================================


class WhiteGloveRequest(BaseModel):
    import_type: str
    description: str
    contact_email: str


class WhiteGloveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    import_type: str
    status: str
    description: str | None = None
    created_at: datetime


# ===================================================================
# Tenant Onboarding — Check-in Call
# ===================================================================


class CheckInCallSchedule(BaseModel):
    scheduled: bool


# ===================================================================
# Tenant Onboarding — Analytics (admin)
# ===================================================================


class OnboardingAnalyticsResponse(BaseModel):
    avg_time_to_first_order_hours: float | None = None
    must_complete_rate_7d: float
    checklist_drop_off: list[dict]
    integration_adoption: dict
    scenario_completion: dict
    white_glove_requests: dict
    check_in_call_rate: float
