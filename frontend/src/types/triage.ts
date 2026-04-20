/**
 * Triage — frontend type mirrors.
 *
 * Shadows `backend/app/services/triage/types.py` + the response
 * shapes in `backend/app/api/routes/triage.py`. Kept in sync by
 * field name, not by codegen — if the backend adds a field to
 * `TriageQueueConfig` or the API response, update here too.
 *
 * These are the request/response shapes the UI consumes. The
 * backend Pydantic models are the source of truth.
 */

export type TriageSchemaVersion = "1.0";

export type ActionType =
  | "approve"
  | "reject"
  | "skip"
  | "snooze"
  | "escalate"
  | "reassign"
  | "custom";

export type ContextPanelType =
  | "saved_view"
  | "document_preview"
  | "communication_thread"
  | "related_entities"
  | "ai_summary";

export interface TriageItemDisplay {
  title_field: string;
  subtitle_field?: string | null;
  body_fields: string[];
  display_component: string; // "task" | "social_service_certificate" | "generic"
}

export interface TriageActionConfig {
  action_id: string;
  label: string;
  action_type: ActionType;
  keyboard_shortcut?: string | null;
  icon: string;
  requires_reason: boolean;
  reason_options?: string[] | null;
  confirmation_required: boolean;
  handler: string;
  playwright_step_id?: string | null;
  workflow_id?: string | null;
  required_permission?: string | null;
}

export interface TriageContextPanelConfig {
  panel_type: ContextPanelType;
  title: string;
  display_order: number;
  default_collapsed: boolean;
  saved_view_id?: string | null;
  document_field?: string | null;
  related_entity_type?: string | null;
  ai_prompt_key?: string | null;
}

export interface TriageEmbeddedActionConfig {
  action_id: string;
  label: string;
  icon: string;
  playwright_step_id?: string | null;
  workflow_id?: string | null;
  creates_entity_type?: string | null;
}

export interface SnoozePreset {
  label: string;
  offset_hours: number;
}

export interface TriageFlowControls {
  snooze_enabled: boolean;
  snooze_presets: SnoozePreset[];
  approval_chain: string[];
  bulk_actions_enabled: boolean;
  rules_enabled: boolean;
}

export interface TriageCollaboration {
  multi_user_enabled: boolean;
  presence_enabled: boolean;
  audit_replay_enabled: boolean;
}

export interface TriageIntelligence {
  ai_questions_enabled: boolean;
  learning_enabled: boolean;
  anomaly_detection_enabled: boolean;
  prioritization_enabled: boolean;
  prompt_key?: string | null;
}

export interface TriageQueueConfig {
  schema_version: TriageSchemaVersion;
  queue_id: string;
  queue_name: string;
  description: string;
  source_saved_view_id?: string | null;
  source_inline_config?: Record<string, unknown> | null;
  source_direct_query_key?: string | null;
  item_entity_type: string;
  item_display: TriageItemDisplay;
  action_palette: TriageActionConfig[];
  context_panels: TriageContextPanelConfig[];
  embedded_actions: TriageEmbeddedActionConfig[];
  flow_controls: TriageFlowControls;
  collaboration: TriageCollaboration;
  intelligence: TriageIntelligence;
  permissions: string[];
  audit_level: "full" | "summary" | "minimal";
  enabled: boolean;
  display_order: number;
  required_vertical?: string | null;
  required_extension?: string | null;
}

export interface TriageItem {
  entity_type: string;
  entity_id: string;
  title: string;
  subtitle?: string | null;
  // Arbitrary per-queue extras rendered by the display component.
  [extra: string]: unknown;
}

export interface TriageActionResult {
  status: "applied" | "skipped" | "errored";
  message: string;
  next_item_id?: string | null;
  audit_log_id?: string | null;
  playwright_log_id?: string | null;
  workflow_run_id?: string | null;
}

export interface TriageSessionSummary {
  session_id: string;
  queue_id: string;
  user_id: string;
  started_at: string;
  ended_at?: string | null;
  items_processed_count: number;
  items_approved_count: number;
  items_rejected_count: number;
  items_snoozed_count: number;
  current_item_id?: string | null;
}
