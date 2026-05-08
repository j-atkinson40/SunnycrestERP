/**
 * R-5.0 — touch swipe gesture for edge panel.
 *
 * When panel is closed: swipe-from-right-edge (within `edgeZonePx` of
 * window.innerWidth) leftward by ≥`thresholdPx` opens the panel.
 * Vertical-dominant swipes are ignored to avoid hijacking page scroll.
 *
 * When panel is open: in-panel page-swipe is handled by the EdgePanel
 * component itself (CSS scroll-snap via the page-track), not this hook.
 */
import { useEffect } from "react"

import { useEdgePanel } from "./EdgePanelProvider"


export interface UseEdgePanelGestureOptions {
  edgeZonePx?: number
  thresholdPx?: number
}


export function useEdgePanelGesture(
  options: UseEdgePanelGestureOptions = {},
): void {
  const { edgeZonePx = 24, thresholdPx = 50 } = options
  const { isOpen, isReady, openPanel, tenantConfig } = useEdgePanel()

  useEffect(() => {
    if (!isReady || !tenantConfig.enabled) return
    if (typeof window === "undefined") return
    if (isOpen) return

    let swipeStart: { x: number; y: number; pointerId: number } | null = null

    function onPointerDown(e: PointerEvent) {
      const w = window.innerWidth
      if (e.clientX >= w - edgeZonePx) {
        swipeStart = {
          x: e.clientX,
          y: e.clientY,
          pointerId: e.pointerId,
        }
      }
    }

    function onPointerUp(e: PointerEvent) {
      if (!swipeStart || swipeStart.pointerId !== e.pointerId) {
        swipeStart = null
        return
      }
      const dx = e.clientX - swipeStart.x
      const dy = e.clientY - swipeStart.y
      swipeStart = null
      // Leftward + horizontal-dominant.
      if (dx <= -thresholdPx && Math.abs(dx) > Math.abs(dy)) {
        openPanel()
      }
    }

    function onPointerCancel() {
      swipeStart = null
    }

    window.addEventListener("pointerdown", onPointerDown)
    window.addEventListener("pointerup", onPointerUp)
    window.addEventListener("pointercancel", onPointerCancel)
    return () => {
      window.removeEventListener("pointerdown", onPointerDown)
      window.removeEventListener("pointerup", onPointerUp)
      window.removeEventListener("pointercancel", onPointerCancel)
    }
  }, [isOpen, isReady, openPanel, edgeZonePx, thresholdPx, tenantConfig.enabled])
}
