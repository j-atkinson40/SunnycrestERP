import { useAuth } from "@/contexts/auth-context";

export function usePermission(permissionKey: string): boolean {
  const { hasPermission } = useAuth();
  return hasPermission(permissionKey);
}

export function useAnyPermission(...keys: string[]): boolean {
  const { hasPermission } = useAuth();
  return keys.some(hasPermission);
}

export function useAllPermissions(...keys: string[]): boolean {
  const { hasPermission } = useAuth();
  return keys.every(hasPermission);
}

export function usePermissions() {
  const { hasPermission, permissions, user, isAdmin } = useAuth();

  return {
    hasPermission,
    hasAnyPermission: (...keys: string[]) => keys.some(hasPermission),
    hasAllPermissions: (...keys: string[]) => keys.every(hasPermission),
    isRole: (slug: string) => user?.role_slug === slug,
    isAdmin,
    permissions,
  };
}
