import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import VoiceMemoButton from "@/components/ai/VoiceMemoButton";
import { KeyboardHelpOverlay } from "@/components/core/KeyboardHelpOverlay";
import { OfflineBanner } from "@/components/core/OfflineBanner";
import { PresetThemeProvider } from "@/contexts/preset-theme-context";
import { SpaceProvider } from "@/contexts/space-context";
import { PeekProvider } from "@/contexts/peek-context";
import { Focus } from "@/components/focus/Focus";
import { ReturnPill } from "@/components/focus/ReturnPill";
// Phase R-0 — shared-bundle refactor (Runtime-Aware Editor foundation).
// `TenantProviders` is the 9-deep tenant context chain extracted into
// a shared module; the admin tree's `/_runtime-host-test/*` route
// mounts the same chain to render tenant content under PlatformUser
// auth + an impersonation token. Behavior of the tenant boot path is
// unchanged — the contexts are constructed identically.
import { TenantProviders } from "@/lib/runtime-host/TenantProviders";
// Phase B Session 4 Phase 4.2 — side-effect import registers the
// funeral-scheduling Focus. Must run before any surface attempts to
// open it (Cmd+K action, Monitor button). At app bootstrap is the
// simplest place to guarantee that.
import "@/components/dispatch/scheduling-focus/register";
// Phase W-3a — register cross-vertical foundation widgets (today,
// operator_profile, recent_activity, anomalies) with the canvas
// widget renderer registry so PinnedSection + Canvas + dashboard
// surfaces dispatch them via `getWidgetRenderer(widget_id)`.
import "@/components/widgets/foundation/register";
// Phase W-3d — register manufacturing per-line widgets (vault_schedule
// + future line_status + urn_catalog_status). Same side-effect-on-
// import pattern as foundation; widgets are registered at app
// bootstrap before any surface consumer.
import "@/components/widgets/manufacturing/register";
// Phase 1 of the Admin Visual Editor — populate the component
// registry with Phase 1 tagged components. The registry is read by
// the /admin/registry debug page and (later phases) by the visual
// editor. Side-effect-on-import; mirrors the widget-registration
// pattern above.
import "@/lib/visual-editor/registry/auto-register";
import { AffinityVisitWatcher } from "@/components/spaces/AffinityVisitWatcher";
import { PeekHost } from "@/components/peek/PeekHost";
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
import HomePage from "@/pages/home/HomePage";
import FocusTestPage from "@/pages/dev/focus-test";
import FuneralSchedulePage from "@/pages/dispatch/funeral-schedule";
import UserManagement from "@/pages/admin/user-management";
import RoleManagement from "@/pages/admin/role-management";
import EmailClassificationPage from "@/pages/admin/EmailClassificationPage";
import CompanyMigrationReviewPage from "@/pages/admin/company-migration-review";
import CompanyClassificationPage from "@/pages/admin/company-classification";
import CompaniesListPage from "@/pages/crm/companies";
import CompanyDetailPage from "@/pages/crm/company-detail";
import NewContactPage from "@/pages/crm/new-contact";
import FuneralHomesPage from "@/pages/crm/funeral-homes";
import BillingGroupsPage from "@/pages/crm/billing-groups";
import BillingGroupDetailPage from "@/pages/crm/billing-group-detail";
import ContractorsPage from "@/pages/crm/contractors";
import CrmSettingsPage from "@/pages/crm/crm-settings";
import PipelinePage from "@/pages/crm/pipeline";
import AiSettingsPage from "@/pages/settings/ai-settings";
import SavedViewsIndex from "@/pages/saved-views/SavedViewsIndex";
import SavedViewPage from "@/pages/saved-views/SavedViewPage";
import SavedViewCreatePage from "@/pages/saved-views/SavedViewCreatePage";
import TasksList from "@/pages/tasks/TasksList";
import TaskCreate from "@/pages/tasks/TaskCreate";
import TaskDetail from "@/pages/tasks/TaskDetail";
import TriageIndex from "@/pages/triage/TriageIndex";
import TriagePage from "@/pages/triage/TriagePage";
import BriefingPage from "@/pages/briefings/BriefingPage";
import BriefingPreferencesPage from "@/pages/settings/BriefingPreferences";
import EdgePanelSettingsPage from "@/pages/settings/EdgePanelSettingsPage";
import ManufacturerPersonalizationStudioFromShareView from "@/pages/personalization-studio/ManufacturerPersonalizationStudioFromShareView";
import SpacesSettings from "@/pages/settings/SpacesSettings";
import PortalUsersSettings from "@/pages/settings/PortalUsersSettings";
import PortalBrandingSettings from "@/pages/settings/PortalBrandingSettings";
import EmailAccountsPage from "@/pages/settings/EmailAccountsPage";
import CalendarAccountsPage from "@/pages/settings/CalendarAccountsPage";
import CalendarConsentPage from "@/pages/settings/CalendarConsentPage";
import CalendarDraftsPage from "@/pages/settings/CalendarDraftsPage";
import CalendarOAuthCallback from "@/pages/settings/CalendarOAuthCallback";
import EmailOAuthCallback from "@/pages/settings/EmailOAuthCallback";
import InboxPage from "@/pages/email/InboxPage";
import SavedOrdersPage from "@/pages/settings/SavedOrders";
import ExternalAccountsPage from "@/pages/settings/ExternalAccounts";
import DuplicateReviewPage from "@/pages/crm/duplicates";
import DataQualityPage from "@/pages/admin/data-quality";
import AuditLogs from "@/pages/admin/audit-logs";
import IntelligencePromptLibrary from "@/pages/admin/intelligence/PromptLibrary";
import DocumentTemplateLibrary from "@/pages/admin/documents/DocumentTemplateLibrary";
import DocumentTemplateDetail from "@/pages/admin/documents/DocumentTemplateDetail";
import DocumentLog from "@/pages/admin/documents/DocumentLog";
import DocumentDetail from "@/pages/admin/documents/DocumentDetail";
import DocumentInbox from "@/pages/admin/documents/DocumentInbox";
import DeliveryLog from "@/pages/admin/documents/DeliveryLog";
import DeliveryDetail from "@/pages/admin/documents/DeliveryDetail";
import SigningEnvelopeLibrary from "@/pages/admin/signing/SigningEnvelopeLibrary";
import SigningEnvelopeDetail from "@/pages/admin/signing/SigningEnvelopeDetail";
import CreateEnvelopeWizard from "@/pages/admin/signing/CreateEnvelopeWizard";
import SignerLandingPage from "@/pages/sign/SignerLandingPage";
import MagicLinkActionPage from "@/pages/email/MagicLinkActionPage";
import CalendarMagicLinkActionPage from "@/pages/calendar/MagicLinkActionPage";
import EventDetailPage from "@/pages/calendar/EventDetailPage";
import IntelligencePromptDetail from "@/pages/admin/intelligence/PromptDetail";
import IntelligenceExecutionLog from "@/pages/admin/intelligence/ExecutionLog";
import IntelligenceExecutionDetail from "@/pages/admin/intelligence/ExecutionDetail";
import IntelligenceModelRoutes from "@/pages/admin/intelligence/ModelRoutes";
import IntelligenceExperimentLibrary from "@/pages/admin/intelligence/ExperimentLibrary";
import IntelligenceExperimentDetail from "@/pages/admin/intelligence/ExperimentDetail";
import IntelligenceCreateExperiment from "@/pages/admin/intelligence/CreateExperiment";
// ── V-1a — Bridgeable Vault Hub ──
// VaultHubLayout wraps every /vault/* route; the existing admin pages
// (Documents, Intelligence) render unchanged inside it under new URLs.
import VaultHubLayout from "@/pages/vault/VaultHubLayout";
import VaultOverview from "@/pages/vault/VaultOverview";
// V-1e: Accounting admin consolidation.
import AccountingAdminLayout from "@/pages/vault/accounting/AccountingAdminLayout";
import AccountingPeriodsTab from "@/pages/vault/accounting/AccountingPeriodsTab";
import AccountingAgentsTab from "@/pages/vault/accounting/AccountingAgentsTab";
import AccountingClassificationTab from "@/pages/vault/accounting/AccountingClassificationTab";
import AccountingTaxTab from "@/pages/vault/accounting/AccountingTaxTab";
import AccountingStatementsTab from "@/pages/vault/accounting/AccountingStatementsTab";
import AccountingCoaTab from "@/pages/vault/accounting/AccountingCoaTab";
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
import QuotingHubPage from "@/pages/quoting/quoting-hub";
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
import ProductionBoardDashboard from "@/pages/production/ProductionBoardDashboard";
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
import OperatorOnboardingFlow from "@/pages/onboarding/OperatorOnboardingFlow";
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
import { PortalApp } from "@/PortalApp";
import ProductLinesPage from "@/pages/settings/ProductLines";
import WorkflowsSettingsPage from "@/pages/settings/Workflows";
import WorkflowBuilderPage from "@/pages/settings/WorkflowBuilder";
// Funeral Home vertical (FH-1a + FH-1b)
import FhDirectionHub from "@/fh/pages/DirectionHub";
import FhCaseList from "@/fh/pages/CaseList";
import FhCaseDashboard from "@/fh/pages/CaseDashboard";
import FhArrangementConference from "@/fh/pages/ArrangementConference";
import FhVitalStatistics from "@/fh/pages/VitalStatistics";
import FhStoryStep from "@/fh/pages/StoryStep";
import FhCemeteryStep from "@/fh/pages/CemeteryStep";
import FhNetworkSettings from "@/fh/pages/NetworkSettings";
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
      // Aesthetic Arc Session 3 refresh — uses DESIGN_LANGUAGE tokens
      // via Tailwind classes rather than inline styles. Pairs with
      // the Alert status-family recipe (status-error + surface-base).
      return (
        <div className="min-h-screen bg-surface-base p-10 font-sans text-content-base">
          <div className="mx-auto max-w-content">
            <div className="rounded-md border-l-4 border-l-status-error bg-status-error-muted p-6 text-status-error">
              <h1 className="text-h2 font-medium">Something went wrong</h1>
              <pre className="mt-4 whitespace-pre-wrap rounded bg-surface-base p-3 font-mono text-caption text-content-base">
                {this.state.error?.message}
              </pre>
              <button
                onClick={() => window.location.reload()}
                className="mt-4 inline-flex items-center rounded bg-accent px-5 py-2.5 font-sans text-body-sm font-semibold text-content-on-accent shadow-level-1 transition-colors duration-quick ease-settle hover:bg-accent-hover active:bg-accent-hover focus-ring-accent"
              >
                Reload page
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// Phase R-0: AuthDeviceProvider was extracted into TenantProviders
// (frontend/src/lib/runtime-host/TenantProviders.tsx) so the same
// chain renders for the admin runtime-host-test surface. Removed
// here to keep a single source of truth.

/**
 * V-1a redirect helper — preserves the last URL segment when
 * forwarding from old /admin/... paths to /vault/... paths.
 * Used for routes with URL params like /:documentId or /:promptId.
 * Example: `/admin/documents/documents/abc-123` →
 * `/vault/documents/abc-123`.
 */
function RedirectPreserveParam({ toPrefix }: { toPrefix: string }) {
  const { pathname } = useLocation();
  const lastSegment = pathname.split("/").filter(Boolean).pop() ?? "";
  return <Navigate to={`${toPrefix}/${lastSegment}`} replace />;
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
  // Phase 8e.2 — portal app (tenant-branded, operational-role UX).
  // Same detection pattern as bridgeable-admin. Portal paths are
  // /portal/<tenant-slug>/* and render an entirely separate shell
  // from the tenant AppLayout.
  const onPortalPath =
    typeof window !== "undefined" &&
    window.location.pathname.startsWith("/portal/")
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

  // Phase 8e.2 — portal route tree. Entirely separate from the tenant
  // AppLayout. Matches /portal/<slug>/* and mounts PortalApp. The
  // portal app owns its own auth (PortalAuthProvider) + branding
  // (PortalBrandProvider) contexts.
  if (onPortalPath) {
    return (
      <BrowserRouter>
        <PortalApp />
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
      <TenantProviders>
        <ImpersonationBanner />
        <OfflineBanner />
        <KeyboardHelpOverlay />
        <CallOverlay />
        {/* Phase A Session 1 — Focus primitive scaffolding. Focus
            renders the overlay when a Focus is open; ReturnPill
            renders just-closed-Focus re-entry affordance. Both
            consume FocusContext (mounted above CommandBarProvider
            so the bar can hide while a Focus is open). */}
        <Focus />
        <ReturnPill />
        <Routes>
          {slug ? renderTenantSlugRoutes() : (
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
      </TenantProviders>
    </BrowserRouter>
    </ErrorBoundary>
  );
}


export interface RenderTenantSlugRoutesOpts {
  /**
   * R-1.6.9: When true, replace the root `<RootRedirect />` and the
   * catch-all `<NotFound />` routes with a direct `<HomePage />` mount
   * at both `/` and `*`. Used by `<TenantRouteTree />` (the runtime
   * editor's tenant route tree) to prevent `<Navigate to="/home" />`
   * from bouncing the URL out of the `/runtime-editor/*` parent route.
   *
   * Production tenant operator flow leaves this false (default) so
   * `<RootRedirect />` continues to dispatch role-based landing
   * (driver → /driver, production → /console, else → /home). The
   * production behavior is unchanged.
   *
   * See `/tmp/picker_navigation_bug.md` for the originating
   * investigation.
   */
  excludeRootRedirect?: boolean;
}


/** Phase R-0 — exported for the admin runtime-host-test surface to
 *  mount via `<Routes>{renderTenantSlugRoutes()}</Routes>` (re-exported
 *  as `TenantRouteTree` from `lib/runtime-host/TenantRouteTree.tsx`).
 *
 *  Returns the slug-set tenant Routes JSX fragment. Children must be
 *  inside a `<Routes>` parent (per react-router contract). The fragment
 *  is the same content the tenant boot path renders today, just lifted
 *  into a function so it's importable.
 *
 *  R-1.6.9: opts.excludeRootRedirect parameterizes the `/` and `*`
 *  routes for the runtime editor consumer — see RenderTenantSlugRoutesOpts. */
export function renderTenantSlugRoutes(
  opts: RenderTenantSlugRoutesOpts = {},
) {
  const { excludeRootRedirect = false } = opts;
  return (
    <>
              {/* Tenant routes — accessed via subdomain or company slug */}
              <Route path="login" element={<LoginPage />} />
              <Route path="register" element={<RegisterPage />} />
              <Route path="unauthorized" element={<Unauthorized />} />

              {/* Protected routes */}
              <Route element={<ProtectedRoute />}>
                <Route
                  element={
                    <PresetThemeProvider>
                      <SpaceProvider>
                        <PeekProvider>
                          <AppLayout />
                          <PeekHost />
                          {/* Phase 8e.1 — fire-and-forget topical
                              affinity recorder. Watches route
                              changes; on any match against the
                              active space's pins, records a visit. */}
                          <AffinityVisitWatcher />
                        </PeekProvider>
                      </SpaceProvider>
                    </PresetThemeProvider>
                  }
                >
                  {/* Dashboard — all authenticated users */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="dashboard.view" />
                    }
                  >
                    <Route path="dashboard" element={<Dashboard />} />
                  </Route>

                  {/* Phase W-4a Commit 5 — Home Space's PulseSurface.
                      No permission gate (Home is the canonical
                      cross-vertical / cross-permission landing space
                      per BRIDGEABLE_MASTER §3.26.1.1). DotNav routes
                      every authenticated user here when they click
                      the Home dot (Phase W-4a Commit 1 seeded the
                      Home system space with default_home_route=/home).
                      Coexists with /dashboard until W-5. */}
                  <Route path="home" element={<HomePage />} />

                  {/* Phase A Session 1 — dev-only test page for the
                      Focus primitive. Not in nav. Any authenticated
                      tenant user can access it. Delete when Phase A
                      ships its first real Focus consumer. */}
                  <Route
                    path="/dev/focus-test"
                    element={<FocusTestPage />}
                  />

                  {/* Phase B Session 1 — Funeral Schedule (formerly
                      "Dispatch Monitor"; renamed Phase 3.3.1 for
                      terminology discipline — "Monitor" is the
                      architectural noun for Pulse's purpose, not a
                      component name). Reachable via direct URL +
                      Cmd+K; not registered as a Space per SPACES_PLAN
                      Option 1 (composition default for Home Pulse,
                      landing here until Phase D Pulse engine ships).
                      Gated on `delivery.view`. */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="delivery.view" />
                    }
                  >
                    <Route
                      path="/dispatch/funeral-schedule"
                      element={<FuneralSchedulePage />}
                    />
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

                  {/* Email classification — R-6.1b.a tenant-admin authoring
                      surface for the R-6.1a + R-6.1a.1 cascade (Tier 1 rules
                      + Tier 2 categories + Tier 2/3 confidence floors). */}
                  <Route element={<ProtectedRoute adminOnly />}>
                    <Route
                      path="/admin/email-classification"
                      element={<EmailClassificationPage />}
                    />
                  </Route>

                  {/* Hub Pages */}
                  <Route element={<ProtectedRoute requiredPermission="financials.view" />}>
                    <Route path="financials" element={<FinancialsHub />} />
                  </Route>
                  {/* V-1c: /crm/* → /vault/crm/* redirects.
                      See the /vault/crm route tree below for the live
                      pages. Redirects stay for one release per the
                      same discipline used for /admin/documents/* in
                      V-1a; see DEBT.md "Vault redirect scaffolding". */}
                  <Route
                    path="/crm"
                    element={<Navigate to="/vault/crm" replace />}
                  />
                  <Route
                    path="/crm/companies"
                    element={
                      <Navigate to="/vault/crm/companies" replace />
                    }
                  />
                  <Route
                    path="/crm/companies/duplicates"
                    element={
                      <Navigate
                        to="/vault/crm/companies/duplicates"
                        replace
                      />
                    }
                  />
                  <Route
                    path="/crm/companies/:id"
                    element={
                      <RedirectPreserveParam toPrefix="/vault/crm/companies" />
                    }
                  />
                  <Route
                    path="/crm/funeral-homes"
                    element={
                      <Navigate to="/vault/crm/funeral-homes" replace />
                    }
                  />
                  <Route
                    path="/crm/contractors"
                    element={
                      <Navigate to="/vault/crm/contractors" replace />
                    }
                  />
                  <Route
                    path="/crm/billing-groups"
                    element={
                      <Navigate to="/vault/crm/billing-groups" replace />
                    }
                  />
                  <Route
                    path="/crm/billing-groups/:id"
                    element={
                      <RedirectPreserveParam toPrefix="/vault/crm/billing-groups" />
                    }
                  />
                  <Route
                    path="/crm/settings"
                    element={
                      <Navigate to="/vault/crm/settings" replace />
                    }
                  />
                  <Route
                    path="/crm/pipeline"
                    element={
                      <Navigate to="/vault/crm/pipeline" replace />
                    }
                  />
                  <Route element={<ProtectedRoute requiredPermission="production_hub.view" />}>
                    <Route path="production-hub" element={<ProductionHub />} />
                  </Route>
                  <Route element={<ProtectedRoute requiredPermission="safety.view" requiredModule="safety_management" />}>
                    <Route path="compliance" element={<ComplianceHub />} />
                  </Route>

                  {/* Admin entry points that happen to live adjacent
                      to CRM but aren't part of the lift-and-shift. */}
                  <Route path="admin/company-classification" element={<CompanyClassificationPage />} />
                  <Route path="admin/data-quality" element={<DataQualityPage />} />
                  <Route path="admin/data-quality" element={<DataQualityPage />} />
                  <Route path="settings/ai-intelligence" element={<AiSettingsPage />} />
                  <Route path="settings/saved-orders" element={<SavedOrdersPage />} />
                  <Route path="settings/external-accounts" element={<ExternalAccountsPage />} />

                  {/* Saved Views — universal primitive (Phase 2). */}
                  {/* Order matters: /new and /:viewId/edit must be
                      declared BEFORE /:viewId so the static
                      segments aren't shadowed by the param route. */}
                  <Route path="saved-views" element={<SavedViewsIndex />} />
                  <Route path="saved-views/new" element={<SavedViewCreatePage mode="create" />} />
                  <Route path="saved-views/:viewId/edit" element={<SavedViewCreatePage mode="edit" />} />
                  <Route path="saved-views/:viewId" element={<SavedViewPage />} />

                  {/* Phase 5 — Tasks. Static /tasks/new declared
                      BEFORE /:taskId so the static route doesn't
                      get shadowed by the param route. */}
                  <Route path="tasks" element={<TasksList />} />
                  <Route path="tasks/new" element={<TaskCreate />} />
                  <Route path="tasks/:taskId" element={<TaskDetail />} />

                  {/* Phase 5 — Triage Workspace. */}
                  <Route path="triage" element={<TriageIndex />} />
                  <Route path="triage/:queueId" element={<TriagePage />} />

                  {/* Phase 6 — Briefings. `/briefing` (no id) shows the
                      latest morning briefing via useBriefing hook; the
                      `:id` variant fetches a specific row. Static paths
                      NOT at risk of shadow — no literal /briefing/X
                      segments collide. Legacy `MorningBriefingCard` at
                      manufacturing-dashboard.tsx + order-station.tsx
                      stays — this route is additive per the Phase 6
                      coexist strategy. */}
                  <Route path="briefing" element={<BriefingPage />} />
                  <Route path="briefing/:id" element={<BriefingPage />} />
                  {/*
                    Phase 1F — Mfg-tenant from-share entry point at
                    canonical `manufacturer_from_fh_share` authoring
                    context. Linked from canonical
                    `email.personalization_studio_share_granted`
                    template's `canvas_url` variable.
                  */}
                  <Route
                    path="/personalization-studio/from-share/:documentShareId"
                    element={
                      <ManufacturerPersonalizationStudioFromShareView />
                    }
                  />
                  <Route
                    path="/settings/briefings"
                    element={<BriefingPreferencesPage />}
                  />
                  <Route
                    path="/settings/spaces"
                    element={<SpacesSettings />}
                  />
                  {/* R-5.1 — per-user edge panel customization. Renders
                      under same authenticated tenant guard as briefing/
                      spaces settings; no admin gate. */}
                  <Route
                    path="/settings/edge-panel"
                    element={<EdgePanelSettingsPage />}
                  />

                  {/* Phase 8e.2.1 — tenant-admin surfaces for managing
                      portal users + tenant-branded portal chrome. Both
                      gated adminOnly because portal-user management
                      affects who can access external driver accounts,
                      and branding changes affect every FH/cemetery
                      rep who sees the tenant's logo in their email. */}
                  <Route element={<ProtectedRoute adminOnly />}>
                    <Route
                      path="/settings/portal-users"
                      element={<PortalUsersSettings />}
                    />
                    <Route
                      path="/settings/portal-branding"
                      element={<PortalBrandingSettings />}
                    />
                    {/* Phase W-4b Layer 1 Step 1 — Email Primitive (§3.26.15).
                       Tenant-admin email account management. Coexists with
                       Phase D-7 transactional send infrastructure (different
                       architectural concern: conversation/inbox vs one-shot
                       transactional send). */}
                    <Route
                      path="/settings/email"
                      element={<EmailAccountsPage />}
                    />
                    <Route
                      path="/settings/email/oauth-callback"
                      element={<EmailOAuthCallback />}
                    />
                    {/* Phase W-4b Layer 1 Calendar Step 1 (§3.26.16).
                       Tenant-admin calendar account management. Coexists
                       with the existing Vault iCal feed at
                       /api/v1/vault/calendar.ics (different concerns:
                       one-way iCal export vs. canonical primitive with
                       provider abstraction + bidirectional sync). */}
                    <Route
                      path="/settings/calendar"
                      element={<CalendarAccountsPage />}
                    />
                    <Route
                      path="/settings/calendar/oauth-callback"
                      element={<CalendarOAuthCallback />}
                    />
                    {/* Phase W-4b Calendar Step 3 — drafted-event review
                       queue per §3.26.16.18. State-change-generated
                       events with status="tentative" surface here for
                       explicit Send (commit + iTIP REQUEST) or Cancel
                       (iTIP CANCEL) per drafted-not-auto-sent discipline. */}
                    <Route
                      path="/settings/calendar/drafts"
                      element={<CalendarDraftsPage />}
                    />
                    {/* Phase W-4b Calendar Step 4.1 — PTR consent upgrade
                       UI write-side per §3.26.16.6 + §3.26.16.14 +
                       §3.26.11.10 cross-tenant Focus consent precedent.
                       Bilateral consent state machine; either tenant can
                       unilaterally revoke. */}
                    <Route
                      path="/settings/calendar/freebusy-consent"
                      element={<CalendarConsentPage />}
                    />
                  </Route>

                  {/* Phase W-4b Layer 1 Step 4a — unified email inbox.
                     Per canon §3.26.15.9 three canonical entry paths:
                     direct nav (this route), Cmd+K summon (Step 5+),
                     Communications-Layer Pulse drill-down (Step 5+).
                     Tenant-scoped via current_user; per-account access
                     enforced server-side via EmailAccountAccess. */}
                  <Route path="inbox" element={<InboxPage />} />

                  {/* Phase W-4b Layer 1 Calendar Step 5 — native event
                     detail page (§14.10.3). Surfaced from Pulse calendar_
                     glance, calendar_summary, V-1c CRM activity feed,
                     and V-1d in-app notifications. View-only with
                     attendee response + send/cancel actions; full edit
                     + reschedule wizards live on the calendar workspace. */}
                  <Route
                    path="/calendar/events/:eventId"
                    element={<EventDetailPage />}
                  />

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
                  <Route path="urns/catalog" element={<UrnSalesCatalog />} />
                  <Route path="urns/orders" element={<UrnOrdersPage />} />
                  <Route path="urns/orders/new" element={<UrnOrderForm />} />
                  <Route path="urns/proof-review/:orderId" element={<ProofReviewPage />} />

                  {/* Resale hub — aliases urn pages + stub inventory */}
                  <Route path="resale" element={<ResaleHub />} />
                  <Route path="resale/catalog" element={<UrnSalesCatalog />} />
                  <Route path="resale/orders" element={<UrnOrdersPage />} />
                  <Route path="resale/inventory" element={<ResaleInventory />} />

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
                    <Route path="order-station" element={<OrderStation />} />
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
                      path="/quoting"
                      element={<QuotingHubPage />}
                    />
                    <Route
                      path="/quoting/:id"
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
                    <Route path="transfers" element={<TransfersPage />} />
                    <Route
                      path="/ap/bills/:id"
                      element={<VendorBillDetailPage />}
                    />
                    <Route
                      path="/ap/received/:id"
                      element={<ReceivedStatementDetail />}
                    />
                    <Route path="alerts" element={<AlertsPage />} />
                    <Route path="journal-entries" element={<JournalEntriesPage />} />
                    <Route path="settings/tax" element={<TaxSettingsPage />} />
                    <Route path="reports" element={<ReportsPage />} />
                    <Route path="social-service-certificates" element={<SocialServiceCertificatesPage />} />
                    <Route path="financials/board" element={<FinancialsBoardPage />} />
                    <Route path="agents" element={<AgentDashboard />} />
                    <Route path="agents/:jobId/review" element={<ApprovalReview />} />
                    <Route path="ar/collections/:sequenceId/review" element={<CollectionsReviewPage />} />
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
                    <Route path="bom" element={<BOMListPage />} />
                    <Route path="bom/:bomId" element={<BOMDetailPage />} />
                  </Route>

                  {/* Project Management — requires project_management module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="projects.view" requiredModule="project_management" />
                    }
                  >
                    <Route path="projects" element={<ProjectListPage />} />
                    <Route path="projects/:projectId" element={<ProjectDetailPage />} />
                  </Route>

                  {/* Quality Control — requires inventory module + qc.view permission */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="qc.view" requiredModule="inventory" />
                    }
                  >
                    <Route path="qc" element={<QCDashboardPage />} />
                    <Route path="qc/inspections/:inspectionId" element={<QCInspectionDetailPage />} />
                    <Route path="qc/mobile/:inspectionId" element={<QCMobilePage />} />
                  </Route>

                  {/* Training hub — accessible to all, tiles gated individually */}
                  <Route path="training" element={<TrainingHubPage />} />

                  {/* Safety Management — requires safety_management module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="safety.view" requiredModule="safety_management" />
                    }
                  >
                    {/* Training */}
                    <Route path="training/vault-order-lifecycle" element={<VaultOrderLifecyclePage />} />
                    <Route path="legacy/proof/:orderId" element={<LegacyProofReviewPage />} />
                    <Route path="legacy/generator" element={<ProofGeneratorPage />} />
                    <Route path="legacy/settings" element={<LegacySettingsPage />} />
                    <Route path="legacy/templates/upload" element={<TemplateUploadPage />} />
                    <Route path="legacy/library" element={<LegacyLibraryPage />} />
                    <Route path="legacy/library/:legacyId" element={<LegacyDetailPage />} />
                    <Route path="training/procedures" element={<ProcedureLibraryPage />} />
                    <Route path="training/procedures/:key" element={<ProcedureDetailPage />} />
                    {/* Safety */}
                    <Route path="safety" element={<SafetyDashboardPage />} />
                    <Route path="safety/programs" element={<SafetyProgramsPage />} />
                    <Route path="safety/training" element={<SafetyTrainingPage />} />
                    <Route path="safety/inspections/new" element={<SafetyInspectPage />} />
                    <Route path="safety/inspect/:inspectionId" element={<SafetyInspectPage />} />
                    <Route path="safety/incidents" element={<SafetyIncidentPage />} />
                    <Route path="safety/incidents/new" element={<SafetyIncidentPage />} />
                    <Route path="safety/chemicals" element={<SafetyChemicalsPage />} />
                    <Route path="safety/loto" element={<SafetyLOTOPage />} />
                    <Route path="safety/notices" element={<SafetyNoticesPage />} />
                    <Route path="safety/training/calendar" element={<SafetyTrainingCalendarPage />} />
                    <Route path="safety/training/:scheduleId/post" element={<SafetyTrainingPostPage />} />
                    <Route path="safety/toolbox-talks" element={<SafetyToolboxTalksPage />} />
                    <Route path="safety/training/documents" element={<SafetyTrainingDocumentsPage />} />
                    <Route path="safety/osha-300" element={<SafetyOSHA300Page />} />
                    <Route path="safety/osha-300/year-end/:year" element={<SafetyOSHA300YearEndPage />} />
                  </Route>

                  {/* NPCA Audit Prep — requires npca_audit_prep extension */}
                  <Route
                    element={
                      <ProtectedRoute requiredModule="npca_audit_prep" />
                    }
                  >
                    <Route path="npca" element={<NpcaAuditPrepPage />} />
                  </Route>

                  {/* Production Log — requires daily_production_log module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="production_log.view" requiredModule="daily_production_log" />
                    }
                  >
                    <Route path="production-log" element={<ProductionLog />} />
                    <Route path="production-log/summary" element={<ProductionLogSummary />} />
                    <Route path="spring-burials" element={<SpringBurialList />} />
                  </Route>

                  {/* Work Orders & Production — requires work_orders module */}
                  <Route element={<ProtectedRoute requiredPermission="work_orders.view" requiredModule="work_orders" />}>
                    {/* Phase 2 UI Arc — /production is now the saved-
                        views-composed dashboard. Legacy bespoke board
                        preserved at /production/legacy for one release
                        while Playwright parity is verified. */}
                    <Route path="production" element={<ProductionBoardDashboard />} />
                    <Route path="production/legacy" element={<ProductionBoardPage />} />
                    <Route path="production/pour-events/new" element={<PourEventCreatePage />} />
                    <Route path="work-orders/:id" element={<WorkOrderDetailPage />} />
                  </Route>

                  {/* Delivery & Logistics — requires driver_delivery module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="delivery.view" requiredModule="driver_delivery" />
                    }
                  >
                    <Route path="scheduling" element={<SchedulingBoardPage />} />
                    <Route path="delivery/dispatch" element={<Navigate to="/scheduling" replace />} />
                    <Route path="delivery/funeral-scheduling" element={<Navigate to="/scheduling" replace />} />
                    <Route path="delivery/operations" element={<OperationsPage />} />
                    <Route path="delivery/history" element={<HistoryPage />} />
                    <Route path="delivery/deliveries/:id" element={<DeliveryDetailPage />} />
                    <Route path="delivery/routes/:id" element={<RouteDetailPage />} />
                    <Route path="delivery/settings" element={<DeliverySettingsPage />} />
                    <Route path="admin/announcements" element={<Navigate to="/announcements" replace />} />
                    <Route path="settings/driver-portal-preview" element={<DriverPortalPreviewPage />} />
                    <Route path="admin/driver-portal-preview" element={<Navigate to="/settings/driver-portal-preview" replace />} />
                  </Route>
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="carriers.view" requiredModule="driver_delivery" />
                    }
                  >
                    <Route path="delivery/carriers" element={<CarriersPage />} />
                  </Route>

                  {/* Funeral Home — requires funeral_home module */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="fh_cases.view" requiredModule="funeral_home" />
                    }
                  >
                    <Route path="cases" element={<FHCaseListPage />} />
                    <Route path="cases/new" element={<FHFirstCallPage />} />
                    <Route path="cases/:id" element={<FHCaseDetailPage />} />
                    <Route path="funeral-home/dashboard" element={<FHDashboardPage />} />
                    <Route path="funeral-home/compliance" element={<FHCompliancePage />} />
                    <Route path="funeral-home/price-list" element={<FHPriceListPage />} />
                  </Route>

                  {/* Disinterment Management — requires disinterment_management extension */}
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="disinterments.view" requiredExtension="disinterment_management" />
                    }
                  >
                    <Route path="disinterments" element={<DisintermentListPage />} />
                    <Route path="disinterments/:id" element={<DisintermentDetailPage />} />
                  </Route>
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="disinterment_settings.manage" requiredExtension="disinterment_management" />
                    }
                  >
                    <Route path="settings/disinterment" element={<DisintermentSettingsPage />} />
                  </Route>
                  <Route
                    element={
                      <ProtectedRoute requiredPermission="union_rotations.view" requiredExtension="disinterment_management" />
                    }
                  >
                    <Route path="settings/union-rotations" element={<UnionRotationsPage />} />
                  </Route>

                  {/* Call Log — any authenticated user */}
                  <Route path="calls" element={<CallLogPage />} />

                  {/* Knowledge Base — any authenticated user */}
                  <Route path="knowledge-base" element={<KnowledgeBasePage />} />

                  {/* Price Management */}
                  <Route path="price-management" element={<PriceManagementPage />} />
                  <Route path="price-management/templates" element={<PriceManagementTemplatesPage />} />
                  <Route path="price-management/email-settings" element={<PriceManagementEmailSettingsPage />} />
                  <Route path="price-management/send" element={<PriceManagementSendPage />} />

                  {/* Announcements — any authenticated user */}
                  <Route path="announcements" element={<AnnouncementsPage />} />

                  {/* Onboarding — any authenticated user.
                      /onboarding now renders the new step-by-step flow
                      (identity, locations, programs, compliance, team,
                      network, command_bar — 7 essential steps, +import
                      when the tenant has no orders). The legacy hub with
                      the 12 must_complete items stays available at
                      /onboarding/hub for tenants whose data hasn't been
                      migrated to the new checklist yet. */}
                  <Route path="onboarding" element={<OnboardingFlow />} />
                  <Route path="onboarding/flow" element={<OnboardingFlow />} />
                  {/* Phase W-4a — operator onboarding (work_areas + responsibilities) */}
                  <Route
                    path="/onboarding/operator-profile"
                    element={<OperatorOnboardingFlow />}
                  />
                  <Route path="onboarding/hub" element={<OnboardingHub />} />
                  <Route path="onboarding/import-matching" element={<ImportMatchingPage />} />
                  <Route path="onboarding/integrations/:type" element={<IntegrationSetupPage />} />
                  <Route path="onboarding/product-library" element={<ProductLibraryPage />} />
                  <Route path="onboarding/import/:type" element={<ImportWizardPage />} />
                  <Route path="onboarding/scenarios/:scenarioKey" element={<ScenarioPlayerPage />} />
                  <Route path="onboarding/website-review" element={<WebsiteSuggestionsReview />} />
                  <Route path="onboarding/catalog-builder" element={<CatalogBuilder />} />
                  <Route path="onboarding/team" element={<TeamSetupPage />} />
                  <Route path="onboarding/team-intelligence" element={<TeamIntelligencePage />} />
                  <Route path="onboarding/safety-training" element={<SafetyTrainingSetupPage />} />
                  <Route path="onboarding/tax-jurisdictions" element={<TaxJurisdictionsOnboarding />} />
                  <Route path="onboarding/charges" element={<ChargeSetupPage />} />
                  <Route path="onboarding/charge-terms" element={<ChargeTermsOnboardingPage />} />
                  <Route path="onboarding/customers/funeral-homes" element={<FuneralHomeCustomersWizard />} />
                  <Route path="onboarding/cemeteries" element={<CemeterySetupWizard />} />
                  <Route path="onboarding/quick-orders" element={<QuickOrdersOnboarding />} />
                  <Route path="onboarding/historical-orders" element={<HistoricalOrderImportPage />} />
                  <Route path="onboarding/import" element={<UnifiedImportPage />} />
                  <Route path="onboarding/branding" element={<CompanyBrandingPage />} />
                  <Route path="settings/seasonal-templates" element={<SeasonalTemplatesSettings />} />
                  <Route path="onboarding/accounting" element={<AccountingSetupPage />} />
                  <Route path="onboarding/data-migration" element={<DataMigrationPage />} />
                  <Route path="settings/data-migration" element={<DataMigrationPage />} />
                  <Route path="settings/data/customer-types" element={<CustomerTypesPage />} />
                  <Route path="settings/cemeteries/:cemeteryId" element={<CemeteryProfilePage />} />
                  <Route path="settings/cemeteries" element={<CemeteryDeliverySettingsPage />} />
                  <Route path="onboarding/accounting/review" element={<AccountingReviewPage />} />
                  <Route path="onboarding/scheduling" element={<SchedulingSetupPage />} />
                  <Route path="onboarding/network-preferences" element={<NetworkPreferencesPage />} />
                  <Route path="onboarding/vault-setup" element={<VaultSetupPage />} />
                  <Route path="onboarding/vault-molds" element={<VaultMoldSetupPage />} />
                  <Route path="settings/team-intelligence" element={<TeamIntelligencePage />} />
                  <Route path="settings/charges" element={<ChargeSetupPage />} />
                  <Route path="settings/invoice" element={<InvoiceSettingsPage />} />
                  <Route path="settings/vault-supplier" element={<VaultSupplierSettingsPage />} />
                  <Route path="settings/vault-molds" element={<VaultMoldSettingsPage />} />
                  <Route path="settings/network/preferences" element={<NetworkPreferencesSettingsPage />} />
                  <Route path="settings/scheduling" element={<SchedulingSettingsPage />} />
                  <Route path="settings/call-intelligence" element={<CallIntelligenceSettingsPage />} />
                  <Route path="settings/programs" element={<ProgramsSettingsPage />} />
                  <Route path="settings/compliance" element={<ComplianceConfigPage />} />
                  <Route path="settings/integrations/accounting" element={<SyncHealthDashboardPage />} />

                  {/* Locations — admin only */}
                  <Route
                    element={<ProtectedRoute adminOnly />}
                  >
                    <Route path="locations" element={<LocationsOverview />} />
                    <Route path="settings/locations" element={<LocationSettings />} />
                  </Route>

                  {/* Extension Catalog — any authenticated user */}
                  <Route path="extensions" element={<ExtensionCatalogPage />} />
                  <Route path="extensions/installed" element={<ExtensionInstalledPage />} />

                  {/* Notifications — V-1d promoted to full Vault
                      service; the canonical path is now
                      /vault/notifications. /notifications redirects
                      for backward compat (existing email links,
                      bookmarks, widget click-throughs from before
                      V-1d). */}
                  <Route
                    path="/notifications"
                    element={<Navigate to="/vault/notifications" replace />}
                  />
                  <Route
                    path="/vault/notifications"
                    element={<NotificationsPage />}
                  />

                  {/* My Profile — any authenticated user */}
                  <Route path="profile" element={<MyProfile />} />

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
                    <Route
                      path="/settings/workflows/new"
                      element={<WorkflowBuilderPage />}
                    />
                    <Route
                      path="/settings/workflows/:workflowId/edit"
                      element={<WorkflowBuilderPage />}
                    />
                    <Route
                      path="/settings/workflows/:workflowId/view"
                      element={<WorkflowBuilderPage />}
                    />
                    {/* Funeral Home vertical (FH-1a + FH-1b) */}
                    <Route path="fh" element={<FhDirectionHub />} />
                    <Route path="fh/cases" element={<FhCaseList />} />
                    <Route path="fh/cases/:caseId" element={<FhCaseDashboard />} />
                    <Route path="fh/cases/:caseId/arrangement" element={<FhArrangementConference />} />
                    <Route path="fh/cases/:caseId/vital-statistics" element={<FhVitalStatistics />} />
                    <Route path="fh/cases/:caseId/story" element={<FhStoryStep />} />
                    <Route path="fh/cases/:caseId/cemetery" element={<FhCemeteryStep />} />
                    <Route path="fh/settings/network" element={<FhNetworkSettings />} />
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

                  {/* Admin Visual Editor (Phase 1-4) routes RELOCATED
                      (May 2026) to BridgeableAdminApp at
                      /bridgeable-admin/visual-editor/* (or via the
                      admin.* subdomain at /visual-editor/*). They are
                      gated by PlatformUser auth — not tenant admin
                      auth. The lib/visual-editor/registry side-effect
                      import remains at the top of this file because
                      registry registrations populate at module load
                      regardless of which tree consumes them (future
                      tenant Workshop UI will read from the same
                      registry). */}

                  {/* ── Phase V-1a/b/c: Bridgeable Vault Hub ──
                      VaultHubLayout wraps every /vault/* child route.
                      Per-subtree gating: Documents + Intelligence are
                      admin-only (platform infrastructure), CRM uses
                      the existing `customers.view` permission. The
                      Overview (index) is open to any authenticated
                      tenant user — it renders only the widgets whose
                      service they have access to (backend enforces). */}
                  <Route path="vault" element={<VaultHubLayout />}>
                    <Route index element={<VaultOverview />} />

                    {/* Documents — admin-only */}
                    <Route element={<ProtectedRoute adminOnly />}>
                      <Route path="documents">
                        <Route index element={<DocumentLog />} />
                        <Route
                          path="templates"
                          element={<DocumentTemplateLibrary />}
                        />
                        <Route
                          path="templates/:templateId"
                          element={<DocumentTemplateDetail />}
                        />
                        <Route path="inbox" element={<DocumentInbox />} />
                        <Route
                          path="deliveries"
                          element={<DeliveryLog />}
                        />
                        <Route
                          path="deliveries/:deliveryId"
                          element={<DeliveryDetail />}
                        />
                        <Route path="signing">
                          <Route
                            index
                            element={<SigningEnvelopeLibrary />}
                          />
                          <Route
                            path="new"
                            element={<CreateEnvelopeWizard />}
                          />
                          <Route
                            path=":envelopeId"
                            element={<SigningEnvelopeDetail />}
                          />
                        </Route>
                        {/* :documentId MUST be last under /documents so
                            it doesn't shadow /documents/templates,
                            /documents/inbox, etc. */}
                        <Route
                          path=":documentId"
                          element={<DocumentDetail />}
                        />
                      </Route>

                      {/* Intelligence — admin-only */}
                      <Route path="intelligence">
                        <Route
                          index
                          element={<IntelligencePromptLibrary />}
                        />
                        <Route
                          path="prompts"
                          element={<IntelligencePromptLibrary />}
                        />
                        <Route
                          path="prompts/:promptId"
                          element={<IntelligencePromptDetail />}
                        />
                        <Route
                          path="executions"
                          element={<IntelligenceExecutionLog />}
                        />
                        <Route
                          path="executions/:executionId"
                          element={<IntelligenceExecutionDetail />}
                        />
                        <Route
                          path="model-routes"
                          element={<IntelligenceModelRoutes />}
                        />
                        <Route
                          path="experiments"
                          element={<IntelligenceExperimentLibrary />}
                        />
                        <Route
                          path="experiments/new"
                          element={<IntelligenceCreateExperiment />}
                        />
                        <Route
                          path="experiments/:experimentId"
                          element={<IntelligenceExperimentDetail />}
                        />
                      </Route>
                    </Route>

                    {/* CRM — V-1c lift-and-shift. Permission-gated
                        on customers.view (same gate the pre-V-1c
                        /crm top-level nav entry used). */}
                    <Route
                      element={
                        <ProtectedRoute requiredPermission="customers.view" />
                      }
                    >
                      <Route path="crm">
                        <Route index element={<CRMHub />} />
                        {/* Phase 4 — Tab-fallback target for the NL
                            contact overlay. Accessible via the
                            Phase 1 `create.contact` command-bar
                            action URL `/vault/crm/contacts/new`. */}
                        <Route
                          path="contacts/new"
                          element={<NewContactPage />}
                        />
                        <Route
                          path="companies"
                          element={<CompaniesListPage />}
                        />
                        <Route
                          path="companies/duplicates"
                          element={<DuplicateReviewPage />}
                        />
                        <Route
                          path="companies/:id"
                          element={<CompanyDetailPage />}
                        />
                        <Route
                          path="pipeline"
                          element={<PipelinePage />}
                        />
                        <Route
                          path="funeral-homes"
                          element={<FuneralHomesPage />}
                        />
                        <Route
                          path="contractors"
                          element={<ContractorsPage />}
                        />
                        <Route
                          path="duplicates"
                          element={<DuplicateReviewPage />}
                        />
                        <Route
                          path="billing-groups"
                          element={<BillingGroupsPage />}
                        />
                        <Route
                          path="billing-groups/:id"
                          element={<BillingGroupDetailPage />}
                        />
                        <Route
                          path="settings"
                          element={<CrmSettingsPage />}
                        />
                      </Route>
                    </Route>

                    {/* V-1e: Accounting admin consolidation. Admin-only
                        at the sub-tree root — same gate the backend
                        uses on every endpoint under
                        /api/v1/vault/accounting/*. Tenant-facing
                        Financials Hub (invoices/AR/AP/JEs) stays in
                        the vertical nav, NOT here. */}
                    <Route element={<ProtectedRoute adminOnly />}>
                      <Route
                        path="accounting"
                        element={<AccountingAdminLayout />}
                      >
                        <Route
                          index
                          element={<Navigate to="periods" replace />}
                        />
                        <Route
                          path="periods"
                          element={<AccountingPeriodsTab />}
                        />
                        <Route
                          path="agents"
                          element={<AccountingAgentsTab />}
                        />
                        <Route
                          path="classification"
                          element={<AccountingClassificationTab />}
                        />
                        <Route path="tax" element={<AccountingTaxTab />} />
                        <Route
                          path="statements"
                          element={<AccountingStatementsTab />}
                        />
                        <Route path="coa" element={<AccountingCoaTab />} />
                      </Route>
                    </Route>
                  </Route>

                  {/* ── Pre-V-1a compatibility redirects ──
                      Old /admin/documents/* and /admin/intelligence/*
                      paths redirect to /vault/*. One-release grace
                      period; remove after that. */}
                  <Route
                    path="/admin/documents"
                    element={<Navigate to="/vault/documents" replace />}
                  />
                  <Route
                    path="/admin/documents/templates"
                    element={
                      <Navigate to="/vault/documents/templates" replace />
                    }
                  />
                  <Route
                    path="/admin/documents/templates/:templateId"
                    element={<RedirectPreserveParam toPrefix="/vault/documents/templates" />}
                  />
                  <Route
                    path="/admin/documents/documents"
                    element={<Navigate to="/vault/documents" replace />}
                  />
                  <Route
                    path="/admin/documents/documents/:documentId"
                    element={<RedirectPreserveParam toPrefix="/vault/documents" />}
                  />
                  <Route
                    path="/admin/documents/inbox"
                    element={<Navigate to="/vault/documents/inbox" replace />}
                  />
                  <Route
                    path="/admin/documents/deliveries"
                    element={
                      <Navigate to="/vault/documents/deliveries" replace />
                    }
                  />
                  <Route
                    path="/admin/documents/deliveries/:deliveryId"
                    element={<RedirectPreserveParam toPrefix="/vault/documents/deliveries" />}
                  />
                  <Route
                    path="/admin/documents/signing/envelopes"
                    element={
                      <Navigate to="/vault/documents/signing" replace />
                    }
                  />
                  <Route
                    path="/admin/documents/signing/envelopes/new"
                    element={
                      <Navigate to="/vault/documents/signing/new" replace />
                    }
                  />
                  <Route
                    path="/admin/documents/signing/envelopes/:envelopeId"
                    element={<RedirectPreserveParam toPrefix="/vault/documents/signing" />}
                  />

                  <Route
                    path="/admin/intelligence"
                    element={<Navigate to="/vault/intelligence" replace />}
                  />
                  <Route
                    path="/admin/intelligence/prompts"
                    element={
                      <Navigate to="/vault/intelligence/prompts" replace />
                    }
                  />
                  <Route
                    path="/admin/intelligence/prompts/:promptId"
                    element={<RedirectPreserveParam toPrefix="/vault/intelligence/prompts" />}
                  />
                  <Route
                    path="/admin/intelligence/executions"
                    element={
                      <Navigate
                        to="/vault/intelligence/executions"
                        replace
                      />
                    }
                  />
                  <Route
                    path="/admin/intelligence/executions/:executionId"
                    element={<RedirectPreserveParam toPrefix="/vault/intelligence/executions" />}
                  />
                  <Route
                    path="/admin/intelligence/model-routes"
                    element={
                      <Navigate
                        to="/vault/intelligence/model-routes"
                        replace
                      />
                    }
                  />
                  <Route
                    path="/admin/intelligence/experiments"
                    element={
                      <Navigate
                        to="/vault/intelligence/experiments"
                        replace
                      />
                    }
                  />
                  <Route
                    path="/admin/intelligence/experiments/new"
                    element={
                      <Navigate
                        to="/vault/intelligence/experiments/new"
                        replace
                      />
                    }
                  />
                  <Route
                    path="/admin/intelligence/experiments/:experimentId"
                    element={<RedirectPreserveParam toPrefix="/vault/intelligence/experiments" />}
                  />

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
                  <Route path="driver" element={<DriverConsolePage />} />
                  <Route path="driver/home" element={<DriverHomePage />} />
                  <Route path="driver/route" element={<DriverRoutePage />} />
                  <Route path="driver/stops/:stopId" element={<StopDetailPage />} />
                  <Route path="driver/mileage" element={<MileagePage />} />
                </Route>
              </Route>

              {/* Console — production/delivery employees */}
              <Route element={<ProtectedRoute />}>
                <Route element={<ConsoleLayout />}>
                  <Route path="console" element={<ConsoleSelectPage />} />
                  <Route path="console/delivery" element={<DeliveryConsolePage />} />
                  <Route path="console/operations" element={<OperationsBoardPage />} />
                  <Route path="console/production" element={<ProductionConsolePage />} />
                  <Route path="console/operations/product-entry" element={<LogProductionPage />} />
                  <Route path="console/operations/incident" element={<SafetyLogPage />} />
                  <Route path="console/operations/observation" element={<SafetyLogPage />} />
                  <Route path="console/operations/qc" element={<QCCheckPage />} />
                  <Route path="console/operations/receive" element={<ReceiveDeliveryPage />} />
                  <Route path="console/operations/receive/:poId" element={<ReceiveDeliveryPage />} />
                  <Route path="console/operations/end-of-day" element={<EndOfDayPage />} />
                  <Route path="console/operations/inspection" element={<EquipmentInspectionPage />} />
                </Route>
              </Route>

              {/* Carrier portal — authenticated, minimal UI */}
              <Route element={<ProtectedRoute />}>
                <Route path="carrier/deliveries" element={<CarrierDeliveriesPage />} />
              </Route>

              {/* Mobile production log — standalone, no sidebar */}
              <Route element={<ProtectedRoute />}>
                <Route path="m/production-log" element={<MobileProductionLog />} />
              </Route>

              {/* Public intake form — no auth required */}
              <Route path="intake/disinterment/:token" element={<DisintermentIntakePage />} />

              {/* FH proof approval — public, token-validated */}
              <Route path="proof-approval/:token" element={<FHApprovalPage />} />

              {/* Native signing signer-facing page — public, token-validated (Phase D-4) */}
              <Route path="sign/:token" element={<SignerLandingPage />} />

              {/* Email operational-action magic-link surface — public, token-
                  authenticated kill-the-portal contextual surface per
                  §3.26.15.17 + §14.9.5 (Phase W-4b Layer 1 Step 4c). */}
              <Route path="email/actions/:token" element={<MagicLinkActionPage />} />

              {/* Calendar operational-action magic-link surface — public, token-
                  authenticated kill-the-portal contextual surface per
                  §3.26.16.17 + §14.10.5 (Phase W-4b Layer 1 Step 4). */}
              <Route path="calendar/actions/:token" element={<CalendarMagicLinkActionPage />} />

              {/* Family portal — no auth required, standalone page */}
              <Route path="portal/:token" element={<FHPortalPage />} />

              {/* Platform admin entry (for non-subdomain setups) */}
              <Route path="platform-admin" element={<PlatformAdminEntry />} />

              {/* Root redirect — R-1.6.9 parameterized.
               *
               *  Production tenant operator flow (default): RootRedirect
               *  dispatches role-based landing (driver → /driver,
               *  production → /console, else → /home). Catch-all renders
               *  NotFound for unmatched URLs — surfaces a 404 page so
               *  invalid tenant URLs are visible.
               *
               *  Runtime editor flow (excludeRootRedirect=true): both `/`
               *  and `*` mount HomePage directly. Skips the
               *  `<Navigate to="/home" replace />` inside RootRedirect,
               *  which would have absolute-navigated out of the
               *  `/runtime-editor/*` parent route and bounced the user
               *  to `admin.<domain>/home`. Catch-all also renders
               *  HomePage so the runtime editor never falls through to
               *  a 404 — under impersonation we always show tenant-shaped
               *  content.
               *
               *  See /tmp/picker_navigation_bug.md for the originating
               *  investigation. */}
              {excludeRootRedirect ? (
                <>
                  <Route index element={<HomePage />} />
                  <Route path="*" element={<HomePage />} />
                </>
              ) : (
                <>
                  <Route index element={<RootRedirect />} />
                  <Route path="*" element={<NotFound />} />
                </>
              )}
    </>
  );
}
