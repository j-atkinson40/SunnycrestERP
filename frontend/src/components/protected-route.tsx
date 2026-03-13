import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { ModuleUpsell, getModuleMeta } from "@/components/module-upsell";

interface ProtectedRouteProps {
  requiredPermission?: string;
  requiredModule?: string;
}

export function ProtectedRoute({ requiredPermission, requiredModule }: ProtectedRouteProps) {
  const { user, isLoading, isAuthenticated, hasPermission, hasModule } = useAuth();

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

  if (requiredPermission && user && !hasPermission(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <Outlet />;
}
