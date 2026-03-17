// --- Checklist ---

export type ChecklistPreset = 'manufacturing' | 'funeral_home' | 'cemetery' | 'crematory';
export type ChecklistStatus = 'not_started' | 'in_progress' | 'must_complete_done' | 'fully_complete';
export type ChecklistItemTier = 'must_complete' | 'should_complete' | 'optional';
export type ChecklistItemCategory = 'data_setup' | 'integration' | 'workflow' | 'team' | 'explore';
export type ChecklistItemStatus = 'not_started' | 'in_progress' | 'completed' | 'skipped';
export type ActionType = 'navigate' | 'modal' | 'external' | 'automatic';

export interface OnboardingChecklist {
  id: string;
  tenant_id: string;
  preset: ChecklistPreset;
  status: ChecklistStatus;
  must_complete_percent: number;
  overall_percent: number;
  check_in_call_offered_at: string | null;
  check_in_call_scheduled: boolean;
  check_in_call_completed_at: string | null;
  white_glove_import_requested: boolean;
  white_glove_import_completed_at: string | null;
  created_at: string;
  updated_at: string;
  items: ChecklistItem[];
}

export interface ChecklistItem {
  id: string;
  item_key: string;
  tier: ChecklistItemTier;
  category: ChecklistItemCategory;
  title: string;
  description: string | null;
  estimated_minutes: number;
  status: ChecklistItemStatus;
  completed_at: string | null;
  completed_by: string | null;
  action_type: ActionType;
  action_target: string | null;
  sort_order: number;
  depends_on: string[] | null;
}

// --- Scenarios ---

export type ScenarioStatus = 'not_started' | 'in_progress' | 'completed';

export interface OnboardingScenario {
  id: string;
  scenario_key: string;
  preset: string;
  title: string;
  description: string | null;
  estimated_minutes: number;
  step_count: number;
  status: ScenarioStatus;
  started_at: string | null;
  completed_at: string | null;
  current_step: number;
  steps: ScenarioStep[] | null;
}

export interface ScenarioStep {
  id: string;
  step_number: number;
  title: string;
  instruction: string;
  target_route: string | null;
  target_element: string | null;
  completion_trigger: string | null;
  hint_text: string | null;
}

// --- Data Imports ---

export type ImportType = 'customers' | 'products' | 'employees' | 'price_list';
export type SourceFormat = 'quickbooks_export' | 'sage_export' | 'csv_upload' | 'manual_entry' | 'white_glove';
export type ImportStatus = 'not_started' | 'mapping' | 'preview' | 'importing' | 'complete' | 'failed';

export interface DataImport {
  id: string;
  tenant_id: string;
  import_type: ImportType;
  source_format: SourceFormat;
  status: ImportStatus;
  total_records: number;
  imported_records: number;
  failed_records: number;
  field_mapping: Record<string, string> | null;
  preview_data: Record<string, unknown>[] | null;
  error_log: Record<string, unknown>[] | null;
  file_url: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface FieldMapping {
  source_column: string;
  target_field: string;
}

export interface ImportPreview {
  preview_rows: Record<string, unknown>[];
  total_records: number;
  mapped_fields: FieldMapping[];
}

// --- Integration Setup ---

export type IntegrationType = 'quickbooks' | 'sage_csv' | 'sage_api';
export type IntegrationStatus = 'not_started' | 'briefing_acknowledged' | 'sandbox_tested' | 'live';

export interface IntegrationSetup {
  id: string;
  tenant_id: string;
  integration_type: IntegrationType;
  status: IntegrationStatus;
  briefing_acknowledged_at: string | null;
  sandbox_test_run_at: string | null;
  sandbox_test_approved_at: string | null;
  went_live_at: string | null;
  created_at: string;
  updated_at: string;
}

// --- Help ---

export interface HelpDismissal {
  id: string;
  help_key: string;
  dismissed_at: string;
}

// --- Product Catalog Templates ---

export interface ProductTemplate {
  id: string;
  preset: string;
  category: string;
  product_name: string;
  product_description: string | null;
  sku_prefix: string | null;
  default_unit: string | null;
  is_manufactured: boolean;
  sort_order: number;
}

export interface ProductImportItem {
  template_id: string;
  price: number | null;
  sku: string | null;
}

// --- White Glove ---

export interface WhiteGloveRequest {
  import_type: string;
  description: string;
  contact_email: string;
}

// --- Analytics (admin) ---

export interface OnboardingAnalytics {
  avg_time_to_first_order_hours: number | null;
  must_complete_rate_7d: number;
  checklist_drop_off: Array<{ item_key: string; stuck_count: number; skipped_count: number }>;
  integration_adoption: Record<string, number>;
  scenario_completion: Record<string, number>;
  white_glove_requests: { total: number; pending: number; completed: number };
  check_in_call_rate: number;
}

// --- Contextual Help content ---

export interface HelpTooltipContent {
  key: string;
  title: string;
  body: string;
  learnMoreUrl?: string;
}

export interface ContextualHelpContent {
  route: string;
  title: string;
  sections: Array<{ heading: string; body: string }>;
}

// Helper maps for UI display
export const TIER_LABELS: Record<ChecklistItemTier, string> = {
  must_complete: 'Essential',
  should_complete: 'Recommended',
  optional: 'Optional',
};

export const TIER_COLORS: Record<ChecklistItemTier, string> = {
  must_complete: 'text-red-700 bg-red-50 border-red-200',
  should_complete: 'text-amber-700 bg-amber-50 border-amber-200',
  optional: 'text-blue-700 bg-blue-50 border-blue-200',
};

export const ITEM_STATUS_LABELS: Record<ChecklistItemStatus, string> = {
  not_started: 'Not Started',
  in_progress: 'In Progress',
  completed: 'Complete',
  skipped: 'Skipped',
};

export const CATEGORY_LABELS: Record<ChecklistItemCategory, string> = {
  data_setup: 'Data Setup',
  integration: 'Integrations',
  workflow: 'Workflows',
  team: 'Team',
  explore: 'Explore',
};
