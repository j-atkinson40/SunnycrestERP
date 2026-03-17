import apiClient from "@/lib/api-client";
import type {
  BOM,
  BOMCreate,
  BOMLineCreate,
  BOMLineUpdate,
  BOMUpdate,
  PaginatedBOMs,
} from "@/types/bom";

export const bomService = {
  // -----------------------------------------------------------------------
  // BOMs
  // -----------------------------------------------------------------------

  async listBOMs(
    page = 1,
    perPage = 20,
    search?: string,
    status?: string,
    productId?: string,
  ): Promise<PaginatedBOMs> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (productId) params.set("product_id", productId);
    const response = await apiClient.get<PaginatedBOMs>(
      `/bom?${params.toString()}`,
    );
    return response.data;
  },

  async getBOM(id: string): Promise<BOM> {
    const response = await apiClient.get<BOM>(`/bom/${id}`);
    return response.data;
  },

  async createBOM(data: BOMCreate): Promise<BOM> {
    const response = await apiClient.post<BOM>("/bom", data);
    return response.data;
  },

  async updateBOM(id: string, data: BOMUpdate): Promise<BOM> {
    const response = await apiClient.patch<BOM>(`/bom/${id}`, data);
    return response.data;
  },

  async activateBOM(id: string): Promise<BOM> {
    const response = await apiClient.post<BOM>(`/bom/${id}/activate`);
    return response.data;
  },

  async archiveBOM(id: string): Promise<BOM> {
    const response = await apiClient.post<BOM>(`/bom/${id}/archive`);
    return response.data;
  },

  async cloneBOM(id: string): Promise<BOM> {
    const response = await apiClient.post<BOM>(`/bom/${id}/clone`);
    return response.data;
  },

  async deleteBOM(id: string): Promise<void> {
    await apiClient.delete(`/bom/${id}`);
  },

  // -----------------------------------------------------------------------
  // BOM Lines
  // -----------------------------------------------------------------------

  async addLine(bomId: string, data: BOMLineCreate): Promise<BOM> {
    const response = await apiClient.post<BOM>(`/bom/${bomId}/lines`, data);
    return response.data;
  },

  async updateLine(
    bomId: string,
    lineId: string,
    data: BOMLineUpdate,
  ): Promise<BOM> {
    const response = await apiClient.patch<BOM>(
      `/bom/${bomId}/lines/${lineId}`,
      data,
    );
    return response.data;
  },

  async removeLine(bomId: string, lineId: string): Promise<BOM> {
    const response = await apiClient.delete<BOM>(
      `/bom/${bomId}/lines/${lineId}`,
    );
    return response.data;
  },
};
