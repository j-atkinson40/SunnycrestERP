import apiClient from "@/lib/api-client";
import type {
  ApiKey,
  ApiKeyCreate,
  ApiKeyCreated,
  ApiKeyUpdate,
  ApiKeyUsageSummary,
} from "@/types/api-key";

export const apiKeyService = {
  async list(): Promise<ApiKey[]> {
    const response = await apiClient.get<ApiKey[]>("/api-keys/");
    return response.data;
  },

  async get(keyId: string): Promise<ApiKey> {
    const response = await apiClient.get<ApiKey>(`/api-keys/${keyId}`);
    return response.data;
  },

  async create(data: ApiKeyCreate): Promise<ApiKeyCreated> {
    const response = await apiClient.post<ApiKeyCreated>("/api-keys/", data);
    return response.data;
  },

  async update(keyId: string, data: ApiKeyUpdate): Promise<ApiKey> {
    const response = await apiClient.patch<ApiKey>(`/api-keys/${keyId}`, data);
    return response.data;
  },

  async revoke(keyId: string): Promise<ApiKey> {
    const response = await apiClient.post<ApiKey>(`/api-keys/${keyId}/revoke`);
    return response.data;
  },

  async delete(keyId: string): Promise<void> {
    await apiClient.delete(`/api-keys/${keyId}`);
  },

  async getUsage(keyId: string, hours = 24): Promise<ApiKeyUsageSummary> {
    const response = await apiClient.get<ApiKeyUsageSummary>(
      `/api-keys/${keyId}/usage`,
      { params: { hours } },
    );
    return response.data;
  },

  async getScopes(): Promise<string[]> {
    const response = await apiClient.get<string[]>("/api-keys/scopes");
    return response.data;
  },
};
