"""Schemas for the tenant onboarding system."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


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


class ProductImportItem(BaseModel):
    """One sellable variant the licensee ticked, with the price THEY set.

    ⚠️ `price` IS TENANT-AUTHORED DATA, not a platform value. The platform
    catalog carries no price — what a licensee charges for a Bronze Triune is
    their decision, and this field is how it arrives. A schema that accepted
    only `template_id` would discard the entire commercial half of the import.
    """

    template_id: str  # a VARIANT id — see import_product_templates
    price: float | None = Field(default=None, ge=0)
    sku: str | None = None


class ProductTemplateImportRequest(BaseModel):
    """⚠️ `products` IS AUTHORITATIVE. `template_ids` is redundant and accepted
    only because the shipped client sends both.

    Until 2026-10-05 this schema declared `template_ids` ALONE. The frontend has
    sent `{template_ids, products}` since 2026-03-17, so Pydantic's default
    extra-ignore silently dropped `products` — and with it every price the
    licensee had just typed. The route then passed `template_ids` to a service
    expecting items, so the request never got far enough for the loss to show.

    The client derives `template_ids` from `products` (`products.map(p =>
    p.template_id)` at product-library.tsx:253), so the two cannot disagree in
    practice. If they ever do, that is a client defect and `_agree` says so
    rather than silently preferring one.
    """

    products: list[ProductImportItem] = Field(min_length=1)
    #: Redundant. Kept so the shipped payload validates; never read.
    template_ids: list[str] | None = None

    @model_validator(mode="after")
    def _agree(self) -> "ProductTemplateImportRequest":
        if self.template_ids is None:
            return self
        if sorted(self.template_ids) != sorted(p.template_id for p in self.products):
            raise ValueError(
                "template_ids and products disagree. `products` is authoritative; "
                "template_ids is redundant and should be derived from it. "
                f"template_ids={sorted(self.template_ids)} "
                f"products={sorted(p.template_id for p in self.products)}"
            )
        return self


class ProductTemplateImportResponse(BaseModel):
    """⚠️ `product_ids` REMOVED 2026-10-05. It was declared 2026-03-17 and never
    produced: no route in this file carried a `response_model`, so this class was
    referenced by nothing, and the route returned a bare `int`. Removing a field
    that was never serialised cannot break a client. The count is what the
    frontend reads (`result.imported_count`).
    """

    imported_count: int


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
    kanban_driver_ids: list[str] = []
    saturday_delivery_enabled: bool = True
    saturday_surcharge_type: str | None = None  # always | spring_burials_only | none | null
    sunday_delivery_enabled: bool = False
    sunday_surcharge_enabled: bool = False


# ---------------------------------------------------------------------------
# Cross-Tenant Preferences
# ---------------------------------------------------------------------------


class CrossTenantPreferences(BaseModel):
    delivery_notifications_enabled: bool = True
    cemetery_delivery_notifications: bool = True
    allow_portal_spring_burial_requests: bool = True
    accept_legacy_print_submissions: bool = True
    # Driver status milestones
    milestone_scheduled_enabled: bool = True
    milestone_on_my_way_enabled: bool = True
    milestone_arrived_enabled: bool = True
    milestone_delivered_enabled: bool = True
