/**
 * useResize — custom pointer-event resize hook for canvas widgets.
 *
 * @dnd-kit/core handles drag but not resize natively. This hook wires
 * a PointerEvent-based handler to a "resize corner" element. The
 * consumer passes the current position + callbacks; the hook exposes:
 *   - `onPointerDown`: attach to the resize-corner element
 *   - `size`: current in-progress size during resize (or null when
 *     not resizing) — lets consumer render real-time feedback
 *   - `isResizing`: boolean, true while pointer is down on the corner
 *
 * On pointer-up, the hook calls `onResizeEnd(newPosition)` with the
 * final 8px-snapped size, clamped to min size + canvas bounds. The
 * consumer then calls `updateSessionLayout` to persist.
 *
 * Uses pointer events (not mouse events) for cross-device support
 * (touch + pen + mouse via single API, per W3C PointerEvent spec).
 */

import { useCallback, useEffect, useRef, useState } from "react"

import type { WidgetPosition } from "@/contexts/focus-registry"
import { clampToCanvas, enforceMinSize, snapTo8px } from "./geometry"


interface UseResizeInput {
  position: WidgetPosition
  minWidth: number
  minHeight: number
  canvasWidth: number
  canvasHeight: number
  onResizeEnd: (next: WidgetPosition) => void
}


interface UseResizeReturn {
  /** Real-time size during resize — null when not actively resizing.
   *  Consumer reads this to render visual feedback; not 8px-snapped
   *  (snap happens on release). */
  liveSize: { width: number; height: number } | null
  isResizing: boolean
  /** Attach to the resize-corner element via onPointerDown. */
  onPointerDown: (event: React.PointerEvent) => void
}


export function useResize({
  position,
  minWidth,
  minHeight,
  canvasWidth,
  canvasHeight,
  onResizeEnd,
}: UseResizeInput): UseResizeReturn {
  const [liveSize, setLiveSize] = useState<{
    width: number
    height: number
  } | null>(null)

  // Keep the latest position + canvas dims in a ref so the pointer-
  // move + pointer-up handlers installed on the window always see
  // current values without re-registering.
  const latest = useRef({
    position,
    minWidth,
    minHeight,
    canvasWidth,
    canvasHeight,
    onResizeEnd,
  })
  useEffect(() => {
    latest.current = {
      position,
      minWidth,
      minHeight,
      canvasWidth,
      canvasHeight,
      onResizeEnd,
    }
  }, [position, minWidth, minHeight, canvasWidth, canvasHeight, onResizeEnd])

  const onPointerDown = useCallback((event: React.PointerEvent) => {
    event.preventDefault()
    event.stopPropagation()

    const { position: startPos } = latest.current
    const startX = event.clientX
    const startY = event.clientY
    const startWidth = startPos.width
    const startHeight = startPos.height

    function computeLive(e: PointerEvent) {
      const dx = e.clientX - startX
      const dy = e.clientY - startY
      const { minWidth, minHeight, canvasWidth, canvasHeight, position: pos } =
        latest.current
      // Clamp width by min + available canvas room to the right of
      // the widget's left edge.
      const maxWidth = canvasWidth - pos.x
      const maxHeight = canvasHeight - pos.y
      return {
        width: Math.max(minWidth, Math.min(maxWidth, startWidth + dx)),
        height: Math.max(minHeight, Math.min(maxHeight, startHeight + dy)),
      }
    }

    function handleMove(e: PointerEvent) {
      setLiveSize(computeLive(e))
    }

    function handleUp(e: PointerEvent) {
      const live = computeLive(e)
      const { position: pos, minWidth, minHeight, canvasWidth, canvasHeight, onResizeEnd } =
        latest.current
      const snapped: WidgetPosition = {
        x: pos.x,
        y: pos.y,
        width: snapTo8px(live.width),
        height: snapTo8px(live.height),
      }
      const enforced = enforceMinSize(snapped, minWidth, minHeight)
      const clamped = clampToCanvas(enforced, canvasWidth, canvasHeight)
      onResizeEnd(clamped)
      setLiveSize(null)
      window.removeEventListener("pointermove", handleMove)
      window.removeEventListener("pointerup", handleUp)
      window.removeEventListener("pointercancel", handleUp)
    }

    window.addEventListener("pointermove", handleMove)
    window.addEventListener("pointerup", handleUp)
    window.addEventListener("pointercancel", handleUp)

    // Seed liveSize so the consumer sees immediate feedback even
    // before the first pointermove.
    setLiveSize({ width: startWidth, height: startHeight })
  }, [])

  return {
    liveSize,
    isResizing: liveSize !== null,
    onPointerDown,
  }
}
