"""Pydantic schemas for Bridgeable Intelligence API."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Prompts ─────────────────────────────────────────────────────────────

class PromptCreate(BaseModel):
    prompt_key: str = Field(..., max_length=128)
    display_name: str = Field(..., max_length=256)
    description: str | None = None
    domain: str = Field(..., max_length=64)
    caller_module: str | None = None
    company_id: str | None = None  # null = platform-global


class PromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str | None
    prompt_key: str
    display_name: str
    description: str | None
    domain: str
    caller_module: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PromptListItem(PromptResponse):
    active_version_id: str | None = None
    active_version_number: int | None = None
    active_model_preference: str | None = None
    execution_count: int = 0
    # 30-day stats (Phase 3a)
    executions_30d: int = 0
    error_rate_30d: float = 0.0
    avg_latency_ms_30d: float | None = None
    avg_cost_usd_30d: Decimal | None = None
    # Phase 3b — draft indicator for the library badge
    has_draft: bool = False


class PromptDetailResponse(PromptResponse):
    """Prompt + all versions (metadata only, not full content)."""
    active_version_id: str | None = None
    active_version_number: int | None = None
    versions: list["PromptVersionResponse"] = Field(default_factory=list)
    executions_30d: int = 0
    error_rate_30d: float = 0.0
    avg_latency_ms_30d: float | None = None
    avg_cost_usd_30d: Decimal | None = None


# ── Prompt Versions ─────────────────────────────────────────────────────

class PromptVersionCreate(BaseModel):
    system_prompt: str
    user_template: str
    variable_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] | None = None
    model_preference: str = Field(..., max_length=64)
    temperature: float = 0.7
    max_tokens: int = 4096
    force_json: bool = False
    supports_streaming: bool = False
    supports_tool_use: bool = False
    supports_vision: bool = False
    vision_content_type: str | None = None
    changelog: str | None = None


class PromptVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    prompt_id: str
    version_number: int
    system_prompt: str
    user_template: str
    variable_schema: dict[str, Any]
    response_schema: dict[str, Any] | None
    model_preference: str
    temperature: float
    max_tokens: int
    force_json: bool
    supports_streaming: bool
    supports_tool_use: bool
    supports_vision: bool = False
    vision_content_type: str | None = None
    status: str
    changelog: str | None
    created_by: str | None
    created_at: datetime
    activated_at: datetime | None


class PromptTestRequest(BaseModel):
    """Render + execute a version without persisting execution (playground)."""
    version_id: str
    variables: dict[str, Any] = Field(default_factory=dict)


class PromptTestResponse(BaseModel):
    rendered_system_prompt: str
    rendered_user_prompt: str
    response_text: str | None = None
    response_parsed: dict[str, Any] | None = None
    model_used: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    cost_usd: Decimal | None = None
    status: str


# ── Executions ──────────────────────────────────────────────────────────

class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str | None
    prompt_id: str | None
    prompt_version_id: str | None
    model_preference: str | None
    model_used: str | None
    input_hash: str | None
    input_variables: dict[str, Any] | None
    rendered_system_prompt: str | None
    rendered_user_prompt: str | None
    response_text: str | None
    response_parsed: dict[str, Any] | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    cost_usd: Decimal | None
    status: str
    error_message: str | None
    caller_module: str | None
    caller_entity_type: str | None
    caller_entity_id: str | None
    caller_workflow_run_id: str | None
    caller_workflow_step_id: str | None
    caller_workflow_run_step_id: str | None
    caller_agent_job_id: str | None
    caller_conversation_id: str | None
    caller_command_bar_session_id: str | None
    # Phase 2c-0a linkage columns
    caller_accounting_analysis_run_id: str | None = None
    caller_price_list_import_id: str | None = None
    caller_fh_case_id: str | None = None
    caller_ringcentral_call_log_id: str | None = None
    caller_kb_document_id: str | None = None
    caller_import_session_id: str | None = None
    experiment_id: str | None
    experiment_variant: str | None
    is_test_execution: bool = False
    created_at: datetime


class ExecutionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    prompt_id: str | None
    prompt_key: str | None = None
    model_used: str | None
    status: str
    caller_module: str | None
    caller_entity_type: str | None
    caller_entity_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    cost_usd: Decimal | None
    is_test_execution: bool = False
    created_at: datetime


class ReproduceResponse(BaseModel):
    original_execution_id: str
    new_execution_id: str
    rendered_system_prompt_match: bool
    rendered_user_prompt_match: bool
    original_response_text: str | None
    new_response_text: str | None


# ── Experiments ─────────────────────────────────────────────────────────

class ExperimentCreate(BaseModel):
    prompt_id: str
    name: str = Field(..., max_length=256)
    hypothesis: str | None = None
    version_a_id: str
    version_b_id: str
    traffic_split: int = Field(50, ge=0, le=100)
    min_sample_size: int = 100
    company_id: str | None = None
    # Phase 3c — if false, create in "draft" status; POST /start transitions
    # to "running". Default True preserves Phase 1 behavior.
    start_immediately: bool = True


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str | None
    prompt_id: str
    name: str
    hypothesis: str | None
    version_a_id: str
    version_b_id: str
    traffic_split: int
    min_sample_size: int
    status: str
    winner_version_id: str | None
    conclusion_notes: str | None
    started_at: datetime | None
    concluded_at: datetime | None


class ExperimentVariantStats(BaseModel):
    variant: str  # "a" | "b"
    version_id: str
    sample_count: int
    success_count: int
    error_count: int
    avg_latency_ms: float | None
    avg_input_tokens: float | None
    avg_output_tokens: float | None
    total_cost_usd: Decimal
    success_rate: float


class ExperimentResultsResponse(BaseModel):
    experiment_id: str
    status: str
    min_sample_size: int
    variants: list[ExperimentVariantStats]
    ready_to_conclude: bool


class ExperimentConclude(BaseModel):
    winner_version_id: str
    conclusion_notes: str | None = None


# ── Phase 3c — Experiment flow schemas ─────────────────────────────────

class ExperimentStopRequest(BaseModel):
    reason: str | None = None


class ExperimentPromoteRequest(BaseModel):
    """Pick a variant as winner mid-flight. Ends the experiment and activates
    the chosen variant as the new active version of the prompt."""
    variant_version_id: str
    changelog: str = Field(..., min_length=1)
    confirmation_text: str | None = None  # required for platform-global


class ExperimentDailyPoint(BaseModel):
    date: str
    variant_a_count: int
    variant_b_count: int
    variant_a_cost_usd: float
    variant_b_cost_usd: float


class ExperimentResultsResponseExtended(BaseModel):
    """Phase 3c extension of ExperimentResultsResponse with daily breakdown
    and p95 per variant. Kept as a separate model so the Phase 1 /results
    endpoint stays stable."""
    experiment_id: str
    status: str
    min_sample_size: int
    variants: list["ExperimentVariantStats"]
    p95_latency_ms: dict[str, int | None]  # {"a": 420, "b": 510}
    daily_breakdown: list[ExperimentDailyPoint]
    ready_to_conclude: bool


class ExperimentListItem(BaseModel):
    """List-view summary — includes variant metadata + execution counts."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str | None
    prompt_id: str
    prompt_key: str | None = None
    name: str
    hypothesis: str | None
    version_a_id: str
    version_a_number: int | None = None
    version_b_id: str
    version_b_number: int | None = None
    traffic_split: int
    min_sample_size: int
    status: str
    winner_version_id: str | None
    started_at: datetime | None
    concluded_at: datetime | None
    variant_a_count: int = 0
    variant_b_count: int = 0


# Resolve the forward reference now that ExperimentVariantStats is defined above
ExperimentResultsResponseExtended.model_rebuild()


# ── Model Routes ────────────────────────────────────────────────────────

class ModelRouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    route_key: str
    primary_model: str
    fallback_model: str | None
    provider: str
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    max_tokens_default: int
    temperature_default: float
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ModelRouteUpdate(BaseModel):
    primary_model: str | None = None
    fallback_model: str | None = None
    input_cost_per_million: Decimal | None = None
    output_cost_per_million: Decimal | None = None
    max_tokens_default: int | None = None
    temperature_default: float | None = None
    is_active: bool | None = None
    notes: str | None = None


# ── Conversations ───────────────────────────────────────────────────────

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    user_id: str | None
    context_snapshot: dict[str, Any]
    started_at: datetime
    last_message_at: datetime
    message_count: int = 0


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    execution_id: str | None
    created_at: datetime


# ── Stats (Phase 3a) ────────────────────────────────────────────────────

class DailyStatPoint(BaseModel):
    date: str  # ISO YYYY-MM-DD
    count: int
    cost_usd: Decimal
    error_count: int = 0
    avg_latency_ms: float | None = None


class PromptStatsResponse(BaseModel):
    prompt_id: str
    prompt_key: str
    days: int
    total_executions: int
    success_count: int
    error_count: int
    avg_latency_ms: float | None
    p95_latency_ms: int | None
    total_cost_usd: Decimal
    total_input_tokens: int
    total_output_tokens: int
    daily_breakdown: list[DailyStatPoint]


class TopPromptByVolume(BaseModel):
    prompt_key: str
    prompt_id: str | None
    count: int


class TopPromptByCost(BaseModel):
    prompt_key: str
    prompt_id: str | None
    cost_usd: Decimal


class OverallStatsResponse(BaseModel):
    days: int
    total_executions: int
    success_count: int
    error_count: int
    error_rate: float
    total_cost_usd: Decimal
    avg_latency_ms: float | None
    top_prompts_by_volume: list[TopPromptByVolume]
    top_prompts_by_cost: list[TopPromptByCost]
    daily_breakdown: list[DailyStatPoint]


class CallerModuleOption(BaseModel):
    caller_module: str
    execution_count: int


# ── Phase 3b — Editing schemas ──────────────────────────────────────────

class DraftCreateRequest(BaseModel):
    """Clone an existing version into a new draft. If base_version_id is
    omitted, use the current active version of the prompt."""
    base_version_id: str | None = None
    changelog: str | None = None


class DraftUpdateRequest(BaseModel):
    """PATCH — all fields optional. Only draft versions are mutable."""
    system_prompt: str | None = None
    user_template: str | None = None
    variable_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None
    model_preference: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    force_json: bool | None = None
    supports_streaming: bool | None = None
    supports_tool_use: bool | None = None
    supports_vision: bool | None = None
    vision_content_type: str | None = None
    changelog: str | None = None


class ActivateRequest(BaseModel):
    changelog: str = Field(..., min_length=1)
    confirmation_text: str | None = None  # required for platform-global


class RollbackRequest(BaseModel):
    changelog: str = Field(..., min_length=1)
    confirmation_text: str | None = None  # required for platform-global


class TestRunRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    content_blocks: list[dict[str, Any]] | None = None
    source_execution_id: str | None = None


class SchemaValidationIssue(BaseModel):
    kind: str  # "undeclared" | "unused"
    variable: str


class VariableSchemaValidationError(BaseModel):
    detail: str
    issues: list[SchemaValidationIssue]


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    prompt_id: str
    version_id: str | None
    action: str
    actor_user_id: str | None
    actor_email: str | None
    changelog_summary: str | None
    meta_json: dict[str, Any]
    created_at: datetime


class EditPermissionResponse(BaseModel):
    """Returned by a preflight GET so the UI knows whether to enable Edit."""
    can_edit: bool
    reason: str | None = None  # why editing is disabled
    requires_super_admin: bool
    requires_confirmation_text: bool  # true iff platform-global


# Resolve the forward reference on PromptDetailResponse
PromptDetailResponse.model_rebuild()
