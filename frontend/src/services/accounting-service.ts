import apiClient from "@/lib/api-client";
import type {
  AccountingProviderInfo,
  AccountingStatus,
  AccountMapping,
  ProviderAccount,
  QBOConnectResponse,
  SyncResult,
} from "@/types/accounting";

export const accountingService = {
  // Provider management
  async getProviders(): Promise<AccountingProviderInfo[]> {
    const response = await apiClient.get<AccountingProviderInfo[]>(
      "/accounting/providers",
    );
    return response.data;
  },

  async getStatus(): Promise<AccountingStatus> {
    const response = await apiClient.get<AccountingStatus>(
      "/accounting/status",
    );
    return response.data;
  },

  async testConnection(): Promise<AccountingStatus> {
    const response = await apiClient.post<AccountingStatus>(
      "/accounting/test",
    );
    return response.data;
  },

  async setProvider(provider: string): Promise<AccountingStatus> {
    const response = await apiClient.patch<AccountingStatus>(
      "/accounting/provider",
      { provider },
    );
    return response.data;
  },

  // Sync operations
  async runSync(params: {
    sync_type: string;
    direction?: string;
    date_from?: string;
    date_to?: string;
  }): Promise<SyncResult> {
    const response = await apiClient.post<SyncResult>(
      "/accounting/sync",
      params,
    );
    return response.data;
  },

  // Chart of accounts
  async getChartOfAccounts(): Promise<ProviderAccount[]> {
    const response = await apiClient.get<ProviderAccount[]>(
      "/accounting/chart-of-accounts",
    );
    return response.data;
  },

  // Account mappings
  async getMappings(): Promise<AccountMapping[]> {
    const response = await apiClient.get<AccountMapping[]>(
      "/accounting/mappings",
    );
    return response.data;
  },

  async setMapping(
    internalId: string,
    providerId: string,
  ): Promise<AccountMapping> {
    const response = await apiClient.put<AccountMapping>(
      "/accounting/mappings",
      { internal_id: internalId, provider_id: providerId },
    );
    return response.data;
  },

  // QBO OAuth
  async qboConnect(): Promise<QBOConnectResponse> {
    const response = await apiClient.post<QBOConnectResponse>(
      "/accounting/qbo/connect",
    );
    return response.data;
  },

  async qboDisconnect(): Promise<void> {
    await apiClient.post("/accounting/qbo/disconnect");
  },
};
