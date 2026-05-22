/**
 * useBindingPicker — WB-6 picker data hook.
 *
 * Fetches saved-views + entity-types from the existing
 * `/api/v1/saved-views` substrate. Component-local memoization +
 * AbortController for unmount cancellation. No session-scope cache
 * (matches saved-view executor canon "no caching").
 *
 * Returns:
 *   - savedViews: list of saved views the operator can see
 *   - entityTypes: catalog of entity types + their `available_fields`
 *   - loading: parallel fetch in flight
 *   - error: surfaced for the picker's empty-state path
 *   - refresh: manual re-fetch (for post-create-saved-view refresh)
 */
import { useCallback, useEffect, useRef, useState } from "react"

import {
  listEntityTypes,
  listSavedViews,
} from "@/services/saved-views-service"
import type {
  EntityTypeMetadata,
  SavedView,
} from "@/types/saved-views"


export interface UseBindingPickerResult {
  savedViews: SavedView[]
  entityTypes: EntityTypeMetadata[]
  loading: boolean
  error: string | null
  refresh: () => void
}


export function useBindingPicker(): UseBindingPickerResult {
  const [savedViews, setSavedViews] = useState<SavedView[]>([])
  const [entityTypes, setEntityTypes] = useState<EntityTypeMetadata[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState<number>(0)

  // Track latest fetch to discard out-of-order results.
  const latestFetchId = useRef<number>(0)

  const refresh = useCallback(() => {
    setTick((t) => t + 1)
  }, [])

  useEffect(() => {
    const fetchId = latestFetchId.current + 1
    latestFetchId.current = fetchId
    let cancelled = false

    setLoading(true)
    setError(null)

    Promise.all([listSavedViews(), listEntityTypes()])
      .then(([views, entities]) => {
        if (cancelled) return
        if (latestFetchId.current !== fetchId) return
        setSavedViews(views)
        setEntityTypes(entities)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (latestFetchId.current !== fetchId) return
        const msg =
          err instanceof Error ? err.message : "Failed to load saved views"
        setError(msg)
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { savedViews, entityTypes, loading, error, refresh }
}
