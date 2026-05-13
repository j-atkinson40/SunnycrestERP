/**
 * useVerticals — load the platform's verticals list once and share
 * the result across consumers in the admin tree.
 *
 * Studio 1a-i.B follow-up #4 — needed by StudioLiveModeWrap and
 * TenantUserPicker to disambiguate the first post-`live` URL segment
 * (real vertical slug vs. spurious tail capture from React Router's
 * `<Route path="live/:vertical/*">` greedy match).
 *
 * Pattern matches `StudioScopeSwitcher`'s existing inline load + filter
 * (drops `archived` rows). Encapsulated as a hook so picker + wrap
 * share the loading-state contract.
 *
 * Implementation note: module-level Promise cache keyed by
 * include-archived prevents redundant fetches when multiple consumers
 * mount simultaneously. Cache is in-memory only — a page reload
 * refetches. Sufficient for the current usage pattern; if a refresh
 * mechanism is needed later, add a `refresh()` callback.
 */
import { useEffect, useState } from "react"

import {
  verticalsService,
  type Vertical,
} from "@/bridgeable-admin/services/verticals-service"


// Module-level cache so the same Promise is reused across consumers
// that mount in the same session. Reset on full page reload.
let _verticalsPromise: Promise<Vertical[]> | null = null


function getVerticalsPromise(): Promise<Vertical[]> {
  if (_verticalsPromise === null) {
    _verticalsPromise = verticalsService
      .list()
      .then((rows) => rows.filter((r) => r.status !== "archived"))
      .catch((err) => {
        // Reset so a later mount can retry. Surface error to caller.
        _verticalsPromise = null
        throw err
      })
  }
  return _verticalsPromise
}


export interface UseVerticalsResult {
  /** Loaded verticals (archived filtered out). Empty array until `loaded`. */
  verticals: Vertical[]
  /** True once the initial load resolved (success or failure). */
  loaded: boolean
  /** Set when the initial load failed. */
  error: string | null
  /** Canonical list of valid slugs for disambiguation helpers. */
  knownSlugs: readonly string[]
}


export function useVerticals(): UseVerticalsResult {
  const [verticals, setVerticals] = useState<Vertical[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getVerticalsPromise()
      .then((rows) => {
        if (cancelled) return
        setVerticals(rows)
        setLoaded(true)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.message ?? "Failed to load verticals")
        // Treat failure as "loaded with empty list" so downstream
        // disambiguation defaults to "no slug is known" — every URL
        // segment becomes tail. Picker still works, wrap still mounts.
        setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return {
    verticals,
    loaded,
    error,
    knownSlugs: verticals.map((v) => v.slug),
  }
}


/** Test helper — reset the module-level cache between tests. */
export function __resetVerticalsCacheForTests(): void {
  _verticalsPromise = null
}
