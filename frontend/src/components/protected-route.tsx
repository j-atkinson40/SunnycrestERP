import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";

interface ProtectedRouteProps {
  requiredPermission?: string;
}

export function ProtectedRoute({ requiredPermission }: ProtectedRouteProps) {
  const { user, isLoading, isAuthenticated, hasPermission } = useAuth();

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

  if (requiredPermission && user && !hasPermission(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <Outlet />;
}
