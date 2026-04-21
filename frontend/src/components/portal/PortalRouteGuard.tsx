/**
 * PortalRouteGuard — Workflow Arc Phase 8e.2.
 *
 * Mirrors the tenant `ProtectedRoute` but for the portal realm.
 * Redirects unauthenticated portal users to `/portal/<slug>/login`.
 *
 * Relies on PortalAuthProvider being mounted above — reads the
 * auth state via `usePortalAuth()`. Waits for `isReady=true` before
 * rendering OR redirecting, so a valid-but-still-hydrating token
 * doesn't flash the login page.
 */

import { Navigate, Outlet } from "react-router-dom";

import { usePortalAuth } from "@/contexts/portal-auth-context";

export function PortalRouteGuard() {
  const { me, isReady, slug } = usePortalAuth();

  if (!isReady) {
    // Loading shimmer — minimal, not branded. Renders for ~100ms
    // tops on a valid session.
    return (
      <div
        className="flex min-h-screen items-center justify-center text-body-sm text-content-muted"
        data-testid="portal-hydrating"
      >
        Loading…
      </div>
    );
  }

  if (!me) {
    return <Navigate to={`/portal/${slug}/login`} replace />;
  }

  return <Outlet />;
}
