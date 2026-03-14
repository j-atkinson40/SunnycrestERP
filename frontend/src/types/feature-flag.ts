export interface FeatureFlag {
  id: string;
  key: string;
  name: string;
  description: string | null;
  category: string;
  default_enabled: boolean;
  is_global: boolean;
  created_at: string;
  updated_at: string;
}

export interface TenantFlagOverride {
  tenant_id: string;
  tenant_name: string;
  enabled: boolean;
  notes: string | null;
  updated_at: string | null;
}

export interface FeatureFlagDetail extends FeatureFlag {
  overrides: TenantFlagOverride[];
}

export interface TenantFlagMatrix {
  flags: FeatureFlag[];
  tenants: { id: string; name: string }[];
  overrides: Record<string, Record<string, boolean>>; // flag_id -> tenant_id -> enabled
}

export interface FlagAuditLogEntry {
  id: string;
  tenant_id: string;
  flag_key: string;
  action: string;
  endpoint: string | null;
  user_id: string | null;
  details: string | null;
  created_at: string;
}

export interface PaginatedFlagAuditLogs {
  items: FlagAuditLogEntry[];
  total: number;
  page: number;
  per_page: number;
}

export interface UserFeatureFlags {
  flags: Record<string, boolean>;
}

export interface FeatureFlagCreate {
  key: string;
  name: string;
  description?: string;
  category?: string;
  default_enabled?: boolean;
  is_global?: boolean;
}

export interface FeatureFlagUpdate {
  name?: string;
  description?: string;
  category?: string;
  default_enabled?: boolean;
  is_global?: boolean;
}
