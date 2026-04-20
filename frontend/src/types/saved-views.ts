/**
 * Saved Views — frontend type mirrors.
 *
 * These shadow `backend/app/services/saved_views/types.py`. Keep
 * names + literal sets in lockstep; add new fields on both sides in
 * the same change.
 *
 * Backend enforces schema validation in SavedViewConfig.from_dict(),
 * so the frontend types are intentionally permissive — extra keys
 * are allowed (extras: Record<string, unknown>) so future backend
 * additions don't break older clients.
 */

export type EntityType =
  | "fh_case"
  | "sales_order"
  | "invoice"
  | "contact"
  | "product"
  | "document"
  | "vault_item";

export type FilterOperator =
  | "eq"
  | "ne"
  | "contains"
  | "in"
  | "not_in"
  | "gt"
  | "lt"
  | "gte"
  | "lte"
  | "between"
  | "is_null"
  | "is_not_null";

export type SortDirection = "asc" | "desc";

export type PresentationMode =
  | "list"
  | "table"
  | "kanban"
  | "calendar"
  | "cards"
  | "chart"
  | "stat";

export type ChartType = "bar" | "line" | "pie" | "donut" | "area";

export type Aggregation = "count" | "sum" | "avg" | "min" | "max";

export type Visibility =
  | "private"
  | "role_shared"
  | "user_shared"
  | "tenant_public";

export type FieldType =
  | "text"
  | "number"
  | "currency"
  | "date"
  | "datetime"
  | "boolean"
  | "enum"
  | "relation";

// ── Query shape ───────────────────────────────────────────────────

export interface Filter {
  field: string;
  operator: FilterOperator;
  value?: unknown;
}

export interface Sort {
  field: string;
  direction: SortDirection;
}

export interface Grouping {
  field: string;
  secondary_field?: string | null;
}

export interface AggregationSpec {
  function: Aggregation;
  field?: string | null;
  alias?: string | null;
}

export interface Query {
  entity_type: EntityType;
  filters: Filter[];
  sort: Sort[];
  grouping?: Grouping | null;
  aggregations?: AggregationSpec[];
  limit?: number | null;
}

// ── Presentation shape ────────────────────────────────────────────

export interface TableConfig {
  columns: string[];
  column_widths?: Record<string, number>;
}

export interface CardConfig {
  title_field: string;
  subtitle_field?: string | null;
  body_fields: string[];
  image_field?: string | null;
}

export interface KanbanConfig {
  group_by_field: string;
  card_title_field: string;
  card_meta_fields: string[];
  columns_order?: string[];
}

export interface CalendarConfig {
  date_field: string;
  end_date_field?: string | null;
  label_field: string;
  color_field?: string | null;
}

export interface ChartConfig {
  chart_type: ChartType;
  x_field: string;
  y_field?: string | null;
  y_aggregation?: Aggregation | null;
  series_field?: string | null;
}

export interface StatConfig {
  metric_field: string;
  aggregation: Aggregation;
  label?: string | null;
  comparison_field?: string | null;
}

export interface Presentation {
  mode: PresentationMode;
  table_config?: TableConfig | null;
  card_config?: CardConfig | null;
  kanban_config?: KanbanConfig | null;
  calendar_config?: CalendarConfig | null;
  chart_config?: ChartConfig | null;
  stat_config?: StatConfig | null;
}

// ── Permissions ───────────────────────────────────────────────────

export interface CrossTenantFieldVisibility {
  per_tenant_fields: Record<string, string[]>;
}

export interface Permissions {
  owner_user_id: string;
  visibility: Visibility;
  shared_with_users?: string[];
  shared_with_roles?: string[];
  shared_with_tenants?: string[];
  cross_tenant_field_visibility?: CrossTenantFieldVisibility;
}

// ── Config envelope ──────────────────────────────────────────────

export interface SavedViewConfig {
  query: Query;
  presentation: Presentation;
  permissions: Permissions;
  extras?: Record<string, unknown>;
}

export interface SavedView {
  id: string;
  company_id: string;
  title: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  config: SavedViewConfig;
}

// ── Execution result ──────────────────────────────────────────────

export type PermissionMode = "full" | "cross_tenant_masked";

export interface SavedViewResult {
  total_count: number;
  rows: Record<string, unknown>[];
  groups?: Record<string, Record<string, unknown>[]> | null;
  aggregations?: Record<string, unknown> | null;
  permission_mode: PermissionMode;
  masked_fields: string[];
}

// ── Entity metadata ──────────────────────────────────────────────

export interface FieldMetadata {
  field_name: string;
  display_name: string;
  field_type: FieldType;
  enum_values?: string[] | null;
  relation_entity?: string | null;
  filterable?: boolean;
  sortable?: boolean;
  groupable?: boolean;
}

export interface EntityTypeMetadata {
  entity_type: EntityType;
  display_name: string;
  icon: string;
  navigate_url_template: string;
  available_fields: FieldMetadata[];
  default_sort: Sort[];
  default_columns: string[];
}

// ── Masking sentinel (MUST match backend MASK_SENTINEL) ──────────

export const MASK_SENTINEL = "__MASKED__";
