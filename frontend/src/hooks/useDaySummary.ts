/**
 * useDaySummary — Phase B Session 4.4.3 hover-preview data hook.
 *
 * Fetches the lightweight DaySummaryDTO for the Scheduling Focus
 * date-box tooltip. Module-scoped Map cache with 30-second TTL — the
 * same pattern useAffinityVisit established for client-side caching.
 *
 * Cache rationale
 * ───────────────
 * Tooltips are hover-triggered. Without a cache, every hover-out /
 * hover-in cycle would refetch the same data. The 30s TTL covers the
 * common dispatcher pattern (hover today, hover day-after, return to
 * today seconds later) while still picking up moderately fresh
 * counts on a focused-back tab. For the dispatcher actively working
 * the schedule, the kanban refresh on drag-drop already invalidates
 * via reload(); this cache only matters for header-level peeks.
 *
 * Lifecycle
 * ─────────
 * - Hook fires on mount + whenever `date` changes
 * - In-flight fetches are cancelled on unmount or date change via
 *   AbortController, so a hover that starts and quickly moves away
 *   doesn't waste a roundtrip OR set state on an unmounted component
 * - Cache hits resolve synchronously — no flash-of-loading on hover
 *   if the same date was fetched within 30s
 *
 * Null-date contract
 * ──────────────────
 * Hook returns `{ summary: null, loading: false, error: null }` when
 * date is null. Callers (DateBox during initial loading state when
 * targetDate isn't yet resolved) can render the tooltip body with a
 * "—" or "loading" string and the hook stays a no-op.
 */

import { useCallback, useEffect, useRef, useState } from "react"

import {
  fetchDaySummary,
  type DaySummaryDTO,
} from "@/services/dispatch-service"

const TTL_MS = 30_000

interface CacheEntry {
  summary: DaySummaryDTO
  cachedAt: number
}

// Module-scoped cache — persists across hook instances within a tab.
// Not persisted across reloads (same convention as useAffinityVisit).
const _cache = new Map<string, CacheEntry>()

function _readCache(date: string): DaySummaryDTO | null {
  const entry = _cache.get(date)
  if (!entry) return null
  if (Date.now() - entry.cachedAt > TTL_MS) {
    _cache.delete(date)
    return null
  }
  return entry.summary
}

function _writeCache(date: string, summary: DaySummaryDTO): void {
  _cache.set(date, { summary, cachedAt: Date.now() })
}

/** Test/dev helper — clears the in-module cache. Exported so unit
 *  tests can isolate fetches between cases without leaking state. */
export function _resetDaySummaryCache(): void {
  _cache.clear()
}

export interface UseDaySummaryResult {
  summary: DaySummaryDTO | null
  loading: boolean
  error: string | null
  /** Manually refresh — bypasses cache, fires a fresh fetch. */
  reload: () => void
}

export function useDaySummary(date: string | null): UseDaySummaryResult {
  const [summary, setSummary] = useState<DaySummaryDTO | null>(() =>
    date ? _readCache(date) : null,
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadTick, setReloadTick] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  // Effect contract:
  //   - date null → clear local state, no fetch
  //   - cache hit → set summary, no fetch
  //   - cache miss → fetch with AbortController, write cache on success
  useEffect(() => {
    if (date === null) {
      setSummary(null)
      setLoading(false)
      setError(null)
      return
    }
    // Cache hit — no network call, synchronous resolve.
    const cached = _readCache(date)
    if (cached !== null && reloadTick === 0) {
      setSummary(cached)
      setLoading(false)
      setError(null)
      return
    }

    // Cache miss (or explicit reload). Cancel any prior in-flight
    // request before firing the new one — relevant when the user
    // hover-changes the target date faster than a roundtrip.
    if (abortRef.current) {
      abortRef.current.abort()
    }
    const ac = new AbortController()
    abortRef.current = ac
    setLoading(true)
    setError(null)

    fetchDaySummary(date)
      .then((result) => {
        // Guard against late-arriving response after unmount or date
        // change — only commit state if this fetch is still the
        // current one.
        if (ac.signal.aborted) return
        _writeCache(date, result)
        setSummary(result)
        setLoading(false)
      })
      .catch((e: unknown) => {
        if (ac.signal.aborted) return
        // Swallow abort errors — they're expected on supersede.
        const code = (e as { code?: string })?.code
        const name = (e as { name?: string })?.name
        if (code === "ERR_CANCELED" || name === "CanceledError") return
        console.warn("[useDaySummary] fetch failed:", e)
        setError("Couldn't load summary")
        setLoading(false)
      })

    return () => {
      ac.abort()
    }
  }, [date, reloadTick])

  const reload = useCallback(() => {
    if (date) _cache.delete(date)
    setReloadTick((n) => n + 1)
  }, [date])

  return { summary, loading, error, reload }
}
