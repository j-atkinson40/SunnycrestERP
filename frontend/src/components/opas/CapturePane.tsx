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
import { Link } from "react-router-dom"

import {
  completeCapture,
  approveCapture,
  choosePick,
  setCaptureText,
  startCapture,
  takeSwitch,
  type CapturePick,
  type CaptureState,
} from "@/services/opas-capture-service"
import type { CaptureSpan } from "@/services/opas-capture-service"
import { EXTRACT_DEBOUNCE_MS, createSequencer } from "./capture-sequence"

/** What the pane tells the command line about itself.
 *
 * ⚠️ IT TRAVELS UPWARD BECAUSE THE INPUT IS UP THERE. The bar needs the placeholder
 * (which must describe what is happening NOW), the pending picks (so ⌘1..9 can settle
 * one), and whether the session is still capturing (so Enter can be a no-op). All
 * three are facts about the pane; the bar is where they are used.
 */
export interface EntryPaneStatus {
  /** ⚠️ DERIVED ON EVERY RENDER, NEVER LATCHED — see `placeholderFor`. */
  readonly placeholder: string
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
export function placeholderFor(args: {
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
    const n = args.picks[0].options.length
    return `Which one? 1–${Math.min(n, 9)}, or ⌘ and the number`
  }
  if (args.reviewing) return "Ready to review"
  if (args.inFlight) return "Reading what you typed…"
  if (args.text.trim() === "") return "Say what the director said"
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
  onSessionStarted,
  text = "",
  onStatus,
  pickRequest,
  onApproved,
  completeRequest,
  caretFieldIds,
}: {
  /** Fed through extraction on start, per the prototype (`:568` calls `feed` at once). */
  readonly openingLine?: string
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
  /** ⚠️ A PICK REQUESTED FROM THE BAR (⌘1..9), as a counter-stamped value so the same
   *  option chosen twice still fires. A bare `{field_id, index}` object would be
   *  compared by identity and the second identical press would be a no-op. */
  readonly pickRequest?: { readonly fieldId: string; readonly index: number; readonly nonce: number }
  /** ⚠️ CALLED ONCE THE ORDER EXISTS, so the HOST can clear the bar and end the
   *  capture. The pane does not own the bar and must not reach for it. */
  readonly onApproved?: (order: { readonly number: string; readonly total: string }) => void
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
        const s = await startCapture(openingLine)
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
  }, [openingLine])

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
      void setCaptureText(sessionId, text, seq)
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

  /** ⚠️ ⌘1..9 ARRIVES FROM THE BAR, because the bar holds the focus. The pane is the
   *  only thing that knows which picks are pending and how to settle one, so the bar
   *  sends an INTENT and this turns it into the call. */
  useEffect(() => {
    if (pickRequest === undefined) return
    void pick(pickRequest.fieldId, pickRequest.index)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickRequest?.nonce])

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
  const placeholder = placeholderFor({
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
      placeholder,
      picks: livePicks,
      capturing: state !== null && state.status === "capturing",
      ready: state !== null,
      spans: state?.spans,
      spansForText: state?.spans_for_text ?? null,
      hoveredFieldIds: hoveredFields,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeholder, livePicks, state?.status, state !== null, state?.spans,
      state?.spans_for_text, hoveredFields])

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
  const amberRowIds = rows
    .filter((r) => (r.missing_field_ids ?? []).length > 0)
    .map((r) => r.row_id)
  const needed = amberRowIds.length
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
        })
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
          id: state.sales_order_id ?? null,
        }
      : null
  const blockers = state.blockers ?? []
  const missingLabels = state.missing_labels ?? []
  // ⚠️ AMBER ONLY AFTER AN ATTEMPT, by ruling: "as soon as Complete is attempted".
  // Colouring a half-typed order's gaps while the director is still speaking would
  // make every order start alarming.
  const amber = attempted || (state.completion_attempt ?? false)
  const lines = state.lines ?? []

  return (
    <div className="flex flex-col gap-3 p-3" data-testid="capture-pane">
      {/* header — prototype `:413` */}
      <div className="flex items-center gap-2" data-testid="capture-head">
        <span className="text-body-sm font-medium text-content-strong">
          {reviewing ? "Review" : "Order capture"}
        </span>
        <span
          className="rounded-full border border-border-subtle px-2 py-0.5 text-micro text-content-muted"
          data-testid="capture-captured-pill"
        >
          <b className="text-content-strong">{captured}</b> captured
        </span>
        {/* ⚠️ THE COUNT THAT REPLACED THE "Not understood" BOX (James, 2026-10-16).
            The words themselves are now dotted-underlined in the bar; this says HOW
            MANY so a word scrolled out of view above the 40vh cap is still accounted
            for. It renders only when there is something to count — a persistent
            "0 not understood" would be the noise the box was removed for. */}
        {state.unrecognized.length > 0 && (
          <span
            className="rounded-full border border-dashed border-border-base px-2 py-0.5 text-micro text-content-muted"
            data-testid="capture-unrecognized-count"
            title={state.unrecognized.join(", ")}
          >
            <b className="text-content-strong">{state.unrecognized.length}</b> not
            understood
          </span>
        )}
        {/* ⚠️ A BUTTON, BECAUSE THE COUNT HAS TO ANSWER "WHICH ONES". Ruled
            2026-10-14: hovering or clicking the pill highlights the rows it counts.
            James read "2 needed" with nothing highlighted and had to guess. */}
        <button
          type="button"
          className={`rounded-full border px-2 py-0.5 text-micro ${
            needed
              ? "border-[rgba(224,168,74,0.55)] text-[rgb(224,168,74)]"
              : "border-border-subtle text-content-muted"
          }`}
          data-testid="capture-needed-pill"
          data-lit={pillLit ? "true" : "false"}
          aria-label={
            needed
              ? `${needed} row${needed === 1 ? "" : "s"} still needed`
              : "nothing needed"
          }
          onMouseEnter={() => setPillHover(true)}
          onMouseLeave={() => setPillHover(false)}
          onFocus={() => setPillHover(true)}
          onBlur={() => setPillHover(false)}
          onClick={() => setPillPinned((v) => !v)}
        >
          <b>{needed}</b> needed
        </button>
      </div>

      {!reviewing && (
        <>
          {/* column header — prototype `:414`. ⚠️ `AI ASSIST` is a LABEL in the
              prototype and nothing more; this slice makes no model call, so the label
              would be a claim. It reads RULES, which is what the pane does. */}
          <div className="flex items-center justify-between border-b border-border-subtle pb-1 text-micro uppercase tracking-wide text-content-subtle">
            <span>Order capture</span>
            <span data-testid="capture-assist-label">RULES</span>
          </div>

          {/* ⚠️ TWO COLUMNS, BY RULING (2026-10-13), AND NO SCROLL CONTAINER.
              Ten rows in one column do not fit above the bar at 800px tall, so the
              pane grew a scrollbar and auto-scrolled the focused row out of view —
              James watched a captured row disappear. Two columns of five fit, which
              is why the grid and the no-scrolling rule are one change.

              ⚠️ `items-start` SO A SHORT COLUMN DOES NOT STRETCH, and `min-w-0` on
              each column so a long value wraps instead of widening the grid past
              the bar. */}
          <div
            className="grid grid-cols-2 items-start gap-x-3 gap-y-1"
            data-testid="capture-rows"
          >
            {[cols.left, cols.right].map((column, ci) => (
              <div
                key={ci}
                className="flex min-w-0 flex-col gap-1"
                data-testid={`capture-column-${ci === 0 ? "left" : "right"}`}
              >
                {column.map((r) => (
                  <div
                    key={r.row_id}
                    data-testid={`capture-row-${r.row_id}`}
                    data-state={r.state}
                    // ⚠️ HOVER LIGHTS THE SPAN; THE CARET LIGHTS THE ROW. Two
                    // directions, two devices, and they can be true at once — see
                    // `mirror-spans.ts` for why the pointer cannot reach a span.
                    {...(hoveredFields.length > 0 &&
                    (r.field_ids ?? []).some((f) => hoveredFields.includes(f))
                      ? { "data-hovered": "true" }
                      : {})}
                    onMouseEnter={() => setHoveredFields(r.field_ids ?? [])}
                    onMouseLeave={() => setHoveredFields([])}
                    {...((caretFieldIds ?? []).length > 0 &&
                    (r.field_ids ?? []).some((f) => (caretFieldIds ?? []).includes(f))
                      ? { "data-caret": "true" }
                      : {})}
                    {...((r.missing_field_ids ?? []).length > 0
                      ? { "data-missing": "true" }
                      : {})}
                    {...((amber || pillLit) &&
                    (r.missing_field_ids ?? []).length > 0
                      ? { "data-amber": "true" }
                      : {})}
                    /* ⚠️ THE AMBER COMES FROM THE ROW'S OWN MISSING LIST, NOT FROM
                       ITS STATE. The server only promotes a row to `needed` after a
                       done signal, and a PARTIAL row (something captured, something
                       missing — James's Service row) never reaches that state at
                       all. Reading the list colours exactly the rows the pill
                       counts, which is the ruling. */
                    className={`flex items-start gap-2 rounded-base border px-2 py-1.5 ${
                      (amber || pillLit) && (r.missing_field_ids ?? []).length > 0
                        ? ROW_CLASS.needed
                        : (ROW_CLASS[r.state] ?? ROW_CLASS.not_mentioned)
                    } ${
                      // ⚠️ THE CARET'S END OF THE LINK. Added rather than replacing the state
                      // colour, because a row can be amber AND be the one the caret is in.
                      (caretFieldIds ?? []).length > 0 &&
                      (r.field_ids ?? []).some((f) => (caretFieldIds ?? []).includes(f))
                        ? ROW_CARET_CLASS
                        : ""
                    }`}
                  >
                    <span
                      aria-hidden
                      className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px] ${
                        MARK_CLASS[r.state] ?? MARK_CLASS.not_mentioned
                      }`}
                    >
                      {r.state === "done" ? "✓" : ""}
                    </span>
                    <div className="min-w-0">
                      <div className="text-micro uppercase tracking-wide text-content-subtle">
                        {r.label}
                      </div>
                      <div
                        className={`text-body-sm ${
                          r.state === "done"
                            ? "text-content-strong"
                            : "italic text-content-muted"
                        }`}
                      >
                        {valueText(r.state, r.value)}
                      </div>
                      {r.secondary_value ? (
                        <div className="text-micro text-content-muted">
                          {r.secondary_value}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* numbered picks — the prototype's `pending` mechanism (`:583`, `:606`, `:622`).
              ⚠️ ONE-BASED LABELS because the prototype's digit keys are 1..9. */}
          {state.pending_picks.map((p) => (
            <div
              key={p.field_id}
              data-testid={`capture-pick-${p.field_id}`}
              className="rounded-base border border-border-accent bg-accent-subtle p-2"
            >
              <div className="text-body-sm text-content-strong">
                {p.options.length} matches for “{p.phrase}”. Which one?
                {p.discriminator ? (
                  <span className="ml-1 text-micro text-content-muted">
                    ({p.discriminator})
                  </span>
                ) : null}
              </div>
              <ol className="mt-1 flex flex-col gap-1">
                {p.options.map(([value, label], i) => (
                  <li key={value}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void pick(p.field_id, i + 1)}
                      data-testid={`capture-pick-option-${p.field_id}-${i + 1}`}
                      className="flex w-full items-center gap-2 rounded-base px-2 py-1 text-left text-body-sm hover:bg-surface-sunken focus-ring-accent"
                    >
                      {/* ⚠️ THE NUMBER IS VISIBLE BECAUSE ⌘N IS ONLY AVAILABLE WHILE IT
                          IS, by ruling. A keyboard shortcut whose number is not on
                          screen is a shortcut nobody can use and a key nobody can
                          predict. Past 9 the number is dropped rather than shown
                          un-pressable — ⌘0 is not a pick and labelling it "10" would
                          promise a key that does nothing. */}
                      {i < 9 ? (
                        <kbd
                          data-testid={`capture-pick-number-${p.field_id}-${i + 1}`}
                          className="flex h-5 min-w-5 items-center justify-center rounded-[4px] border border-border-base px-1 text-micro text-content-muted"
                        >
                          {i + 1}
                        </kbd>
                      ) : (
                        <span aria-hidden className="h-5 min-w-5" />
                      )}
                      <span className="min-w-0 flex-1">{label}</span>
                    </button>
                  </li>
                ))}
              </ol>
              {/* ⚠️ THE SHORTCUT IS ADVERTISED WHERE THE NUMBERS ARE, and this copy
                  WAS WRONG ON PRODUCTION for a round. It read "Typed digits go into
                  the text" — the ruling of 2026-10-12, superseded on 10-13 by "a
                  plain number picks". The behaviour changed and the sentence
                  telling the office the opposite stayed, which is worse than no
                  hint at all. Found by reading the pane in a real browser; no test
                  asserted the sentence, so nothing went red.

                  ⚠️ IT NO LONGER PROMISES WHAT HAPPENS TO OTHER NUMBERS. The old
                  copy made a blanket claim about digits; the rule is narrower than
                  a sentence this size can carry (see `pick-digit.ts`), and a
                  half-stated rule is what just misled everybody. */}
              <div className="mt-1 text-micro text-content-subtle" data-testid={`capture-pick-hint-${p.field_id}`}>
                Click, or type the number.
              </div>
            </div>
          ))}

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
          {/* ── finishing ──────────────────────────────────────────────────
              ⚠️ ALWAYS VISIBLE, BY RULING (2026-10-14). The only way to finish was
              to type the right phrase, and the phrase that most people would type —
              "approve" — was the one that did not work. A control that is always
              there cannot be the thing nobody found. */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              data-testid="capture-complete"
              disabled={busy}
              onClick={() => void doComplete()}
              /* ⚠️ THE PROTOTYPE'S SECONDARY `.btn`: a translucent white pill on the
                 glass. Same reasoning as the primary above — the overlay is written
                 in the prototype's literals, and a token pair chosen for platform
                 cards is what made the primary unreadable. */
              style={{
                background: "rgba(255,255,255,0.08)",
                color: "#f2f2f2",
                border: "1px solid rgba(255,255,255,0.22)",
                borderRadius: 999,
                padding: "7px 16px",
                fontSize: 14,
                cursor: busy ? "default" : "pointer",
                opacity: busy ? 0.6 : 1,
              }}
              className="outline-none focus-visible:ring-2 focus-visible:ring-[rgba(255,255,255,0.6)] focus-visible:ring-offset-2 focus-visible:ring-offset-[rgba(14,14,14,0.9)]"
            >
              {busy ? "Checking…" : "Complete order"}
            </button>
            {/* ⚠️ THE MISSING FIELDS ARE NAMED, not counted. "2 needed" is what sent
                James looking for which two. The labels come from the server's own
                missing set, so this sentence cannot name something the rows are not
                highlighting. */}
            <span
              className="text-micro text-content-subtle"
              data-testid="capture-still-need"
            >
              {amber && missingLabels.length > 0
                ? `Still need: ${missingLabels.join(", ").toLowerCase()}`
                : "Or type \u201cdone\u201d. \u2318\u21a9 also works."}
            </span>
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
          because those are the two things the office writes down. */}
      {approvedOrder && (
        <div className="flex flex-col gap-1" data-testid="capture-approved">
          {/* ⚠️ THE NUMBER IS A LINK, BY RULING (James, 2026-10-14): "the order
              number links to the order". He was reading SO-2026-0001 off the pane
              and then navigating to /ar/orders by hand to find it.

              ⚠️ IT DEGRADES TO TEXT WITHOUT AN ID RATHER THAN LINKING NOWHERE. An
              older server does not send `sales_order_id`, and an anchor to
              `/ar/orders/undefined` would land on a broken detail page — worse than
              the plain text it replaced, because it looks like it should work. */}
          {approvedOrder.id ? (
            <Link
              to={`/ar/orders/${approvedOrder.id}`}
              className="text-body-sm text-content-strong underline decoration-border-strong underline-offset-2 hover:decoration-current focus-ring-accent"
              data-testid="capture-approved-link"
            >
              Created {approvedOrder.number}
            </Link>
          ) : (
            <span className="text-body-sm text-content-strong">
              Created {approvedOrder.number}
            </span>
          )}
          <span className="text-micro tabular-nums text-content-muted">
            {money(approvedOrder.total)}
          </span>
        </div>
      )}
    </div>
  )
}
