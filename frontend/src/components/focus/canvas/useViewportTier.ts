/**
 * useViewportTier — reactive hook exposing the current viewport
 * dimensions + focus tier. Phase A Session 3.7.
 *
 * One source of truth for tier. Canvas + Focus both consume this so
 * core sizing and widget rendering stay in sync.
 */

import { useEffect, useState } from "react"

import { determineTier, type FocusTier } from "./geometry"


export interface ViewportTierState {
  width: number
  height: number
  tier: FocusTier
}


export function useViewportTier(): ViewportTierState {
  const [state, setState] = useState<ViewportTierState>(() => {
    const w = typeof window !== "undefined" ? window.innerWidth : 1440
    const h = typeof window !== "undefined" ? window.innerHeight : 900
    return { width: w, height: h, tier: determineTier(w, h) }
  })

  useEffect(() => {
    if (typeof window === "undefined") return
    const handler = () => {
      const w = window.innerWidth
      const h = window.innerHeight
      setState({ width: w, height: h, tier: determineTier(w, h) })
    }
    window.addEventListener("resize", handler)
    return () => window.removeEventListener("resize", handler)
  }, [])

  return state
}
