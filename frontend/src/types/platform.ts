/** Platform-level TypeScript types. */

export interface PlatformUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "super_admin" | "support" | "viewer";
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface TenantOverview {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  user_count: number;
  subscription_status: string | null;
  plan_name: string | null;
  created_at: string;
  company_legal_name?: string | null;
  facility_address_line1?: string | null;
  facility_address_line2?: string | null;
  facility_city?: string | null;
  facility_state?: string | null;
  facility_zip?: string | null;
  company_phone?: string | null;
  website_url?: string | null;
  npca_certification_status?: string | null;
  spring_burials_answer?: string | null;
  internal_admin_notes?: string | null;
}

export interface TenantDetail extends TenantOverview {
  users: TenantUser[];
  modules: TenantModule[];
  subscription: {
    status: string;
    plan_name: string | null;
    billing_interval: string | null;
  } | null;
  recent_syncs: SyncEntry[];
}

export interface TenantUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  role_id: string;
}

export interface TenantModule {
  module: string;
  enabled: boolean;
}

export interface SyncEntry {
  id: string;
  direction: string;
  entity_type: string;
  status: string;
  created_at: string;
  records_synced: number;
  error_message: string | null;
}

export interface SystemHealth {
  total_tenants: number;
  active_tenants: number;
  total_users: number;
  active_users: number;
  total_jobs_24h: number;
  failed_jobs_24h: number;
  redis_connected: boolean;
  db_connected: boolean;
}

export interface ImpersonationSession {
  id: string;
  platform_user_id: string;
  platform_user_name: string | null;
  tenant_id: string;
  tenant_name: string | null;
  impersonated_user_id: string | null;
  impersonated_user_name: string | null;
  ip_address: string | null;
  actions_performed: number;
  reason: string | null;
  started_at: string;
  ended_at: string | null;
}

export interface ImpersonateResponse {
  access_token: string;
  token_type: string;
  tenant_slug: string;
  tenant_name: string;
  impersonated_user_id: string;
  impersonated_user_name: string;
  expires_in_minutes: number;
  session_id: string;
}

export interface FeatureFlagMatrix {
  id: string;
  key: string;
  description: string;
  enabled_by_default: boolean;
  tenants: {
    tenant_id: string;
    tenant_name: string;
    enabled: boolean;
    has_override: boolean;
  }[];
}

// ---- Module Configuration ----

export interface ModuleDefinition {
  key: string;
  name: string;
  description: string | null;
  category: string;
  icon: string | null;
  is_core: boolean;
  dependencies: string[];
  sort_order: number;
}

export interface VerticalPreset {
  id: string;
  key: string;
  name: string;
  description: string | null;
  icon: string | null;
  module_keys: string[];
}

export interface TenantModuleConfig {
  key: string;
  name: string;
  description: string | null;
  category: string;
  icon: string | null;
  is_core: boolean;
  dependencies: string[];
  enabled: boolean;
  enabled_at: string | null;
  enabled_by: string | null;
}

export interface OnboardTenantRequest {
  name: string;
  slug: string;
  vertical: string | null;
  admin_email: string;
  admin_password: string;
  admin_first_name: string;
  admin_last_name: string;
  initial_settings?: Record<string, unknown>;
  website_url?: string;
  company_legal_name?: string;
  facility_address_line1?: string;
  facility_address_line2?: string;
  facility_city?: string;
  facility_state?: string;
  facility_zip?: string;
  company_phone?: string;
  npca_certification_status?: string;
  spring_burials_answer?: string;
  internal_admin_notes?: string;
}

export interface OnboardTenantResponse {
  tenant_id: string;
  slug: string;
  modules_enabled: number;
}
