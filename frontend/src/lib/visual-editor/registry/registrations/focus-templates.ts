/**
 * Registry registrations — concrete Focus templates (examples).
 *
 * Two templates as Phase 1 examples — one Decision Focus
 * (Triage) and one Generation Focus (Arrangement Scribe). Each
 * adopts a base Focus type (declared via `extensions.focusType`)
 * and adds template-specific configurable props.
 *
 * Phase 3 backfill: configurableProps expanded from Phase 1's
 * minimal set to comprehensively describe template-specific
 * behavior. Triage: auto-advance, keyboard-overlay, items-per-
 * page. Arrangement: optional fields default, scribe panel
 * width, autosave interval, low-confidence threshold.
 */

import { registerComponent } from "../register"
import { makePlaceholder } from "./_placeholders"


registerComponent({
  type: "focus-template",
  name: "triage-decision",
  displayName: "Triage",
  description:
    "Decision Focus with triage as core element. Keyboard-driven decision stream over a queue of items. Two shipped queues today: task_triage (cross-vertical) and ss_cert_triage (manufacturing).",
  category: "decision-templates",
  verticals: ["all"],
  userParadigms: ["operator-power-user", "focused-executor"],
  consumedTokens: [
    "surface-raised",
    "surface-elevated",
    "border-base",
    "accent",
    "accent-subtle",
    "status-success",
    "status-error",
    "status-warning",
    "shadow-level-3",
    "radius-base",
    "text-h3",
    "text-body",
    "text-caption",
  ],
  configurableProps: {
    queueId: {
      type: "string",
      default: "task_triage",
      displayLabel: "Queue ID",
      description:
        "Identifier of the triage queue config to load (e.g., task_triage, ss_cert_triage).",
      required: true,
      bounds: { maxLength: 64 },
    },
    autoAdvance: {
      type: "boolean",
      default: true,
      displayLabel: "Auto-advance on action",
      description:
        "After approve/reject/skip, advance to the next item without operator input.",
    },
    advanceDelayMs: {
      type: "number",
      default: 250,
      bounds: [0, 2000],
      displayLabel: "Advance delay (ms)",
      description:
        "Brief pause between action commit and next-item display, so the operator sees the confirmation chrome flash.",
    },
    showContextPanel: {
      type: "boolean",
      default: true,
      displayLabel: "Show context panel",
      description: "Render the right-rail context panel.",
    },
    contextPanelLayout: {
      type: "enum",
      default: "right-rail",
      bounds: ["right-rail", "below", "modal"],
      displayLabel: "Context panel layout",
    },
    contextPanelWidth: {
      type: "number",
      default: 380,
      bounds: [240, 640],
      displayLabel: "Context panel width (px)",
      description: "Only applies when context panel layout is right-rail.",
    },
    showKeyboardShortcutsOverlay: {
      type: "boolean",
      default: true,
      displayLabel: "Show keyboard shortcuts overlay (?)",
      description:
        "Render a help overlay listing all bound shortcuts when the operator presses ?.",
    },
    itemsPerPage: {
      type: "number",
      default: 1,
      bounds: [1, 10],
      displayLabel: "Items rendered per page",
      description:
        "Single-item is canonical decision pace; >1 enables a list mode where multiple items render at once for batch review.",
    },
    confirmDestructiveActions: {
      type: "boolean",
      default: true,
      displayLabel: "Confirm destructive actions",
    },
    showAcknowledgedItems: {
      type: "boolean",
      default: false,
      displayLabel: "Show acknowledged items inline",
      description:
        "When true, processed items remain in view (faded) instead of disappearing.",
    },
  },
  slots: [
    {
      name: "actionPalette",
      displayLabel: "Action palette",
      acceptedTypes: ["composite"],
      description:
        "Per-queue action set rendered as keyboard-bindable buttons.",
    },
    {
      name: "contextPanels",
      displayLabel: "Context panels",
      acceptedTypes: ["composite"],
      description:
        "Document preview, related entities, AI summary, etc. Editor composes the per-queue mix.",
    },
  ],
  schemaVersion: 1,
  componentVersion: 2,
  extensions: {
    focusType: "decision",
    canonicalQueues: ["task_triage", "ss_cert_triage"],
  },
})(makePlaceholder("Triage Decision Focus Template"))


registerComponent({
  type: "focus-template",
  name: "arrangement-scribe",
  displayName: "Arrangement Scribe",
  description:
    "Generation Focus template for funeral arrangement intake. Conversational adapter (voice-to-structured-data) feeds a 70-field case file via AI extraction with confidence-scored line items. The director conducts a natural conversation; the scribe captures structured data.",
  category: "generation-templates",
  verticals: ["funeral_home"],
  userParadigms: ["operator-power-user", "owner-operator"],
  consumedTokens: [
    "surface-raised",
    "surface-elevated",
    "surface-sunken",
    "border-base",
    "border-accent",
    "accent",
    "accent-subtle",
    "status-success",
    "status-warning",
    "shadow-level-3",
    "radius-base",
    "text-display",
    "text-h3",
    "text-body",
    "text-body-sm",
    "duration-settle",
    "ease-settle",
  ],
  configurableProps: {
    intakeMethod: {
      type: "enum",
      default: "voice",
      bounds: ["voice", "transcript-paste", "manual-form"],
      displayLabel: "Intake method",
      description:
        "Voice = real-time transcription + extraction. Transcript-paste = post-call review. Manual-form = form fallback.",
    },
    confidenceThreshold: {
      type: "number",
      default: 0.85,
      bounds: [0.5, 1],
      displayLabel: "Auto-accept confidence threshold",
      description:
        "Extraction confidence above this auto-fills the field; below requires review.",
    },
    showFieldGrouping: {
      type: "boolean",
      default: true,
      displayLabel: "Show field-grouping headers",
      description:
        "Render section headers (Decedent, Service, Informant, etc.) above field clusters.",
    },
    showOptionalFieldsByDefault: {
      type: "boolean",
      default: false,
      displayLabel: "Show optional fields by default",
      description:
        "When false, optional fields are collapsed under an 'Add more details' affordance.",
    },
    primaryAccentToken: {
      type: "tokenReference",
      default: "accent",
      tokenCategory: "accent",
      displayLabel: "Primary accent",
    },
    scribePanelWidth: {
      type: "number",
      default: 420,
      bounds: [280, 720],
      displayLabel: "Scribe panel width (px)",
      description: "Right-rail conversation transcript panel width.",
    },
    autosaveIntervalSeconds: {
      type: "number",
      default: 10,
      bounds: [3, 60],
      displayLabel: "Autosave interval (seconds)",
    },
    showLowConfidenceWarnings: {
      type: "boolean",
      default: true,
      displayLabel: "Show low-confidence warnings inline",
      description:
        "Render the warning icon next to fields below the confidence threshold.",
    },
    voiceWaveformVisualization: {
      type: "enum",
      default: "bars",
      bounds: ["bars", "wave", "minimal", "off"],
      displayLabel: "Voice waveform style",
      description:
        "Visualization for the active microphone input. 'off' hides the waveform entirely.",
    },
    completionThreshold: {
      type: "number",
      default: 0.7,
      bounds: [0, 1],
      displayLabel: "Completion threshold",
      description:
        "Required fields populated ratio before the commit affordance enables.",
    },
  },
  slots: [
    {
      name: "intakeAdapter",
      displayLabel: "Intake adapter",
      acceptedTypes: ["composite"],
      maxChildren: 1,
      description:
        "Voice / transcript / manual intake adapter. Editor swaps adapters per template instance.",
    },
    {
      name: "extractionReview",
      displayLabel: "Extraction review",
      acceptedTypes: ["composite"],
      maxChildren: 1,
    },
  ],
  schemaVersion: 1,
  componentVersion: 2,
  extensions: {
    focusType: "generation",
    targetEntity: "fh_case",
    extractionPromptKey: "scribe.extract_first_call",
  },
})(makePlaceholder("Arrangement Scribe Generation Focus Template"))


// ─── Production Focus templates ────────────────────────────────
// Templates that map to actual registered Focus instances in the
// runtime registry (frontend/src/contexts/focus-registry.ts). When
// the editor renders a preview for these templates, it shows the
// real production surface (e.g. SchedulingKanbanCore) wrapped in
// the accessory layer rendered from a focus_compositions row.
//
// `compositionFocusType` carries the lookup key the runtime uses
// per the May 2026 composition runtime integration phase
// (decoupling descriptive Focus id from composition focus_type).


registerComponent({
  type: "focus-template",
  name: "funeral-scheduling",
  displayName: "Funeral Scheduling",
  description:
    "Decision Focus for the funeral home dispatcher's daily planning workspace. Bespoke kanban core (SchedulingKanbanCore) handles drag-drop, finalize, ancillary pin; composition layer authors accessory widgets (today, recent_activity, anomalies) in a sidebar rail.",
  category: "decision-templates",
  verticals: ["funeral_home"],
  userParadigms: ["operator-power-user", "focused-executor"],
  consumedTokens: [
    "surface-base",
    "surface-elevated",
    "surface-raised",
    "border-base",
    "border-subtle",
    "accent",
    "accent-subtle",
    "status-success",
    "status-warning",
    "shadow-level-2",
    "radius-base",
    "text-h3",
    "text-body",
  ],
  configurableProps: {
    showAccessoryRail: {
      type: "boolean",
      default: true,
      displayLabel: "Show accessory rail",
      description:
        "When false, the kanban core renders at full width with no composition-authored sidebar. Useful for narrow viewports or kiosk-mode scheduling stations.",
    },
    accessoryRailWidth: {
      type: "number",
      default: 288,
      bounds: [240, 480],
      displayLabel: "Accessory rail width (px)",
      description:
        "Width of the right-side accessory region. Cap is 480px so the kanban core retains usable lane width on standard monitors.",
    },
    showFinalizeAction: {
      type: "boolean",
      default: true,
      displayLabel: "Show Finalize action",
      description:
        "Render the Finalize button above the kanban. When false, schedule finalization happens via API only (e.g., for read-only preview tenants).",
    },
    daySelectorStyle: {
      type: "enum",
      default: "popover-with-flanking-boxes",
      bounds: ["popover-with-flanking-boxes", "popover-only", "minimal"],
      displayLabel: "Day selector style",
      description:
        "Header treatment — flanking date boxes + popover (canonical), popover trigger only, or minimal arrow buttons.",
    },
    showAncillaryPin: {
      type: "boolean",
      default: true,
      displayLabel: "Show ancillary pool pin",
      description: "Render the right-side ancillary pool pin widget.",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
  extensions: {
    focusType: "decision",
    compositionFocusType: "scheduling",
    productionRegistryId: "funeral-scheduling",
  },
})(makePlaceholder("Funeral Scheduling Decision Focus Template"))
