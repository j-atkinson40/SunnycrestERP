/**
 * Which recognized words have been TYPED PAST, and may therefore leave the bar.
 *
 * Slice 2, clause 1 (James, 2026-10-28): *"words leave the bar when typed past and fly
 * into their field"*.
 *
 * ⚠️ THE RULE IS THE PROTOTYPE'S `settled()`, TRANSLATED FROM ITS TOKEN MATCHER TO OUR
 * SERVER SPANS. `docs/prototypes/2026-10-27-guided-order-capture.html`:
 *
 *     function settled(T,i,c,text){
 *       if(c.e>=text.length)return false;
 *       if(c.waitable===false)return true;
 *       const phrase=…, nx=T[i+c.len];
 *       if(!nx){ if(c.bareNum)return false;
 *                return !LEX.some(l=>l.key.startsWith(phrase+' ')) }
 *       if(i+c.len===T.length-1&&!/\s$/.test(text)){
 *                if(c.bareNum&&/^(a|am|p|pm)$/.test(nx.n))return false;
 *                return !LEX.some(l=>l.key.startsWith(phrase+' '+nx.n)) }
 *       return true;
 *     }
 *
 * Three gates, and each has its own reason:
 *
 *   1. **the word is still at the caret** → wait. This is the whole of "typed past":
 *      nothing leaves while the director's cursor is still on it.
 *   2. **a LONGER term may still be coming** → wait. `"st marys "` must not fly while
 *      `St. Mary's Cemetery` is a term that starts with it. The design review of
 *      2026-10-28 named this a *"new vocabulary lookahead"*, and it is buildable here
 *      because the bar already holds the vocabulary for the ghost.
 *   3. **a bare number may still become a time** → wait.
 *
 * ⚠️ GATE 3 IS INERT IN OUR EXTRACTOR AND IS NOT IMPLEMENTED, measured rather than
 * assumed. The prototype's matcher captures a bare `10` and has to wait in case `am`
 * follows; ours does not capture it at all — measured 2026-11-03,
 * `"order for johnson 10"` yields `('unrecognized', (), 18, 20, '10')` while
 * `"…10am"` yields `('captured', ('service_time',), 18, 22)`. A word that is never a
 * `captured` span can never fly away early, so the gate has nothing to guard.
 * `test_a_bare_number_is_never_capturable` pins that, so the day a bare number becomes
 * capturable this rule is revisited rather than silently wrong.
 *
 * ⚠️ AND THE START RECT CANNOT COME FROM THE SERVER, which is why this module returns
 * OFFSETS and not geometry. `spans_for_text` describes the text the server was handed,
 * and clause 1 removes the word from that text in the same gesture — so the rect has to
 * be measured client-side off the mirror BEFORE the removal. The design review found
 * this before anything was built; the split here is that finding made structural.
 */
import type { CaptureSpan, VocabTerm } from "@/services/opas-capture-service"

/** A word that may leave, with everything the caller needs to fly it and record it. */
export interface Leaving {
  readonly fieldId: string
  /** The word as it stands in the bar — what the chip shows. */
  readonly text: string
  readonly start: number
  readonly end: number
}

function norm(s: string): string {
  return s.toLowerCase().replace(/\s+/g, " ").trim()
}

/**
 * Is some vocabulary term a LONGER phrase beginning with `prefix`?
 *
 * ⚠️ WORD-WISE AND PUNCTUATION-INSENSITIVE, WHICH THE DESIGN REVIEW FOUND THE HARD WAY.
 * The office types `st marys`; the term is `St. Mary's Cemetery`; and
 * `"st. mary's cemetery".startsWith("st marys")` is **false** — the period and the
 * apostrophe are both in the way. Comparing the WORDS, stripped of punctuation, is what
 * makes the lookahead fire on the very case it exists for.
 */
export function aLongerTermStartsWith(
  prefix: string,
  vocab: readonly VocabTerm[],
): boolean {
  const want = words(prefix)
  if (want.length === 0) return false
  return vocab.some((t) => {
    const have = words(t.text)
    // ⚠️ "LONGER" IS NOT "MORE WORDS", AND MY SECOND VERSION GOT THAT WRONG TOO. This
    // read `if (have.length <= want.length) return false`, which rejected
    // `"st marys ce"` against `St. Mary's Cemetery` — both are three words, and the
    // term is longer by CHARACTERS in its last one. So the word flew away mid-
    // "cemetery", which is the very case gate 2 exists for.
    //
    // Longer therefore means: more words, OR the same words with a strictly longer
    // last one. The equal case must be excluded or a complete term would wait for
    // itself forever — `test_the_lookahead_needs_a_LONGER_term` pins that end.
    if (have.length < want.length) return false
    // ⚠️ EVERY WORD BUT THE LAST MATCHES EXACTLY; THE LAST MATCHES AS A PREFIX — and
    // getting that wrong is what my first version did. A whole-word comparison said
    // `"st marys ce"` could not continue `St. Mary's Cemetery`, because `"ce" !==
    // "cemetery"`, so the word flew away while the director was mid-"cemetery". The
    // prototype's character-wise `key.startsWith(phrase+' '+nx.n)` gets this for free;
    // word-wise comparison has to say it.
    //
    // ⚠️ AND IT IS STILL WORD-WISE FOR THE REST, which is the half character-wise
    // cannot do: the office types `st marys` and the term is `St. Mary's Cemetery`, so
    // `"st. mary's cemetery".startsWith("st marys")` is FALSE in plain JS. Both halves
    // are needed, and each covers the other's blind spot.
    const last = want.length - 1
    for (let i = 0; i < last; i++) {
      if (have[i] !== want[i]) return false
    }
    const tailWord = have[last]
    if (tailWord === undefined) return false
    if (!tailWord.startsWith(want[last])) return false
    return have.length > want.length || tailWord.length > want[last].length
  })
}

function words(s: string): readonly string[] {
  return norm(s)
    .split(" ")
    .map((w) => w.replace(/[.,;:!?'"()‘’“”]/g, ""))
    .filter(Boolean)
}

/**
 * The captured words in `text` that have been typed past.
 *
 * ⚠️ `captured` SPANS ONLY. An `unrecognized` word stays in the bar until Tab — that is
 * the prototype's own division of labour, stated in its header: *"Words Opas
 * understands fly into the order … anything Opas can't place waits under the order."*
 * Flying away words nobody placed would empty the bar of exactly the text the director
 * still needs to fix.
 *
 * ⚠️ AND A SPAN CARRYING TWO FIELDS IS REFUSED, which is a deliberate omission rather
 * than an oversight. `"1948 to 2026"` is one span for `date_of_birth` AND
 * `date_of_death`; one word cannot fly to two rows, and picking one would record half
 * a claim. It stays in the bar, where it is already captured and already visible.
 */
export function wordsReadyToLeave(
  text: string,
  spans: readonly CaptureSpan[] | undefined,
  spansForText: string | null | undefined,
  vocab: readonly VocabTerm[],
): readonly Leaving[] {
  // ⚠️ STALE SPANS LEAVE NOTHING, the same rule `mirrorPieces` applies to the tint and
  // for a stronger reason: a span computed for `"order for hop"` says nothing about
  // `"order for hopkins"`, and acting on it would cut the wrong characters out of the
  // bar. The mirror merely paints the wrong word; this would destroy text.
  if (!text || !spans || spans.length === 0) return []
  if (spansForText !== text) return []

  const out: Leaving[] = []
  for (const sp of spans) {
    if (sp.state !== "captured") continue
    if (sp.field_ids.length !== 1) continue
    if (sp.start < 0 || sp.end > text.length || sp.end <= sp.start) continue

    // gate 1 — still at the caret
    if (sp.end >= text.length) continue

    const phrase = text.slice(sp.start, sp.end)
    const tail = text.slice(sp.end)
    const nextTokens = tail.trim().split(/\s+/).filter(Boolean)

    if (nextTokens.length === 0) {
      // only whitespace follows: a longer term may still be coming
      if (aLongerTermStartsWith(phrase, vocab)) continue
    } else if (nextTokens.length === 1 && !/\s$/.test(text)) {
      // the next token is the last and still being typed
      if (aLongerTermStartsWith(`${phrase} ${nextTokens[0]}`, vocab)) continue
    }

    out.push({
      fieldId: sp.field_ids[0],
      text: phrase,
      start: sp.start,
      end: sp.end,
    })
  }
  return out
}

/**
 * The text with `[start,end)` cut out, and the join tidied.
 *
 * ⚠️ THE SURROUNDING WHITESPACE COLLAPSES, AND NOT COLLAPSING IT IS A MEASURED DEFECT.
 * James's own session carried `full_text = 'riverside full equipment  chairs'` — a
 * DOUBLE SPACE where a removed word had been — which is what made the digit-swallowing
 * bug visible in the first place. Cutting `"a hopkins b"` at the middle word must give
 * `"a b"`, not `"a  b"`.
 *
 * ⚠️ AND A LEADING CUT LEAVES NO LEADING SPACE. `" chairs"` was the other half of that
 * same session; removing the first word must not leave the bar starting with a gap,
 * because the next thing typed would then be the second word of a sentence.
 */
export function textWithout(text: string, start: number, end: number): string {
  const before = text.slice(0, start)
  const after = text.slice(end)
  if (before === "") return after.replace(/^\s+/, "")
  if (after.trim() === "") return before.replace(/\s+$/, "")
  return `${before.replace(/\s+$/, "")} ${after.replace(/^\s+/, "")}`
}
