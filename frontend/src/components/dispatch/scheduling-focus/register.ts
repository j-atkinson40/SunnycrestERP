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
 * the AncillaryPoolPin at right-rail anchor (180px wide, was 260
 * pre-Aesthetic-Arc-Session-1). The right-rail anchor is one of the
 * 8 canonical widget anchors (focus-registry.ts). User can drag-
 * reposition via WidgetChrome — the position then persists per-user
 * via Phase A Session 4's focus_sessions table.
 *
 * Aesthetic Arc Session 1 Commit C — pin narrowed from 260 → 180px
 * so it fits in canvas tier alongside the kanban (CANVAS_RESERVED_
 * MARGIN bumped 100→220 in geometry.ts). Pre-Session-1 the 260px
 * pin always exceeded the canvas-tier reserved margin, forcing
 * stack tier → core left-anchored → kanban not centered. Post-
 * Session-1 the pin is a peripheral reference (Section 0 Quietness
 * + Detail Concentration: pin is not primary work, should be
 * quietly available not visually competing) and fits in canvas
 * tier where computeCoreRect centers the core symmetrically.
 *
 * Width 180px is the new balance between content visibility (still
 * 4+ pool items visible at typical row height with truncated
 * labels) and canvas real estate (kanban core gets full breathing
 * room with the centered-by-construction canvas-tier formula).
 * Height 600 unchanged.
 */

import { registerFocus } from "@/contexts/focus-registry"
import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers"

import { AncillaryPoolPin } from "./AncillaryPoolPin"
import { SchedulingFocusWithAccessories } from "./SchedulingFocusWithAccessories"


// Phase 4.3b.3 — register the AncillaryPoolPin component before the
// Focus config that references it. Order matters because
// registerFocus's defaultLayout.tenantDefault declares the same
// widgetType, and Canvas calls getWidgetRenderer(widgetType) at
// render time — the resolver returns MissingWidgetEmptyState if the
// type isn't registered. Both register* calls are synchronous +
// idempotent; the order is for reader clarity, not behavioral
// correctness.
//
// Phase W-4a Cleanup Session B.2 — registration key migrated from
// the legacy `funeral-scheduling.ancillary-pool` to the canonical
// backend key `scheduling.ancillary-pool` (matches
// `widget_registry.py::WIDGET_DEFINITIONS` entry). Pre-Session-B.2
// the key mismatch caused Pulse-rendered ancillary-pool slots to
// resolve via the empty-slot filter (§13.4.3 platform-composed
// silent filter) — symptom hidden but architecturally wrong.
// Backend key is the canonical SOT; frontend registers under the
// matching key. CI parity test (`widget-renderer-parity.test.ts`)
// catches any future drift.
registerWidgetRenderer(
  "scheduling.ancillary-pool",
  AncillaryPoolPin,
)


registerFocus({
  id: "funeral-scheduling",
  mode: "kanban",
  displayName: "Funeral Scheduling",
  coreComponent: SchedulingFocusWithAccessories,
  // May 2026 — composition runtime integration phase. The seeded
  // scheduling composition is keyed by `focus_type="scheduling"`
  // (categorization) while the registered Focus id is the
  // descriptive `"funeral-scheduling"`. The accessory layer wrapper
  // (introduced this phase) resolves compositions via this field
  // rather than the registered id. See focus-registry.ts
  // `compositionFocusType` field doc for full rationale.
  compositionFocusType: "scheduling",
  // Phase 4.3b.3 seed, refined through Aesthetic Arc Session 1
  // (Commit C: width narrowed 260 → 180 so the pin fits in canvas
  // tier and kanban centers via computeCoreRect's canvas-tier
  // formula) and Session 1.5 (height: 600 → "auto" + maxHeight: 480
  // per the new Widget Content Sizing principle in PLATFORM_PRODUCT
  // _PRINCIPLES.md). User can drag-reposition; Phase A Session 4's
  // focus_sessions persistence remembers the override per-user.
  //
  // Position: right-rail anchor, offset (16, 16) — sits near the
  // top-right corner of the canvas. Width 180px fits in the post-
  // Session-1 CANVAS_RESERVED_MARGIN=220 band.
  //
  // Aesthetic Arc Session 1.5 — height "auto" + maxHeight 480:
  //   • Empty state: pin fits to ~120px (header + small empty copy)
  //   • 1 pool item: ~150px (header + 1 row + padding)
  //   • 5 items: ~280px
  //   • 10+ items: hits maxHeight=480, WidgetChrome's overflow-y
  //     auto handles scroll at the chrome level
  // Section 0 Restraint TP3: empty internal space is decorative
  // chrome, removed. Pin claims only the visual real estate its
  // content actually needs.
  defaultLayout: {
    tenantDefault: {
      widgets: {
        "ancillary-pool": {
          widgetType: "scheduling.ancillary-pool",
          // Widget Library Phase W-1 — Section 12.10 reference:
          // AncillaryPoolPin declares Glance + Brief + Detail
          // variants in the backend WIDGET_DEFINITIONS catalog.
          // Funeral Scheduling Focus seeds the Detail variant
          // (full scrollable list with drag-source affordance) on
          // canvas tier per Section 12.5 default. Stack tier
          // crossfade renders the same instance with surface=
          // "focus_stack" — the component switches internally on
          // surface discriminator (Decision 5 + 6).
          variant_id: "detail",
          position: {
            anchor: "right-rail",
            offsetX: 16,
            offsetY: 16,
            width: 180,
            height: "auto",
            maxHeight: 480,
          },
        },
      },
    },
  },
})
