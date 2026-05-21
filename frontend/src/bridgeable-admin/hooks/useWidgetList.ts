/**
 * useWidgetList — WB-4b composed-widget index hook.
 *
 * Fetches the list of composed widgets from the new
 * `GET /api/v1/widget-definitions` endpoint. Filters client-side
 * by tier_scope ("all" | "platform" | "vertical").
 *
 * Phase 1 surface — no pagination, no search, no per-tenant scoping.
 * The list is bounded (≤ ~30 composed widgets per tenant in Phase 1
 * per the Widget Library substrate at r58); rendering all rows is
 * cheap.
 */
import { useCallback, useEffect, useState } from "react"

import apiClient from "@/lib/api-client"
import type { WidgetBuilderRecord } from "@/bridgeable-admin/services/widget-builder-service"


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
    apiClient
      .get<{ widgets: WidgetBuilderRecord[] } | WidgetBuilderRecord[]>(
        "/widget-definitions",
      )
      .then((r) => {
        if (cancelled) return
        // Accept either {widgets: [...]} or a raw array for forward-compat.
        const data = r.data as unknown
        const list = Array.isArray(data)
          ? (data as WidgetBuilderRecord[])
          : (data as { widgets?: WidgetBuilderRecord[] })?.widgets ?? []
        setWidgets(list)
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
