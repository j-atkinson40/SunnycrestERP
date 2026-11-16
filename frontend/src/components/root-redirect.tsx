import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";

export function RootRedirect() {
  const { user, isLoading, isAuthenticated, track, consoleAccess } = useAuth();
  // ⚠️ OPTIONAL, NOT THE THROWING HOOK. This component previously needed
  // only `useAuth`; the throwing version made it unrenderable wherever the
  // provider is absent and reddened eight of its own tests. Null here means
  // the nav is not knowable, which for a landing decision correctly means
  // do not redirect.

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

  // ⚠️ THE AREA-LANDING BRANCH WAS HERE AND IS DELETED (2026-11-16).
  //
  // It sent an area-limited user to their own area instead of Home, via
  // `landingRouteForAreas`. It never ran: this component reads
  // `usePresetThemeOptional()`, and the only `PresetThemeProvider` in App.tsx
  // wraps a different route subtree, so the hook returned null on every render
  // and `areaLanding` was always null. The tests mocked the hook and supplied a
  // preset, which is why they were green against code that could not execute.
  //
  // James's ruling of 2026-11-16: every user lands on `/home` — the note —
  // area-limited users included. That is the `return <Navigate to="/home" />`
  // at the bottom of this function, which a payroll-limited user now reaches by
  // falling through. `test_a_payroll_limited_user_lands_on_home` below pins it
  // with no mocked hook, so it exercises the wiring rather than the helper.

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
