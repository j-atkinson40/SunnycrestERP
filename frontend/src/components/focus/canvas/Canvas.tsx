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
 * geometry.ts's `determineTier`. Core size continues to transition
 * smoothly via Focus.tsx's Popup `transition-[width,height,left,
 * top]`. Together they deliver macOS-window-resize feel: widgets
 * flow, stack fades in/out, icon materializes — no discrete mode
 * switch.
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
            "absolute inset-0 transition-opacity duration-settle ease-settle",
            "data-[active=true]:opacity-100 data-[active=false]:opacity-0",
            "data-[active=true]:pointer-events-auto data-[active=false]:pointer-events-none",
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
            "absolute inset-0 transition-opacity duration-settle ease-settle",
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
            "absolute inset-0 transition-opacity duration-settle ease-settle",
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
    </DndContext>
  )
}
