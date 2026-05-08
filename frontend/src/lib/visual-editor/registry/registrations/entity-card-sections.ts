/**
 * R-2.1 — entity-card-section registrations.
 *
 * 10 sub-section registrations across the three entity cards
 * shipped in R-2.0:
 *   - delivery-card.{header,body,actions,hole-dug-badge} (4)
 *   - ancillary-card.{header,body,actions} (3)
 *   - order-card.{header,body,actions} (3)
 *
 * Slug convention is dot-separated `<parent>.<child>`. The dot-
 * segment-zero is the parent slug; explicit parent linkage lives at
 * `extensions.entityCardSection.{parentKind, parentName, sectionRole, optional}`
 * (see `types.ts::EntityCardSectionExtension`).
 *
 * Per /tmp/r2_1_subsection_scope.md architectural calls 1-10:
 *   - HYBRID taxonomy: common spine `header / body / [actions?]` +
 *     per-card extensions (DeliveryCard's HoleDugBadge as `custom`).
 *   - `optional: boolean` on the extension shape: AncillaryCard's
 *     actions is optional (renders only when note exists);
 *     OrderCard's actions is optional (informational bottom region);
 *     DeliveryCard's actions is non-optional (always renders icon row).
 *   - Each sub-component is its own React function (`*Raw` export)
 *     wrapped via `registerComponent({...})({Name}Raw)`. The wrapped
 *     HOC emits `data-component-name="{slug}"` with `display: contents`.
 *
 * Path 1 wrapping pattern parallels R-2.0's entity-cards.ts and
 * R-1.6.12's widget wrapping: capture the
 * `registerComponent(meta)(*Raw)` return value as a wrapped const +
 * export. Render sites import the wrapped versions from this barrel
 * (NOT from the underlying component files); ESLint rule
 * `bridgeable/entity-card-wrapped-import` enforces.
 *
 * R-4.0 button composition (Path A from /tmp/r2_1_subsection_scope.md
 * Section 7): the actions sub-section's `buttonSlugs` prop is an array
 * of `componentReference` props with `componentTypes: ["button"]` —
 * existing config-prop schema supports this directly. Runtime maps
 * the slugs to `<RegisteredButton componentName={slug} />`. First arc
 * consuming R-4.0 substrate inside another registered component.
 */

import { DeliveryCardHeaderRaw } from "@/components/dispatch/DeliveryCardHeader"
import { DeliveryCardBodyRaw } from "@/components/dispatch/DeliveryCardBody"
import { DeliveryCardActionsRaw } from "@/components/dispatch/DeliveryCardActions"
import { DeliveryCardHoleDugBadgeRaw } from "@/components/dispatch/DeliveryCardHoleDugBadge"
import { AncillaryCardHeaderRaw } from "@/components/dispatch/AncillaryCardHeader"
import { AncillaryCardBodyRaw } from "@/components/dispatch/AncillaryCardBody"
import { AncillaryCardActionsRaw } from "@/components/dispatch/AncillaryCardActions"
import { OrderCardHeaderRaw } from "@/components/delivery/OrderCardHeader"
import { OrderCardBodyRaw } from "@/components/delivery/OrderCardBody"
import { OrderCardActionsRaw } from "@/components/delivery/OrderCardActions"

import { registerComponent } from "../register"
import type { EntityCardSectionExtension } from "../types"


/** Internal helper: builds a `RegistrationMetadata` shape with the
 *  R-2.1 entity-card-section extension under
 *  `extensions.entityCardSection`. Keeps the per-section declarations
 *  below readable. */
function sectionMeta(opts: {
  slug: string
  displayName: string
  description: string
  category: string
  verticals: ("manufacturing" | "funeral_home" | "cemetery" | "crematory" | "all")[]
  productLines?: string[]
  consumedTokens: string[]
  parentName: string
  sectionRole: EntityCardSectionExtension["sectionRole"]
  optional: boolean
  configurableProps?: Record<
    string,
    import("../types").ConfigPropSchema
  >
}) {
  return {
    type: "entity-card-section" as const,
    name: opts.slug,
    displayName: opts.displayName,
    description: opts.description,
    category: opts.category,
    verticals: opts.verticals,
    userParadigms: [
      "operator-power-user" as const,
      "focused-executor" as const,
    ],
    productLines: opts.productLines,
    componentClasses: ["entity-card-section"],
    consumedTokens: opts.consumedTokens,
    configurableProps: opts.configurableProps,
    schemaVersion: 1,
    componentVersion: 1,
    extensions: {
      entityCardSection: {
        parentKind: "entity-card" as const,
        parentName: opts.parentName,
        sectionRole: opts.sectionRole,
        optional: opts.optional,
      } satisfies EntityCardSectionExtension,
    },
  }
}


/** Shared `buttonSlugs` prop schema — R-2.1 button composition Path A.
 *  Array of componentReference props filtered to `button` ComponentKind.
 *  The actions sub-section's runtime maps each slug to a
 *  `<RegisteredButton componentName={slug} />`. */
const BUTTON_SLUGS_PROP: import("../types").ConfigPropSchema<string[]> = {
  type: "array",
  default: [],
  bounds: { maxLength: 6 },
  displayLabel: "Action buttons",
  description:
    "Array of registered button slugs to render in this section. Each slug fires its R-4 contract on click. Buttons must be registered via `registry/registrations/buttons.ts` first.",
  itemSchema: {
    type: "componentReference",
    default: "",
    componentTypes: ["button"],
    displayLabel: "Button",
    description: "Pick a registered button by slug.",
  },
}


// ─── delivery-card sub-sections (4) ────────────────────────────────


export const DeliveryCardHeader = registerComponent(
  sectionMeta({
    slug: "delivery-card.header",
    displayName: "Delivery Card · Header",
    description:
      "Identity block — driver-start-time eyebrow + funeral-home headline + cemetery line. The stacked identity block at the top of every DeliveryCard. Renders inside the parent's QuickEdit click-button.",
    category: "manufacturing-operations",
    verticals: ["manufacturing"],
    productLines: ["vault"],
    consumedTokens: [
      "content-strong",
      "content-base",
      "content-muted",
      "text-body-sm",
      "text-caption",
      "text-micro",
    ],
    parentName: "delivery-card",
    sectionRole: "header",
    optional: false,
    configurableProps: {
      showStartTimeEyebrow: {
        type: "boolean",
        default: true,
        displayLabel: "Show start-time eyebrow",
        description:
          "Per-delivery driver start-time renders above the funeral-home headline as a tiny uppercase muted label.",
      },
      fhHeadlineFontTreatment: {
        type: "enum",
        default: "display",
        bounds: ["display", "body"],
        displayLabel: "FH headline typeface",
        description:
          "Display = Fraunces engraving register; body = Geist sans body register.",
      },
    },
  }),
)(DeliveryCardHeaderRaw)


export const DeliveryCardBody = registerComponent(
  sectionMeta({
    slug: "delivery-card.body",
    displayName: "Delivery Card · Body",
    description:
      "Service-time + location + ETA on line 3, product/equipment bundle on line 4. The 'what about this delivery matters' block. Renders inside the parent's QuickEdit click-button.",
    category: "manufacturing-operations",
    verticals: ["manufacturing"],
    productLines: ["vault"],
    consumedTokens: [
      "content-base",
      "content-muted",
      "text-body-sm",
      "text-caption",
    ],
    parentName: "delivery-card",
    sectionRole: "body",
    optional: false,
    configurableProps: {
      serviceTimeFormat: {
        type: "enum",
        default: "12h",
        bounds: ["12h", "24h"],
        displayLabel: "Service time format",
        description:
          "12h with AM/PM suffix or 24h. Render-only — does not affect data persistence.",
      },
      showProductLine: {
        type: "boolean",
        default: true,
        displayLabel: "Show product/equipment line",
        description:
          "Bottom muted line with vault type · equipment bundle. Tenants whose dispatchers don't reference product on the kanban can suppress.",
      },
    },
  }),
)(DeliveryCardBodyRaw)


export const DeliveryCardActions = registerComponent(
  sectionMeta({
    slug: "delivery-card.actions",
    displayName: "Delivery Card · Actions",
    description:
      "Status + icons row at the bottom of DeliveryCard — left cluster (info icons), optional middle cluster (R-4 buttons), right cluster (ancillary count + hole-dug badge). Always renders (per /tmp/r2_1_subsection_scope.md Section 1: DeliveryCard's actions section is non-optional — icon row always present).",
    category: "manufacturing-operations",
    verticals: ["manufacturing"],
    productLines: ["vault"],
    consumedTokens: [
      "content-muted",
      "border-subtle",
      "surface-sunken",
      "accent",
      "content-on-accent",
      "duration-quick",
    ],
    parentName: "delivery-card",
    sectionRole: "actions",
    optional: false,
    configurableProps: {
      showAncillaryCount: {
        type: "boolean",
        default: true,
        displayLabel: "Show ancillary attachment badge",
        description:
          "Surface the count of attached ancillary deliveries as an icon-and-count chip in the action row.",
      },
      buttonSlugs: BUTTON_SLUGS_PROP,
    },
  }),
)(DeliveryCardActionsRaw)


export const DeliveryCardHoleDugBadge = registerComponent(
  sectionMeta({
    slug: "delivery-card.hole-dug-badge",
    displayName: "Delivery Card · Hole-dug badge",
    description:
      "Three-state jewel-set status indicator (unknown → yes → no → unknown). DeliveryCard-specific; not part of the canonical header/body/actions spine. Background uses `--surface-base`; icon color carries the status semantic. Click cycles through the three states.",
    category: "manufacturing-operations",
    verticals: ["manufacturing"],
    productLines: ["vault"],
    consumedTokens: [
      "surface-base",
      "accent",
      "accent-confirmed",
      "content-muted",
      "shadow-jewel-inset",
    ],
    parentName: "delivery-card",
    sectionRole: "custom",
    optional: false,
    configurableProps: {
      jewelInsetEnabled: {
        type: "boolean",
        default: true,
        displayLabel: "Jewel-set inset shadow",
        description:
          "Pattern 3 inset shadow making the badge read as recessed into the card surface. Disable for flat-on-surface visual register.",
      },
      cycleOrder: {
        type: "enum",
        default: "unknown-yes-no",
        bounds: ["unknown-yes-no", "no-unknown-yes"],
        displayLabel: "Cycle order",
        description:
          "Order through which clicks cycle the three states. Default = unknown → yes → no → unknown.",
      },
    },
  }),
)(DeliveryCardHoleDugBadgeRaw)


// ─── ancillary-card sub-sections (3) ───────────────────────────────


export const AncillaryCardHeader = registerComponent(
  sectionMeta({
    slug: "ancillary-card.header",
    displayName: "Ancillary Card · Header",
    description:
      "Product/type label headline. Resolves via product_summary → vault_type → delivery_type label fallback chain. Renders inside the parent's QuickEdit click-button.",
    category: "manufacturing-operations",
    verticals: ["manufacturing"],
    productLines: ["vault"],
    consumedTokens: ["content-strong", "text-body-sm"],
    parentName: "ancillary-card",
    sectionRole: "header",
    optional: false,
    configurableProps: {
      labelFallbackStrategy: {
        type: "enum",
        default: "type-config-priority",
        bounds: ["type-config-priority", "delivery-type-only"],
        displayLabel: "Headline label resolution",
        description:
          "type-config-priority walks type_config.product_summary → vault_type → delivery_type label. delivery-type-only skips the type_config fallbacks.",
      },
    },
  }),
)(AncillaryCardHeaderRaw)


export const AncillaryCardBody = registerComponent(
  sectionMeta({
    slug: "ancillary-card.body",
    displayName: "Ancillary Card · Body",
    description:
      "Destination funeral home + city subhead. Renders inside the parent's QuickEdit click-button.",
    category: "manufacturing-operations",
    verticals: ["manufacturing"],
    productLines: ["vault"],
    consumedTokens: ["content-muted", "text-caption"],
    parentName: "ancillary-card",
    sectionRole: "body",
    optional: false,
    configurableProps: {
      showDestinationCity: {
        type: "boolean",
        default: true,
        displayLabel: "Show destination city",
        description:
          "Append cemetery city after the funeral-home headline. Some tenants prefer FH-only.",
      },
    },
  }),
)(AncillaryCardBodyRaw)


export const AncillaryCardActions = registerComponent(
  sectionMeta({
    slug: "ancillary-card.actions",
    displayName: "Ancillary Card · Actions",
    description:
      "Optional icon row — only renders when a note exists (or when buttonSlugs has entries). Per /tmp/r2_1_subsection_scope.md: ancillary actions is optional — empty row collapses entirely so the card stays minimal-vertical.",
    category: "manufacturing-operations",
    verticals: ["manufacturing"],
    productLines: ["vault"],
    consumedTokens: ["content-muted", "border-subtle"],
    parentName: "ancillary-card",
    sectionRole: "actions",
    optional: true,
    configurableProps: {
      iconRowVisibility: {
        type: "enum",
        default: "auto",
        bounds: ["auto", "always", "hidden"],
        displayLabel: "Icon row visibility",
        description:
          "Auto = render only when ancillary has a driver note. Always = always render even when empty. Hidden = suppress.",
      },
      buttonSlugs: BUTTON_SLUGS_PROP,
    },
  }),
)(AncillaryCardActionsRaw)


// ─── order-card sub-sections (3) ───────────────────────────────────


export const OrderCardHeader = registerComponent(
  sectionMeta({
    slug: "order-card.header",
    displayName: "Order Card · Header",
    description:
      "Funeral home name + 'RE: deceased_name' identity lines. Pre-R-2.1 OrderCard had no data-slot markers; R-2.1 adds order-card-fh + order-card-deceased.",
    category: "funeral-home-operations",
    verticals: ["funeral_home"],
    consumedTokens: ["content-strong", "content-muted"],
    parentName: "order-card",
    sectionRole: "header",
    optional: false,
    configurableProps: {
      showDeceasedName: {
        type: "boolean",
        default: true,
        displayLabel: "Show deceased name",
        description:
          "Render the 'RE: {deceased_name}' line below the funeral home headline. Some tenants prefer to omit deceased identification on the kanban surface for privacy.",
      },
    },
  }),
)(OrderCardHeaderRaw)


export const OrderCardBody = registerComponent(
  sectionMeta({
    slug: "order-card.body",
    displayName: "Order Card · Body",
    description:
      "Vault/equipment summary + service location/cemetery + service/ETA times. Pre-R-2.1 OrderCard had no data-slot markers; R-2.1 adds order-card-vault + order-card-service.",
    category: "funeral-home-operations",
    verticals: ["funeral_home"],
    consumedTokens: [
      "content-base",
      "content-muted",
      "content-subtle",
      "status-warning",
    ],
    parentName: "order-card",
    sectionRole: "body",
    optional: false,
    configurableProps: {
      showVaultPersonalizationBadge: {
        type: "boolean",
        default: true,
        displayLabel: "Show 'Custom' personalization badge",
        description:
          "Inline badge appears next to vault type when vault_personalization is true.",
      },
    },
  }),
)(OrderCardBodyRaw)


export const OrderCardActions = registerComponent(
  sectionMeta({
    slug: "order-card.actions",
    displayName: "Order Card · Actions",
    description:
      "Hours-countdown badge + free-form notes. Per /tmp/r2_1_subsection_scope.md: OrderCard's actions region is informational (countdown + notes), not action-shaped — optional. Section collapses entirely when no countdown / no notes / no buttons.",
    category: "funeral-home-operations",
    verticals: ["funeral_home"],
    consumedTokens: [
      "status-error",
      "status-warning",
      "content-subtle",
      "border-subtle",
    ],
    parentName: "order-card",
    sectionRole: "actions",
    optional: true,
    configurableProps: {
      showHoursCountdown: {
        type: "boolean",
        default: true,
        displayLabel: "Show hours-until-service countdown",
        description:
          "Bottom-of-card badge displaying time until service. Critical-window animates per accent-pulse semantics.",
      },
      showNotes: {
        type: "boolean",
        default: true,
        displayLabel: "Show notes line",
        description:
          "Bottom italic line for free-form notes.",
      },
      buttonSlugs: BUTTON_SLUGS_PROP,
    },
  }),
)(OrderCardActionsRaw)
