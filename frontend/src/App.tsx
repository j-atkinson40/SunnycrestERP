import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/auth-context";
import { ExtensionProvider } from "@/contexts/extension-context";
import { FeatureFlagProvider } from "@/contexts/feature-flag-context";
import { PresetThemeProvider } from "@/contexts/preset-theme-context";
import { ProtectedRoute } from "@/components/protected-route";
import { RootRedirect } from "@/components/root-redirect";
import { AppLayout } from "@/components/layout/app-layout";
import { Toaster } from "@/components/ui/sonner";
import { ImpersonationBanner } from "@/components/platform/impersonation-banner";
import { getCompanySlug } from "@/lib/tenant";
import { isPlatformAdmin } from "@/lib/platform";
import PlatformApp from "@/PlatformApp";
import LoginPage from "@/pages/login";
import RegisterPage from "@/pages/register";
import Dashboard from "@/pages/dashboard/employee-dashboard";
import UserManagement from "@/pages/admin/user-management";
import RoleManagement from "@/pages/admin/role-management";
import AuditLogs from "@/pages/admin/audit-logs";
import CompanySettings from "@/pages/admin/company-settings";
import AccountingPage from "@/pages/admin/accounting";
import ApiKeysPage from "@/pages/admin/api-keys";
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
import FuneralSchedulingPage from "@/pages/delivery/funeral-scheduling";
import BOMListPage from "@/pages/bom/bom-list";
import BOMDetailPage from "@/pages/bom/bom-detail";
import ProjectListPage from "@/pages/projects/project-list";
import ProjectDetailPage from "@/pages/projects/project-detail";
import QCMobilePage from "@/pages/qc/qc-mobile";
import QCDashboardPage from "@/pages/qc/qc-dashboard";
import QCInspectionDetailPage from "@/pages/qc/qc-inspection-detail";
import SafetyDashboardPage from "@/pages/safety/safety-dashboard";
import SafetyInspectPage from "@/pages/safety/safety-inspect";
import SafetyIncidentPage from "@/pages/safety/safety-incidents";
import SafetyChemicalsPage from "@/pages/safety/safety-chemicals";
import SafetyLOTOPage from "@/pages/safety/safety-loto";
import SafetyProgramsPage from "@/pages/safety/safety-programs";
import SafetyTrainingPage from "@/pages/safety/safety-training";
import SafetyOSHA300Page from "@/pages/safety/safety-osha300";
import ProductionBoardPage from "@/pages/production/production-board";
import PourEventCreatePage from "@/pages/production/pour-event-create";
import WorkOrderDetailPage from "@/pages/production/work-order-detail";
import { DriverLayout } from "@/components/layout/driver-layout";
import DriverHomePage from "@/pages/driver/home";
import DriverRoutePage from "@/pages/driver/route";
import StopDetailPage from "@/pages/driver/stop-detail";
import MileagePage from "@/pages/driver/mileage";
import CarrierDeliveriesPage from "@/pages/carrier/deliveries";
import ExtensionCatalogPage from "@/pages/extensions/extension-catalog";
import ExtensionInstalledPage from "@/pages/extensions/extension-installed";
import FHCaseListPage from "@/pages/funeral-home/case-list";
import FHFirstCallPage from "@/pages/funeral-home/first-call";
import FHCaseDetailPage from "@/pages/funeral-home/case-detail";
import FHDashboardPage from "@/pages/funeral-home/dashboard";
import FHCompliancePage from "@/pages/funeral-home/ftc-compliance";
import FHPriceListPage from "@/pages/funeral-home/price-list";
import FHPortalPage from "@/pages/funeral-home/portal";
import ProductionLog from "@/pages/production-log/production-log";
import ProductionLogSummary from "@/pages/production-log/production-log-summary";
import MobileProductionLog from "@/pages/production-log/mobile-production-log";
import SpringBurialList from "@/pages/spring-burials/spring-burial-list";
import OrderStation from "@/pages/orders/order-station";
import OnboardingHub from "@/pages/onboarding/onboarding-hub";
import IntegrationSetupPage from "@/pages/onboarding/integration-setup";
import OnboardingAnalyticsPage from "@/pages/onboarding/onboarding-analytics";
import ProductLibraryPage from "@/pages/onboarding/product-library";
import ImportWizardPage from "@/pages/onboarding/import-wizard";
import ScenarioPlayerPage from "@/pages/onboarding/scenario-player";
import CatalogBuilder from "@/pages/onboarding/catalog-builder";
import WebsiteSuggestionsReview from "@/pages/onboarding/website-suggestions-review";
import UrnCatalogPage from "@/pages/products/urn-catalog";
import UrnImportWizard from "@/pages/products/urn-import-wizard";
import Unauthorized from "@/pages/unauthorized";
import NotFound from "@/pages/not-found";
import LandingPage from "@/pages/landing";
import CompanyRegisterPage from "@/pages/company-register";
import PlatformAdminEntry from "@/pages/platform-admin-entry";

export default function App() {
  // Platform admin gets an entirely separate app
  if (isPlatformAdmin()) {
    return (
      <BrowserRouter>
        <PlatformApp />
        <Toaster />
      </BrowserRouter>
    );
  }

  const slug = getCompanySlug();

  return (
    <BrowserRouter>
      <AuthProvider>
      <FeatureFlagProvider>
      <ExtensionProvider>
        <ImpersonationBanner />
        <Routes>
          {slug ? (
            <>
              {/* Tenant routes — accessed via subdomain or company slug */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/unauthorized" element={<Unauthorized />} />

              {/* Protected routes */}
              <Route element={<ProtectedRoute />}>
                <Route element={<PresetThemeProvider><AppLayout /></PresetThemeProvider>}>
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
                    <Route
                      path="/products/urns"
                      element={<UrnCatalogPage />}
                    />
                    <Route
                      path="/products/urns/import"
                      element={<UrnImportWizard />}
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

                  {/* Order Station — requires sales module + ar.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="ar.view" requiredModule="sales" />
                    }
                  >
                    <Route path="/order-station" element={<OrderStation />} />
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

                  {/* Bill of Materials — requires inventory module + inventory.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="inventory.view" requiredModule="inventory" />
                    }
                  >
                    <Route path="/bom" element={<BOMListPage />} />
                    <Route path="/bom/:bomId" element={<BOMDetailPage />} />
                  </Route>

                  {/* Project Management — requires project_management module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="projects.view" requiredModule="project_management" />
                    }
                  >
                    <Route path="/projects" element={<ProjectListPage />} />
                    <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
                  </Route>

                  {/* Quality Control — requires inventory module + qc.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="qc.view" requiredModule="inventory" />
                    }
                  >
                    <Route path="/qc" element={<QCDashboardPage />} />
                    <Route path="/qc/inspections/:inspectionId" element={<QCInspectionDetailPage />} />
                    <Route path="/qc/mobile/:inspectionId" element={<QCMobilePage />} />
                  </Route>

                  {/* Safety Management — requires safety_management module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="safety.view" requiredModule="safety_management" />
                    }
                  >
                    <Route path="/safety" element={<SafetyDashboardPage />} />
                    <Route path="/safety/programs" element={<SafetyProgramsPage />} />
                    <Route path="/safety/training" element={<SafetyTrainingPage />} />
                    <Route path="/safety/inspections/new" element={<SafetyInspectPage />} />
                    <Route path="/safety/inspect/:inspectionId" element={<SafetyInspectPage />} />
                    <Route path="/safety/incidents" element={<SafetyIncidentPage />} />
                    <Route path="/safety/incidents/new" element={<SafetyIncidentPage />} />
                    <Route path="/safety/chemicals" element={<SafetyChemicalsPage />} />
                    <Route path="/safety/loto" element={<SafetyLOTOPage />} />
                    <Route path="/safety/osha-300" element={<SafetyOSHA300Page />} />
                  </Route>

                  {/* Production Log — requires daily_production_log module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="production_log.view" requiredModule="daily_production_log" />
                    }
                  >
                    <Route path="/production-log" element={<ProductionLog />} />
                    <Route path="/production-log/summary" element={<ProductionLogSummary />} />
                    <Route path="/spring-burials" element={<SpringBurialList />} />
                  </Route>

                  {/* Work Orders & Production — requires work_orders module */}
                  <Route element={<ProtectedRoute requiredPermission="work_orders.view" requiredModule="work_orders" />}>
                    <Route path="/production" element={<ProductionBoardPage />} />
                    <Route path="/production/pour-events/new" element={<PourEventCreatePage />} />
                    <Route path="/work-orders/:id" element={<WorkOrderDetailPage />} />
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
                    <Route path="/delivery/funeral-scheduling" element={<FuneralSchedulingPage />} />
                  </Route>
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="carriers.view" requiredModule="driver_delivery" />
                    }
                  >
                    <Route path="/delivery/carriers" element={<CarriersPage />} />
                  </Route>

                  {/* Funeral Home — requires funeral_home module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="fh_cases.view" requiredModule="funeral_home" />
                    }
                  >
                    <Route path="/cases" element={<FHCaseListPage />} />
                    <Route path="/cases/new" element={<FHFirstCallPage />} />
                    <Route path="/cases/:id" element={<FHCaseDetailPage />} />
                    <Route path="/funeral-home/dashboard" element={<FHDashboardPage />} />
                    <Route path="/funeral-home/compliance" element={<FHCompliancePage />} />
                    <Route path="/funeral-home/price-list" element={<FHPriceListPage />} />
                  </Route>

                  {/* Onboarding — any authenticated user */}
                  <Route path="/onboarding" element={<OnboardingHub />} />
                  <Route path="/onboarding/integrations/:type" element={<IntegrationSetupPage />} />
                  <Route path="/onboarding/product-library" element={<ProductLibraryPage />} />
                  <Route path="/onboarding/import/:type" element={<ImportWizardPage />} />
                  <Route path="/onboarding/scenarios/:scenarioKey" element={<ScenarioPlayerPage />} />
                  <Route path="/onboarding/website-review" element={<WebsiteSuggestionsReview />} />
                  <Route path="/onboarding/catalog-builder" element={<CatalogBuilder />} />

                  {/* Extension Catalog — any authenticated user */}
                  <Route path="/extensions" element={<ExtensionCatalogPage />} />
                  <Route path="/extensions/installed" element={<ExtensionInstalledPage />} />

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

                  {/* Modules — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/modules"
                      element={<ModulesPage />}
                    />
                  </Route>

                  {/* Onboarding analytics — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route
                      path="/admin/onboarding/analytics"
                      element={<OnboardingAnalyticsPage />}
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

              {/* Mobile production log — standalone, no sidebar */}
              <Route element={<ProtectedRoute />}>
                <Route path="/m/production-log" element={<MobileProductionLog />} />
              </Route>

              {/* Family portal — no auth required, standalone page */}
              <Route path="/portal/:token" element={<FHPortalPage />} />

              {/* Platform admin entry (for non-subdomain setups) */}
              <Route path="/platform-admin" element={<PlatformAdminEntry />} />

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
              <Route path="/platform-admin" element={<PlatformAdminEntry />} />
              <Route path="*" element={<NotFound />} />
            </>
          )}
        </Routes>
        <Toaster />
      </ExtensionProvider>
      </FeatureFlagProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
