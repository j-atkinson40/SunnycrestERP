import apiClient from "@/lib/api-client";
import type { FunctionalAreasResponse } from "@/types/functional-area";

export const functionalAreaService = {
  async getAreas(): Promise<FunctionalAreasResponse> {
    const response = await apiClient.get<FunctionalAreasResponse>(
      "/team/functional-areas",
    );
    return response.data;
  },
};
