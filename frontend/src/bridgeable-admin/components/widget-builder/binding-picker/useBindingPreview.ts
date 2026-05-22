/**
 * useBindingPreview — WB-6 in-inspector preview-value hook.
 *
 * Resolves a candidate (saved_view_id + field_path + iteration_mode)
 * via the existing `executeSavedView` endpoint + WB-6's resolveBinding
 * runtime. Returns a stringified preview value or an error string.
 *
 * The hook debounces 200 ms (matches WB-4a auto-save pattern) so
 * picker authoring doesn't fire one fetch per keystroke. Cancels
 * in-flight fetches when inputs change.
 *
 * Bridges WB-6 → WB-5: operators verify their binding selections
 * during authoring without waiting for canvas-preview wiring.
 */
import { useEffect, useRef, useState } from "react"

import { executeSavedView } from "@/services/saved-views-service"
import { resolveBinding } from "@/lib/widget-builder/runtime/resolveBinding"
import type { BindingRef } from "@/lib/widget-builder/types/composition-blob"


export type BindingPreviewState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "value"; preview: string; description?: string }
  | { kind: "empty"; reason: string }
  | { kind: "error"; message: string }


function stringifyPreview(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}


export interface UseBindingPreviewArgs {
  savedViewId: string | null
  fieldPath: string | null
  iterationMode: "per_row" | "single_summary" | "single_record" | null
  /** Debounce ms (defaults to 200; matches WB-4a auto-save). */
  debounceMs?: number
}


export function useBindingPreview(
  args: UseBindingPreviewArgs,
): BindingPreviewState {
  const { savedViewId, fieldPath, iterationMode, debounceMs = 200 } = args
  const [state, setState] = useState<BindingPreviewState>({ kind: "idle" })
  const latestFetchId = useRef<number>(0)

  useEffect(() => {
    // No selection → idle.
    if (!savedViewId || !fieldPath || !iterationMode) {
      setState({ kind: "idle" })
      return
    }

    const fetchId = latestFetchId.current + 1
    latestFetchId.current = fetchId
    let cancelled = false

    const timer = setTimeout(() => {
      setState({ kind: "loading" })

      executeSavedView(savedViewId)
        .then((result) => {
          if (cancelled) return
          if (latestFetchId.current !== fetchId) return

          // Synthesize the right binding ref + dataContext.
          const ref: BindingRef = {
            binding_id: "__preview",
            binding_type: "field_path",
            saved_view_id: savedViewId,
            field_path: fieldPath,
            iteration_mode: iterationMode,
          }

          try {
            if (iterationMode === "single_summary") {
              const ctx = {
                __summary: true,
                aggregations: result.aggregations,
                total_count: result.total_count,
              }
              const value = resolveBinding(ref, ctx)
              setState({
                kind: "value",
                preview: stringifyPreview(value),
                description: `Aggregation over ${result.total_count} rows`,
              })
              return
            }

            const rows = result.rows ?? []
            if (rows.length === 0) {
              setState({
                kind: "empty",
                reason: "Saved view returned no rows",
              })
              return
            }

            // per_row + single_record both resolve against first row.
            const first = rows[0]
            const ctx = { __row: true, __index: 0, ...first }
            const value = resolveBinding(ref, ctx)

            const description =
              iterationMode === "per_row"
                ? `First row preview; ${result.total_count} total ${result.total_count === 1 ? "row" : "rows"}`
                : `First record at field_path`
            setState({
              kind: "value",
              preview: stringifyPreview(value),
              description,
            })
          } catch (err) {
            const msg =
              err instanceof Error ? err.message : "Resolution failed"
            setState({ kind: "error", message: msg })
          }
        })
        .catch((err: unknown) => {
          if (cancelled) return
          if (latestFetchId.current !== fetchId) return
          const msg = err instanceof Error ? err.message : "Fetch failed"
          setState({ kind: "error", message: msg })
        })
    }, debounceMs)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [savedViewId, fieldPath, iterationMode, debounceMs])

  return state
}
