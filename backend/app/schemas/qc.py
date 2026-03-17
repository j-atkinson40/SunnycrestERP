from datetime import datetime

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Defect Type schemas
# ---------------------------------------------------------------------------


class DefectTypeCreate(BaseModel):
    defect_name: str
    product_category: str
    default_severity: str = "minor"
    default_disposition: str = "hold_pending_review"
    description: str | None = None


class DefectTypeResponse(BaseModel):
    id: str
    company_id: str
    defect_name: str
    product_category: str
    default_severity: str
    default_disposition: str
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Inspection Step schemas
# ---------------------------------------------------------------------------


class StepCreate(BaseModel):
    step_name: str
    step_order: int = 0
    inspection_type: str = "visual"
    description: str | None = None
    pass_criteria: str | None = None
    photo_required: bool = False
    required: bool = True


class StepUpdate(BaseModel):
    step_name: str | None = None
    step_order: int | None = None
    inspection_type: str | None = None
    description: str | None = None
    pass_criteria: str | None = None
    photo_required: bool | None = None
    required: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class StepResponse(BaseModel):
    id: str
    template_id: str
    company_id: str
    step_name: str
    step_order: int
    inspection_type: str
    description: str | None = None
    pass_criteria: str | None = None
    photo_required: bool
    required: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Template schemas
# ---------------------------------------------------------------------------


class TemplateCreate(BaseModel):
    product_category: str
    template_name: str
    description: str | None = None
    wilbert_warranty_compliant: bool = False
    steps: list[StepCreate] | None = None


class TemplateResponse(BaseModel):
    id: str
    company_id: str
    product_category: str
    template_name: str
    description: str | None = None
    wilbert_warranty_compliant: bool
    is_active: bool
    steps: list[StepResponse] = []
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Step Result schemas
# ---------------------------------------------------------------------------


class StepResultUpdate(BaseModel):
    result: str
    notes: str | None = None
    defect_type_id: str | None = None
    defect_severity: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class StepResultResponse(BaseModel):
    id: str
    inspection_id: str
    step_id: str
    company_id: str
    result: str
    notes: str | None = None
    defect_type_id: str | None = None
    defect_severity: str | None = None
    created_at: datetime
    step: StepResponse | None = None
    defect_type: DefectTypeResponse | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Media schemas
# ---------------------------------------------------------------------------


class MediaCreate(BaseModel):
    inspection_id: str
    step_result_id: str | None = None
    file_url: str
    caption: str | None = None
    captured_at: datetime | None = None


class MediaResponse(BaseModel):
    id: str
    step_result_id: str | None = None
    inspection_id: str
    company_id: str
    file_url: str
    caption: str | None = None
    captured_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Disposition schemas
# ---------------------------------------------------------------------------


class DispositionCreate(BaseModel):
    disposition: str
    disposition_notes: str | None = None
    rework_instructions: str | None = None


class DispositionResponse(BaseModel):
    id: str
    inspection_id: str
    company_id: str
    decided_by: str
    decided_by_name: str | None = None
    disposition: str
    disposition_notes: str | None = None
    rework_instructions: str | None = None
    decided_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Rework schemas
# ---------------------------------------------------------------------------


class ReworkCreate(BaseModel):
    rework_description: str


class ReworkResponse(BaseModel):
    id: str
    inspection_id: str
    original_inspection_id: str
    company_id: str
    rework_description: str
    rework_completed_by: str | None = None
    rework_completed_at: datetime | None = None
    re_inspection_id: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Inspection schemas
# ---------------------------------------------------------------------------


class InspectionCreate(BaseModel):
    inventory_item_id: str | None = None
    template_id: str
    product_type: str | None = None


class InspectionResponse(BaseModel):
    id: str
    company_id: str
    inventory_item_id: str | None = None
    template_id: str
    product_category: str
    product_type: str | None = None
    inspector_id: str
    inspector_name: str | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    overall_notes: str | None = None
    certificate_number: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    step_results: list[StepResultResponse] = []
    disposition: DispositionResponse | None = None
    media: list[MediaResponse] = []

    model_config = {"from_attributes": True}


class InspectionListItem(BaseModel):
    id: str
    company_id: str
    inventory_item_id: str | None = None
    template_id: str
    product_category: str
    product_type: str | None = None
    inspector_id: str
    inspector_name: str | None = None
    template_name: str | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    certificate_number: str | None = None
    created_at: datetime
    pass_count: int = 0
    fail_count: int = 0
    step_count: int = 0

    model_config = {"from_attributes": True}


class InspectionListResponse(BaseModel):
    items: list[InspectionListItem]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Report schemas
# ---------------------------------------------------------------------------


class DefectFrequency(BaseModel):
    defect_name: str
    product_category: str
    count: int
    severity: str


class InspectorPerformance(BaseModel):
    inspector_id: str
    inspector_name: str
    total_inspections: int
    pass_count: int
    fail_count: int
    avg_duration_minutes: float | None = None


class QCSummaryReport(BaseModel):
    total_inspections: int
    pass_rate: float
    fail_rate: float
    conditional_pass_rate: float
    rework_rate: float
    rework_success_rate: float
    avg_time_in_qc_minutes: float | None = None
    defect_frequency: list[DefectFrequency]
    inspector_performance: list[InspectorPerformance]


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------


class DashboardStats(BaseModel):
    pending_count: int
    in_progress_count: int
    failed_today_count: int
    passed_today_count: int
    rework_pending_count: int


# ---------------------------------------------------------------------------
# Complete inspection request
# ---------------------------------------------------------------------------


class CompleteInspectionRequest(BaseModel):
    overall_notes: str | None = None


# ---------------------------------------------------------------------------
# Paginated inspections
# ---------------------------------------------------------------------------


class PaginatedInspections(BaseModel):
    items: list[InspectionListItem]
    total: int
    page: int
    per_page: int
