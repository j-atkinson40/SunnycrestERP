import apiClient from "@/lib/api-client";
import type {
  CompanyChildItem,
  HierarchyResponse,
  SetParentRequest,
} from "@/types/hierarchy";

export const hierarchyService = {
  async getTree(): Promise<HierarchyResponse> {
    const response = await apiClient.get<HierarchyResponse>("/hierarchy/tree");
    return response.data;
  },

  async getChildren(companyId: string): Promise<CompanyChildItem[]> {
    const response = await apiClient.get<CompanyChildItem[]>(
      `/hierarchy/${companyId}/children`,
    );
    return response.data;
  },

  async getAncestors(companyId: string): Promise<CompanyChildItem[]> {
    const response = await apiClient.get<CompanyChildItem[]>(
      `/hierarchy/${companyId}/ancestors`,
    );
    return response.data;
  },

  async setParent(
    companyId: string,
    data: SetParentRequest,
  ): Promise<unknown> {
    const response = await apiClient.put(
      `/hierarchy/${companyId}/parent`,
      data,
    );
    return response.data;
  },
};
