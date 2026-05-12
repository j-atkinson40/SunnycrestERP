/**
 * Registry registrations — scheduling-focus widgets (Arc 1).
 *
 * Separate shim file from `./widgets.ts` so the dispatch widget
 * cluster owns its visual-editor metadata alongside the existing
 * `dispatch/scheduling-focus/register.ts` canvas-renderer cluster.
 *
 * AncillaryPoolPin is Group E from the Arc 1 investigation — the
 * sole non-foundation/non-manufacturing-cluster widget in the lift
 * scope. Context-coupling already resolved (R-5.0.5 lineage): the
 * component calls `useSchedulingFocusOptional()` and degrades
 * gracefully when rendered outside the FH Focus subtree, so it is
 * safe to wrap + emit `data-component-name` on Pulse / spaces_pin
 * / focus_canvas surfaces.
 *
 * R-1.6.12 Path 1: register the wrapped component here; the canvas
 * registry at `dispatch/scheduling-focus/register.ts` imports the
 * wrapped version + casts through `unknown` to ComponentType<
 * WidgetRendererProps> (same pattern as other Path-1 widgets).
 *
 * Naming convention (per Arc 1 investigation §5 observation):
 *   - Visual-editor metadata `name`: "ancillary-pool" (clean slug;
 *     matches `widget:<slug>` convention from R-1.6.12).
 *   - Canvas registry key: "scheduling.ancillary-pool" (matches
 *     backend `widget_id` in WIDGET_DEFINITIONS; load-bearing for
 *     CI parity test).
 *   - The two are intentionally distinct: visual-editor metadata
 *     describes the component for the editor; canvas key matches
 *     the backend SOT. The mapping is one-way (visual-editor
 *     metadata is the truth for editor lookups; canvas key is the
 *     truth for runtime dispatch).
 */

import { AncillaryPoolPin as AncillaryPoolPinRaw } from "@/components/dispatch/scheduling-focus/AncillaryPoolPin"

import { registerComponent } from "../register"


// ─── ancillary-pool (Group E — dispatch/scheduling-focus) ────────
export const AncillaryPoolPin = registerComponent({
  type: "widget",
  name: "ancillary-pool",
  displayName: "Ancillary Pool",
  description:
    "Scheduling-focus widget surfacing the pool of unassigned ancillary items (urns + accessories awaiting attachment to a delivery). Renders on Pulse, spaces_pin, focus_canvas, focus_stack. Uses useSchedulingFocusOptional so it degrades gracefully outside the FH Focus subtree (R-5.0.5 lineage). View-only per §12.6a in non-Focus surfaces; drag-attach interactions only fire inside the scheduling Focus's DnD context.",
  category: "scheduling-focus",
  verticals: ["funeral_home"],
  userParadigms: ["operator-power-user", "focused-executor"],
  consumedTokens: [
    "surface-elevated",
    "surface-sunken",
    "border-subtle",
    "border-accent",
    "content-strong",
    "content-base",
    "content-muted",
    "accent",
    "accent-subtle",
    "status-warning",
    "radius-base",
    "shadow-level-1",
    "text-body-sm",
    "text-caption",
    "text-micro",
  ],
  configurableProps: {
    showPoolCount: {
      type: "boolean",
      default: true,
      displayLabel: "Show pool count",
      description:
        "Show numeric count of unassigned ancillary items in header chrome.",
    },
    maxItemsBrief: {
      type: "number",
      default: 5,
      bounds: [1, 20],
      displayLabel: "Max items in Brief variant",
      description:
        "Cap on pool rows rendered in Brief variant (spaces_pin Glance shows count only; Detail/focus_canvas renders all).",
    },
    showItemThumbnails: {
      type: "boolean",
      default: false,
      displayLabel: "Show item thumbnails",
      description:
        "Render product thumbnails alongside item labels (urns + accessories with R2 image keys).",
    },
    pinWidth: {
      type: "number",
      default: 180,
      bounds: [120, 320],
      displayLabel: "Pin width (focus_canvas)",
      description:
        "Pixel width when rendered in focus_canvas surface. Aesthetic Arc Session 1 narrowed from 260 → 180 so the pin fits canvas tier alongside the kanban without forcing stack-tier fallback. Pulse / spaces_pin surfaces ignore this prop.",
    },
    emptyStateText: {
      type: "string",
      default: "No unassigned items",
      displayLabel: "Empty state text",
      description: "Copy shown when the ancillary pool is empty.",
      bounds: { maxLength: 80 },
    },
    accentToken: {
      type: "tokenReference",
      default: "accent",
      tokenCategory: "accent",
      displayLabel: "Accent token",
      description: "Token coloring active drag-source highlights.",
    },
  },
  variants: [
    { name: "glance", displayLabel: "Glance" },
    { name: "brief", displayLabel: "Brief" },
    { name: "detail", displayLabel: "Detail" },
  ],
  extensions: {
    // Forward-compat — visual-editor slug and canvas key differ.
    // Reverse-lookup mechanisms can read this field to find the
    // canvas registry entry.
    canvasKey: "scheduling.ancillary-pool",
  },
  schemaVersion: 1,
  componentVersion: 1,
})(AncillaryPoolPinRaw)
