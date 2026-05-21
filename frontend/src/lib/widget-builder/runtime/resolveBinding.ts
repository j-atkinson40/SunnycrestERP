/**
 * resolveBinding — WB-2 placeholder data-binding helper.
 *
 * Phase 1 scope (intentionally narrow):
 *   - binding_type === "literal" → returns BindingRef.literal_value verbatim.
 *   - binding_type === "field_path" → returns a placeholder string
 *     `[bound:${field_path}]`. WB-6 makes this real (saved-view query
 *     execution + row-shape projection + iteration_mode handling).
 *   - Malformed BindingRef (unknown binding_type) throws — defensive
 *     gate; codec is supposed to have already validated structurally.
 *
 * Consumer interface (`(bindingRef, dataContext?) → unknown`) stays
 * stable across WB-2 → WB-6. ComposedWidget + AtomRenderer don't
 * care what's inside; they wire the value to the per-atom config
 * field name declared in `AtomNode.binding_refs`.
 *
 * dataContext is unused in Phase 1; declared to lock the eventual
 * call shape so WB-6 doesn't have to recoordinate every call site.
 */

import type { BindingRef } from "../types/composition-blob"

export function resolveBinding(
  bindingRef: BindingRef,
  dataContext?: unknown,
): unknown {
  if (bindingRef.binding_type === "literal") {
    return bindingRef.literal_value
  }
  if (bindingRef.binding_type === "field_path") {
    // WB-3 — per-row dataContext placeholder. When AtomRenderer is
    // iterating a repeater_atom, it passes a per-row dataContext
    // object signaling iteration: `{ __row: true, __index: number }`.
    // Phase 1 surface a marker that distinguishes per-row from
    // page-scoped resolution so authors see the iteration is wired.
    // WB-6 makes both real.
    if (
      typeof dataContext === "object" &&
      dataContext !== null &&
      (dataContext as { __row?: boolean }).__row === true
    ) {
      const idx = (dataContext as { __index?: number }).__index ?? 0
      return `[bound:row.${bindingRef.field_path ?? "<missing>"}#${idx}]`
    }
    return `[bound:${bindingRef.field_path ?? "<missing>"}]`
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
