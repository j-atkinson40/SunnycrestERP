import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/auth-context";
import VoiceMemoButton from "@/components/ai/VoiceMemoButton";
import { CommandBarProvider } from "@/core/CommandBarProvider";
import { ExtensionProvider } from "@/contexts/extension-context";
import { FeatureFlagProvider } from "@/contexts/feature-flag-context";
import { DeviceProvider } from "@/contexts/device-context";
import { LayoutProvider } from "@/contexts/layout-context";
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
import CompanyMigrationReviewPage from "@/pages/admin/company-migration-review";
import CompanyClassificationPage from "@/pages/admin/company-classification";
import CompaniesListPage from "@/pages/crm/companies";
import CompanyDetailPage from "@/pages/crm/company-detail";
import FuneralHomesPage from "@/pages/crm/funeral-homes";
import BillingGroupsPage from "@/pages/crm/billing-groups";
import BillingGroupDetailPage from "@/pages/crm/billing-group-detail";
import ContractorsPage from "@/pages/crm/contractors";
import CrmSettingsPage from "@/pages/crm/crm-settings";
import PipelinePage from "@/pages/crm/pipeline";
import AiSettingsPage from "@/pages/settings/ai-settings";
import DuplicateReviewPage from "@/pages/crm/duplicates";
import DataQualityPage from "@/pages/admin/data-quality";
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
// CustomersPage removed — /customers redirects to /crm/companies?role=customer
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
import BillingPage from "@/pages/billing/billing-page";
import { ReceivedStatementDetail } from "@/pages/billing/received-statements";
import InvoiceDetailPage from "@/pages/invoice-detail";
import CustomerPaymentsPage from "@/pages/customer-payments";
import PaymentDetailPage from "@/pages/payment-detail";
import ARAgingPage2 from "@/pages/ar-aging";
import ModulesPage from "@/pages/admin/modules";
import DeliverySettingsPage from "@/pages/admin/delivery-settings";
import DriverPortalPreviewPage from "@/pages/admin/driver-portal-preview";
import OperationsPage from "@/pages/delivery/operations";
import HistoryPage from "@/pages/delivery/history";
import DeliveryDetailPage from "@/pages/delivery/delivery-detail";
import RouteDetailPage from "@/pages/delivery/route-detail";
import CarriersPage from "@/pages/delivery/carriers";
import SchedulingBoardPage from "@/pages/delivery/scheduling-board";
import BOMListPage from "@/pages/bom/bom-list";
import BOMDetailPage from "@/pages/bom/bom-detail";
import ProjectListPage from "@/pages/projects/project-list";
import ProjectDetailPage from "@/pages/projects/project-detail";
import QCMobilePage from "@/pages/qc/qc-mobile";
import QCDashboardPage from "@/pages/qc/qc-dashboard";
import QCInspectionDetailPage from "@/pages/qc/qc-inspection-detail";
import NpcaAuditPrepPage from "@/pages/compliance/npca-audit-prep";
import TrainingHubPage from "@/pages/training/training-hub";
import SafetyDashboardPage from "@/pages/safety/safety-dashboard";
import SafetyInspectPage from "@/pages/safety/safety-inspect";
import SafetyIncidentPage from "@/pages/safety/safety-incidents";
import SafetyChemicalsPage from "@/pages/safety/safety-chemicals";
import SafetyLOTOPage from "@/pages/safety/safety-loto";
import SafetyProgramsPage from "@/pages/safety/safety-programs";
import SafetyTrainingPage from "@/pages/safety/safety-training";
import SafetyOSHA300Page from "@/pages/safety/safety-osha300";
import SafetyNoticesPage from "@/pages/safety/safety-notices";
import SafetyTrainingCalendarPage from "@/pages/safety/safety-training-calendar";
import SafetyTrainingPostPage from "@/pages/safety/safety-training-post";
import SafetyToolboxTalksPage from "@/pages/safety/safety-toolbox-talks";
import SafetyTrainingDocumentsPage from "@/pages/safety/safety-training-documents";
import SafetyOSHA300YearEndPage from "@/pages/safety/safety-osha300-yearend";
import ProductionBoardPage from "@/pages/production/production-board";
import PourEventCreatePage from "@/pages/production/pour-event-create";
import WorkOrderDetailPage from "@/pages/production/work-order-detail";
import { ConsoleLayout } from "@/components/layout/console-layout";
import { DriverLayout } from "@/components/layout/driver-layout";
import ConsoleSelectPage from "@/pages/console/console-select";
import DeliveryConsolePage from "@/pages/console/delivery-console";
import OperationsBoardPage from "@/pages/console/operations-board";
import ProductionConsolePage from "@/pages/console/production-console";
import LogProductionPage from "@/pages/console/mobile/log-production";
import SafetyLogPage from "@/pages/console/mobile/safety-log";
import QCCheckPage from "@/pages/console/mobile/qc-check";
import ReceiveDeliveryPage from "@/pages/console/mobile/receive-delivery";
import EndOfDayPage from "@/pages/console/mobile/end-of-day";
import EquipmentInspectionPage from "@/pages/console/mobile/equipment-inspection";
import DriverHomePage from "@/pages/driver/home";
import DriverRoutePage from "@/pages/driver/route";
import StopDetailPage from "@/pages/driver/stop-detail";
import MileagePage from "@/pages/driver/mileage";
import DriverConsolePage from "@/pages/driver/driver-console";
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
import AnnouncementsPage from "@/pages/announcements";
import OnboardingHub from "@/pages/onboarding/onboarding-hub";
import OnboardingFlow from "@/pages/onboarding/onboarding-flow";
import IntegrationSetupPage from "@/pages/onboarding/integration-setup";
import OnboardingAnalyticsPage from "@/pages/onboarding/onboarding-analytics";
import ProductLibraryPage from "@/pages/onboarding/product-library";
import ImportWizardPage from "@/pages/onboarding/import-wizard";
import ScenarioPlayerPage from "@/pages/onboarding/scenario-player";
import CatalogBuilder from "@/pages/onboarding/catalog-builder";
import WebsiteSuggestionsReview from "@/pages/onboarding/website-suggestions-review";
import ChargeSetupPage from "@/pages/onboarding/charge-setup";
import ChargeTermsOnboardingPage from "@/pages/onboarding/charge-terms";
import TeamSetupPage from "@/pages/onboarding/team-setup";
import SafetyTrainingSetupPage from "@/pages/onboarding/safety-training-setup";
import TaxJurisdictionsOnboarding from "@/pages/onboarding/tax-jurisdictions";
import TransfersPage from "@/pages/transfers";
import ProcedureLibraryPage, { ProcedureDetailPage } from "@/pages/training/procedure-library";
import VaultOrderLifecyclePage from "@/pages/training/vault-order-lifecycle";
import LegacyProofReviewPage from "@/pages/legacy/legacy-proof-review";
import LegacyLibraryPage from "@/pages/legacy/library";
import LegacyDetailPage from "@/pages/legacy/legacy-detail";
import ProofGeneratorPage from "@/pages/legacy/proof-generator";
import LegacySettingsPage from "@/pages/legacy/legacy-settings";
import TemplateUploadPage from "@/pages/legacy/template-upload";
import TeamIntelligencePage from "@/pages/onboarding/team-intelligence";
import FuneralHomeCustomersWizard from "@/pages/onboarding/funeral-home-customers";
import CemeterySetupWizard from "@/pages/onboarding/cemetery-setup";
import QuickOrdersOnboarding from "@/pages/onboarding/quick-orders";
import HistoricalOrderImportPage from "@/pages/onboarding/historical-order-import";
import UnifiedImportPage from "@/pages/onboarding/unified-import";
import CompanyBrandingPage from "@/pages/onboarding/company-branding";
import InvoiceSettingsPage from "@/pages/settings/invoice-settings";
import SeasonalTemplatesSettings from "@/pages/settings/seasonal-templates";
import VaultMoldSettingsPage from "@/pages/settings/vault-mold-settings";
import VaultSupplierSettingsPage from "@/pages/settings/vault-supplier-settings";
import CallIntelligenceSettingsPage from "@/pages/settings/call-intelligence-settings";
import ImportMatchingPage from "@/pages/onboarding/import-matching";
import ProgramsSettingsPage from "@/pages/settings/programs-settings";
import ComplianceConfigPage from "@/pages/settings/compliance-config";
import VaultMoldSetupPage from "@/pages/onboarding/vault-mold-setup";
import VaultSetupPage from "@/pages/onboarding/vault-setup";
import AccountingSetupPage from "@/pages/onboarding/accounting-setup";
import DataMigrationPage from "@/pages/onboarding/data-migration";
import AccountingReviewPage from "@/pages/onboarding/accounting-review";
import TeamDashboardPage from "@/pages/team/team-dashboard";
import CallLogPage from "@/pages/calls/call-log";
import KnowledgeBasePage from "@/pages/knowledge-base";
import PriceManagementPage from "@/pages/price-management";
import PriceManagementTemplatesPage from "@/pages/price-management-templates";
import PriceManagementEmailSettingsPage from "@/pages/price-management-email-settings";
import PriceManagementSendPage from "@/pages/price-management-send";
import AlertsPage from "@/pages/alerts";
import JournalEntriesPage from "@/pages/journal-entries";
import TaxSettingsPage from "@/pages/settings/tax-settings";
import CustomerTypesPage from "@/pages/settings/customer-types";
import CemeteryDeliverySettingsPage from "@/pages/settings/cemeteries";
import CemeteryProfilePage from "@/pages/settings/cemetery-profile";
import ReportsPage from "@/pages/reports";
import SocialServiceCertificatesPage from "@/pages/social-service-certificates";
import FinancialsBoardPage from "@/pages/financials-board";
import AgentDashboard from "@/pages/agents/AgentDashboard";
import ApprovalReview from "@/pages/agents/ApprovalReview";
import FinancialsHub from "@/pages/hubs/financials-hub";
import CRMHub from "@/pages/hubs/crm-hub";
import ProductionHub from "@/pages/hubs/production-hub";
import ComplianceHub from "@/pages/hubs/compliance-hub";
import StatementsPage from "@/pages/statements";
import CollectionsReviewPage from "@/pages/ar/collections-review";
import InvoiceReviewQueuePage from "@/pages/ar/invoice-review-queue";
import SyncHealthDashboardPage from "@/pages/admin/sync-health-dashboard";
import SchedulingSetupPage from "@/pages/onboarding/scheduling-setup";
import NetworkPreferencesPage from "@/pages/onboarding/network-preferences";
import NetworkPreferencesSettingsPage from "@/pages/admin/network-preferences";
import SchedulingSettingsPage from "@/pages/admin/scheduling-settings";
import LocationsOverview from "@/pages/locations/LocationsOverview";
import LocationSettings from "@/pages/settings/Locations";
import UrnCatalogPage from "@/pages/products/urn-catalog";
import UrnImportWizard from "@/pages/products/urn-import-wizard";
import UrnSalesCatalog from "@/pages/urns/urn-catalog";
import UrnOrderForm from "@/pages/urns/urn-order-form";
import UrnOrdersPage from "@/pages/urns/urn-orders";
import ProofReviewPage from "@/pages/urns/proof-review";
import FHApprovalPage from "@/pages/urns/fh-approval";
import ResaleHub from "@/pages/resale/resale-hub";
import ResaleInventory from "@/pages/resale/resale-inventory";
import DisintermentListPage from "@/pages/disinterments/disinterment-list";
import DisintermentDetailPage from "@/pages/disinterments/disinterment-detail";
import DisintermentSettingsPage from "@/pages/settings/disinterment-settings";
import UnionRotationsPage from "@/pages/settings/union-rotations";
import DisintermentIntakePage from "@/pages/intake/disinterment-intake";
import Unauthorized from "@/pages/unauthorized";
import NotFound from "@/pages/not-found";
import LandingPage from "@/pages/landing";
import CompanyRegisterPage from "@/pages/company-register";
import PlatformAdminEntry from "@/pages/platform-admin-entry";
import { BridgeableAdminApp } from "@/bridgeable-admin/BridgeableAdminApp";
import ProductLinesPage from "@/pages/settings/ProductLines";
import WorkflowsSettingsPage from "@/pages/settings/Workflows";
// Funeral Home vertical (FH-1a + FH-1b)
import FhDirectionHub from "@/fh/pages/DirectionHub";
import FhCaseList from "@/fh/pages/CaseList";
import FhCaseDashboard from "@/fh/pages/CaseDashboard";
import FhArrangementConference from "@/fh/pages/ArrangementConference";
import FhVitalStatistics from "@/fh/pages/VitalStatistics";
import FhStoryStep from "@/fh/pages/StoryStep";
import FhCemeteryStep from "@/fh/pages/CemeteryStep";
import FhNetworkSettings from "@/fh/pages/NetworkSettings";
import { LocationProvider } from "@/contexts/location-context";
import { CallContextProvider } from "@/contexts/call-context";
import { CallOverlay } from "@/components/call/CallOverlay";
import { Component, type ErrorInfo, type ReactNode } from "react";

class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("App error boundary caught:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, fontFamily: "sans-serif" }}>
          <h1 style={{ color: "#b91c1c" }}>Something went wrong</h1>
          <pre style={{ whiteSpace: "pre-wrap", color: "#666", marginTop: 12 }}>
            {this.state.error?.message}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{ marginTop: 16, padding: "8px 16px", cursor: "pointer" }}
          >
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/** Bridges auth context → DeviceProvider so userId is available */
function AuthDeviceProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  return <DeviceProvider userId={user?.id ?? null}>{children}</DeviceProvider>
}

export default function App() {
  // Bridgeable super admin portal (new redesigned portal) — entirely separate app.
  // Accessed three ways:
  //   1. /bridgeable-admin/* path on any host
  //   2. admin.* subdomain (replaces legacy PlatformApp as the default admin UI)
  //   3. localStorage flag `use_legacy_platform_admin=true` falls back to old PlatformApp
  const onBridgeableAdminPath =
    typeof window !== "undefined" &&
    window.location.pathname.startsWith("/bridgeable-admin")
  const onAdminSubdomain = isPlatformAdmin()
  const useLegacyPlatform =
    typeof localStorage !== "undefined" &&
    localStorage.getItem("use_legacy_platform_admin") === "true"

  if (onBridgeableAdminPath || (onAdminSubdomain && !useLegacyPlatform)) {
    return (
      <BrowserRouter>
        <BridgeableAdminApp />
        <Toaster />
      </BrowserRouter>
    )
  }

  // Legacy platform admin — kept as opt-in fallback via localStorage flag
  if (onAdminSubdomain) {
    return (
      <BrowserRouter>
        <PlatformApp />
        <Toaster />
      </BrowserRouter>
    );
  }

  const slug = getCompanySlug();

  return (
    <ErrorBoundary>
    <BrowserRouter>
      <AuthProvider>
      <FeatureFlagProvider>
      <ExtensionProvider>
      <LocationProvider>
      <LayoutProvider>
      <AuthDeviceProvider>
      <CommandBarProvider>
      <CallContextProvider>
        <ImpersonationBanner />
        <CallOverlay />
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

                  {/* Team dashboard — requires users.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="users.view" />
                    }
                  >
                    <Route
                      path="/team"
                      element={<TeamDashboardPage />}
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
                    <Route
                      path="/admin/company-migration"
                      element={<CompanyMigrationReviewPage />}
                    />
                  </Route>

                  {/* Hub Pages */}
                  <Route element={<ProtectedRoute requiredPermission="financials.view" />}>
                    <Route path="/financials" element={<FinancialsHub />} />
                  </Route>
                  <Route path="/crm" element={<CRMHub />} />
                  <Route element={<ProtectedRoute requiredPermission="production_hub.view" />}>
                    <Route path="/production-hub" element={<ProductionHub />} />
                  </Route>
                  <Route element={<ProtectedRoute requiredPermission="safety.view" requiredModule="safety_management" />}>
                    <Route path="/compliance" element={<ComplianceHub />} />
                  </Route>

                  {/* CRM */}
                  <Route path="/crm/companies" element={<CompaniesListPage />} />
                  <Route path="/admin/company-classification" element={<CompanyClassificationPage />} />
                  <Route path="/crm/companies/:id" element={<CompanyDetailPage />} />
                  <Route path="/crm/funeral-homes" element={<FuneralHomesPage />} />
                  <Route path="/crm/contractors" element={<ContractorsPage />} />
                  <Route path="/crm/billing-groups" element={<BillingGroupsPage />} />
                  <Route path="/crm/billing-groups/:id" element={<BillingGroupDetailPage />} />
                  <Route path="/crm/settings" element={<CrmSettingsPage />} />
                  <Route path="/crm/pipeline" element={<PipelinePage />} />
                  <Route path="/crm/companies/duplicates" element={<DuplicateReviewPage />} />
                  <Route path="/admin/data-quality" element={<DataQualityPage />} />
                  <Route path="/settings/ai-intelligence" element={<AiSettingsPage />} />

                  {/* Products — core feature, no module gate */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="products.view" />
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
                    <Route
                      path="settings/catalog/bundles"
                      element={<Navigate to="/products?tab=bundles" replace />}
                    />
                  </Route>

                  {/* Urn Sales extension */}
                  <Route path="/urns/catalog" element={<UrnSalesCatalog />} />
                  <Route path="/urns/orders" element={<UrnOrdersPage />} />
                  <Route path="/urns/orders/new" element={<UrnOrderForm />} />
                  <Route path="/urns/proof-review/:orderId" element={<ProofReviewPage />} />

                  {/* Resale hub — aliases urn pages + stub inventory */}
                  <Route path="/resale" element={<ResaleHub />} />
                  <Route path="/resale/catalog" element={<UrnSalesCatalog />} />
                  <Route path="/resale/orders" element={<UrnOrdersPage />} />
                  <Route path="/resale/inventory" element={<ResaleInventory />} />

                  {/* Customers — requires sales module + customers.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="customers.view" requiredModule="sales" />
                    }
                  >
                    <Route
                      path="/customers"
                      element={<Navigate to="/crm/companies?role=customer" replace />}
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
                      path="/billing"
                      element={<BillingPage />}
                    />
                    {/* Redirect old billing/received to Vendors & Bills */}
                    <Route
                      path="/billing/received/:id"
                      element={<Navigate to="/ap/bills?tab=received" replace />}
                    />
                    <Route
                      path="/billing/received"
                      element={<Navigate to="/ap/bills?tab=received" replace />}
                    />
                    <Route
                      path="/ar/invoices/review"
                      element={<InvoiceReviewQueuePage />}
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
                      path="/ar/payments/:id"
                      element={<PaymentDetailPage />}
                    />
                    <Route
                      path="/ar/aging"
                      element={<ARAgingPage2 />}
                    />
                    <Route
                      path="/ar/statements"
                      element={<StatementsPage />}
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
                    <Route path="/transfers" element={<TransfersPage />} />
                    <Route
                      path="/ap/bills/:id"
                      element={<VendorBillDetailPage />}
                    />
                    <Route
                      path="/ap/received/:id"
                      element={<ReceivedStatementDetail />}
                    />
                    <Route path="/alerts" element={<AlertsPage />} />
                    <Route path="/journal-entries" element={<JournalEntriesPage />} />
                    <Route path="/settings/tax" element={<TaxSettingsPage />} />
                    <Route path="/reports" element={<ReportsPage />} />
                    <Route path="/social-service-certificates" element={<SocialServiceCertificatesPage />} />
                    <Route path="/financials/board" element={<FinancialsBoardPage />} />
                    <Route path="/agents" element={<AgentDashboard />} />
                    <Route path="/agents/:jobId/review" element={<ApprovalReview />} />
                    <Route path="/ar/collections/:sequenceId/review" element={<CollectionsReviewPage />} />
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

                  {/* Training hub — accessible to all, tiles gated individually */}
                  <Route path="/training" element={<TrainingHubPage />} />

                  {/* Safety Management — requires safety_management module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="safety.view" requiredModule="safety_management" />
                    }
                  >
                    {/* Training */}
                    <Route path="/training/vault-order-lifecycle" element={<VaultOrderLifecyclePage />} />
                    <Route path="/legacy/proof/:orderId" element={<LegacyProofReviewPage />} />
                    <Route path="/legacy/generator" element={<ProofGeneratorPage />} />
                    <Route path="/legacy/settings" element={<LegacySettingsPage />} />
                    <Route path="/legacy/templates/upload" element={<TemplateUploadPage />} />
                    <Route path="/legacy/library" element={<LegacyLibraryPage />} />
                    <Route path="/legacy/library/:legacyId" element={<LegacyDetailPage />} />
                    <Route path="/training/procedures" element={<ProcedureLibraryPage />} />
                    <Route path="/training/procedures/:key" element={<ProcedureDetailPage />} />
                    {/* Safety */}
                    <Route path="/safety" element={<SafetyDashboardPage />} />
                    <Route path="/safety/programs" element={<SafetyProgramsPage />} />
                    <Route path="/safety/training" element={<SafetyTrainingPage />} />
                    <Route path="/safety/inspections/new" element={<SafetyInspectPage />} />
                    <Route path="/safety/inspect/:inspectionId" element={<SafetyInspectPage />} />
                    <Route path="/safety/incidents" element={<SafetyIncidentPage />} />
                    <Route path="/safety/incidents/new" element={<SafetyIncidentPage />} />
                    <Route path="/safety/chemicals" element={<SafetyChemicalsPage />} />
                    <Route path="/safety/loto" element={<SafetyLOTOPage />} />
                    <Route path="/safety/notices" element={<SafetyNoticesPage />} />
                    <Route path="/safety/training/calendar" element={<SafetyTrainingCalendarPage />} />
                    <Route path="/safety/training/:scheduleId/post" element={<SafetyTrainingPostPage />} />
                    <Route path="/safety/toolbox-talks" element={<SafetyToolboxTalksPage />} />
                    <Route path="/safety/training/documents" element={<SafetyTrainingDocumentsPage />} />
                    <Route path="/safety/osha-300" element={<SafetyOSHA300Page />} />
                    <Route path="/safety/osha-300/year-end/:year" element={<SafetyOSHA300YearEndPage />} />
                  </Route>

                  {/* NPCA Audit Prep — requires npca_audit_prep extension */}
                  <Route
                    element={
                      <ProtectedRoute requiredModule="npca_audit_prep" />
                    }
                  >
                    <Route path="/npca" element={<NpcaAuditPrepPage />} />
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
                    <Route path="/scheduling" element={<SchedulingBoardPage />} />
                    <Route path="/delivery/dispatch" element={<Navigate to="/scheduling" replace />} />
                    <Route path="/delivery/funeral-scheduling" element={<Navigate to="/scheduling" replace />} />
                    <Route path="/delivery/operations" element={<OperationsPage />} />
                    <Route path="/delivery/history" element={<HistoryPage />} />
                    <Route path="/delivery/deliveries/:id" element={<DeliveryDetailPage />} />
                    <Route path="/delivery/routes/:id" element={<RouteDetailPage />} />
                    <Route path="/delivery/settings" element={<DeliverySettingsPage />} />
                    <Route path="/admin/announcements" element={<Navigate to="/announcements" replace />} />
                    <Route path="/settings/driver-portal-preview" element={<DriverPortalPreviewPage />} />
                    <Route path="/admin/driver-portal-preview" element={<Navigate to="/settings/driver-portal-preview" replace />} />
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

                  {/* Disinterment Management — requires disinterment_management extension */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="disinterments.view" requiredExtension="disinterment_management" />
                    }
                  >
                    <Route path="/disinterments" element={<DisintermentListPage />} />
                    <Route path="/disinterments/:id" element={<DisintermentDetailPage />} />
                  </Route>
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="disinterment_settings.manage" requiredExtension="disinterment_management" />
                    }
                  >
                    <Route path="/settings/disinterment" element={<DisintermentSettingsPage />} />
                  </Route>
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="union_rotations.view" requiredExtension="disinterment_management" />
                    }
                  >
                    <Route path="/settings/union-rotations" element={<UnionRotationsPage />} />
                  </Route>

                  {/* Call Log — any authenticated user */}
                  <Route path="/calls" element={<CallLogPage />} />

                  {/* Knowledge Base — any authenticated user */}
                  <Route path="/knowledge-base" element={<KnowledgeBasePage />} />

                  {/* Price Management */}
                  <Route path="/price-management" element={<PriceManagementPage />} />
                  <Route path="/price-management/templates" element={<PriceManagementTemplatesPage />} />
                  <Route path="/price-management/email-settings" element={<PriceManagementEmailSettingsPage />} />
                  <Route path="/price-management/send" element={<PriceManagementSendPage />} />

                  {/* Announcements — any authenticated user */}
                  <Route path="/announcements" element={<AnnouncementsPage />} />

                  {/* Onboarding — any authenticated user */}
                  <Route path="/onboarding" element={<OnboardingHub />} />
                  <Route path="/onboarding/flow" element={<OnboardingFlow />} />
                  <Route path="/onboarding/import-matching" element={<ImportMatchingPage />} />
                  <Route path="/onboarding/integrations/:type" element={<IntegrationSetupPage />} />
                  <Route path="/onboarding/product-library" element={<ProductLibraryPage />} />
                  <Route path="/onboarding/import/:type" element={<ImportWizardPage />} />
                  <Route path="/onboarding/scenarios/:scenarioKey" element={<ScenarioPlayerPage />} />
                  <Route path="/onboarding/website-review" element={<WebsiteSuggestionsReview />} />
                  <Route path="/onboarding/catalog-builder" element={<CatalogBuilder />} />
                  <Route path="/onboarding/team" element={<TeamSetupPage />} />
                  <Route path="/onboarding/team-intelligence" element={<TeamIntelligencePage />} />
                  <Route path="/onboarding/safety-training" element={<SafetyTrainingSetupPage />} />
                  <Route path="/onboarding/tax-jurisdictions" element={<TaxJurisdictionsOnboarding />} />
                  <Route path="/onboarding/charges" element={<ChargeSetupPage />} />
                  <Route path="/onboarding/charge-terms" element={<ChargeTermsOnboardingPage />} />
                  <Route path="/onboarding/customers/funeral-homes" element={<FuneralHomeCustomersWizard />} />
                  <Route path="/onboarding/cemeteries" element={<CemeterySetupWizard />} />
                  <Route path="/onboarding/quick-orders" element={<QuickOrdersOnboarding />} />
                  <Route path="/onboarding/historical-orders" element={<HistoricalOrderImportPage />} />
                  <Route path="/onboarding/import" element={<UnifiedImportPage />} />
                  <Route path="/onboarding/branding" element={<CompanyBrandingPage />} />
                  <Route path="/settings/seasonal-templates" element={<SeasonalTemplatesSettings />} />
                  <Route path="/onboarding/accounting" element={<AccountingSetupPage />} />
                  <Route path="/onboarding/data-migration" element={<DataMigrationPage />} />
                  <Route path="/settings/data-migration" element={<DataMigrationPage />} />
                  <Route path="/settings/data/customer-types" element={<CustomerTypesPage />} />
                  <Route path="/settings/cemeteries/:cemeteryId" element={<CemeteryProfilePage />} />
                  <Route path="/settings/cemeteries" element={<CemeteryDeliverySettingsPage />} />
                  <Route path="/onboarding/accounting/review" element={<AccountingReviewPage />} />
                  <Route path="/onboarding/scheduling" element={<SchedulingSetupPage />} />
                  <Route path="/onboarding/network-preferences" element={<NetworkPreferencesPage />} />
                  <Route path="/onboarding/vault-setup" element={<VaultSetupPage />} />
                  <Route path="/onboarding/vault-molds" element={<VaultMoldSetupPage />} />
                  <Route path="/settings/team-intelligence" element={<TeamIntelligencePage />} />
                  <Route path="/settings/charges" element={<ChargeSetupPage />} />
                  <Route path="/settings/invoice" element={<InvoiceSettingsPage />} />
                  <Route path="/settings/vault-supplier" element={<VaultSupplierSettingsPage />} />
                  <Route path="/settings/vault-molds" element={<VaultMoldSettingsPage />} />
                  <Route path="/settings/network/preferences" element={<NetworkPreferencesSettingsPage />} />
                  <Route path="/settings/scheduling" element={<SchedulingSettingsPage />} />
                  <Route path="/settings/call-intelligence" element={<CallIntelligenceSettingsPage />} />
                  <Route path="/settings/programs" element={<ProgramsSettingsPage />} />
                  <Route path="/settings/compliance" element={<ComplianceConfigPage />} />
                  <Route path="/settings/integrations/accounting" element={<SyncHealthDashboardPage />} />

                  {/* Locations — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route path="/locations" element={<LocationsOverview />} />
                    <Route path="/settings/locations" element={<LocationSettings />} />
                  </Route>

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
                    <Route
                      path="/settings/product-lines"
                      element={<ProductLinesPage />}
                    />
                    <Route
                      path="/settings/workflows"
                      element={<WorkflowsSettingsPage />}
                    />
                    {/* Funeral Home vertical (FH-1a + FH-1b) */}
                    <Route path="/fh" element={<FhDirectionHub />} />
                    <Route path="/fh/cases" element={<FhCaseList />} />
                    <Route path="/fh/cases/:caseId" element={<FhCaseDashboard />} />
                    <Route path="/fh/cases/:caseId/arrangement" element={<FhArrangementConference />} />
                    <Route path="/fh/cases/:caseId/vital-statistics" element={<FhVitalStatistics />} />
                    <Route path="/fh/cases/:caseId/story" element={<FhStoryStep />} />
                    <Route path="/fh/cases/:caseId/cemetery" element={<FhCemeteryStep />} />
                    <Route path="/fh/settings/network" element={<FhNetworkSettings />} />
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
                  <Route path="/driver" element={<DriverConsolePage />} />
                  <Route path="/driver/home" element={<DriverHomePage />} />
                  <Route path="/driver/route" element={<DriverRoutePage />} />
                  <Route path="/driver/stops/:stopId" element={<StopDetailPage />} />
                  <Route path="/driver/mileage" element={<MileagePage />} />
                </Route>
              </Route>

              {/* Console — production/delivery employees */}
              <Route element={<ProtectedRoute />}>
                <Route element={<ConsoleLayout />}>
                  <Route path="/console" element={<ConsoleSelectPage />} />
                  <Route path="/console/delivery" element={<DeliveryConsolePage />} />
                  <Route path="/console/operations" element={<OperationsBoardPage />} />
                  <Route path="/console/production" element={<ProductionConsolePage />} />
                  <Route path="/console/operations/product-entry" element={<LogProductionPage />} />
                  <Route path="/console/operations/incident" element={<SafetyLogPage />} />
                  <Route path="/console/operations/observation" element={<SafetyLogPage />} />
                  <Route path="/console/operations/qc" element={<QCCheckPage />} />
                  <Route path="/console/operations/receive" element={<ReceiveDeliveryPage />} />
                  <Route path="/console/operations/receive/:poId" element={<ReceiveDeliveryPage />} />
                  <Route path="/console/operations/end-of-day" element={<EndOfDayPage />} />
                  <Route path="/console/operations/inspection" element={<EquipmentInspectionPage />} />
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

              {/* Public intake form — no auth required */}
              <Route path="/intake/disinterment/:token" element={<DisintermentIntakePage />} />

              {/* FH proof approval — public, token-validated */}
              <Route path="/proof-approval/:token" element={<FHApprovalPage />} />

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
        {/* Global floating voice memo button */}
        <div className="fixed bottom-6 right-6 z-40 sm:hidden">
          <VoiceMemoButton compact />
        </div>
      </CallContextProvider>
      </CommandBarProvider>
      </AuthDeviceProvider>
      </LayoutProvider>
      </LocationProvider>
      </ExtensionProvider>
      </FeatureFlagProvider>
      </AuthProvider>
    </BrowserRouter>
    </ErrorBoundary>
  );
}
