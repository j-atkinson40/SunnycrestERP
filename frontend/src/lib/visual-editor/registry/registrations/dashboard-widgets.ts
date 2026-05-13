/**
 * Registry registrations — dashboard ops-board widgets (Arc 4a.2a).
 *
 * Path 1 wrap for the 17 ops-board widgets that have concrete React
 * components today. Mirrors `./widgets.ts` structure verbatim — each
 * registration is a `registerComponent({...})(RawWidget)` call whose
 * return value (the wrapped component carrying the
 * `data-component-name` boundary div from the HOC at
 * `register.ts:185`) is exported so the OPS_BOARD_WIDGETS componentMap
 * at `components/widgets/ops-board/index.ts` consumes the wrapped
 * version.
 *
 * Pre-Arc-4a.2a these 17 widgets rendered on the manufacturing
 * operations-board-desktop page (and home dashboard via shared
 * componentMap consumers) WITHOUT the `data-component-name` boundary
 * div. The runtime editor's SelectionOverlay walks up the DOM to
 * find the nearest registered component; without the boundary, clicks
 * on these widgets resolved past them. Post-Arc-4a.2a they are
 * inspector-clickable like every other Path 1 widget.
 *
 * Why a separate shim file from `./widgets.ts`:
 *   • `./widgets.ts` owns the Pulse-eligible foundation + manufacturing
 *     cluster (14 widgets — Phase 1 + Phase 3 + Arc 1 lifts).
 *   • This file owns the dashboard-only ops-board cluster (17 widgets).
 *   • Both files are imported at app bootstrap via auto-register.ts.
 *   • Surface separation matches the dispatch substrate asymmetry:
 *     dashboards dispatch via WidgetGrid componentMap; Pulse dispatches
 *     via getWidgetRenderer (canvas registry). See
 *     `widget-renderer-parity.test.ts:18-24` for the canon.
 *
 * `supported_surfaces` backfill per B-4a2-4: every dashboard widget
 * declares `["dashboard_grid"]` in the backend WIDGET_DEFINITIONS
 * (Arc 4a.2a Part 1). No `pulse_grid` additions this arc — Pulse
 * promotion is a downstream decision when concrete signal warrants
 * (per B-4a2-4 settled scope).
 *
 * B-4a2-3 ≥3 configurableProps discipline: each widget declares ≥3
 * honest configurable props with type / default / bounds /
 * displayLabel / description. Bounds reflect realistic operator-meaning
 * ranges (item counts, refresh intervals, threshold values, density
 * tiers). No synthetic props.
 *
 * `consumedTokens` audit: tokens declared per widget reflect the
 * widget's render path through WidgetWrapper (which migrated to
 * DESIGN_LANGUAGE tokens at Aesthetic Arc Phase II Batch 1a per
 * `WidgetWrapper.tsx:1-7`). Widget bodies in this cluster still
 * predominantly consume legacy raw Tailwind palette (`bg-gray-100`,
 * `text-blue-600`, etc.) — that's drift flagged in the build report,
 * NOT canonical token consumption. Tokens listed below are what the
 * widget legitimately consumes via WidgetWrapper chrome + the few
 * spots where the widget body uses canonical DESIGN_LANGUAGE tokens
 * (e.g. status tokens via newer code paths).
 *
 * Cast pattern at consumer: every wrapped export needs
 * `as unknown as ComponentType<WidgetProps>` at the consumer
 * (componentMap site) per the existing R-1.6.12 / Arc 1 convention
 * (see `components/widgets/foundation/register.ts:54-60`).
 *
 * NOT wrapped this arc (surfaced in Arc 4a.2a build report):
 *   • revenue_summary — backend WIDGET_DEFINITIONS entry exists; NO
 *     frontend component exists today. Wrapping is impossible until
 *     the component is built. Documented as a finding; not blocking.
 *   • ar_summary — same shape as revenue_summary; no frontend
 *     component today.
 *   • All 9 vault widgets — deferred to Arc 4a.2b. Vault has its own
 *     componentMap indirection via vaultHubRegistry.
 */

import type { ComponentType } from "react"

// Raw widget imports (default exports — all 17 ops-board widgets
// export their component as `default`, not named).
import TodaysServicesWidgetRaw from "@/components/widgets/ops-board/TodaysServicesWidget"
import LegacyQueueWidgetRaw from "@/components/widgets/ops-board/LegacyQueueWidget"
import DriverStatusWidgetRaw from "@/components/widgets/ops-board/DriverStatusWidget"
import ProductionStatusWidgetRaw from "@/components/widgets/ops-board/ProductionStatusWidget"
import OpenOrdersWidgetRaw from "@/components/widgets/ops-board/OpenOrdersWidget"
import InventoryWidgetRaw from "@/components/widgets/ops-board/InventoryWidget"
import BriefingSummaryWidgetRaw from "@/components/widgets/ops-board/BriefingSummaryWidget"
import ActivityFeedWidgetRaw from "@/components/widgets/ops-board/ActivityFeedWidget"
import AtRiskAccountsWidgetRaw from "@/components/widgets/ops-board/AtRiskAccountsWidget"
import QCStatusWidgetRaw from "@/components/widgets/ops-board/QCStatusWidget"
import TimeClockWidgetRaw from "@/components/widgets/ops-board/TimeClockWidget"
import SafetyWidgetRaw from "@/components/widgets/ops-board/SafetyWidget"
import ComplianceUpcomingWidgetRaw from "@/components/widgets/ops-board/ComplianceUpcomingWidget"
import TeamCertificationsWidgetRaw from "@/components/widgets/ops-board/TeamCertificationsWidget"
import MyCertificationsWidgetRaw from "@/components/widgets/ops-board/MyCertificationsWidget"
import MyTrainingWidgetRaw from "@/components/widgets/ops-board/MyTrainingWidget"
import KbRecentWidgetRaw from "@/components/widgets/ops-board/KbRecentWidget"

import { registerComponent } from "../register"


// Tokens consumed by every widget via WidgetWrapper chrome. Pulled
// out as a shared constant so each registration declares the same
// chrome consumers without duplication. Widget-specific tokens
// (status colors, accent variants, etc.) added per-widget below.
const WIDGET_WRAPPER_TOKENS = [
  "surface-elevated",
  "border-subtle",
  "shadow-level-1",
  "radius-base",
  "content-strong",
  "content-base",
  "content-muted",
  "text-body-sm",
  "text-caption",
] as const


// ─── todays_services (manufacturing-leaning ops-board) ───────────
export const TodaysServicesWidget = registerComponent({
  type: "widget",
  name: "todays_services",
  displayName: "Today's Services",
  description:
    "Today's scheduled vault orders with status pills + cemetery info. Click-through to sales-order detail. Backed by /widget-data/orders/today; per-row chrome shows service time when present.",
  category: "manufacturing-operations",
  verticals: ["manufacturing"],
  userParadigms: ["owner-operator", "operator-power-user", "focused-executor"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS, "accent"],
  configurableProps: {
    maxOrdersShown: {
      type: "number",
      default: 10,
      bounds: [1, 50],
      displayLabel: "Max orders shown",
      description: "Cap on order rows rendered. Older orders scroll within the widget.",
    },
    showServiceTime: {
      type: "boolean",
      default: true,
      displayLabel: "Show service time",
      description: "Show formatted service time (e.g. '10:30 AM') alongside cemetery name.",
    },
    showStatusBadges: {
      type: "boolean",
      default: true,
      displayLabel: "Show status badges",
      description: "Show colored status pill for each order. When false, status is hidden.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches today's orders. Range: 1–60 minutes.",
    },
    emptyStateText: {
      type: "string",
      default: "No services scheduled for today",
      displayLabel: "Empty state text",
      description: "Shown when no orders are scheduled for today.",
      bounds: { maxLength: 80 },
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(TodaysServicesWidgetRaw)


// ─── legacy_queue (cross-vertical ops-board) ────────────────────
export const LegacyQueueWidget = registerComponent({
  type: "widget",
  name: "legacy_queue",
  displayName: "Legacy Proof Queue",
  description:
    "Funeral home proofs awaiting review or approval. Two counts (pending + approved-today) plus inline pending list. Click-through to legacy-studio detail per proof.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS, "status-success"],
  configurableProps: {
    maxPendingShown: {
      type: "number",
      default: 4,
      bounds: [1, 20],
      displayLabel: "Max pending shown",
      description: "Cap on pending proofs rendered in the inline list.",
    },
    showApprovedTodayCount: {
      type: "boolean",
      default: true,
      displayLabel: "Show approved-today count",
      description: "Show 'approved today' alongside pending count. When false, only pending count surfaces.",
    },
    showServiceDate: {
      type: "boolean",
      default: true,
      displayLabel: "Show service date",
      description: "Show formatted service date in each row's subtitle.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 1800],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches the proof queue. Range: 1–30 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(LegacyQueueWidgetRaw)


// ─── driver_status (cross-vertical ops-board) ───────────────────
export const DriverStatusWidget = registerComponent({
  type: "widget",
  name: "driver_status",
  displayName: "Driver Status",
  description:
    "Active drivers with current state (available / en_route / at_stop / off_duty), next stop, and phone link. Click-through to delivery operations.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    ...WIDGET_WRAPPER_TOKENS,
    "accent",
    "status-info",
    "status-warning",
    "status-success",
  ],
  configurableProps: {
    maxDriversShown: {
      type: "number",
      default: 8,
      bounds: [1, 30],
      displayLabel: "Max drivers shown",
      description: "Cap on driver rows rendered. Larger fleets scroll within the widget.",
    },
    showDriverAvatars: {
      type: "boolean",
      default: true,
      displayLabel: "Show driver avatars",
      description: "Show initials avatar circle in each row.",
    },
    showPhoneLink: {
      type: "boolean",
      default: true,
      displayLabel: "Show phone link",
      description: "Show clickable tel: link icon when driver has phone on file.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 120,
      bounds: [30, 600],
      displayLabel: "Refresh interval (seconds)",
      description: "More frequent refresh than other dashboard widgets — drivers move state often.",
    },
    showOffDuty: {
      type: "boolean",
      default: false,
      displayLabel: "Show off-duty drivers",
      description: "Include off-duty drivers in the list. When false, only active drivers render.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(DriverStatusWidgetRaw)


// ─── production_status (manufacturing ops-board) ────────────────
export const ProductionStatusWidget = registerComponent({
  type: "widget",
  name: "production_status",
  displayName: "Production Status",
  description:
    "Today's vault production progress: total units + target progress bar + per-product breakdown. Backed by /widget-data/production/daily-summary.",
  category: "manufacturing-operations",
  verticals: ["manufacturing"],
  userParadigms: ["owner-operator", "operator-power-user", "focused-executor"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS, "status-success", "surface-sunken"],
  configurableProps: {
    showProgressBar: {
      type: "boolean",
      default: true,
      displayLabel: "Show progress bar",
      description: "Show progress bar relative to target when target is set. Hidden when no target configured.",
    },
    maxProductsShown: {
      type: "number",
      default: 5,
      bounds: [1, 20],
      displayLabel: "Max products shown",
      description: "Cap on per-product breakdown rows.",
    },
    showTargetLabel: {
      type: "boolean",
      default: true,
      displayLabel: "Show target alongside total",
      description: "Show 'X / Y target' in header. When false, only total shows.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 1800],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches today's production summary. Range: 1–30 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(ProductionStatusWidgetRaw)


// ─── open_orders (cross-vertical ops-board) ─────────────────────
export const OpenOrdersWidget = registerComponent({
  type: "widget",
  name: "open_orders",
  displayName: "Open Orders",
  description:
    "Orders pending scheduling or fulfillment, broken down by status (unscheduled / scheduled / in_production). Click any row to navigate to filtered sales-orders list.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS, "accent"],
  configurableProps: {
    showTotalCount: {
      type: "boolean",
      default: true,
      displayLabel: "Show total count",
      description: "Show large 'total open' number at top of widget.",
    },
    statusBreakdownVisible: {
      type: "boolean",
      default: true,
      displayLabel: "Show status breakdown rows",
      description: "Show clickable rows for each status (unscheduled / scheduled / in_production).",
    },
    showFooterCTA: {
      type: "boolean",
      default: true,
      displayLabel: "Show 'View all' footer link",
      description: "Show footer link navigating to /sales-orders.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 1800],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches the open-orders summary. Range: 1–30 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(OpenOrdersWidgetRaw)


// ─── inventory_levels (manufacturing ops-board) ─────────────────
export const InventoryWidget = registerComponent({
  type: "widget",
  name: "inventory_levels",
  displayName: "Key Inventory",
  description:
    "Stock levels for key vault products with status indicators (ok / low / out). Read-only widget — full inventory management lives at the page level.",
  category: "manufacturing-operations",
  verticals: ["manufacturing"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    ...WIDGET_WRAPPER_TOKENS,
    "status-success",
    "status-warning",
    "status-error",
  ],
  configurableProps: {
    maxItemsShown: {
      type: "number",
      default: 8,
      bounds: [1, 30],
      displayLabel: "Max items shown",
      description: "Cap on inventory rows rendered.",
    },
    showStatusDots: {
      type: "boolean",
      default: true,
      displayLabel: "Show status dots",
      description: "Show colored status dot (green/amber/red) per row. When false, only quantities render.",
    },
    sortByStatus: {
      type: "boolean",
      default: false,
      displayLabel: "Sort by status (out → low → ok)",
      description: "When true, sort with out-of-stock items first, then low, then ok. Otherwise preserves server order.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 600,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description: "Inventory changes less frequently than other surfaces; default refresh is 10 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(InventoryWidgetRaw)


// ─── briefing_summary (cross-vertical ops-board) ────────────────
export const BriefingSummaryWidget = registerComponent({
  type: "widget",
  name: "briefing_summary",
  displayName: "Morning Briefing (Dashboard)",
  description:
    "Today's morning briefing narrative + action items count. Distinct from the foundation `briefing` widget (which renders Phase 6 per-user briefings on Pulse + sidebar); this widget is dashboard-only and surfaces the legacy briefing-of-the-day flow. Click 'View full briefing' to navigate to /dashboard.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS, "accent", "status-warning-muted", "status-warning"],
  configurableProps: {
    narrativeLineClamp: {
      type: "number",
      default: 4,
      bounds: [2, 12],
      displayLabel: "Narrative line clamp",
      description: "Maximum visible lines of narrative before truncation. Range: 2–12 lines.",
    },
    showActionItemsCount: {
      type: "boolean",
      default: true,
      displayLabel: "Show action items count",
      description: "Show 'N action items for today' pill when actions exist. When false, the pill is hidden.",
    },
    showViewFullLink: {
      type: "boolean",
      default: true,
      displayLabel: "Show 'View full briefing' footer link",
      description: "Show footer link to /dashboard. When false, no click-through is rendered.",
    },
    refreshOncePerSession: {
      type: "boolean",
      default: true,
      displayLabel: "Refresh once per session",
      description: "Default behavior — briefings are stable through the day. Set false to refresh on every focus event.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(BriefingSummaryWidgetRaw)


// ─── activity_feed (cross-vertical ops-board) ───────────────────
export const ActivityFeedWidget = registerComponent({
  type: "widget",
  name: "activity_feed",
  displayName: "Recent Activity (Dashboard)",
  description:
    "Recent platform activity feed: events list with user, action, entity, relative timestamp. Dashboard-only sibling of the `recent-activity` foundation widget (which renders on Pulse + sidebar). Backed by /widget-data/activity/recent.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS, "accent"],
  configurableProps: {
    maxEventsShown: {
      type: "number",
      default: 10,
      bounds: [3, 50],
      displayLabel: "Max events shown",
      description: "Cap on activity rows. The widget fetches the same count regardless to keep the API contract stable.",
    },
    showUserName: {
      type: "boolean",
      default: true,
      displayLabel: "Show user name",
      description: "Show actor name in each row's subtitle. When false, only event description + timestamp render.",
    },
    showRelativeTimestamps: {
      type: "boolean",
      default: true,
      displayLabel: "Show relative timestamps",
      description: "Show 'Nm ago' style. When false, absolute timestamps render.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 1800],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches activity. Range: 1–30 minutes.",
    },
    emptyStateText: {
      type: "string",
      default: "No recent activity",
      displayLabel: "Empty state text",
      description: "Shown when no activity events match the current filter.",
      bounds: { maxLength: 80 },
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(ActivityFeedWidgetRaw)


// ─── at_risk_accounts (cross-vertical ops-board + vault) ────────
//
// Surface NOTE: `at_risk_accounts` appears in TWO componentMaps —
// ops-board (canonical) AND vault (which re-exports the same
// component). Path 1 wrapping at the canonical site here suffices;
// vault's import re-routes through the wrapped version naturally.
export const AtRiskAccountsWidget = registerComponent({
  type: "widget",
  name: "at_risk_accounts",
  displayName: "At-Risk Accounts",
  description:
    "Funeral home accounts flagged as needing attention. Inline list of up to 3 accounts with reason; click-through to /vault/crm/companies/{id}. Renders on home + ops_board + vault_overview surfaces via shared component.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    ...WIDGET_WRAPPER_TOKENS,
    "status-error",
    "status-success",
  ],
  configurableProps: {
    maxAccountsShown: {
      type: "number",
      default: 3,
      bounds: [1, 10],
      displayLabel: "Max accounts shown",
      description: "Cap on at-risk account rows. Larger lists scroll within the widget.",
    },
    showHealthyState: {
      type: "boolean",
      default: true,
      displayLabel: "Show 'all healthy' state when count is 0",
      description: "Show '0 / All accounts healthy' message when no at-risk accounts exist. When false, widget renders empty.",
    },
    showReason: {
      type: "boolean",
      default: true,
      displayLabel: "Show at-risk reason",
      description: "Show the reason string per account in its subtitle.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 600,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description: "At-risk classification updates infrequently; default refresh is 10 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(AtRiskAccountsWidgetRaw)


// ─── qc_status (FH-vertical, extension-gated) ───────────────────
export const QCStatusWidget = registerComponent({
  type: "widget",
  name: "qc_status",
  displayName: "QC Inspection Status",
  description:
    "Today's quality control inspections: completed count + failed count + pass rate. Extension-gated on `npca_audit_prep`; vertical=funeral_home per CLAUDE.md §1 audit-prep canon.",
  category: "funeral-home-operations",
  verticals: ["funeral_home"],
  userParadigms: ["operator-power-user", "focused-executor"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS, "status-error", "accent"],
  configurableProps: {
    showFailedCount: {
      type: "boolean",
      default: true,
      displayLabel: "Show failed count when > 0",
      description: "Show prominent failed-count column when failures exist. When false, only completed count renders.",
    },
    showPassRate: {
      type: "boolean",
      default: true,
      displayLabel: "Show pass-rate percentage",
      description: "Show 'Pass rate: X%' subtext beneath counts.",
    },
    showLogCheckFooter: {
      type: "boolean",
      default: true,
      displayLabel: "Show 'Log QC check' footer CTA",
      description: "Show footer link to /console/operations/qc. When false, widget is read-only.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 1800],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches today's QC summary. Range: 1–30 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(QCStatusWidgetRaw)


// ─── time_clock (cross-vertical, extension-gated) ───────────────
export const TimeClockWidget = registerComponent({
  type: "widget",
  name: "time_clock",
  displayName: "Time Clock",
  description:
    "Clocked-in staff count + employee names + overtime alerts. Extension-gated on `time_clock`. Surfaces team-state on dashboard for owner-operator + operator-power-user paradigms.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS, "status-warning"],
  configurableProps: {
    maxEmployeesShown: {
      type: "number",
      default: 12,
      bounds: [1, 50],
      displayLabel: "Max employees shown",
      description: "Cap on listed employee names. Larger lists scroll within the widget.",
    },
    showOvertimeAlerts: {
      type: "boolean",
      default: true,
      displayLabel: "Show overtime alerts",
      description: "Show overtime alert pill when employees are approaching or exceeding overtime threshold.",
    },
    showCountOnly: {
      type: "boolean",
      default: false,
      displayLabel: "Compact mode (count only)",
      description: "When true, show only the clocked-in count without the employee list.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 1800],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches the time-clock summary. Range: 1–30 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(TimeClockWidgetRaw)


// ─── safety_status (cross-vertical, extension-gated) ────────────
export const SafetyWidget = registerComponent({
  type: "widget",
  name: "safety_status",
  displayName: "Safety Dashboard",
  description:
    "Safety dashboard summary: open incidents + overdue inspections + training overdue counts. Extension-gated on `safety`. Click-through to /safety for full management.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    ...WIDGET_WRAPPER_TOKENS,
    "status-error",
    "status-warning",
    "status-success",
    "accent",
  ],
  configurableProps: {
    showOpenIncidents: {
      type: "boolean",
      default: true,
      displayLabel: "Show open incidents row",
      description: "Show open incidents count. When false, the row is hidden.",
    },
    showOverdueInspections: {
      type: "boolean",
      default: true,
      displayLabel: "Show overdue inspections row",
      description: "Show overdue inspections count row. When false, the row is hidden.",
    },
    showTrainingOverdue: {
      type: "boolean",
      default: true,
      displayLabel: "Show overdue training row",
      description: "Show overdue training count row. When false, the row is hidden.",
    },
    showFooterLink: {
      type: "boolean",
      default: true,
      displayLabel: "Show 'View all' footer link",
      description: "Show footer link to /safety.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 1800],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches the safety dashboard summary. Range: 1–30 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(SafetyWidgetRaw)


// ─── compliance_upcoming (cross-vertical) ───────────────────────
export const ComplianceUpcomingWidget = registerComponent({
  type: "widget",
  name: "compliance_upcoming",
  displayName: "Compliance — Upcoming",
  description:
    "Compliance items due in next 30 days with severity-coded status badges (overdue / this_week / upcoming). Permission-gated on `compliance.view`. Click-through to /compliance.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    ...WIDGET_WRAPPER_TOKENS,
    "status-error",
    "status-warning",
    "surface-sunken",
  ],
  configurableProps: {
    maxItemsShown: {
      type: "number",
      default: 6,
      bounds: [3, 25],
      displayLabel: "Max items shown",
      description: "Cap on compliance items rendered inline. Overflow shows '+N more' link.",
    },
    daysWindow: {
      type: "number",
      default: 30,
      bounds: [7, 90],
      displayLabel: "Days window",
      description: "Look-ahead window for upcoming items. Range: 1–13 weeks.",
    },
    showStatusBadges: {
      type: "boolean",
      default: true,
      displayLabel: "Show status badges",
      description: "Show severity-coded badge (Overdue / Nd / etc.) per item. When false, only titles render.",
    },
    showOverflowLink: {
      type: "boolean",
      default: true,
      displayLabel: "Show '+N more' overflow link",
      description: "Show '+N more →' when total items exceeds maxItemsShown.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches the upcoming-compliance summary. Range: 1–60 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(ComplianceUpcomingWidgetRaw)


// ─── team_certifications (cross-vertical) ───────────────────────
export const TeamCertificationsWidget = registerComponent({
  type: "widget",
  name: "team_certifications",
  displayName: "Team Certifications Expiring",
  description:
    "Team members with certifications expiring soon (CDL, forklift, OSHA, etc.). Severity-coded urgency by days remaining: ≤14d urgent, ≤30d soon. Permission-gated on `employees.view`.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    ...WIDGET_WRAPPER_TOKENS,
    "status-error",
    "status-warning",
  ],
  configurableProps: {
    maxCertsShown: {
      type: "number",
      default: 6,
      bounds: [1, 25],
      displayLabel: "Max certifications shown",
      description: "Cap on certification rows.",
    },
    daysWindow: {
      type: "number",
      default: 60,
      bounds: [14, 180],
      displayLabel: "Look-ahead window (days)",
      description: "How far ahead to flag expiring certifications. Range: 2 weeks – 6 months.",
    },
    urgentDaysThreshold: {
      type: "number",
      default: 14,
      bounds: [3, 30],
      displayLabel: "Urgent threshold (days)",
      description: "Days-remaining threshold for urgent (red) classification.",
    },
    soonDaysThreshold: {
      type: "number",
      default: 30,
      bounds: [7, 60],
      displayLabel: "Soon threshold (days)",
      description: "Days-remaining threshold for soon (amber) classification. Should be greater than urgentDaysThreshold.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 600,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches the team-certifications list. Range: 1–60 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(TeamCertificationsWidgetRaw)


// ─── my_certifications (cross-vertical) ─────────────────────────
export const MyCertificationsWidget = registerComponent({
  type: "widget",
  name: "my_certifications",
  displayName: "My Certifications",
  description:
    "Current user's personal certifications with status (current / expiring_soon / expired) + days remaining. Read-only individual surface; no click-through.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["focused-executor", "operator-power-user"],
  consumedTokens: [
    ...WIDGET_WRAPPER_TOKENS,
    "status-success",
    "status-warning",
    "status-error",
  ],
  configurableProps: {
    maxCertsShown: {
      type: "number",
      default: 10,
      bounds: [1, 25],
      displayLabel: "Max certifications shown",
      description: "Cap on certification rows for the current user.",
    },
    showDaysRemaining: {
      type: "boolean",
      default: true,
      displayLabel: "Show days remaining",
      description: "Show 'Nd' suffix per row when not yet expired. When false, only icon + name + status render.",
    },
    hideExpired: {
      type: "boolean",
      default: false,
      displayLabel: "Hide expired certifications",
      description: "When true, expired certifications are hidden from the list.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 600,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches the current user's certifications. Range: 1–60 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(MyCertificationsWidgetRaw)


// ─── my_training (cross-vertical) ───────────────────────────────
export const MyTrainingWidget = registerComponent({
  type: "widget",
  name: "my_training",
  displayName: "My Training",
  description:
    "Current user's assigned training items with completion state + days until due. Overdue items highlighted in red. Click-through to /training for full management.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["focused-executor", "operator-power-user"],
  consumedTokens: [
    ...WIDGET_WRAPPER_TOKENS,
    "status-success",
    "status-error",
  ],
  configurableProps: {
    maxItemsShown: {
      type: "number",
      default: 5,
      bounds: [1, 20],
      displayLabel: "Max training items shown",
      description: "Cap on training rows for the current user.",
    },
    showCompletedItems: {
      type: "boolean",
      default: true,
      displayLabel: "Show completed items",
      description: "Show completed training (with check icon + strikethrough). When false, only incomplete items render.",
    },
    showDaysUntilDue: {
      type: "boolean",
      default: true,
      displayLabel: "Show days-until-due",
      description: "Show 'Nd' or 'Nd late' suffix per incomplete item.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 600,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description: "How often the widget re-fetches the current user's training items. Range: 1–60 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(MyTrainingWidgetRaw)


// ─── kb_recent (cross-vertical) ─────────────────────────────────
export const KbRecentWidget = registerComponent({
  type: "widget",
  name: "kb_recent",
  displayName: "Knowledge Base — Recent",
  description:
    "Most recently updated knowledge base entries with category + relative-time stamp. Click-through to /knowledge-base for full library.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [...WIDGET_WRAPPER_TOKENS],
  configurableProps: {
    maxItemsShown: {
      type: "number",
      default: 3,
      bounds: [1, 15],
      displayLabel: "Max entries shown",
      description: "Cap on recent KB entries rendered.",
    },
    showCategory: {
      type: "boolean",
      default: true,
      displayLabel: "Show category label",
      description: "Show category name per entry subtitle. When false, only title + relative time render.",
    },
    showRelativeTime: {
      type: "boolean",
      default: true,
      displayLabel: "Show relative timestamp",
      description: "Show 'N days ago' style. When false, absolute timestamps render.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 900,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description: "KB updates infrequently; default refresh is 15 minutes.",
    },
  },
  variants: [{ name: "brief", displayLabel: "Brief" }],
  schemaVersion: 1,
  componentVersion: 1,
})(KbRecentWidgetRaw)


// Re-export typed shape for consumer cast helpers. The componentMap
// at `components/widgets/ops-board/index.ts` imports these wrapped
// exports + casts through `unknown as ComponentType<WidgetProps>`
// per the established R-1.6.12 / Arc 1 convention (see
// `components/widgets/foundation/register.ts:54-60`).
export type DashboardWrappedWidget = ComponentType<unknown>
