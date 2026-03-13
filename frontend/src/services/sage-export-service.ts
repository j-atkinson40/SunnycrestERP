import apiClient from "@/lib/api-client";
import type {
  SageExportConfig,
  SageExportConfigUpdate,
  SageExportRequest,
  SageExportResponse,
  PaginatedSyncLogs,
} from "@/types/sage-export";

export const sageExportService = {
  async getConfig(): Promise<SageExportConfig> {
    const response = await apiClient.get<SageExportConfig>(
      "/sage-exports/config",
    );
    return response.data;
  },

  async updateConfig(
    data: SageExportConfigUpdate,
  ): Promise<SageExportConfig> {
    const response = await apiClient.patch<SageExportConfig>(
      "/sage-exports/config",
      data,
    );
    return response.data;
  },

  async generateExport(
    data: SageExportRequest,
  ): Promise<SageExportResponse> {
    const response = await apiClient.post<SageExportResponse>(
      "/sage-exports/generate",
      data,
    );
    return response.data;
  },

  async downloadExport(dateFrom: string, dateTo: string): Promise<void> {
    const params = new URLSearchParams({
      date_from: dateFrom,
      date_to: dateTo,
    });
    const response = await apiClient.get(
      `/sage-exports/download?${params.toString()}`,
      { responseType: "blob" },
    );
    const blob = new Blob([response.data], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sage_export_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  async getExportHistory(
    page = 1,
    perPage = 20,
  ): Promise<PaginatedSyncLogs> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    const response = await apiClient.get<PaginatedSyncLogs>(
      `/sage-exports/history?${params.toString()}`,
    );
    return response.data;
  },
};
