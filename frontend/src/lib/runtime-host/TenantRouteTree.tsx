/**
 * Phase R-0 — TenantRouteTree.
 *
 * The tenant App's slug-set route tree, mountable from anywhere. The
 * actual route declarations + tenant page imports live in `App.tsx`
 * (the canonical source — exported as `renderTenantSlugRoutes`); this
 * module re-exports them as a self-contained `<Routes>`-wrapped
 * component so the admin tree's `/_runtime-host-test/*` route can
 * mount tenant content under PlatformUser auth + an impersonation
 * token.
 *
 * Why two files instead of one: keeping the route declarations in
 * App.tsx avoids a 1,300-line physical move (tenant operator
 * regression risk) AND lets the admin tree lazy-load this module to
 * defer the tenant chunk on admin-only sessions. Vite splits the
 * chunk at the `React.lazy(() => import("@/lib/runtime-host/TenantRouteTree"))`
 * boundary in BridgeableAdminApp, so admin pages that don't visit
 * `/_runtime-host-test/*` never pull the tenant route components.
 *
 * Public API:
 *   - default export: `<TenantRouteTree />` — renders `<Routes>` +
 *     the tenant slug-set route fragment.
 *
 * Constraints:
 *   - `<TenantProviders>` must be mounted by the caller (not here).
 *     This is intentional — tests mount providers explicitly so they
 *     can control auth state.
 *   - A `<BrowserRouter>` ancestor is required (react-router hooks
 *     need it). App.tsx provides one for the tenant boot;
 *     BridgeableAdminApp provides one at the admin tree root.
 */
import { Routes } from "react-router-dom"

import { renderTenantSlugRoutes } from "@/App"


export function TenantRouteTree() {
  return <Routes>{renderTenantSlugRoutes()}</Routes>
}


export default TenantRouteTree
