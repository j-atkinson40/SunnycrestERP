import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/auth-context";
import { FeatureFlagProvider } from "@/contexts/feature-flag-context";
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
import AccountingPage from "@/pages/admin/accounting";
import ApiKeysPage from "@/pages/admin/api-keys";
import FeatureFlagsPage from "@/pages/admin/feature-flags";
import SyncDashboardPage from "@/pages/admin/sync-dashboard";
import OrgHierarchyPage from "@/pages/admin/org-hierarchy";
import NetworkManagementPage from "@/pages/admin/network-management";
import PlatformFeesPage from "@/pages/admin/platform-fees";
import BillingPage from "@/pages/admin/billing";
import SuperDashboardPage2 from "@/pages/admin/super-dashboard";
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
import VendorsPage from "@/pages/vendors";
import VendorDetailPage from "@/pages/vendor-detail";
import PurchaseOrdersPage from "@/pages/purchase-orders";
import PurchaseOrderDetailPage from "@/pages/purchase-order-detail";
import VendorBillsPage from "@/pages/vendor-bills";
import VendorBillDetailPage from "@/pages/vendor-bill-detail";
import VendorPaymentsPage from "@/pages/vendor-payments";
import VendorPaymentDetailPage from "@/pages/vendor-payment-detail";
import APAgingPage from "@/pages/ap-aging";
import QuotesPage from "@/pages/quotes";
import QuoteDetailPage from "@/pages/quote-detail";
import SalesOrdersPage from "@/pages/sales-orders";
import SalesOrderDetailPage from "@/pages/sales-order-detail";
import InvoicesPage from "@/pages/invoices";
import InvoiceDetailPage from "@/pages/invoice-detail";
import CustomerPaymentsPage from "@/pages/customer-payments";
import ARAgingPage2 from "@/pages/ar-aging";
import ModulesPage from "@/pages/admin/modules";
import DeliverySettingsPage from "@/pages/admin/delivery-settings";
import DispatchPage from "@/pages/delivery/dispatch";
import OperationsPage from "@/pages/delivery/operations";
import HistoryPage from "@/pages/delivery/history";
import DeliveryDetailPage from "@/pages/delivery/delivery-detail";
import RouteDetailPage from "@/pages/delivery/route-detail";
import CarriersPage from "@/pages/delivery/carriers";
import { DriverLayout } from "@/components/layout/driver-layout";
import DriverHomePage from "@/pages/driver/home";
import DriverRoutePage from "@/pages/driver/route";
import StopDetailPage from "@/pages/driver/stop-detail";
import MileagePage from "@/pages/driver/mileage";
import CarrierDeliveriesPage from "@/pages/carrier/deliveries";
import Unauthorized from "@/pages/unauthorized";
import NotFound from "@/pages/not-found";
import LandingPage from "@/pages/landing";
import CompanyRegisterPage from "@/pages/company-register";

export default function App() {
  const slug = getCompanySlug();

  return (
    <BrowserRouter>
      <AuthProvider>
      <FeatureFlagProvider>
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

                  {/* Sales / AR — requires sales module + ar.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="ar.view" requiredModule="sales" />
                    }
                  >
                    <Route
                      path="/ar/quotes"
                      element={<QuotesPage />}
                    />
                    <Route
                      path="/ar/quotes/:id"
                      element={<QuoteDetailPage />}
                    />
                    <Route
                      path="/ar/orders"
                      element={<SalesOrdersPage />}
                    />
                    <Route
                      path="/ar/orders/:id"
                      element={<SalesOrderDetailPage />}
                    />
                    <Route
                      path="/ar/invoices"
                      element={<InvoicesPage />}
                    />
                    <Route
                      path="/ar/invoices/:id"
                      element={<InvoiceDetailPage />}
                    />
                    <Route
                      path="/ar/payments"
                      element={<CustomerPaymentsPage />}
                    />
                    <Route
                      path="/ar/aging"
                      element={<ARAgingPage2 />}
                    />
                  </Route>

                  {/* Vendors — requires purchasing module + vendors.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="vendors.view" requiredModule="purchasing" />
                    }
                  >
                    <Route
                      path="/vendors"
                      element={<VendorsPage />}
                    />
                    <Route
                      path="/vendors/:vendorId"
                      element={<VendorDetailPage />}
                    />
                  </Route>

                  {/* AP / Purchasing — requires purchasing module + ap.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="ap.view" requiredModule="purchasing" />
                    }
                  >
                    <Route
                      path="/ap/purchase-orders"
                      element={<PurchaseOrdersPage />}
                    />
                    <Route
                      path="/ap/purchase-orders/:id"
                      element={<PurchaseOrderDetailPage />}
                    />
                    <Route
                      path="/ap/bills"
                      element={<VendorBillsPage />}
                    />
                    <Route
                      path="/ap/bills/:id"
                      element={<VendorBillDetailPage />}
                    />
                    <Route
                      path="/ap/payments"
                      element={<VendorPaymentsPage />}
                    />
                    <Route
                      path="/ap/payments/:id"
                      element={<VendorPaymentDetailPage />}
                    />
                    <Route
                      path="/ap/aging"
                      element={<APAgingPage />}
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

                  {/* Delivery & Logistics — requires driver_delivery module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="delivery.view" requiredModule="driver_delivery" />
                    }
                  >
                    <Route path="/delivery/dispatch" element={<DispatchPage />} />
                    <Route path="/delivery/operations" element={<OperationsPage />} />
                    <Route path="/delivery/history" element={<HistoryPage />} />
                    <Route path="/delivery/deliveries/:id" element={<DeliveryDetailPage />} />
                    <Route path="/delivery/routes/:id" element={<RouteDetailPage />} />
                    <Route path="/delivery/settings" element={<DeliverySettingsPage />} />
                  </Route>
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="carriers.view" requiredModule="driver_delivery" />
                    }
                  >
                    <Route path="/delivery/carriers" element={<CarriersPage />} />
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

                  {/* Feature flags — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/feature-flags"
                      element={<FeatureFlagsPage />}
                    />
                  </Route>

                  {/* API keys — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/api-keys"
                      element={<ApiKeysPage />}
                    />
                  </Route>

                  {/* Accounting integration — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/accounting"
                      element={<AccountingPage />}
                    />
                  </Route>

                  {/* Sync monitoring — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/sync-dashboard"
                      element={<SyncDashboardPage />}
                    />
                  </Route>

                  {/* Org Hierarchy — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/hierarchy"
                      element={<OrgHierarchyPage />}
                    />
                  </Route>

                  {/* Partner Network — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/network"
                      element={<NetworkManagementPage />}
                    />
                  </Route>

                  {/* Platform Fees — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/platform-fees"
                      element={<PlatformFeesPage />}
                    />
                  </Route>

                  {/* Billing — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/billing"
                      element={<BillingPage />}
                    />
                  </Route>

                  {/* Modules — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/modules"
                      element={<ModulesPage />}
                    />
                  </Route>

                  {/* Super Dashboard — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/super-dashboard"
                      element={<SuperDashboardPage2 />}
                    />
                  </Route>
                </Route>
              </Route>

              {/* Driver mobile — uses DriverLayout (no sidebar) */}
              <Route element={<ProtectedRoute />}>
                <Route element={<DriverLayout />}>
                  <Route path="/driver" element={<DriverHomePage />} />
                  <Route path="/driver/route" element={<DriverRoutePage />} />
                  <Route path="/driver/stops/:stopId" element={<StopDetailPage />} />
                  <Route path="/driver/mileage" element={<MileagePage />} />
                </Route>
              </Route>

              {/* Carrier portal — authenticated, minimal UI */}
              <Route element={<ProtectedRoute />}>
                <Route path="/carrier/deliveries" element={<CarrierDeliveriesPage />} />
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
      </FeatureFlagProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
