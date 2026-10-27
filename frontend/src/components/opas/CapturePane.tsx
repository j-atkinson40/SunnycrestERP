/**
 * The typed order-capture pane.
 *
 * ⚠️ EVERY STRUCTURAL CHOICE IS QUOTED FROM `docs/prototypes/2026-10-01-opas-overlay.html`
 * (md5 `a52a1e95153bd5c686b88d0acffc31e6`) rather than designed here:
 *
 *   `:413`  header = title + `<b>N</b> captured` + `<b>N</b> needed`, the needed pill
 *           taking its emphasis class only once the director has signalled done
 *   `:414`  a column header row: the capture label on the left, `AI ASSIST` on the right
 *   `:410`  one row per field: a mark, a label, a value
 *   `:409`  value text per state — the value, "Still needed", "Not mentioned yet"
 *   `:416`  footer = a `Review` button, disabled while anything is needed, + Cancel
 *   `:389`  the review stage replaces the rows with a summary grid
 *   `:431`  a capture pane is `wide`
 *
 * ⚠️ THE FOURTH ROW STATE COMES FROM THE OTHER PROTOTYPE, and the Opas overlay is SILENT
 * on it — measured: zero occurrences of `unconfig` there. `not_configured` is
 * `docs/prototypes/2026-09-22-capture-schema-prototype.html` (md5
 * `5d286c79a855f7397a8d62f3ad983228`), `.cap.unconfig`: amber at lower intensity with a
 * DASHED mark border. Two sources, each cited, neither inferred from the other.
 *
 * ⚠️ THE SERVER OWNS THE STATE. This component holds a `CaptureState` and renders it. It
 * does not compute which fields are missing, does not resolve anything, and does not
 * choose between candidates — those are the engine's and the resolvers' jobs, and a
 * second implementation here would be the duplication the capture engine removed.
 *
 * ⚠️ IT HAS NO TEXT FIELD, BY RULING (2026-10-12). THE BAR IS THE ONLY INPUT. The pane
 * receives `text` as a prop and never owns it — see `opas-context.tsx::entryText`. The
 * prototype's pane had its own box and the pane-plus-bar arrangement had TWO places to
 * type, which is the thing the ruling removed: a director with a half-typed line in one
 * of them and the cursor in the other.
 *
 * ⚠️ IT EXTRACTS ON A PAUSE, NOT ON A SUBMIT. `EXTRACT_DEBOUNCE_MS` after the last
 * keystroke the whole text is re-read, so the rows fill in while someone types. Two
 * consequences worth stating because they look like bugs otherwise:
 *
 *   deleting a word UN-CAPTURES what it said — the text is the source, the server
 *   rebuilds from scratch, and that is the behaviour an editable bar has to have.
 *
 *   responses can arrive out of order, and the stale ones are DROPPED HERE. See
 *   `capture-sequence.ts` for why the client decides and not the server.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import {
  answerCapture,
  completeCapture,
  approveCapture,
  choosePick,
  readCapture,
  setCaptureText,
  startCapture,
  takeSwitch,
  type CapturePick,
  type CaptureState,
} from "@/services/opas-capture-service"
import type { CaptureSpan } from "@/services/opas-capture-service"
import type { GuidedPill } from "./GuidedQuestion"
import { EXTRACT_DEBOUNCE_MS, createSequencer } from "./capture-sequence"

/** What the pane tells the command line about itself.
 *
 * ⚠️ IT TRAVELS UPWARD BECAUSE THE INPUT IS UP THERE. The bar needs the placeholder
 * (which must describe what is happening NOW), the pending picks (so ⌘1..9 can settle
 * one), and whether the session is still capturing (so Enter can be a no-op). All
 * three are facts about the pane; the bar is where they are used.
 */
export interface EntryPaneStatus {
  /** What OPAS SAYS about this order — the next question, or what is still needed.
   *
   *  ⚠️ IT WAS `placeholder: string` UNTIL 2026-10-20, AND THAT NAME WAS THE BUG. The
   *  bar renders this string as the textarea's `placeholder`, which a browser shows
   *  ONLY WHEN THE FIELD IS EMPTY — and `placeholderFor` returned the question only
   *  when the text was NON-empty. The two conditions are mutually exclusive, so the
   *  server's `next_question` and every "Still need: …" variant were computed for
   *  exactly the state in which they could not be seen. Measured 2026-10-20: four of
   *  the nine strings that function could return were unreachable on screen, including
   *  the one the 2026-10-15 ruling was written for.
   *
   *  ⚠️ DERIVED ON EVERY RENDER, NEVER LATCHED — see `captureVoice`. */
  readonly question: string
  readonly picks: readonly CapturePick[]
  readonly capturing: boolean
  readonly ready: boolean
  /** ⚠️ THE SPANS TRAVEL PANE -> BAR because the pane owns the server state and the
   *  bar owns the mirror. Sending them up the existing status channel avoids a
   *  second place that knows how to fetch capture state. */
  readonly spans?: readonly CaptureSpan[]
  readonly spansForText?: string | null
  /** Fields whose span should light up — the row the pointer is over. */
  readonly hoveredFieldIds?: readonly string[]
  /** ── guided capture, slice 1 ──────────────────────────────────────────────────
   *
   *  ⚠️ THESE TRAVEL UPWARD FOR THE SAME REASON THE SPANS DO: the pane owns the server
   *  state and the surface that renders them sits beside the BAR, not inside the pane.
   *  Fetching capture state in a second place to get them would be a second thing that
   *  can disagree about what Opas is asking.
   *
   *  ⚠️ AND THEY ARE THE SERVER'S WORDS, UNTOUCHED. `question` above is composed by
   *  `captureVoice` — a client-side sentence for the bar — and these are not. The
   *  dispatch is explicit: "THE NEXT QUESTION comes from the engine (server-side, the
   *  capture schema), not the client." */
  readonly guidedQuestion?: string | null
  readonly guidedHint?: string | null
  readonly guidedFieldId?: string | null
  readonly guidedPills?: readonly GuidedPill[]
  readonly cremation?: string | null
  /** Why something was just cleared. ⚠️ TRANSIENT — set by the answer that caused it
   *  and dropped by the next one, because it answers "what just happened". */
  readonly clearedNote?: string | null
  readonly sessionId?: string | null
  /** Which fields the server considers answered.
   *
   *  ⚠️ IT TRAVELS UP SO THE HOST CAN RETIRE A CLICKED ROW. "Clicking a row asks that
   *  question again" needs an end condition, and the prototype's is "while it is still
   *  unanswered" (`S.focus&&…&&!S.f[S.focus]`). The host holds the click; only the
   *  server knows when it was answered. */
  readonly answeredFieldIds?: readonly string[]
}

/** The placeholder, derived from what is true right now.
 *
 * ⚠️ THE RULING IS "SAYS WHAT IT IS DOING, NEVER STALE", AND THAT RULES OUT THE OBVIOUS
 * IMPLEMENTATION. A message set on an event — `setPlaceholder("Reading…")` when a
 * request starts — survives whatever happens next, including the request failing, the
 * pane being tucked, or the director deleting everything. This is a pure function of
 * the current state, so there is no stored message that can outlive its cause.
 *
 * ⚠️ ORDER IS BY URGENCY, AND THE PICK COMES FIRST. A pending pick is the one thing
 * that needs the director's hand; reporting "reading…" over the top of it would hide a
 * question behind a progress note.
 */
/** The bar's own prompt in entry mode — a plain one, by ruling.
 *
 * ⚠️ JAMES, 2026-10-20: "capture's question moves into the reply line above the bar and
 * stays visible while typing; the placeholder goes back to a plain prompt. One voice
 * everywhere. Supersedes the 2026-10-15 placeholder ruling."
 *
 * ⚠️ IT IS THE SAME STRING THE BAR ALREADY SHOWED. Of everything `placeholderFor` could
 * return, this is the one a director with an empty bar actually saw, so the bar looks
 * unchanged while empty and the question now appears above it and stays.
 */
export const ENTRY_PLACEHOLDER = "Say what the director said"

export function captureVoice(args: {
  readonly ready: boolean
  readonly inFlight: boolean
  readonly text: string
  readonly picks: readonly CapturePick[]
  /** ⚠️ THE SIZE OF THE SERVER'S `missing` SET — NOT A COUNT OF ROWS IN THE
   *  `needed` STATE, WHICH IS WHAT THIS USED TO READ. A row only reaches `needed`
   *  AFTER a done signal; before that a required-and-unanswered row renders as
   *  `not_mentioned`. So the bar said "Nothing needed — say "that's it"" while eight
   *  required fields were unanswered. Measured in a real browser on the walk phrase:
   *  one funeral home captured, and the bar inviting the director to finish.
   *
   *  ⚠️ `missing` IS ALSO THE SET `is_complete` IS COMPUTED FROM, so the bar and the
   *  engine now answer "is this order finishable" from the same place. */
  readonly missing: number
  /** The missing fields in the office's words.
   *
   *  ⚠️ IT NAMES THEM RATHER THAN COUNTING THEM, BY RULING (2026-10-14): the bar
   *  says what is missing. "2 needed" is what sent James looking for which two.
   *
   *  ⚠️ AND IT REMOVES A SECOND NUMBER THAT COULD DISAGREE WITH THE PILL. The pill
   *  counts ROWS (two missing fields can share one), so a bar counting FIELDS would
   *  print a different number for the same order — which is the defect
   *  `THE HEADER CHIP AND THE BAR AGREE` was written to catch. One names, one
   *  counts, and there is nothing left to contradict. */
  readonly missingLabels?: readonly string[]
  /** The server's single next question. See `next_question` in schema.py. */
  readonly nextQuestion?: string | null
  readonly reviewing: boolean
}): string {
  if (!args.ready) return "Starting the order…"
  if (args.picks.length > 0) {
    // ⚠️ ⌥ AND NOT ⌘, BY RULING (James, 2026-10-27): "Chrome keeps ⌘1–8 for switching
    // tabs, so ⌘ would only ever work in a desktop app. ⌥ works in every browser."
    // This sentence advertised a chord the browser eats, in the one place a director
    // would read to learn it.
    //
    // ⚠️ AND IT IS THE FLOOR, NOT THE AFFORDANCE. The options themselves are now pills
    // above the bar, each carrying its own ⌥-number — this line is what the bar says
    // when the guided surface is not up, which is why it still names the keys at all.
    const n = args.picks[0].options.length
    return `Which one? 1–${Math.min(n, 9)}, or ⌥ and the number`
  }
  if (args.reviewing) return "Ready to review"
  if (args.inFlight) return "Reading what you typed…"
  // ⚠️ THE `text.trim() === ""` BRANCH IS GONE, and it is why the question was invisible.
  // It read:
  //
  //     if (args.text.trim() === "") return "Say what the director said"
  //
  // That is a PROMPT, not something Opas says, and it stood in front of every line
  // below it for the only state in which this string was rendered. The prompt is now
  // `ENTRY_PLACEHOLDER` on the bar itself and this function answers one question: what
  // does Opas say about this order right now. With an empty bar that is still the next
  // question, which is what "stays visible while typing" needs at both ends.
  // ⚠️ ONE QUESTION, FROM THE SERVER, REPLACING "Still need: a, b, c" (James,
  // 2026-10-15). Three gaps named at once is a report; the bar is a conversation and
  // asks for the next thing. The wording and the ORDER are the server's — see
  // `CALL_ORDER` in schema.py — because the bar and the pane must not disagree about
  // what is outstanding, and a hand-written order in the frontend is exactly how
  // they would.
  //
  // ⚠️ IT FALLS BACK TO THE OLD SENTENCE WHEN THE SERVER DID NOT SEND ONE. An older
  // server has no `next_question`, and the same blank-pane defect of 2026-10-12 came
  // from reading a key an older server omits.
  if (args.nextQuestion) return args.nextQuestion
  if (args.missing > 0) {
    const named = (args.missingLabels ?? []).join(", ").toLowerCase()
    if (named) return `Still need: ${named}`
    return `${args.missing} still needed — keep typing`
  }
  return "Nothing needed — say “that’s it”"
}

/** ⚠️ Per-state classes, named after the prototype's own selectors so a reader can find
 *  them in the source file. */
/** ⚠️ THE CARET'S ROW, lit from the bar. Deliberately the same blue as the span's
 *  lit state in the mirror so the two ends of the link read as one thing. */
/** The prototype's `.row.current` — a steel outline and a 3px halo.
 *
 * ⚠️ IT OUTLINES RATHER THAN FILLS, which is the prototype's choice and the right one:
 * the asked row is the one thing on the pane that is about to change, and a fill would
 * read as a value already there. */
const ROW_ASKING_CLASS =
  "border-[rgba(143,176,207,0.5)] bg-[rgba(255,255,255,0.025)] " +
  "shadow-[0_0_0_3px_rgba(143,176,207,0.16)]"

/** `.row.current .mk{border-color:var(--steel)}` — the ring, not yet ticked. */
const MARK_ASKING_CLASS = "border-[rgb(143,176,207)] text-transparent"

/** What the "N to go" pill lights while it is hovered — the rows it counts. */
const ROW_LIT_CLASS = "border-[rgba(227,171,79,0.45)]"

/** ⚠️ THE PROTOTYPE'S OWN WORDS for the asked row's empty value: `Opas is asking`.
 *  The old pane read "Not mentioned yet" on every empty row, which James named: a row
 *  Opas is asking about right now has not been "not mentioned" — it is the question. */
const ASKING_TEXT = "Opas is asking"

/** The prototype's footer fallback: `'Click any line to change it.'`
 *
 * ⚠️ IT IS THE ONLY PLACE THAT SAYS THE ROWS ARE CLICKABLE. The rows became buttons by
 * ruling ("clicking a row asks that question again") and a button that looks like a
 * line needs one sentence somewhere saying so. */
const FOOTER_HINT = "Click any line to change it."

const ROW_CARET_CLASS =
  "outline outline-1 outline-[rgba(138,164,189,0.55)] bg-[rgba(138,164,189,0.07)]"

const ROW_CLASS: Record<string, string> = {
  done: "border-[rgba(74,160,110,0.35)] bg-[rgba(74,160,110,0.05)]",
  needed: "border-[rgba(224,168,74,0.55)] bg-[rgba(224,168,74,0.08)]",
  not_mentioned: "border-border-subtle bg-transparent",
  // `.cap.unconfig` — amber at LOWER intensity than `needed`, and the mark is dashed.
  not_configured: "border-[rgba(224,168,74,0.35)] bg-[rgba(224,168,74,0.04)]",
  // ⚠️ `partial` IS NOT IN EITHER PROTOTYPE, because neither had the case. The server
  // added the state 2026-10-12 for a row that has captured something and is not
  // finished — the defect James saw, where "Church" rendered in the not-mentioned
  // style. Styled between `not_mentioned` and `done`: the green hue of progress at
  // the lower intensity `unconfig` uses for "incomplete", so a part-filled row reads
  // as started without claiming to be answered.
  partial: "border-[rgba(74,160,110,0.30)] bg-[rgba(74,160,110,0.03)]",
}

const MARK_CLASS: Record<string, string> = {
  done: "border-[rgb(74,160,110)] text-[rgb(74,160,110)]",
  needed: "border-[rgb(224,168,74)] text-[rgb(224,168,74)]",
  not_mentioned: "border-border-base text-content-subtle",
  not_configured: "border-[rgb(224,168,74)] border-dashed text-[rgb(224,168,74)]",
  // ⚠️ NO CHECK, AND THAT IS THE POINT. A partial row is started, not answered; the
  // mark carries the progress hue but stays an empty circle, so `done` remains the
  // only state that shows a tick.
  partial: "border-[rgb(74,160,110)] text-[rgb(74,160,110)]",
}

/** The value text per state.
 *
 * ⚠️ A VALUE WINS OVER THE STATE WORDING, AND THIS DEVIATES FROM THE PROTOTYPE ON PURPOSE.
 * The prototype shows the value only when `done` (`:409`) — correct there, because its
 * rows are ONE FIELD each, so a row is either answered or it is not.
 *
 * Our rows COMPOSE several fields (`surfaces.py`): the Service row joins location, date
 * and time. Measured on dev: after typing a service date and time but no location, the
 * server returned that row with `state: "not_mentioned"` AND
 * `value: "2027-03-02 · 10:00"`. Following the prototype literally would print "Not
 * mentioned yet" over a value the director had just given, and they would retype it.
 *
 * So the wording is the FALLBACK, used when there is nothing to show. The state still
 * drives the colour and the mark, which is what says the row is not finished.
 */
function valueText(state: string, value: string | null): string {
  if (value) return value
  if (state === "needed") return "Still needed"
  if (state === "not_configured") return "Not configured for this licensee"
  return "Not mentioned yet"
}

/** The two columns of the capture grid, by James's direction (2026-10-13).
 *
 * ⚠️ THE PROTOTYPE HAS NO TWO-COLUMN GROUPING TO QUOTE, and I checked before
 * inventing one. Measured in `docs/prototypes/2026-10-01-opas-overlay.html` (md5
 * `a52a1e95153bd5c686b88d0acffc31e6`): the capture rows are
 * `.caps{display:flex;flex-direction:column;gap:7px}` — a SINGLE column — inside
 * `.win.wide{width:min(440px,calc(100vw - 32px))}`. So the grid is a departure from
 * the prototype rather than an implementation of it, and the order below is the
 * ruled order, not a derived one.
 *
 * ⚠️ TEN ROWS IN TWO COLUMNS IS WHAT REMOVES THE SCROLLBAR, which is why the grid
 * and the no-scrolling rule are one change and not two. One column of ten rows does
 * not fit above the bar at 800px tall; two columns of five do.
 *
 * ⚠️ EVERY ROW ID BELONGS TO EXACTLY ONE COLUMN, ratcheted in
 * `capture-columns.test.ts`. A row the server adds and this map does not name would
 * be captured and silently not rendered — the same class as the three template
 * fields that had no row at all.
 */
export const LEFT_COLUMN: readonly string[] = [
  "funeral_home",
  "deceased_name",
  "dates",
  "burial",
  "service",
]

export const RIGHT_COLUMN: readonly string[] = [
  "vault",
  "personalization",
  "cemetery",
  "cemetery_equipment",
  "contact",
]

/** Rows in column order, then anything the columns do not name.
 *
 * ⚠️ THE UNNAMED TAIL IS RENDERED, NOT DROPPED. A new row must be visible even
 * before someone places it, because invisible-and-captured is the failure this
 * whole arc keeps finding. The ratchet makes the tail empty; this makes a non-empty
 * tail harmless rather than silent.
 */
export function splitIntoColumns<T extends { readonly row_id: string }>(
  rows: readonly T[],
): { left: T[]; right: T[] } {
  const by = new Map(rows.map((r) => [r.row_id, r]))
  const left = LEFT_COLUMN.map((id) => by.get(id)).filter((r): r is T => !!r)
  const right = RIGHT_COLUMN.map((id) => by.get(id)).filter((r): r is T => !!r)
  const named = new Set([...LEFT_COLUMN, ...RIGHT_COLUMN])
  const tail = rows.filter((r) => !named.has(r.row_id))
  // alternate the tail so an unplaced row cannot make one column run long
  tail.forEach((r, i) => (i % 2 === 0 ? left : right).push(r))
  return { left, right }
}

/** A decimal string as the office writes money.
 *
 * ⚠️ IT FORMATS A STRING AND NEVER DOES ARITHMETIC ON IT. The server sends decimal
 * strings because money in a float loses cents; parsing to a number here to add
 * things up would put the loss back. Every total on screen was summed by Postgres.
 *
 * ⚠️ A VALUE IT CANNOT PARSE IS SHOWN AS GIVEN, not as "$NaN". If the server ever
 * sends something unexpected the office should see the oddity, not a broken number.
 */
export function money(value: string): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return value
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  })
}

export function CapturePane({
  openingLine,
  prefill,
  onSessionStarted,
  text = "",
  onStatus,
  pickRequest,
  answerRequest,
  askedFieldId = null,
  onAskAgain,
  focusRequest,
  onApproved,
  onAskWhy,
  completeRequest,
  caretFieldIds,
}: {
  /** Fed through extraction on start, per the prototype (`:568` calls `feed` at once). */
  readonly openingLine?: string
  /** What a pane chose. Survives re-extraction; yields to a different name in the text. */
  readonly prefill?: Readonly<Record<string, string>>
  readonly onSessionStarted?: (id: string) => void
  /** ⚠️ WHAT IS IN THE BAR. The pane does not own this and has no field of its own —
   *  the bar is the only input, by ruling. */
  readonly text?: string
  /** Reports the placeholder, the picks and the capturing flag up to the bar. */
  readonly onStatus?: (s: EntryPaneStatus) => void
  /** ⚠️ WHICH FIELDS THE CARET IS INSIDE, from the bar. The link runs caret -> row
   *  rather than hover -> row because the textarea owns the pointer over its own
   *  text (James, 2026-10-16). */
  readonly caretFieldIds?: readonly string[]
  /** Which field Opas is asking about, so the pane can outline that row.
   *
   *  ⚠️ IT COMES DOWN FROM THE HOST RATHER THAN BEING READ OFF `state` HERE, because
   *  the host already holds it for the question above the bar. Two reads of the same
   *  server field would not disagree today and would the moment one of them gained a
   *  fallback. */
  readonly askedFieldId?: string | null
  /** Ask a question again, because the office clicked its row.
   *
   *  ⚠️ IT GOES UP TO THE HOST, NOT STRAIGHT TO THE SERVER. "Clicking a row asks that
   *  question again" is a change to what Opas is ASKING, and the asking lives beside
   *  the bar — the pane would otherwise be a second thing deciding the question. */
  readonly onAskAgain?: (fieldId: string) => void
  /** A row the office clicked, counter-stamped so a second click on the same row still
   *  asks again. */
  readonly focusRequest?: { readonly fieldId: string; readonly nonce: number }
  /** ⚠️ AN ANSWER REQUESTED FROM THE BAR — a pill click or a ⌥-digit — counter-stamped
   *  for the same reason `pickRequest` is: the same answer picked twice is two events,
   *  and an effect keyed on the VALUE would fire once. */
  readonly answerRequest?: {
    readonly fieldId: string
    readonly value: string
    readonly nonce: number
  }
  /** ⚠️ A PICK REQUESTED FROM THE BAR (⌘1..9), as a counter-stamped value so the same
   *  option chosen twice still fires. A bare `{field_id, index}` object would be
   *  compared by identity and the second identical press would be a no-op. */
  readonly pickRequest?: { readonly fieldId: string; readonly index: number; readonly nonce: number }
  /** ⚠️ CALLED ONCE THE ORDER EXISTS, so the HOST can clear the bar and end the
   *  capture. The pane does not own the bar and must not reach for it. */
  /** ⚠️ `id` ADDED 2026-10-19 so the host can open the new order's pane. James's third
   *  opening path: "After Approve on the capture Review: the capture closes and the new
   *  order's pane opens in its place." It is OPTIONAL because the server's
   *  `sales_order_id` is — see the `capture-approved-link` guard below — and the host
   *  falls back to leaving this pane open when it is absent. */
  /** Opas's one question after an approve, handed up for the BAR to ask.
   *
   *  ⚠️ THE PANE DOES NOT ASK IT. "one line above the bar" (James, 2026-10-26) — the
   *  question is a conversation and conversations happen in the reply line, beside every
   *  other thing Opas says. A question inside the pane would also vanish when the pane
   *  was tucked, taking the answer with it. */
  readonly onAskWhy?: (sessionId: string, ask: NonNullable<CaptureState["ask_why"]>) => void
  readonly onApproved?: (order: {
    readonly number: string
    readonly total: string
    readonly id: string | null
  }) => void
  /** Enter pressed in the bar, as a counter so a second press is not swallowed.
   *
   *  ⚠️ THE PANE DECIDES WHICH ACTION THAT IS, because the pane holds the stage:
   *  capturing → Complete, review → Approve. The host does not know the stage and
   *  giving it a copy would be two sources for one fact. */
  readonly completeRequest?: number
}) {
  const [state, setState] = useState<CaptureState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // ⚠️ LATCHED, UNLIKE EVERY OTHER PIECE OF PANE STATE, and the exception is deliberate.
  // `captureVoice`'s whole design is "a pure function of what is true right now, so no
  // stored message can outlive its cause". This one has no current-state form to be
  // derived from: the server sends it once, on the response to the answer that caused
  // the clearing, and nothing afterwards remembers that it happened.
  const [clearedNote, setClearedNote] = useState<string | null>(null)
  // ⚠️ CLIENT-SIDE AND NOT PERSISTED. "Somebody just tried to finish this" is a fact
  // about this moment, not about the order; a tuck and a re-read must not come back
  // amber. The server reports the same thing for a TYPED phrase, which the client
  // cannot see — hence two sources for one flag.
  const [attempted, setAttempted] = useState(false)
  // ⚠️ THE PILL IS A CONTROL, NOT A LABEL. Hovering or clicking it highlights the
  // rows it counts, which is what makes the count answer "which ones".
  //
  // ⚠️ TWO STATES, NOT ONE, AND A TEST FOUND OUT WHY. With a single flag that hover
  // set and click TOGGLED, a real click turned it off: the pointer enters first
  // (flag true), then the click toggles (flag false), so clicking the pill
  // un-highlighted the rows. Hover is transient, a click is sticky, and the rows are
  // lit by either.
  const [pillHover, setPillHover] = useState(false)
  /** ⚠️ WHICH ROW THE POINTER IS OVER, so its span can light in the bar. The other
   *  direction (caret -> row) arrives as a prop; the two are separate state because
   *  they are driven by different devices and can be true at once. */
  const [hoveredFields, setHoveredFields] = useState<readonly string[]>([])
  const [pillPinned, setPillPinned] = useState(false)
  const pillLit = pillHover || pillPinned
  const [inFlight, setInFlight] = useState(false)
  // ⚠️ A REF, NOT STATE. Two StrictMode mounts would otherwise start two sessions, and
  // the second would orphan the first — a half-typed order nobody can reach.
  const started = useRef(false)
  // ⚠️ ONE SEQUENCER PER PANE INSTANCE, created once. Inside the render body it would be
  // rebuilt every keystroke, `applied` would reset to 0, and every response would be
  // accepted — the sequencer would be present, consulted, and useless, which is worse
  // than absent because it reads as handled.
  const seqRef = useRef(createSequencer())
  /** ⚠️ IS THIS COMPONENT STILL MOUNTED — a ref with a lifetime, not a per-effect flag.
   *
   *  ⚠️ THIS REPLACES AN `alive` FLAG LOCAL TO THE START EFFECT, AND THE BUG IT CAUSED
   *  IS WORTH RECORDING BECAUSE IT WAS INVISIBLE UNTIL THE PARENT CHANGED. That effect
   *  was gated by `started.current` and listed `onSessionStarted` — an inline arrow in
   *  `OpasHost` — among its dependencies. Once the host began re-rendering while the
   *  start call was in flight (it now holds per-pane entry status), the dependency's
   *  identity changed, React ran the CLEANUP, `alive` went false, the re-run hit the
   *  ref guard and returned immediately, and `setState` was never reached. The pane sat
   *  on "Starting…" forever, with no error and no failed request.
   *
   *  ⚠️ THE CALLBACKS ARE HELD IN REFS BELOW SO THEY ARE NOT DEPENDENCIES AT ALL. That
   *  is the actual repair: an effect that must run exactly once cannot depend on a
   *  value whose identity changes, and a ref guard does not save it — it makes the
   *  failure silent. */
  const mounted = useRef(true)
  useEffect(() => {
    // ⚠️ SET TO TRUE IN THE BODY, NOT JUST FALSE IN THE CLEANUP, AND OMITTING THIS
    // WAS A DEFECT I SHIPPED. `main.tsx` wraps the app in `<StrictMode>`, which in
    // development runs effect -> cleanup -> effect. With only the cleanup assigning,
    // `mounted.current` was left FALSE after the double-invoke and never restored —
    // so the start call's promise resolved, hit `if (!mounted.current) return`, and
    // never reached `setState`. The pane sat on "Starting the order…" forever with a
    // 200 OK in the network log.
    //
    // ⚠️ FOUND IN A REAL BROWSER, NOT BY A TEST. Testing Library renders without
    // StrictMode, so no component test could double-invoke the effect; all 147
    // passed. It took driving actual Chrome over CDP to see it.
    //
    // ⚠️ AND IT IS THE SAME CLASS AS THE BUG IT REPLACED. The previous version used
    // an `alive` flag local to the start effect, which a dependency change cancelled
    // — a ref guard turning a failure silent. I swapped it for this ref and
    // reintroduced the shape one layer along: a guard whose state can be left in the
    // blocking position with nothing to report it.
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  // ⚠️ REFS, UPDATED EVERY RENDER. The start effect calls the LATEST callback without
  // listing it, which is the point; a stale closure here would report the session id to
  // a pane id that no longer exists.
  const onSessionStartedRef = useRef(onSessionStarted)
  onSessionStartedRef.current = onSessionStarted

  useEffect(() => {
    if (started.current) return
    started.current = true
    const run = async () => {
      try {
        // ⚠️ ALWAYS A NEW SESSION. THE RESTORE BRANCH IS GONE, BY RULING
        // (2026-10-13): opening Opas never shows an order, so no pane is ever
        // created from a stored id and `readCapture` had no caller here.
        //
        // ⚠️ WHAT WENT WITH IT WAS THIS MORNING'S FIX, and that is the right
        // outcome rather than wasted work. A restored pane raises itself to front,
        // which puts the bar in entry mode, which made the opening effect return
        // before it looked at the phrase — so a tab that had ever started an order
        // could never start another. The fix closed an UNUSABLE restored pane;
        // removing the restore removes the whole class, including the usable case
        // that still held the bar. Smaller mechanism, no bug to have.
        const s = await startCapture(openingLine, prefill)
        if (!mounted.current) return
        setState(s)
        onSessionStartedRef.current?.(s.session_id)
      } catch {
        if (!mounted.current) return
        setError("Could not start the capture")
      }
    }
    void run()
    // ⚠️ NO CLEANUP, AND NO CALLBACK DEPENDENCIES. Both were a bug: the cleanup
    // cancelled a start that was still needed, and the callback dependency was what
    // made the cleanup run at all.
  }, [openingLine, prefill])

  /**
   * LIVE EXTRACTION. One call per pause, the whole text, stale responses dropped.
   *
   * ⚠️ IT RUNS ON `text` CHANGING, INCLUDING TO THE EMPTY STRING. Deleting everything
   * is a real edit that must un-capture everything, so there is no `if (!text) return`
   * — that guard is exactly how the pane would come to show values for words that are
   * no longer on screen.
   *
   * ⚠️ THE SESSION ID IS READ OFF `state`, SO THE EFFECT WAITS FOR THE START CALL. A
   * keystroke before the session exists is not lost: `text` is held in the context, the
   * effect re-runs when `state` arrives, and the first extraction gets the whole thing.
   *
   * ⚠️ THE TIMER IS CLEARED ON EVERY CHANGE, which is what makes this a debounce rather
   * than a throttle. Nine keystrokes in a second produce ONE request, not nine.
   */
  const sessionId = state?.session_id
  // ⚠️ A REF FOR THE CALLBACK. An inline parent callback changes identity every
  // render; held directly it would make any effect depending on it re-run forever —
  // the same trap that left the pane stuck on "Starting…" earlier in this arc.
  const onApprovedRef = useRef(onApproved)
  onApprovedRef.current = onApproved
  const onAskWhyRef = useRef(onAskWhy)
  onAskWhyRef.current = onAskWhy
  // ⚠️ A REF, NOT THE PROP, AND THE DEBOUNCE IS WHY. The extraction effect is keyed on
  // `[sessionId, text]` so that a click does not fire a request; its closure would
  // therefore capture whatever the focus was when the text last changed. A ref reads
  // the current value at send time without adding a dependency that re-triggers.
  const askedFieldIdRef = useRef<string | null>(askedFieldId)
  askedFieldIdRef.current = askedFieldId
  useEffect(() => {
    if (sessionId === undefined) return
    // ⚠️ THE OPENING LINE WAS ALREADY EXTRACTED BY `start`, so the first effect run on
    // a restored or just-started session would re-send identical text for no reason.
    // Skipping when the server's text already equals ours costs one comparison and
    // removes a request per mount.
    if (state?.full_text === text) return
    const timer = window.setTimeout(() => {
      const seq = seqRef.current.issue()
      setInFlight(true)
      // ⚠️ THE CLICKED ROW RIDES THE EXTRACTION. A director who clicks a row and then
      // TYPES the answer gets this response, and without the field the server would
      // compose the question for ITS next choice and the outline would jump away
      // mid-answer.
      void setCaptureText(sessionId, text, seq, askedFieldIdRef.current)
        .then((next) => {
          // ⚠️ THE DROP. A response that arrives behind a newer one describes text the
          // director has already changed; applying it makes the pane show an older
          // reading, which looks like the extractor failing to see words on screen.
          if (!seqRef.current.accept(next.seq ?? seq)) return
          setState(next)
        })
        .catch(() => {
          setError("The order did not reach the server")
        })
        .finally(() => {
          // ⚠️ CLEARED UNCONDITIONALLY, INCLUDING FOR A DROPPED RESPONSE. Gating this
          // on `accept` would leave the placeholder saying "Reading…" forever after a
          // single out-of-order delivery — a stale message, which is the one thing the
          // placeholder ruling forbids.
          setInFlight(false)
        })
    }, EXTRACT_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, text])

  const pick = useCallback(
    async (fieldId: string, oneBased: number) => {
      if (!state) return
      setBusy(true)
      try {
        const next = await choosePick(state.session_id, fieldId, oneBased)
        // ⚠️ A CHOICE IS NOT SEQUENCED AND MUST NOT BE DROPPED. The sequencer orders
        // EXTRACTIONS, which are all readings of the same text; a pick is a decision,
        // it has no competitor, and the server has already applied it. Running it
        // through `accept` would let an extraction in flight discard it.
        //
        // ⚠️ BUT THE SEQUENCE IS ADVANCED, so an extraction already in flight — issued
        // before the pick and describing text the pick has since reinterpreted —
        // cannot land on top of this and re-raise the settled question.
        seqRef.current.accept(seqRef.current.issue())
        setState(next)
      } catch {
        setError("That choice did not reach the server")
      } finally {
        setBusy(false)
      }
    },
    [state],
  )

  const takeTheSwitch = useCallback(
    async (fieldId: string, toValue: string) => {
      if (!state) return
      setBusy(true)
      try {
        const next = await takeSwitch(state.session_id, fieldId, toValue)
        // ⚠️ THE SEQUENCE IS ADVANCED, like a pick. An extraction already in flight
        // was issued before the click and would otherwise land on top of it and put
        // the burial vault straight back.
        seqRef.current.accept(seqRef.current.issue())
        setState(next)
      } catch {
        setError("That change did not reach the server")
      } finally {
        setBusy(false)
      }
    },
    [state],
  )

  /**
   * Answer the question Opas is asking — a pill, a ⌥-digit, or a click.
   *
   * ⚠️ IT IS NOT `pick`, AND THE DIFFERENCE IS THE SHAPE OF WHAT IS BEING SETTLED. A
   * pick settles an AMBIGUITY the extractor raised, by index into options the server
   * stored. A pill answers a field that is simply MISSING, by value — and the pills
   * are recomputed from live order history on every read, so an index into them would
   * settle whichever answer happened to be third by the time it arrived.
   *
   * ⚠️ THE CLEARED NOTE IS LATCHED HERE AND NOWHERE ELSE, because this is the only
   * moment it exists: the server returns it on the response to the answer that caused
   * the clearing and never again. Deriving it from state would be impossible, and
   * storing it server-side would leave a stale sentence surviving a reload.
   */
  const answer = useCallback(
    async (fieldId: string, value: string) => {
      if (!state) return
      setBusy(true)
      try {
        const next = await answerCapture(state.session_id, fieldId, value)
        // ⚠️ THE SEQUENCE IS ADVANCED, exactly as a pick and a switch do. An extraction
        // issued before this answer would otherwise land on top of it and put the
        // question straight back.
        seqRef.current.accept(seqRef.current.issue())
        setState(next)
        setClearedNote(next.cleared_note ?? null)
      } catch {
        setError("That answer did not reach the server")
      } finally {
        setBusy(false)
      }
    },
    [state],
  )

  /**
   * A clicked row asks its question NOW, not on the next keystroke.
   *
   * ⚠️ WITHOUT THIS THE CLICK ONLY MOVED THE OUTLINE until the director typed. The
   * question, its hint and its pills are composed on the server, so seeing them means
   * asking for them — and a click is not a keystroke, so the extraction effect does
   * not fire.
   *
   * ⚠️ IT IS NOT SEQUENCED, LIKE A PICK. The sequencer orders EXTRACTIONS, which are
   * competing readings of the same text; this is a decision about which question to
   * show and has no competitor. But the sequence is ADVANCED, so an extraction already
   * in flight cannot land on top of it and put the previous question back.
   *
   * ⚠️ IT WATCHES A COUNTER-STAMPED REQUEST, NOT `askedFieldId`, AND THE FIRST VERSION
   * WATCHED THE FIELD. `askedFieldId` is non-null whenever the server is asking
   * ANYTHING, so that effect re-read on every question — one redundant request per
   * answer, and in the tests it replaced each fixture with the default one. A request
   * fires only when the office clicks, which is the event this is for.
   *
   * ⚠️ AND THE NONCE IS WHY CLICKING THE SAME ROW TWICE WORKS. Keyed on the field, a
   * second click on the row already focused would be a no-op — and the office clicking
   * again plainly means "ask me that again".
   */
  useEffect(() => {
    if (focusRequest === undefined || state === null) return
    let alive = true
    void readCapture(state.session_id, focusRequest.fieldId)
      .then((next) => {
        if (!alive || !mounted.current) return
        seqRef.current.accept(seqRef.current.issue())
        setState(next)
      })
      .catch(() => {
        // ⚠️ SILENT, AND THAT IS RIGHT HERE. The row is already outlined by the host;
        // a failed re-read means the question text lags, which is a smaller wrong than
        // an error message about a click.
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusRequest?.nonce])

  /** ⚠️ ⌘1..9 ARRIVES FROM THE BAR, because the bar holds the focus. The pane is the
   *  only thing that knows which picks are pending and how to settle one, so the bar
   *  sends an INTENT and this turns it into the call. */
  useEffect(() => {
    if (pickRequest === undefined) return
    void pick(pickRequest.fieldId, pickRequest.index)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickRequest?.nonce])

  /** ⚠️ THE SAME ARRANGEMENT FOR THE SAME REASON: the pills render beside the bar, so
   *  the click and the keystroke both happen up there, and the pane is the only thing
   *  that can perform the call. */
  useEffect(() => {
    if (answerRequest === undefined) return
    void answer(answerRequest.fieldId, answerRequest.value)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answerRequest?.nonce])

  /**
   * Tell the bar what to say and what it can settle.
   *
   * ⚠️ ABOVE THE EARLY RETURNS, because a hook cannot be conditional. It is also the
   * reason the "Starting the order…" placeholder works at all: while `state` is null
   * the pane renders a loading line, and if this effect sat below that return the bar
   * would have nothing to say during exactly the moment it most needs to.
   *
   * ⚠️ THE REPORTED OBJECT IS REBUILT EVERY RENDER, SO THE PARENT MUST NOT STORE IT
   * NAIVELY. `OpasHost` compares field by field before setting state; without that,
   * parent setState -> child re-render -> new object -> parent setState is an infinite
   * loop. That is a real constraint on the parent and is stated at both ends.
   */
  const liveMissing = state?.missing.length ?? 0
  const liveReviewing = state?.status === "review"
  const livePicks = state?.pending_picks ?? []
  const question = captureVoice({
    ready: state !== null,
    inFlight,
    text,
    picks: livePicks,
    missing: liveMissing,
    missingLabels: state?.missing_labels ?? [],
    nextQuestion: state?.next_question ?? null,
    reviewing: liveReviewing,
  })
  useEffect(() => {
    onStatus?.({
      question,
      picks: livePicks,
      // ⚠️ THE SERVER'S OWN FOUR, PASSED THROUGH RATHER THAN RE-DERIVED. `question`
      // above is `captureVoice`'s client-side sentence for the bar; these are the
      // engine's, and the dispatch says the engine decides.
      guidedQuestion: state?.question ?? state?.next_question ?? null,
      guidedHint: state?.question_hint ?? null,
      guidedFieldId: state?.question_field_id ?? null,
      guidedPills: state?.pills ?? [],
      cremation: state?.cremation?.label ?? null,
      clearedNote,
      sessionId: state?.session_id ?? null,
      answeredFieldIds: state?.answered ?? [],
      capturing: state !== null && state.status === "capturing",
      ready: state !== null,
      spans: state?.spans,
      spansForText: state?.spans_for_text ?? null,
      hoveredFieldIds: hoveredFields,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, livePicks, state?.status, state !== null, state?.spans,
      state?.spans_for_text, hoveredFields,
      // ⚠️ THE GUIDED FIELDS ARE IN THE DEPENDENCIES ON PURPOSE. Without them the
      // status reported upward would only refresh when one of the ABOVE changed —
      // so answering a question whose next question has the same `captureVoice`
      // sentence would leave the old question and the old pills on screen.
      state?.question, state?.question_hint, state?.question_field_id,
      state?.pills, state?.cremation?.label, clearedNote, state?.session_id,
      state?.answered])

  // ⚠️ DECLARED WITH THE OTHER HOOKS, ABOVE THE EARLY RETURNS. Placed after them it
  // ran conditionally and React reported "a change in the order of Hooks called by
  // CapturePane" — the pane threw and sixteen tests went red. The handlers it calls
  // are function DECLARATIONS further down and are hoisted, so referring to them
  // here is sound.
  // ⚠️ ⌘ENTER IS THE SAME ACTION, BY RULING, AND WHICH ONE DEPENDS ON THE STAGE:
  // from capture it finishes, from the summary it approves. The prototype binds the
  // same chord to both (`:90049`), which is the behaviour a director already has in
  // their fingers.
  // ⚠️ ENTER FROM THE BAR LANDS HERE, and it chooses by stage exactly as ⌘Enter
  // does below. One decision, two entrances.
  const lastComplete = useRef(0)
  useEffect(() => {
    if (completeRequest === undefined || completeRequest === lastComplete.current) {
      return
    }
    lastComplete.current = completeRequest
    if (state?.status === "review") void doApprove()
    else void doComplete()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [completeRequest])

  /**
   * Enter approves from the Review wherever focus happens to be.
   *
   * ⚠️ AUTOFOCUSING THE BUTTON IS NOT ENOUGH, and a real browser said so. Focus does
   * land on Approve — measured — but that makes Enter depend on the browser's native
   * button activation, so it works only while focus stays there. One click anywhere
   * else and the ruling's "press Enter" quietly stops being true.
   *
   * ⚠️ IT IGNORES ENTER WHILE A FIELD IS FOCUSED. The bar is a textarea and owns its
   * own Enter (it means Complete there); taking it from under the bar would make the
   * two handlers race for the same keypress.
   *
   * ⚠️ DOUBLE-FIRING IS HARMLESS AND GUARDED TWICE: `busy` stops the second call
   * here, and `approve` is idempotent on the server — it reads the session's
   * `sales_order_id` first.
   */
  useEffect(() => {
    if (state?.status !== "review") return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Enter" || e.metaKey || e.ctrlKey || e.altKey) return
      const tag = (document.activeElement as HTMLElement | null)?.tagName
      if (tag === "TEXTAREA" || tag === "INPUT") return
      e.preventDefault()
      void doApprove()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.status, sessionId, busy])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!(e.metaKey || e.ctrlKey) || e.key !== "Enter") return
      e.preventDefault()
      if (state?.status === "review") void doApprove()
      else void doComplete()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.status, sessionId, busy])

  if (error) {
    return (
      <div className="p-4 text-body-sm text-status-error" data-testid="capture-error">
        {error}
      </div>
    )
  }
  if (!state) {
    return (
      <div className="p-4 text-body-sm text-content-muted" data-testid="capture-loading">
        Starting…
      </div>
    )
  }

  const rows = state.surface.rows
  const cols = splitIntoColumns(rows)
  const captured = rows.filter((r) => r.state === "done").length
  // ⚠️ THE SAME SET THE BAR USES, AND THIS CHIP USED TO COUNT ROWS IN THE `needed`
  // STATE. A row only reaches that state AFTER a done signal, so before then it read
  // **"0 needed" with nine rows empty** — which James saw on screen on 2026-10-13,
  // in the same screenshot where the bar said "Nothing needed". Both were answering
  // "has the director said they are finished", not "is anything outstanding".
  //
  // ⚠️ THE BAR WAS FIXED FOR THIS ON 2026-10-12 AND THE CHIP WAS NOT — two readouts
  // of one fact, one of them corrected. That is why they are now computed from the
  // same expression and tested together (`capture-live.test.tsx`): a second place
  // that derives the same number is a second place to get it wrong.
  // ⚠️ DEFAULTED, NOT ASSUMED. An instance older than r209 sends no `switches`, and
  // reading `.length` off the missing key threw during render — which React turns
  // into an EMPTY PANE, the exact symptom James walked into three times. Defaulting
  // is what keeps a missing wire field from looking like a missing feature.
  const switches = state.switches ?? []
  const conflicts = state.conflicts ?? []
  // ⚠️ THE PILL COUNTS ROWS, NOT FIELDS, BY RULING (2026-10-14). It counted
  // `state.missing.length` — fields — while the amber belongs to rows, and two
  // missing fields can share one row. So "2 needed" could mean one amber row and
  // James had to guess which fields the pane meant. Both now read the same list.
  // ⚠️ `amberRowIds` AND `needed` ARE BOTH GONE, AND DELETING THEM IS THE POINT.
  // They were the 2026-10-14 pair — a count and the list it lights, derived from one
  // filter so they could not disagree. The count is now `toGo` over a wider set
  // (every unfilled row, the prototype's `fields.length - filled`), and `toGoRowIds`
  // is that same list, so the invariant is preserved by the NEW pair rather than by
  // the old one surviving beside it.
  //
  // ⚠️ I FIRST KEPT THEM WITH `void amberRowIds` TO SILENCE THE UNUSED WARNING. That
  // is a dead derivation wearing a comment: a later reader would find two count-ish
  // lists and have to work out which the pane obeys. The completion-attempt amber
  // reads each row's own `missing_field_ids`, so nothing needed the list.
  // ⚠️ "to go" IS UNFILLED ROWS, AND `toGoRowIds` IS THAT SAME LIST. The 2026-10-14
  // ruling is that the count and the highlight agree by construction; deriving them
  // from one filter is how that stays true rather than being asserted.
  const toGoRowIds = rows.filter((r) => r.state !== "done").map((r) => r.row_id)
  const toGo = toGoRowIds.length
  // ⚠️ THE EYEBROW AND TITLE READ THE OBJECT TYPE, not a flag the pane invents. A quote
  // and an order are captured by the same pane and the prototype titles them
  // differently (`S.type==='quote'?'New quote':'New order'`).
  const quoteLike = state.object_type === "quote"
  async function doComplete() {
    /**
     * Finish the order. One action behind three entrances, by ruling (2026-10-14).
     *
     * ⚠️ `attempted` IS SET BEFORE THE REQUEST, not after it. The rows must turn
     * amber on the press — waiting for the round trip would leave the office looking
     * at an unchanged pane for the length of a network call and pressing again.
     *
     * ⚠️ IT DOES NOT APPROVE. From a capturing session this moves to the summary;
     * approving is the second press. The office looks at the lines and the total
     * before an order exists.
     */
    if (busy || !sessionId) return
    setAttempted(true)
    setBusy(true)
    try {
      setState(await completeCapture(sessionId))
    } catch {
      setError("Could not finish the order. Nothing was written.")
    } finally {
      setBusy(false)
    }
  }

  async function doApprove() {
    // ⚠️ GUARDED AGAINST THE DOUBLE CLICK ON THE CLIENT AS WELL AS THE SERVER. The
    // server is idempotent (it reads `sales_order_id` first), so a second request
    // cannot make a second order — but it would still fire a second round trip and
    // briefly re-render, and `busy` is what stops the office seeing that.
    if (busy || !sessionId) return
    setBusy(true)
    try {
      const next = await approveCapture(sessionId)
      setState(next)
      if (next.sales_order_number) {
        onApprovedRef.current?.({
          number: next.sales_order_number,
          total: next.total ?? "0.00",
          id: next.sales_order_id ?? null,
        })
      }
      // ⚠️ AFTER `onApproved`, SO THE ORDER'S OWN LINE IS SAID FIRST. The approve
      // acknowledgement is the answer to what the person just did; the question is the
      // next thing Opas says, not a replacement for it.
      //
      // ⚠️ AND ONLY FROM THE APPROVE RESPONSE, never from a plain read. The server
      // recomputes `ask_why` on every read so a reload still shows it — but handing it
      // up from here means the bar asks once, at the moment the dispatch names ("once,
      // right after you approve"), rather than every time this pane refetches.
      if (next.ask_why) {
        onAskWhyRef.current?.(sessionId, next.ask_why)
      }
    } catch (e) {
      // ⚠️ THE 409'S BLOCKERS ARE SHOWN, NOT "something went wrong". The server
      // re-checks inside the transaction, so it can refuse for a reason the pane
      // had not seen yet — a product deleted a second ago, a pick reopened.
      const detail = (e as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail
      const list =
        detail && typeof detail === "object" && "blockers" in detail
          ? (detail as { blockers?: string[] }).blockers
          : undefined
      setError(
        list?.length
          ? list.join(" ")
          : "The order could not be created. Nothing was written.",
      )
    } finally {
      setBusy(false)
    }
  }

  const reviewing = state.status === "review"
  const approvedOrder =
    state.status === "approved" && state.sales_order_number
      ? {
          number: state.sales_order_number,
          total: state.total ?? "0.00",
          // ⚠️ KEPT THOUGH THIS COMPONENT NO LONGER RENDERS IT: `onApproved` hands it to
          // the host, which is what decides whether to close this pane and open the
          // order's. Dropping it here would make the host's id branch unreachable.
          id: state.sales_order_id ?? null,
        }
      : null
  const blockers = state.blockers ?? []
  /**
   * The running total for the footer, or null while there is nothing to total.
   *
   * ⚠️ NULL RATHER THAN "$0.00", AND THE PROTOTYPE AGREES: `${t?money(t):''}` — it
   * renders the total only when there IS one. A "$0.00" on a fresh order is a priced
   * order that costs nothing, which is a different and wrong statement from "no vault
   * chosen yet".
   *
   * ⚠️ AND IT READS THE SERVER'S TOTAL, never a sum of the lines. `assess_approval`
   * prices the order from the tenant's products; adding the lines here would be a
   * second total that could disagree with the one Approve obeys.
   */
  const total = (() => {
    const raw = state.total
    if (raw === null || raw === undefined) return null
    const n = Number(raw)
    if (!Number.isFinite(n) || n === 0) return null
    return money(raw)
  })()
  // ⚠️ `missingLabels` IS GONE FROM THIS PANE AND STILL ON THE WIRE. It fed "Still
  // need: service date, cemetery" beside the removed Complete button; `captureVoice`
  // (line 204) still reads it for the BAR's own sentence, and the Approve blockers
  // still name every gap at once because that is a report and should be. Deleted here
  // rather than left unused.
  // ⚠️ AMBER ONLY AFTER AN ATTEMPT, by ruling: "as soon as Complete is attempted".
  // Colouring a half-typed order's gaps while the director is still speaking would
  // make every order start alarming.
  const amber = attempted || (state.completion_attempt ?? false)
  const lines = state.lines ?? []

  return (
    <div className="flex flex-col gap-3 p-3" data-testid="capture-pane">
      {/* header — prototype `:413` */}
      {/* ── the header — the prototype's `.ph` ────────────────────────────────────
          ⚠️ REPLACED 2026-10-27 BY RULING. James, after walking the screen: "The pane
          is still the old one. It says 'Order capture', 'RULES', 'Deceased name' and
          'Not mentioned yet'… The executor kept the old pane's look."

          The prototype's shape, quoted:
            `<div class="ph"><div><div class="eb">Order</div>
                                  <div class="pt">New order</div></div>
                             <div class="pills">…chips…</div></div>` */}
      <div
        className="flex flex-wrap items-end justify-between gap-3"
        data-testid="capture-head"
      >
        <div>
          {/* `.eb{font-size:10.5px;letter-spacing:.16em;text-transform:uppercase}` */}
          <div
            className="text-micro uppercase tracking-[0.16em] text-content-subtle"
            data-testid="capture-eyebrow"
          >
            {quoteLike ? "Quote" : "Order"}
          </div>
          {/* `.pt{font-size:19px;font-weight:400;letter-spacing:-.01em}` */}
          <div
            className="mt-0.5 text-[19px] font-normal tracking-[-0.01em] text-content-strong"
            data-testid="capture-title"
          >
            {reviewing ? "Review" : quoteLike ? "New quote" : "New order"}
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5" data-testid="capture-chips">
          {/* ⚠️ THE CREMATION CHIP IS THE SERVER'S WORD, and it lives here as well as
              beside the question because this is the prototype's place for it —
              `.chip.kind` in the pane header, where the order's KIND belongs. */}
          {state.cremation?.label !== undefined && (
            <span
              className="whitespace-nowrap rounded-full border border-[rgba(143,176,207,0.5)] px-2.5 py-0.5 text-[12px] text-[rgb(143,176,207)]"
              data-testid="capture-kind-chip"
            >
              {state.cremation.label}
            </span>
          )}
          <span
            className="whitespace-nowrap rounded-full border border-border-subtle px-2.5 py-0.5 text-[12px] text-content-muted"
            data-testid="capture-captured-pill"
          >
            <b className="text-content-strong">{captured}</b> captured
          </span>
          {/* ⚠️ "to go", NOT "needed", AND IT COUNTS THE SAME ROWS IT LIGHTS. The
              2026-10-14 ruling is that the count and the highlight must agree by
              construction — James read "2 needed" with nothing highlighted and had to
              guess. `toGo` is the unfilled rows and `toGoRowIds` is that same list, so
              they cannot disagree.

              ⚠️ IT COUNTS UNFILLED ROWS RATHER THAN REQUIRED-UNANSWERED ONES, which
              is the prototype's meaning (`fields.length - filled`) and is wider than
              the old pill's. With every applicable question now rendering a row, an
              optional unanswered row is a question still to be asked — which is what
              "to go" says. */}
          {toGo > 0 && (
            <button
              type="button"
              className="whitespace-nowrap rounded-full border border-[rgba(227,171,79,0.45)] px-2.5 py-0.5 text-[12px] text-[rgb(227,171,79)]"
              data-testid="capture-needed-pill"
              data-lit={pillLit ? "true" : "false"}
              aria-label={`${toGo} line${toGo === 1 ? "" : "s"} still to answer`}
              onMouseEnter={() => setPillHover(true)}
              onMouseLeave={() => setPillHover(false)}
              onFocus={() => setPillHover(true)}
              onBlur={() => setPillHover(false)}
              onClick={() => setPillPinned((v) => !v)}
            >
              <b>{toGo}</b> to go
            </button>
          )}
          {/* ⚠️ KEPT FROM 2026-10-16 AND NOT MENTIONED IN THE FIXES. The words carry a
              dotted underline in the bar; this says HOW MANY, so one scrolled out of
              view above the 40vh cap is still accounted for. */}
          {state.unrecognized.length > 0 && (
            <span
              className="whitespace-nowrap rounded-full border border-dashed border-border-base px-2.5 py-0.5 text-[12px] text-content-muted"
              data-testid="capture-unrecognized-count"
              title={state.unrecognized.join(", ")}
            >
              <b className="text-content-strong">{state.unrecognized.length}</b> not
              understood
            </span>
          )}
        </div>
      </div>

      {!reviewing && (
        <>
          {/* ⚠️ THE "Order capture / RULES" SUB-HEADER IS GONE, BY RULING. James,
              2026-10-27: "'RULES' in the corner is an internal label for how Opas
              understood you. You shouldn't see it." It was taken from the prototype's
              `AI ASSIST` label and corrected to RULES because this slice makes no
              model call — accurate, and still an internal fact on a screen for the
              office. The decision log is where it belongs, and it is already there:
              every row carries `source` (`catalog/rules/...`, `bar/model/asked`).

              ⚠️ AND "Order capture" WENT WITH IT because the header above now says
              what this is — eyebrow "Order", title "New order". The old pane said it
              twice. */}
          {/* ── the rows — the prototype's `.rows` / `.row` ─────────────────────────
              ⚠️ TWO COLUMNS, BY RULING (2026-10-13), AND NO SCROLL CONTAINER. Ten rows
              in one column do not fit above the bar at 800px tall, so the pane grew a
              scrollbar and auto-scrolled the focused row out of view — James watched a
              captured row disappear. Two columns fit, which is why the grid and the
              no-scrolling rule are one change.

              ⚠️ EACH ROW IS A BUTTON NOW, BY RULING (2026-10-27): "clicking a row asks
              that question again". It was a `div` with a hover handler; a thing the
              office is told to click is a button, and the keyboard gets it for free.

              `.row{display:grid;grid-template-columns:18px minmax(0,1fr);…}`
              `.row.filled .mk{background:var(--ok)}`  — the tick
              `.row.current{border-color:var(--steel-b);box-shadow:0 0 0 3px …}`
              `.row.current .v.empty{color:var(--steel);font-style:normal}` */}
          <div
            className="grid grid-cols-2 items-start gap-x-3 gap-y-2"
            data-testid="capture-rows"
          >
            {[cols.left, cols.right].map((column, ci) => (
              <div
                key={ci}
                className="flex min-w-0 flex-col gap-2"
                data-testid={`capture-column-${ci === 0 ? "left" : "right"}`}
              >
                {column.map((r) => {
                  const filled = r.state === "done"
                  // ⚠️ THE ASKED ROW COMES FROM THE SERVER'S `question_field_id`, not
                  // from the pane's own guess at what is next. The question above the
                  // bar and the outline below it must name the same field, and two
                  // derivations of "what is Opas asking" is how they would come to
                  // disagree while both looked right.
                  const asking =
                    askedFieldId !== null &&
                    (r.field_ids ?? []).includes(askedFieldId)
                  // ⚠️ TWO HIGHLIGHTS, NOT ONE, AND EACH AGREES WITH ITS OWN COUNT.
                  // `amber` fires after a completion attempt and lights the
                  // REQUIRED-unanswered rows — "what is blocking you". `litByPill`
                  // fires while the "N to go" pill is hovered and lights the rows that
                  // pill COUNTS, which are the unfilled ones. They were one attribute
                  // reading `missing_field_ids`, so hovering a pill counting 10 would
                  // light 7 — the 2026-10-14 defect ("the count and the highlight must
                  // agree") reintroduced by widening the count.
                  const litByPill = pillLit && !filled
                  return (
                    <button
                      key={r.row_id}
                      type="button"
                      data-testid={`capture-row-${r.row_id}`}
                      data-state={r.state}
                      {...(asking ? { "data-asking": "true" } : {})}
                      {...(hoveredFields.length > 0 &&
                      (r.field_ids ?? []).some((f) => hoveredFields.includes(f))
                        ? { "data-hovered": "true" }
                        : {})}
                      {...((caretFieldIds ?? []).length > 0 &&
                      (r.field_ids ?? []).some((f) =>
                        (caretFieldIds ?? []).includes(f),
                      )
                        ? { "data-caret": "true" }
                        : {})}
                      {...((r.missing_field_ids ?? []).length > 0
                        ? { "data-missing": "true" }
                        : {})}
                      {...(amber && (r.missing_field_ids ?? []).length > 0
                        ? { "data-amber": "true" }
                        : {})}
                      {...(litByPill ? { "data-lit": "true" } : {})}
                      onMouseEnter={() => setHoveredFields(r.field_ids ?? [])}
                      onMouseLeave={() => setHoveredFields([])}
                      // ⚠️ IT ASKS THE ROW'S OWN `edit_target`, which the SERVER named
                      // — `cemetery` for the cemetery row, `service_location` for the
                      // Service row. Deriving it from `field_ids[0]` would ask about
                      // the cemetery's TOWN on a row whose first source happens to be
                      // the town.
                      onClick={() => {
                        const target = r.edit_target ?? (r.field_ids ?? [])[0]
                        if (target !== undefined) onAskAgain?.(target)
                      }}
                      title={filled ? "Change this" : "Answer this"}
                      className={`grid w-full grid-cols-[18px_minmax(0,1fr)] items-start gap-x-2.5 rounded-xl border px-3 py-2 text-left transition-[border-color,box-shadow,background] ${
                        asking
                          ? ROW_ASKING_CLASS
                          : amber && (r.missing_field_ids ?? []).length > 0
                            ? ROW_CLASS.needed
                            : (ROW_CLASS[r.state] ?? ROW_CLASS.not_mentioned)
                      } ${
                        (caretFieldIds ?? []).length > 0 &&
                        (r.field_ids ?? []).some((f) =>
                          (caretFieldIds ?? []).includes(f),
                        )
                          ? ROW_CARET_CLASS
                          : ""
                      } ${litByPill ? ROW_LIT_CLASS : ""}`}
                    >
                      {/* `.mk` — a ring, filled green with a tick once answered. */}
                      <span
                        aria-hidden
                        className={`row-span-2 mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px] ${
                          asking && !filled
                            ? MARK_ASKING_CLASS
                            : (MARK_CLASS[r.state] ?? MARK_CLASS.not_mentioned)
                        }`}
                      >
                        {filled ? "✓" : ""}
                      </span>
                      {/* `.lab{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase}` */}
                      <span className="min-w-0 text-micro uppercase tracking-[0.13em] text-content-subtle">
                        {r.label}
                      </span>
                      {/* `.v` / `.v.empty` — and "Opas is asking" is the prototype's
                          own words for the current row's empty value. */}
                      <span
                        className={`col-start-2 min-w-0 break-words text-body-sm ${
                          filled
                            ? "text-content-strong"
                            : asking
                              ? "text-[rgb(143,176,207)]"
                              : "italic text-content-muted"
                        }`}
                      >
                        {filled
                          ? r.value
                          : asking
                            ? ASKING_TEXT
                            : valueText(r.state, r.value)}
                      </span>
                      {r.secondary_value ? (
                        <span className="col-start-2 min-w-0 text-micro text-content-muted">
                          {r.secondary_value}
                        </span>
                      ) : null}
                    </button>
                  )
                })}
              </div>
            ))}
          </div>

          {/* ⚠️ THE AMBIGUITY LIST MOVED OUT OF THIS PANE ON 2026-10-27, BY RULING.
              James: "The ambiguity choice list becomes these same pills." So the
              options now render in the pills row above the bar, from the server's
              `pills` — one place answers Opas, whether the question is "which of these
              two did you mean" or "which cemetery".

              ⚠️ AND THE PANE IS THE WRONG PLACE FOR IT FOR THE SAME REASON THE QUESTION
              WAS MOVED OUT ON 2026-10-20: this pane can be TUCKED. A choice list that
              disappears with the pane takes the only way to answer with it, and the
              bar then sits there asking a question with no visible options.

              ⚠️ THE SETTLING PATH IS UNCHANGED AT THE SERVER. A pill answers through
              `/answer`, which writes the same resolution `/choose` wrote — `choose`
              stores `options[index-1][0]` and `answer` stores the value directly, so
              the two are the same write by different handles. `choosePick` and the
              `pickRequest` channel stay because ⌘1..9 from the bar still uses them. */}

          {/* ⚠️ A SWITCH IS NOT A PICK, AND IT IS RENDERED DIFFERENTLY ON PURPOSE.
              The field is already captured — the row above shows the value with a
              tick — so this is a quiet one-click correction, not a question. A pick
              is a numbered list that blocks the field; styling them alike would make
              a settled field look unsettled. Ruled 2026-10-13. */}
          {switches.length > 0 && (
            <div className="flex flex-col gap-1" data-testid="capture-switches">
              {switches.map((sw) => (
                <button
                  key={`${sw.field_id}-${sw.to_value}`}
                  type="button"
                  disabled={busy}
                  onClick={() => void takeTheSwitch(sw.field_id, sw.to_value)}
                  data-testid={`capture-switch-${sw.field_id}`}
                  className="self-start rounded-base border border-border-subtle px-2 py-0.5 text-micro text-content-muted hover:bg-surface-sunken focus-ring-accent"
                >
                  {sw.to_label}
                </button>
              ))}
            </div>
          )}

          {/* ⚠️ A CONFLICT IS NOT "NOT UNDERSTOOD", AND IT GETS ITS OWN BLOCK ABOVE
              THAT ONE. The extractor read both phrases correctly; the combination is
              what the vault does not offer. Showing it among the unreadable text
              would tell the director their words were wrong, when what is wrong is
              the pairing — and it is ranked higher because it is the one of the two
              that names a decision only they can make.

              ⚠️ IT NAMES WHAT IS AVAILABLE. "Not available on this vault" with no
              alternatives is a dead end; the permitted list is what turns the
              message into a next step. */}
          {conflicts.length > 0 && (
            <div
              className="rounded-base border border-[rgba(224,168,74,0.55)] bg-[rgba(224,168,74,0.08)] p-2"
              data-testid="capture-conflicts"
            >
              <div className="text-micro uppercase tracking-wide text-[rgb(224,168,74)]">
                Not available on this vault
              </div>
              <ul className="mt-1 flex flex-col gap-1">
                {conflicts.map((c) => (
                  <li
                    key={c.field_id}
                    className="text-body-sm text-content-base"
                    data-testid={`capture-conflict-${c.field_id}`}
                  >
                    {/* ⚠️ THE SERVER'S OWN MESSAGE, NOT A SENTENCE BUILT HERE. The
                        permitted set and the refused value are both in it, and a
                        second wording in the client could disagree with the engine
                        about which combinations are refused. */}
                    {c.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ⚠️ THE "NOT UNDERSTOOD" BOX IS GONE SINCE 2026-10-16, BY RULING. The
              words themselves now carry a dotted underline in the bar, which is where
              the director is already looking — a list underneath repeated them in a
              second place and made a half-typed order look like it had errors.

              ⚠️ THE COUNT STAYS, IN THE HEADER, because the underline is only visible
              while the text is on screen and a long order can push a word out of view
              above the 40vh cap. James asked for exactly that: "Remove the 'Not
              understood' box; keep a count in the pane header." */}

          {/* ⚠️ WHAT THE SERVER IS READING, SHOWN BACK. Not an input — the bar is the
              only input, by ruling. This is the text the rows above were derived
              from, so a director who sees a row they did not expect can see the words
              that produced it. On a line-captured session the server has no text and
              the lines are shown instead, which is the only thing there is. */}
          {state.full_text !== null ? (
            state.full_text.trim() !== "" && (
              <div
                className="border-t border-border-subtle pt-2 text-micro text-content-subtle"
                data-testid="capture-text-echo"
              >
                {state.full_text}
              </div>
            )
          ) : (
            state.typed_lines.length > 0 && (
              <ul
                className="flex flex-col gap-0.5 border-t border-border-subtle pt-2"
                data-testid="capture-lines"
              >
                {state.typed_lines.map((l, i) => (
                  <li key={`${l}-${i}`} className="text-micro text-content-subtle">
                    {l}
                  </li>
                ))}
              </ul>
            )
          )}
          {/* ⚠️ THE "Complete order" BUTTON AND ITS HINT ARE GONE, BY RULING. James,
              2026-10-27: "Remove the Complete order button and its hint. When
              everything needed is answered, Opas says 'That's everything.' with a
              Review pill (⌥1) and Enter, as in the prototype."

              ⚠️ AND IT SUPERSEDES THE 2026-10-14 RULING THAT PUT IT THERE, which said:
              "the only way to finish was to type the right phrase, and the phrase that
              most people would type — 'approve' — was the one that did not work. A
              control that is always there cannot be the thing nobody found." That
              problem is solved differently now: the Review PILL is the always-visible
              control, it sits where the office is already looking, and it carries its
              own key. The button was a second one, in the pane, which the pills then
              covered.

              ⚠️ THE ACTION ITSELF IS UNTOUCHED. `doComplete` still exists and is still
              reached three ways — Enter from the bar, ⌘Enter, and the Review pill. The
              button was one entrance to it, not the thing itself.

              ⚠️ "Still need: …" WENT WITH IT. It named the missing fields, which was
              right when the pane was the only surface; now the question above the bar
              names ONE thing and the rows carry the rest, and a sentence listing them
              all is the report that ruling replaced. */}

          {/* ── the footer — the prototype's `.pf` ───────────────────────────────────
              `<div class="pf"><span class="note">${S.note}</span>
                               <span class="tot">${money(t)}</span></div>`

              ⚠️ ONE LINE, TWO ENDS: why something was just cleared on the left, the
              running total on the right. James, 2026-10-27: "the footer with the
              one-line note and the running total."

              ⚠️ THE NOTE IS THE SERVER'S AND IS TRANSIENT. `clears.py` composes it
              beside the rule it explains — the arrangement the pick hint's
              wrong-for-a-round copy is the argument for — and it arrives on the
              response to the answer that caused the clearing, never on a plain read.

              ⚠️ WITH NO NOTE THE LEFT SIDE SAYS WHAT CLICKING DOES, which is the
              prototype's fallback (`'Click any line to change it.'`) and is what makes
              the clickable rows discoverable. It is the only place that says so.

              ⚠️ AMBER FOR THE NOTE (`.pf .note{color:var(--need)}`), grey otherwise.
              Nothing went wrong; something stopped applying. */}
          <div
            className="flex items-baseline justify-between gap-3 border-t border-border-subtle pt-2"
            data-testid="capture-footer"
          >
            <span
              className={`text-micro ${
                clearedNote !== null ? "text-status-warning" : "text-content-subtle"
              }`}
              data-testid={
                clearedNote !== null ? "capture-cleared-note" : "capture-footer-hint"
              }
            >
              {clearedNote ?? FOOTER_HINT}
            </span>
            {/* ⚠️ `tabular-nums` SO THE DIGITS DO NOT JUMP as the total changes under
                the director's hand — the same reason the summary's lines use it. */}
            {total !== null && (
              <span
                className="text-body-sm tabular-nums text-content-strong"
                data-testid="capture-total"
              >
                {total}
              </span>
            )}
          </div>

        </>
      )}

      {/* review stage — prototype `:389-404`. ⚠️ READ-ONLY: no Approve control, by
          ruling (E5). A disabled button would read as a feature that exists. */}
      {reviewing && (
        <div data-testid="capture-summary" className="flex flex-col gap-2">
          {/* ── the subject ───────────────────────────────────────────────
              ⚠️ THE DECEASED NAME LIVES HERE AND NOWHERE ELSE, which is why the
              Review had no name on it at all: the summary surface puts the decedent
              in a `SubjectSlot` — "Smith" over "1948 — 2026" above the grid, from
              the prototype — and neither the API nor this render had ever carried
              it. James's 09:24 screenshot. */}
          {state.surface.subject_primary ? (
            <div data-testid="capture-subject">
              <div className="text-body text-content-strong">
                {state.surface.subject_primary}
              </div>
              {state.surface.subject_secondary ? (
                <div className="text-micro text-content-muted">
                  {state.surface.subject_secondary}
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="grid grid-cols-2 gap-2">
            {rows.map((r) => (
              <div
                key={r.row_id}
                data-testid={`summary-row-${r.row_id}`}
                className="rounded-base border border-border-subtle p-2"
              >
                <div className="text-micro uppercase tracking-wide text-content-subtle">
                  {r.label}
                </div>
                <div className="text-body-sm text-content-strong">
                  {r.value ?? "None"}
                </div>
                {r.secondary_value ? (
                  <div className="text-micro text-content-muted">
                    {r.secondary_value}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
          {/* ── line items and the total ──────────────────────────────────
              Prototype `:179`, `:393-395`: the vault, then one row per extra, then
              a Total. The prices here come from the TENANT'S products, matched by
              exact name — the prototype used a hardcoded `VAULTS` map (`:270`). */}
          {lines.length > 0 && (
            <div
              className="flex flex-col gap-1 rounded-base border border-border-subtle p-2"
              data-testid="capture-lineitems"
            >
              {lines.map((l) => (
                <div
                  key={`${l.kind}-${l.description}`}
                  className="flex items-baseline justify-between gap-3"
                  data-testid={`capture-line-${l.kind}`}
                >
                  <span className="text-body-sm text-content-strong">
                    {l.description}
                  </span>
                  {/* ⚠️ `tabular-nums` SO THE COLUMN LINES UP. Money read off a
                      summary is compared down the column, not across. */}
                  <span className="text-body-sm tabular-nums text-content-strong">
                    {money(l.line_total)}
                  </span>
                </div>
              ))}
              <div
                className="mt-1 flex items-baseline justify-between gap-3 border-t border-border-subtle pt-1"
                data-testid="capture-total"
              >
                <span className="text-body-sm font-medium text-content-strong">
                  Total
                </span>
                <span className="text-body-sm font-medium tabular-nums text-content-strong">
                  {money(state.total ?? "0.00")}
                </span>
              </div>
            </div>
          )}

          {/* ── what is stopping approval ──────────────────────────────────
              ⚠️ THE REASONS ARE SHOWN, NOT A DISABLED BUTTON ALONE. A greyed
              control says "no" without saying why, and the office cannot fix a
              missing product it has not been told about. */}
          {blockers.length > 0 && (
            <div className="flex flex-col gap-1" data-testid="capture-blockers">
              <span className="text-micro uppercase tracking-wide text-content-subtle">
                Before this can be approved
              </span>
              <ul className="list-disc pl-4">
                {blockers.map((b) => (
                  <li
                    key={b}
                    className="text-body-sm text-status-error"
                    data-testid="capture-blocker"
                  >
                    {b}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── what Approve will do ───────────────────────────────────────
              ⚠️ STATED BEFORE THE PRESS, BECAUSE THE PRESS NOW CONFIRMS (James's
              step 3, 2026-10-16). Approve used to make a draft; it now creates a
              CONFIRMED order, which is the moment an order enters the end-of-day
              batch's net. This line is the last chance to notice a wrong service
              date, and it is the server's sentence rather than one rebuilt here —
              see `approve_effect` in the service type. */}
          {state.approve_effect && blockers.length === 0 && (
            <div
              className="text-body-sm text-content-muted"
              data-testid="capture-approve-effect"
            >
              {state.approve_effect}
            </div>
          )}

          {/* ── the approve control ────────────────────────────────────────
              Prototype `:404`: a primary button labelled by the surface's own verb,
              beside a way back. ⚠️ ABSENT WHEN BLOCKED RATHER THAN DISABLED, which
              is the same ruling (E5) that kept a disabled Approve out of the
              read-only summary: a control that cannot act should not be on screen
              pretending it might. */}
          <div className="flex items-center gap-3">
            {blockers.length === 0 ? (
              <button
                type="button"
                data-testid="capture-approve"
                // ⚠️ FOCUSED SO ENTER APPROVES, by ruling: "you see the summary and
                // press Enter or Approve". Enter on a focused button is the
                // browser's own behaviour — binding a second Enter handler would
                // fight it and would also fire while the bar had focus.
                autoFocus
                disabled={busy}
                onClick={() => void doApprove()}
                /* ⚠️ IT RENDERED AS A BLANK WHITE BLOCK, and the cause was two tokens
                   agreeing. `bg-accent` resolves to a near-white on this overlay and
                   `text-content-inverse` is also near-white, so the label was white
                   on white — James's screenshot showed an empty box where the
                   primary action was.

                   ⚠️ THE PROTOTYPE'S OWN VALUES, NOT TOKENS, AND DELIBERATELY SO.
                   `.btn.primary` in `2026-10-01-opas-overlay.html` is
                   `background:var(--fg); color:#0a0a0a; border-color:var(--fg)` — a
                   near-WHITE pill with NEAR-BLACK text, which is what a light
                   primary on dark glass has to be. This overlay is written in the
                   prototype's literals throughout (GLASS, ROW_CLASS), because it is
                   reproducing one specific surface rather than composing platform
                   cards; reaching for the platform's accent pair is what produced
                   the collision.

                   ⚠️ AND THE FOCUS RING IS EXPLICIT, because Enter now approves from
                   here — a keyboard affordance nobody can see is a keyboard
                   affordance nobody uses. */
                style={{
                  background: busy ? "rgba(242,242,242,0.45)" : "#f2f2f2",
                  color: "#0a0a0a",
                  border: "1px solid #f2f2f2",
                  borderRadius: 999,
                  padding: "7px 16px",
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: busy ? "default" : "pointer",
                }}
                className="outline-none focus-visible:ring-2 focus-visible:ring-[rgba(255,255,255,0.85)] focus-visible:ring-offset-2 focus-visible:ring-offset-[rgba(14,14,14,0.9)]"
              >
                {busy ? "Creating…" : "Approve & Create Sales Order"}
              </button>
            ) : null}
            <span className="text-micro text-content-subtle">
              {blockers.length === 0
                ? "Or type \u201capprove\u201d."
                : "Fix the above, or keep typing to correct the order."}
            </span>
          </div>
        </div>
      )}

      {/* ── after approve ─────────────────────────────────────────────────
          Prototype `:493` echoes one line and is done. ⚠️ THE NUMBER AND THE TOTAL,
          because those are the two things the office writes down.

          ⚠️ THIS IS NOW THE FALLBACK PATH, NOT THE NORMAL ONE. Since 2026-10-19 the HOST
          closes this pane the moment Approve returns an order id and opens the order's
          own pane in its place — James's third opening path. So the office reads the
          number off the Sales Order Pane, which also carries "Open the full order". This
          block is what they see when the server sent NO id and there is therefore no
          pane to open: the number as plain text, for the few seconds before the timer
          closes it.

          ⚠️ THE `capture-approved-link` ANCHOR IS DELETED, and its ruling is superseded
          rather than forgotten. It was added 2026-10-14 — "the order number links to the
          order", because James was reading SO-2026-0001 off this pane and navigating to
          /ar/orders by hand. It required `approvedOrder.id`, and an id is exactly the
          condition under which the host now closes this pane, so the anchor had become
          unreachable in the app: dead machinery behind a live-looking guard. What the
          ruling asked for is better served by the order's pane opening by itself. */}
      {approvedOrder && (
        <div className="flex flex-col gap-1" data-testid="capture-approved">
          <span className="text-body-sm text-content-strong">
            Created {approvedOrder.number}
          </span>
          <span className="text-micro tabular-nums text-content-muted">
            {money(approvedOrder.total)}
          </span>
        </div>
      )}
    </div>
  )
}
