/**
 * resolveBinding — WB-6 data-binding helper.
 *
 * Substantiates WB-2's Phase 1 placeholder. Now handles real
 * field_path resolution against saved-view data — dot-notation
 * traversal with numeric-segment array indexing, null-safe on
 * missing paths, throws on malformed path syntax, per-row context
 * via dataContext spread, aggregate path resolution via
 * `iteration_mode='single_summary'`.
 *
 * Phase 1 semantics (per Area 3 + Area 4 locks):
 *   - `literal` → returns BindingRef.literal_value verbatim
 *     (BACKWARD-COMPAT preserved: behavior unchanged vs WB-2).
 *   - `field_path` + `iteration_mode='per_row'` → resolves field_path
 *     against `dataContext` (the spread row dict). Returns the value
 *     at the dotted path, or null on missing.
 *   - `field_path` + `iteration_mode='single_record'` → resolves
 *     against the row dict at `dataContext` (provided by caller; the
 *     first row is selected by the caller from SavedViewResult.rows).
 *   - `field_path` + `iteration_mode='single_summary'` → resolves
 *     against `dataContext.aggregations` (and `dataContext.total_count`
 *     as a synthetic `count` shortcut) — caller passes the full
 *     SavedViewResult as dataContext for summary mode.
 *
 * Malformed field_path syntax (empty string, consecutive dots,
 * leading/trailing dot) throws. Missing path traversal (any
 * intermediate is null/undefined) returns null defensively — atom
 * renderers consume null as missing data + render placeholder.
 *
 * dataContext shape contract (WB-6):
 *   { __row: true, __index: number, ...rowDict }  // per_row mode
 *   { __row: true, __index: 0, ...rows[0] }       // single_record
 *   { __summary: true, aggregations?: object,
 *     total_count?: number }                       // single_summary
 *   undefined / null                                // no context
 */

import type { BindingRef } from "../types/composition-blob"


/** Parse a dotted field_path into segments. Throws on malformed input.
 *
 *  Valid: `a`, `a.b`, `a.b.c`, `items.0.name`, `aggregations.value`.
 *  Invalid: ``, `.a`, `a.`, `a..b`.
 */
export function parseFieldPath(path: string): string[] {
  if (path === "") {
    throw new Error(`[resolveBinding] malformed field_path: empty string`)
  }
  if (path.startsWith(".") || path.endsWith(".")) {
    throw new Error(
      `[resolveBinding] malformed field_path: leading/trailing dot in ${JSON.stringify(path)}`,
    )
  }
  if (path.includes("..")) {
    throw new Error(
      `[resolveBinding] malformed field_path: consecutive dots in ${JSON.stringify(path)}`,
    )
  }
  return path.split(".")
}


/** Walk dotted path segments against `target`. Null-safe on missing
 *  intermediates; numeric segments index into arrays. */
export function walkFieldPath(target: unknown, segments: string[]): unknown {
  let cursor: unknown = target
  for (const segment of segments) {
    if (cursor === null || cursor === undefined) return null
    // Numeric segment → array index
    if (/^\d+$/.test(segment)) {
      const idx = parseInt(segment, 10)
      if (!Array.isArray(cursor)) return null
      cursor = cursor[idx]
      continue
    }
    if (typeof cursor !== "object") return null
    cursor = (cursor as Record<string, unknown>)[segment]
  }
  // Convert undefined→null for a stable null-on-missing contract.
  return cursor === undefined ? null : cursor
}


/** Determine whether dataContext signals per-row iteration. */
function isPerRowContext(dataContext: unknown): boolean {
  return (
    typeof dataContext === "object" &&
    dataContext !== null &&
    (dataContext as { __row?: boolean }).__row === true
  )
}


/** Determine whether dataContext signals single_summary scope. */
function isSummaryContext(dataContext: unknown): boolean {
  return (
    typeof dataContext === "object" &&
    dataContext !== null &&
    (dataContext as { __summary?: boolean }).__summary === true
  )
}


export function resolveBinding(
  bindingRef: BindingRef,
  dataContext?: unknown,
): unknown {
  if (bindingRef.binding_type === "literal") {
    // BACKWARD-COMPAT: literal behavior unchanged from WB-2. Existing
    // callers passing literal bindings continue working without any
    // adjustment. dataContext is ignored.
    return bindingRef.literal_value
  }

  if (bindingRef.binding_type === "field_path") {
    const fp = bindingRef.field_path ?? ""
    if (fp === "") {
      // WB-2 backward-compat: an unset field_path renders the
      // <missing> sentinel placeholder. WB-6 strict validator (Publish
      // gate) rejects empty/missing field_path on field_path bindings,
      // so this is only reachable for in-flight draft state.
      return `[bound:<missing>]`
    }

    // Parse segments (throws on malformed syntax).
    const segments = parseFieldPath(fp)

    const mode = bindingRef.iteration_mode

    // single_summary → resolve against dataContext (expected shape:
    // SavedViewResult-ish — `aggregations` + `total_count`). Provides a
    // synthetic `count` shortcut so authors can bind to total_count
    // without separate plumbing.
    if (mode === "single_summary") {
      if (!isSummaryContext(dataContext)) return null
      const ctx = dataContext as {
        aggregations?: unknown
        total_count?: number
      }
      // Special-case: `count` → total_count.
      if (segments.length === 1 && segments[0] === "count") {
        return ctx.total_count ?? null
      }
      // Top-level `aggregations.x.y` resolves against the full ctx
      // (operator names the aggregations prefix explicitly).
      if (segments[0] === "aggregations") {
        return walkFieldPath(ctx, segments)
      }
      // Otherwise resolve against `aggregations` directly — the most
      // common author intent ("value", "comparison_delta").
      return walkFieldPath(ctx.aggregations, segments)
    }

    // per_row + single_record both resolve against a per-row context
    // (spread row dict). Caller arranges single_record by passing the
    // first row as the context with __row=true semantics.
    if (mode === "per_row" || mode === "single_record") {
      if (!isPerRowContext(dataContext)) return null
      return walkFieldPath(dataContext, segments)
    }

    // No iteration_mode declared (loose / draft state). Behave like
    // single_record if context is per-row; otherwise null. The strict
    // validator rejects this at Publish per WB-6 Lock 5e.
    if (isPerRowContext(dataContext)) {
      return walkFieldPath(dataContext, segments)
    }
    return null
  }

  // Defensive: WB-1 codec rejects unknown binding_types structurally;
  // this throw catches a hypothetical bypass (direct construction in
  // tests, future binding_type addition without resolver update).
  throw new Error(
    `[resolveBinding] unknown binding_type: ${
      (bindingRef as { binding_type: string }).binding_type
    }`,
  )
}
