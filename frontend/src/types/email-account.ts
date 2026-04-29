/**
 * Email Account types — Phase W-4b Layer 1 Step 1.
 *
 * Mirror the backend Pydantic shapes in
 * `backend/app/api/routes/email_accounts.py`. Keep in sync.
 */

export type AccountType = "shared" | "personal";

export type ProviderType = "gmail" | "msgraph" | "imap" | "transactional";

export type AccessLevel = "read" | "read_write" | "admin";

export type SyncStatus = "pending" | "syncing" | "synced" | "error";

export interface EmailAccount {
  id: string;
  tenant_id: string;
  account_type: AccountType;
  display_name: string;
  email_address: string;
  provider_type: ProviderType;
  provider_config_keys: string[];
  signature_html: string | null;
  reply_to_override: string | null;
  is_active: boolean;
  is_default: boolean;
  sync_status: SyncStatus | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmailAccountAccess {
  id: string;
  account_id: string;
  user_id: string;
  user_email: string | null;
  user_name: string | null;
  access_level: AccessLevel;
  granted_by_user_id: string | null;
  granted_at: string;
  revoked_at: string | null;
}

export interface ProviderInfo {
  provider_type: ProviderType;
  display_label: string;
  supports_inbound: boolean;
  supports_realtime: boolean;
}

export interface CreateAccountRequest {
  account_type: AccountType;
  display_name: string;
  email_address: string;
  provider_type: ProviderType;
  provider_config?: Record<string, unknown>;
  signature_html?: string | null;
  reply_to_override?: string | null;
  is_default?: boolean;
}

export interface UpdateAccountRequest {
  display_name?: string;
  signature_html?: string | null;
  reply_to_override?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  provider_config_patch?: Record<string, unknown>;
}

export interface OAuthAuthorizeUrlResponse {
  authorize_url: string;
  state: string;
}
