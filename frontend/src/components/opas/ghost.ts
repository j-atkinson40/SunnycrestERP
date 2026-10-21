/**
 * Ghost completion: what the bar offers after the caret.
 *
 * ⚠️ PURE AND CLIENT-SIDE. James 2026-10-16: "Matching is client-side only" and
 * "keystroke latency must not depend on the network". Keeping it a pure function of
 * (text, caret, vocabulary) is also what makes the tie-break testable — the rule is
 * the hard part of this feature, not the rendering.
 */

export interface VocabTerm {
  readonly text: string
  readonly kind: string
  /** Does this tenant carry it? Breaks ties — see `completionFor`. */
  readonly carried?: boolean
  readonly note?: string | null
  /** Catalog form for vault terms: `burial_vault`, `urn_vault`, ... */
  readonly form?: string | null
}

/** ⚠️ THE SAME DEFAULT THE CAPTURE ALREADY USES. James 2026-10-13 ruled that a vault
 *  phrase ambiguous ONLY by form resolves to the burial vault; 2026-10-16 extended it
 *  to the ghost. The office means a burial vault nine times in ten. */
const BURIAL = "burial_vault"

/**
 * Do these matches differ ONLY by form?
 *
 * ⚠️ IT MIRRORS THE CAPTURE'S CONDITION, WHICH IS `discriminators === ("form",)`
 * EXACTLY — not "form is among them". `Continental Burial Vault` and `Continental 34"`
 * differ by SIZE as well, and the capture refuses to guess there; so does this. The
 * test is whether removing each term's own form word leaves them all identical.
 */
function differOnlyByForm(matches: readonly VocabTerm[]): boolean {
  if (matches.length < 2) return false
  if (!matches.every((m) => m.form)) return false
  if (new Set(matches.map((m) => m.form)).size < 2) return false
  const stems = new Set(
    matches.map((m) => {
      const word = (m.form ?? "").split("_")[0] // burial_vault -> "burial"
      return norm(m.text).replace(new RegExp(`\\b${word}\\b`, "g"), "").replace(/\s+/g, " ").trim()
    }),
  )
  return stems.size === 1
}

export interface Ghost {
  /** The characters to show after the caret, and to insert on Tab. */
  readonly suffix: string
  /** The whole term being completed to, for the label. */
  readonly term: VocabTerm
}

/** ⚠️ MINIMUM 2 CHARACTERS, BY RULING. One letter matches most of the vocabulary. */
export const MIN_PREFIX = 2

/** How many trailing words a prefix may span. "hopkins fu" is two. */
const MAX_WORDS = 4

function norm(s: string): string {
  return s.toLowerCase().replace(/\s+/g, " ").trim()
}

/**
 * How far into `term` the typed `prefix` reaches, ignoring punctuation and spacing,
 * or -1 if it does not.
 *
 * ⚠️ PUNCTUATION-TOLERANT, AND "st m" IS WHY. A director types "st m"; the record is
 * `St. Mary's Cemetery`. A plain `startsWith` on the lowercased strings fails on the
 * PERIOD, so the ruling's own example offered nothing. Measured 2026-10-16.
 *
 * ⚠️ EXPORTED SO THE GENERATED CORPUS CAN HOLD THE PYTHON PORT TO IT. The walk is
 * corpus'd SEPARATELY from the resolutions, because a port can agree on every final
 * answer and still differ on the walk — and the walk is what produces the visible
 * suffix, so a divergence draws "ry's Cemetery" where it meant "ary's Cemetery".
 *
 * ⚠️ IT RETURNS AN INDEX INTO THE ORIGINAL TERM, NOT INTO A NORMALISED COPY, which is
 * the whole reason this is a walk rather than a `normalize().startsWith()`. The
 * completion is `term.slice(index)` — computed on a stripped copy it would be off by
 * one character per punctuation mark skipped, and the ghost would show "ry's
 * Cemetery" where it meant "ary's Cemetery".
 */
export function consumeLoose(term: string, prefix: string): number {
  const skippable = (ch: string) => /[^a-z0-9]/i.test(ch)
  let ti = 0
  let pi = 0
  while (pi < prefix.length) {
    // skip characters in the PREFIX that carry no identity
    if (skippable(prefix[pi]) ) {
      // a space in the prefix must still force a boundary in the term
      if (/\s/.test(prefix[pi])) {
        while (ti < term.length && !/\s/.test(term[ti])) ti++
        while (ti < term.length && /\s/.test(term[ti])) ti++
      }
      pi++
      continue
    }
    while (ti < term.length && skippable(term[ti]) && !/\s/.test(term[ti])) ti++
    if (ti >= term.length) return -1
    if (term[ti].toLowerCase() !== prefix[pi].toLowerCase()) return -1
    ti++
    pi++
  }
  return ti
}

/**
 * The completion for this text and caret, or null.
 *
 * THE RULE, STATED BECAUSE THE DISPATCH ASKS FOR IT:
 *
 *   1. The caret must be at the END of the text. A completion offered mid-sentence
 *      would be inserted where the director is not looking.
 *   2. Take the trailing 1..4 words as candidate prefixes, LONGEST FIRST, so
 *      "hopkins fu" is tried before "fu".
 *   3. A prefix shorter than 2 characters offers nothing.
 *   4. Matches are terms whose normalised text STARTS WITH the normalised prefix and
 *      is longer than it.
 *   5. ⚠️ IF ANY MATCH IS CARRIED BY THIS TENANT, ONLY CARRIED MATCHES COUNT. This
 *      is the step that makes the ruling's own example work: the platform catalog
 *      holds both `Monticello Burial Vault` and `Monticello Urn Vault`, so "monti" is
 *      ambiguous across the catalog and would offer nothing — but sunnycrest carries
 *      only the burial vault.
 *   6. Exactly one match -> offer it.
 *   7. Several -> offer their LONGEST COMMON PREFIX, if that is longer than what was
 *      typed. Otherwise nothing.
 *
 * ⚠️ STEP 7 IS A DELIBERATE WIDENING OF THE DISPATCH'S WORDING, which says "offer
 * none unless one is a strict extension of all others". Taken literally, two terms
 * sharing a stem offer nothing at all, and a director typing "monti" on a tenant
 * carrying both vaults gets no help whatever. The common prefix completes exactly as
 * far as the vocabulary AGREES and stops — which is what shell completion does, and
 * which can never insert a word the terms disagree about. Where one term IS a strict
 * extension of all the others the two rules give the same answer.
 */
/** Vocabulary kinds naming a catalog VARIANT rather than a tenant's own product. */
const VARIANT_KINDS = new Set(["vault", "vault_alias"])

/**
 * Drop tenant product names when a catalog VARIANT already matches.
 *
 * ⚠️ RULED 2026-10-21, AND THIS STEP IS WHAT MAKES THAT RULING SAFE. Product names
 * joined the vocabulary so "venet" can reach Venetian — the variants are spelled
 * `White Venetian Burial Vault` and `Gold Venetian Burial Vault`, so "venet" prefixes
 * neither. But sunnycrest's `products` table also holds `Monticello Burial Vault`, so
 * without this a prefix that RESOLVES today would start ASKING.
 *
 * ⚠️ A PRODUCT NAME IS A ROUTE OF LAST RESORT, NOT A COMPETITOR: it adds reach where
 * the variants' own spellings cannot be prefixed, and says nothing new where they can.
 * Mirrored from `prefix_resolve.py::_rank_down_products` and held to it by the corpus.
 */
export function rankDownProducts(
  matches: readonly VocabTerm[],
): readonly VocabTerm[] {
  const variants = matches.filter((t) => VARIANT_KINDS.has(t.kind))
  return variants.length > 0 ? variants : matches
}

/** What a prefix MEANS, before any decision about how much to draw. */
export interface PrefixResolution {
  readonly prefix: string
  /** Every term still in play after the tie-breaks. */
  readonly matches: readonly VocabTerm[]
  /** The single term this prefix means, or null when it is a question. */
  readonly chosen: VocabTerm | null
}

/**
 * Steps 4-6a of the rule above, as their own function.
 *
 * ⚠️ EXTRACTED SO THE SERVER CAN BE HELD TO IT. James ruled on 2026-10-20 that the
 * extractor must accept abbreviations "using exactly the ghost's vocabulary and
 * tie-break rules (one source of truth, not a copy)". The vocabulary genuinely is one
 * source — `build_vocabulary` makes it and `/capture/vocabulary` serves these very rows.
 * The RULE cannot be one implementation: this must stay client-side (James, 2026-10-16:
 * "keystroke latency must not depend on the network") and the extractor runs on the
 * server, so neither can call the other.
 *
 * ⚠️ SO THE PAIR IS HELD BY A GENERATED CORPUS, NOT BY CARE.
 * `backend/tests/data/opas_prefix_corpus.json` is produced FROM the Python rule and
 * replayed through this function by `ghost-agrees.test.ts`. Change one side only and
 * that suite goes red. Same device as the canvas validators.
 *
 * ⚠️ WHAT THIS DOES *NOT* DECIDE IS HOW MUCH TO DRAW. On several matches it reports a
 * question; `completionFor` then offers their longest common prefix, because a ghost
 * can usefully complete as far as the vocabulary AGREES. The extractor has no
 * equivalent of that and does not need one — it resolves or it asks. The corpus
 * therefore compares MEANING, not suffixes, and that boundary is the reason the two
 * can be compared at all.
 */
export function resolvePrefix(
  prefix: string,
  vocab: readonly VocabTerm[],
  kinds?: readonly string[],
): PrefixResolution | null {
  const p = norm(prefix)
  if (p.length < MIN_PREFIX) return null

  const pool = kinds ? vocab.filter((t) => kinds.includes(t.kind)) : vocab
  // ⚠️ `readonly`, BECAUSE `rankDownProducts` RETURNS ONE. Typed as `VocabTerm[]` this
  // failed `tsc -b` with TS4104 — which is the error class that froze the deploy on
  // 2026-10-20, so it is worth the annotation rather than a cast.
  let matches: readonly VocabTerm[] = pool.filter((t) => {
    const at = consumeLoose(t.text, prefix)
    return at > 0 && at < t.text.length
  })
  if (matches.length === 0) return null

  const carried = matches.filter((t) => t.carried)
  if (carried.length > 0) matches = carried

  matches = rankDownProducts(matches)

  if (matches.length === 1) return { prefix, matches, chosen: matches[0] }

  if (differOnlyByForm(matches)) {
    const burial = matches.find((m) => m.form === BURIAL)
    if (burial) return { prefix, matches, chosen: burial }
  }

  // ⚠️ SEVERAL TERMS WITH THE SAME TEXT ARE ONE ANSWER, NOT A QUESTION. The vocabulary
  // is keyed on (kind, text), so one name carried as both a variant and a confirmed
  // alias appears twice, and "did you mean X or X?" is unanswerable.
  if (new Set(matches.map((m) => norm(m.text))).size === 1) {
    return { prefix, matches, chosen: matches[0] }
  }

  return { prefix, matches, chosen: null }
}

export function completionFor(
  text: string,
  caret: number | null,
  vocab: readonly VocabTerm[],
): Ghost | null {
  if (!text || caret === null || caret !== text.length) return null
  if (vocab.length === 0) return null
  // ⚠️ A TRAILING SPACE ENDS A WORD AND OFFERS NOTHING. Completing after "hopkins "
  // would append to a word the director has finished.
  if (/\s$/.test(text)) return null

  const words = text.split(/\s+/).filter(Boolean)
  for (let n = Math.min(MAX_WORDS, words.length); n >= 1; n--) {
    const prefix = words.slice(words.length - n).join(" ")
    if (prefix.length < MIN_PREFIX) continue
    const p = norm(prefix)
    if (!p) continue

    // ⚠️ THE MATCHING AND THE TIE-BREAKS NOW LIVE IN `resolvePrefix`, which the server
    // is held to by a generated corpus. Only the DRAWING decision stays here.
    const res = resolvePrefix(prefix, vocab)
    if (res === null) continue
    const matches = res.matches

    if (res.chosen !== null) {
      // ⚠️ STEP 6a, RULED 2026-10-16: a vault ambiguous ONLY by form offers the burial
      // vault. Tenant scoping happens to resolve that today because sunnycrest stocks
      // one Monticello — the day it stocks the urn vault too, this is what covers it.
      const at = consumeLoose(res.chosen.text, prefix)
      return { suffix: res.chosen.text.slice(at), term: res.chosen }
    }

    // several: complete as far as they agree
    const shared = commonPrefix(matches.map((t) => t.text))
    const at = consumeLoose(matches[0].text, prefix)
    if (at > 0 && shared.length > at) {
      return { suffix: shared.slice(at), term: matches[0] }
    }
    // ⚠️ AMBIGUOUS AT THIS LENGTH MEANS AMBIGUOUS, FULL STOP — it does not fall
    // through to a SHORTER prefix. "st m" matching two records must not then offer
    // whatever "m" alone reaches; the director typed the longer thing.
    return null
  }
  return null
}

/** Case-insensitive common prefix, returned in the FIRST term's own capitalisation. */
function commonPrefix(values: readonly string[]): string {
  if (values.length === 0) return ""
  let len = values[0].length
  for (const v of values.slice(1)) {
    let i = 0
    while (i < len && i < v.length && values[0][i].toLowerCase() === v[i].toLowerCase()) i++
    len = i
  }
  return values[0].slice(0, len)
}

/** What Tab inserts: the completion plus a space, so the next word can start. */
export function acceptGhost(text: string, ghost: Ghost): string {
  return text + ghost.suffix + " "
}
