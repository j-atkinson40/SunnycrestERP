/**
 * Registry registrations — the five Focus primitive types.
 *
 * Per BRIDGEABLE_MASTER §3.26.11, the platform has five canonical
 * Focus types: Decision, Coordination, Execution, Review,
 * Generation. Each type is an abstract category — concrete
 * Focuses (e.g., "Triage Decision Focus", "Funeral Scheduling
 * Coordination Focus") are templates that adopt one of these
 * types.
 *
 * Phase 1 registered the types with placeholder components. Phase 3
 * backfills configurableProps that describe characteristics shared
 * by all instances of each type — type-level header style, action-
 * button placement, content density, transition style. Concrete
 * templates inherit these defaults and may override per-template.
 */

import { registerComponent } from "../register"
import { makePlaceholder } from "./_placeholders"


// ─── Shared type-level configurable props ────────────────────
// Patterns repeated across the five Focus types. Declared once
// here so each type's registration stays readable.

const SHARED_FOCUS_PROPS = {
  density: {
    type: "enum" as const,
    default: "comfortable",
    bounds: ["compact", "comfortable", "spacious"],
    displayLabel: "Content density",
    description:
      "Vertical spacing inside the Focus shell. Affects all instances of this Focus type.",
  },
  headerStyle: {
    type: "enum" as const,
    default: "serif-display",
    bounds: ["serif-display", "sans-emphasis", "minimal"],
    displayLabel: "Header style",
    description:
      "Title typography treatment in the Focus header.",
  },
  showCloseButton: {
    type: "boolean" as const,
    default: true,
    displayLabel: "Show close button",
    description: "Render the X close affordance in the top-right.",
  },
  transitionStyle: {
    type: "enum" as const,
    default: "settle",
    bounds: ["settle", "gentle", "instant"],
    displayLabel: "Open/close transition",
    description: "Easing applied when the Focus shell opens or closes.",
  },
  shellAccentToken: {
    type: "tokenReference" as const,
    default: "border-accent",
    tokenCategory: "border" as const,
    displayLabel: "Shell accent border",
    description: "Token coloring the shell's accent edge.",
  },
}


registerComponent({
  type: "focus",
  name: "decision",
  displayName: "Decision Focus",
  description:
    "Bounded decision primitive. User answers a question, optionally with triage as a core element. Outcome flow closes the Focus.",
  category: "focus-type",
  verticals: ["all"],
  userParadigms: ["operator-power-user", "focused-executor"],
  consumedTokens: [
    "surface-raised",
    "surface-elevated",
    "border-base",
    "border-accent",
    "accent",
    "shadow-level-3",
    "radius-base",
  ],
  configurableProps: {
    ...SHARED_FOCUS_PROPS,
    autoCloseOnDecision: {
      type: "boolean",
      default: true,
      displayLabel: "Auto-close on outcome",
      description:
        "Close the Focus automatically when the decision flow reaches a terminal outcome.",
    },
    pushBackToPulse: {
      type: "boolean",
      default: true,
      displayLabel: "Push back to Pulse on dismiss",
      description:
        "When the user dismisses without deciding, surface the unresolved item back into Pulse.",
    },
    actionButtonLayout: {
      type: "enum",
      default: "horizontal-right",
      bounds: ["horizontal-right", "horizontal-center", "vertical-stack"],
      displayLabel: "Action button layout",
      description:
        "Placement of the primary + secondary decision buttons.",
    },
    confirmLabel: {
      type: "string",
      default: "Confirm",
      displayLabel: "Confirm button label",
      description: "Default label on the primary decision button.",
      bounds: { maxLength: 32 },
    },
    cancelLabel: {
      type: "string",
      default: "Cancel",
      displayLabel: "Cancel button label",
      bounds: { maxLength: 32 },
    },
  },
  schemaVersion: 1,
  componentVersion: 2,
})(makePlaceholder("Decision Focus"))


registerComponent({
  type: "focus",
  name: "coordination",
  displayName: "Coordination Focus",
  description:
    "Multi-primitive integration substrate. Coordinates work across email/calendar/SMS/phone/messaging plus Generation Focus and sub-Focus hierarchy. Five canonical templates (load, job, pour-week, mold-changeover, quality-issue).",
  category: "focus-type",
  verticals: ["all"],
  userParadigms: ["operator-power-user", "owner-operator"],
  consumedTokens: [
    "surface-raised",
    "surface-elevated",
    "border-base",
    "accent",
    "accent-subtle",
    "shadow-level-3",
    "radius-base",
    "text-h3",
    "text-body",
  ],
  configurableProps: {
    ...SHARED_FOCUS_PROPS,
    autoClosureRule: {
      type: "enum",
      default: "all-children-complete",
      bounds: ["all-children-complete", "manual", "scheduled"],
      displayLabel: "Auto-closure rule",
      description:
        "When this Focus type's instances close automatically.",
    },
    participantScope: {
      type: "enum",
      default: "tenant-only",
      bounds: ["tenant-only", "cross-tenant", "magic-link"],
      displayLabel: "Participant scope",
      description:
        "Default participant scope across all instances of this Focus type.",
    },
    showSubFocusBreadcrumbs: {
      type: "boolean",
      default: true,
      displayLabel: "Show sub-Focus breadcrumbs",
      description:
        "When inside a child Focus (e.g., Load), show the parent Job breadcrumb at the top.",
    },
    timelineDefaultView: {
      type: "enum",
      default: "list",
      bounds: ["list", "timeline", "kanban"],
      displayLabel: "Timeline default view",
      description: "Initial view mode for coordination state.",
    },
    showParticipantAvatars: {
      type: "boolean",
      default: true,
      displayLabel: "Show participant avatars",
    },
  },
  slots: [
    {
      name: "subFocuses",
      displayLabel: "Sub-Focus hierarchy",
      acceptedTypes: ["focus", "focus-template"],
      description:
        "Per-template sub-Focus declaration (e.g., Job → Load canonical hierarchy at September scope).",
    },
  ],
  schemaVersion: 1,
  componentVersion: 2,
})(makePlaceholder("Coordination Focus"))


registerComponent({
  type: "focus",
  name: "execution",
  displayName: "Execution Focus",
  description:
    "Bounded task-completion primitive. User executes a known procedure step-by-step; closure happens when the procedure terminates.",
  category: "focus-type",
  verticals: ["all"],
  userParadigms: ["focused-executor", "operator-power-user"],
  consumedTokens: [
    "surface-raised",
    "border-base",
    "accent",
    "shadow-level-3",
    "radius-base",
    "text-body",
    "text-caption",
  ],
  configurableProps: {
    ...SHARED_FOCUS_PROPS,
    confirmOnComplete: {
      type: "boolean",
      default: false,
      displayLabel: "Confirm on complete",
      description:
        "Require an explicit confirmation step before transitioning to closure.",
    },
    showStepProgress: {
      type: "boolean",
      default: true,
      displayLabel: "Show step progress indicator",
    },
    progressStyle: {
      type: "enum",
      default: "numeric",
      bounds: ["numeric", "bar", "dots"],
      displayLabel: "Progress indicator style",
      description:
        "Numeric ('Step 2 of 4'), bar (filled progress bar), or dots (per-step indicator).",
    },
    allowSkipSteps: {
      type: "boolean",
      default: false,
      displayLabel: "Allow skipping steps",
      description:
        "When true, the operator can advance past a step without completing it.",
    },
    completionMessage: {
      type: "string",
      default: "Done.",
      displayLabel: "Completion message",
      bounds: { maxLength: 80 },
    },
  },
  schemaVersion: 1,
  componentVersion: 2,
})(makePlaceholder("Execution Focus"))


registerComponent({
  type: "focus",
  name: "review",
  displayName: "Review Focus",
  description:
    "State-review primitive. User reviews a queue or single item, optionally taking a bounded approve/reject action. Closes when the queue is exhausted or the user dismisses.",
  category: "focus-type",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user"],
  consumedTokens: [
    "surface-raised",
    "surface-elevated",
    "border-subtle",
    "accent",
    "status-success",
    "status-error",
    "shadow-level-3",
    "radius-base",
  ],
  configurableProps: {
    ...SHARED_FOCUS_PROPS,
    advanceOnAction: {
      type: "boolean",
      default: true,
      displayLabel: "Auto-advance on action",
      description:
        "After approve/reject, advance to the next item rather than closing.",
    },
    queueOrdering: {
      type: "enum",
      default: "priority",
      bounds: ["priority", "fifo", "due-date"],
      displayLabel: "Queue ordering",
    },
    showQueueProgress: {
      type: "boolean",
      default: true,
      displayLabel: "Show queue progress (N of M)",
    },
    approveLabel: {
      type: "string",
      default: "Approve",
      displayLabel: "Approve button label",
      bounds: { maxLength: 24 },
    },
    rejectLabel: {
      type: "string",
      default: "Reject",
      displayLabel: "Reject button label",
      bounds: { maxLength: 24 },
    },
    confirmRejection: {
      type: "boolean",
      default: true,
      displayLabel: "Confirm rejection",
      description:
        "Require a confirmation modal + reason text before applying a reject.",
    },
  },
  schemaVersion: 1,
  componentVersion: 2,
})(makePlaceholder("Review Focus"))


registerComponent({
  type: "focus",
  name: "generation",
  displayName: "Generation Focus",
  description:
    "Producer Focus type. Creates new vault items via canvas + palette + AI-extraction-review + parametric authoring. Output commit closes the Focus. Six canonical adapter categories (manual, extraction, conversational, visual, ingestion, aggregation).",
  category: "focus-type",
  verticals: ["all"],
  userParadigms: ["operator-power-user", "owner-operator"],
  consumedTokens: [
    "surface-raised",
    "surface-elevated",
    "border-base",
    "border-accent",
    "accent",
    "accent-subtle",
    "shadow-level-3",
    "radius-base",
    "text-display",
    "text-body",
    "duration-settle",
    "ease-settle",
  ],
  configurableProps: {
    ...SHARED_FOCUS_PROPS,
    operationalMode: {
      type: "enum",
      default: "interactive",
      bounds: ["interactive", "headless"],
      displayLabel: "Operational mode",
      description:
        "Interactive: operator authors + commits. Headless: workflow invokes generation logic; output enters review queue.",
    },
    draftLifetimeDays: {
      type: "number",
      default: 90,
      bounds: [30, 365],
      displayLabel: "Draft lifetime (days)",
      description:
        "Tenant-configurable retention for in-progress draft state.",
    },
    requireReviewBeforeActive: {
      type: "boolean",
      default: true,
      displayLabel: "Review-by-default for headless output",
      description:
        "Headless-generated output requires human review before active state. Manual-entry interactive mode bypasses review.",
    },
    autosaveIntervalSeconds: {
      type: "number",
      default: 15,
      bounds: [5, 120],
      displayLabel: "Autosave interval (seconds)",
      description:
        "How often draft state is persisted while authoring is in progress.",
    },
    confidenceWarningThreshold: {
      type: "number",
      default: 0.85,
      bounds: [0, 1],
      displayLabel: "Confidence warning threshold",
      description:
        "Extracted line items below this confidence flag for explicit review.",
    },
    canvasDefaultZoom: {
      type: "number",
      default: 1,
      bounds: [0.25, 4],
      displayLabel: "Canvas default zoom",
    },
  },
  slots: [
    {
      name: "canvas",
      displayLabel: "Canvas surface",
      acceptedTypes: ["composite"],
      maxChildren: 1,
    },
    {
      name: "palette",
      displayLabel: "Palette",
      acceptedTypes: ["composite"],
      maxChildren: 1,
    },
  ],
  schemaVersion: 1,
  componentVersion: 2,
})(makePlaceholder("Generation Focus"))
