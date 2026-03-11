import apiClient from "@/lib/api-client";
import type {
  EmployeeProfile,
  EmployeeProfileAdminUpdate,
  EmployeeProfileUpdate,
} from "@/types/employee-profile";

export const employeeProfileService = {
  // Self-access
  async getMyProfile(): Promise<EmployeeProfile> {
    const response = await apiClient.get<EmployeeProfile>(
      "/employee-profiles/me"
    );
    return response.data;
  },

  async updateMyProfile(
    data: EmployeeProfileUpdate
  ): Promise<EmployeeProfile> {
    const response = await apiClient.patch<EmployeeProfile>(
      "/employee-profiles/me",
      data
    );
    return response.data;
  },

  // Admin access
  async getProfile(userId: string): Promise<EmployeeProfile> {
    const response = await apiClient.get<EmployeeProfile>(
      `/employee-profiles/${userId}`
    );
    return response.data;
  },

  async updateProfile(
    userId: string,
    data: EmployeeProfileAdminUpdate
  ): Promise<EmployeeProfile> {
    const response = await apiClient.patch<EmployeeProfile>(
      `/employee-profiles/${userId}`,
      data
    );
    return response.data;
  },
};
