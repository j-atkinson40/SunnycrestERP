/**
 * Canvas — tier-dispatching widget region surrounding the anchored
 * Focus core. Phase A Session 3.7.
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
 * Pointer-events discipline (inherited from Session 3):
 *   - Canvas wrapper has `pointer-events: none` so backdrop clicks
 *     still reach Dialog.Backdrop for dismiss
 *   - Interactive sub-components set `pointer-events: auto` on
 *     themselves
 */

import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
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


export function Canvas() {
  const { currentFocus, updateSessionLayout, removeWidget } = useFocus()

  const [searchParams] = useSearchParams()
  const devMode = searchParams.get("dev-canvas") === "1"

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

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
    const { active, delta } = event
    const widgetId = String(active.id) as WidgetId
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

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
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

        {/* CANVAS TIER — free-form widgets at anchor positions. */}
        {tier === "canvas" &&
          Object.entries(widgets).map(([id, state]) => (
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

        {/* STACK TIER — right-rail Smart Stack. */}
        {tier === "stack" && (
          <StackRail
            widgets={widgets}
            onExpandWidget={(id) => setExpandedWidgetId(id)}
          />
        )}

        {/* STACK TIER expanded overlay — rendered above stack when
            user taps a widget. */}
        {tier === "stack" && expandedWidgetId && widgets[expandedWidgetId] && (
          <StackExpandedOverlay
            widgetId={expandedWidgetId}
            state={widgets[expandedWidgetId]}
            onDismiss={() => setExpandedWidgetId(null)}
          />
        )}

        {/* ICON TIER — floating button (when closed) or bottom sheet
            (when open). Mutually exclusive. */}
        {tier === "icon" && !sheetOpen && (
          <IconButton
            widgetCount={Object.keys(widgets).length}
            onOpen={() => setSheetOpen(true)}
          />
        )}
        {tier === "icon" && sheetOpen && (
          <BottomSheet
            widgets={widgets}
            onDismiss={() => setSheetOpen(false)}
          />
        )}
      </div>
    </DndContext>
  )
}
