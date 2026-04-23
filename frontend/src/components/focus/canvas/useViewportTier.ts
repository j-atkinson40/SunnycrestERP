/**
 * useViewportTier — reactive hook exposing the current viewport
 * dimensions + focus tier. Phase A Session 3.7, rAF-throttled
 * Session 3.8.2.
 *
 * One source of truth for tier. Canvas + Focus both consume this so
 * core sizing and widget rendering stay in sync.
 *
 * Content-aware (Session 3.7 post-verification fix):
 *   Pass the current widget set to the hook and tier detection
 *   considers whether widgets fit in canvas reserved space. When
 *   widgets don't fit, the tier transitions to stack even if the
 *   viewport alone would permit canvas. See
 *   `geometry.ts::widgetsFitInCanvas` for the per-anchor fit logic.
 *
 * Tier is derived fresh on every render (from current dims + current
 * widgets), so a widget mutation triggers re-evaluation without the
 * hook needing a useEffect dependency on widgets. Viewport dims still
 * update only via the resize listener to avoid pointless re-renders.
 *
 * Session 3.8.2 — resize handler rAF-throttled. Browsers fire resize
 * events during window drag faster than a render frame can complete
 * (10+ per frame on some platforms). Without throttling, React would
 * re-render on every event, stacking work. The rAF-throttle collapses
 * multiple resize events within a single animation frame into ONE
 * setDims call — one re-render per frame, matching the browser's
 * paint cadence. Contributes to the macOS-Finder-style resize feel
 * alongside the removal of layout-prop CSS transitions.
 */

import { useEffect, useState } from "react"

import type { WidgetId, WidgetState } from "@/contexts/focus-registry"

import { determineTier, type FocusTier } from "./geometry"


export interface ViewportTierState {
  width: number
  height: number
  tier: FocusTier
}


export function useViewportTier(
  widgets: Record<WidgetId, WidgetState> | WidgetState[] = [],
): ViewportTierState {
  const [dims, setDims] = useState(() => {
    const w = typeof window !== "undefined" ? window.innerWidth : 1440
    const h = typeof window !== "undefined" ? window.innerHeight : 900
    return { width: w, height: h }
  })

  useEffect(() => {
    if (typeof window === "undefined") return
    let rafId = 0
    const handler = () => {
      if (rafId) return
      rafId = requestAnimationFrame(() => {
        setDims({ width: window.innerWidth, height: window.innerHeight })
        rafId = 0
      })
    }
    window.addEventListener("resize", handler)
    return () => {
      window.removeEventListener("resize", handler)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [])

  // Derive tier on every render so widget-set changes retrigger
  // detection without an extra useEffect dependency chain.
  const tier = determineTier(dims.width, dims.height, widgets)
  return { width: dims.width, height: dims.height, tier }
}
