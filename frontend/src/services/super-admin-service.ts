import apiClient from "@/lib/api-client";
import type { SuperDashboard } from "@/types/super-admin";

export const superAdminService = {
  async getDashboard(): Promise<SuperDashboard> {
    const response = await apiClient.get<SuperDashboard>(
      "/super-admin/dashboard",
    );
    return response.data;
  },
};
