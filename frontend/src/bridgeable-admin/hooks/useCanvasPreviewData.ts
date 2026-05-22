/**
 * useCanvasPreviewData — WB-5 canvas-side fetch orchestrator.
 *
 * Walks `blob.bindings_catalog`, deduplicates `saved_view_id`s, and
 * fetches each unique view via `executeSavedView`. Returns a map
 * keyed on `saved_view_id` carrying loading / success / error state
 * with optimistic-stale-rendering support.
 *
 * Substrate parity:
 *   - Dedup at saved_view_id level (Lock 6a / Risk 6) — different
 *     field_paths against the same view share one fetch.
 *   - Per-saved-view AbortController + fetchId discriminator (Lock 6a).
 *     The AbortController is the primary defense; the fetchId check
 *     is defense-in-depth for responses that landed after abort fired
 *     but before .then() ran.
 *   - 200ms debounce on the set of saved_view_ids (Lock 5a / Risk 8) —
 *     keystroke-rate config edits to non-binding properties do not
 *     re-fire fetches; only changes to the set of referenced views.
 *   - Optimistic stale rendering: while a fetch is in flight, the
 *     prior success result is retained as `previous` so the canvas
 *     can keep rendering data (with a shimmer overlay) instead of
 *     flashing through an empty / skeleton state on every refresh.
 *
 * Coexistence with WB-4a `useWidgetAutoSave`: completely separate
 * controller refs + separate request paths (GET
 * /saved-views/{id}/execute vs PUT /widget-definitions/{slug}/draft).
 * Source-shape regression gate verifies the separation (Risk 3).
 *
 * Tenant context is operator's JWT (implicit) per Area 2 Lock 2a —
 * `executeSavedView` reads `current_user.company_id` at the backend;
 * the canvas does not need to thread tenant explicitly.
 */
import { useEffect, useMemo, useRef, useState } from "react"

import { executeSavedView } from "@/services/saved-views-service"
import type {
  BindingRef,
  CompositionBlob,
} from "@/lib/widget-builder/types/composition-blob"
import type { SavedViewResult } from "@/types/saved-views"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"


/** Error class surfaced to the canvas per Area 4. */
export type CanvasPreviewErrorCode =
  | "view_not_found"
  | "permission_denied"
  | "network_error"
  | "fetch_failed"


/** Structured error descriptor flowing in the `__error` flavor. */
export interface CanvasPreviewError {
  code: CanvasPreviewErrorCode
  message: string
  /** Whether the error is a network-class condition that warrants the
   *  canvas-level banner (per Lock 4a). E1/E2 are atom-level only;
   *  E4 (network) is canvas-level. */
  network_class: boolean
}


export interface CanvasPreviewFetchState {
  status: "loading" | "success" | "error"
  /** Present when status==="success" (current fresh result) or
   *  status==="loading" with prior data (optimistic stale). */
  data?: SavedViewResult
  /** Optimistic-stale handle — the last successful result rendered
   *  alongside a shimmer overlay while a refresh is in flight. */
  previous?: SavedViewResult
  /** Present when status==="error". */
  error?: CanvasPreviewError
}


/** The map type consumed by WidgetCanvas. */
export type CanvasPreviewDataMap = Record<string, CanvasPreviewFetchState>


/** Public debounce constant — parallels WB-4a + WB-6 200ms convention. */
export const CANVAS_PREVIEW_DEBOUNCE_MS = 200


/** Walk the bindings catalog and extract the deduplicated set of
 *  saved_view_ids referenced by field_path bindings.
 *  Literal bindings are skipped (they carry no view reference). */
export function extractSavedViewIds(
  bindingsCatalog: Record<string, BindingRef> | undefined,
): string[] {
  if (!bindingsCatalog) return []
  const ids = new Set<string>()
  for (const ref of Object.values(bindingsCatalog)) {
    if (ref.binding_type === "field_path" && ref.saved_view_id) {
      ids.add(ref.saved_view_id)
    }
  }
  // Sorted for stable memo keys (debounce + effect dependency).
  return Array.from(ids).sort()
}


/** Classify an unknown thrown error into a CanvasPreviewError. */
function classifyError(err: unknown): CanvasPreviewError {
  // Axios-style error shape detection (apiClient uses Axios).
  const ax = err as {
    response?: { status?: number; data?: { detail?: string } }
    message?: string
    code?: string
  }
  const status = ax?.response?.status
  const detail = ax?.response?.data?.detail
  const message = detail ?? ax?.message ?? "Fetch failed"

  if (status === 404) {
    return {
      code: "view_not_found",
      message: detail ?? "Saved view not found",
      network_class: false,
    }
  }
  if (status === 403) {
    return {
      code: "permission_denied",
      message: detail ?? "No permission for saved view",
      network_class: false,
    }
  }
  // Network class — no response, or 5xx, or explicit Axios network code.
  if (
    ax?.code === "ERR_NETWORK" ||
    ax?.code === "ECONNABORTED" ||
    (status !== undefined && status >= 500) ||
    status === undefined
  ) {
    return {
      code: "network_error",
      message,
      network_class: true,
    }
  }
  return { code: "fetch_failed", message, network_class: false }
}


/**
 * Public hook.
 *
 * Returns a stable map keyed on saved_view_id; reads should be
 * defensive against missing keys (caller falls back to undefined
 * dataContext when a binding's view isn't yet in the map).
 *
 * On unmount: aborts every in-flight fetch.
 */
export function useCanvasPreviewData(
  compositionBlob: CompositionBlob | null,
  /** Override the debounce window. Tests pass 0 to fire immediately;
   *  production callers omit (default 200ms per Lock 5a + WB-4a
   *  + WB-6 200ms convention). */
  debounceMs: number = CANVAS_PREVIEW_DEBOUNCE_MS,
): CanvasPreviewDataMap {
  const [resultsMap, setResultsMap] = useState<CanvasPreviewDataMap>({})

  // Memoize the deduplicated set of saved_view_ids; the stringified
  // set is what we debounce on (per Risk 8 — only re-fire when the
  // referenced views actually change, not on every blob mutation).
  const savedViewIds = useMemo(
    () =>
      extractSavedViewIds(
        compositionBlob?.bindings_catalog,
      ),
    [compositionBlob?.bindings_catalog],
  )

  // Stringified key drives both debounce + effect dependency.
  const idsKey = useMemo(() => savedViewIds.join("|"), [savedViewIds])
  const debouncedIdsKey = useDebouncedValue(idsKey, debounceMs)

  // Per-saved-view AbortController + fetchId discriminator.
  // Map<saved_view_id, { controller, fetchId }>. Lives across renders
  // via ref so abort semantics survive React re-renders.
  const controllersRef = useRef<
    Map<string, { controller: AbortController; fetchId: number }>
  >(new Map())

  // Monotonically increasing per-saved-view counter — only the
  // most-recent fetchId for a given view applies its response.
  const fetchIdCountersRef = useRef<Map<string, number>>(new Map())

  // Cleanup on unmount — abort everything in-flight.
  useEffect(() => {
    return () => {
      for (const { controller } of controllersRef.current.values()) {
        controller.abort()
      }
      controllersRef.current.clear()
    }
  }, [])

  useEffect(() => {
    // Resolve the debounced ids back to an array. Empty key → no
    // bindings; keep the map state but DO NOT clear it (caller will
    // treat missing keys as undefined dataContext anyway, and stale
    // entries for views that have left the catalog are harmless until
    // next mount).
    const ids = debouncedIdsKey === "" ? [] : debouncedIdsKey.split("|")

    if (ids.length === 0) {
      return
    }

    for (const viewId of ids) {
      // Determine which views need (re)fetching. For Phase 1 we always
      // re-fetch on debounced-set change; per-view caching across
      // multiple set-shrink-then-grow cycles is post-arc.
      const existing = controllersRef.current.get(viewId)
      if (existing) {
        existing.controller.abort()
      }

      const nextFetchId = (fetchIdCountersRef.current.get(viewId) ?? 0) + 1
      fetchIdCountersRef.current.set(viewId, nextFetchId)

      const controller = new AbortController()
      controllersRef.current.set(viewId, {
        controller,
        fetchId: nextFetchId,
      })

      // Optimistic stale: transition to "loading" but retain the
      // prior `data` as `previous` so atoms can keep rendering with
      // a shimmer overlay.
      setResultsMap((prev) => {
        const prior = prev[viewId]
        if (prior?.status === "success" && prior.data) {
          return {
            ...prev,
            [viewId]: {
              status: "loading",
              previous: prior.data,
            },
          }
        }
        return {
          ...prev,
          [viewId]: { status: "loading" },
        }
      })

      // Fire the fetch.
      executeSavedView(viewId)
        .then((result) => {
          // Defense-in-depth: ignore late responses superseded by
          // newer fetches (per Lock 6a).
          if (controller.signal.aborted) return
          const latest = fetchIdCountersRef.current.get(viewId)
          if (latest !== nextFetchId) return
          setResultsMap((prev) => ({
            ...prev,
            [viewId]: { status: "success", data: result },
          }))
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          const latest = fetchIdCountersRef.current.get(viewId)
          if (latest !== nextFetchId) return
          setResultsMap((prev) => {
            const prior = prev[viewId]
            // Preserve previous success as `previous` so the operator
            // can see the last-known-good value alongside the error
            // chrome (Phase 1 surfaces the error; previous data is
            // available for future UX if it proves valuable).
            const previous =
              prior?.status === "success" ? prior.data : prior?.previous
            return {
              ...prev,
              [viewId]: {
                status: "error",
                error: classifyError(err),
                previous,
              },
            }
          })
        })
    }
  }, [debouncedIdsKey])

  return resultsMap
}
