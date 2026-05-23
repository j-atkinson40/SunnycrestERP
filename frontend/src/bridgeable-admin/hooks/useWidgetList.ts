/**
 * useWidgetList — WB-4b composed-widget index hook.
 *
 * Fetches the list of composed widgets from
 * `GET /api/platform/admin/visual-editor/widgets` (post WB-cycle-followup-2
 * — was `GET /api/v1/widget-definitions` against tenant apiClient prior).
 *
 * Filters client-side by tier_scope ("all" | "platform" | "vertical").
 *
 * Phase 1 surface — no pagination, no search, no per-tenant scoping.
 * The list is bounded (≤ ~30 composed widgets per tenant in Phase 1
 * per the Widget Library substrate at r58); rendering all rows is
 * cheap.
 */
import { useCallback, useEffect, useState } from "react"

import {
  visualEditorWidgetsService,
  type WidgetBuilderRecord,
} from "@/bridgeable-admin/services/visual-editor-widgets-service"


export type TierScopeFilter = "all" | "platform" | "vertical"


export interface UseWidgetListResult {
  widgets: WidgetBuilderRecord[]
  loading: boolean
  error: string | null
  tierFilter: TierScopeFilter
  setTierFilter: (f: TierScopeFilter) => void
  refresh: () => void
}


export function useWidgetList(): UseWidgetListResult {
  const [widgets, setWidgets] = useState<WidgetBuilderRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tierFilter, setTierFilter] = useState<TierScopeFilter>("all")
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    visualEditorWidgetsService
      .list()
      .then((r) => {
        if (cancelled) return
        setWidgets(r.widgets)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [nonce])

  const filtered =
    tierFilter === "all"
      ? widgets
      : widgets.filter((w) => w.tier_scope === tierFilter)

  const refresh = useCallback(() => setNonce((n) => n + 1), [])

  return {
    widgets: filtered,
    loading,
    error,
    tierFilter,
    setTierFilter,
    refresh,
  }
}
