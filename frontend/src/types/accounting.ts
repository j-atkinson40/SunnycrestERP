export interface AccountingProviderInfo {
  key: string;
  name: string;
  description: string;
  supports_sync: boolean;
}

export interface AccountingStatus {
  provider: string;
  connected: boolean;
  last_sync_at: string | null;
  error: string | null;
  details: Record<string, unknown>;
}

export interface SyncResult {
  success: boolean;
  records_synced: number;
  records_failed: number;
  sync_log_id: string | null;
  error_message: string | null;
  details: Record<string, unknown> | null;
}

export interface ProviderAccount {
  id: string;
  name: string;
  account_type: string;
  number: string | null;
  is_active: boolean;
}

export interface AccountMapping {
  internal_id: string;
  internal_name: string;
  provider_id: string | null;
  provider_name: string | null;
}

export interface QBOConnectResponse {
  authorization_url: string;
  state: string;
}
