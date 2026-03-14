import apiClient from "@/lib/api-client";
import type {
  FeatureFlag,
  FeatureFlagCreate,
  FeatureFlagDetail,
  FeatureFlagUpdate,
  PaginatedFlagAuditLogs,
  TenantFlagMatrix,
  UserFeatureFlags,
} from "@/types/feature-flag";

export const featureFlagService = {
  // User-facing
  async getMyFlags(): Promise<UserFeatureFlags> {
    const response = await apiClient.get<UserFeatureFlags>(
      "/feature-flags/me",
    );
    return response.data;
  },

  // Admin — flag CRUD
  async listFlags(): Promise<FeatureFlag[]> {
    const response = await apiClient.get<FeatureFlag[]>("/feature-flags/");
    return response.data;
  },

  async getFlag(flagId: string): Promise<FeatureFlagDetail> {
    const response = await apiClient.get<FeatureFlagDetail>(
      `/feature-flags/${flagId}`,
    );
    return response.data;
  },

  async createFlag(data: FeatureFlagCreate): Promise<FeatureFlag> {
    const response = await apiClient.post<FeatureFlag>(
      "/feature-flags/",
      data,
    );
    return response.data;
  },

  async updateFlag(
    flagId: string,
    data: FeatureFlagUpdate,
  ): Promise<FeatureFlag> {
    const response = await apiClient.patch<FeatureFlag>(
      `/feature-flags/${flagId}`,
      data,
    );
    return response.data;
  },

  async deleteFlag(flagId: string): Promise<void> {
    await apiClient.delete(`/feature-flags/${flagId}`);
  },

  // Admin — matrix
  async getMatrix(): Promise<TenantFlagMatrix> {
    const response = await apiClient.get<TenantFlagMatrix>(
      "/feature-flags/matrix",
    );
    return response.data;
  },

  // Admin — tenant overrides
  async setTenantFlag(
    flagId: string,
    tenantId: string,
    enabled: boolean,
    notes?: string,
  ): Promise<void> {
    await apiClient.put(`/feature-flags/${flagId}/tenants/${tenantId}`, {
      enabled,
      notes,
    });
  },

  async removeTenantOverride(
    flagId: string,
    tenantId: string,
  ): Promise<void> {
    await apiClient.delete(`/feature-flags/${flagId}/tenants/${tenantId}`);
  },

  async bulkSetFlag(
    flagId: string,
    tenantIds: string[],
    enabled: boolean,
  ): Promise<{ updated: number }> {
    const response = await apiClient.post<{ updated: number }>(
      `/feature-flags/${flagId}/bulk`,
      { tenant_ids: tenantIds, enabled },
    );
    return response.data;
  },

  // Admin — audit logs
  async getAuditLogs(params?: {
    page?: number;
    per_page?: number;
    flag_key?: string;
    tenant_id?: string;
    action?: string;
  }): Promise<PaginatedFlagAuditLogs> {
    const response = await apiClient.get<PaginatedFlagAuditLogs>(
      "/feature-flags/audit-logs",
      { params },
    );
    return response.data;
  },
};
