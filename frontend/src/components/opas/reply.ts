/**
 * What Opas says, and the choices it offers. ONE voice, in ONE place.
 *
 * ⚠️ JAMES'S RULING, 2026-10-20: "One Opas voice, just above the bar. The question line
 * from order capture becomes the place Opas answers everything... It's one voice, in one
 * place." And: "Nothing Opas says appears as a toast or a floating pane anymore."
 *
 * ⚠️ MEASURED FROM `docs/prototypes/2026-10-01-opas-overlay.html` (93177 bytes, md5
 * a52a1e95153bd5c686b88d0acffc31e6). The prototype already had this and it is quoted
 * rather than reinvented:
 *
 *     .said{position:fixed;z-index:44;right:24px;width:min(600px,calc(100vw - 48px));
 *           display:flex;flex-direction:column;align-items:flex-end;gap:6px;…}
 *     function placeSaid(){const r=line.getBoundingClientRect();
 *                          said.style.bottom=(innerHeight-r.top+10)+'px'}
 *     function show(chips){ … if(pending){ … p.className='pick';
 *         pending.opts.forEach((o,i)=>{ … b.innerHTML=`<kbd>${i+1}</kbd>${o.name}
 *                                        <span>· ${o.city}</span>`; …}) …}
 *       said.classList.add('on');
 *       if(!pending)saidTimer=setTimeout(()=>said.classList.remove('on'),4200)}
 *     function choose(i){ … pending=null; … p.then(o); show([{t:o.name}]); input.focus()}
 *
 * Three things come straight out of that and are not choices made here: the container
 * sits **10px above the bar's top edge**, the options render **below** the sentence in the
 * same stack, and **a reply with options does NOT fade** while one without fades after
 * **4200ms**. `choose` ending in `input.focus()` is dispatch item 1, already in the
 * prototype.
 */

/** What kind of thing Opas is saying. It decides whether the line fades. */
export type ReplyKind =
  /** Opas needs an answer. Never fades — the director is mid-answer. */
  | "question"
  /** Opas found nothing. Fades; the phrase is still in the bar to correct. */
  | "miss"
  /** Opas did something. Fades. */
  | "ack"

/** One choice, as a row in the list above the bar. */
export interface ReplyOption {
  /** Stable within one reply. What the host maps back to an action. */
  readonly id: string
  /** The primary text — a decedent's name, a product name. */
  readonly label: string
  /** What tells this one apart: a service day, a status, a size. */
  readonly detail?: string
}

export interface Reply {
  readonly kind: ReplyKind
  readonly text: string
  /** Present only on a `question` that can be answered by picking. */
  readonly options?: readonly ReplyOption[]
}

/** The prototype's own `saidTimer` delay. */
export const REPLY_FADE_MS = 4200

/** The prototype's `placeSaid`: 10px above the bar's top edge. */
export const REPLY_GAP_ABOVE_BAR = 10

/**
 * Words dropped before matching typed text against the options.
 *
 * ⚠️ A VOCABULARY, SO IT PROTECTS WHAT IT LISTS AND NOTHING ELSE — the same caveat
 * `pick-digit.NUMBER_LABELS` carries. Every entry is a word that appears in the dispatch's
 * own examples of how a person answers ("the Friday one", "the confirmed one") or is a
 * word the bar's other rules already treat as noise. It is short on purpose.
 *
 * ⚠️ AND IT IS DELIBERATELY NOT WIDENED WITH PREPOSITIONS, which was the obvious
 * improvement and is the wrong direction. Dropping "in" would make "the smith one on
 * friday" answerable — a real nuisance — at the price of making "orders in october",
 * which is a LIST question, reduce to `["october"]`, hit both options, and be eaten as
 * an answer. Measured: with "in" absent that phrase is `none`; with "in" present it is
 * `many`.
 *
 * The asymmetry decides it. A question mis-read as a request costs a retype. A request
 * mis-read as an answer opens the wrong order, silently, and the director finds out
 * later. So the rule stays strict and "the smith one on friday" is a new request.
 */
export const FILLER: readonly string[] = [
  "the", "a", "an", "one", "ones", "that", "this", "it", "its",
  "order", "orders", "please", "is", "was", "for", "of", "to",
]

/** The shortest token that may match by prefix in either direction. */
export const MIN_PREFIX = 3

/**
 * Lower-case, drop apostrophes, turn every other non-alphanumeric run into one space.
 *
 * ⚠️ APOSTROPHES ARE DROPPED, NOT REPLACED WITH A SPACE, AND A TEST CAUGHT THE
 * DIFFERENCE. Written as one `[^a-z0-9]+ -> " "` pass, `"when's the service"` becomes
 * `"when s the service"` — four tokens, no table key, and `contextIntent` returned null
 * for the dispatch's own example phrase. The same would hit `"St. Mary's"` and
 * `"who's it for"`. Both the straight and the curly apostrophe are dropped, because a
 * browser's smart quotes produce the curly one.
 */
export function normalizeAnswer(text: string): string {
  return text
    .toLowerCase()
    .replace(/['\u2019]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ")
}

/** The words a typed answer offers, filler removed. */
export function answerTokens(text: string): string[] {
  const filler = new Set(FILLER)
  return normalizeAnswer(text).split(" ").filter((t) => t !== "" && !filler.has(t))
}

/** The words an option can be matched on. */
export function optionWords(option: ReplyOption): string[] {
  return normalizeAnswer(`${option.label} ${option.detail ?? ""}`)
    .split(" ")
    .filter((w) => w !== "")
}

/**
 * Does one typed token pick out this word?
 *
 * ⚠️ WORD-PREFIX IN EITHER DIRECTION, NOT SUBSTRING, and the direction matters in both.
 * `"fri"` must reach `"Friday"` (the option is abbreviated, the typist is not) and
 * `"friday"` must reach `"Fri"` (the reverse, which is what the detail line actually
 * says). A substring rule would let `"id"` match `"Friday"`, which is not an answer to
 * anything.
 *
 * ⚠️ AND THE SHORTER SIDE MUST BE AT LEAST `MIN_PREFIX`, which is what stops the loose
 * direction from being a wildcard: without it an option containing the word `"a"` would
 * be matched by every token beginning with `a`.
 */
export function tokenHitsWord(token: string, word: string): boolean {
  if (token === word) return true
  const shorter = Math.min(token.length, word.length)
  if (shorter < MIN_PREFIX) return false
  return word.startsWith(token) || token.startsWith(word)
}

export function optionMatches(option: ReplyOption, tokens: readonly string[]): boolean {
  if (tokens.length === 0) return false
  const words = optionWords(option)
  // ⚠️ EVERY TOKEN MUST LAND, not any. "the friday one" with two options both on a Friday
  // narrows to neither if only one token had to hit — and "smith friday" is a person
  // asking for the intersection, not the union.
  return tokens.every((t) => words.some((w) => tokenHitsWord(t, w)))
}

export type AnswerMatch =
  /** Exactly one option. `index` is 0-based. */
  | { readonly kind: "one"; readonly index: number }
  /** Still ambiguous. The list narrows to these and the question stays. */
  | { readonly kind: "many"; readonly indices: readonly number[] }
  /** Nothing matched. The caller treats the text as a new request. */
  | { readonly kind: "none" }

/**
 * Which option the typed words name.
 *
 * ⚠️ IT NEVER GUESSES. One match is an answer; several narrow the list and keep the
 * question; none is a new request. That is the dispatch verbatim: "One match -> chosen.
 * Still ambiguous -> the list narrows and the question stays. ... when the typed text
 * matches no option and is a new request (handle it as one)."
 */
export function matchAnswer(
  options: readonly ReplyOption[],
  typed: string,
): AnswerMatch {
  const tokens = answerTokens(typed)
  if (tokens.length === 0) return { kind: "none" }
  const hits: number[] = []
  options.forEach((option, i) => {
    if (optionMatches(option, tokens)) hits.push(i)
  })
  if (hits.length === 1) return { kind: "one", index: hits[0] }
  if (hits.length > 1) return { kind: "many", indices: hits }
  return { kind: "none" }
}
