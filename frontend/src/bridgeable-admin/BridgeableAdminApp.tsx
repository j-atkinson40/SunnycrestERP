import { Routes, Route, Navigate } from "react-router-dom"
import { AdminAuthProvider } from "./lib/admin-auth-context"
import { AdminLayout } from "./components/AdminLayout"
import { AdminLogin } from "./pages/AdminLogin"
import { HealthDashboard } from "./pages/HealthDashboard"
import { TenantKanban } from "./pages/TenantKanban"
import { AuditRunner } from "./pages/AuditRunner"
import { MigrationsPanel } from "./pages/MigrationsPanel"
import { FeatureFlagsPage } from "./pages/FeatureFlagsPage"
import { DeploymentsPage } from "./pages/DeploymentsPage"
import { StagingCreatePage } from "./pages/StagingPage"

/**
 * Accessed via either:
 *   - /bridgeable-admin/* path on any host
 *   - admin.* subdomain (no /bridgeable-admin prefix in URL)
 *
 * Both entry points are supported simultaneously — the Routes below
 * are duplicated with and without the prefix.
 */
export function BridgeableAdminApp() {
  const pages = (
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
      </Routes>
    </AdminLayout>
  )

  return (
    <AdminAuthProvider>
      <Routes>
        {/* Path-based entry: /bridgeable-admin/* */}
        <Route path="/bridgeable-admin/login" element={<AdminLogin />} />
        <Route path="/bridgeable-admin/*" element={pages} />

        {/* Subdomain entry: admin.* — routes at root */}
        <Route path="/login" element={<AdminLogin />} />
        <Route path="/*" element={pages} />

        {/* Catch-all redirect to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AdminAuthProvider>
  )
}

export function isBridgeableAdminPath(): boolean {
  return window.location.pathname.startsWith("/bridgeable-admin")
}
