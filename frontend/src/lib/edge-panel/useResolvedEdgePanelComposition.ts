/**
 * R-5.0 — composition resolver hook.
 *
 * Public hook for callers that want the panel composition WITHOUT
 * pulling EdgePanelContext (e.g., the visual editor preview pane,
 * or test harnesses). Mirrors `useResolvedComposition` for Focus
 * compositions.
 */
import { useEffect, useState } from "react"

import { resolveEdgePanel } from "./edge-panel-service"
import type { ResolvedEdgePanel } from "./types"


export interface UseResolvedEdgePanelOptions {
  panelKey: string
  enabled?: boolean
}


export function useResolvedEdgePanelComposition({
  panelKey,
  enabled = true,
}: UseResolvedEdgePanelOptions): {
  composition: ResolvedEdgePanel | null
  isLoading: boolean
  error: Error | null
} {
  const [composition, setComposition] = useState<ResolvedEdgePanel | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(enabled)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false)
      return
    }
    let cancelled = false
    setIsLoading(true)
    setError(null)
    void (async () => {
      try {
        const result = await resolveEdgePanel(panelKey)
        if (cancelled) return
        setComposition(result)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err : new Error(String(err)))
        setComposition(null)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [panelKey, enabled])

  return { composition, isLoading, error }
}
