/**
 * Registry registrations — entity cards (R-2.0).
 *
 * Three registrations across the manufacturer-side dispatch surfaces:
 *   - `delivery-card`   (DeliveryCard, dispatch/funeral-schedule kanban)
 *   - `ancillary-card`  (AncillaryCard, scheduling Focus accessory rail)
 *   - `order-card`      (OrderCard, scheduling-board kanban-panel)
 *
 * Pattern parallels R-1.6.12's widget wrapping: capture the
 * `registerComponent(meta)(*Raw)` return value as a wrapped const +
 * export. Render sites import the wrapped versions from this barrel
 * (NOT from the underlying component files), guaranteeing the
 * `data-component-name` boundary div emitted by `register.ts:185-218`
 * reaches the runtime DOM. SelectionOverlay's capture-phase walker can
 * then resolve a clicked card into the inspector panel for click-to-
 * edit.
 *
 * Spec-Override Discipline note (CLAUDE.md §12) — the R-2.0 prompt
 * targeted 11-13 registrations across the three cards (whole + header +
 * status + body + actions). Investigation of the actual component
 * structures showed each card is a single React function with inline
 * JSX subsections marked by `data-slot` attributes — no separately-
 * declared section sub-components. Sub-section registrations would
 * require either:
 *   (a) Extracting each `data-slot` region into its own React
 *       component, then wrapping each at registration site —
 *       ~800 LOC of component refactoring across DeliveryCard.tsx
 *       (823 LOC), AncillaryCard.tsx (209 LOC), OrderCard.tsx
 *       (224 LOC) plus updating tests that reference internal
 *       structure.
 *   (b) Wrapping inline JSX expressions inside the parent component,
 *       which doesn't produce useful click-to-edit targets because
 *       the editor's inspector resolves component names via
 *       `getByName(kind, name)` and the wrapped inline expression
 *       wouldn't have a discoverable identity.
 *
 * Both options were out-of-scope for R-2.0 per the prompt's
 * "Don't force a registration if a 'section' is just a single inline
 * element with no distinct boundary" guidance. Sub-section granularity
 * (header / status pill / actions / footer registrations) lands as
 * R-2.1 once the cards are decomposed into named sub-components —
 * R-2.0 ships the foundational pattern with 3 whole-card targets.
 *
 * Internal sub-component candidates for R-2.1 (already structurally
 * separable, just need export + wrap):
 *   - DeliveryCard's HoleDugBadge (line 732+) — already its own
 *     internal function declaration; wrapping requires only adding
 *     `export` + extracting to its own file (to avoid circular
 *     import: entity-cards.ts → DeliveryCard.tsx → HoleDugBadge).
 *   - AncillaryCard's icon-row (line 191+) — currently inline; would
 *     need extraction to a named sub-component first.
 */

import { DeliveryCardRaw as DeliveryCardRawImpl } from "@/components/dispatch/DeliveryCard"
import { AncillaryCardRaw as AncillaryCardRawImpl } from "@/components/dispatch/AncillaryCard"
import { OrderCardRaw as OrderCardRawImpl } from "@/components/delivery/OrderCard"

import { registerComponent } from "../register"


// ─── delivery-card (manufacturer dispatch kanban) ─────────────────

export const DeliveryCard = registerComponent({
  type: "entity-card",
  name: "delivery-card",
  displayName: "Delivery Card",
  description:
    "Manufacturer-side dispatch entity card. Renders a single Delivery row in the funeral-schedule kanban + scheduling Focus accessory rail. Carries family + cemetery + service-time + funeral-home + vault/equipment fields, with hole-dug status pill + ancillary count + chat affordance + drag-handle composition. Workspace-core surface — primary touch point for dispatcher daily use.",
  category: "manufacturing-operations",
  verticals: ["manufacturing"],
  userParadigms: ["operator-power-user", "focused-executor"],
  productLines: ["vault"],
  consumedTokens: [
    "surface-elevated",
    "surface-base",
    "surface-sunken",
    "border-base",
    "border-subtle",
    "border-l-accent",
    "border-l-accent-confirmed",
    "border-l-transparent",
    "accent",
    "accent-subtle",
    "accent-confirmed",
    "content-strong",
    "content-base",
    "content-muted",
    "content-subtle",
    "content-on-accent",
    "shadow-level-1",
    "shadow-level-2",
    "card-edge-highlight",
    "card-edge-shadow",
    "card-ambient-shadow",
    "flag-press-shadow",
    "shadow-jewel-inset",
    "radius-base",
    "text-body-sm",
    "text-caption",
    "text-micro",
    "duration-settle",
    "duration-quick",
    "ease-settle",
  ],
  configurableProps: {
    density: {
      type: "enum",
      default: "default",
      bounds: ["default", "compact"],
      displayLabel: "Density",
      description:
        "Compact tightens horizontal + vertical rhythm without hiding any content. Default reads at full-detail scan-distance; compact fits more cards in narrow lanes.",
    },
    showStartTimeEyebrow: {
      type: "boolean",
      default: true,
      displayLabel: "Show driver start-time eyebrow",
      description:
        "Per-delivery driver start-time renders above the funeral-home headline as a tiny uppercase muted label. NULL value = implicit tenant default = not displayed regardless of this flag.",
    },
    showAncillaryCount: {
      type: "boolean",
      default: true,
      displayLabel: "Show ancillary attachment badge",
      description:
        "Surface the count of attached ancillary deliveries as an icon-and-count chip in the bottom action row.",
    },
    showHoleDugBadge: {
      type: "boolean",
      default: true,
      displayLabel: "Show hole-dug status badge",
      description:
        "Bottom-right jewel-set status indicator with three states (yes / no / unknown). Hiding suppresses the entire bottom-right cluster on cards with no other right-side content.",
    },
    flagAccentToken: {
      type: "tokenReference",
      default: "accent",
      tokenCategory: "accent",
      displayLabel: "Flag accent (unknown state)",
      description:
        "3px left-edge flag color for hole-dug=unknown. Confirmed (yes) state uses --accent-confirmed sage-green which is not configurable here — sage is architectural register per DESIGN_LANGUAGE §3.",
    },
    serviceTimeFormat: {
      type: "enum",
      default: "12h",
      bounds: ["12h", "24h"],
      displayLabel: "Service time format",
      description:
        "12h with AM/PM suffix or 24h. Render-only — does not affect data persistence.",
    },
    chatBadgeBehavior: {
      type: "enum",
      default: "highlight-with-count",
      bounds: [
        "highlight-with-count",
        "icon-only",
        "hidden",
      ],
      displayLabel: "Chat-activity badge behavior",
      description:
        "How unread chat messages with the funeral home surface in the icon row. Highlight-with-count is canonical; icon-only suppresses the count chip; hidden suppresses the icon entirely.",
    },
  },
  variants: [
    { name: "default", displayLabel: "Default" },
    { name: "compact", displayLabel: "Compact" },
  ],
  schemaVersion: 1,
  componentVersion: 1,
})(DeliveryCardRawImpl)


// ─── ancillary-card (manufacturer scheduling Focus rail) ──────────

export const AncillaryCard = registerComponent({
  type: "entity-card",
  name: "ancillary-card",
  displayName: "Ancillary Card",
  description:
    "Standalone ancillary delivery card. Renders inside Scheduling Focus driver lanes alongside primary DeliveryCards. Field set is intentionally smaller than DeliveryCard — product label + funeral-home headline + optional driver-note icon. Drag handle for reassignment; click opens QuickEditDialog.",
  category: "manufacturing-operations",
  verticals: ["manufacturing"],
  userParadigms: ["operator-power-user", "focused-executor"],
  productLines: ["vault"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "content-strong",
    "content-base",
    "content-muted",
    "shadow-level-1",
    "shadow-level-2",
    "radius-base",
    "text-body-sm",
    "text-caption",
    "duration-settle",
    "ease-settle",
  ],
  configurableProps: {
    showDestinationCity: {
      type: "boolean",
      default: true,
      displayLabel: "Show destination city",
      description:
        "Append cemetery city after the funeral-home headline (when populated on the delivery's type_config). Geographic anchor for pairing decisions; some tenants prefer FH-only.",
    },
    iconRowVisibility: {
      type: "enum",
      default: "auto",
      bounds: ["auto", "always", "hidden"],
      displayLabel: "Icon row visibility",
      description:
        "Auto = render only when the ancillary has a driver note. Always = always render the row even when empty (preserves vertical alignment with DeliveryCards in same lane). Hidden = suppress.",
    },
    labelFallbackStrategy: {
      type: "enum",
      default: "type-config-priority",
      bounds: [
        "type-config-priority",
        "delivery-type-only",
      ],
      displayLabel: "Headline label resolution",
      description:
        "type-config-priority walks type_config.product_summary → vault_type → delivery_type label. delivery-type-only skips the type_config fallbacks for tenants whose ancillary product_summary is unreliable.",
    },
  },
  variants: [{ name: "default", displayLabel: "Default" }],
  schemaVersion: 1,
  componentVersion: 1,
})(AncillaryCardRawImpl)


// ─── order-card (scheduling-board kanban-panel) ───────────────────

export const OrderCard = registerComponent({
  type: "entity-card",
  name: "order-card",
  displayName: "Order Card",
  description:
    "Funeral-home-side scheduling-board entity card. Renders a single KanbanCard row in the daily kanban-panel. Fields: funeral home + deceased + vault/equipment + service location + cemetery + service-time + ETA + hours-until-service countdown. Critical/warning windows surface as accent-pulse outlines per SchedulingBoard urgency model.",
  category: "funeral-home-operations",
  verticals: ["funeral_home"],
  userParadigms: ["operator-power-user", "focused-executor"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "border-base",
    "accent",
    "content-strong",
    "content-base",
    "content-muted",
    "content-subtle",
    "status-error",
    "status-error-muted",
    "status-warning",
    "status-warning-muted",
    "shadow-level-1",
    "shadow-level-2",
    "radius-base",
    "text-body-sm",
    "text-caption",
    "duration-settle",
    "ease-settle",
  ],
  configurableProps: {
    showDeceasedName: {
      type: "boolean",
      default: true,
      displayLabel: "Show deceased name",
      description:
        "Render the 'RE: {deceased_name}' line below the funeral home headline. Some tenants prefer to omit deceased identification on the kanban surface for privacy.",
    },
    showHoursCountdown: {
      type: "boolean",
      default: true,
      displayLabel: "Show hours-until-service countdown",
      description:
        "Bottom-of-card badge displaying time until service. Critical-window animates per accent-pulse semantics (under critical_window_hours from kanban config).",
    },
    showVaultPersonalizationBadge: {
      type: "boolean",
      default: true,
      displayLabel: "Show 'Custom' personalization badge",
      description:
        "Inline badge appears next to vault type when vault_personalization is true. Signals dispatcher that the vault is a custom configuration requiring extra coordination.",
    },
    criticalWindowAccentToken: {
      type: "tokenReference",
      default: "status-error",
      tokenCategory: "status",
      displayLabel: "Critical-window accent",
      description:
        "Status token coloring the card border + chip + countdown when the service falls inside the critical window. Pulse animation is fixed; only the color is configurable.",
    },
    showNotes: {
      type: "boolean",
      default: true,
      displayLabel: "Show notes line",
      description:
        "Bottom italic line for free-form notes. Tenants with high signal-to-noise notes preserve; tenants where notes drift to operational chaff disable.",
    },
  },
  variants: [{ name: "default", displayLabel: "Default" }],
  schemaVersion: 1,
  componentVersion: 1,
})(OrderCardRawImpl)
