export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  rate_limit_per_minute: number;
  expires_at: string | null;
  last_used_at: string | null;
  is_active: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyCreated {
  id: string;
  name: string;
  key: string; // Full key — only shown once
  key_prefix: string;
  scopes: string[];
  rate_limit_per_minute: number;
  expires_at: string | null;
  created_at: string;
}

export interface ApiKeyCreate {
  name: string;
  scopes: string[];
  rate_limit_per_minute?: number;
  expires_at?: string | null;
}

export interface ApiKeyUpdate {
  name?: string;
  scopes?: string[];
  rate_limit_per_minute?: number;
  expires_at?: string | null;
  is_active?: boolean;
}

export interface ApiKeyUsageHour {
  hour: string;
  request_count: number;
  error_count: number;
}

export interface ApiKeyUsageSummary {
  api_key_id: string;
  name: string;
  key_prefix: string;
  total_requests_24h: number;
  total_errors_24h: number;
  last_used_at: string | null;
  hourly: ApiKeyUsageHour[];
}
