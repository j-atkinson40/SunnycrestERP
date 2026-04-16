import { Routes, Route } from "react-router-dom"
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

export function BridgeableAdminApp() {
  return (
    <AdminAuthProvider>
      <Routes>
        <Route path="/bridgeable-admin/login" element={<AdminLogin />} />
        <Route
          path="/bridgeable-admin/*"
          element={
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
          }
        />
      </Routes>
    </AdminAuthProvider>
  )
}

export function isBridgeableAdminPath(): boolean {
  return window.location.pathname.startsWith("/bridgeable-admin")
}
