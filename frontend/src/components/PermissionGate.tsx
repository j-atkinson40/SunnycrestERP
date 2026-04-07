import type { ReactNode } from "react";
import { useAuth } from "@/contexts/auth-context";

interface PermissionGateProps {
  permission?: string;
  permissions?: string[];
  requireAll?: boolean;
  fallback?: ReactNode;
  children: ReactNode;
}

export function PermissionGate({
  permission,
  permissions,
  requireAll = false,
  fallback = null,
  children,
}: PermissionGateProps) {
  const { hasPermission, isAdmin } = useAuth();

  if (isAdmin) return <>{children}</>;

  if (permission) {
    return hasPermission(permission) ? <>{children}</> : <>{fallback}</>;
  }

  if (permissions && permissions.length > 0) {
    const check = requireAll
      ? permissions.every(hasPermission)
      : permissions.some(hasPermission);
    return check ? <>{children}</> : <>{fallback}</>;
  }

  return <>{children}</>;
}
