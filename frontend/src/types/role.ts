export interface RoleResponse {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
  permission_keys: string[];
  created_at: string;
}

export interface RoleCreate {
  name: string;
  slug: string;
  description?: string;
  permission_keys: string[];
}

export interface RoleUpdate {
  name?: string;
  description?: string;
  is_active?: boolean;
}

export interface PermissionRegistry {
  [module: string]: string[];
}

export interface PermissionOverride {
  permission_key: string;
  granted: boolean;
}
