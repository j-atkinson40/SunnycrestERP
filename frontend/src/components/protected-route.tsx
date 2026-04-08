import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { useExtensions } from "@/contexts/extension-context";
import { ModuleUpsell, getModuleMeta } from "@/components/module-upsell";

interface ProtectedRouteProps {
  requiredPermission?: string;
  requiredModule?: string;
  requiredExtension?: string;
  adminOnly?: boolean;
  requiredConsole?: string;
}

export function ProtectedRoute({ requiredPermission, requiredModule, requiredExtension, adminOnly, requiredConsole }: ProtectedRouteProps) {
  const { user, isLoading, isAuthenticated, hasPermission, hasModule, isAdmin, consoleAccess, track } = useAuth();
  const { isExtensionEnabled } = useExtensions();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredModule && !hasModule(requiredModule)) {
    const meta = getModuleMeta(requiredModule);
    return (
      <ModuleUpsell
        moduleLabel={meta.label}
        moduleDescription={meta.description}
      />
    );
  }

  if (requiredExtension && !isExtensionEnabled(requiredExtension)) {
    return (
      <ModuleUpsell
        moduleLabel={requiredExtension.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
        moduleDescription="This feature requires an extension to be installed. Visit the Extension Library to enable it."
      />
    );
  }

  if (adminOnly && !isAdmin) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (requiredPermission && user && !hasPermission(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (requiredConsole) {
    if (track !== "production_delivery" || !consoleAccess.has(requiredConsole)) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  return <Outlet />;
}
