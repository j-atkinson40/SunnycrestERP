/**
 * What a typed request opens. RULE-BASED — no model call in this slice.
 *
 * ⚠️ THE CLASSIFIER IS RULES ON PURPOSE, matching `command_bar/intent.py`, which is
 * explicitly rule-based to hold a p50 < 100 ms budget. "the catalog" is a fixed phrase; a
 * model call to recognise a fixed phrase would spend a round trip to learn nothing.
 */

/**
 * ⚠️ THE CAPTURE ENTRANCE, VERBATIM FROM THE PROTOTYPE (`:296`):
 *
 *   /\b(new|create|start|make|enter|put in|take)\b.*\border\b|^order for\b/
 *
 * Not re-worded. The prototype is the authority on what a director types, and a phrase
 * that starts a capture there and not here would be a difference nobody chose. The
 * SERVER carries the same regex (`session_service.START_SIGNAL`); this one exists so the
 * overlay can route without a round trip, exactly as `detectNLIntent.ts` mirrors
 * `intent.py`.
 *
 * ⚠️ THE WHOLE LINE IS PASSED THROUGH, NOT STRIPPED. The prototype starts the capture and
 * immediately feeds the same text (`:568`), which is what lets "start an order for
 * Hopkins" capture the funeral home on the opening keystroke.
 */
export const CAPTURE_START =
  /\b(new|create|start|make|enter|put in|take)\b.*\border\b|^order for\b/

/**
 * An opener followed by the beginning of a funeral home's name.
 *
 * ⚠️ JAMES TYPED "order hopk" ON PRODUCTION AND GOT NOTHING — no pane, no question
 * line, no ghost. `CAPTURE_START` requires a VERB before "order" ("new order…") or
 * the exact phrase "order for". Measured 2026-10-16: "order hopk" and "order from
 * hopk" both failed; "order for hopk" and "new order hopk" both worked. Nothing had
 * regressed — the opening was simply narrower than people type.
 *
 * ⚠️ AND THE COST COMPOUNDS, WHICH IS WHY IT READ AS A DEAD FEATURE. The ghost only
 * runs in entry mode, so an opening that does not start capture takes the completion
 * down with it — the bar is least able to help at exactly the moment the director is
 * typing a name it knows.
 *
 * ⚠️ IT IS GATED ON THE VOCABULARY, NOT ON "order" PLUS ANYTHING, AND THAT IS
 * DELIBERATE. `isOrderListPhrase` matches `\borders?\b`, so a blanket "order + word"
 * rule would swallow "order list" and route a list question into an order capture.
 * Requiring the next words to PREFIX a known funeral home is both narrower and
 * exactly what James asked for: "plus a funeral-home prefix".
 */
export function startsCaptureWithParty(
  phrase: string,
  funeralHomes: readonly string[],
): boolean {
  const m = /^\s*(?:new\s+|create\s+|start\s+(?:an?\s+)?|make\s+)?orders?\s+(?:for\s+|from\s+)?(.+)$/i
    .exec(phrase)
  if (!m) return false
  const rest = m[1].trim().toLowerCase()
  if (rest.length < 2) return false
  return funeralHomes.some((name) => {
    const n = name.toLowerCase()
    // ⚠️ EITHER DIRECTION: the typed text may be a prefix of the name ("hopk"), or
    // the name may be a prefix of a longer typed line ("hopkins funeral home
    // monticello"), which is what an opening line usually is.
    return n.startsWith(rest) || rest.startsWith(n.split(/\s+/)[0])
  })
}

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

/** The fields of a catalog candidate this module passes through. Structural on purpose
 *  so `CatalogVariant` and a hand-built test double both satisfy it. */
export interface RouteCandidate {
  variant_template_id: string
  name?: string
  option_label?: string
  sku?: string
}

export type OpasRoute =
  | { kind: "capture"; openingLine: string }
  | { kind: "product-list" }
  | { kind: "product"; variantTemplateId: string }
  /** ⚠️ CARRIES THE WHOLE CANDIDATES, NOT JUST THEIR IDS, SINCE 2026-10-20. It was
   *  `candidateIds: string[]`, which was enough while the pick lived in a pane that
   *  could look the variants up for itself. The pick now renders above the bar as a
   *  numbered option list (James's third rule), and a list of opaque uuids is not a
   *  list of choices — each row has to say the product's name and what tells it apart.
   *  `candidateIds` is kept alongside, derived, because three tests and the Escape
   *  flag address it and deriving it here keeps the two from drifting. */
  | {
      kind: "numbered-pick"
      candidateIds: string[]
      candidates: RouteCandidate[]
      discriminators: string[]
    }
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
  candidates: RouteCandidate[]
  discriminators: string[]
}): OpasRoute {
  if (r.candidates.length === 1) {
    return { kind: "product", variantTemplateId: r.candidates[0].variant_template_id }
  }
  if (r.candidates.length > 1) {
    return {
      kind: "numbered-pick",
      // ⚠️ DERIVED FROM `candidates`, NOT COLLECTED SEPARATELY, so the two cannot
      // disagree about which candidates are in the pick or about their order.
      candidateIds: r.candidates.map((c) => c.variant_template_id),
      candidates: r.candidates,
      discriminators: r.discriminators,
    }
  }
  return { kind: "product-list-unmatched", phrase: r.phrase }
}
