import apiClient from "@/lib/api-client";
import type {
  PermissionOverride,
  PermissionRegistry,
  RoleCreate,
  RoleResponse,
  RoleUpdate,
} from "@/types/role";

export const roleService = {
  /** Fetch all roles for the current company. */
  async getRoles(): Promise<RoleResponse[]> {
    const response = await apiClient.get<RoleResponse[]>("/roles");
    return response.data;
  },

  /** Fetch a single role by ID. */
  async getRole(roleId: string): Promise<RoleResponse> {
    const response = await apiClient.get<RoleResponse>(`/roles/${roleId}`);
    return response.data;
  },

  /** Create a new custom role. */
  async createRole(data: RoleCreate): Promise<RoleResponse> {
    const response = await apiClient.post<RoleResponse>("/roles", data);
    return response.data;
  },

  /** Update an existing role (name, description, is_active). */
  async updateRole(roleId: string, data: RoleUpdate): Promise<RoleResponse> {
    const response = await apiClient.patch<RoleResponse>(
      `/roles/${roleId}`,
      data
    );
    return response.data;
  },

  /** Delete a custom role (system roles cannot be deleted). */
  async deleteRole(roleId: string): Promise<void> {
    await apiClient.delete(`/roles/${roleId}`);
  },

  /** Set the full permission list for a role (replaces existing). */
  async setRolePermissions(
    roleId: string,
    permissionKeys: string[]
  ): Promise<RoleResponse> {
    const response = await apiClient.put<RoleResponse>(
      `/roles/${roleId}/permissions`,
      { permission_keys: permissionKeys }
    );
    return response.data;
  },

  /** Fetch the permission registry (all available modules + actions). */
  async getPermissionRegistry(): Promise<PermissionRegistry> {
    const response = await apiClient.get<PermissionRegistry>(
      "/roles/permissions/registry"
    );
    return response.data;
  },

  /** Fetch effective permissions + overrides for a specific user. */
  async getUserPermissions(
    userId: string
  ): Promise<{
    effective_permissions: string[];
    overrides: PermissionOverride[];
  }> {
    const response = await apiClient.get(`/users/${userId}/permissions`);
    return response.data;
  },

  /** Set per-user permission overrides. */
  async setUserPermissionOverrides(
    userId: string,
    overrides: PermissionOverride[]
  ): Promise<{
    effective_permissions: string[];
    overrides: PermissionOverride[];
  }> {
    const response = await apiClient.put(`/users/${userId}/permissions`, {
      overrides,
    });
    return response.data;
  },
};
