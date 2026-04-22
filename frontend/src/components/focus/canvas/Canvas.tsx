/**
 * Canvas — free-form widget region surrounding the anchored Focus
 * core. Phase A Session 3.
 *
 * Visual structure (inside Dialog.Portal):
 *   ┌───────────────────────── viewport ─────────────────────────┐
 *   │                                                             │
 *   │   ┌── Canvas (fixed inset-0, pointer-events: none) ──┐      │
 *   │   │   Widgets absolutely positioned (pointer-events   │      │
 *   │   │   auto via WidgetChrome) — can live top, left,    │      │
 *   │   │   right, or below the anchored core.              │      │
 *   │   │                                                    │      │
 *   │   │           ┌── Anchored core (Dialog.Popup) ──┐    │      │
 *   │   │           │   ModeDispatcher renders here.   │    │      │
 *   │   │           └──────────────────────────────────┘    │      │
 *   │   │                                                    │      │
 *   │   └────────────────────────────────────────────────────┘     │
 *   │                                                             │
 *   └─────────────────────────────────────────────────────────────┘
 *
 * Pointer-events discipline:
 *   - Canvas wrapper has `pointer-events: none` so backdrop clicks
 *     pass through to Dialog.Backdrop's dismiss handler.
 *   - Widgets (via WidgetChrome) set `pointer-events: auto` on
 *     themselves so drag / resize / dismiss remain interactive.
 *
 * Coordinate space:
 *   - Viewport pixels. Origin (0, 0) at viewport top-left.
 *   - All widget positions snapped to 8px (see geometry.ts).
 *
 * Drag wiring:
 *   - DndContext wraps the widget set.
 *   - Each WidgetChrome uses useDraggable.
 *   - On drag end, Canvas's onDragEnd computes the new absolute
 *     position by adding the drag delta to the widget's previous
 *     position, snapping to 8px, and clamping to canvas bounds minus
 *     the forbidden core zone (widget can't land on top of the
 *     core). Persists via updateSessionLayout.
 */

import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { useFocus } from "@/contexts/focus-context"
import type { WidgetId, WidgetPosition } from "@/contexts/focus-registry"
import { cn } from "@/lib/utils"

import {
  clampPositionOffsets,
  computeCoreRect,
  computeOffsetsForAnchor,
  determineAnchorFromDrop,
  rectsOverlap,
  resolvePosition,
  snapTo8px,
} from "./geometry"
import { MockSavedViewWidget } from "./MockSavedViewWidget"
import { WidgetChrome } from "./WidgetChrome"


/** Read the current viewport dimensions reactively — updates on
 *  window resize so geometry stays correct. */
function useViewportSize() {
  const [size, setSize] = useState(() => ({
    width: typeof window !== "undefined" ? window.innerWidth : 1440,
    height: typeof window !== "undefined" ? window.innerHeight : 900,
  }))
  useEffect(() => {
    if (typeof window === "undefined") return
    const handler = () =>
      setSize({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener("resize", handler)
    return () => window.removeEventListener("resize", handler)
  }, [])
  return size
}


export function Canvas() {
  const { currentFocus, updateSessionLayout, removeWidget } = useFocus()
  const viewport = useViewportSize()

  // dev mode grid visualization — URL ?dev-canvas=1 only. Reads
  // via react-router's useSearchParams so tests using MemoryRouter
  // can exercise the dev-grid path (MemoryRouter doesn't update
  // window.location).
  const [searchParams] = useSearchParams()
  const devMode = searchParams.get("dev-canvas") === "1"

  // @dnd-kit sensors — 8px activation threshold prevents accidental
  // drag on click (matches WidgetGrid precedent).
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  const widgets = currentFocus?.layoutState?.widgets ?? {}
  const coreRect = computeCoreRect(viewport.width, viewport.height)

  function handleDragEnd(event: DragEndEvent) {
    const { active, delta } = event
    const widgetId = String(active.id) as WidgetId
    const current = widgets[widgetId]
    if (!current) return

    // Compute the drop rect in absolute-viewport space: resolve
    // current anchor position, apply drag delta, snap to 8px.
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

    // Core-overlap guard: if the drop rect overlaps the anchored
    // core, silently reject the drop. Widget state never updated →
    // visually snaps back. Smarter slide-to-nearest-edge heuristic
    // is reasonable polish for Session 5.
    if (rectsOverlap(dropRect, coreRect)) return

    // Determine the new anchor from the drop point. The drop point
    // for anchor picking is the widget's CENTER — "which zone does
    // the user think they dropped into" — not the top-left corner.
    const dropCenterX = dropRect.x + dropRect.width / 2
    const dropCenterY = dropRect.y + dropRect.height / 2
    const newAnchor = determineAnchorFromDrop(
      dropCenterX,
      dropCenterY,
      viewport.width,
      viewport.height,
    )

    // Re-project drop rect to the new anchor's offsets. Snap offsets
    // to 8px (widget position is always on the grid).
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

    // Clamp offsets so the widget stays within the viewport.
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

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div
        data-slot="focus-canvas"
        className={cn(
          "fixed inset-0",
          // pointer-events none on the wrapper so backdrop clicks
          // reach the Dialog.Backdrop beneath us. Widgets re-enable
          // pointer events on themselves via WidgetChrome.
          "pointer-events-none",
        )}
        style={{ zIndex: "var(--z-focus)" }}
      >
        {/* Dev-only grid lines — only visible with ?dev-canvas=1 */}
        {devMode && (
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

        {/* Widgets — each positioned absolutely via WidgetChrome
            using their layout-state position. The widget rendering
            itself is Session 3 stub (MockSavedViewWidget); Session 5
            replaces with the real pin system. */}
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
    </DndContext>
  )
}
