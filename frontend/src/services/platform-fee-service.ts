import apiClient from "@/lib/api-client";
import type {
  FeeRateConfig,
  FeeRateConfigCreate,
  FeeRateConfigUpdate,
  FeeStats,
  PaginatedFees,
  PlatformFee,
} from "@/types/platform-fee";

export const platformFeeService = {
  // Fee Rate Configs
  async listConfigs(): Promise<FeeRateConfig[]> {
    const response =
      await apiClient.get<FeeRateConfig[]>("/platform-fees/configs");
    return response.data;
  },

  async createConfig(data: FeeRateConfigCreate): Promise<FeeRateConfig> {
    const response = await apiClient.post<FeeRateConfig>(
      "/platform-fees/configs",
      data,
    );
    return response.data;
  },

  async updateConfig(
    id: string,
    data: FeeRateConfigUpdate,
  ): Promise<FeeRateConfig> {
    const response = await apiClient.patch<FeeRateConfig>(
      `/platform-fees/configs/${id}`,
      data,
    );
    return response.data;
  },

  async deleteConfig(id: string): Promise<void> {
    await apiClient.delete(`/platform-fees/configs/${id}`);
  },

  // Platform Fees
  async getStats(): Promise<FeeStats> {
    const response = await apiClient.get<FeeStats>("/platform-fees/stats");
    return response.data;
  },

  async listFees(params?: {
    page?: number;
    per_page?: number;
    status?: string;
  }): Promise<PaginatedFees> {
    const response = await apiClient.get<PaginatedFees>("/platform-fees", {
      params,
    });
    return response.data;
  },

  async collectFee(id: string): Promise<PlatformFee> {
    const response = await apiClient.post<PlatformFee>(
      `/platform-fees/${id}/collect`,
    );
    return response.data;
  },

  async waiveFee(id: string, reason: string): Promise<PlatformFee> {
    const response = await apiClient.post<PlatformFee>(
      `/platform-fees/${id}/waive`,
      { reason },
    );
    return response.data;
  },
};
