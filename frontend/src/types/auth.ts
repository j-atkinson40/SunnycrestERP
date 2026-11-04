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
  /**
   * Payroll 2 — she was invited and has not signed in yet. Derived on the
   * server from the presence of an invite digest, never stored as a column.
   *
   * ⚠️ Optional because older callers and the auth `/me` payload do not carry
   * it. Treat `undefined` as "not known", not as "no invite" — a falsy check
   * conflates them, and the row that conflates them hides the Resend button
   * from the one person who needs it.
   */
  has_outstanding_invite?: boolean;
  /** When her invite link stops working. Null unless one is outstanding. */
  invite_expires_at?: string | null;
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
