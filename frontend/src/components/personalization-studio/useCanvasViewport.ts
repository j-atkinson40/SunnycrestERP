/**
 * useCanvasViewport — canonical viewport hook for Phase 1B canvas
 * implementation per Phase A Session 3.8.2 + 3.8.3 canonical resize
 * pattern.
 *
 * **Canonical Phase A Session 3.8.2 rAF-coalesced resize handler**:
 * window.resize event listener canonical at rAF-coalesced single
 * setDims call per animation frame. Browsers fire resize events
 * during window drag faster than a render frame can complete
 * (10+ per frame on some platforms). Without throttling, React
 * would re-render on every event, stacking work. The rAF-throttle
 * collapses multiple resize events within a single animation frame
 * into ONE setDims call — one re-render per frame, matching the
 * browser's paint cadence.
 *
 * **Canonical three-tier responsive cascade** per Phase A canonical:
 * canvas | stack | icon. Phase 1B canvas implementation reuses Phase
 * A's `determineTier` for the canvas-vs-stack-vs-icon decision so
 * canonical viewport behavior stays consistent across the canvas
 * substrate (Focus canvas widget chrome from Phase A + canonical
 * Personalization Studio canvas from Phase 1B).
 *
 * **Canonical-pattern-establisher discipline**: Phase 1B canonical
 * viewport hook establishes canonical pattern for Step 2 (Urn Vault
 * Personalization Studio) viewport canonical. Step 2 inherits via
 * canonical reuse.
 */

import { useEffect, useState } from "react"

import { determineTier, type FocusTier } from "@/components/focus/canvas/geometry"

export interface CanvasViewportDims {
  width: number
  height: number
  /** Canonical three-tier responsive cascade per Phase A canonical. */
  tier: FocusTier
}

/**
 * Reactive canvas viewport hook with canonical rAF-coalesced
 * resize handling per Phase A Session 3.8.2 canonical.
 *
 * @returns canonical viewport dimensions + tier
 */
export function useCanvasViewport(): CanvasViewportDims {
  const [dims, setDims] = useState(() => {
    const w = typeof window !== "undefined" ? window.innerWidth : 1440
    const h = typeof window !== "undefined" ? window.innerHeight : 900
    return { width: w, height: h }
  })

  useEffect(() => {
    if (typeof window === "undefined") return
    let rafId = 0
    const handler = () => {
      // Canonical rAF-coalesced canonical: collapse multiple resize
      // events within single animation frame to single setDims call
      // per Phase A Session 3.8.2 canonical.
      if (rafId) return
      rafId = requestAnimationFrame(() => {
        setDims({
          width: window.innerWidth,
          height: window.innerHeight,
        })
        rafId = 0
      })
    }
    window.addEventListener("resize", handler)
    return () => {
      window.removeEventListener("resize", handler)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [])

  // Canonical three-tier responsive cascade per Phase A. Pass empty
  // widget set — Phase 1B canvas substrate doesn't have widget-fit
  // logic; canvas vs stack vs icon decision purely by viewport.
  const tier = determineTier(dims.width, dims.height, [])
  return { width: dims.width, height: dims.height, tier }
}
