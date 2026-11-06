import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { usePresetThemeOptional } from "@/contexts/preset-theme-context";
import { landingRouteForAreas } from "@/services/navigation-service";

export function RootRedirect() {
  const { user, isLoading, isAuthenticated, track, consoleAccess, limitedToAreas } = useAuth();
  // ⚠️ OPTIONAL, NOT THE THROWING HOOK. This component previously needed
  // only `useAuth`; the throwing version made it unrenderable wherever the
  // provider is absent and reddened eight of its own tests. Null here means
  // the nav is not knowable, which for a landing decision correctly means
  // do not redirect.
  const preset = usePresetThemeOptional();

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

  // ⚠️ **AN AREA-LIMITED USER LANDS ON HER AREA, NEVER ON HOME.** James's
  // ruling of 2026-11-06, from signing in as the real payroll user: Home's
  // note comes from `/briefings/*`, which the server refuses for her, so the
  // first thing she saw after signing in was an error page. The page was
  // behaving correctly — it reported an honest failure rather than an empty
  // day — but it is the wrong destination, not a wrong message.
  //
  // ⚠️ THE ROUTE IS DERIVED FROM HER OWN RESTRICTED NAV, not from a second
  // area→route table. A hardcoded `/payroll` would be a third list to drift
  // alongside the two that already disagreed, and it would be wrong the moment
  // a second area exists. If her nav is empty this returns null and she falls
  // through to the default — she sees the honest error rather than a redirect
  // loop, which is the better failure of the two.
  //
  // Placed before the driver and console branches only in the sense of being
  // checked against them: an area-limited DRIVER would be a configuration
  // nobody has made, and the console branches key off `track`, so the ordering
  // below keeps those paths exactly as they were.
  const areaLanding = preset
    ? landingRouteForAreas(preset.navigation, limitedToAreas)
    : null;
  if (areaLanding && user?.role_slug !== "driver" && track !== "production_delivery") {
    return <Navigate to={areaLanding} replace />;
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
