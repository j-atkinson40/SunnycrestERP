/**
 * PortalApp — Workflow Arc Phase 8e.2.
 *
 * Entirely separate route tree from the tenant AppLayout. Matches
 * `/portal/:slug/*`. Owns its own providers (PortalAuthProvider +
 * PortalBrandProvider) — NEVER shares context with tenant auth.
 *
 * Structure:
 *
 *   /portal/:slug/login                          public (PortalBrandProvider only)
 *   /portal/:slug/driver                         authed (PortalBrandProvider + PortalAuthProvider + PortalRouteGuard + PortalLayout)
 *   /portal/:slug/driver/*                       future driver pages (Phase 8e.2.1)
 *   /portal/:slug/reset-password?token=…         password-reset page (Phase 8e.2.1)
 *
 * Phase 8e.2 reconnaissance ships only the login + driver home
 * routes. Phase 8e.2.1 adds the remaining 4 driver pages + the
 * admin-invite password-set flow.
 */

import { Navigate, Route, Routes, useParams } from "react-router-dom";

import { PortalAuthProvider } from "@/contexts/portal-auth-context";
import { PortalBrandProvider } from "@/contexts/portal-brand-context";
import { PortalLayout } from "@/components/portal/PortalLayout";
import { PortalRouteGuard } from "@/components/portal/PortalRouteGuard";
import PortalLogin from "@/pages/portal/PortalLogin";
import PortalDriverHome from "@/pages/portal/PortalDriverHome";

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
          <Route path="login" element={<PortalLogin />} />
          <Route element={<PortalRouteGuard />}>
            <Route element={<PortalLayout />}>
              <Route path="driver" element={<PortalDriverHome />} />
              {/* Phase 8e.2.1 adds:
                  <Route path="driver/route" element={<PortalDriverRoute />} />
                  <Route path="driver/stops/:stopId" element={<PortalStopDetail />} />
                  <Route path="driver/mileage" element={<PortalMileage />} />
                  <Route path="driver/vehicle-inspection" element={<PortalVehicleInspection />} />
              */}
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
