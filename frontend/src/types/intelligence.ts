// Types mirror backend/app/schemas/intelligence.py. Keep in sync.

export interface PromptListItem {
  id: string;
  company_id: string | null;
  prompt_key: string;
  display_name: string;
  description: string | null;
  domain: string;
  caller_module: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  active_version_id: string | null;
  active_version_number: number | null;
  active_model_preference: string | null;
  execution_count: number;
  executions_30d: number;
  error_rate_30d: number;
  avg_latency_ms_30d: number | null;
  avg_cost_usd_30d: string | null; // Decimal serialized as string
  has_draft: boolean;
}

export interface PromptVersionResponse {
  id: string;
  prompt_id: string;
  version_number: number;
  system_prompt: string;
  user_template: string;
  variable_schema: Record<string, unknown>;
  response_schema: Record<string, unknown> | null;
  model_preference: string;
  temperature: number;
  max_tokens: number;
  force_json: boolean;
  supports_streaming: boolean;
  supports_tool_use: boolean;
  supports_vision: boolean;
  vision_content_type: string | null;
  status: string; // draft | active | archived
  changelog: string | null;
  created_by: string | null;
  created_at: string;
  activated_at: string | null;
}

export interface PromptDetailResponse extends PromptListItem {
  versions: PromptVersionResponse[];
}

export interface ExecutionListItem {
  id: string;
  prompt_id: string | null;
  prompt_key: string | null;
  model_used: string | null;
  status: string;
  caller_module: string | null;
  caller_entity_type: string | null;
  caller_entity_id: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  cost_usd: string | null;
  created_at: string;
}

export interface ExecutionResponse extends ExecutionListItem {
  company_id: string | null;
  prompt_version_id: string | null;
  model_preference: string | null;
  input_hash: string | null;
  input_variables: Record<string, unknown> | null;
  rendered_system_prompt: string | null;
  rendered_user_prompt: string | null;
  response_text: string | null;
  response_parsed: Record<string, unknown> | null;
  error_message: string | null;
  caller_workflow_run_id: string | null;
  caller_workflow_step_id: string | null;
  caller_workflow_run_step_id: string | null;
  caller_agent_job_id: string | null;
  caller_conversation_id: string | null;
  caller_command_bar_session_id: string | null;
  caller_accounting_analysis_run_id: string | null;
  caller_price_list_import_id: string | null;
  caller_fh_case_id: string | null;
  caller_ringcentral_call_log_id: string | null;
  caller_kb_document_id: string | null;
  caller_import_session_id: string | null;
  experiment_id: string | null;
  experiment_variant: string | null;
}

export interface ModelRouteResponse {
  id: string;
  route_key: string;
  primary_model: string;
  fallback_model: string | null;
  provider: string;
  input_cost_per_million: string;
  output_cost_per_million: string;
  max_tokens_default: number;
  temperature_default: number;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DailyStatPoint {
  date: string;
  count: number;
  cost_usd: string;
  error_count: number;
  avg_latency_ms: number | null;
}

export interface PromptStatsResponse {
  prompt_id: string;
  prompt_key: string;
  days: number;
  total_executions: number;
  success_count: number;
  error_count: number;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
  total_cost_usd: string;
  total_input_tokens: number;
  total_output_tokens: number;
  daily_breakdown: DailyStatPoint[];
}

export interface TopPromptByVolume {
  prompt_id: string | null;
  prompt_key: string;
  count: number;
}

export interface TopPromptByCost {
  prompt_id: string | null;
  prompt_key: string;
  cost_usd: string;
}

export interface OverallStatsResponse {
  days: number;
  total_executions: number;
  success_count: number;
  error_count: number;
  error_rate: number;
  total_cost_usd: string;
  avg_latency_ms: number | null;
  top_prompts_by_volume: TopPromptByVolume[];
  top_prompts_by_cost: TopPromptByCost[];
  daily_breakdown: DailyStatPoint[];
}

export interface CallerModuleOption {
  caller_module: string;
  execution_count: number;
}

export interface ListPromptsParams {
  domain?: string;
  search?: string;
  caller_module?: string;
  model_preference?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}

export interface ListExecutionsParams {
  prompt_key?: string;
  caller_module?: string;
  caller_entity_type?: string;
  caller_entity_id?: string;
  status?: string;
  company_id?: string;
  since_days?: number;
  start_date?: string;
  end_date?: string;
  include_test_executions?: boolean;
  sort?: "created_desc" | "created_asc" | "cost_desc" | "latency_desc" | "tokens_desc";
  limit?: number;
  offset?: number;
}

// ── Phase 3b — Editing types ──────────────────────────────────────────

export interface EditPermissionResponse {
  can_edit: boolean;
  reason: string | null;
  requires_super_admin: boolean;
  requires_confirmation_text: boolean;
}

export interface DraftCreateRequest {
  base_version_id?: string;
  changelog?: string;
}

export interface DraftUpdateRequest {
  system_prompt?: string;
  user_template?: string;
  variable_schema?: Record<string, unknown>;
  response_schema?: Record<string, unknown> | null;
  model_preference?: string;
  temperature?: number;
  max_tokens?: number;
  force_json?: boolean;
  supports_streaming?: boolean;
  supports_tool_use?: boolean;
  supports_vision?: boolean;
  vision_content_type?: string | null;
  changelog?: string;
}

export interface ActivateRequest {
  changelog: string;
  confirmation_text?: string;
}

export interface RollbackRequest {
  changelog: string;
  confirmation_text?: string;
}

export interface TestRunRequest {
  variables: Record<string, unknown>;
  content_blocks?: unknown[];
  source_execution_id?: string;
}

export interface AuditLogEntry {
  id: string;
  prompt_id: string;
  version_id: string | null;
  action: string; // activate | rollback | create_draft | update_draft | delete_draft
  actor_user_id: string | null;
  actor_email: string | null;
  changelog_summary: string | null;
  meta_json: Record<string, unknown>;
  created_at: string;
}

export interface SchemaValidationIssue {
  kind: "undeclared" | "unused";
  variable: string;
}

// ── Phase 3c — Experiments ────────────────────────────────────────────

export interface ExperimentResponse {
  id: string;
  company_id: string | null;
  prompt_id: string;
  name: string;
  hypothesis: string | null;
  version_a_id: string;
  version_b_id: string;
  traffic_split: number;
  min_sample_size: number;
  status: string; // "draft" | "running" | "completed" (legacy "active")
  winner_version_id: string | null;
  conclusion_notes: string | null;
  started_at: string | null;
  concluded_at: string | null;
}

export interface ExperimentListItem extends ExperimentResponse {
  prompt_key: string | null;
  version_a_number: number | null;
  version_b_number: number | null;
  variant_a_count: number;
  variant_b_count: number;
}

export interface ExperimentVariantStats {
  variant: "a" | "b";
  version_id: string;
  sample_count: number;
  success_count: number;
  error_count: number;
  avg_latency_ms: number | null;
  avg_input_tokens: number | null;
  avg_output_tokens: number | null;
  total_cost_usd: string;
  success_rate: number;
}

export interface ExperimentDailyPoint {
  date: string;
  variant_a_count: number;
  variant_b_count: number;
  variant_a_cost_usd: number;
  variant_b_cost_usd: number;
}

export interface ExperimentResultsResponse {
  experiment_id: string;
  status: string;
  min_sample_size: number;
  variants: ExperimentVariantStats[];
  p95_latency_ms: { a: number | null; b: number | null };
  daily_breakdown: ExperimentDailyPoint[];
  ready_to_conclude: boolean;
}

export interface ExperimentCreateRequest {
  prompt_id: string;
  name: string;
  hypothesis?: string;
  version_a_id: string;
  version_b_id: string;
  traffic_split?: number;
  min_sample_size?: number;
  start_immediately?: boolean;
}

export interface ExperimentStopRequest {
  reason?: string;
}

export interface ExperimentPromoteRequest {
  variant_version_id: string;
  changelog: string;
  confirmation_text?: string;
}

export interface ListExperimentsParams {
  status?: "draft" | "running" | "completed" | "all";
  prompt_id?: string;
  limit?: number;
  offset?: number;
}
