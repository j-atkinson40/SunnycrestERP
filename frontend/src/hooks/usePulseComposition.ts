/**
 * Phase W-4a Commit 5 — Pulse composition fetch hook.
 *
 * Fetches `GET /api/v1/pulse/composition` on mount, exposes
 * `refresh()` for manual reload (`?refresh=true` bypass per D1),
 * and auto-refreshes every 5 minutes to match the backend
 * composition cache TTL.
 *
 * The `pulseLoadedAt` ref is exposed so PulsePiece's navigation
 * tracking can compute dwell time as `Date.now() - pulseLoadedAt`
 * at click moment.
 */

import { useCallback, useEffect, useRef, useState } from "react"

import { fetchPulseComposition } from "@/services/pulse-service"
import type { PulseComposition } from "@/types/pulse"


const AUTO_REFRESH_MS = 5 * 60 * 1000  // 5 min, matches backend TTL


export interface UsePulseCompositionResult {
  composition: PulseComposition | null
  isLoading: boolean
  error: string | null
  /** Manually refresh — bypasses backend cache via ?refresh=true. */
  refresh: () => Promise<void>
  /** Wall-clock timestamp (ms) when the composition currently in
   *  state was first received. PulsePiece reads this to compute
   *  dwell time on navigation. */
  pulseLoadedAt: number | null
}


export function usePulseComposition(): UsePulseCompositionResult {
  const [composition, setComposition] = useState<PulseComposition | null>(
    null,
  )
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pulseLoadedAt, setPulseLoadedAt] = useState<number | null>(null)
  const mountedRef = useRef(true)

  const load = useCallback(async (refresh: boolean) => {
    if (!mountedRef.current) return
    setError(null)
    if (refresh) {
      // Manual refresh — show loading state. Auto-refresh is silent
      // (composition stays in place during background fetch).
      setIsLoading(true)
    }
    try {
      const data = await fetchPulseComposition(refresh)
      if (!mountedRef.current) return
      setComposition(data)
      setPulseLoadedAt(Date.now())
      setIsLoading(false)
    } catch (err) {
      if (!mountedRef.current) return
      setError(
        err instanceof Error ? err.message : "Failed to load Pulse.",
      )
      setIsLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => {
    mountedRef.current = true
    void load(false)
    return () => {
      mountedRef.current = false
    }
  }, [load])

  // Auto-refresh every 5 min — silent (no loading flash). The
  // backend cache will return the same composition until the user's
  // work_areas change OR the 5-min window rolls over; either way the
  // hook's state updates with whatever the server returns.
  useEffect(() => {
    const interval = window.setInterval(() => {
      void load(false)
    }, AUTO_REFRESH_MS)
    return () => {
      window.clearInterval(interval)
    }
  }, [load])

  const refresh = useCallback(async () => {
    await load(true)
  }, [load])

  return { composition, isLoading, error, refresh, pulseLoadedAt }
}
