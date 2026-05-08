/**
 * R-4.0 — button registrations.
 *
 * Three example button registrations seeded for R-4.0:
 *   - `open-funeral-scheduling-focus` (open_focus action)
 *   - `trigger-cement-order-workflow` (trigger_workflow action)
 *   - `navigate-to-pulse` (navigate action)
 *
 * Pattern follows the widget-shaped registration model:
 *   1 ComponentKind ("button") + N registered instances. Mirrors how
 *   widgets are structured (1 kind, many slugs). Differs from entity-
 *   cards which wrap an underlying React component via Path 1; buttons
 *   are rendered uniformly by `RegisteredButton` which looks up its
 *   own metadata via `getByName("button", slug)` at click-time.
 *
 * Per Spec-Override Discipline (CLAUDE.md §12): R-4.0 ships ONLY 5
 * action types in dispatch (navigate / open_focus / trigger_workflow
 * / create_vault_item / run_playwright_workflow). Other ActionKind
 * values from `services/actions/` are deferred to R-4.x increments.
 *
 * Each registration declares its R-4 contract under
 * `extensions.r4` (versioned key so future R-4.x increments can
 * evolve the contract without disturbing the rest of the
 * `extensions` namespace).
 *
 * The registration's `configurableProps` declare the per-instance
 * customizable surface (label / variant / size / iconName / etc.).
 * Composition placement carries `prop_overrides` which RegisteredButton
 * overlays on top of registration defaults at render time.
 */

import type { RegistrationMetadata } from "../types"
import { registerComponent } from "../register"
import { RegisteredButton } from "@/lib/runtime-host/buttons/RegisteredButton"
import type { R4ButtonContract } from "@/lib/runtime-host/buttons/types"


/** Internal helper: builds a `RegistrationMetadata` shape with the
 *  R-4 contract under `extensions.r4`. Keeps the per-button declarations
 *  below readable. */
function buttonRegistration(opts: {
  name: string
  displayName: string
  description: string
  category: string
  verticals: RegistrationMetadata["verticals"]
  defaultLabel: string
  defaultVariant?: "default" | "secondary" | "outline" | "ghost" | "destructive" | "link"
  defaultSize?: "default" | "sm" | "lg"
  defaultIconName?: string
  contract: R4ButtonContract
}): RegistrationMetadata {
  return {
    type: "button",
    name: opts.name,
    displayName: opts.displayName,
    description: opts.description,
    category: opts.category,
    verticals: opts.verticals,
    userParadigms: ["operator-power-user", "focused-executor"],
    componentClasses: ["button"],
    consumedTokens: [
      "accent",
      "accent-hover",
      "content-on-accent",
      "shadow-level-1",
      "radius-base",
      "duration-quick",
      "ease-settle",
    ],
    configurableProps: {
      label: {
        type: "string",
        default: opts.defaultLabel,
        bounds: { maxLength: 48 },
        displayLabel: "Label",
        description: "Visible button text. Keep ≤ 48 chars for layout fit.",
      },
      variant: {
        type: "enum",
        default: opts.defaultVariant ?? "default",
        bounds: [
          "default",
          "secondary",
          "outline",
          "ghost",
          "destructive",
          "link",
        ],
        displayLabel: "Variant",
        description:
          "Button visual treatment. `default` is the brass primary CTA; `destructive` for irreversible actions; `link` for inline tertiary.",
      },
      size: {
        type: "enum",
        default: opts.defaultSize ?? "default",
        bounds: ["default", "sm", "lg"],
        displayLabel: "Size",
        description:
          "Sizing scale. `default` is the substantial 40px CTA; `sm` for dense composition rows; `lg` for hero placements.",
      },
      iconName: {
        type: "string",
        default: opts.defaultIconName ?? "",
        bounds: { maxLength: 32 },
        displayLabel: "Icon name (lucide)",
        description:
          "Optional leading icon by lucide-react export name (e.g. 'CalendarPlus', 'Workflow', 'Home'). Empty disables.",
      },
      disabled: {
        type: "boolean",
        default: false,
        displayLabel: "Disabled",
        description:
          "When true the button renders disabled. Useful for surfaces that need a visible-but-inactive button while a precondition is still loading.",
      },
    },
    schemaVersion: 1,
    componentVersion: 1,
    extensions: { r4: opts.contract },
  }
}


// ─── 1. open-funeral-scheduling-focus ─────────────────────────────


export const OpenFuneralSchedulingFocusButton = registerComponent(
  buttonRegistration({
    name: "open-funeral-scheduling-focus",
    displayName: "Open Scheduling Focus",
    description:
      "Opens the funeral-scheduling Focus over the current page. Targets manufacturing-vertical dispatchers + funeral home operators planning the day's schedule. Forwards the current ?date= query param when set so the Focus opens at the same date the operator is viewing on the underlying surface.",
    category: "scheduling",
    verticals: ["manufacturing", "funeral_home"],
    defaultLabel: "Open scheduling",
    defaultIconName: "CalendarPlus",
    contract: {
      actionType: "open_focus",
      actionConfig: { focusId: "funeral-scheduling" },
      parameterBindings: [
        // Forward `?date=` from the underlying URL into the Focus's
        // params bag. FocusContext.open() stores params; the Focus core
        // (SchedulingKanbanCore) reads them for its initial date.
        { name: "date", source: "current_query_param", paramName: "date" },
      ],
      successBehavior: "stay",
    },
  }),
)(RegisteredButton)


// ─── 2. trigger-cement-order-workflow ─────────────────────────────


export const TriggerCementOrderWorkflowButton = registerComponent(
  buttonRegistration({
    name: "trigger-cement-order-workflow",
    displayName: "Order cement",
    description:
      "Kicks off the cement-order workflow (PO + Playwright vendor order + receiving). Manufacturer-vertical only — vault tenants ordering raw cement supply. Surfaces a confirmation Dialog before firing because the workflow runs against external vendor systems and is not trivially reversible.",
    category: "manufacturing-operations",
    verticals: ["manufacturing"],
    defaultLabel: "Order cement",
    defaultVariant: "default",
    defaultIconName: "Workflow",
    contract: {
      actionType: "trigger_workflow",
      actionConfig: { workflowId: "wf_mfg_cement_order" },
      parameterBindings: [
        // Workflow trigger context carries who/where/when. Workflow
        // engine receives these under `trigger_context` and forwards
        // to step inputs as needed.
        { name: "tenant_id", source: "current_tenant", tenantField: "id" },
        {
          name: "triggered_by",
          source: "current_user",
          userField: "id",
        },
        { name: "ordered_at", source: "current_date", dateFormat: "iso" },
      ],
      confirmBeforeFire: true,
      confirmCopy:
        "Trigger the cement order workflow? This creates a PO and dispatches the vendor order via Playwright. The action is not trivially reversible.",
      successBehavior: "toast",
      successToastMessage: "Cement order workflow started.",
    },
  }),
)(RegisteredButton)


// ─── 3. navigate-to-pulse ─────────────────────────────────────────


export const NavigateToPulseButton = registerComponent(
  buttonRegistration({
    name: "navigate-to-pulse",
    displayName: "Go to Pulse",
    description:
      "Navigates to the user's Home Pulse surface. Cross-vertical — every authenticated tenant user has Pulse home at /home per BRIDGEABLE_MASTER §3.26.1.1. No action_config parameters; the route is fixed.",
    category: "navigation",
    verticals: ["manufacturing", "funeral_home", "cemetery", "crematory"],
    defaultLabel: "Pulse",
    defaultVariant: "ghost",
    defaultSize: "sm",
    defaultIconName: "Home",
    contract: {
      actionType: "navigate",
      actionConfig: { route: "/home" },
      parameterBindings: [],
      successBehavior: "stay",
    },
  }),
)(RegisteredButton)
