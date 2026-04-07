import apiClient from "@/lib/api-client";

export interface PermissionCategory {
  [category: string]: Array<{
    slug: string;
    name: string;
    category: string;
  }>;
}

export interface CustomPermission {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  category: string;
  notification_routing: boolean;
  access_gating: boolean;
  created_at: string | null;
}

export interface UserPermissionDetails {
  role_slug: string | null;
  role_name: string | null;
  is_admin: boolean;
  role_permissions: string[];
  explicit_grants: Array<{
    permission_key: string;
    granted_by_user_id: string | null;
    notes: string | null;
    granted_at: string | null;
  }>;
  explicit_revokes: Array<{
    permission_key: string;
    granted_by_user_id: string | null;
    notes: string | null;
    granted_at: string | null;
  }>;
  effective_permissions: string[];
}

export interface PermissionAuditEntry {
  permission_key: string;
  permission_name: string;
  granted: boolean;
  change: string;
  granted_by: string;
  granted_at: string | null;
  notes: string | null;
}

export interface RoleWithPermissions {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_system: boolean;
  default_permissions: string[];
}

export const permissionService = {
  async getPermissionsByCategory(): Promise<PermissionCategory> {
    const res = await apiClient.get<PermissionCategory>("/permissions");
    return res.data;
  },

  async getCustomPermissions(): Promise<CustomPermission[]> {
    const res = await apiClient.get<CustomPermission[]>("/permissions/custom");
    return res.data;
  },

  async createCustomPermission(data: {
    name: string;
    description?: string;
    notification_routing?: boolean;
    access_gating?: boolean;
  }): Promise<CustomPermission> {
    const res = await apiClient.post<CustomPermission>("/permissions/custom", data);
    return res.data;
  },

  async updateCustomPermission(
    id: string,
    data: {
      name?: string;
      description?: string;
      notification_routing?: boolean;
      access_gating?: boolean;
    }
  ): Promise<CustomPermission> {
    const res = await apiClient.patch<CustomPermission>(`/permissions/custom/${id}`, data);
    return res.data;
  },

  async deleteCustomPermission(id: string): Promise<void> {
    await apiClient.delete(`/permissions/custom/${id}`);
  },

  async getUserPermissions(userId: string): Promise<UserPermissionDetails> {
    const res = await apiClient.get<UserPermissionDetails>(`/permissions/users/${userId}`);
    return res.data;
  },

  async grantPermission(
    userId: string,
    permissionSlug: string,
    notes?: string
  ): Promise<void> {
    await apiClient.post(`/permissions/users/${userId}/grant`, {
      permission_slug: permissionSlug,
      notes,
    });
  },

  async revokePermission(
    userId: string,
    permissionSlug: string,
    notes?: string
  ): Promise<void> {
    await apiClient.post(`/permissions/users/${userId}/revoke`, {
      permission_slug: permissionSlug,
      notes,
    });
  },

  async resetPermission(userId: string, slug: string): Promise<void> {
    await apiClient.delete(`/permissions/users/${userId}/${slug}`);
  },

  async getAuditLog(userId: string): Promise<PermissionAuditEntry[]> {
    const res = await apiClient.get<PermissionAuditEntry[]>(
      `/permissions/users/${userId}/audit-log`
    );
    return res.data;
  },

  async getRolesWithPermissions(): Promise<RoleWithPermissions[]> {
    const res = await apiClient.get<RoleWithPermissions[]>("/permissions/roles");
    return res.data;
  },
};
