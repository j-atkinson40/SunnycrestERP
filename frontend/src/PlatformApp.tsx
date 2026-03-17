/**
 * Platform admin application — entirely separate route tree from the tenant app.
 *
 * This component is rendered when the hostname matches the admin subdomain.
 */

import { Routes, Route, Navigate } from "react-router-dom";
import { PlatformAuthProvider } from "@/contexts/platform-auth-context";
import { PlatformProtectedRoute } from "@/components/platform/platform-protected-route";
import { PlatformLayout } from "@/components/platform/platform-layout";
import PlatformLoginPage from "@/pages/platform/login";
import PlatformDashboard from "@/pages/platform/dashboard";
import TenantsPage from "@/pages/platform/tenants";
import TenantDetailPage from "@/pages/platform/tenant-detail";
import PlatformFeatureFlagsPage from "@/pages/platform/feature-flags";
import SystemHealthPage from "@/pages/platform/system-health";
import ImpersonationLogPage from "@/pages/platform/impersonation-log";
import PlatformUsersPage from "@/pages/platform/platform-users";
import TenantOnboardingPage from "@/pages/platform/tenant-onboarding";
import TenantModulesPage from "@/pages/platform/tenant-modules";
import ExtensionDemandPage from "@/pages/platform/extension-demand";

export default function PlatformApp() {
  return (
    <PlatformAuthProvider>
      <Routes>
        <Route path="/login" element={<PlatformLoginPage />} />

        {/* Protected platform routes */}
        <Route element={<PlatformProtectedRoute />}>
          <Route element={<PlatformLayout />}>
            <Route path="/dashboard" element={<PlatformDashboard />} />
            <Route path="/tenants" element={<TenantsPage />} />
            <Route
              path="/tenants/new"
              element={<TenantOnboardingPage />}
            />
            <Route
              path="/tenants/:tenantId"
              element={<TenantDetailPage />}
            />
            <Route
              path="/tenants/:tenantId/modules"
              element={<TenantModulesPage />}
            />
            <Route
              path="/extensions/demand"
              element={<ExtensionDemandPage />}
            />
            <Route
              path="/feature-flags"
              element={<PlatformFeatureFlagsPage />}
            />
            <Route path="/system" element={<SystemHealthPage />} />
            <Route
              path="/impersonation"
              element={<ImpersonationLogPage />}
            />
            <Route path="/users" element={<PlatformUsersPage />} />
          </Route>
        </Route>

        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </PlatformAuthProvider>
  );
}
