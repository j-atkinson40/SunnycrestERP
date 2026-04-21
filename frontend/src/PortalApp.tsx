/**
 * PortalApp — Workflow Arc Phase 8e.2 / 8e.2.1.
 *
 * Entirely separate route tree from the tenant AppLayout. Matches
 * `/portal/:slug/*`. Owns its own providers (PortalAuthProvider +
 * PortalBrandProvider) — NEVER shares context with tenant auth.
 *
 * Route tree:
 *
 *   /portal/:slug/login                          public  (PortalBrandProvider only)
 *   /portal/:slug/reset-password?token=…         public  (PortalBrandProvider only) — Phase 8e.2.1
 *   /portal/:slug/driver                         authed  (+PortalAuthProvider + PortalRouteGuard + PortalLayout)
 *   /portal/:slug/driver/route                   authed — Phase 8e.2.1
 *   /portal/:slug/driver/stops/:stopId           authed — Phase 8e.2.1
 *   /portal/:slug/driver/mileage                 authed — Phase 8e.2.1
 *
 * The reset-password route sits OUTSIDE the auth guard on purpose:
 * the link lands in the user's email before they have a session.
 * Token is their auth; PortalBrandProvider still renders so the page
 * wears tenant chrome.
 */

import { Navigate, Route, Routes, useParams } from "react-router-dom";

import { PortalAuthProvider } from "@/contexts/portal-auth-context";
import { PortalBrandProvider } from "@/contexts/portal-brand-context";
import { PortalLayout } from "@/components/portal/PortalLayout";
import { PortalRouteGuard } from "@/components/portal/PortalRouteGuard";
import PortalLogin from "@/pages/portal/PortalLogin";
import PortalResetPassword from "@/pages/portal/PortalResetPassword";
import PortalDriverHome from "@/pages/portal/PortalDriverHome";
import PortalDriverRoute from "@/pages/portal/PortalDriverRoute";
import PortalStopDetail from "@/pages/portal/PortalStopDetail";
import PortalMileage from "@/pages/portal/PortalMileage";

function PortalShell() {
  // Grab :slug from the URL. If absent, redirect to a 404-ish landing.
  const { slug } = useParams<{ slug: string }>();
  if (!slug) {
    return <Navigate to="/" replace />;
  }

  return (
    <PortalBrandProvider slug={slug}>
      <PortalAuthProvider slug={slug}>
        <Routes>
          {/* Public (no auth required) — pre-session branded pages. */}
          <Route path="login" element={<PortalLogin />} />
          <Route path="reset-password" element={<PortalResetPassword />} />

          {/* Authed — everything under the route guard + layout shell. */}
          <Route element={<PortalRouteGuard />}>
            <Route element={<PortalLayout />}>
              <Route path="driver" element={<PortalDriverHome />} />
              <Route path="driver/route" element={<PortalDriverRoute />} />
              <Route
                path="driver/stops/:stopId"
                element={<PortalStopDetail />}
              />
              <Route path="driver/mileage" element={<PortalMileage />} />
              {/* Default: driver home. */}
              <Route index element={<Navigate to="driver" replace />} />
            </Route>
          </Route>

          {/* Unknown portal path — redirect to login. The guard will
              bounce authed users forward; unauthed users land on login. */}
          <Route path="*" element={<Navigate to="login" replace />} />
        </Routes>
      </PortalAuthProvider>
    </PortalBrandProvider>
  );
}

export function PortalApp() {
  return (
    <Routes>
      <Route path="/portal/:slug/*" element={<PortalShell />} />
      {/* Any other path under the portal detection — redirect home. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
