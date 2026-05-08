import { lazy, Suspense } from "react"
import { Routes, Route, Navigate } from "react-router-dom"
import { AdminAuthProvider } from "./lib/admin-auth-context"
import { AdminLayout } from "./components/AdminLayout"
import { VisualEditorLayout } from "./components/VisualEditorLayout"

// Phase R-0 + R-1 — runtime editor pages are lazy-loaded so the
// tenant route tree chunk only ships when an admin actually visits
// the editor. Vite splits at the dynamic-import boundary; admin
// pages that don't visit the runtime editor never pull the tenant
// chunk into their bundle.
//
// R-0 path `/_runtime-host-test/*` is preserved as an alias for the
// R-1 RuntimeEditorShell — existing test references continue to
// resolve. The canonical path going forward is `/runtime-editor/*`.
//
// R-1.6.1 (picker-route-conflict fix): TenantUserPicker is rendered
// as a CHILD of RuntimeEditorShell when impersonation params are
// missing — NOT as a sibling route. Two reasons:
//   1. React Router v7 score-ranks routes; an exact path beats a
//      splat path. With both `/runtime-editor` (picker) and
//      `/runtime-editor/*` (shell) registered, the picker silently
//      won the navigate-from-picker-to-shell handoff because the
//      target URL `/runtime-editor/?tenant=...` resolves to the
//      same exact-path route after trailing-slash normalization.
//   2. Structurally, the shell IS the editor surface. A "missing
//      params" state is a render of the picker, not a different
//      route. Collapsing fixes the conflict + simplifies the URL
//      contract (picker and shell share `/runtime-editor/*`).
// Bug history + fix rationale: see
// /tmp/picker_navigation_bug.md (R-1.6.1 investigation report).
const RuntimeHostTestPage = lazy(
  () => import("./pages/RuntimeHostTestPage"),
)
const RuntimeEditorShell = lazy(
  () => import("./pages/runtime-editor/RuntimeEditorShell"),
)
import { AdminLogin } from "./pages/AdminLogin"
import { HealthDashboard } from "./pages/HealthDashboard"
import { TenantKanban } from "./pages/TenantKanban"
import { AuditRunner } from "./pages/AuditRunner"
import { MigrationsPanel } from "./pages/MigrationsPanel"
import { FeatureFlagsPage } from "./pages/FeatureFlagsPage"
import { DeploymentsPage } from "./pages/DeploymentsPage"
import { StagingCreatePage } from "./pages/StagingPage"
import { ArcTelemetry } from "./pages/ArcTelemetry"
import VisualEditorIndex from "./pages/visual-editor/VisualEditorIndex"
import RegistryDebugPage from "./pages/visual-editor/RegistryDebugPage"
import ThemeEditorPage from "./pages/visual-editor/themes/ThemeEditorPage"
import WorkflowEditorPage from "./pages/visual-editor/WorkflowEditorPage"
import ClassEditorPage from "./pages/visual-editor/ClassEditorPage"
import FocusEditorPage from "./pages/visual-editor/FocusEditorPage"
import WidgetEditorPage from "./pages/visual-editor/WidgetEditorPage"
import DocumentsEditorPage from "./pages/visual-editor/DocumentsEditorPage"
import EdgePanelEditorPage from "./pages/visual-editor/EdgePanelEditorPage"

/**
 * Accessed via either:
 *   - /bridgeable-admin/* path on any host
 *   - admin.* subdomain (no /bridgeable-admin prefix in URL)
 *
 * Both entry points are supported simultaneously — the Routes below
 * are duplicated with and without the prefix.
 *
 * Two coexisting layouts:
 *   - AdminLayout (slate chrome) wraps operational admin pages
 *     (Health, Tenants, Audit, Migrations, etc.)
 *   - VisualEditorLayout (warm tokens) wraps the four visual editor
 *     pages (themes, components, workflows, registry) plus the
 *     visual editor landing page.
 */
export function BridgeableAdminApp() {
  const operationalPages = (
    <AdminLayout>
      <Routes>
        <Route path="/" element={<HealthDashboard />} />
        <Route path="/tenants" element={<TenantKanban />} />
        <Route path="/tenants/:id" element={<TenantKanban />} />
        <Route path="/audit" element={<AuditRunner />} />
        <Route path="/migrations" element={<MigrationsPanel />} />
        <Route path="/feature-flags" element={<FeatureFlagsPage />} />
        <Route path="/deployments" element={<DeploymentsPage />} />
        <Route path="/staging/create" element={<StagingCreatePage />} />
        <Route path="/staging" element={<StagingCreatePage />} />
        {/* Phase 7 — arc telemetry (minimal process-scoped counters) */}
        <Route path="/telemetry" element={<ArcTelemetry />} />
      </Routes>
    </AdminLayout>
  )

  const visualEditorPages = (
    <VisualEditorLayout>
      <Routes>
        <Route index element={<VisualEditorIndex />} />
        <Route path="themes" element={<ThemeEditorPage />} />
        {/* New top-level editors (May 2026 reorganization). */}
        <Route path="focuses" element={<FocusEditorPage />} />
        <Route path="widgets" element={<WidgetEditorPage />} />
        <Route path="documents" element={<DocumentsEditorPage />} />
        <Route path="classes" element={<ClassEditorPage />} />
        <Route path="workflows" element={<WorkflowEditorPage />} />
        {/* R-5.0 — edge panel multi-page authoring. */}
        <Route path="edge-panels" element={<EdgePanelEditorPage />} />
        <Route path="registry" element={<RegistryDebugPage />} />
        {/* Legacy redirects — May 2026 reorganization dismantled the
            standalone Component Editor + Compositions page. Their
            functionality is redistributed across Widget Editor + Focus
            Editor. Existing bookmarks land on the editor index where
            the new structure is discoverable. */}
        <Route path="components" element={<Navigate to="../" replace />} />
        <Route path="compositions" element={<Navigate to="../focuses" replace />} />
      </Routes>
    </VisualEditorLayout>
  )

  // Phase R-0 — Runtime Host Test routes (super_admin gated, hidden
  // from VisualEditorIndex). Mount before any layouts so the route
  // bypasses both AdminLayout and VisualEditorLayout — RuntimeHostTestPage
  // owns its own chrome (the warning ribbon at top + the tenant
  // content beneath). Lazy-loaded; loading state renders the
  // <Suspense> fallback.
  const runtimeHostRoute = (
    <Suspense
      fallback={
        <div
          className="flex h-screen items-center justify-center bg-surface-base text-content-muted"
          data-testid="runtime-host-test-suspense"
        >
          <span>Loading runtime host…</span>
        </div>
      }
    >
      <RuntimeHostTestPage />
    </Suspense>
  )

  // Phase R-1 — Runtime Editor (canonical path). The shell handles
  // both entry states: when impersonation params are absent, the
  // shell renders the picker as a child (R-1.6.1 Fix 2 — collapse
  // exact + splat routes to splat-only, eliminating the route
  // specificity conflict that silently bounced picker→shell
  // navigations back to the picker route). Lazy-loaded; bypasses
  // admin/visual-editor layouts. Auth gate (platform_admin/support/
  // super_admin) enforced inside RuntimeEditorShell + impersonation
  // API.
  const runtimeEditorShellRoute = (
    <Suspense
      fallback={
        <div
          className="flex h-screen items-center justify-center bg-surface-base text-content-muted"
          data-testid="runtime-editor-shell-suspense"
        >
          <span>Loading runtime editor…</span>
        </div>
      }
    >
      <RuntimeEditorShell />
    </Suspense>
  )

  return (
    <AdminAuthProvider>
      <Routes>
        {/* Login is unauthenticated — handled before either layout. */}
        <Route path="/bridgeable-admin/login" element={<AdminLogin />} />
        <Route path="/login" element={<AdminLogin />} />

        {/* Phase R-0 runtime-host-test surface — lazy-loaded; super_admin
            gate enforced inside the page. Path-based + subdomain-based
            entry parallel to visual editor's pattern. Preserved as
            R-1 alias so existing test references resolve. */}
        <Route
          path="/bridgeable-admin/_runtime-host-test/*"
          element={runtimeHostRoute}
        />
        <Route
          path="/_runtime-host-test/*"
          element={runtimeHostRoute}
        />

        {/* Phase R-1 — canonical runtime editor entry. R-1.6.1 fix:
            collapse to splat-only routes. RuntimeEditorShell renders
            the picker as a child component when tenant/user params
            are absent. Single route handles both states; React
            Router has no specificity conflict. */}
        <Route
          path="/bridgeable-admin/runtime-editor/*"
          element={runtimeEditorShellRoute}
        />
        <Route
          path="/runtime-editor/*"
          element={runtimeEditorShellRoute}
        />

        {/* Path-based entry: /bridgeable-admin/visual-editor/* — visual editor */}
        <Route
          path="/bridgeable-admin/visual-editor/*"
          element={visualEditorPages}
        />
        {/* Subdomain entry: /visual-editor/* — visual editor */}
        <Route path="/visual-editor/*" element={visualEditorPages} />

        {/* Path-based entry: /bridgeable-admin/* — operational admin */}
        <Route path="/bridgeable-admin/*" element={operationalPages} />
        {/* Subdomain entry: admin.* — routes at root — operational admin */}
        <Route path="/*" element={operationalPages} />

        {/* Catch-all redirect to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AdminAuthProvider>
  )
}

export function isBridgeableAdminPath(): boolean {
  return window.location.pathname.startsWith("/bridgeable-admin")
}
