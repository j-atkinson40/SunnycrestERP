/**
 * useSwipeDismiss — PointerEvent hook for vertical swipe-down
 * dismissal. Phase A Session 3.7.
 *
 * Binds to a draggable bar element (e.g. the BottomSheet's top
 * handle or the whole sheet if preferred). Tracks vertical delta
 * during pointer move. On release:
 *   - if delta > threshold → onDismiss()
 *   - else snap back (state resets)
 *
 * No spring physics — architecture-first, polish deferred to the
 * mobile polish session per PLATFORM_QUALITY_BAR.md 'Almost But
 * Not Quite' entry.
 *
 * Usage:
 *   const swipe = useSwipeDismiss({ onDismiss, threshold: 150 })
 *   <div
 *     onPointerDown={swipe.onPointerDown}
 *     style={{ transform: `translateY(${swipe.offsetY}px)` }}
 *   >
 */

import { useCallback, useRef, useState } from "react"


interface UseSwipeDismissInput {
  onDismiss: () => void
  /** Vertical px threshold past which release dismisses (default 150). */
  threshold?: number
}


interface UseSwipeDismissReturn {
  /** Current vertical translate offset during drag. Apply to the
   *  sheet via transform: translateY. Resets to 0 on release (if no
   *  dismiss) or persists and unmounts (if dismiss). */
  offsetY: number
  isDragging: boolean
  onPointerDown: (event: React.PointerEvent) => void
}


export function useSwipeDismiss({
  onDismiss,
  threshold = 150,
}: UseSwipeDismissInput): UseSwipeDismissReturn {
  const [offsetY, setOffsetY] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const latestRef = useRef({ onDismiss, threshold })
  latestRef.current = { onDismiss, threshold }

  const onPointerDown = useCallback((event: React.PointerEvent) => {
    event.preventDefault()
    const startY = event.clientY
    setIsDragging(true)

    function handleMove(e: PointerEvent) {
      const dy = e.clientY - startY
      // Only respond to downward drags; upward drags get clamped
      // to 0 (no "dragging up" behavior for a dismiss handle).
      setOffsetY(Math.max(0, dy))
    }

    function handleUp(e: PointerEvent) {
      const dy = e.clientY - startY
      window.removeEventListener("pointermove", handleMove)
      window.removeEventListener("pointerup", handleUp)
      window.removeEventListener("pointercancel", handleUp)
      setIsDragging(false)

      if (dy > latestRef.current.threshold) {
        latestRef.current.onDismiss()
        // Leave offsetY non-zero briefly so exit animation can run
        // from current position; caller unmounts the sheet anyway.
      } else {
        setOffsetY(0)
      }
    }

    window.addEventListener("pointermove", handleMove)
    window.addEventListener("pointerup", handleUp)
    window.addEventListener("pointercancel", handleUp)
  }, [])

  return { offsetY, isDragging, onPointerDown }
}
