/**
 * Funeral Scheduling Focus registration — Phase B Session 4 Phase 4.2,
 * extended for Phase 4.3b.3 ancillary pool pin widget.
 *
 * Side-effect module: importing this file
 *   - Registers the funeral-scheduling Focus with the focus registry
 *     so `useFocus().open("funeral-scheduling", ...)` resolves to the
 *     SchedulingKanbanCore.
 *   - Registers the AncillaryPoolPin component with the canvas widget
 *     renderer registry under `"funeral-scheduling.ancillary-pool"`
 *     so the canvas framework can dispatch it via `getWidgetRenderer`.
 *
 * Imported once at app bootstrap (see App.tsx) alongside other
 * registries that follow the side-effect-on-import pattern.
 *
 * Default layout
 * ──────────────
 * The funeral-scheduling Focus's `defaultLayout.tenantDefault` seeds
 * the AncillaryPoolPin at right-rail anchor (~260px wide × ~70vh
 * tall). The right-rail anchor is one of the 8 canonical widget
 * anchors (focus-registry.ts). User can drag-reposition via
 * WidgetChrome — the position then persists per-user via Phase A
 * Session 4's focus_sessions table.
 *
 * Width 260px chosen to balance content visibility (5+ pool items
 * visible at once at typical row height) against canvas real estate
 * (kanban core needs ~1100px+ to render comfortably with all driver
 * lanes; right-rail 260 leaves the core that space at vw=1500+).
 * Height auto-sized via `height: 70vh` analog from StackRail —
 * generous enough for overflow scroll, short enough to hint the
 * pin is one widget among potentially several.
 */

import { registerFocus } from "@/contexts/focus-registry"
import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers"

import { AncillaryPoolPin } from "./AncillaryPoolPin"
import { SchedulingKanbanCore } from "./SchedulingKanbanCore"


// Phase 4.3b.3 — register the AncillaryPoolPin component before the
// Focus config that references it. Order matters because
// registerFocus's defaultLayout.tenantDefault declares
// `widgetType: "funeral-scheduling.ancillary-pool"`, and Canvas calls
// getWidgetRenderer(widgetType) at render time — the resolver
// returns MockSavedViewWidget if the type isn't registered. Both
// register* calls are synchronous + idempotent; the order is for
// reader clarity, not behavioral correctness.
registerWidgetRenderer(
  "funeral-scheduling.ancillary-pool",
  AncillaryPoolPin,
)


registerFocus({
  id: "funeral-scheduling",
  mode: "kanban",
  displayName: "Funeral Scheduling",
  coreComponent: SchedulingKanbanCore,
  // Phase 4.3b.3 — seed the ancillary pool pin in tenantDefault.
  // User can drag-reposition; Phase A Session 4's focus_sessions
  // persistence remembers the override per-user.
  //
  // Position: right-rail anchor, offset (16, 16) — sits near the
  // top-right corner of the canvas, hugging the right edge for the
  // full vertical extent. Width 260px provides comfortable row
  // visibility; height 600px (capped by the canvas's available
  // height at canvas tier) shows ~10 rows before scroll.
  defaultLayout: {
    tenantDefault: {
      widgets: {
        "ancillary-pool": {
          widgetType: "funeral-scheduling.ancillary-pool",
          position: {
            anchor: "right-rail",
            offsetX: 16,
            offsetY: 16,
            width: 260,
            height: 600,
          },
        },
      },
    },
  },
})
