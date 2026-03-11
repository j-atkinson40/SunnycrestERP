import { useAuth } from "@/contexts/auth-context";

export function usePermission(permissionKey: string): boolean {
  const { hasPermission } = useAuth();
  return hasPermission(permissionKey);
}

export function useAnyPermission(...keys: string[]): boolean {
  const { hasPermission } = useAuth();
  return keys.some(hasPermission);
}
