/**
 * useResize — custom PointerEvent resize hook for canvas widgets.
 *
 * Phase A Session 3.5 — zone-aware. Supports all 8 resize zones
 * (4 corners + 4 edges). The consumer passes the zone identifier
 * plus the current anchor-based position; the hook:
 *   - On pointer down: captures start rect (resolved) + start cursor
 *   - On pointer move: applies zone-specific delta, enforces min
 *     size + canvas clamp, reports liveRect (for visual feedback)
 *   - On pointer up: re-projects to the ORIGINAL anchor, persists
 *     via onResizeEnd
 *
 * The anchor is preserved across a resize — resizing doesn't move
 * the widget to a different zone. Drag handles that.
 *
 * Uses PointerEvent API for cross-device support (mouse + touch +
 * pen via single API).
 */

import { useCallback, useEffect, useRef, useState } from "react"

import type {
  WidgetAnchor,
  WidgetPosition,
} from "@/contexts/focus-registry"

import {
  applyResizeDelta,
  clampRectToCanvas,
  clampRectDimensions,
  computeOffsetsForAnchor,
  enforceMinRect,
  resolvePosition,
  snapTo8px,
  type Rect,
  type ResizeZone,
} from "./geometry"


interface UseResizeInput {
  anchor: WidgetAnchor
  position: WidgetPosition
  minWidth: number
  minHeight: number
  canvasWidth: number
  canvasHeight: number
  onResizeEnd: (next: WidgetPosition) => void
}


interface UseResizeReturn {
  /** Real-time rect during resize — null when not actively resizing.
   *  Consumer reads this to render live visual feedback. Expressed
   *  in absolute (resolved) viewport coordinates. */
  liveRect: Rect | null
  isResizing: boolean
  /** Returns an onPointerDown handler bound to a specific resize
   *  zone. Attach to the zone element's onPointerDown prop. */
  bind: (zone: ResizeZone) => (event: React.PointerEvent) => void
}


export function useResize({
  anchor,
  position,
  minWidth,
  minHeight,
  canvasWidth,
  canvasHeight,
  onResizeEnd,
}: UseResizeInput): UseResizeReturn {
  const [liveRect, setLiveRect] = useState<Rect | null>(null)

  // Keep latest props in a ref so window pointer listeners see
  // current values without needing to re-register.
  const latest = useRef({
    anchor,
    position,
    minWidth,
    minHeight,
    canvasWidth,
    canvasHeight,
    onResizeEnd,
  })
  useEffect(() => {
    latest.current = {
      anchor,
      position,
      minWidth,
      minHeight,
      canvasWidth,
      canvasHeight,
      onResizeEnd,
    }
  }, [
    anchor,
    position,
    minWidth,
    minHeight,
    canvasWidth,
    canvasHeight,
    onResizeEnd,
  ])

  const bind = useCallback(
    (zone: ResizeZone) => (event: React.PointerEvent) => {
      // Prevent drag initiation + text selection.
      event.preventDefault()
      event.stopPropagation()

      const startRect = resolvePosition(
        latest.current.position,
        latest.current.canvasWidth,
        latest.current.canvasHeight,
      )
      const startClientX = event.clientX
      const startClientY = event.clientY

      function computeLive(e: PointerEvent): Rect {
        const {
          minWidth,
          minHeight,
          canvasWidth,
          canvasHeight,
        } = latest.current
        const dx = e.clientX - startClientX
        const dy = e.clientY - startClientY
        let rect = applyResizeDelta(zone, startRect, dx, dy)
        rect = enforceMinRect(rect, minWidth, minHeight)
        // Clamp so the rect stays inside the viewport. Width/height
        // are clamped to canvas dims too — a widget being resized
        // wider than viewport gets clipped (respects min).
        rect = clampRectDimensions(
          rect,
          canvasWidth,
          canvasHeight,
          minWidth,
          minHeight,
        )
        rect = clampRectToCanvas(rect, canvasWidth, canvasHeight)
        return rect
      }

      function handleMove(e: PointerEvent) {
        setLiveRect(computeLive(e))
      }

      function handleUp(e: PointerEvent) {
        const finalRect = computeLive(e)
        const snapped: Rect = {
          x: snapTo8px(finalRect.x),
          y: snapTo8px(finalRect.y),
          width: snapTo8px(finalRect.width),
          height: snapTo8px(finalRect.height),
        }
        const enforced = enforceMinRect(snapped, latest.current.minWidth, latest.current.minHeight)
        const finalClamped = clampRectToCanvas(
          enforced,
          latest.current.canvasWidth,
          latest.current.canvasHeight,
        )

        // Re-project to the ORIGINAL anchor. The widget doesn't
        // change zones just because it was resized.
        const offsets = computeOffsetsForAnchor(
          latest.current.anchor,
          finalClamped,
          latest.current.canvasWidth,
          latest.current.canvasHeight,
        )
        const nextPosition: WidgetPosition = {
          anchor: latest.current.anchor,
          offsetX: Math.max(0, snapTo8px(offsets.offsetX)),
          offsetY: Math.max(0, snapTo8px(offsets.offsetY)),
          width: finalClamped.width,
          height: finalClamped.height,
        }

        latest.current.onResizeEnd(nextPosition)
        setLiveRect(null)

        window.removeEventListener("pointermove", handleMove)
        window.removeEventListener("pointerup", handleUp)
        window.removeEventListener("pointercancel", handleUp)
      }

      window.addEventListener("pointermove", handleMove)
      window.addEventListener("pointerup", handleUp)
      window.addEventListener("pointercancel", handleUp)

      // Seed liveRect so the consumer sees immediate feedback before
      // the first pointermove.
      setLiveRect(startRect)
    },
    [],
  )

  return {
    liveRect,
    isResizing: liveRect !== null,
    bind,
  }
}
