import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";

export function RootRedirect() {
  const { user, isLoading, isAuthenticated, track, consoleAccess } = useAuth();

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

  // Driver role → redirect immediately to driver console
  if (user?.role_slug === "driver") {
    return <Navigate to="/driver" replace />;
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

  // Phase W-4a Step 4 (May 2026) — canonical entry point per
  // BRIDGEABLE_MASTER §3.26.1.1: Home Space is "always present, always
  // first in navigation, contains the Pulse." RootRedirect honors that
  // canon: authenticated tenant users land on /home (Pulse) on app
  // open. /dashboard remains accessible via the Ownership space's
  // default_home_route, via direct URL, and as a coexistence surface
  // until Phase W-5 ships My Stuff + Custom Spaces and dashboard
  // retires. See Phase W-4a Step 4 routing-bug investigation.
  return <Navigate to="/home" replace />;
}
