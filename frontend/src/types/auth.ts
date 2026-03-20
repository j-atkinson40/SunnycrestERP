export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role_id: string;
  role_name: string;
  role_slug: string;
  permissions: string[];
  enabled_modules: string[];
  enabled_extensions: string[];
  functional_areas: string[];
  is_active: boolean;
  company_id: string;
  created_at: string;
  track?: string;
  username?: string;
  console_access?: string[];
  idle_timeout_minutes?: number;
}

export interface LoginRequest {
  email?: string;
  password?: string;
  username?: string;
  pin?: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
