/**
 * Registry registrations — Focus Builder placeholder widgets (sub-arc F-3).
 *
 * Three inert placeholder widgets that demonstrate the F-3 palette →
 * drag → canvas pipeline end-to-end. Real implementations land in
 * vertical-specific arcs.
 *
 * Each registers as `kind: "widget"`, `canvasPlaceable: true`, with a
 * narrow `configurableProps` surface for the F-3 inspector to render.
 */
import {
  DayStripWidget as DayStripRaw,
  TodayPinWidget as TodayPinRaw,
  MapPlaceholderWidget as MapPlaceholderRaw,
} from "@/components/widgets/focus-builder/PlaceholderWidgets"

import { registerComponent } from "../register"

export const DayStripWidget = registerComponent({
  type: "widget",
  name: "day-strip-widget",
  displayName: "Day Strip",
  description: "Seven-day strip with today highlighted (placeholder).",
  category: "focus-builder",
  verticals: ["all"],
  userParadigms: ["all"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "shadow-level-1",
    "content-strong",
    "content-muted",
  ],
  canvasPlaceable: true,
  canvasMetadata: {
    minDimensions: { columns: 4, rows: 1 },
    defaultDimensions: { columns: 12, rows: 1 },
    // FF-2 — pixel defaults for free-form Decide canvas (per Q-5).
    freeFormDefaultDimensions: { width: 240, height: 120 },
    freeFormMinDimensions: { width: 120, height: 64 },
    resizable: true,
  },
  configurableProps: {
    daysVisible: {
      type: "number",
      default: 7,
      bounds: [1, 14],
      displayLabel: "Days visible",
      description: "How many day cells to render in the strip.",
    },
    highlightToday: {
      type: "boolean",
      default: true,
      displayLabel: "Highlight today",
      description: "Whether the current day cell renders with emphasis.",
    },
    weekStartsOn: {
      type: "enum",
      default: "sunday",
      bounds: ["sunday", "monday"],
      displayLabel: "Week starts on",
      description: "Which weekday anchors the strip.",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
})(DayStripRaw)

export const TodayPinWidget = registerComponent({
  type: "widget",
  name: "today-pin-widget",
  displayName: "Today Pin",
  description: "Pinned summary of today's items (placeholder).",
  category: "focus-builder",
  verticals: ["all"],
  userParadigms: ["all"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "shadow-level-1",
    "content-strong",
    "content-muted",
  ],
  canvasPlaceable: true,
  canvasMetadata: {
    minDimensions: { columns: 2, rows: 1 },
    defaultDimensions: { columns: 4, rows: 1 },
    // FF-2 — pixel defaults for free-form Decide canvas (per Q-5).
    freeFormDefaultDimensions: { width: 240, height: 120 },
    freeFormMinDimensions: { width: 120, height: 64 },
    resizable: true,
  },
  configurableProps: {
    showCount: {
      type: "boolean",
      default: true,
      displayLabel: "Show count",
      description: "Whether to surface a numeric item count.",
    },
    compact: {
      type: "boolean",
      default: false,
      displayLabel: "Compact density",
      description: "Tighter padding for narrow rail placements.",
    },
    label: {
      type: "string",
      default: "Today",
      displayLabel: "Label",
      description: "Pin label rendered above the count.",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
})(TodayPinRaw)

export const MapPlaceholderWidget = registerComponent({
  type: "widget",
  name: "map-placeholder-widget",
  displayName: "Map",
  description: "Geographic context for placements (placeholder).",
  category: "focus-builder",
  verticals: ["all"],
  userParadigms: ["all"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "shadow-level-2",
    "content-strong",
    "content-muted",
  ],
  canvasPlaceable: true,
  canvasMetadata: {
    minDimensions: { columns: 4, rows: 2 },
    defaultDimensions: { columns: 8, rows: 3 },
    // FF-2 — pixel defaults for free-form Decide canvas (per Q-5).
    // Map naturally wants a square footprint — wider/taller than the
    // strip + pin widgets.
    freeFormDefaultDimensions: { width: 400, height: 400 },
    freeFormMinDimensions: { width: 200, height: 200 },
    resizable: true,
  },
  configurableProps: {
    zoom: {
      type: "number",
      default: 10,
      bounds: [1, 20],
      displayLabel: "Zoom level",
      description: "Initial map zoom (placeholder, no map renders yet).",
    },
    showLegend: {
      type: "boolean",
      default: false,
      displayLabel: "Show legend",
      description: "Whether to render the placement-color legend pane.",
    },
    aspect: {
      type: "enum",
      default: "wide",
      bounds: ["square", "wide"],
      displayLabel: "Aspect",
      description: "Map render aspect; square for narrow rails, wide for canvas rows.",
    },
  },
  schemaVersion: 1,
  componentVersion: 1,
})(MapPlaceholderRaw)
