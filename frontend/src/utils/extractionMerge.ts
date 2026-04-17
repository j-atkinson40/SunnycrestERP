// Field-merging rules for natural-language workflow extraction.
// See NaturalLanguageOverlay.tsx — the overlay calls extract on debounce,
// then merges the new field payload into the current state additively.

export interface ExtractedField {
  value: unknown
  display_value: string
  confidence: number
  matched_id?: string | null
  matched_type?: string | null
  unresolved?: boolean
  alternatives?: string[]
  // Conflict bookkeeping
  previous_value?: string
  is_conflict?: boolean
  is_new?: boolean
}

export type FieldMap = Record<string, ExtractedField>

/** Merge a new extraction payload into the existing fields.
 *  - Low-confidence (< 0.6) incoming fields are dropped.
 *  - New keys are added verbatim.
 *  - Same value with higher confidence → bump confidence.
 *  - Existing *high*-confidence key conflicts with a different new value
 *    → mark `is_conflict`, keep `previous_value` for UI revert.
 *  - Existing *low*-confidence key is replaced when new confidence is
 *    higher.
 */
export function mergeExtractions(
  existing: FieldMap,
  incoming: FieldMap,
): FieldMap {
  const merged: FieldMap = { ...existing }
  for (const [key, nf] of Object.entries(incoming || {})) {
    if (!nf || typeof nf.confidence !== "number") continue
    if (nf.confidence < 0.6) continue

    const cur = merged[key]
    if (!cur) {
      merged[key] = { ...nf, is_new: true }
      continue
    }

    const sameValue =
      String(cur.display_value || "").toLowerCase().trim() ===
      String(nf.display_value || "").toLowerCase().trim()

    if (sameValue) {
      if (nf.confidence > cur.confidence) {
        merged[key] = {
          ...cur,
          confidence: nf.confidence,
          matched_id: nf.matched_id ?? cur.matched_id,
        }
      }
      continue
    }

    if (cur.confidence >= 0.85) {
      // Existing was confident, new differs → flag conflict
      merged[key] = {
        ...nf,
        is_conflict: true,
        previous_value: cur.display_value,
      }
      continue
    }

    if (nf.confidence > cur.confidence) {
      merged[key] = nf
    }
  }
  return merged
}

/** Return only fields whose extraction is confident. Used to tell the
 *  backend which fields it should preserve on subsequent calls.  */
export function getConfidentFields(
  fields: FieldMap,
): Record<string, { value: unknown; display_value: string; confidence: number }> {
  const out: Record<
    string,
    { value: unknown; display_value: string; confidence: number }
  > = {}
  for (const [key, f] of Object.entries(fields)) {
    if (!f || f.is_conflict) continue
    if (f.confidence >= 0.85) {
      out[key] = {
        value: f.value,
        display_value: f.display_value,
        confidence: f.confidence,
      }
    }
  }
  return out
}

/** Strip the UI-only bookkeeping so we submit clean inputs to
 *  the workflow engine.  */
export function flattenForSubmit(
  fields: FieldMap,
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [key, f] of Object.entries(fields)) {
    if (!f) continue
    // Pass the resolved id for crm_search / record_search fields,
    // otherwise the raw value. The workflow engine expects either a
    // primitive or an {id, name} shape.
    if (f.matched_id) {
      out[key] = { id: f.matched_id, name: f.display_value }
    } else {
      out[key] = f.value ?? f.display_value
    }
  }
  return out
}
