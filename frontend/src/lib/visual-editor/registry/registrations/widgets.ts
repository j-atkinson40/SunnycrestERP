/**
 * Registry registrations — widgets (Phase 1 + Phase 3 backfill).
 *
 * Six widgets across funeral_home + manufacturing verticals.
 *
 * Phase 3 backfill: configurableProps expanded from Phase 1's
 * placeholder set to comprehensively describe what's genuinely
 * configurable on each widget — the props an admin would
 * meaningfully want to vary across verticals or tenants.
 *
 * Tokens declared here mirror what each widget actually consumes
 * via Tailwind classes — when refactoring a widget to consume
 * different tokens, the registration here must be updated
 * alongside.
 *
 * Phase 3 keeps registrations in shim files (this directory) so
 * existing component files stay untouched. Phase 4+ may migrate
 * to in-file `registerComponent(...)` wrapping.
 *
 * R-1.6.12 — capture each `registerComponent(meta)(RawWidget)` return
 * value and export it. The wrapped versions carry the `data-component-name`
 * boundary div (per `register.ts:185` HOC). The canvas widget-renderer
 * registries at `components/widgets/{foundation,manufacturing}/register.ts`
 * import these wrapped versions and pass them to `registerWidgetRenderer`,
 * so the runtime DOM (Pulse, dashboards, pinned sections) emits
 * `data-component-name` — which the runtime editor's SelectionOverlay
 * walks up to resolve a clicked widget. Pre-R-1.6.12 the return
 * values were discarded, leaving runtime widgets unwrapped.
 */

import { TodayWidget as TodayWidgetRaw } from "@/components/widgets/foundation/TodayWidget"
import { OperatorProfileWidget as OperatorProfileWidgetRaw } from "@/components/widgets/foundation/OperatorProfileWidget"
import { RecentActivityWidget as RecentActivityWidgetRaw } from "@/components/widgets/foundation/RecentActivityWidget"
import { AnomaliesWidget as AnomaliesWidgetRaw } from "@/components/widgets/foundation/AnomaliesWidget"
import { VaultScheduleWidget as VaultScheduleWidgetRaw } from "@/components/widgets/manufacturing/VaultScheduleWidget"
import { LineStatusWidget as LineStatusWidgetRaw } from "@/components/widgets/manufacturing/LineStatusWidget"

import { registerComponent } from "../register"


// ─── today (cross-vertical foundation) ───────────────────────────

export const TodayWidget = registerComponent({
  type: "widget",
  name: "today",
  displayName: "Today",
  description:
    "Cross-vertical foundation widget surfacing today's relevant work items as a count + breakdown. Per-vertical-and-line content resolved server-side.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user", "focused-executor"],
  consumedTokens: [
    "surface-elevated",
    "surface-base",
    "border-base",
    "border-subtle",
    "shadow-level-1",
    "radius-base",
    "content-strong",
    "content-base",
    "content-muted",
    "text-h4",
    "text-body",
    "text-body-sm",
    "text-micro",
  ],
  configurableProps: {
    showRowBreakdown: {
      type: "boolean",
      default: true,
      displayLabel: "Show category breakdown",
      description:
        "Show the per-category count rows beneath the total in Brief variant.",
    },
    showTotalCount: {
      type: "boolean",
      default: true,
      displayLabel: "Show total count",
      description: "Show the large numeric total at the top.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 300,
      bounds: [60, 3600],
      displayLabel: "Refresh interval (seconds)",
      description:
        "How often the widget re-fetches from /widget-data/today. Range: 1–60 minutes.",
    },
    maxCategoriesShown: {
      type: "number",
      default: 5,
      bounds: [1, 12],
      displayLabel: "Max categories shown",
      description:
        "Cap on how many category rows render in Brief variant before collapsing.",
    },
    accentToken: {
      type: "tokenReference",
      default: "accent",
      tokenCategory: "accent",
      displayLabel: "Accent token",
      description: "Token used for the count-emphasis chrome.",
    },
    dateFormatStyle: {
      type: "enum",
      default: "weekday-month-day",
      bounds: ["weekday-month-day", "iso", "month-day", "relative"],
      displayLabel: "Date format style",
      description:
        "How the subtitle date renders — full weekday, ISO, abbreviated, or relative.",
    },
    emptyStateBehavior: {
      type: "enum",
      default: "vertical-default-cta",
      bounds: ["vertical-default-cta", "minimal", "hidden"],
      displayLabel: "Empty state behavior",
      description:
        "What renders when the day has no relevant work items.",
    },
  },
  variants: [
    {
      name: "glance",
      displayLabel: "Glance",
      description: "Compact 60px sidebar tablet — date + total count.",
    },
    {
      name: "brief",
      displayLabel: "Brief",
      description:
        "Pattern 2 grid card — header with date + 3-5 row breakdown + click-through per row.",
    },
  ],
  schemaVersion: 1,
  componentVersion: 2,
})(TodayWidgetRaw)


// ─── operator_profile (cross-vertical foundation) ────────────────

export const OperatorProfileWidget = registerComponent({
  type: "widget",
  name: "operator-profile",
  displayName: "Operator Profile",
  description:
    "Cross-vertical foundation widget rendering authenticated user identity + active space context. Renders from auth/spaces context with no backend call.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["all"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "content-strong",
    "content-base",
    "content-muted",
    "accent",
    "accent-subtle",
    "accent-muted",
    "radius-base",
    "radius-full",
    "shadow-level-1",
    "text-body",
    "text-body-sm",
    "text-caption",
  ],
  configurableProps: {
    avatarSize: {
      type: "enum",
      default: "medium",
      bounds: ["small", "medium", "large"],
      displayLabel: "Avatar size",
      description: "Initials-avatar size in the header row.",
    },
    avatarStyle: {
      type: "enum",
      default: "initials",
      bounds: ["initials", "icon", "image"],
      displayLabel: "Avatar style",
      description:
        "Initials reads first letter of first + last name; icon uses a generic user glyph; image uses tenant-uploaded avatar when set.",
    },
    showRoleBadge: {
      type: "boolean",
      default: true,
      displayLabel: "Show role badge",
      description: "Show the user's role label below their name.",
    },
    showActiveSpace: {
      type: "boolean",
      default: true,
      displayLabel: "Show active space",
      description: "Show which Space the operator currently has selected.",
    },
    showTenantName: {
      type: "boolean",
      default: true,
      displayLabel: "Show tenant name",
    },
    avatarAccentToken: {
      type: "tokenReference",
      default: "accent-muted",
      tokenCategory: "accent",
      displayLabel: "Avatar background token",
      description: "Background fill on the initials avatar.",
    },
    density: {
      type: "enum",
      default: "comfortable",
      bounds: ["compact", "comfortable", "spacious"],
      displayLabel: "Density",
      description: "Vertical spacing inside the widget.",
    },
  },
  variants: [
    { name: "glance", displayLabel: "Glance" },
    { name: "brief", displayLabel: "Brief" },
  ],
  schemaVersion: 1,
  componentVersion: 2,
})(OperatorProfileWidgetRaw)


// ─── recent_activity (cross-vertical foundation) ─────────────────

export const RecentActivityWidget = registerComponent({
  type: "widget",
  name: "recent-activity",
  displayName: "Recent Activity",
  description:
    "Cross-vertical activity feed backed by /vault/activity/recent. Renders most-recent activity rows with actor + verb + entity + relative timestamp; click-through navigates to the related entity.",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "content-strong",
    "content-base",
    "content-muted",
    "content-subtle",
    "accent",
    "radius-base",
    "shadow-level-1",
    "text-body-sm",
    "text-caption",
  ],
  configurableProps: {
    maxItems: {
      type: "number",
      default: 10,
      bounds: [1, 50],
      displayLabel: "Max items shown",
      description: "Cap on activity rows rendered in Brief + Detail.",
    },
    showActorAvatar: {
      type: "boolean",
      default: true,
      displayLabel: "Show actor avatar",
      description: "Show initials avatar for the actor on each row.",
    },
    showRelativeTimestamps: {
      type: "boolean",
      default: true,
      displayLabel: "Show relative timestamps",
      description:
        "Show 'N minutes ago' style timestamps. When false, shows absolute time.",
    },
    activityTypeFilter: {
      type: "enum",
      default: "all",
      bounds: ["all", "comms", "work", "system"],
      displayLabel: "Default activity-type filter",
      description:
        "Initial filter chip selection. User can override at runtime.",
    },
    sinceWindowDays: {
      type: "number",
      default: 7,
      bounds: [1, 90],
      displayLabel: "Look-back window (days)",
      description:
        "Filter activity to events within this many days. Older events are hidden.",
    },
    actorAccentToken: {
      type: "tokenReference",
      default: "accent",
      tokenCategory: "accent",
      displayLabel: "Actor name accent",
      description: "Token coloring the actor's name on each row.",
    },
    showFilterChips: {
      type: "boolean",
      default: true,
      displayLabel: "Show filter chips (Detail variant)",
    },
    emptyStateText: {
      type: "string",
      default: "No recent activity",
      displayLabel: "Empty state text",
      description: "Shown when no activity matches the current filter.",
      bounds: { maxLength: 80 },
    },
  },
  variants: [
    { name: "brief", displayLabel: "Brief" },
    { name: "detail", displayLabel: "Detail" },
  ],
  schemaVersion: 1,
  componentVersion: 2,
})(RecentActivityWidgetRaw)


// ─── anomalies (cross-vertical foundation) ───────────────────────

export const AnomaliesWidget = registerComponent({
  type: "widget",
  name: "anomalies",
  displayName: "Anomalies",
  description:
    "Cross-vertical AI-detected anomalies queue backed by agent_anomalies. Severity-sorted with bounded Acknowledge action (single-anomaly state flip, audit-logged).",
  category: "foundation",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "content-strong",
    "content-base",
    "content-muted",
    "status-error",
    "status-error-muted",
    "status-warning",
    "status-warning-muted",
    "status-info",
    "status-info-muted",
    "status-success",
    "radius-base",
    "shadow-level-1",
    "text-body-sm",
    "text-micro",
  ],
  configurableProps: {
    severityFilter: {
      type: "enum",
      default: "all",
      bounds: ["all", "critical", "warning", "info"],
      displayLabel: "Default severity filter",
      description:
        "Initial filter selection. User can override at runtime.",
    },
    maxItemsBrief: {
      type: "number",
      default: 5,
      bounds: [1, 20],
      displayLabel: "Max items in Brief variant",
    },
    maxItemsDetail: {
      type: "number",
      default: 25,
      bounds: [5, 100],
      displayLabel: "Max items in Detail variant",
    },
    showAcknowledgeAction: {
      type: "boolean",
      default: true,
      displayLabel: "Show Acknowledge action",
      description:
        "Hide the inline Acknowledge button for read-only audiences.",
    },
    showSeverityBadges: {
      type: "boolean",
      default: true,
      displayLabel: "Show severity badges",
    },
    showAmounts: {
      type: "boolean",
      default: true,
      displayLabel: "Show monetary amounts when present",
      description:
        "Some anomalies carry an amount field — toggling controls whether it renders.",
    },
    sortOrder: {
      type: "enum",
      default: "severity-then-recent",
      bounds: [
        "severity-then-recent",
        "severity-then-amount",
        "most-recent",
        "highest-amount",
      ],
      displayLabel: "Sort order",
      description: "Default ordering of anomaly rows.",
    },
    autoCollapseAcknowledged: {
      type: "boolean",
      default: true,
      displayLabel: "Auto-collapse acknowledged anomalies",
      description:
        "Hide acknowledged items by default; user can expand to view.",
    },
  },
  variants: [
    { name: "brief", displayLabel: "Brief" },
    { name: "detail", displayLabel: "Detail" },
  ],
  schemaVersion: 1,
  componentVersion: 2,
})(AnomaliesWidgetRaw)


// ─── vault_schedule (manufacturing) ──────────────────────────────

export const VaultScheduleWidget = registerComponent({
  type: "widget",
  name: "vault-schedule",
  displayName: "Vault Schedule",
  description:
    "Workspace-core canonical reference. Renders the same data the scheduling Focus kanban consumes with a deliberately abridged interactive surface (mark hole-dug, drag delivery between drivers, attach/detach ancillary). Mode-aware — production reads Delivery rows, purchase reads incoming LicenseeTransfer rows.",
  category: "manufacturing-operations",
  verticals: ["manufacturing"],
  userParadigms: ["operator-power-user", "focused-executor"],
  productLines: ["vault"],
  consumedTokens: [
    "surface-elevated",
    "surface-sunken",
    "border-base",
    "border-subtle",
    "border-accent",
    "accent",
    "accent-subtle",
    "content-strong",
    "content-base",
    "content-muted",
    "status-warning",
    "status-success",
    "radius-base",
    "shadow-level-1",
    "shadow-level-2",
    "text-body-sm",
    "text-caption",
    "text-micro",
  ],
  configurableProps: {
    targetDate: {
      type: "string",
      default: "today",
      displayLabel: "Target date",
      description:
        "ISO date or 'today' / 'tomorrow' shortcut. Drives which deliveries render.",
      bounds: { maxLength: 32 },
    },
    operatingMode: {
      type: "enum",
      default: "auto",
      bounds: ["auto", "production", "purchase", "hybrid"],
      displayLabel: "Operating mode",
      description:
        "Auto reads from TenantProductLine.config['operating_mode']; explicit values override.",
    },
    showAncillaryAttachments: {
      type: "boolean",
      default: true,
      displayLabel: "Show ancillary attachment count",
      description:
        "Surface the count of attached ancillary items per delivery row.",
    },
    showDriverAvatars: {
      type: "boolean",
      default: false,
      displayLabel: "Show driver avatars",
      description: "Render initials avatars for assigned drivers.",
    },
    unscheduledHighlightToken: {
      type: "tokenReference",
      default: "status-warning",
      tokenCategory: "status",
      displayLabel: "Unscheduled highlight",
      description:
        "Status token coloring rows assigned to the 'Unscheduled' lane.",
    },
    timeColumnFormat: {
      type: "enum",
      default: "12h",
      bounds: ["12h", "24h", "relative"],
      displayLabel: "Time column format",
    },
    confirmDestructiveActions: {
      type: "boolean",
      default: true,
      displayLabel: "Confirm destructive actions",
      description:
        "Require confirmation modal before mark-pickup-cancel or detach.",
    },
    maxDriverLanes: {
      type: "number",
      default: 12,
      bounds: [1, 24],
      displayLabel: "Max driver lanes shown",
      description:
        "Cap on driver lanes; tenants with more drivers fall back to a 'Show all' affordance.",
    },
  },
  variants: [
    { name: "glance", displayLabel: "Glance" },
    { name: "brief", displayLabel: "Brief" },
    { name: "detail", displayLabel: "Detail" },
    { name: "deep", displayLabel: "Deep" },
  ],
  slots: [
    {
      name: "drivers",
      displayLabel: "Driver lanes",
      acceptedTypes: ["composite"],
      description:
        "Driver lane composition. Phase 1 is read-only; Phase 2+ allows reordering driver lanes via the editor.",
    },
  ],
  schemaVersion: 1,
  componentVersion: 2,
})(VaultScheduleWidgetRaw)


// ─── line_status (manufacturing) ─────────────────────────────────

export const LineStatusWidget = registerComponent({
  type: "widget",
  name: "line-status",
  displayName: "Line Status",
  description:
    "Cross-line operational health aggregator. Per-line health vocabulary canonical: on_track / behind / blocked / idle / unknown. Multi-line builder pattern — vault health real today; redi_rock / wastewater / urn_sales / rosetta render placeholder rows until each line's metrics aggregator ships.",
  category: "manufacturing-operations",
  verticals: ["manufacturing"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "border-base",
    "content-strong",
    "content-base",
    "content-muted",
    "status-success",
    "status-warning",
    "status-error",
    "status-info",
    "radius-base",
    "shadow-level-1",
    "text-body-sm",
    "text-caption",
  ],
  configurableProps: {
    productLineFilter: {
      type: "array",
      default: [],
      displayLabel: "Product line filter",
      description:
        "Restrict to specific lines. Empty array = render all activated lines.",
      itemSchema: { type: "string", default: "" },
    },
    showHeadlineMetrics: {
      type: "boolean",
      default: true,
      displayLabel: "Show headline metrics per line",
      description:
        "Show key metric (e.g., 'On-time rate 92%') beside each line's status pill.",
    },
    showIdleLines: {
      type: "boolean",
      default: true,
      displayLabel: "Show idle lines",
      description:
        "When false, hides lines with status='idle' or 'unknown'.",
    },
    refreshIntervalSeconds: {
      type: "number",
      default: 180,
      bounds: [30, 1800],
      displayLabel: "Refresh interval (seconds)",
    },
    statusOrder: {
      type: "enum",
      default: "severity",
      bounds: ["severity", "alphabetical", "by-product-line"],
      displayLabel: "Status sort order",
      description:
        "Severity puts blocked/behind first; alphabetical sorts by line name; by-product-line uses the configured ordering.",
    },
    blockedLineHighlight: {
      type: "tokenReference",
      default: "status-error",
      tokenCategory: "status",
      displayLabel: "Blocked line highlight",
    },
    healthyLineHighlight: {
      type: "tokenReference",
      default: "status-success",
      tokenCategory: "status",
      displayLabel: "Healthy line highlight",
    },
  },
  variants: [
    { name: "brief", displayLabel: "Brief" },
    { name: "detail", displayLabel: "Detail" },
  ],
  schemaVersion: 1,
  componentVersion: 2,
})(LineStatusWidgetRaw)
