import apiClient from "@/lib/api-client";
import type {
  Department,
  DepartmentCreate,
  DepartmentUpdate,
} from "@/types/department";

export const departmentService = {
  async getDepartments(includeInactive = false): Promise<Department[]> {
    const params = includeInactive ? "?include_inactive=true" : "";
    const response = await apiClient.get<Department[]>(
      `/departments${params}`,
    );
    return response.data;
  },

  async createDepartment(data: DepartmentCreate): Promise<Department> {
    const response = await apiClient.post<Department>("/departments", data);
    return response.data;
  },

  async updateDepartment(
    id: string,
    data: DepartmentUpdate,
  ): Promise<Department> {
    const response = await apiClient.patch<Department>(
      `/departments/${id}`,
      data,
    );
    return response.data;
  },

  async deleteDepartment(id: string): Promise<void> {
    await apiClient.delete(`/departments/${id}`);
  },
};
