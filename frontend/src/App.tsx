import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/auth-context";
import { ProtectedRoute } from "@/components/protected-route";
import { RootRedirect } from "@/components/root-redirect";
import { AppLayout } from "@/components/layout/app-layout";
import { Toaster } from "@/components/ui/sonner";
import { getCompanySlug } from "@/lib/tenant";
import LoginPage from "@/pages/login";
import RegisterPage from "@/pages/register";
import Dashboard from "@/pages/dashboard/employee-dashboard";
import UserManagement from "@/pages/admin/user-management";
import RoleManagement from "@/pages/admin/role-management";
import AuditLogs from "@/pages/admin/audit-logs";
import CompanySettings from "@/pages/admin/company-settings";
import MyProfile from "@/pages/my-profile";
import AdminEmployeeProfile from "@/pages/admin/employee-profile";
import NotificationsPage from "@/pages/notifications";
import ProductsPage from "@/pages/products";
import ProductDetailPage from "@/pages/product-detail";
import InventoryPage from "@/pages/inventory";
import InventoryDetailPage from "@/pages/inventory-detail";
import ProductionEntryPage from "@/pages/production-entry";
import WriteOffsPage from "@/pages/write-offs";
import SageExportsPage from "@/pages/sage-exports";
import CustomersPage from "@/pages/customers";
import CustomerDetailPage from "@/pages/customer-detail";
import Unauthorized from "@/pages/unauthorized";
import NotFound from "@/pages/not-found";
import LandingPage from "@/pages/landing";
import CompanyRegisterPage from "@/pages/company-register";

export default function App() {
  const slug = getCompanySlug();

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {slug ? (
            <>
              {/* Tenant routes — accessed via subdomain or company slug */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/unauthorized" element={<Unauthorized />} />

              {/* Protected routes */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  {/* Dashboard — all authenticated users */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="dashboard.view" />
                    }
                  >
                    <Route path="/dashboard" element={<Dashboard />} />
                  </Route>

                  {/* User management — requires users.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="users.view" />
                    }
                  >
                    <Route
                      path="/admin/users"
                      element={<UserManagement />}
                    />
                  </Route>

                  {/* Role management — requires roles.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="roles.view" />
                    }
                  >
                    <Route
                      path="/admin/roles"
                      element={<RoleManagement />}
                    />
                  </Route>

                  {/* Products — requires products module + products.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="products.view" requiredModule="products" />
                    }
                  >
                    <Route
                      path="/products"
                      element={<ProductsPage />}
                    />
                    <Route
                      path="/products/:productId"
                      element={<ProductDetailPage />}
                    />
                  </Route>

                  {/* Customers — requires sales module + customers.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="customers.view" requiredModule="sales" />
                    }
                  >
                    <Route
                      path="/customers"
                      element={<CustomersPage />}
                    />
                    <Route
                      path="/customers/:customerId"
                      element={<CustomerDetailPage />}
                    />
                  </Route>

                  {/* Inventory — requires inventory module + inventory.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="inventory.view" requiredModule="inventory" />
                    }
                  >
                    <Route
                      path="/inventory"
                      element={<InventoryPage />}
                    />
                    <Route
                      path="/inventory/production"
                      element={<ProductionEntryPage />}
                    />
                    <Route
                      path="/inventory/write-offs"
                      element={<WriteOffsPage />}
                    />
                    <Route
                      path="/inventory/sage-exports"
                      element={<SageExportsPage />}
                    />
                    <Route
                      path="/inventory/:productId"
                      element={<InventoryDetailPage />}
                    />
                  </Route>

                  {/* Notifications — any authenticated user */}
                  <Route
                    path="/notifications"
                    element={<NotificationsPage />}
                  />

                  {/* My Profile — any authenticated user */}
                  <Route path="/profile" element={<MyProfile />} />

                  {/* Admin employee profile — requires employees.view */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="employees.view" />
                    }
                  >
                    <Route
                      path="/admin/users/:userId/profile"
                      element={<AdminEmployeeProfile />}
                    />
                  </Route>

                  {/* Company settings — requires company.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="company.view" />
                    }
                  >
                    <Route
                      path="/admin/settings"
                      element={<CompanySettings />}
                    />
                  </Route>

                  {/* Audit logs — requires audit.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="audit.view" />
                    }
                  >
                    <Route
                      path="/admin/audit-logs"
                      element={<AuditLogs />}
                    />
                  </Route>
                </Route>
              </Route>

              {/* Root redirect */}
              <Route path="/" element={<RootRedirect />} />
              <Route path="*" element={<NotFound />} />
            </>
          ) : (
            <>
              {/* Root domain routes — landing page + company registration */}
              <Route path="/" element={<LandingPage />} />
              <Route
                path="/register-company"
                element={<CompanyRegisterPage />}
              />
              <Route path="*" element={<NotFound />} />
            </>
          )}
        </Routes>
        <Toaster />
      </AuthProvider>
    </BrowserRouter>
  );
}
