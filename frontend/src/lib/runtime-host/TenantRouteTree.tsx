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


/**
 * R-1.6.9: Pass `excludeRootRedirect: true` so the inner Routes mount
 * `<HomePage />` at `/` instead of `<RootRedirect />`. Pre-R-1.6.9, the
 * runtime editor mounted at `/runtime-editor/?tenant=...&user=...` would
 * see the inner Routes match its splat-empty path against `<Route path="/"
 * element={<RootRedirect />} />`, and RootRedirect's
 * `<Navigate to="/home" replace />` would absolute-navigate the URL out
 * of the `/runtime-editor/*` parent route — bouncing the user to
 * `admin.<domain>/home` (empty Bridgeable Admin chrome). With
 * excludeRootRedirect, HomePage renders inline inside the shell and the
 * URL stays put. See /tmp/picker_navigation_bug.md.
 */
export function TenantRouteTree() {
  return (
    <Routes>{renderTenantSlugRoutes({ excludeRootRedirect: true })}</Routes>
  )
}


export default TenantRouteTree
