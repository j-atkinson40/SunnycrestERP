/** Extension Catalog API client. */

import apiClient from "@/lib/api-client";
import type {
  ExtensionCatalogItem,
  ExtensionDetail,
  InstallResponse,
  NotifyResponse,
} from "@/types/extension";

export interface CatalogParams {
  category?: string;
  vertical?: string;
  status?: string;
  search?: string;
}

export const extensionService = {
  /** Full catalog with tenant install status. */
  async listCatalog(params?: CatalogParams): Promise<ExtensionCatalogItem[]> {
    const response = await apiClient.get<ExtensionCatalogItem[]>("/extensions/", { params });
    return response.data;
  },

  /** Only installed extensions for current tenant. */
  async listInstalled(): Promise<ExtensionCatalogItem[]> {
    const response = await apiClient.get<ExtensionCatalogItem[]>("/extensions/installed");
    return response.data;
  },

  /** Single extension detail. */
  async getDetail(extensionKey: string): Promise<ExtensionDetail> {
    const response = await apiClient.get<ExtensionDetail>(`/extensions/${extensionKey}`);
    return response.data;
  },

  /** Install (enable) extension. */
  async install(extensionKey: string): Promise<InstallResponse> {
    const response = await apiClient.post<InstallResponse>(`/extensions/${extensionKey}/install`);
    return response.data;
  },

  /** Submit configuration for pending_setup extension. */
  async configure(extensionKey: string, configuration: Record<string, unknown>): Promise<{ status: string; message: string }> {
    const response = await apiClient.post(`/extensions/${extensionKey}/configure`, { configuration });
    return response.data;
  },

  /** Disable extension. */
  async disable(extensionKey: string): Promise<void> {
    await apiClient.post(`/extensions/${extensionKey}/disable`);
  },

  /** Register notify-me interest. */
  async notifyMe(extensionKey: string): Promise<NotifyResponse> {
    const response = await apiClient.post<NotifyResponse>(`/extensions/${extensionKey}/notify`);
    return response.data;
  },
};
