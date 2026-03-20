import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";

export function RootRedirect() {
  const { isLoading, isAuthenticated, track, consoleAccess } = useAuth();

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

  // Production users go to console
  if (track === "production_delivery") {
    const accesses = [...consoleAccess];
    if (accesses.length === 1) {
      // Single console — go directly
      if (accesses[0] === "delivery_console") return <Navigate to="/console/delivery" replace />;
      if (accesses[0] === "production_console") return <Navigate to="/console/production" replace />;
    }
    return <Navigate to="/console" replace />;
  }

  return <Navigate to="/dashboard" replace />;
}
