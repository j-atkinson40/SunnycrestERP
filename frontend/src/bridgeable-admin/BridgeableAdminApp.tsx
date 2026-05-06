import { lazy, Suspense } from "react"
import { Routes, Route, Navigate } from "react-router-dom"
import { AdminAuthProvider } from "./lib/admin-auth-context"
import { AdminLayout } from "./components/AdminLayout"
import { VisualEditorLayout } from "./components/VisualEditorLayout"

// Phase R-0 — runtime-host-test page is lazy-loaded so the tenant
// route tree chunk only ships when an admin actually visits the
// runtime host. Vite splits at the dynamic-import boundary; admin
// pages that don't visit /_runtime-host-test/* never pull the
// tenant chunk into their bundle.
const RuntimeHostTestPage = lazy(
  () => import("./pages/RuntimeHostTestPage"),
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

  return (
    <AdminAuthProvider>
      <Routes>
        {/* Login is unauthenticated — handled before either layout. */}
        <Route path="/bridgeable-admin/login" element={<AdminLogin />} />
        <Route path="/login" element={<AdminLogin />} />

        {/* Phase R-0 runtime-host-test surface — lazy-loaded; super_admin
            gate enforced inside the page. Path-based + subdomain-based
            entry parallel to visual editor's pattern. */}
        <Route
          path="/bridgeable-admin/_runtime-host-test/*"
          element={runtimeHostRoute}
        />
        <Route
          path="/_runtime-host-test/*"
          element={runtimeHostRoute}
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
