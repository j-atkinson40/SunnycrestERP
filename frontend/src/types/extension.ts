/** Extension Catalog types — matches backend schemas. */

export type ExtensionCategory =
  | "scheduling"
  | "compliance"
  | "integrations"
  | "reporting"
  | "workflow"
  | "communications"
  | "industry_specific";

export type ExtensionStatus = "active" | "coming_soon" | "beta" | "deprecated";
export type AccessModel = "included" | "plan_required" | "paid_addon";
export type InstallStatus = "active" | "disabled" | "pending_setup";

export interface ExtensionCatalogItem {
  id: string;
  extension_key: string;
  name: string;
  tagline: string | null;
  description: string | null;
  category: ExtensionCategory;
  publisher: string;
  applicable_verticals: string[];
  default_enabled_for: string[];
  access_model: AccessModel;
  required_plan_tier: string | null;
  addon_price_monthly: number | null;
  status: ExtensionStatus;
  version: string;
  screenshots: { url: string; caption: string }[];
  feature_bullets: string[];
  setup_required: boolean;
  is_customer_requested: boolean;
  notify_me_count: number;
  sort_order: number;

  // Tenant-specific
  installed: boolean;
  install_status: InstallStatus | null;
  tenant_config: Record<string, unknown> | null;
  enabled_at: string | null;
  enabled_by: string | null;
  version_at_install: string | null;
}

export interface ExtensionDetail extends ExtensionCatalogItem {
  config_schema: Record<string, unknown>;
  setup_config_schema: Record<string, unknown>;
  hooks_registered: string[];
  module_key: string;
  requested_by_tenant_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface InstallResponse {
  extension_key: string;
  status: string;
  setup_config_schema: Record<string, unknown> | null;
  message: string;
}

export interface NotifyResponse {
  extension_key: string;
  notify_me_count: number;
  message: string;
}

export interface DemandSignalItem {
  id: string;
  extension_key: string;
  name: string;
  category: string;
  tagline: string | null;
  notify_me_count: number;
  tenant_names: string[];
  status: string;
}

export const CATEGORY_LABELS: Record<ExtensionCategory, string> = {
  scheduling: "Scheduling",
  compliance: "Compliance",
  integrations: "Integrations",
  reporting: "Reporting",
  workflow: "Workflow",
  communications: "Communications",
  industry_specific: "Industry Specific",
};

export const CATEGORY_COLORS: Record<ExtensionCategory, string> = {
  scheduling: "bg-blue-100 text-blue-800",
  compliance: "bg-amber-100 text-amber-800",
  integrations: "bg-purple-100 text-purple-800",
  reporting: "bg-emerald-100 text-emerald-800",
  workflow: "bg-indigo-100 text-indigo-800",
  communications: "bg-pink-100 text-pink-800",
  industry_specific: "bg-orange-100 text-orange-800",
};

export const STATUS_LABELS: Record<ExtensionStatus, string> = {
  active: "Available",
  coming_soon: "Coming Soon",
  beta: "Beta",
  deprecated: "Deprecated",
};
