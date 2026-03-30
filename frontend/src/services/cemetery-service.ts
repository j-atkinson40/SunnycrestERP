import apiClient from "@/lib/api-client";
import type {
  Cemetery,
  CemeteryCreate,
  CemeteryShortlistItem,
  CemeteryUpdate,
  EquipmentPrefill,
  PaginatedCemeteries,
} from "@/types/customer";

export const cemeteryService = {
  async getCemeteries(params?: {
    search?: string;
    state?: string;
    county?: string;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedCemeteries> {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.state) qs.set("state", params.state);
    if (params?.county) qs.set("county", params.county);
    if (params?.page) qs.set("page", String(params.page));
    if (params?.per_page) qs.set("per_page", String(params.per_page));
    const response = await apiClient.get<PaginatedCemeteries>(
      `/cemeteries?${qs.toString()}`,
    );
    return response.data;
  },

  async getCemetery(id: string): Promise<Cemetery> {
    const response = await apiClient.get<Cemetery>(`/cemeteries/${id}`);
    return response.data;
  },

  async createCemetery(data: CemeteryCreate): Promise<Cemetery> {
    const response = await apiClient.post<Cemetery>("/cemeteries", data);
    return response.data;
  },

  async updateCemetery(id: string, data: CemeteryUpdate): Promise<Cemetery> {
    const response = await apiClient.patch<Cemetery>(`/cemeteries/${id}`, data);
    return response.data;
  },

  async deleteCemetery(id: string): Promise<void> {
    await apiClient.delete(`/cemeteries/${id}`);
  },

  async getEquipmentPrefill(cemeteryId: string): Promise<EquipmentPrefill> {
    const response = await apiClient.get<EquipmentPrefill>(
      `/cemeteries/${cemeteryId}/equipment-prefill`,
    );
    return response.data;
  },

  async getCemeteryShortlist(customerId: string): Promise<CemeteryShortlistItem[]> {
    const response = await apiClient.get<CemeteryShortlistItem[]>(
      `/customers/${customerId}/cemetery-shortlist`,
    );
    return response.data;
  },
};
