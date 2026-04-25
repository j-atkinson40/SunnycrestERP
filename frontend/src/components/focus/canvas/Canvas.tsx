/**
 * Canvas — tier-dispatching widget region surrounding the anchored
 * Focus core. Phase A Session 3.7, continuous cascade Session 3.8.
 *
 * Three responsive tiers:
 *   - canvas: free-form placement (drag/resize, anchor positioning)
 *   - stack: right-rail Smart Stack (scroll-snap, tap-to-expand)
 *   - icon: floating button → bottom-sheet overlay (mobile-ready)
 *
 * Widget state (anchor, offset, size) is canonical across all tiers.
 * Tier is a pure render-time override — no state mutation when
 * transitioning between tiers. `useViewportTier` hook detects tier
 * and re-renders appropriately on window resize.
 *
 * Session 3.8 crossfade: all three renderers mount simultaneously;
 * visibility switches via `data-active` attribute + opacity/pointer-
 * events transitions. A tier change fades the old renderer out as
 * the new one fades in — simultaneous crossfade, not sequential —
 * matching the continuous-geometric-cascade model documented in
 * geometry.ts's `determineTier`.
 *
 * Session 3.8.2 — core + widget sizes no longer transition on
 * left/top/width/height. Session 3.8 tried a CSS transition on those
 * but user verification surfaced the transition-lag problem (each
 * resize event starts a new 300ms ease to new target, position
 * always trails viewport by ~150ms). Layout props now update
 * synchronously with viewport — macOS-Finder-style per-frame follow.
 * The tier-renderer opacity crossfade carries visual continuity at
 * tier boundaries; core/widget size changes instantly underneath.
 *
 * Pointer-events discipline (inherited from Session 3):
 *   - Canvas wrapper has `pointer-events: none` so backdrop clicks
 *     still reach Dialog.Backdrop for dismiss
 *   - Active tier's subtree re-enables pointer-events via
 *     `data-active=true` styling
 *   - Inactive tier subtrees keep `pointer-events: none` during fade
 *     so in-flight gestures can't hit a dimmed renderer
 */

import {
  useDndMonitor,
  type DragEndEvent,
} from "@dnd-kit/core"
import { useState } from "react"
import { useSearchParams } from "react-router-dom"

import { useFocus } from "@/contexts/focus-context"
import type { WidgetId, WidgetPosition } from "@/contexts/focus-registry"
import { cn } from "@/lib/utils"

import { BottomSheet } from "./BottomSheet"
import {
  clampPositionOffsets,
  computeCoreRect,
  computeOffsetsForAnchor,
  determineAnchorFromDrop,
  rectsOverlap,
  resolvePosition,
  snapTo8px,
} from "./geometry"
import { IconButton } from "./IconButton"
import { MockSavedViewWidget } from "./MockSavedViewWidget"
import { StackExpandedOverlay } from "./StackExpandedOverlay"
import { StackRail } from "./StackRail"
import { useViewportTier } from "./useViewportTier"
import { WidgetChrome } from "./WidgetChrome"


// Phase B Session 4.3b D-1 elevation. The canvas drag id has a
// `widget:` prefix so the elevated DndContext can discriminate canvas
// widget drags from kanban delivery / ancillary drags. WidgetChrome
// emits the prefixed id; this constant is the single source of truth
// for the prefix string used by both the producer (WidgetChrome) and
// the consumer (Canvas's handleDragEnd below).
const WIDGET_DRAG_PREFIX = "widget:"


export function Canvas() {
  const { currentFocus, updateSessionLayout, removeWidget } = useFocus()

  const [searchParams] = useSearchParams()
  const devMode = searchParams.get("dev-canvas") === "1"

  // Pre-4.3b Canvas owned its own `<DndContext>` with a local
  // PointerSensor. Phase 4.3b D-1 elevation moved the DndContext up
  // to FocusDndProvider so cross-context drag (canvas widget OR
  // canvas pin item → kanban lane) becomes possible. Canvas is now
  // a CONSUMER of the elevated context via `useDndMonitor` —
  // listener gates on the `widget:` id prefix, no-ops on every
  // other drag (delivery: / ancillary:). Sensors live in the
  // provider; same `distance: 8` activation constraint as before.

  const widgets = currentFocus?.layoutState?.widgets ?? {}
  // Session 3.7 fix — pass widgets so tier detection is content-aware.
  // If canvas reserved space can't hold the widgets at their canonical
  // sizes, tier transitions to stack. Focus.tsx must pass the same
  // widget set so Popup sizing stays in sync with Canvas rendering.
  const viewport = useViewportTier(widgets)
  const tier = viewport.tier

  // Stack-mode expand-overlay state + icon-mode sheet-open state.
  // Both local to Canvas; transitioning tiers resets naturally on
  // re-render.
  const [expandedWidgetId, setExpandedWidgetId] = useState<WidgetId | null>(
    null,
  )
  const [sheetOpen, setSheetOpen] = useState(false)

  function handleDragEnd(event: DragEndEvent) {
    // Drag only applies in canvas tier. Stack + icon tiers don't
    // mount WidgetChrome, so useDraggable never fires there.
    //
    // Phase 4.3b D-1 routing: the elevated DndContext also serves
    // delivery: and ancillary: drags. Canvas's listener early-
    // returns on every non-widget id, leaving those drags to the
    // SchedulingKanbanCore listener (separate useDndMonitor
    // subscriber).
    const { active, delta } = event
    const rawId = String(active.id)
    if (!rawId.startsWith(WIDGET_DRAG_PREFIX)) return
    const widgetId = rawId.slice(WIDGET_DRAG_PREFIX.length) as WidgetId
    const current = widgets[widgetId]
    if (!current) return

    const coreRect = computeCoreRect("canvas", viewport.width, viewport.height)
    const startRect = resolvePosition(
      current.position,
      viewport.width,
      viewport.height,
    )
    const dropRect = {
      x: snapTo8px(startRect.x + delta.x),
      y: snapTo8px(startRect.y + delta.y),
      width: startRect.width,
      height: startRect.height,
    }

    if (rectsOverlap(dropRect, coreRect)) return

    const dropCenterX = dropRect.x + dropRect.width / 2
    const dropCenterY = dropRect.y + dropRect.height / 2
    const newAnchor = determineAnchorFromDrop(
      dropCenterX,
      dropCenterY,
      viewport.width,
      viewport.height,
    )
    const rawOffsets = computeOffsetsForAnchor(
      newAnchor,
      dropRect,
      viewport.width,
      viewport.height,
    )
    const nextPosition: WidgetPosition = {
      anchor: newAnchor,
      offsetX: Math.max(0, snapTo8px(rawOffsets.offsetX)),
      offsetY: Math.max(0, snapTo8px(rawOffsets.offsetY)),
      width: dropRect.width,
      height: dropRect.height,
    }
    const clampedPosition = clampPositionOffsets(
      nextPosition,
      viewport.width,
      viewport.height,
    )
    updateSessionLayout({
      widgets: {
        [widgetId]: { position: clampedPosition },
      },
    })
  }

  // Subscribe to the elevated DndContext (provided by
  // FocusDndProvider). The listener filters by id-prefix and runs
  // the existing widget-repositioning logic. Other consumers
  // (SchedulingKanbanCore, future AncillaryPoolPin) register their
  // own listeners on the same context — @dnd-kit fires all listeners
  // on each event; gating happens per-listener via the prefix check.
  useDndMonitor({ onDragEnd: handleDragEnd })

  return (
    <>
      <div
        data-slot="focus-canvas"
        data-focus-tier={tier}
        className={cn(
          "fixed inset-0",
          // Wrapper pointer-events none; children re-enable.
          "pointer-events-none",
        )}
        style={{ zIndex: "var(--z-focus)" }}
      >
        {/* Dev grid overlay — canvas tier only. */}
        {devMode && tier === "canvas" && (
          <div
            aria-hidden
            data-slot="focus-canvas-dev-grid"
            className="pointer-events-none absolute inset-0 opacity-30"
            style={{
              backgroundImage:
                "linear-gradient(to right, var(--border-subtle) 1px, transparent 1px), linear-gradient(to bottom, var(--border-subtle) 1px, transparent 1px)",
              backgroundSize: "8px 8px",
            }}
          />
        )}

        {/* Crossfade contract: all three tier subtrees render
            always, visibility switches via `data-active`. CSS
            transitions opacity + pointer-events over `--duration-
            settle` (token-first per Aesthetic Arc). Token-
            referenced opacity transition so reduced-motion users
            inherit the global retrofit in base.css. Inactive
            subtrees keep `pointer-events: none` so a dimmed widget
            can't eat a click mid-fade.

            Session 3.8 — simultaneous crossfade. Old + new render
            together during the fade window, neither discretely
            replacing the other. Matches macOS window-resize feel
            rather than "mode switch" feel. */}

        {/* CANVAS TIER — free-form widgets at anchor positions. */}
        <div
          data-slot="focus-tier-renderer"
          data-tier-renderer="canvas"
          data-active={tier === "canvas" ? "true" : "false"}
          className={cn(
            "absolute inset-0 transition-opacity ease-settle",
            // Session 3.8.1 — asymmetric fade duration. The inactive
            // (fading-out) renderer uses duration-quick so it's
            // mostly gone before the core has moved appreciably into
            // its old area. Active (fading-in) renderer uses the
            // full duration-settle for a deliberate reveal. Without
            // asymmetry, the fading renderer sat in its old spatial
            // position long enough for the growing core to visibly
            // overlap it mid-fade ("stack appeared under core" bug).
            "data-[active=true]:duration-settle data-[active=false]:duration-quick",
            "data-[active=true]:opacity-100 data-[active=false]:opacity-0",
            // Phase B Session 4 Phase 4.2.1 — canvas tier is the ONE
            // tier where the tier-renderer itself is non-interactive:
            // each widget inside wraps itself in `pointer-events-auto`
            // (see the widget .map below), so the wrapping tier-
            // renderer has nothing of its own to catch. Keeping it
            // `pointer-events-none` lets drag events in Focus cores
            // beneath (e.g. SchedulingKanbanCore's DndContext on
            // cards) reach their listeners without the full-viewport
            // `absolute inset-0` renderer intercepting pointerdown
            // via elementFromPoint-on-top.
            //
            // Stack + icon tiers still need `pointer-events-auto` on
            // their tier-renderer because StackRail / IconButton are
            // themselves interactive (scroll-snap region, button
            // click) and don't wrap their interactive surface in
            // another per-child auto layer.
            "pointer-events-none",
          )}
        >
          {Object.entries(widgets).map(([id, state]) => (
            <div key={id} className="pointer-events-auto">
              <WidgetChrome
                widgetId={id as WidgetId}
                position={state.position}
                canvasWidth={viewport.width}
                canvasHeight={viewport.height}
                onDismiss={() => removeWidget(id as WidgetId)}
              >
                <MockSavedViewWidget />
              </WidgetChrome>
            </div>
          ))}
        </div>

        {/* STACK TIER — right-rail Smart Stack + expanded overlay. */}
        <div
          data-slot="focus-tier-renderer"
          data-tier-renderer="stack"
          data-active={tier === "stack" ? "true" : "false"}
          className={cn(
            "absolute inset-0 transition-opacity ease-settle",
            // Session 3.8.1 — asymmetric fade duration. The inactive
            // (fading-out) renderer uses duration-quick so it's
            // mostly gone before the core has moved appreciably into
            // its old area. Active (fading-in) renderer uses the
            // full duration-settle for a deliberate reveal. Without
            // asymmetry, the fading renderer sat in its old spatial
            // position long enough for the growing core to visibly
            // overlap it mid-fade ("stack appeared under core" bug).
            "data-[active=true]:duration-settle data-[active=false]:duration-quick",
            "data-[active=true]:opacity-100 data-[active=false]:opacity-0",
            "data-[active=true]:pointer-events-auto data-[active=false]:pointer-events-none",
          )}
        >
          <StackRail
            widgets={widgets}
            onExpandWidget={(id) => setExpandedWidgetId(id)}
          />
          {expandedWidgetId && widgets[expandedWidgetId] && (
            <StackExpandedOverlay
              widgetId={expandedWidgetId}
              state={widgets[expandedWidgetId]}
              onDismiss={() => setExpandedWidgetId(null)}
            />
          )}
        </div>

        {/* ICON TIER — floating button (closed) or bottom sheet (open).
            Mutually exclusive within the tier. */}
        <div
          data-slot="focus-tier-renderer"
          data-tier-renderer="icon"
          data-active={tier === "icon" ? "true" : "false"}
          className={cn(
            "absolute inset-0 transition-opacity ease-settle",
            // Session 3.8.1 — asymmetric fade duration. The inactive
            // (fading-out) renderer uses duration-quick so it's
            // mostly gone before the core has moved appreciably into
            // its old area. Active (fading-in) renderer uses the
            // full duration-settle for a deliberate reveal. Without
            // asymmetry, the fading renderer sat in its old spatial
            // position long enough for the growing core to visibly
            // overlap it mid-fade ("stack appeared under core" bug).
            "data-[active=true]:duration-settle data-[active=false]:duration-quick",
            "data-[active=true]:opacity-100 data-[active=false]:opacity-0",
            "data-[active=true]:pointer-events-auto data-[active=false]:pointer-events-none",
          )}
        >
          {!sheetOpen && (
            <IconButton
              widgetCount={Object.keys(widgets).length}
              onOpen={() => setSheetOpen(true)}
            />
          )}
          {sheetOpen && (
            <BottomSheet
              widgets={widgets}
              onDismiss={() => setSheetOpen(false)}
            />
          )}
        </div>
      </div>
    </>
  )
}
