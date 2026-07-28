/**
 * ParkCanvas — the free-form spatial canvas for park tablets (S-5).
 *
 * Reuses the SHIPPED drag machinery core-free: the same
 * `WidgetChrome` (drag/resize/dismiss), the same @dnd-kit
 * `useDndMonitor` id-prefix routing, the same pure anchor geometry +
 * 8px snap. The ONE difference from the Focus canvas is that park has
 * NO anchored core — so there is no core-rect forbidden zone and no
 * tier cascade (slice 1 is desktop free-form; the stack/icon mobile
 * cascade is deferred). Positions persist to the PARK session via
 * `WidgetChrome.onLayoutChange` (not FocusContext).
 *
 * The wrapper is `pointer-events-none`; each tablet self-asserts
 * `pointer-events-auto` on its own container per the Focus Canvas tier
 * contract — so empty canvas regions fall through to the app beneath.
 * Must be mounted inside a `<FocusDndProvider>` (the generic DndContext)
 * and a `<ParkProvider>`.
 */

import { useEffect, useState } from "react"
import { useDndMonitor, type DragEndEvent } from "@dnd-kit/core"

import { usePark } from "@/contexts/park-context"
import type { WidgetId, WidgetPosition } from "@/contexts/focus-registry"
import {
  clampPositionOffsets,
  computeOffsetsForAnchor,
  determineAnchorFromDrop,
  resolvePosition,
  snapTo8px,
} from "@/components/focus/canvas/geometry"
import { WidgetChrome } from "@/components/focus/canvas/WidgetChrome"
import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers"

// Same prefix the shipped WidgetChrome emits on its draggable id.
const WIDGET_DRAG_PREFIX = "widget:"

/** Minimal viewport-size hook — park's canvas fills the viewport and
 *  positions resolve against window dims. Core-free (no tier math). */
function useWindowSize() {
  const [size, setSize] = useState(() => ({
    width: typeof window !== "undefined" ? window.innerWidth : 1280,
    height: typeof window !== "undefined" ? window.innerHeight : 800,
  }))
  useEffect(() => {
    const onResize = () =>
      setSize({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])
  return size
}

export function ParkCanvas() {
  const { tablets, updateTabletPosition, dismissTablet } = usePark()
  const { width, height } = useWindowSize()

  function handleDragEnd(event: DragEndEvent) {
    const { active, delta } = event
    const rawId = String(active.id)
    if (!rawId.startsWith(WIDGET_DRAG_PREFIX)) return
    const tabletId = rawId.slice(WIDGET_DRAG_PREFIX.length)
    const tablet = tablets.find((t) => t.tabletId === tabletId)
    if (!tablet) return

    const startRect = resolvePosition(tablet.position, width, height)
    const dropRect = {
      x: snapTo8px(startRect.x + delta.x),
      y: snapTo8px(startRect.y + delta.y),
      width: startRect.width,
      height: startRect.height,
    }
    // NO core-overlap reject — park has no core; tablets may overlap
    // freely (z-order handles it), exactly the spec's free-form canvas.
    const dropCenterX = dropRect.x + dropRect.width / 2
    const dropCenterY = dropRect.y + dropRect.height / 2
    const newAnchor = determineAnchorFromDrop(
      dropCenterX,
      dropCenterY,
      width,
      height,
    )
    const rawOffsets = computeOffsetsForAnchor(newAnchor, dropRect, width, height)
    const nextPosition: WidgetPosition = {
      anchor: newAnchor,
      offsetX: Math.max(0, snapTo8px(rawOffsets.offsetX)),
      offsetY: Math.max(0, snapTo8px(rawOffsets.offsetY)),
      width: dropRect.width,
      height: dropRect.height,
    }
    updateTabletPosition(
      tabletId,
      clampPositionOffsets(nextPosition, width, height),
    )
  }

  useDndMonitor({ onDragEnd: handleDragEnd })

  return (
    <div
      data-slot="park-canvas"
      className="pointer-events-none fixed inset-0"
      // Park sits above the app content, below the command bar (110) and
      // FocusPopover (115) so portaled pickers inside tablets paint on
      // top. Inline literal for slice 1 — tokenize `--z-park` in the
      // arc-close canon sweep (park conventions accumulate there).
      style={{ zIndex: 90 }}
    >
      {tablets.map((tablet) => {
        const Renderer = getWidgetRenderer(tablet.widgetType)
        return (
          <div key={tablet.tabletId} className="pointer-events-auto">
            <WidgetChrome
              widgetId={tablet.tabletId as WidgetId}
              position={tablet.position}
              canvasWidth={width}
              canvasHeight={height}
              onDismiss={() => dismissTablet(tablet.tabletId)}
              onLayoutChange={(id, pos) => updateTabletPosition(id, pos)}
            >
              <Renderer
                widgetId={tablet.tabletId}
                surface="park"
                config={{ tabletId: tablet.tabletId }}
              />
            </WidgetChrome>
          </div>
        )
      })}
    </div>
  )
}
