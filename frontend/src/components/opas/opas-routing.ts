/**
 * What a typed request opens. RULE-BASED — no model call in this slice.
 *
 * ⚠️ THE CLASSIFIER IS RULES ON PURPOSE, matching `command_bar/intent.py`, which is
 * explicitly rule-based to hold a p50 < 100 ms budget. "the catalog" is a fixed phrase; a
 * model call to recognise a fixed phrase would spend a round trip to learn nothing.
 */

/** Phrases that open the Product List. Lower-cased, trimmed, punctuation-stripped. */
const CATALOG_PHRASES: readonly string[] = [
  "catalog",
  "the catalog",
  "show catalog",
  "show the catalog",
  "open catalog",
  "open the catalog",
  "products",
  "the products",
  "product catalog",
  "the product catalog",
]

/** ⚠️ Strips trailing punctuation and collapses whitespace. A director typing "the
 *  catalog." or "the  catalog" means the catalog; failing on a full stop would be the
 *  kind of brittleness that makes an overlay feel broken rather than strict. */
export function normalizeRequest(text: string): string {
  // ⚠️ TRIM BEFORE STRIPPING PUNCTUATION. Written the other way round first, and a test
  // caught it: the `$` anchor cannot match a full stop that has whitespace after it, so
  // "  THE CATALOG!  " survived as "the catalog!" and failed to match.
  return text
    .toLowerCase()
    .trim()
    .replace(/[.!?,;:]+$/g, "")
    .replace(/\s+/g, " ")
    .trim()
}

export function isCatalogRequest(text: string): boolean {
  return CATALOG_PHRASES.includes(normalizeRequest(text))
}

export type OpasRoute =
  | { kind: "product-list" }
  | { kind: "product"; variantTemplateId: string }
  | { kind: "numbered-pick"; candidateIds: string[]; discriminators: string[] }
  | { kind: "product-list-unmatched"; phrase: string }

/**
 * Decide what a phrase opens, given a resolution.
 *
 * ⚠️ THE THREE BRANCHES ARE THE RULING, and the middle one is the one that matters:
 *
 *   one candidate    -> the Product pane
 *   several          -> a NUMBERED PICK (per the spec and the prototype's `.pick` list;
 *                       the earlier "filtered list" branch was withdrawn)
 *   none             -> the Product List, unfiltered, with the phrase shown as not matched
 *
 * ⚠️ NEITHER THE RESOLVER NOR THIS FUNCTION PICKS. `Resolution.variant_template_id` is
 * deliberately null when ambiguous, and this returns the whole candidate set plus the
 * discriminators that would narrow it. Choosing "the best match" here would discard exactly
 * what the resolver returns a set to preserve.
 */
export function routeResolution(r: {
  phrase: string
  candidates: { variant_template_id: string }[]
  discriminators: string[]
}): OpasRoute {
  if (r.candidates.length === 1) {
    return { kind: "product", variantTemplateId: r.candidates[0].variant_template_id }
  }
  if (r.candidates.length > 1) {
    return {
      kind: "numbered-pick",
      candidateIds: r.candidates.map((c) => c.variant_template_id),
      discriminators: r.discriminators,
    }
  }
  return { kind: "product-list-unmatched", phrase: r.phrase }
}
