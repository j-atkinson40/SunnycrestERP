import { Routes, Route, Navigate } from "react-router-dom"
import { AdminAuthProvider } from "./lib/admin-auth-context"
import { AdminLayout } from "./components/AdminLayout"
import { VisualEditorLayout } from "./components/VisualEditorLayout"
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
import ComponentEditorPage from "./pages/visual-editor/ComponentEditorPage"
import WorkflowEditorPage from "./pages/visual-editor/WorkflowEditorPage"

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
        <Route path="components" element={<ComponentEditorPage />} />
        <Route path="workflows" element={<WorkflowEditorPage />} />
        <Route path="registry" element={<RegistryDebugPage />} />
      </Routes>
    </VisualEditorLayout>
  )

  return (
    <AdminAuthProvider>
      <Routes>
        {/* Login is unauthenticated — handled before either layout. */}
        <Route path="/bridgeable-admin/login" element={<AdminLogin />} />
        <Route path="/login" element={<AdminLogin />} />

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
