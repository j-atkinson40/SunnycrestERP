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

import { writeStoredCaptureSession } from "@/contexts/opas-context"
import {
  choosePick,
  readCapture,
  setCaptureText,
  startCapture,
  type CapturePick,
  type CaptureState,
} from "@/services/opas-capture-service"
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
  if (args.missing > 0) {
    return `${args.missing} still needed — keep typing`
  }
  return "Nothing needed — say “that’s it”"
}

/** ⚠️ Per-state classes, named after the prototype's own selectors so a reader can find
 *  them in the source file. */
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

export function CapturePane({
  openingLine,
  sessionId: existingSessionId,
  onSessionStarted,
  text = "",
  onStatus,
  onRestoreText,
  pickRequest,
  onRestoreUnusable,
}: {
  /** Fed through extraction on start, per the prototype (`:568` calls `feed` at once). */
  readonly openingLine?: string
  /** ⚠️ WHEN PRESENT THE PANE RE-READS RATHER THAN STARTING. This is how a tuck survives:
   *  the pane is re-mounted and reconstructed from the server, not from client memory. */
  readonly sessionId?: string
  readonly onSessionStarted?: (id: string) => void
  /** ⚠️ WHAT IS IN THE BAR. The pane does not own this and has no field of its own —
   *  the bar is the only input, by ruling. */
  readonly text?: string
  /** Reports the placeholder, the picks and the capturing flag up to the bar. */
  readonly onStatus?: (s: EntryPaneStatus) => void
  /** ⚠️ RESTORES THE BAR AFTER A RELOAD. The server holds the full text; the bar is
   *  empty on a fresh mount, so the pane hands it back exactly once. Without it a
   *  reload would show every captured row above an empty bar, and the first keystroke
   *  would re-extract from one character and un-capture the whole order. */
  readonly onRestoreText?: (text: string) => void
  /** ⚠️ A PICK REQUESTED FROM THE BAR (⌘1..9), as a counter-stamped value so the same
   *  option chosen twice still fires. A bare `{field_id, index}` object would be
   *  compared by identity and the second identical press would be a no-op. */
  readonly pickRequest?: { readonly fieldId: string; readonly index: number; readonly nonce: number }
  /** ⚠️ THE RESTORED SESSION CANNOT BE USED — CLOSE THIS PANE.
   *
   *  Called when a pane restored from `sessionStorage` either fails to read or comes
   *  back in a status that is not an order in progress. The pane must GO, not sit
   *  there showing an error: it is an ENTRY pane, so while it exists it is the front
   *  pane, which puts the bar in entry mode, which means a typed opening phrase is
   *  routed into this dead session instead of opening a new order. The tab becomes
   *  permanently unable to start one.
   *
   *  ⚠️ MEASURED IN A REAL BROWSER, 2026-10-13, against a stale stored id: the pane
   *  rendered "That order is no longer on the server", the id cleared itself, and
   *  typing "Order for hopkins" opened nothing — for as long as the tab lived.
   *  `sessionStorage` survives a reload and dies only with the tab, which is why
   *  James's hard refreshes never cleared it and why a NEW TAB would have worked. */
  readonly onRestoreUnusable?: (carryText: string) => void
}) {
  const [state, setState] = useState<CaptureState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [inFlight, setInFlight] = useState(false)
  // ⚠️ A REF, NOT STATE. Two StrictMode mounts would otherwise start two sessions, and
  // the second would orphan the first — a half-typed order nobody can reach.
  const started = useRef(false)
  // ⚠️ ONE SEQUENCER PER PANE INSTANCE, created once. Inside the render body it would be
  // rebuilt every keystroke, `applied` would reset to 0, and every response would be
  // accepted — the sequencer would be present, consulted, and useless, which is worse
  // than absent because it reads as handled.
  const seqRef = useRef(createSequencer())
  const restored = useRef(false)
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
  const onRestoreTextRef = useRef(onRestoreText)
  const onRestoreUnusableRef = useRef(onRestoreUnusable)
  const textRef = useRef(text)
  onSessionStartedRef.current = onSessionStarted
  onRestoreTextRef.current = onRestoreText
  onRestoreUnusableRef.current = onRestoreUnusable
  // ⚠️ THE LATEST TEXT, FOR THE CARRY-ACROSS. The start effect does not depend on
  // `text`, so it would otherwise close over whatever was in the bar at mount —
  // which is "" — and the director's words would be lost on recovery.
  textRef.current = text

  useEffect(() => {
    if (started.current) return
    started.current = true
    const run = async () => {
      try {
        const s = existingSessionId
          ? await readCapture(existingSessionId)
          : await startCapture(openingLine)
        if (!mounted.current) return
        // ⚠️ A RESTORED SESSION THAT IS NOT AN ORDER IN PROGRESS MUST NOT HOLD THE
        // BAR. `abandoned` is finished with; keeping its pane in front would block
        // every new order in this tab, exactly as a failed read does.
        // `capturing` and `review` are both live things to look at and are kept.
        if (existingSessionId && s.status === "abandoned") {
          writeStoredCaptureSession(null)
          onRestoreUnusableRef.current?.(textRef.current)
          return
        }
        setState(s)
        if (!existingSessionId) onSessionStartedRef.current?.(s.session_id)
        // ⚠️ ONCE, AND ONLY WHEN THERE IS A RECORD. `full_text === null` means this
        // session has no whole-text record at all (it was captured line-by-line), and
        // handing `""` to the bar in that case would be indistinguishable from the
        // director having cleared it — so the check is `!== null`, not truthiness.
        if (!restored.current && s.full_text !== null) {
          restored.current = true
          onRestoreTextRef.current?.(s.full_text)
        }
      } catch {
        if (!mounted.current) return
        // ⚠️ A STALE RESTORED ID CLEARS ITSELF. If this mount was a restore and the server
        // no longer has that session, carrying the id forward would resurrect a ghost pane
        // on every reload. The wording distinguishes the two causes, because "could not
        // start" on a restore would send someone looking for the wrong fault.
        if (existingSessionId) {
          // ⚠️ CLEAR THE ID **AND** CLOSE THE PANE. Clearing alone was the defect:
          // the next reload was clean, but THIS tab kept a dead entry pane in front
          // for as long as it lived, so no new order could ever open in it. The
          // error text is no longer rendered because there is no pane to render it
          // in — the recovery is to carry the director's words into the bar and let
          // them open a real order, which is more use than a red line.
          writeStoredCaptureSession(null)
          onRestoreUnusableRef.current?.(textRef.current)
        } else {
          setError("Could not start the capture")
        }
      }
    }
    void run()
    // ⚠️ NO CLEANUP, AND NO CALLBACK DEPENDENCIES. Both were the bug: the cleanup
    // cancelled a start that was still needed, and the callback dependency was what
    // made the cleanup run at all.
  }, [existingSessionId, openingLine])

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
    reviewing: liveReviewing,
  })
  useEffect(() => {
    onStatus?.({
      placeholder,
      picks: livePicks,
      capturing: state !== null && state.status === "capturing",
      ready: state !== null,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeholder, livePicks, state?.status, state !== null])

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
  const needed = state.missing.length
  const reviewing = state.status === "review"

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
        <span
          className={`rounded-full border px-2 py-0.5 text-micro ${
            needed
              ? "border-[rgba(224,168,74,0.55)] text-[rgb(224,168,74)]"
              : "border-border-subtle text-content-muted"
          }`}
          data-testid="capture-needed-pill"
        >
          <b>{needed}</b> needed
        </span>
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
                    className={`flex items-start gap-2 rounded-base border px-2 py-1.5 ${
                      ROW_CLASS[r.state] ?? ROW_CLASS.not_mentioned
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
              {/* ⚠️ THE SHORTCUT IS ADVERTISED WHERE THE NUMBERS ARE. ⌘ and not plain
                  digits: a bare "3" is text the director may be typing — a grave
                  depth, a vault size, a time — and stealing it would make numbers
                  untypable while a question is open. */}
              <div className="mt-1 text-micro text-content-subtle" data-testid={`capture-pick-hint-${p.field_id}`}>
                Click, or ⌘ and the number. Typed digits go into the text.
              </div>
            </div>
          ))}

          {/* ⚠️ A CONFLICT IS NOT "NOT UNDERSTOOD", AND IT GETS ITS OWN BLOCK ABOVE
              THAT ONE. The extractor read both phrases correctly; the combination is
              what the vault does not offer. Showing it among the unreadable text
              would tell the director their words were wrong, when what is wrong is
              the pairing — and it is ranked higher because it is the one of the two
              that names a decision only they can make.

              ⚠️ IT NAMES WHAT IS AVAILABLE. "Not available on this vault" with no
              alternatives is a dead end; the permitted list is what turns the
              message into a next step. */}
          {state.conflicts.length > 0 && (
            <div
              className="rounded-base border border-[rgba(224,168,74,0.55)] bg-[rgba(224,168,74,0.08)] p-2"
              data-testid="capture-conflicts"
            >
              <div className="text-micro uppercase tracking-wide text-[rgb(224,168,74)]">
                Not available on this vault
              </div>
              <ul className="mt-1 flex flex-col gap-1">
                {state.conflicts.map((c) => (
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

          {/* ⚠️ UNRECOGNIZED TEXT IS VISIBLE AND ATTRIBUTED. E1's never-dropped rule is
              only worth anything if the director can see what was not understood. */}
          {state.unrecognized.length > 0 && (
            <div
              className="rounded-base border border-dashed border-border-base p-2"
              data-testid="capture-unrecognized"
            >
              <div className="text-micro uppercase tracking-wide text-content-subtle">
                Not understood
              </div>
              <ul className="mt-1 flex flex-col gap-0.5">
                {state.unrecognized.map((u, i) => (
                  <li
                    key={`${u}-${i}`}
                    className="text-body-sm text-content-muted"
                    data-testid="capture-unrecognized-item"
                  >
                    {u}
                  </li>
                ))}
              </ul>
            </div>
          )}

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
        </>
      )}

      {/* review stage — prototype `:389-404`. ⚠️ READ-ONLY: no Approve control, by
          ruling (E5). A disabled button would read as a feature that exists. */}
      {reviewing && (
        <div data-testid="capture-summary" className="flex flex-col gap-2">
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
          <p className="text-micro text-content-subtle" data-testid="capture-no-approve">
            Read-only. Creating the sales order is a separate build.
          </p>
        </div>
      )}
    </div>
  )
}
