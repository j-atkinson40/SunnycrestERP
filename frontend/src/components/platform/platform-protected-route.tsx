/**
 * Route guard for platform admin pages.
 * Redirects to /login if not authenticated with a platform token.
 */

import { Navigate, Outlet } from "react-router-dom";
import { usePlatformAuth } from "@/contexts/platform-auth-context";

export function PlatformProtectedRoute() {
  const { isAuthenticated, isLoading } = usePlatformAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
