/**
 * Opas — sphere, veil, command line, and the glass panes a request opens.
 *
 * ⚠️ MEASURED FROM `docs/prototypes/2026-10-01-opas-overlay.html` (93177 bytes, md5
 * a52a1e95153bd5c686b88d0acffc31e6), not chosen. Every value below that matches the
 * prototype is marked; where this differs, the reason is stated.
 *
 * Verified from the prototype's own source, not inferred:
 *   orb.addEventListener('click', open)
 *   veil.addEventListener('pointerdown', tuck)      <- pointerdown, not click
 *   Escape -> pending ? cancelPick() : textarea ? input.focus() : tuck()
 *   tuck() -> veil off, wins.forEach(w => w.el.classList.add('tucked'))   panes STAY
 *   open() -> wins.forEach(w => w.el.classList.remove('tucked'))         panes RETURN
 *   orb.classList.toggle('session', wins.length > 0)
 * and in its visible UI: "Esc — tuck everything away; it comes back where you left it".
 *
 * ⚠️ NOT BUILT, DELIBERATELY: the prototype binds Cmd/Ctrl+K to toggle itself. This app
 * binds Cmd+K to the command bar, and taking it would change existing command-bar
 * behaviour. The sphere click is the entrance. Logged in STATE as James's call after the walk.
 *
 * ⚠️ ADMIN-ONLY, via the EXISTING role check (`useAuth().isAdmin`). No new flag mechanism.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { useAuth } from "@/contexts/auth-context"
import { useOpas, type OpasPaneKind } from "@/contexts/opas-context"
import {
  abandonCapture,
  answerWhy,
  fetchCapturePreferences,
  fetchVocabulary,
  setCapturePickModifier,
  type CaptureState,
} from "@/services/opas-capture-service"
import { CapturePane, ENTRY_PLACEHOLDER, type EntryPaneStatus } from "./CapturePane"
import {
  CaptureMirror,
  MIRROR_BOX,
  MIRROR_TEXTAREA_EXTRA,
  MirrorStack,
  useMirrorSync,
} from "./CaptureMirror"
import { acceptGhost, completionFor, type VocabTerm } from "./ghost"
import { sameEntryStatus } from "./entry-status-guard"
import { fieldsAtCaret } from "./mirror-spans"
import {
  CAPTURE_START,
  isCatalogRequest,
  routeResolution,
  startsCaptureWithParty,
} from "./opas-routing"
import { isEntryPane } from "./pane-mode"
import { anchoredSlots, RIGHT_ANCHOR, TOP_ANCHOR } from "./pane-placement"
import { isCloseRequest } from "./close-request"
import {
  REPLY_FADE_MS,
  REPLY_GAP_ABOVE_BAR,
  matchAnswer,
  type Reply,
  type ReplyKind,
  type ReplyOption,
} from "./reply"
import { contextIntent, type ContextIntent } from "./context-phrases"
import { EXTRACT_DEBOUNCE_MS } from "./capture-sequence"

import { consumePickDigit } from "./pick-digit"
import {
  DEFAULT_PICK_MODIFIER,
  GuidedQuestion,
  MODIFIER_GLYPH,
  PILL_ACT_REVIEW,
  STACK_BELOW_PX,
  paneBottomPx,
  questionTakesNumbers,
} from "./GuidedQuestion"
import type { PickModifier } from "./GuidedQuestion"
import {
  DONE_HINT,
  DONE_PILL_LABEL,
  DONE_QUESTION,
  IDLE_HINT,
  IDLE_PILL_LABEL,
  IDLE_QUESTION,
  PILL_ACT_NEW_ORDER,
} from "./opas-prompts"
import { shortcutRequest } from "./shortcut-request"
import { resolvePhrase } from "@/services/opas-catalog-service"
import {
  askOrderList,
  type CemeteryDetail,
  type CustomerDetail,
  type OrderListSnapshot,
  type OrderPick,
  type SalesOrderSummary,
} from "@/services/order-list-service"
import { ProductListPane } from "./ProductListPane"
import { ProductPane } from "./ProductPane"
import { OrderListPane } from "./order-list/OrderListPane"
import {
  isOrderListPhrase,
  isOrderRefinement,
  opensRulebook,
} from "./order-list/order-list-routing"
import { CemeteryPane } from "./order-list/CemeteryPane"
import { RulebookPane } from "./order-list/RulebookPane"
import { CustomerPane } from "./order-list/CustomerPane"
import { SalesOrderPane } from "./order-list/SalesOrderPane"

/** How long an approved pane stays on screen before it closes itself.
 *
 * ⚠️ LONG ENOUGH TO READ AN ORDER NUMBER, SHORT ENOUGH NOT TO BLOCK THE NEXT ORDER.
 * An entry pane holds the bar in entry mode while it is in front, so this is a
 * bounded window rather than "until dismissed". Typing closes it sooner.
 */
const APPROVED_VISIBLE_MS = 6000

/** The prototype's glass, as one object so panes and the command line cannot drift apart. */
const GLASS: React.CSSProperties = {
  background:
    "linear-gradient(160deg,rgba(50,50,50,.48) 0%,rgba(22,22,22,.42) 55%,rgba(14,14,14,.5) 100%)",
  backdropFilter: "blur(26px) saturate(1.5)",
  WebkitBackdropFilter: "blur(26px) saturate(1.5)",
  boxShadow:
    "inset 0 1px 0 rgba(255,255,255,.16),inset 0 0 0 1px rgba(255,255,255,.06)," +
    "inset 0 -1px 0 rgba(0,0,0,.45),0 34px 80px rgba(0,0,0,.55),0 10px 26px rgba(0,0,0,.38)",
}

/** The command line's width, and therefore an entry pane's.
 *
 * ⚠️ ONE CONSTANT, USED BY BOTH, SO "THE SAME WIDTH AS THE BAR" IS TRUE BY
 * CONSTRUCTION rather than by two literals agreeing. They were two literals — 600
 * for the bar, 390 for the pane — which is how the pane came to be visibly narrower
 * than the thing it grows out of.
 */
export const BAR_WIDTH = "min(600px, calc(100vw - 48px))"

/** An info pane is its own width; it does not grow from the bar. */
export const INFO_WIDTH = "min(390px, calc(100vw - 32px))"

/** The order list is a wide list. A product pane stays at INFO_WIDTH. */
export const ORDER_LIST_WIDTH = "min(37rem, calc(100vw - 32px))"

/** The same two widths as NUMBERS, for the first-free-space placement arithmetic.
 *
 * ⚠️ A SECOND SPELLING OF THE SAME MEASUREMENT, AND THE DUPLICATION IS DELIBERATE RATHER
 * THAN LAZY. The CSS strings above are what the browser lays out; `pane-placement` needs
 * pixels before layout exists, so it cannot measure them. The alternative — building the
 * CSS from the numbers — would convert `37rem` into `592px` and silently drop the one
 * property rem has, which is that it follows the reader's own font size.
 *
 * ⚠️ SO THE ORDER-LIST NUMBER ASSUMES A 16px ROOT, AND HERE IS WHAT GOES WRONG WHEN IT IS
 * NOT. A reader at 20px root gets a 740px order list while placement reserves 592px, so
 * the next pane is placed ~148px too far right and OVERLAPS it. That is a pane the
 * director drags apart, not a broken layout, and it is the only consequence — which is
 * why this is stated rather than solved with a layout round trip.
 */
export const INFO_WIDTH_PX = 390
export const ORDER_LIST_WIDTH_PX = 37 * 16

/** The clamp in both CSS strings: never wider than the viewport less 32px. */
export function paneWidthPx(kind: OpasPaneKind, stageWidth: number): number {
  const nominal = kind === "order-list" ? ORDER_LIST_WIDTH_PX : INFO_WIDTH_PX
  return Math.min(nominal, Math.max(0, stageWidth - 32))
}

/** The stage's width, re-read on resize so placement follows the window. */
function useStageWidth(): number {
  const [width, setWidth] = useState(() =>
    typeof window === "undefined" ? 1440 : window.innerWidth,
  )
  useEffect(() => {
    const apply = () => setWidth(window.innerWidth)
    apply()
    window.addEventListener("resize", apply)
    return () => window.removeEventListener("resize", apply)
  }, [])
  return width
}

const ORDER_TRY = "Try: Hopkins orders this month · going out Friday"

/** What Opas says when neither the rules nor the model could place a phrase.
 *
 * ⚠️ ONE LINE, AND NOTHING OPENS, BY RULING (James, 2026-10-23): "A miss should be one
 * honest line above the bar, something like 'I'm not sure what you're asking yet', not a
 * pane full of every vault."
 *
 * ⚠️ IT DOES NOT QUOTE THE PHRASE BACK. The old copy was `Nothing matched “…”.` beside a
 * pane of the whole catalogue — the quotation read as "that is not a thing", which is a
 * claim about the words rather than about Opas. The director can see what they typed; it
 * is still in the bar. */
const NOT_SURE = "I'm not sure what you're asking yet."
const ORDER_CHANGE = 'Say it: "only Hopkins", "last month", "not invoiced"'

function useNarrowScreen(): boolean {
  const [narrow, setNarrow] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 640px)").matches,
  )
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)")
    const apply = () => setNarrow(mq.matches)
    apply()
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [])
  return narrow
}

export function OpasHost() {
  const { isAdmin } = useAuth()
  const opas = useOpas()
  // ⚠️ A TEXTAREA SINCE 2026-10-13, NOT AN INPUT. An `<input>` can only scroll, so a
  // long order ran off the left-hand edge and the director could not see the start of
  // what they had typed — James's walk note. A textarea wraps; the effect below grows
  // it to fit so nothing is ever hidden.
  const inputRef = useRef<HTMLTextAreaElement>(null)
  /** ⚠️ THE BAR'S MEASURED HEIGHT, so an entry pane can sit exactly ON it.
   *
   *  Ruled: the entry pane anchors directly on top of the Opas bar at the bar's
   *  width. A hardcoded offset was what shipped (`bottom: 96` against a bar that is
   *  nearer 46px tall) and it left the pane floating above and narrower than the
   *  bar. The bar also GROWS when it has a `said` line, so the offset cannot be a
   *  constant without going wrong whenever it does.
   *
   *  ⚠️ MEASURED WITH A ResizeObserver, not read once. The bar's height changes with
   *  its content, and a single read at mount would be correct exactly until the
   *  first time it mattered. */
  const barRef = useRef<HTMLDivElement>(null)
  /** ⚠️ THE MIRROR'S OWN NODE, so its scroll can be driven from the textarea's. */
  const mirrorRef = useRef<HTMLDivElement>(null)
  /** ⚠️ WHERE THE CARET IS, SO THE PANE CAN LIGHT THE ROW IT IS INSIDE. Tracked from
   *  the events that can move it — typing, clicking and arrowing — rather than polled,
   *  because a poll would either lag the caret or run forever. */
  const [caret, setCaret] = useState<number | null>(null)
  /** ⚠️ FETCHED ONCE WHEN CAPTURE OPENS, never per keystroke — see `fetchVocabulary`.
   *  Held on the host rather than the pane because the BAR is what completes. */
  const [vocab, setVocab] = useState<readonly VocabTerm[]>([])
  const [barH, setBarH] = useState(0)
  /** How much room the guided question + pills take above the bar.
   *
   *  ⚠️ THE CAPTURE PANE'S ANCHOR READS THIS, and that is the whole fix for what James
   *  saw: the pane was at `bottom: 24 + barH` — the bar's top edge — and the pills sit
   *  12px above that edge, so the pills were drawn over the pane's footer, covering
   *  "Complete order" and its hint. Measured rather than assumed because the row wraps
   *  on content as well as width. */
  const [guidedH, setGuidedH] = useState(0)

  // ── the pill-pick modifier, a per-user preference (James, 2026-10-28) ───────────
  //
  // ⚠️ READ ONCE PER MOUNT, NOT PER QUESTION. It is a preference, not session state,
  // and threading it through the capture read would have meant adding a field to
  // `EntryPaneStatus` — whose equality guard must then compare it, which is the exact
  // gap that turned CI red on 2026-10-27 when seven new fields went uncompared.
  //
  // ⚠️ AND THE DEFAULT IS THE PRE-RULING BEHAVIOUR, so the window before the read
  // lands is indistinguishable from how the bar worked yesterday.
  const [pickModifier, setPickModifier] = useState<PickModifier>(DEFAULT_PICK_MODIFIER)
  const [pickGlyph, setPickGlyph] = useState<string>(MODIFIER_GLYPH[DEFAULT_PICK_MODIFIER])
  useEffect(() => {
    let live = true
    void fetchCapturePreferences().then((p) => {
      if (!live) return
      setPickModifier(p.pick_modifier)
      setPickGlyph(p.pick_modifier_glyph)
    })
    return () => {
      live = false
    }
  }, [])
  /** A row the office clicked, whose question is shown instead of the next one.
   *
   *  ⚠️ IT IS CLEARED THE MOMENT THAT FIELD IS ANSWERED, not on a timer and not on the
   *  next render. The prototype does the same — `if(S.focus===f)S.focus=null` inside
   *  `setField` — because a focus that outlived its answer would hold the pane on a
   *  question the office had just finished with. */
  const [focusField, setFocusField] = useState<string | null>(null)
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  /** ⚠️ WHAT EACH ENTRY PANE IS DOING, keyed by pane id. The bar renders the FRONT
   *  pane's placeholder and settles the FRONT pane's picks, so it needs the status of
   *  whichever pane is in front — not of the last one to report. */
  const [entryStatus, setEntryStatus] = useState<Record<string, EntryPaneStatus>>({})
  /** ⌘1..9, as a counter-stamped intent. The pane turns it into the call. */
  const [pickRequest, setPickRequest] = useState<
    Record<string, { fieldId: string; index: number; nonce: number }>
  >({})
  const pickNonce = useRef(0)
  /** A pill answered — by click or by ⌥-digit — as a counter-stamped intent, the same
   *  shape as `pickRequest`. The pane turns it into the call because the pane owns the
   *  session; the pills render up here because they belong above the bar. */
  const [answerRequest, setAnswerRequest] = useState<
    Record<string, { fieldId: string; value: string; nonce: number }>
  >({})
  const answerNonce = useRef(0)
  // ⚠️ PANE IDS THAT HOLD A CREATED ORDER. The opening effect reads this so the next
  // phrase closes the receipt instead of being typed into a finished order.
  const approvedPanes = useRef<Set<string>>(new Set())
  /**
   * ⚠️ TRUE FROM AN APPROVAL UNTIL THE OFFICE DOES THE NEXT THING. The Opas pane's
   * DONE state (James, 2026-10-28 clause 2) outlives the capture session that caused
   * it — `onApproved` closes that pane and opens the order's own — so the state cannot
   * be read back from a session and has to be remembered here.
   *
   * ⚠️ AND IT IS CLEARED BY TYPING OR BY ACTING, NOT BY A TIMER. The pills are
   * actionable, and a receipt on a fuse is a receipt the office can lose mid-reach.
   */
  const [justApproved, setJustApproved] = useState(false)
  // ⚠️ A COUNTER-STAMPED REQUEST, NOT A BOOLEAN, for the same reason `pickRequest`
  // is: the pane must act on the SECOND Enter as well as the first, and a bare flag
  // would be compared by value and the repeat would be a no-op.
  const [completeRequest, setCompleteRequest] = useState<Record<string, number>>({})
  /** ⚠️ A COUNTER PER ORDER PANE, the same shape as `completeRequest` above — one
   *  mechanism for "the bar is asking the front pane to act", not two. Keyed by ORDER id
   *  rather than pane id because the phrase names the order, and the pane holding it is
   *  an implementation detail of where it is on screen. */
  const [undoRequest, setUndoRequest] = useState<Record<string, number>>({})
  const completeNonce = useRef(0)
  const narrow = useNarrowScreen()
  const stageWidth = useStageWidth()

  /**
   * ⚠️ FIELD-BY-FIELD COMPARISON, AND IT IS LOAD-BEARING RATHER THAN AN OPTIMISATION.
   * `CapturePane` rebuilds its status object on every render (it contains a derived
   * string and an array), so storing it unconditionally is
   * `setState -> child re-render -> new object -> setState` — an infinite loop that
   * renders as a frozen tab, not as an error. Compared here because this is the side
   * that stores it; the pane says so too, at the other end.
   */
  const reportStatus = useCallback((paneId: string, next: EntryPaneStatus) => {
    setEntryStatus((prev) => {
      const cur = prev[paneId]
      // ⚠️ THIS GUARD SWALLOWED A WHOLE FEATURE, AND THE SHAPE OF THE MISTAKE IS
      // WORTH MORE THAN THE FIX. It compared four of the status's fields. Three more
      // were added for the tinting — `spans`, `spansForText`, `hoveredFieldIds` —
      // and a status that differed ONLY in those was judged equal and dropped. So
      // hovering a pane row set the state, reported it, and the report was discarded
      // one function later: every piece worked and the feature did not.
      //
      // ⚠️ IT IS A HAND-MAINTAINED LIST THAT MUST TRACK A TYPE, which is the real
      // defect — adding a field to `EntryPaneStatus` silently fails to propagate
      // unless somebody also edits this. `entry-status-guard.test.ts` now iterates
      // the type's own fields and fails when one of them cannot get through, so the
      // NEXT field added is a failing test rather than a silent feature.
      if (cur !== undefined && sameEntryStatus(cur, next)) return prev
      return { ...prev, [paneId]: next }
    })
  }, [])

  /** ⚠️ THERE IS NO RESTORE-ON-MOUNT, BY RULING (2026-10-13), AND THIS COMMENT
   *  STANDS WHERE IT WAS.
   *
   *  Opening Opas used to re-create a capture pane from a `sessionStorage` id. That
   *  is removed: **opening Opas never shows an order.** The pane appears only once
   *  the typed text is recognised as one.
   *
   *  ⚠️ IT WAS ALSO THE DEFECT THAT COST THREE WALK ROUNDS. A restored pane raises
   *  itself to front, which puts the bar in entry mode, which made the opening
   *  effect return before it looked at the phrase — so a tab that had ever started
   *  an order could never start another. The fix that shipped closed an UNUSABLE
   *  restored pane; this ruling removes the restore itself, which is the smaller
   *  mechanism and the one that cannot have the bug.
   *
   *  ⚠️ THE SERVER ROWS ARE KEPT (`abandon` marks, never deletes), so nothing is
   *  destroyed by not reading them back. What is gone is the client's habit of
   *  re-opening one unasked.
   */

  /** ⚠️ ONE VOICE, IN ONE PLACE (James, 2026-10-20). This replaced
   *  `said: string | null`. A bare string could only ever be a sentence, so a question
   *  that needed choices had nowhere to put them and they went into a floating pane —
   *  which is the thing the ruling retires. The `kind` is what decides whether the line
   *  fades, and `options` is what the list above the bar renders. */
  const [reply, setReply] = useState<Reply | null>(null)
  /** What each option DOES, keyed by option id.
   *
   *  ⚠️ A REF, NOT STATE, AND IT HOLDS CLOSURES. Putting functions in `reply` would make
   *  every `say()` a new object identity, and the fade effect keys off that identity —
   *  so a re-render that rebuilt the same reply would restart the fade timer. */
  const answerActions = useRef<Record<string, () => void>>({})
  /** The orders the open panes have read, keyed by order id.
   *
   *  ⚠️ IT IS A REF AND NOT STATE, because nothing RENDERS from it — only the reply
   *  phrases read it, at the moment the director asks. In state, every order pane
   *  finishing its fetch would re-render the whole host. */
  const orderFacts = useRef<Record<string, SalesOrderSummary>>({})
  /** Customers as read, by id, so the bar can answer from one without re-reading. */
  const customerFacts = useRef<Record<string, CustomerDetail>>({})
  /** Cemeteries as read, same reason. */
  const cemeteryFacts = useRef<Record<string, CemeteryDetail>>({})

  /**
   * The bar gets the cursor back. James's first rule of 2026-10-20: "After any Opas
   * action (pane opens, pick resolved, click inside a pane, pane closed), focus returns
   * to the bar's input."
   *
   * ⚠️ IT IS THE PROTOTYPE'S OWN LAST LINE OF `choose`, quoted:
   * `function choose(i){ … p.then(o); show([{t:o.name}]); input.focus()}`. So this is
   * recovering a behaviour the prototype had rather than inventing one.
   *
   * ⚠️ `preventScroll` BECAUSE THE BAR IS FIXED AT THE BOTTOM. Without it, focusing it
   * from a click higher up the page can scroll the document under the overlay.
   */
  const focusBar = useCallback(() => {
    inputRef.current?.focus({ preventScroll: true })
  }, [])

  /**
   * Opas speaks. The ONE place.
   *
   * ⚠️ `pendingPick` IS SET FROM THE OPTIONS, and that is not bookkeeping — it is what
   * keeps Escape's existing three-branch behaviour unchanged. `onEscape` cancels a
   * pending pick without tucking (the prototype's own order), and it reads that flag
   * from the context. Giving the reply its own separate "a question is outstanding" flag
   * would be a second mechanism for one fact, and Escape would then have to consult
   * both.
   */
  const say = useCallback(
    (
      kind: ReplyKind,
      text: string,
      options?: { readonly options: readonly ReplyOption[]; readonly act: Record<string, () => void> },
    ) => {
      answerActions.current = options?.act ?? {}
      setReply({ kind, text, ...(options ? { options: options.options } : {}) })
      opas.setPendingPick(options ? options.options.map((o) => o.id) : null)
    },
    [opas],
  )

  const hush = useCallback(() => {
    answerActions.current = {}
    setReply(null)
    opas.setPendingPick(null)
  }, [opas])

  /**
   * Answer the outstanding question by index.
   *
   * ⚠️ IT CLEARS THE QUESTION BEFORE ACTING, which is the fix for "the pane that stayed
   * open" in James's own words. The old pick lived in a pane, so choosing opened the
   * thing and left the list behind it; here the list IS the question and answering ends
   * it. Clearing first also means an action that itself says something (opening an
   * order acknowledges it) is not immediately overwritten by a stale clear.
   */
  /**
   * A reply fades unless it is a question. The prototype's own rule, quoted:
   *
   *     said.classList.add('on');
   *     if(!pending)saidTimer=setTimeout(()=>said.classList.remove('on'),4200)
   *
   * ⚠️ A QUESTION NEVER FADES, and that asymmetry is the whole of it: the director is
   * mid-answer, and a question that vanished after four seconds would take its options
   * with it. An acknowledgement and a miss both fade — "Opened Hart · SO-2026-0004" is
   * worth seeing once, not for the rest of the session.
   *
   * ⚠️ IT CLEARS ONLY THE REPLY IT WAS STARTED FOR. Keyed on the `reply` object
   * identity, so a reply that arrives during the window cancels the old timer with the
   * effect's own cleanup rather than being wiped by it four seconds later.
   */
  useEffect(() => {
    if (reply === null || reply.kind === "question") return
    const timer = window.setTimeout(() => setReply((cur) => (cur === reply ? null : cur)), REPLY_FADE_MS)
    return () => window.clearTimeout(timer)
  }, [reply])

  const answerOption = useCallback(
    (index: number) => {
      const options = reply?.options
      if (options === undefined) return
      const option = options[index]
      if (option === undefined) return
      const act = answerActions.current[option.id]
      hush()
      act?.()
      focusBar()
    },
    [reply, hush, focusBar],
  )


  // ⚠️ Escape at the document level, with the prototype's three branches. `onEscape` owns
  // the ordering; this only supplies what is focused and honours the verdict.
  useEffect(() => {
    if (!opas.isOpen) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return
      const active = document.activeElement as HTMLElement | null
      // ⚠️ THE BAR IS A TEXTAREA TOO SINCE IT LEARNED TO WRAP, so `onEscape` is told
      // which one is focused. Identity against the ref, not a testid lookup: the ref
      // is the bar by construction.
      const outcome = opas.onEscape(
        active?.tagName,
        active !== null && active === inputRef.current,
      )
      e.preventDefault()
      if (outcome === "refocused-input") inputRef.current?.focus()
      // ⚠️ ONLY WHEN IT ACTUALLY TUCKED. Escape has three branches and the other two
      // are not a close: cancelling a pending pick must not throw the order away,
      // and re-focusing the bar is not leaving at all. Ending the capture on every
      // Escape would make "never mind" destroy the order.
      if (outcome === "tucked") endEntryCaptures()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [opas])

  useEffect(() => {
    if (opas.isOpen) inputRef.current?.focus()
  }, [opas.isOpen])

  /**
   * ⚠️ CMD+K — THE ONE PIECE OF EXISTING COMMAND-BAR BEHAVIOUR JAMES AUTHORIZED CHANGING,
   * and only for users who can see the sphere.
   *
   * CAPTURE PHASE, and that is the mechanism rather than a detail. `CommandBarProvider`
   * listens for Cmd+K on `document` in the BUBBLE phase; for the same target, capture
   * listeners run first. So this sees the key, stops it, and the bar's handler never runs —
   * no flicker, and no edit to CommandBarProvider.
   *
   * ⚠️ MOUNTED ONLY WHEN `isAdmin && canRender`. For everyone else this effect does nothing
   * and Cmd+K is bit-for-bit unchanged — which is why the existing command-bar tests pass
   * unmodified.
   *
   * ⚠️ FOCUS STILL WINS: `canRender` is false while a Focus is open, so the listener is not
   * even attached and Cmd+K does nothing, exactly as the bar's own `if (focusIsOpen) return`
   * already guaranteed.
   */
  useEffect(() => {
    if (!isAdmin || !opas.canRender) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key.toLowerCase() !== "k") return
      if (!(e.metaKey || e.ctrlKey)) return
      if (e.altKey || e.shiftKey) return
      e.preventDefault()
      // ⚠️ stopImmediatePropagation, not stopPropagation: the bar's listener is on the SAME
      // target, so only the immediate form keeps it from running.
      e.stopImmediatePropagation()
      // The prototype: isOpen ? tuck() : open()
      if (opas.isOpen) opas.tuck()
      else opas.open()
    }
    document.addEventListener("keydown", onKeyDown, true)
    return () => document.removeEventListener("keydown", onKeyDown, true)
  }, [isAdmin, opas])

  /**
   * Drag, built the way the prototype's `wire(w)` does, with the differences named.
   *
   * SAME AS THE PROTOTYPE: left button only (`e.button !== 0`); interactive descendants
   * excluded; `setPointerCapture(e.pointerId)` rather than document listeners, so a fast
   * drag cannot escape the element; and a **4px dead zone** (`Math.hypot(...) < 4`) so a
   * click is not a drag.
   *
   * ⚠️ BINDS ON THE WHOLE PANE, matching the prototype's `el.addEventListener('pointerdown',
   * …)` where `el` is the `.win`. Round 2 bound it to the header only, because the dispatch
   * then required that; the requirement was withdrawn in round 3 in favour of the prototype.
   * `raise()` still runs on every pointerdown BEFORE the drag check, so clicking a button
   * inside a pane still brings it to front — which is the prototype's order too.
   *
   * ⚠️ BOUNDS: the pane cannot be dragged fully off screen. 80px of width and the full
   * header depth are kept on screen in every direction, so there is always something left
   * to grab. The prototype's anchoring code clamps with `Math.max(16, ...)`; I did not find
   * a clamp on its drag path, so this is stated as our requirement rather than as measured.
   */
  const dragStart = useCallback(
    (
      e: React.PointerEvent<HTMLDivElement>,
      id: string,
      placed: { x: number; y: number; anchored: boolean } | undefined,
      index: number,
    ) => {
      if (e.button !== 0) return
      // ⚠️ THE EXCLUSION IS WHAT MAKES WHOLE-PANE DRAGGING SAFE. Without it, clicking a
      // catalog row would start a drag instead of opening the product — the row is a
      // <button>, and `closest` catches a click on anything inside it too.
      //
      // ⚠️ IT MATCHES INTERACTIVE ROLES AS WELL AS TAGS SINCE 2026-10-23, AND THAT IS
      // JAMES'S WALK BUG. The selector listed TAGS only, and the order-list row is a
      // `div role="button"` — the ONLY such element in Opas, measured. So pointerdown on
      // a row fell through this guard, `setPointerCapture` below captured the pointer on
      // the PANE, and the browser then dispatched the `click` to the capturing element
      // instead of the row. `onOpen(row.id)` never ran. Nothing threw, which is why he
      // saw no error — the click simply went somewhere else.
      //
      // ⚠️ AND EVERY JSDOM TEST PASSED THROUGH IT, WHICH IS WHY IT REACHED HIM. jsdom
      // does not implement `setPointerCapture` — that is why the call below is optional
      // — so no capture happens, the click dispatches to the row, and the pane opens.
      // Measured four ways before the fix (bare click, full pointerdown/up/click, with a
      // 2px move, and after a refinement): all four opened the pane in jsdom. The gap is
      // structural, not an oversight in any one test.
      //
      // ⚠️ ROLES, NOT JUST THIS ONE ROLE, because the next `div role="link"` or
      // `role="option"` would land in the same hole. The question this asks is "did the
      // pointer go down on something interactive?", and a role is how a non-native
      // element answers it.
      const INTERACTIVE = [
        "button", "textarea", "input", "select", "a",
        '[role="button"]', '[role="link"]', '[role="option"]',
        '[role="tab"]', '[role="checkbox"]', '[role="switch"]',
        '[contenteditable="true"]',
      ].join(",")
      if ((e.target as HTMLElement).closest(INTERACTIVE) !== null) return
      const handle = e.currentTarget
      // ⚠️ OPTIONAL CALL, WHERE THE PROTOTYPE CALLS IT OUTRIGHT. A raw
      // `handle.setPointerCapture(...)` threw `TypeError: not a function` the moment a
      // pointerdown arrived from anywhere that had not stubbed it — and an UNCAUGHT
      // EXCEPTION INSIDE A POINTERDOWN HANDLER is exactly the "interaction never registers"
      // shape being investigated elsewhere: the handler dies partway and everything after it
      // silently does not happen. The prototype runs in one browser and can assume the API;
      // this runs wherever the app does.
      handle.setPointerCapture?.(e.pointerId)

      const rect = handle.getBoundingClientRect()
      const start = { px: e.clientX, py: e.clientY, x: placed?.x ?? rect.left, y: placed?.y ?? rect.top }
      let moved = false

      const onMove = (ev: PointerEvent) => {
        const dx = ev.clientX - start.px
        const dy = ev.clientY - start.py
        // ⚠️ THE DEAD ZONE. Without it, raising a pane by clicking its header would nudge it.
        if (!moved && Math.hypot(dx, dy) < 4) return
        moved = true
        const KEEP = 80
        const maxX = window.innerWidth - KEEP
        const maxY = window.innerHeight - rect.height > 0 ? window.innerHeight - KEEP : 0
        const x = Math.min(Math.max(start.x + dx, KEEP - rect.width), maxX)
        const y = Math.min(Math.max(start.y + dy, 0), maxY)
        opas.movePane(id, x, y)
      }
      const onUp = (ev: PointerEvent) => {
        handle.releasePointerCapture?.(ev.pointerId)
        handle.removeEventListener("pointermove", onMove)
        handle.removeEventListener("pointerup", onUp)
        handle.removeEventListener("pointercancel", onUp)
      }
      handle.addEventListener("pointermove", onMove)
      handle.addEventListener("pointerup", onUp)
      handle.addEventListener("pointercancel", onUp)
      void index
    },
    [opas],
  )

  /**
   * THE FRONT ENTRY PANE, which is what decides whether the bar is a request line or
   * an order's text field.
   *
   * ⚠️ FRONT, NOT "ANY OPEN ENTRY PANE". With two orders open, typing must go to the
   * one the director is looking at. `frontPaneId` is already the prototype's own
   * notion of which that is (`raise`), so this reuses it rather than inventing a
   * second idea of focus that could disagree with the shadow on the pane.
   */
  const frontPane = opas.panes.find((p) => p.id === opas.frontPaneId)
  const entryPane = frontPane !== undefined && isEntryPane(frontPane.kind) ? frontPane : undefined
  const entryMode = entryPane !== undefined
  const status = entryPane !== undefined ? entryStatus[entryPane.id] : undefined
  const entryValue = entryPane !== undefined ? (opas.entryText[entryPane.id] ?? "") : ""
  // ⚠️ THE MIRROR FOLLOWS WHICHEVER VALUE THE BAR IS SHOWING. The textarea is one
  // input with two jobs — an entry pane's order text, or the request line — and the
  // mirror has to track the same one or it would lay out the other.
  useMirrorSync(inputRef, mirrorRef, entryMode ? entryValue : text)

  // ⚠️ ONCE PER CAPTURE, AND ONLY WHILE CAPTURING. Fetching on mount would pull a
  // tenant catalog for every user who merely opens Opas; fetching per keystroke is
  // what the ruling forbids. The guard on `vocab.length` makes a second entry pane
  // reuse what the first already has.
  // ⚠️ FETCHED WHEN OPAS OPENS, NOT WHEN CAPTURE OPENS, AND THE ORDER MATTERS. The
  // opener now asks whether the words after "order" prefix a funeral home, so the
  // vocabulary has to be in hand BEFORE capture starts — fetching it on `entryMode`
  // was a chicken-and-egg: no capture without the names, no names without a capture.
  // James named this directly: "The vocabulary must be loaded by then."
  useEffect(() => {
    if (!opas.isOpen || vocab.length > 0) return
    let live = true
    void fetchVocabulary().then((terms) => { if (live) setVocab(terms) })
    return () => { live = false }
  }, [opas.isOpen, vocab.length])

  /** The funeral-home names, for the forgiving opener. */
  const funeralHomes = useMemo(
    () => vocab.filter((t) => t.kind === "funeral_home").map((t) => t.text),
    [vocab],
  )

  /** ⚠️ ONE PREDICATE, TWO CALL SITES. Capture opens from live typing AND from
   *  submit; a broadened rule applied to only one of them would make the pane
   *  appear for a phrase that Enter then refused, or the reverse. */
  const opensCapture = useCallback(
    (phrase: string) =>
      CAPTURE_START.test(phrase.toLowerCase()) ||
      startsCaptureWithParty(phrase, funeralHomes),
    [funeralHomes],
  )

  /** ⚠️ DERIVED ON EVERY RENDER, NOT STORED. A ghost held in state outlives its
   *  cause — the director deletes a character and the old completion is still on
   *  screen. Same argument as `placeholderFor`. */
  const ghost = entryMode
    ? completionFor(entryValue, caret, vocab)
    : null
  const picks = status?.picks ?? []

  /**
   * WHAT THE GUIDED SURFACE SHOWS — the server's question, its hint and its pills.
   *
   * ⚠️ NULL WHEN THERE IS NOTHING TO ASK, and that is what makes the one-voice rule
   * above expressible: the reply line speaks only when this does not. It is null
   * before the session exists (nothing has been asked yet) and null when the order is
   * complete (`question_field_id` comes back null and the sentence is the ready line,
   * which belongs to the bar's own flow, not to a question with answers under it).
   *
   * ⚠️ AND IT IS DERIVED, NEVER LATCHED, like `captureVoice` and for the same reason:
   * a question stored on an event survives the thing that caused it, including the
   * director deleting the text it was asked about.
   */
  /**
   * ⚠️ THE RECEIPT IS SPENT ONCE THE OFFICE TYPES, AND IT DOES NOT COME BACK. The memo
   * already HIDES the done pills while the bar holds text, but hiding alone would
   * bring "Order confirmed." back if they typed and then deleted — a receipt for an
   * order they have stopped thinking about. Clearing the flag makes the state
   * one-shot, which is what "Type the next one" means.
   */
  useEffect(() => {
    if (justApproved && text.trim() !== "") setJustApproved(false)
  }, [text, justApproved])

  const guided = useMemo(() => {
    if (!entryMode) {
      // ── the Opas pane with nothing in progress: DONE, then IDLE ────────────────
      //
      // ⚠️ BOTH ARE GATED ON AN EMPTY BAR AND NO REPLY ON SCREEN, which is the
      // dispatch's "typing anything hides them" and its "every other bar use is
      // unchanged" stated as one condition. A reply means the bar is being used for
      // something else — a result list, a miss, a drafted rule — and putting pills
      // over it would answer a question nobody asked.
      if (!opas.isOpen) return null
      if (text.trim() !== "") return null
      if (reply !== null) return null
      if (justApproved) {
        return {
          question: DONE_QUESTION,
          hint: DONE_HINT,
          fieldId: null,
          // ⚠️ `sub: "Enter"` BECAUSE ENTER PERFORMS IT. The dispatch says Enter
          // starts another order, and a key that works without being shown is a key
          // nobody uses.
          pills: [{ value: PILL_ACT_NEW_ORDER, label: DONE_PILL_LABEL,
                    sub: "Enter", act: PILL_ACT_NEW_ORDER }],
          cremation: null,
        }
      }
      return {
        question: IDLE_QUESTION,
        hint: IDLE_HINT,
        fieldId: null,
        pills: [{ value: PILL_ACT_NEW_ORDER, label: IDLE_PILL_LABEL,
                  act: PILL_ACT_NEW_ORDER }],
        cremation: null,
      }
    }
    const question = status?.guidedQuestion ?? null
    if (question === null || question === "") return null
    const fieldId = status?.guidedFieldId ?? null
    // ⚠️ NO FIELD IS NOT NO QUESTION, AND MY FIRST VERSION RETURNED NULL HERE. In the
    // ready state the server sends `question_field_id: null`, "That's everything." and
    // a single Review pill — so bailing out on a null field hid exactly the state
    // James asked for in clause 3, and left the reply line to say it instead.
    return {
      question,
      hint: status?.guidedHint ?? null,
      fieldId,
      pills: status?.guidedPills ?? [],
      cremation: status?.cremation ?? null,
    }
  }, [  // eslint-disable-line react-hooks/exhaustive-deps
    entryMode,
    opas.isOpen,
    text,
    reply,
    justApproved,
    status?.guidedQuestion,
    status?.guidedHint,
    status?.guidedFieldId,
    status?.guidedPills,
    status?.cremation,
  ])

  /** ⚠️ KEYED BY THE FRONT ENTRY PANE, because that is whose question is on screen.
   *  Routing an answer to the last pane to report would settle a field on an order the
   *  director is not looking at. */
  const answerGuided = useCallback(
    (fieldId: string, value: string) => {
      const paneId = entryPane?.id
      if (paneId === undefined) return
      answerNonce.current += 1
      setAnswerRequest((cur) => ({
        ...cur,
        [paneId]: { fieldId, value, nonce: answerNonce.current },
      }))
    },
    [entryPane?.id],
  )

  /**
   * ⌘1..9 AND A BARE DIGIT ANSWER THE REPLY'S QUESTION.
   *
   * ⚠️ A SECOND, SEPARATE HANDLER FROM CAPTURE'S BELOW, AND THEY CANNOT BOTH BE LIVE.
   * Capture's fires only while the front ENTRY pane has a field pick; this one only
   * while the reply carries options, and a reply question is never raised while an
   * entry pane is in front (every `say(…, {options})` site is reached from `submit`,
   * which an entry pane's Enter does not call). Stated rather than assumed because two
   * live ⌘1 handlers would both `preventDefault` and the order would decide.
   *
   * ⚠️ A BARE DIGIT WORKS HERE AND NOT IN CAPTURE, and the asymmetry is the data. In
   * capture the bar holds an order's text, where "3" may be a grave depth or a vault
   * size — the ruling of 2026-10-13 that `pick-digit.ts` implements. Here the bar holds
   * a request, and a request that is just "2" is a choice and nothing else. The
   * dispatch asks for both: "Answer by ⌘1-⌘9, a plain digit, a click, or typing words".
   *
   * ⚠️ IT DOES NOT FIRE PAST THE NUMBER OF OPTIONS. ⌘7 against a 3-option question is
   * ignored rather than clamped.
   */
  useEffect(() => {
    const options = reply?.options
    if (!opas.isOpen || options === undefined || options.length === 0) return
    // ⚠️ BOUND TO A LOCAL BEFORE THE CLOSURE, the same reason capture's handler below
    // does it: TypeScript cannot carry the narrowing of `options` into a function
    // defined after the guard. It is also the correct runtime behaviour — the listener
    // answers the question that was on screen when it was attached.
    const open = options
    function onKeyDown(e: KeyboardEvent) {
      if (e.altKey || e.shiftKey) return
      if (!/^[1-9]$/.test(e.key)) return
      // ⚠️ A BARE DIGIT ONLY WHEN THE BAR IS EMPTY. Mid-phrase it is part of what is
      // being typed — "monticello 28" names a size — and consuming it would both answer
      // the wrong question and eat a character.
      const bare = !(e.metaKey || e.ctrlKey)
      if (bare && text.trim() !== "") return
      const index = Number(e.key)
      if (index > open.length) return
      e.preventDefault()
      e.stopImmediatePropagation()
      answerOption(index - 1)
    }
    document.addEventListener("keydown", onKeyDown, true)
    return () => document.removeEventListener("keydown", onKeyDown, true)
  }, [opas.isOpen, reply, text, answerOption])

  /**
   * CAPTURE SPEAKS IN THE SAME VOICE AS EVERYTHING ELSE.
   *
   * ⚠️ JAMES, 2026-10-20, SUPERSEDING THE 2026-10-15 PLACEHOLDER RULING: "capture's
   * question moves into the reply line above the bar and stays visible while typing;
   * the placeholder goes back to a plain prompt. One voice everywhere."
   *
   * ⚠️ IT IS A BUG FIX AND NOT ONLY A MOVE, which is worth stating because the previous
   * slice declined to make it. The question was rendered as the bar's `placeholder`,
   * which a browser shows only when the field is EMPTY, and `placeholderFor` returned
   * the question only when the text was NON-empty. Measured: four of its nine possible
   * return values could not appear on screen at all — the server's `next_question`,
   * both "Still need" forms, and "Nothing needed". The 2026-10-15 ruling that asked for
   * one question at a time had never been visible to anyone.
   *
   * ⚠️ `kind: "question"` SO IT DOES NOT FADE, which is what "stays visible while
   * typing" requires — an acknowledgement at 4200ms would take the question away
   * mid-sentence.
   *
   * ⚠️ AND IT CLEARS ONLY ITS OWN SENTENCE ON THE WAY OUT. `lastCaptureVoice` holds what
   * capture last said; when the entry pane goes, the reply is cleared only if it is
   * still that string.
   *
   * ⚠️ CORRECTED BEFORE SHIPPING — THAT GUARD IS DEFENSIVE, NOT LOAD-BEARING, AND MY
   * COMMENT CLAIMED OTHERWISE. It read: "Clearing unconditionally would wipe whatever the
   * NEXT thing said — and after Approve the next thing is the new order's pane opening."
   * Measured by break test: replacing the condition with a bare `setReply(null)` turned
   * NOTHING red. The reason is structural — in entry mode the only speaker IS capture
   * (`submit` is not reached, the bar is the order's text field), so at the moment
   * `entryMode` goes false the reply cannot be anyone else's. `openSalesOrder` says
   * nothing, so the approve path has nothing to wipe either.
   *
   * It is kept for independence from that sequencing rather than for a defect it
   * currently prevents: the first thing to speak during a capture — a background
   * notification, a second pane's acknowledgement — makes the unconditional version
   * wrong, and nothing would fail when it does.
   */
  const lastCaptureVoice = useRef<string | null>(null)
  useEffect(() => {
    if (entryMode) {
      // ⚠️ THE GUIDED PANE CARRIES THE QUESTION WHEN IT HAS ONE, AND THE REPLY LINE
      // GOES QUIET — otherwise the same question is on screen twice, in two different
      // wordings, which is the opposite of the one-voice ruling that moved it out of
      // the bar in the first place.
      //
      // ⚠️ THE REPLY LINE IS NOT RETIRED, AND THE REMAINING CASES ARE REAL. Before the
      // session exists the server has said nothing — `captureVoice` is the only thing
      // that can say "Starting the order…" — and the same holds if the guided extras
      // fail to compose, which `_guided` is explicitly allowed to do rather than take
      // the pane down. So the reply line is the floor, not a duplicate.
      if (guided !== null) {
        if (lastCaptureVoice.current !== null) {
          const stale = lastCaptureVoice.current
          lastCaptureVoice.current = null
          setReply((cur) => (cur !== null && cur.text === stale ? null : cur))
        }
        return
      }
      const voice = status?.question
      if (voice === undefined || voice === "") return
      lastCaptureVoice.current = voice
      say("question", voice)
      return
    }
    if (lastCaptureVoice.current === null) return
    const stale = lastCaptureVoice.current
    lastCaptureVoice.current = null
    setReply((cur) => (cur !== null && cur.text === stale ? null : cur))
  }, [entryMode, status?.question, guided, say])

  /**
   * ESCAPE CANCELS THE QUESTION, AND THE REPLY GOES WITH IT.
   *
   * ⚠️ IT WATCHES `pendingPick` RATHER THAN HANDLING THE KEY. `onEscape` in the context
   * already owns Escape's three branches and clears `pendingPick` on the first one; a
   * second Escape listener here would be a second opinion about what Escape does. So
   * this reacts to the flag the context already flips.
   */
  useEffect(() => {
    if (opas.pendingPick === null && reply?.options !== undefined) {
      answerActions.current = {}
      setReply(null)
    }
  }, [opas.pendingPick, reply])

  /**
   * A PRINTABLE KEYPRESS WITH NOTHING EDITABLE FOCUSED GOES INTO THE BAR, AND THE FIRST
   * CHARACTER IS NOT LOST. James's first rule, 2026-10-20.
   *
   * ⚠️ FOCUSING THE BAR IS NOT ENOUGH, which is the whole difficulty. `focus()` during a
   * keydown does not deliver that keydown to the newly-focused element — the browser has
   * already decided where the event goes — so a handler that only focused would swallow
   * the first letter of every sentence typed after a click. This appends the character
   * itself and `preventDefault`s, so exactly one copy lands.
   *
   * ⚠️ `e.key.length === 1` IS THE PRINTABLE TEST, and it is what keeps Enter, Tab,
   * Escape, the arrows and every F-key untouched — all of those have multi-character
   * names. Modifier combinations are left alone for the same reason ⌘1 is: they belong
   * to someone else.
   */
  useEffect(() => {
    if (!opas.isOpen) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key.length !== 1) return
      const el = document.activeElement as HTMLElement | null
      if (el === inputRef.current) return
      // ⚠️ AN EDITABLE FIELD INSIDE A PANE KEEPS THE KEYSTROKE, by ruling: "Exception: an
      // editable field inside a pane that the user clicked into keeps focus until Esc or
      // blur." `closest` rather than a tag test, so a contenteditable's inner spans count.
      if (el !== null && el.closest("input, textarea, select, [contenteditable='true']")) return
      e.preventDefault()
      inputRef.current?.focus({ preventScroll: true })
      if (entryMode && entryPane !== undefined) {
        opas.setEntryText(entryPane.id, (opas.entryText[entryPane.id] ?? "") + e.key)
      } else {
        setText((cur) => cur + e.key)
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [opas, opas.isOpen, entryMode, entryPane])

  /**
   * ⌘1..9 SETTLES A PICK — and ONLY while the front entry pane has one, by ruling.
   *
   * ⚠️ THE GUARD IS `picks.length > 0`, SO THE KEYS ARE NOT BOUND AT ANY OTHER TIME.
   * An always-live ⌘1..9 would collide with the Spaces shortcuts (`Cmd+Shift+1..7`
   * differ by Shift, but `Cmd+1..5`-style bindings are used elsewhere in this app) and
   * would do nothing visible, which is the worst kind of taken key: unavailable to
   * everyone and useful to no one.
   *
   * ⚠️ PLAIN DIGITS ARE NOT TOUCHED, DELIBERATELY. A bare "3" is text the director may
   * be typing — a grave depth, a vault size, a time — so it goes into the text. That
   * is the ruling and it is also why the ⌘ hint is printed next to the numbers.
   *
   * ⚠️ IT DOES NOT FIRE PAST THE NUMBER OF OPTIONS. ⌘7 against a 3-option question is
   * ignored rather than clamped; clamping would settle a question with an answer the
   * director did not choose.
   */
  useEffect(() => {
    if (!opas.isOpen || entryPane === undefined || picks.length === 0) return
    // ⚠️ BOUND TO LOCALS BEFORE THE CLOSURE. TypeScript cannot carry the narrowing of
    // `entryPane` into a function defined below the guard — it has no way to know the
    // listener runs before the next render — so reading `entryPane.id` inside
    // `onKeyDown` is `possibly undefined`. Capturing the id is also the correct
    // runtime behaviour: the listener should settle the pick for the pane that was in
    // front when it was attached, which is the pane the numbers are visible on.
    //
    // ⚠️ THE `picks.length === 0` GUARD IS WHAT MAKES ⌘N UNBOUND AT OTHER TIMES, and
    // it is OBSERVABLE rather than merely defensive: with no listener attached, ⌘2
    // is not `preventDefault`ed and reaches whatever else wants it. A break test
    // removing this guard produced NO red at first — the handler simply crashed on
    // `picks[0].options` and vitest reported exit 1 with no named failing test, which
    // is a signal nobody would read as "this guard matters". The test now dispatches
    // the event and asserts on `defaultPrevented`, which distinguishes "not bound"
    // from "bound and inert".
    const paneId = entryPane.id
    const pick = picks[0]
    function onKeyDown(e: KeyboardEvent) {
      if (!(e.metaKey || e.ctrlKey)) return
      if (e.altKey || e.shiftKey) return
      if (!/^[1-9]$/.test(e.key)) return
      const index = Number(e.key)
      if (index > pick.options.length) return
      e.preventDefault()
      e.stopImmediatePropagation()
      pickNonce.current += 1
      setPickRequest((prev) => ({
        ...prev,
        [paneId]: { fieldId: pick.field_id, index, nonce: pickNonce.current },
      }))
    }
    document.addEventListener("keydown", onKeyDown, true)
    return () => document.removeEventListener("keydown", onKeyDown, true)
  }, [opas.isOpen, entryPane, picks])

  /**
   * AN ORDER PANE OPENS AS SOON AS THE PHRASE SAYS SO — NO ENTER.
   *
   * ⚠️ THIS IS THE DEFECT JAMES HIT ON PRODUCTION, 2026-10-12 13:54 ET. He typed
   * "order for hopkins" in the bar and waited; no pane appeared and no error. The
   * cause: `openPane` for a capture pane was reached from exactly two places — the
   * reload-restore effect, and `submit()` — and `submit()` ran only inside
   * `if (e.key === "Enter")`. So there was NO code path that opened an entry pane
   * from typing, and his own walk instruction said to type it WITHOUT pressing
   * Enter. Confirmed against production: zero `capture_sessions` rows were created
   * in that window, so `POST /capture/sessions` was never called — the pane never
   * opened rather than a request failing.
   *
   * ⚠️ NO DEBOUNCE ON THE OPEN, DELIBERATELY, AND THIS IS THE PART THAT IS EASY TO
   * GET WRONG. A debounce resets on every keystroke, so during continuous typing it
   * never fires — the pane would appear only once the director STOPPED, which is the
   * opposite of "watch it grow out of the bar and fill in as you type". The match is
   * an unambiguous signal and firing on it is what makes the pane arrive while they
   * are still talking. Re-extraction keeps its 350 ms debounce; opening does not
   * need one.
   *
   * ⚠️ THE TYPED TEXT MOVES INTO THE PANE, which is the whole reason `openPane` now
   * returns an id. Without that the director would watch their words vanish at the
   * moment the pane appeared.
   *
   * ⚠️ NO `openingLine`, SO THERE IS ONE WRITE PATH AND NOT TWO. Passing the phrase
   * to `startCapture` would extract it through `add_line` — the FIRST_WINS line
   * model — and the pane's own re-extraction would then replace that reading through
   * the LAST_WINS text model. One of the two would always be redundant, and
   * `typed_lines` would carry a row the text model does not own.
   */
  useEffect(() => {
    if (!opas.isOpen) return
    // ⚠️ ONE PANE PER PHRASE IS HELD BY TWO THINGS JOINTLY, AND NEITHER ONE IS "THE
    // GUARD". Every keystroke after "order for" still matches, so something has to
    // stop a second pane. Measured by removing each in turn, over 147 tests:
    //
    //     removed                              result
    //     an `openedFromBar` ref (all of it)   147 green  <- genuinely dead
    //     this `entryMode` check only          147 green
    //     the `setText("")` below only         1 red (the second-order test)
    //     BOTH entryMode and setText("")       45 red — a pane per keystroke
    //
    // So each is sufficient on its own and both are kept, because each also has an
    // independent job: `entryMode` is what makes the bar the order's field at all,
    // and clearing the host's request-text is what stops a closed pane from
    // instantly reopening and what leaves the bar clean for a catalog request.
    //
    // ⚠️ I NAMED A SINGLE MECHANISM HERE TWICE AND WAS WRONG BOTH TIMES. First an
    // `openedFromBar` ref — deleted; removing the flag, its check and its re-arm
    // together left everything green, though removing only its re-arm DID turn a
    // test red, which is why it read as load-bearing (half of a redundant pair is
    // not the pair). Then this `entryMode` check, which also removes clean. Only
    // elimination found the real answer, and the real answer is "jointly". CLAUDE.md
    // §11, a guard whose protection is supplied by a layer beneath it — twice over.
    //
    // ⚠️ AND `opens ONCE for a phrase typed continuously` CANNOT TELL WHICH IS
    // DOING THE WORK. It stayed green for either single removal and only fell to
    // both. It is a true assertion about the behaviour and not evidence about the
    // mechanism; the table above is the evidence.
    // ⚠️ AN APPROVED PANE IS CLOSED BEFORE THE PHRASE IS READ, AND THIS IS THE
    // SAME TRAP AS THE RESTORED PANE. A pane holding a created order is still an
    // ENTRY pane, so it holds the bar in entry mode and `entryMode` below would
    // return before ever looking at the words — the tab would be unable to start a
    // second order until the 6-second timer fired. Closing it here means the
    // director's next sentence both dismisses the receipt and starts the order.
    if (approvedPanes.current.size > 0) {
      for (const id of approvedPanes.current) opas.closePane(id)
      approvedPanes.current.clear()
    }
    if (entryMode) return
    const phrase = text.trim()
    if (phrase === "") return
    if (!opensCapture(phrase)) return
    const id = opas.openPane({ kind: "capture", label: "Order" })
    opas.setEntryText(id, phrase)
    setText("")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, entryMode, opas.isOpen, opensCapture])

  /**
   * The bar's height follows its content.
   *
   * ⚠️ SET FROM `scrollHeight` ON EVERY CHANGE, AND RESET TO `auto` FIRST. Without
   * the reset the height only ever grows: `scrollHeight` of an element already tall
   * enough is its current height, so deleting a line would leave the gap behind.
   *
   * ⚠️ THE PANE FOLLOWS FOR FREE. It is anchored at `bottom: 24 + barH`, and `barH`
   * comes from a ResizeObserver on the bar — so growing the textarea moves the pane
   * up without anything here knowing about panes.
   */
  useEffect(() => {
    const el = inputRef.current
    if (el === null) return
    el.style.height = "auto"
    el.style.height = `${el.scrollHeight}px`
  }, [text, entryValue, entryMode, opas.isOpen])

  useEffect(() => {
    const el = barRef.current
    if (el === null) return
    const read = () => setBarH(el.getBoundingClientRect().height)
    read()
    // ⚠️ GUARDED: jsdom has no ResizeObserver, and the component must not throw in
    // the test environment just because the browser API is absent. The initial read
    // above is what the tests see.
    const RO = (window as unknown as { ResizeObserver?: typeof ResizeObserver })
      .ResizeObserver
    if (RO === undefined) return
    const ro = new RO(read)
    ro.observe(el)
    return () => ro.disconnect()
  }, [opas.isOpen])

  /**
   * CLOSING OPAS ENDS THE CAPTURE — Esc, the veil, and the close button.
   *
   * ⚠️ RULED FOR A SHARED OFFICE COMPUTER, NOT TIDINESS. The next person at that
   * machine must never see someone else's half-typed order, so an entry pane is
   * CLOSED rather than tucked and its text is cleared. Info panes keep tuck: a
   * catalog list is not somebody's private order.
   *
   * ⚠️ THE SERVER ROW IS MARKED ABANDONED, NEVER DELETED. James accepted the
   * consequence — an accidental click away loses the order from the screen — on the
   * basis that a copy survives for recovery. Deleting would make that promise false
   * while looking identical from here.
   *
   * ⚠️ IT RUNS ON THE CLOSE PATHS, NOT ON UNMOUNT. An unmount effect would also fire
   * when a Focus opens over Opas, or on a hot reload, and would abandon an order the
   * director had not finished with.
   */
  /**
   * The order exists. Clear the bar, let the number be read, then close.
   *
   * ⚠️ THE BAR CLEARS IMMEDIATELY AND THE PANE CLOSES ON A TIMER, in that order and
   * not the reverse. An ENTRY pane holds the bar in entry mode for as long as it is
   * the front pane — which is the mechanism behind the "no pane appeared" bug that
   * cost three walk rounds — so leaving the approved pane open indefinitely would
   * make the tab unable to start a second order. The timer bounds that window.
   *
   * ⚠️ AND A KEYSTROKE CLOSES IT EARLY. The window is only there so the office can
   * read the order number; the moment somebody starts typing the next order they
   * have finished reading, and waiting out a timer would swallow their first words.
   * That is handled by the opening effect, which clears the approved pane before it
   * looks at the phrase.
   *
   * ⚠️ NO `abandonCapture` HERE. The session is `approved` and carries the order id;
   * telling the server it was abandoned would contradict the row it just wrote.
   */
  /** ⚠️ IT NO LONGER DEDUPES OR CLOSES, AND BOTH REMOVALS ARE THE RULING.
   *
   *  The dedupe moved into `opas.openPane` (`pane-identity.ts`), so EVERY caller gets
   *  "already open focuses that pane" rather than only this one — the Product pane had
   *  no such check and made duplicates.
   *
   *  The `for (…) closePane(…)` loop that closed every OTHER sales-order pane is gone.
   *  It belonged to the one-order-beside-the-list arrangement; panes chain now ("an
   *  order links to its funeral home, its vault and its cemetery, so each pane opens the
   *  next one"), and closing the order you came from is the opposite of chaining. */
  const openSalesOrder = useCallback((orderId: string) => {
    opas.openPane({ kind: "sales-order", label: "Sales order", salesOrderId: orderId })
    // ⚠️ THE BAR GETS THE CURSOR BACK, so the next sentence does not need a click.
    focusBar()
  }, [opas, focusBar])

  /** "close" in the bar closes the FRONT pane. James's fourth multi-pane rule. */
  const closeFrontPane = useCallback((): boolean => {
    const front = opas.panes.find((p) => p.id === opas.frontPaneId)
    if (front === undefined) return false
    // ⚠️ THE SAME TWO MEANINGS AS THE × BUTTON. An entry pane's close ENDS the capture
    // (the session is abandoned on the server and the bar's text is cleared); an info
    // pane's just closes the pane. Typing "close" at a half-typed order has to do what
    // clicking its × does, or the two controls disagree about what closing means.
    opas.closePane(front.id)
    if (isEntryPane(front.kind)) {
      setText("")
      if (front.captureSessionId !== undefined) {
        void abandonCapture(front.captureSessionId)
      }
    }
    focusBar()
    return true
  }, [opas, focusBar])

  /**
   * ⚠️ THE CAPTURE CLOSES AND THE ORDER'S PANE OPENS IN ITS PLACE, by James's third
   * opening path (2026-10-19): "After Approve on the capture Review: the capture closes
   * and the new order's pane opens in its place."
   *
   * ⚠️ THE `APPROVED_VISIBLE_MS` WINDOW IS NOW THE FALLBACK, NOT THE BEHAVIOUR, and it
   * is kept rather than deleted for one reachable reason. The window existed so the
   * office could read "Created SO-2026-0003" before the pane went; the order's own pane
   * says that permanently, so it is no longer needed WHEN THERE IS AN ID. The server
   * sends `sales_order_id` and `CapturePane` already guards on its absence
   * (`capture-approved-link` degrades to plain text), so `id === null` is a state this
   * app can reach — and closing the pane with no replacement would leave the office with
   * nothing at all. In that case the old timer runs.
   *
   * ⚠️ AND THE ENTRY-MODE TRAP IS WHY THIS CANNOT JUST LEAVE THE PANE OPEN. An entry
   * pane holds the bar in entry mode for as long as it is in front, which is the bug
   * that cost three walk rounds. Either it closes now (id present) or the timer closes
   * it (id absent). It is never left indefinitely.
   */
  const onApproved = useCallback(
    (paneId: string, order: { id: string | null }) => {
      setText("")
      opas.setEntryText(paneId, "")
      // ⚠️ SET BEFORE EITHER BRANCH, because the Opas pane's done state is owed in
      // both — whether the capture pane is replaced by the order's pane or left for
      // the fallback timer, the office has just confirmed an order and the pane
      // beside the bar should say so.
      setJustApproved(true)
      if (order.id !== null) {
        opas.closePane(paneId)
        openSalesOrder(order.id)
        return
      }
      approvedPanes.current.add(paneId)
      window.setTimeout(() => {
        opas.closePane(paneId)
        approvedPanes.current.delete(paneId)
      }, APPROVED_VISIBLE_MS)
    },
    [opas, setText, openSalesOrder],
  )

  /**
   * Enter in the bar finishes the order — the pane decides which action that is.
   *
   * ⚠️ THE PANE OWNS THE STAGE, SO THE PANE OWNS THE CHOICE. The host does not know
   * whether this session is capturing or in review; asking it to decide would mean a
   * second copy of that state, and the two would disagree the moment one of them
   * lagged a response.
   */
  const requestComplete = useCallback(() => {
    if (entryPane === undefined) return
    completeNonce.current += 1
    const n = completeNonce.current
    setCompleteRequest((prev) => ({ ...prev, [entryPane.id]: n }))
  }, [entryPane])


  /**
   * A pill's ACTION. Today the only one is Review, which is what Enter does.
   *
   * ⚠️ IT GOES THROUGH `requestComplete`, THE SAME ENTRANCE AS ENTER AND ⌘ENTER, and
   * that is the whole reason removing the Complete button was safe. One action behind
   * three entrances was the 2026-10-14 arrangement; this replaces the button with a
   * pill and leaves the action alone.
   */
  /**
   * Start a capture with no phrase — the idle and done states' pill.
   *
   * ⚠️ IT OPENS THE PANE WITH AN EMPTY BAR, WHICH IS WHAT PUTS THE OFFICE ON THE
   * FUNERAL-HOME QUESTION. The dispatch's clause 1: "Picking one starts the capture at
   * the funeral-home question." A capture with no text has every field missing, and
   * `guided_field` walks `CALL_ORDER`, whose first entry is `funeral_home` — so the
   * question is the engine's answer rather than a destination this function picks.
   *
   * ⚠️ NO PHRASE IS PASSED, DELIBERATELY. `openPane` + `setEntryText(id, phrase)` is
   * the typed path; passing text here would make the pane open already holding words
   * the office did not type.
   */
  const startBlankCapture = useCallback(() => {
    setJustApproved(false)
    const id = opas.openPane({ kind: "capture", label: "Order" })
    opas.setEntryText(id, "")
    setText("")
    focusBar()
  }, [opas, focusBar])

  const actGuided = useCallback(
    (act: string) => {
      if (act === PILL_ACT_REVIEW) requestComplete()
      else if (act === PILL_ACT_NEW_ORDER) startBlankCapture()
    },
    [requestComplete, startBlankCapture],
  )

  /**
   * Ask a question again, because the office clicked its row.
   *
   * ⚠️ IT IS A CLIENT-SIDE FOCUS, NOT A SERVER CALL, AND THAT IS THE CHEAP CORRECT
   * VERSION. "Clicking a row asks that question again" means the question line and the
   * pills show that field; nothing about the ORDER changes, so there is nothing to
   * write. The server keeps deciding what is asked NEXT, and this overrides which
   * question is on screen until it is answered — the same shape as the prototype's
   * `S.focus`, which `currentField()` prefers over `nextField()`.
   */
  const focusNonce = useRef(0)
  const [focusRequest, setFocusRequest] = useState<
    Record<string, { fieldId: string; nonce: number }>
  >({})
  const askAgain = useCallback(
    (fieldId: string) => {
      setFocusField(fieldId)
      // ⚠️ THE OUTLINE AND THE QUESTION ARE TWO EFFECTS OF ONE CLICK. `focusField`
      // moves the outline immediately, with no round trip; the request asks the server
      // for that question's sentence, hint and pills, which only it composes.
      const paneId = entryPane?.id
      if (paneId === undefined) return
      focusNonce.current += 1
      setFocusRequest((cur) => ({
        ...cur,
        [paneId]: { fieldId, nonce: focusNonce.current },
      }))
    },
    [entryPane?.id],
  )

  /**
   * Which field is being asked about — the clicked row if there is one, else the
   * server's next question.
   *
   * ⚠️ THE CLICKED ROW WINS, AND ONLY UNTIL IT IS ANSWERED. That is the prototype's
   * `currentField()`:
   *     if(S.focus&&applicable(S.focus)&&!S.f[S.focus])return S.focus;
   *     return nextField();
   * — the focus is preferred while it is still unanswered, and the walk resumes the
   * moment it is not.
   *
   * ⚠️ IT READS `answered` FROM THE SERVER RATHER THAN CLEARING ON THE CLICK'S OWN
   * RESPONSE. A click can be followed by typing instead of a pill, and the answer then
   * arrives through re-extraction with nothing to hang a clear on.
   */
  const askedField = useMemo(() => {
    const next = status?.guidedFieldId ?? null
    if (focusField === null) return next
    // ⚠️ THIS FALLBACK IS DEFENSIVE, NOT LOAD-BEARING, AND A BREAK TEST PROVED IT.
    // Disabling it turned nothing red: the effect below CLEARS `focusField` once the
    // field is answered, so by the time this would matter the state is already null.
    // Kept for independence from that effect's timing — a render between the server's
    // answer and the effect running would otherwise outline a finished question — and
    // recorded as defensive so nobody cites it as the mechanism.
    const answered = new Set(status?.answeredFieldIds ?? [])
    if (answered.has(focusField)) return next
    return focusField
  }, [focusField, status?.guidedFieldId, status?.answeredFieldIds])

  /** ⚠️ CLEARED AS STATE, NOT JUST IGNORED. `askedField` already falls back once the
   *  field is answered; without this the stale id would sit in state for the rest of
   *  the session and win again if the office later cleared that answer. */
  useEffect(() => {
    if (focusField === null) return
    if ((status?.answeredFieldIds ?? []).includes(focusField)) setFocusField(null)
  }, [focusField, status?.answeredFieldIds])

  const endEntryCaptures = useCallback(() => {
    for (const pane of opas.panes) {
      if (!isEntryPane(pane.kind)) continue
      const sid = pane.captureSessionId
      if (sid !== undefined) void abandonCapture(sid)
      opas.closePane(pane.id)
    }
    setText("")
  }, [opas])

  /**
   * A PLAIN NUMBER PICKS, and the number leaves the order text. Ruled 2026-10-13,
   * superseding "typed digits go into the text".
   *
   * ⚠️ IT WATCHES THE TEXT RATHER THAN THE KEY, because the digit must be REMOVED.
   * A key handler would select the option and leave the digit in the sentence, where
   * the next extraction reads it as a size or a year. `consumePickDigit` owns the
   * five conditions and is tested as a pure function.
   *
   * ⚠️ IT CANNOT LOOP. Stripping the digit leaves text that no longer ends in a bare
   * number, so the effect re-runs once and matches nothing.
   *
   * ⚠️ ⌘1..9 IS UNTOUCHED and still works; this is the plain-number path beside it.
   */
  useEffect(() => {
    if (entryPane === undefined || picks.length === 0) return
    const pick = picks[0]
    const paneId = entryPane.id
    // ⚠️ DEBOUNCED ON THE SAME PAUSE AS EXTRACTION, AND NOT OPTIONAL. Checked on
    // every keystroke, a number is judged on its PREFIXES: typing "34" passes
    // through "3", and with three options showing the 3 was consumed and the 4 left
    // behind. James's own counter-example ("34 is not consumed") failed this way in
    // the first version — the rule was right and the timing was wrong. Waiting for
    // the pause means the number is judged once, finished.
    const timer = window.setTimeout(() => {
      const hit = consumePickDigit(entryValue, pick.options.length)
      if (hit === null) return
      opas.setEntryText(paneId, hit.text)
      pickNonce.current += 1
      setPickRequest((prev) => ({
        ...prev,
        [paneId]: {
          fieldId: pick.field_id,
          index: hit.index,
          nonce: pickNonce.current,
        },
      }))
    }, EXTRACT_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entryValue, entryPane, picks])

  /** ⚠️ A REF TO BREAK A REAL CYCLE, not a workaround for a lint rule.
   *  `settleOrderAnswer` builds the option actions, and each one calls
   *  `chooseOrderPick`, which asks the server again and hands the answer back to
   *  `settleOrderAnswer`. The two are mutually recursive by design — narrowing a pick
   *  can produce another pick — and one of them has to be reached indirectly. */
  const chooseOrderPickRef = useRef<(pick: OrderPick) => void>(() => {})

  /**
   * Open a customer, or focus the one already open.
   *
   * ⚠️ IT GOES THROUGH `opas.openPane`, WHICH DEDUPES BY `PANE_IDENTITY`. "Opening one
   * already open focuses it; never a duplicate" (James, 2026-10-24) is therefore true
   * for every caller rather than for the one that remembered — the argument
   * `pane-identity.ts` already makes. A customer is reachable three ways in this slice,
   * so this is the path all three take.
   */
  const openCustomer = useCallback((customerId: string, name?: string) => {
    opas.openPane({ kind: "customer", label: "Customer", customerId })
    if (name !== undefined) say("ack", `Opened ${name}`)
  }, [opas, say])

  const openCemetery = useCallback((cemeteryId: string, name?: string) => {
    opas.openPane({ kind: "cemetery", label: "Cemetery", cemeteryId })
    if (name !== undefined) say("ack", `Opened ${name}`)
  }, [opas, say])

  /**
   * "New order" on a customer: a capture with the funeral home already filled.
   *
   * ⚠️ IT REUSES `openingLine`, THE SAME FIELD THE BAR USES. "as if the bar said 'order
   * <name> '" (James, 2026-10-24) — so the capture is started by the same mechanism as
   * typing it, extraction and all. A second path that pre-filled a field directly would
   * be a second way to start an order, free to drift from the one the director uses.
   */
  const startOrderFor = useCallback(
    (openingLine: string, prefill?: Readonly<Record<string, string>>) => {
      const id = opas.openPane({
        kind: "capture", label: "Order", openingLine, capturePrefill: prefill,
      })
      // ⚠️ THE BAR SHOWS WHAT WAS CAPTURED, AND THAT IS HALF THE FIX. "The bar shows
      // 'order Hopkins Funeral Home ' with the cursor at the end, so what's on screen
      // matches what was captured" (James, 2026-10-24). Without it the pane's `text`
      // prop was whatever the bar held — nothing — and the debounced whole-text re-read
      // erased the funeral home about a second after it appeared.
      //
      // ⚠️ IT IS NOT SUFFICIENT ON ITS OWN, WHICH IS WHY THE PREFILL EXISTS TOO. Text in
      // the bar is text: deleting the name would un-capture the home, and the ruling is
      // that a pane-made choice survives that. Belt and braces, and they do different
      // jobs — this one keeps the screen honest, the prefill keeps the choice.
      opas.setEntryText(id, openingLine)
      // The cursor goes after the trailing space, ready for the next word.
      window.setTimeout(() => {
        const el = inputRef.current
        if (el === null) return
        el.focus({ preventScroll: true })
        el.setSelectionRange(openingLine.length, openingLine.length)
      }, 0)
    },
    [opas],
  )

  const settleOrderAnswer = useCallback((result: OrderListSnapshot, spoken: string | undefined) => {
    if (result.kind === "unrecognized" || result.kind === "total") {
      // ⚠️ A TOTAL IS AN ANSWER, NOT A MISS. "How much is that?" returns a sentence the
      // director asked for; calling it a miss would colour it as a failure and fade it
      // at the same speed as "nothing matched".
      say(result.kind === "total" ? "ack" : "miss", result.hint ?? ORDER_TRY)
      return
    }
    if (result.kind === "open_order" && result.open_order_id) {
      openSalesOrder(result.open_order_id)
      return
    }
    // ⚠️ A BARE NAME OPENS THE CUSTOMER, AND THE RULES DECIDED THAT, NOT THE MODEL. The
    // server tries its own customer table before the door is consulted, so "hopkins" is
    // a deterministic open rather than a ~900 ms guess at an order-list question.
    if (result.kind === "open_customer" && result.customer_id) {
      openCustomer(result.customer_id, result.customer_name)
      return
    }
    if (result.kind === "open_rulebook") {
      openRulebook()
      return
    }
    if (result.kind === "open_cemetery") {
      if (result.cemetery_id !== undefined) {
        openCemetery(result.cemetery_id, result.cemetery_name)
      }
      return
    }
    if (result.kind === "cemetery_picks") {
      const picks = result.cemetery_picks ?? []
      const options: ReplyOption[] = picks.map((pick, i) => ({
        id: `cemetery-${i}`,
        label: pick.label,
        // ⚠️ THE TOWN IS THE DISCRIMINATOR AND IT RIDES IN `detail`. Two cemeteries of
        // the same name are told apart by nothing else — "ask which with the choice
        // list, town shown" (James, 2026-10-26).
        ...(pick.detail !== undefined ? { detail: pick.detail } : {}),
      }))
      const act: Record<string, () => void> = {}
      picks.forEach((pick, i) => {
        act[`cemetery-${i}`] = () => openCemetery(pick.cemetery_id, pick.label)
      })
      say("question", result.hint ?? "Which one?", { options, act })
      return
    }
    if (result.kind === "customer_picks") {
      const picks = result.customer_picks ?? []
      const options: ReplyOption[] = picks.map((pick, i) => ({
        id: `customer-${i}`,
        label: pick.label,
      }))
      const act: Record<string, () => void> = {}
      picks.forEach((pick, i) => {
        act[`customer-${i}`] = () => openCustomer(pick.customer_id, pick.label)
      })
      say("question", result.hint ?? "Which one?", { options, act })
      return
    }
    // ⚠️ THE PICK NO LONGER OPENS A PANE (James's third rule, 2026-10-20: "Choices sit
    // with the question"). It used to go through `updatePane`/`openPane` as an
    // `order-list` pane carrying a `picks` snapshot, so answering opened the order and
    // LEFT THE LIST BEHIND IT — the bug the ruling names. The question and its options
    // are now one thing above the bar, and answering ends both.
    if (result.kind === "picks") {
      const picks = result.picks ?? []
      const options: ReplyOption[] = picks.map((pick) => ({
        id: `pick-${pick.n}`,
        label: pick.label,
      }))
      const act: Record<string, () => void> = {}
      picks.forEach((pick) => {
        act[`pick-${pick.n}`] = () => chooseOrderPickRef.current(pick)
      })
      say("question", result.hint ?? "Which one?", { options, act })
      return
    }
    const existing = opas.panes.find((p) => p.kind === "order-list")
    const patch = {
      orderSnapshot: result,
      ...(result.question ? { orderQuestion: result.question } : {}),
      ...(spoken ? { orderPhrase: spoken } : {}),
    }
    if (existing) {
      opas.updatePane(existing.id, patch)
      opas.raisePane(existing.id)
    } else {
      opas.openPane({ kind: "order-list", label: "Orders", ...patch })
    }
    // ⚠️ THE "CLOSE EVERY SALES-ORDER PANE ON A NEW QUESTION" LOOP IS GONE, by the same
    // ruling as `openSalesOrder`'s. A new list question used to sweep away the order
    // pane the director had just opened from the previous one — which made "each pane
    // opens the next one" impossible to walk. Panes close one at a time, by the × or by
    // "close".
    if (result.hint) say("ack", result.hint)
  }, [opas, openSalesOrder, say])

  const removeOrderPill = useCallback(async (paneId: string, pillId: string) => {
    const pane = opas.panes.find((p) => p.id === paneId)
    if (!pane?.orderQuestion) return
    try {
      const result = await askOrderList({
        question: pane.orderQuestion,
        remove_pill: pillId,
        ...(pane.orderPhrase ? { teach_phrase: pane.orderPhrase } : {}),
        front: pane.kind,
      })
      settleOrderAnswer(result, undefined)
    } catch {
      say("miss", ORDER_TRY)
    }
  }, [opas, settleOrderAnswer, say])

  const chooseOrderPick = useCallback(async (pick: OrderPick) => {
    if (pick.order_id) {
      openSalesOrder(pick.order_id)
      return
    }
    if (!pick.question) return
    try {
      const result = await askOrderList({ question: pick.question })
      settleOrderAnswer(result, undefined)
    } catch {
      say("miss", ORDER_TRY)
    }
  }, [openSalesOrder, settleOrderAnswer, say])
  chooseOrderPickRef.current = (pick: OrderPick) => void chooseOrderPick(pick)

  /**
   * The order the director is looking at, or `null`.
   *
   * ⚠️ STRICTLY THE FRONT PANE, which is the dispatch's own wording ("With a Sales Order
   * pane in front"). The looser reading — "the most recently raised order pane, whatever
   * is in front" — was considered and rejected: with two orders open and the catalog in
   * front, "the total" would have to guess which order, and guessing is the one thing
   * this slice is built to stop doing. When the front pane is not an order, the host
   * asks, with the open orders as options.
   */
  const frontOrder = useMemo(() => {
    const front = opas.panes.find((p) => p.id === opas.frontPaneId)
    if (front?.kind !== "sales-order" || front.salesOrderId === undefined) return null
    return { paneId: front.id, orderId: front.salesOrderId }
  }, [opas.panes, opas.frontPaneId])

  /** Every open order pane, for the "Which order?" options. */
  const openOrderPanes = useMemo(
    () => opas.panes.filter((p) => p.kind === "sales-order" && p.salesOrderId !== undefined),
    [opas.panes],
  )

  /**
   * Answer or act on the order in front. Returns false when it could not.
   *
   * ⚠️ AN ANSWER OPENS NOTHING, by ruling. "when's the service" produces a sentence in
   * the reply line; a pane would be a worse answer than a sentence, because the director
   * already has the pane.
   *
   * ⚠️ AND AN UNREADABLE ORDER SAYS SO. The facts come from the pane's own read, so a
   * pane still loading has nothing to answer from — which says "Still reading the
   * order…" rather than answering with a blank.
   */
  const handleContext = useCallback(
    (intent: ContextIntent, orderId: string): void => {
      const order = orderFacts.current[orderId]
      if (order === undefined) {
        say("miss", "Still reading the order\u2026")
        return
      }
      const rowValue = (label: string): string | undefined =>
        order.order.find((r) => r.label === label)?.value

      if (intent.kind === "answer") {
        switch (intent.question) {
          case "service": {
            const service = rowValue("Service")
            say("ack", service !== undefined
              ? `${order.title} \u00b7 ${service}`
              : `${order.number} has no service date.`)
            return
          }
          case "total":
            say("ack", `${order.number} \u00b7 ${order.billing.total ?? rowValue("Total") ?? "no total"}`)
            return
          case "who":
            say("ack", `${order.title} \u00b7 ${order.funeral_home}`)
            return
          case "where": {
            const cemetery = rowValue("Cemetery")
            say("ack", cemetery !== undefined
              ? `${order.number} \u00b7 ${cemetery}`
              : `${order.number} has no cemetery on it.`)
            return
          }
          case "status":
            // ⚠️ `stands_at` IS THE SERVER'S OWN SENTENCE for where an order stands —
            // the same string the order list shows. Deriving a second one from `state`
            // would be two answers to one question.
            say("ack", `${order.number} \u00b7 ${order.stands_at}`)
            return
        }
      }

      switch (intent.action) {
        case "vault": {
          const vault = order.order.find((r) => r.label === "Vault")
          const variant = vault?.link?.kind === "product" ? vault.link.variant_template_id : undefined
          if (variant === undefined) {
            // ⚠️ THE SAME HONESTY AS THE PANE'S OWN ROW. A vault whose name resolves to
            // several catalog variants has no single product to open, so this says why
            // rather than opening an arbitrary one.
            say("miss", vault !== undefined
              ? `${vault.value} doesn\u2019t match one catalog product.`
              : "This order has no vault on it.")
            return
          }
          opas.openPane({ kind: "product", label: "Product", variantTemplateId: variant })
          say("ack", `Opened ${vault?.value ?? "the vault"}`)
          return
        }
        case "customer":
          // ⚠️ THE ID, NOT THE NAME. `detail.order_detail` emits `customer_id` since
          // 2026-10-24; before that this case could only say the name, because resolving
          // it back to an account here would have been client-side name matching for a
          // key the server holds.
          if (order.customer_id === undefined) {
            // An order with no customer row. The LEFT JOIN tolerates it, so this must.
            say("miss", `${order.funeral_home} \u00b7 no customer record on this order.`)
            return
          }
          openCustomer(order.customer_id, order.funeral_home)
          return
        case "cemetery": {
          // ⚠️ THE ID COMES OFF THE ROW'S LINK, not from matching the name. This case
          // said "the cemetery pane isn't built yet" until 2026-10-26 — honest, and
          // unopenable while the row carried only a name. The server now puts
          // `cemetery_id` on that link, and reading it here is what keeps the id in ONE
          // place rather than having the client resolve a name it did not resolve.
          const row = order.order.find((r) => r.label === "Cemetery")
          const id = row?.link?.kind === "cemetery" ? row.link.cemetery_id : undefined
          if (id === undefined) {
            // A name with no link is an order whose cemetery join did not resolve, and
            // no name at all is an order with no cemetery. Different sentences.
            say("miss", row?.value !== undefined
              ? `${row.value} \u00b7 no cemetery record on this order.`
              : "This order has no cemetery on it.")
            return
          }
          openCemetery(id, row?.value)
          return
        }
        case "undo-confirm":
          if (!order.can_undo_confirm) {
            say("miss", `${order.number} is not confirmed.`)
            return
          }
          // ⚠️ IT GOES THROUGH THE PANE'S OWN BUTTON, not a second call to the API. The
          // refusal message, the re-read and the notice all live there, and a parallel
          // path here would be a second copy of the rule the server owns.
          setUndoRequest((prev) => ({ ...prev, [orderId]: (prev[orderId] ?? 0) + 1 }))
          return
      }
    },
    [opas, say],
  )

  /**
   * Opas's one question after an approve, and the two steps that answer it.
   *
   * ⚠️ A SMALL STATE MACHINE RATHER THAN THREE BOOLEANS. `reason` is waiting for words;
   * `rule` is waiting for the office to confirm or retype the sentence the model
   * drafted. A flag per stage would permit both at once, which is not a state this
   * conversation has.
   */
  const [whyAsk, setWhyAsk] = useState<
    | { stage: "reason"; sessionId: string; ask: NonNullable<CaptureState["ask_why"]> }
    | { stage: "rule"; sessionId: string; draft: string }
    | null
  >(null)
  /** Bumped when a rule lands, so an open rulebook pane re-reads itself. */
  const [rulesChanged, setRulesChanged] = useState(0)

  const openRulebook = useCallback(() => {
    opas.openPane({ kind: "rulebook", label: "Rulebook" })
  }, [opas])

  /**
   * Skip the question, silently, and log it as skipped.
   *
   * ⚠️ "NEVER BLOCKS" IS THE WHOLE RULE, so this is fire-and-forget: a failed skip must
   * not stop whatever the person typed instead from being routed. The record is best
   * effort; the person's next request is not.
   */
  const skipWhy = useCallback((sessionId: string) => {
    setWhyAsk(null)
    void answerWhy(sessionId, { scope: "skipped" }).catch(() => {})
  }, [])

  /** Ask for the scope once there is a reason. ⌘1 / ⌘2, a bare digit, or a click. */
  const askScope = useCallback(
    (sessionId: string, reason: string) => {
      const act: Record<string, () => void> = {
        today: () => {
          setWhyAsk(null)
          void answerWhy(sessionId, { reason, scope: "today" })
            .then(() => say("ack", "Noted for today."))
            .catch(() => say("miss", "That did not save."))
        },
        always: () => {
          // ⚠️ THE PANE DOES NOT WAIT ON THE MODEL WITH A SPINNER. The reason is already
          // stored by the time a draft comes back, so a slow or dead model costs the
          // office nothing it typed — and when it is dead the server returns their own
          // words as the draft, which is the dispatch's own fallback.
          setWhyAsk(null)
          void answerWhy(sessionId, { reason, scope: "always" })
            .then((out) => {
              const draft = out.draft ?? reason
              setWhyAsk({ stage: "rule", sessionId, draft })
              say("question", `Rule: “${draft}” — Enter to keep it, or type a different sentence.`)
            })
            .catch(() => say("miss", "That did not save."))
        },
      }
      say("question", "Just today, or always?", {
        options: [
          { id: "today", label: "Just today" },
          { id: "always", label: "Always" },
        ],
        act,
      })
    },
    [say],
  )

  const confirmRule = useCallback(
    (sessionId: string, reason: string, ruleText: string) => {
      setWhyAsk(null)
      void answerWhy(sessionId, { reason, scope: "always", rule_text: ruleText })
        .then(() => {
          setRulesChanged((n) => n + 1)
          // ⚠️ IT SAYS WHERE THE RULE WENT. A confirmation with no destination leaves
          // the office unsure whether anything was kept — and "rules" is how they look.
          say("ack", "In the rulebook. Say “rules” to see it.")
        })
        .catch(() => say("miss", "That did not save."))
    },
    [say],
  )

  const submit = useCallback(async () => {
    const phrase = text.trim()

    // ⚠️ BEFORE THE EMPTY GUARD, because a bare Enter is how the drafted rule is kept.
    // "shown in the reply line for the person to confirm (Enter) or edit (type a new
    // sentence)" — and `submit` returns early on an empty phrase, so a confirm that
    // lived below this line could never fire.
    if (whyAsk?.stage === "rule") {
      const sentence = phrase === "" ? whyAsk.draft : phrase
      setText("")
      confirmRule(whyAsk.sessionId, whyAsk.draft, sentence)
      return
    }

    if (phrase === "" || busy) return
    setBusy(true)
    // ⚠️ IT CLEARS A SENTENCE, NOT A QUESTION, AND THE DISTINCTION IS A BUG I SHIPPED
    // AND A TEST CAUGHT. This was a bare `hush()` — inherited from the old
    // `setSaid(null)`, which could only ever be clearing a hint. `hush()` now also
    // empties `answerActions.current`, so clearing here wiped the outstanding question's
    // ACTIONS before the answer check below could use them. The symptom was precise and
    // silent: typing "hart" matched one option, consumed the phrase, closed the list —
    // and did nothing, because the action map was empty by then.
    if (reply !== null && reply.kind !== "question") hush()
    try {
      // ⚠️ BEFORE EVERYTHING, INCLUDING THE CAPTURE ENTRANCE. "close" is a word about
      // the overlay, not about an order, and it must work while an entry pane holds the
      // bar — which is the one state where every other route is suppressed.
      if (isCloseRequest(phrase)) {
        const closed = closeFrontPane()
        setText("")
        if (!closed) say("miss", "Nothing is open.")
        return
      }

      // ⚠️ ALSO BEFORE THE CAPTURE ENTRANCE, AND FOR THE SAME REASON AS "close". "set
      // my shortcut to control" is a sentence about the keyboard, not about an order,
      // and it has to work while an entry pane holds the bar — which is precisely when
      // the office is looking at the pills and notices the wrong glyph on them.
      //
      // ⚠️ THE WRITE IS REPORTED, NOT ASSUMED. `setCapturePickModifier` deliberately
      // does not swallow its error, so a failed PATCH says so instead of answering
      // "done" and leaving the chord unchanged.
      const wanted = shortcutRequest(phrase)
      if (wanted !== null) {
        setText("")
        try {
          const saved = await setCapturePickModifier(wanted)
          setPickModifier(saved.pick_modifier)
          setPickGlyph(saved.pick_modifier_glyph)
          // ⚠️ THE CONFIRMATION SHOWS THE GLYPH, not the word, because the glyph is
          // what the pills now print and is the thing to check.
          // ⚠️ `"ack"` IS "Opas did something" AND IT FADES, which is right here: the
          // confirmation is a receipt, and the pills themselves now carry the answer
          // on every label. `"question"` would pin a line that needs no reply.
          say("ack", `Pills pick with ${saved.pick_modifier_glyph} now.`)
        } catch {
          say("miss", "Could not save that shortcut.")
        }
        return
      }

      // ⚠️ AN OUTSTANDING QUESTION GETS FIRST REFUSAL ON WHAT WAS TYPED (James's third
      // rule, 2026-10-20): "typing words that match one option ('smith', 'friday', 'the
      // confirmed one'). One match -> chosen. Still ambiguous -> the list narrows and
      // the question stays. ... Typing something unrelated drops the question and
      // treats it as a new request."
      //
      // ⚠️ IT IS BEFORE THE CAPTURE ENTRANCE AND BEFORE EVERY OTHER RULE, because the
      // director is mid-answer and an answer is not a request. `matchAnswer` returning
      // `none` is what hands the phrase on — so an unrelated line is never swallowed.
      const outstanding = reply?.options
      if (outstanding !== undefined && outstanding.length > 0) {
        const match = matchAnswer(outstanding, phrase)
        if (match.kind === "one") {
          setText("")
          answerOption(match.index)
          return
        }
        if (match.kind === "many") {
          // The list narrows and the question stays. The typed text is CLEARED, because
          // the next word the director types is another narrowing and not an addition
          // to the one just consumed.
          const kept = match.indices.map((i) => outstanding[i])
          const act: Record<string, () => void> = {}
          for (const option of kept) {
            const existing = answerActions.current[option.id]
            if (existing !== undefined) act[option.id] = existing
          }
          setText("")
          say("question", `${reply?.text ?? "Which one?"}`, { options: kept, act })
          return
        }
        // `none` — fall through. The question is dropped by whatever handles the
        // phrase, because every branch below calls `say` or `hush`.
        hush()
      }
      // ⚠️ THE CAPTURE ENTRANCE IS CHECKED BEFORE THE CATALOG AND BEFORE THE RESOLVER.
      // "start an order for Hopkins" contains no catalog phrase, but sending it to the
      // vault resolver would resolve "order" against product names and open the wrong
      // thing. The whole line is passed through so the funeral home is captured on the
      // opening keystroke (prototype `:568`).
      if (opensCapture(phrase)) {
        opas.openPane({ kind: "capture", label: "Order", openingLine: phrase })
        setText("")
        return
      }
      // ⚠️ RULE-BASED FIRST. "the catalog" is a fixed phrase and never reaches the resolver.
      if (isCatalogRequest(phrase)) {
        opas.openPane({ kind: "product-list", label: "Catalog" })
        setText("")
        return
      }

      // ⚠️ CONTEXT, AND IT IS GATED ON THE FRONT PANE BEING AN ORDER (James's fourth
      // rule, 2026-10-20). That gate is what keeps every existing phrase working: "how
      // much" and "what's the total" are ALSO order-list phrases, so with a LIST in
      // front they still total the list, and only with an ORDER in front do they answer
      // about that order. One phrase, two readings, decided by what is in front rather
      // than by a mode.
      const intent = contextIntent(phrase)
      if (intent !== null && frontOrder !== null) {
        setText("")
        handleContext(intent, frontOrder.orderId)
        return
      }
      // ⚠️ AND WITH NO ORDER IN FRONT IT ASKS, rather than falling through to the
      // resolver — which is what used to happen, matching no product and opening an
      // unfiltered catalog on "the vault".
      //
      // ⚠️ EXCEPT WHERE THE PHRASE HAS ANOTHER MEANING THAT ALREADY WORKS. "how much" is
      // the order list's own total question; asking "Which order?" instead would break
      // a shipped behaviour to serve a new one. So a context phrase that is also an
      // order-list phrase falls through, and the list answers it.
      if (intent !== null && !isOrderListPhrase(phrase)) {
        setText("")
        if (openOrderPanes.length === 0) {
          say("miss", "No order is open. Try: \u201criverside order\u201d")
          return
        }
        const options: ReplyOption[] = openOrderPanes.map((pane) => {
          const facts = orderFacts.current[pane.salesOrderId!]
          return {
            id: pane.salesOrderId!,
            label: facts?.title ?? "This order",
            ...(facts !== undefined ? { detail: facts.number } : {}),
          }
        })
        const act: Record<string, () => void> = {}
        for (const pane of openOrderPanes) {
          const orderId = pane.salesOrderId!
          act[orderId] = () => {
            opas.raisePane(pane.id)
            handleContext(intent, orderId)
          }
        }
        say("question", "Which order?", { options, act })
        return
      }
      // ⚠️ THE REASON STAGE SITS AFTER THE OUTSTANDING-OPTIONS CHECK AND BEFORE EVERY
      // ROUTE. The person has been asked "why?" and what they type next is either the
      // answer or a change of subject — and the dispatch says the second one wins
      // silently: "Esc, or typing something that's clearly a new request, skips it
      // silently (logged as skipped). Never blocks."
      //
      // ⚠️ "CLEARLY A NEW REQUEST" IS DECIDED BY THE ROUTES THAT ALREADY EXIST, not by a
      // new guess. If the phrase opens a capture, reads as an order-list question, is a
      // close request or asks for the rulebook, it is a request. Anything else is prose,
      // and prose is what a reason is. A fresh predicate here would be a second place
      // deciding what the bar means.
      if (whyAsk?.stage === "reason") {
        const looksLikeARequest =
          opensCapture(phrase) ||
          isOrderListPhrase(phrase) ||
          isCloseRequest(phrase) ||
          opensRulebook(phrase)
        if (looksLikeARequest) {
          skipWhy(whyAsk.sessionId)
          // and fall through: the phrase is routed as what it is
        } else {
          const sessionId = whyAsk.sessionId
          setWhyAsk(null)
          setText("")
          askScope(sessionId, phrase)
          return
        }
      }

      // ⚠️ THE RULEBOOK, BEFORE EVERY NAME RULE. "the rulebook" / "rules" are the
      // dispatch's words and no record should be able to shadow them.
      if (opensRulebook(phrase)) {
        setText("")
        openRulebook()
        say("ack", "The rulebook")
        return
      }

      // ⚠️ AFTER CAPTURE AND THE CATALOG, BEFORE THE RESOLVER. An order question
      // is a structured read, not a product name. A refinement ("only Hopkins")
      // only counts while the order list — or the sales order it opened — is in front.
      const front = opas.panes.find((p) => p.id === opas.frontPaneId)
      const talking = front?.kind === "order-list" || front?.kind === "sales-order"
      if ((talking && isOrderRefinement(phrase)) || isOrderListPhrase(phrase)) {
        const list = opas.panes.find((p) => p.kind === "order-list")
        try {
          const result = await askOrderList({
            phrase,
            question: talking ? list?.orderQuestion : undefined,
            // The decision log's only unreachable-from-the-server fact.
            ...(front ? { front: front.kind } : {}),
          })
          settleOrderAnswer(result, phrase)
        } catch {
          say("miss", ORDER_TRY)
        }
        setText("")
        return
      }
      const r = await resolvePhrase(phrase)
      const route = routeResolution(r)
      if (route.kind === "product") {
        opas.openPane({
          kind: "product",
          label: "Product",
          variantTemplateId: route.variantTemplateId,
        })
      } else if (route.kind === "numbered-pick") {
        // ⚠️ A NUMBERED PICK, not a filtered list and not a guess. The discriminators say
        // what would narrow it, which is the only thing that tells the director WHY they
        // are being asked.
        //
        // ⚠️ AND IT NO LONGER OPENS A PANE. This used to open a `product-list` pane with
        // `candidateIds`, which rendered the same numbered list inside a floating card
        // and stayed open after the choice was made. The options now sit with the
        // question above the bar.
        const options: ReplyOption[] = route.candidates.map((c) => ({
          id: c.variant_template_id,
          label: c.name ?? c.variant_template_id,
          ...(c.option_label !== undefined ? { detail: c.option_label } : {}),
        }))
        const act: Record<string, () => void> = {}
        for (const c of route.candidates) {
          act[c.variant_template_id] = () =>
            opas.openPane({
              kind: "product",
              label: "Product",
              variantTemplateId: c.variant_template_id,
            })
        }
        say(
          "question",
          route.discriminators.length > 0
            ? `Which one? They differ by ${route.discriminators.join(", ")}.`
            : "Which one?",
          { options, act },
        )
      } else {
        // ⚠️ THE "WHOLE CATALOG" FALLBACK IS GONE, BY RULING (James, 2026-10-23). It
        // opened a `product-list` pane carrying `unmatchedPhrase`, which rendered every
        // vault the platform sells under the heading "Nothing matched … The whole
        // catalog:". He typed "anything going to st. marys coming up?" and got the
        // catalogue. A miss is one honest line above the bar and nothing opened.
        //
        // ⚠️ AND BEFORE GIVING UP, THE SERVER GETS THE PHRASE — which is the other half
        // of the same ruling: "choosing where a request goes is exactly the job the
        // model should do, so it has to sit at the front, not behind one pane." The
        // rules had already decided this was not an order phrase (no "order" word), so
        // the door was never consulted. Now the last resort before a miss is
        // `/order-list/ask`, where the engine tries its own rules and then the model
        // door, validates whatever comes back, and returns `unrecognized` on any
        // failure. One door, one validator, no second model path.
        const front = opas.panes.find((p) => p.id === opas.frontPaneId)
        let routed = false
        try {
          const result = await askOrderList({
            phrase,
            ...(front ? { front: front.kind } : {}),
          })
          // ⚠️ `unrecognized` IS NOT ROUTING — it is the server agreeing it does not
          // know, which is the miss. Anything else opened or asked something.
          if (result.kind !== "unrecognized") {
            settleOrderAnswer(result, phrase)
            routed = true
          }
        } catch {
          // a transport failure is not an answer; fall through to the honest miss
        }
        if (!routed) say("miss", NOT_SURE)
      }
      setText("")
    } finally {
      setBusy(false)
      // ⚠️ ONE PLACE, IN THE `finally`, RATHER THAN AT EVERY `return` ABOVE. `submit`
      // has eleven exits and a focus call on each would be eleven chances to miss one
      // — which is exactly how the bar lost the cursor in the first place.
      focusBar()
    }
  }, [
    text, busy, opas, settleOrderAnswer, closeFrontPane, say, hush,
    reply, answerOption, frontOrder, openOrderPanes, handleContext, focusBar,
    // ⚠️ CORRECTED AFTER A BREAK TEST FALSIFIED THE REASON I FIRST GAVE. I wrote that
    // omitting `whyAsk` "would make every piece work and the feature do nothing" — a
    // stale closure seeing `null` forever. Removing it turns NOTHING red, and the
    // ranking is why: `text` is already a dependency and changes on every keystroke, so
    // `submit` is rebuilt constantly and picks up fresh state regardless.
    //
    // They stay listed because the equivalence is a property of `text` being here, not
    // of this line — drop `text` one day (a ref, say) and the stale-closure bug becomes
    // real while a comment explaining why it could not happen sits above it. Correct
    // and NOT load-bearing is a different claim from load-bearing, and the difference
    // is what a reader needs.
    whyAsk, askScope, confirmRule, skipWhy, openRulebook,
  ])

  /** The panes on the desk. Order-list and sales-order panes move to the mobile track
   *  below `narrow`, so they are not on the desk at all there. */
  const visible = opas.panes.filter(
    (pane) => !(narrow && (pane.kind === "order-list" || pane.kind === "sales-order")),
  )

  /** First-free-space slots for the anchored info panes, computed in pane order.
   *
   * ⚠️ DRAGGED PANES ARE OBSTACLES, NOT CANDIDATES. A pane the director has moved keeps
   * its place (`placements[id].anchored === false`), and a new pane must not be placed
   * under it — so it goes into `dragged` and is never given a slot.
   *
   * ⚠️ AN ENTRY PANE IS NEITHER. It anchors to the bar at the bottom right and is not in
   * the anchored band, so it neither takes a slot nor blocks one.
   */
  const dragged = visible
    .filter((pane) => {
      const placed = opas.placements[pane.id]
      return placed !== undefined && !placed.anchored
    })
    .map((pane) => ({
      left: opas.placements[pane.id].x,
      width: paneWidthPx(pane.kind, stageWidth),
    }))
  const slots = anchoredSlots(
    visible
      .filter((pane) => {
        const placed = opas.placements[pane.id]
        return !isEntryPane(pane.kind) && (placed === undefined || placed.anchored)
      })
      .map((pane) => ({ id: pane.id, width: paneWidthPx(pane.kind, stageWidth) })),
    dragged,
    stageWidth,
  )

  // ⚠️ The sphere is admin-only for now. Not rendering is the whole gate: a hidden-but-
  // mounted sphere would still answer keyboard and pointer events.
  if (!isAdmin || !opas.canRender) return null

  return (
    <>
      {/* VEIL — blur(7px) saturate(.9) and rgba(6,6,6,.38) are the prototype's values.
          pointerdown, not click, also the prototype's. */}
      <div
        data-testid="opas-veil"
        aria-hidden="true"
        onPointerDown={() => {
          // ⚠️ THE VEIL IS A CLOSE, so it ends the capture — the accidental
          // click-away James was warned about and accepted.
          endEntryCaptures()
          opas.tuck()
        }}
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 30,
          background: "rgba(6,6,6,.38)",
          backdropFilter: "blur(7px) saturate(.9)",
          WebkitBackdropFilter: "blur(7px) saturate(.9)",
          opacity: opas.isOpen ? 1 : 0,
          pointerEvents: opas.isOpen ? "auto" : "none",
          transition: "opacity .4s cubic-bezier(0.4,0,0.4,1)",
        }}
      />

      {/* PANES — above the veil. `tucked` hides without unmounting, so the session
          survives: opacity 0 / pointer-events none, exactly the prototype's `.win.tucked`. */}
      <div data-testid="opas-desk" style={{ position: "fixed", inset: 0, zIndex: 35, pointerEvents: "none" }}>
        {visible.map((pane, i) => {
          const placed = opas.placements[pane.id]
          const slot = slots[pane.id]
          const isFront = opas.frontPaneId === pane.id
          // ⚠️ COMPUTED ONCE AND USED BY BOTH THE STYLE AND THE ATTRIBUTE, which is
          // the only arrangement a test can rely on. Two separate
          // `isEntryPane(...) ? A : B` expressions — one for `width`, one for
          // `data-pane-width` — are free to diverge, and a break test narrowing only
          // the style produced NO RED twice: first when the attribute held the word
          // "bar", then again when it held the constant but computed it itself. One
          // binding makes the attribute a report of the width rather than a second
          // opinion about it.
          const paneWidth = isEntryPane(pane.kind)
            ? BAR_WIDTH
            : pane.kind === "order-list"
              ? ORDER_LIST_WIDTH
              : INFO_WIDTH
          return (
          <div
            key={pane.id}
            data-testid={`opas-pane-${pane.id}`}
            data-tucked={opas.isOpen ? "false" : "true"}
            data-focused={isFront ? "true" : "false"}
            data-pane-width={paneWidth}
            onPointerDown={(e) => {
              // The prototype's order: raise FIRST, unconditionally, then try to drag.
              opas.raisePane(pane.id)
              dragStart(e, pane.id, placed, i)
            }}
            // ⚠️ A CLICK INSIDE A PANE HANDS THE CURSOR BACK TO THE BAR (James, item 1:
            // "click inside a pane"). ON `click`, NOT `pointerdown`: stealing focus on
            // pointerdown would move it before the button under the pointer had received
            // its own click, and a button that never fires is worse than a lost cursor.
            //
            // ⚠️ AND NOT WHEN THE CLICK LANDED IN AN EDITABLE FIELD, which is the
            // ruling's one exception. `closest` rather than a tag test so a
            // contenteditable's children count.
            onClick={(e) => {
              const el = e.target as HTMLElement | null
              if (el?.closest("input, textarea, select, [contenteditable='true']")) return
              focusBar()
            }}
            style={{
              ...GLASS,
              position: "absolute",
              // ⚠️ A DRAGGED PANE USES left/top; AN ANCHORED ONE CASCADES FROM right/top.
              // Mixing them is what keeps "new panes still cascade" true after another pane
              // has been moved: `anchored` decides which pair applies, per pane.
              // ⚠️ AN ENTRY PANE GROWS FROM THE BAR, AN INFO PANE CASCADES FROM THE
              // TOP RIGHT, and the difference is the pane TYPE rather than a per-pane
              // setting (`pane-mode.ts`). The bar is a pill at right 24 / bottom 24,
              // so an entry pane is anchored to its right edge and sits directly above
              // it — `bottom: 96` clears the 30px orb plus the pill's padding with a
              // gap. It comes out of the thing the director is typing into, which is
              // the whole point: the order appears where the words are going.
              // ⚠️ AN ENTRY PANE SITS ON THE BAR: same right edge, and a bottom of
              // 24 (the bar's own offset) plus the bar's MEASURED height, so the two
              // touch. `bottom: 96` was a guess against a ~46px bar and left it
              // floating — asked for last round and still wrong, which is why the
              // height is now measured rather than assumed.
              ...(placed !== undefined && !placed.anchored
                ? { left: placed.x, top: placed.y }
                : isEntryPane(pane.kind)
                  ? {
                      right: 24,
                      // ⚠️ THE PILLS GET THEIR OWN ROW (James, 2026-10-27): "The pills
                      // row takes its own space: pane, then pills, then bar, with
                      // nothing overlapping at any width." `guidedH` already carries
                      // its own gap, and is 0 when there are no pills — which keeps
                      // the pane TOUCHING the bar in that case, as asked for last
                      // round ("`bottom: 96` was a guess … and left it floating").
                      //
                      // ⚠️ THE ARITHMETIC IS A SHARED FUNCTION so the overlap test can
                      // read the real one rather than a copy of it.
                      bottom: paneBottomPx(barH || 46, guidedH),
                    }
                  // ⚠️ FIRST FREE SPACE, NOT AN INDEX CASCADE (James, 2026-10-19: "A new
                  // pane is placed in the first free space, not on top of another"). This
                  // read `{ right: 24 + i * 18, top: 72 + i * 22 }` — so a second pane sat
                  // 18px left and 22px down from the first and covered nearly all of it,
                  // on a screen with room for both side by side. `pane-placement.ts`
                  // scans for a gap; `slot` is always defined for an anchored info pane
                  // and the `right/top` fallback is the one render where it is not (a
                  // kind that is neither entry nor in `slots`, which cannot happen today
                  // and would otherwise be a pane at 0,0).
                  : slot !== undefined
                    ? { left: slot.left, top: slot.top }
                    : { right: RIGHT_ANCHOR, top: TOP_ANCHOR }),
              zIndex: opas.zOf(pane.id),
              cursor: "grab",
              touchAction: "none",
              // `.win.focused` from the prototype: a stronger shadow on the front pane, and
              // the others dimmed to .8 rather than hidden.
              boxShadow: isFront
                ? "inset 0 1px 0 rgba(255,255,255,.24),inset 0 0 0 1px rgba(255,255,255,.10)," +
                  "inset 0 -1px 0 rgba(0,0,0,.45),0 44px 100px rgba(0,0,0,.65),0 14px 32px rgba(0,0,0,.45)"
                : GLASS.boxShadow,
              opacity: opas.isOpen ? (isFront ? 1 : 0.8) : 0,
              // ⚠️ THE BAR'S WIDTH FOR AN ENTRY PANE, by ruling — the bar is
              // `min(600px, calc(100vw - 48px))` and the pane was 390px, so it was
              // visibly narrower than the thing it grows out of.
              //
              // ⚠️ THE VALUE IS ALSO ON THE ELEMENT AS `data-pane-width`, BECAUSE
              // JSDOM DROPS `min()`. Its CSS parser rejects the function outright, so
              // `style.width` reads as the empty string and no test can assert this
              // line.
              //
              // ⚠️ THE ATTRIBUTE CARRIES THE WIDTH ITSELF, NOT THE WORD "bar", AND
              // THAT DISTINCTION IS WHY A BREAK TEST CAUGHT IT. It first held
              // `isEntryPane(...) ? "bar" : "info"` — derived from the SAME condition
              // as the width — so narrowing the pane back to 390px changed the width
              // and left the attribute saying "bar", and the test passed. An
              // attribute computed from the same input as the thing it describes is
              // not evidence about it.
              width: paneWidth,
              // ⚠️ NO SCROLL CONTAINER ON AN ENTRY PANE, EVER, BY RULING. The
              // `maxHeight` + `overflowY: auto` pair is what let the pane scroll and
              // what let the browser AUTO-SCROLL a captured row out of view when
              // focus moved — James watched Hopkins disappear upward. Ten rows in
              // two columns fit above the bar at 800px tall, which is what makes
              // removing the container safe rather than merely desirable.
              //
              // ⚠️ INFO PANES KEEP THEIRS. A catalog list is unbounded in principle
              // and has to be scrollable; an order has exactly ten rows.
              ...(isEntryPane(pane.kind)
                ? { overflow: "visible" }
                : { maxHeight: "calc(100vh - 160px)", overflowY: "auto" as const }),
              borderRadius: 22,
              pointerEvents: opas.isOpen ? "auto" : "none",
              // ⚠️ THE ORIGIN IS WHAT MAKES "GROWS FROM THE BAR" VISIBLE. With the
              // default centre origin, the same scale animation reads as a pane fading
              // in place; anchored bottom-right it reads as unfolding out of the bar.
              // Info panes keep the top-right origin they cascade from.
              transformOrigin: isEntryPane(pane.kind) ? "100% 100%" : "100% 0%",
              transform: opas.isOpen ? "none" : "translateY(12px) scale(.96)",
              transition: "opacity .4s cubic-bezier(0.2,0,0.1,1), transform .45s cubic-bezier(0.2,0,0.1,1)",
            }}
          >
            {/* ⚠️ NO LONGER THE DRAG HANDLE — the whole pane is, per the prototype. The
                header keeps `cursor: grab` as the affordance, because it is the one place
                with no interactive child, so it is where a drag is guaranteed to start. */}
            <div
              data-testid={`opas-pane-handle-${pane.id}`}
              style={{
                display: "flex", alignItems: "center", gap: 10, padding: "14px 10px 6px 20px",
                userSelect: "none",
              }}
            >
              <span style={{ fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#5e5e5e" }}>
                {pane.label}
              </span>
              <button
                type="button"
                aria-label="Close pane"
                data-testid={`opas-pane-close-${pane.id}`}
                onClick={() => {
                  // ⚠️ AN ENTRY PANE'S CLOSE BUTTON ENDS THE CAPTURE; an info pane's
                  // just closes the pane. Same control, two meanings, because one of
                  // them is somebody's order and the other is a catalog list.
                  // ⚠️ THE PANE CLOSES FIRST, AND THE SERVER IS TOLD AFTERWARDS.
                  // Ordered the other way, anything that threw on the way to the
                  // network — a missing export, an offline tab — left the pane
                  // OPEN, and since an entry pane holds the bar in entry mode that
                  // tab could no longer start an order. That is the shape of the
                  // bug James walked into, and it cost a test run here to see it.
                  opas.closePane(pane.id)
                  if (isEntryPane(pane.kind)) {
                    setText("")
                    if (pane.captureSessionId !== undefined) {
                      void abandonCapture(pane.captureSessionId)
                    }
                  }
                }}
                style={{
                  marginLeft: "auto", width: 26, height: 26, borderRadius: "50%", border: 0,
                  background: "rgba(255,255,255,.06)", color: "#9a9a9a", cursor: "pointer",
                }}
              >
                ×
              </button>
            </div>
            <div style={{ padding: "0 20px 20px" }}>
              {pane.kind === "product-list" ? (
                <ProductListPane
                  onOpenProduct={(id) => {
                    // ⚠️ NO `setPendingPick(null)` ANY MORE. This pane is no longer a
                    // pick, so there is no pending question for it to cancel — the only
                    // thing that raises one is `say(…, {options})`, above the bar.
                    opas.openPane({ kind: "product", label: "Product", variantTemplateId: id })
                    focusBar()
                  }}
                />
              ) : pane.kind === "capture" ? (
                <CapturePane
                  openingLine={pane.openingLine}
                  prefill={pane.capturePrefill}
                  // ⚠️ THE QUESTION GOES TO THE BAR, NOT THE PANE. "one line above the
                  // bar" (James) — and a question drawn inside the pane would vanish
                  // with it when tucked, taking the answer with it.
                  onAskWhy={(sessionId, ask) => {
                    setWhyAsk({ stage: "reason", sessionId, ask })
                    say("question", ask.prompt)
                  }}
                  onSessionStarted={(id) => opas.setCaptureSession(pane.id, id)}
                  text={opas.entryText[pane.id] ?? ""}
                  onStatus={(st) => reportStatus(pane.id, st)}
                  caretFieldIds={fieldsAtCaret(
                    status?.spans,
                    status?.spansForText,
                    opas.entryText[pane.id] ?? "",
                    caret,
                  )}
                  pickRequest={pickRequest[pane.id]}
                  answerRequest={answerRequest[pane.id]}
                  // ⚠️ THE OUTLINED ROW AND THE QUESTION ABOVE THE BAR READ THE SAME
                  // VALUE. Passing the server's field down rather than letting the
                  // pane re-derive it is what stops the sentence and the outline
                  // naming different fields.
                  askedFieldId={askedField}
                  onAskAgain={askAgain}
                  focusRequest={focusRequest[pane.id]}
                  onApproved={(order) => onApproved(pane.id, order)}
                  completeRequest={completeRequest[pane.id]}
                />
              ) : pane.kind === "order-list" && pane.orderSnapshot ? (
                <OrderListPane
                  snapshot={pane.orderSnapshot}
                  // ⚠️ THE FRONT ORDER PANE, NOT THE FIRST ONE. Several can be open now
                  // that panes chain, and `find` would highlight whichever was opened
                  // earliest rather than the one the director is looking at.
                  selectedId={
                    opas.panes.find(
                      (p) => p.kind === "sales-order" && p.id === opas.frontPaneId,
                    )?.salesOrderId
                    ?? opas.panes.filter((p) => p.kind === "sales-order").at(-1)?.salesOrderId
                  }
                  onOpenOrder={openSalesOrder}
                  onRemovePill={(pillId) => void removeOrderPill(pane.id, pillId)}
                  onAskHint={() => say("ack", ORDER_CHANGE)}
                />
              ) : pane.kind === "sales-order" && pane.salesOrderId ? (
                <SalesOrderPane
                  orderId={pane.salesOrderId}
                  // ⚠️ THE VAULT OPENS THE EXISTING PRODUCT PANE, which is the chain the
                  // dispatch is testing ("Its vault opens the Product Pane, which already
                  // exists"). `openPane` dedupes, so opening the same vault from two
                  // different orders focuses one pane rather than stacking two.
                  onOpenProduct={(id) =>
                    opas.openPane({ kind: "product", label: "Product", variantTemplateId: id })
                  }
                  // The other half of the walk: the funeral home link comes back to the
                  // Customer Pane, and `openPane` dedupes so it focuses the open one.
                  onOpenCustomer={openCustomer}
                  // ⚠️ AND THE CEMETERY ROW, LIVE SINCE 2026-10-26. This is step 2 of
                  // James's walk — cemetery, an order, then back to the cemetery — and
                  // `openPane` dedupes on `cemetery:<id>`, so it focuses the St. Mary's
                  // already open rather than putting a second one on the desk.
                  //
                  // ⚠️ THE MOBILE MOUNT BELOW GETS NEITHER THIS NOR `onOpenCustomer`,
                  // which is pre-existing and left alone deliberately: on a phone the
                  // order panes live in their own track and an info pane opened from
                  // there would land on a desk that is not on screen. Matching the
                  // customer link's treatment exactly rather than fixing half of it.
                  onOpenCemetery={openCemetery}
                  // ⚠️ THE ORDER IS REPORTED UP so the bar can answer "when's the
                  // service" from it without opening anything.
                  onLoaded={(order) => { orderFacts.current[order.id] = order }}
                  undoRequest={undoRequest[pane.salesOrderId]}
                />
              ) : pane.kind === "customer" && pane.customerId ? (
                <CustomerPane
                  customerId={pane.customerId}
                  // The walk: open a customer, open one of its orders, and the funeral
                  // home link on that order comes back here — to this same pane.
                  onOpenOrder={openSalesOrder}
                  onNewOrder={startOrderFor}
                  onLoaded={(c) => { customerFacts.current[c.id] = c }}
                />
              ) : pane.kind === "cemetery" && pane.cemeteryId ? (
                <CemeteryPane
                  cemeteryId={pane.cemeteryId}
                  // The walk James gave with the slice: open the cemetery, open one of
                  // its orders, and that order's cemetery link comes back HERE — to this
                  // same pane, because `pane-identity` gives a cemetery an identity.
                  onOpenOrder={openSalesOrder}
                  onOpenCustomer={openCustomer}
                  onOpenCemetery={openCemetery}
                  onLoaded={(c) => { cemeteryFacts.current[c.id] = c }}
                />
              ) : pane.kind === "rulebook" ? (
                <RulebookPane
                  refresh={rulesChanged}
                  // ⚠️ NO `onOpenDecision` YET, DELIBERATELY. A rule's provenance is a
                  // DECISION row, and nothing opens one — the decision log has no pane.
                  // Passing a handler that could not resolve would be the dead click
                  // the cemetery row spent two weeks avoiding; the pane renders the
                  // change as plain text without one.
                />
              ) : pane.kind === "product" ? (
                <ProductPane variantTemplateId={pane.variantTemplateId!} />
              ) : null}
            </div>
          </div>
          )
        })}
      </div>

      {narrow && opas.panes.some((p) => p.kind === "order-list" || p.kind === "sales-order") && (
        <div style={{ position: "fixed", left: 0, right: 0, bottom: 88, zIndex: 40, pointerEvents: opas.isOpen ? "auto" : "none" }}>
          <div
            data-testid="opas-order-track"
            style={{
              display: "flex",
              gap: 8,
              overflowX: "auto",
              scrollSnapType: "x mandatory",
              padding: "0 8px 8px",
              opacity: opas.isOpen ? 1 : 0,
            }}
          >
            {opas.panes.filter((p) => p.kind === "order-list" || p.kind === "sales-order").map((pane) => (
              <div
                key={pane.id}
                data-testid={`opas-pane-${pane.id}`}
                data-tucked={opas.isOpen ? "false" : "true"}
                data-focused={opas.frontPaneId === pane.id ? "true" : "false"}
                data-pane-width={pane.kind === "order-list" ? ORDER_LIST_WIDTH : INFO_WIDTH}
                onPointerDown={() => opas.raisePane(pane.id)}
                style={{
                  ...GLASS,
                  flex: "0 0 calc(100vw - 16px)",
                  scrollSnapAlign: "center",
                  maxHeight: "68vh",
                  overflowY: "auto",
                  borderRadius: 22,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 10px 6px 20px" }}>
                  <span style={{ fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#5e5e5e" }}>
                    {pane.label}
                  </span>
                  <button
                    type="button"
                    aria-label="Close pane"
                    data-testid={`opas-pane-close-${pane.id}`}
                    onClick={() => opas.closePane(pane.id)}
                    style={{
                      marginLeft: "auto", width: 26, height: 26, borderRadius: "50%", border: 0,
                      background: "rgba(255,255,255,.06)", color: "#9a9a9a", cursor: "pointer",
                    }}
                  >
                    ×
                  </button>
                </div>
                <div style={{ padding: "0 20px 20px" }}>
                  {pane.kind === "order-list" && pane.orderSnapshot ? (
                    <OrderListPane
                      layout="phone"
                      snapshot={pane.orderSnapshot}
                      selectedId={opas.panes.find((p) => p.kind === "sales-order")?.salesOrderId}
                      onOpenOrder={openSalesOrder}
                      onRemovePill={(pillId) => void removeOrderPill(pane.id, pillId)}
                      onAskHint={() => say("ack", ORDER_CHANGE)}
                    />
                  ) : pane.kind === "sales-order" && pane.salesOrderId ? (
                    <SalesOrderPane
                      orderId={pane.salesOrderId}
                      onOpenProduct={(id) =>
                        opas.openPane({
                          kind: "product", label: "Product", variantTemplateId: id,
                        })
                      }
                      onLoaded={(order) => { orderFacts.current[order.id] = order }}
                      undoRequest={undoRequest[pane.salesOrderId]}
                    />
                  ) : null}
                </div>
              </div>
            ))}
          </div>
          {opas.panes.filter((p) => p.kind === "order-list" || p.kind === "sales-order").length > 1 && (
            <div data-testid="opas-order-track-dots" style={{ display: "flex", justifyContent: "center", gap: 6, paddingBottom: 4 }}>
              {opas.panes.filter((p) => p.kind === "order-list" || p.kind === "sales-order").map((pane) => (
                <span
                  key={pane.id}
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: opas.frontPaneId === pane.id ? "#f2f2f2" : "rgba(255,255,255,.28)",
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* COMMAND LINE — glass pill at the sphere's corner. */}
      {opas.isOpen && (
        <div
          ref={barRef}
          data-testid="opas-command-line"
          /* ⚠️ OBSERVABLE BECAUSE THE INSTRUMENTS WERE NOT. Diagnosing the ghost, both
             resource-timing and the server access log reported ZERO requests for calls
             that demonstrably happened — an empty list from a blind instrument reads
             exactly like a true absence. The state says so directly instead. */
          data-vocab={vocab.length}
          style={{
            ...GLASS, position: "fixed", zIndex: 44, right: 24, bottom: 24,
            width: BAR_WIDTH, borderRadius: 28, padding: "6px 8px 6px 10px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span
              aria-hidden="true"
              style={{
                flex: "none", width: 30, height: 30, borderRadius: "50%",
                background: "radial-gradient(circle at 36% 30%,#4a4a4a,#111 70%)",
                boxShadow: "0 0 12px 1px rgba(138,164,189,.35)",
              }}
            />
            {/* ⚠️ ONE INPUT, TWO JOBS, AND WHICH ONE IS DECIDED BY THE PANE TYPE IN
                FRONT — not by a mode the director has to set or notice. An entry pane
                in front makes this that order's text field; otherwise it is the
                request line. `pane-mode.ts` owns the classification. */}
            <MirrorStack>
              <CaptureMirror
                value={entryMode ? entryValue : text}
                mirrorRef={mirrorRef}
                spans={entryMode ? status?.spans : undefined}
                spansForText={entryMode ? status?.spansForText : undefined}
                litFieldIds={entryMode ? status?.hoveredFieldIds : undefined}
                ghostSuffix={ghost?.suffix ?? null}
              />
            <textarea
              ref={inputRef}
              rows={1}
              data-testid="opas-input"
              // ⚠️ THE OS MUST NOT MARK UP WHAT THE DIRECTOR TYPES HERE. James's
              // 2026-10-20 screenshot showed a red dotted underline beneath "hopk
              // monti thursday", and the engine could not have drawn it: measured on
              // production, that span came back `captured` for `service_date` and
              // `unrecognized` was empty — and the mirror's unrecognized mark is a
              // GREY dotted underline, never red. macOS spell check is what it was:
              // "hopk" and "monti" are not words, and a lowercase "thursday" is
              // flagged too. So the bar said "not a word" about an abbreviation Opas
              // had just understood, in the same visual language Opas uses for "not
              // understood" — two different claims, one underline.
              //
              // ⚠️ THE PROTOTYPE HAD IT OFF AND WE DID NOT COPY THAT.
              // `2026-10-01-opas-overlay.html` carries `spellcheck="false"` and
              // `autocomplete="off"` on its own input; measured rather than assumed.
              //
              // ⚠️ ALL FOUR, BECAUSE ONE IS NOT ENOUGH ON A TOUCH KEYBOARD.
              // `spellCheck` stops the underline; autocorrect would REWRITE "monti"
              // to a real word mid-sentence, and autocapitalize would send "Hopk" to
              // an engine whose vocabulary match is case-insensitive but whose
              // decedent-name rule looks for capitalised words.
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              autoComplete="off"
              data-entry-mode={entryMode ? "true" : "false"}
              value={entryMode ? entryValue : text}
              onChange={(e) => {
                if (entryMode && entryPane !== undefined) {
                  opas.setEntryText(entryPane.id, e.target.value)
                } else {
                  setText(e.target.value)
                }
              }}
              // ⚠️ THE CARET FOLLOWS THE VALUE, NOT ONLY THE KEYBOARD. Tracked from
              // select/click/keyUp alone it misses every way the text changes without
              // a key coming back up: paste, IME, undo, autofill. The ghost needs the
              // caret at the end, so a stale caret means no completion at all.
              onInput={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
              onSelect={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
              onClick={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
              onKeyUp={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
              onBlur={() => setCaret(null)}
              onKeyDown={(e) => {
                // ⚠️ TAB ACCEPTS THE GHOST AND NEVER LEAVES THE BAR WHILE CAPTURING,
                // by ruling. `preventDefault` is the whole mechanism: without it the
                // browser moves focus to the next control and the director is typing
                // into nothing. It is called even when there is NO ghost, because a
                // Tab that sometimes moves focus and sometimes does not is worse than
                // either — the bar is the only input while an order is open.
                if (e.key === "Tab" && entryMode) {
                  e.preventDefault()
                  if (ghost && entryPane !== undefined) {
                    opas.setEntryText(entryPane.id, acceptGhost(entryValue, ghost))
                  }
                  return
                }
                if (e.key !== "Enter") return
                // ⚠️ ENTER FINISHES THE ORDER, BY RULING (James, 2026-10-14),
                // SUPERSEDING "Enter is a hard no-op while capturing". It is the
                // reservation that ruling kept open, now spent on the obvious thing:
                // while capturing it does what Complete order does, and on the
                // Review it approves.
                //
                // ⚠️ AN ACCIDENTAL ENTER MID-SENTENCE CANNOT CREATE AN ORDER, and
                // that is the property that makes this safe rather than the keypress
                // being rare. Complete never approves from `capturing` — it shows
                // the summary or lights up what is missing — so the worst a stray
                // Enter can do is show the director their own order.
                //
                // ⚠️ `preventDefault` IS STILL THE MECHANISM and matters more now
                // that the bar is a TEXTAREA: without it the keypress also inserts a
                // newline into the middle of the order text.
                if (entryMode) {
                  e.preventDefault()
                  requestComplete()
                  return
                }
                // ⚠️ ENTER STARTS ANOTHER ORDER IN THE DONE STATE (James, 2026-10-28
                // clause 2), AND ONLY WITH THE BAR EMPTY. With words in the bar Enter
                // belongs to `submit()` — that is how "orders this month" and a typed
                // order both work, and the dispatch says every other bar use is
                // unchanged.
                if (justApproved && text.trim() === "") {
                  e.preventDefault()
                  startBlankCapture()
                  return
                }
                void submit()
              }}
              // ⚠️ A PLAIN PROMPT IN ENTRY MODE SINCE 2026-10-20, BY RULING. It was
              // `status?.placeholder` — the capture question — and a textarea shows its
              // placeholder ONLY WHEN EMPTY, while `placeholderFor` returned the
              // question only when the text was NON-empty. Four of its nine possible
              // strings were therefore unreachable on screen, the server's
              // `next_question` among them. The question is in the reply line now.
              placeholder={entryMode ? ENTRY_PLACEHOLDER : "orders · the catalog"}
              aria-label={entryMode ? "Say what the director said" : "Ask Opas"}
              style={{
                // ⚠️ EVERY TYPOGRAPHIC PROPERTY COMES FROM `MIRROR_BOX` SINCE 2026-10-16, AND
                // NONE IS REPEATED HERE. The mirror behind this textarea must break lines in
                // exactly the same places; two style blocks that happen to match today drift
                // the first time one of them is tuned, and the symptom is a tint sliding a
                // character sideways on the last line of a long order. `padding`, `border`,
                // `fontFamily`, `fontSize`, `lineHeight` and `maxHeight` all moved into it.
                ...MIRROR_BOX,
                ...MIRROR_TEXTAREA_EXTRA,
                width: "100%",
                color: "#f2f2f2",
                outline: "none",
                // ⚠️ THE BAR GROWS INSTEAD OF SCROLLING. `resize: none` keeps the drag handle
                // off a chrome element; `overflow: hidden` matters because the height is set
                // from `scrollHeight` and a visible scrollbar would feed its own width back
                // into the measurement.
                resize: "none",
                overflow: "hidden",
              }}
            />
            </MirrorStack>
          </div>
        </div>
      )}

      {/* ── GUIDED CAPTURE — the question to the LEFT of the bar, pills ABOVE it ───
          James's dispatch of 2026-10-27, clause 1. The geometry is the prototype's
          `.dock` grid, computed from the bar's own fixed box rather than re-parenting
          the bar into a grid — see `GuidedQuestion.tsx` for why.

          ⚠️ IT RENDERS OUTSIDE THE ENTRY PANE, which is the whole point of putting it
          here. The pane can be tucked; the question and its answers must not go with
          it, exactly as the question itself was moved out of the pane on 2026-10-20. */}
      {opas.isOpen && guided !== null && (
        <GuidedQuestion
          question={guided.question}
          hint={guided.hint}
          fieldId={guided.fieldId}
          pills={guided.pills}
          cremation={guided.cremation}
          barHeight={barH || 46}
          barWidth={BAR_WIDTH}
          stacked={stageWidth < STACK_BELOW_PX}
          // ⚠️ THE BAR'S EMPTINESS DECIDES WHETHER A BARE DIGIT ANSWERS. Mid-phrase a
          // digit is part of what is being typed — "monticello 28" names a size.
          barIsEmpty={text.trim() === ""}
          questionTakesNumbers={questionTakesNumbers(guided.fieldId)}
          pickModifier={pickModifier}
          pickModifierGlyph={pickGlyph}
          onAnswer={answerGuided}
          onAct={actGuided}
          onHeightAbove={setGuidedH}
        />
      )}

      {/* ── OPAS'S VOICE — one place, directly above the bar ─────────────────
          ⚠️ IT MOVED OUT OF THE BAR ON 2026-10-20. It was a line INSIDE the glass pill,
          below the input (`padding: "0 0 6px 52px"`), which is where a hint can live and
          a question cannot: a question needs options under it, and the pill is the thing
          the options have to sit above.

          ⚠️ THE GEOMETRY IS THE PROTOTYPE'S `placeSaid`, not a new choice:
            function placeSaid(){const r=line.getBoundingClientRect();
                                 said.style.bottom=(innerHeight-r.top+10)+'px'}
          The bar sits at `bottom: 24` and is `barH` tall, so its top edge is
          `24 + barH` from the bottom and this sits `REPLY_GAP_ABOVE_BAR` above that.
          Computed rather than measured, because `barH` is already observed by a
          ResizeObserver for the entry pane and a second measurement of one thing is a
          second thing to disagree.

          ⚠️ AND `align-items: flex-end`, ALSO THE PROTOTYPE'S, so the sentence and the
          options hug the bar's right edge rather than stretching across it. */}
      {opas.isOpen && reply !== null && (
        <div
          data-testid="opas-reply"
          data-reply-kind={reply.kind}
          style={{
            position: "fixed",
            zIndex: 44,
            right: 24,
            bottom: 24 + (barH || 46) + REPLY_GAP_ABOVE_BAR,
            width: BAR_WIDTH,
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: 6,
            pointerEvents: "none",
          }}
        >
          {/* ⚠️ THE SENTENCE IS A CHIP, from the prototype's `.chip`, and it is ABOVE the
              options — `show(chips)` writes the chips and then appends `.pick`. */}
          <span
            data-testid="opas-said"
            role="status"
            aria-live="polite"
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "3px 10px",
              borderRadius: 999,
              background: "rgba(40,40,40,.55)",
              backdropFilter: "blur(16px)",
              WebkitBackdropFilter: "blur(16px)",
              border: "1px solid rgba(255,255,255,.12)",
              fontSize: 12,
              color: "#f2f2f2",
              boxShadow: "0 8px 20px rgba(0,0,0,.45)",
              maxWidth: "100%",
            }}
          >
            {reply.text}
          </span>

          {reply.options !== undefined && reply.options.length > 0 && (
            <div
              data-testid="opas-options"
              style={{
                pointerEvents: "auto",
                ...GLASS,
                borderRadius: 18,
                padding: 6,
                minWidth: "min(340px, 100%)",
                maxWidth: "100%",
              }}
            >
              {reply.options.map((option, i) => (
                <button
                  key={option.id}
                  type="button"
                  data-testid={`opas-option-${i + 1}`}
                  onClick={() => answerOption(i)}
                  style={{
                    display: "flex",
                    gap: 10,
                    alignItems: "baseline",
                    width: "100%",
                    textAlign: "left",
                    background: "none",
                    border: 0,
                    borderRadius: 10,
                    padding: "8px 10px",
                    cursor: "pointer",
                    fontSize: 14,
                    color: "#f2f2f2",
                  }}
                >
                  {/* The prototype's `<kbd>${i+1}</kbd>`. ⌘1-9 and a bare digit reach the
                      same option; the number is the affordance for all three. */}
                  <kbd
                    style={{
                      flex: "none",
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 11,
                      padding: "2px 6px",
                      borderRadius: 4,
                      border: "1px solid rgba(255,255,255,.14)",
                      color: "#9a9a9a",
                    }}
                  >
                    {i + 1}
                  </kbd>
                  <span>{option.label}</span>
                  {option.detail !== undefined && (
                    <span
                      data-testid={`opas-option-detail-${i + 1}`}
                      style={{ color: "#9a9a9a", fontSize: 13 }}
                    >
                      {option.detail}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SPHERE — 56px, right 24 bottom 24, the prototype's geometry. `session` shows a held
          set of panes: orb.classList.toggle('session', wins.length > 0). */}
      <button
        type="button"
        data-testid="opas-sphere"
        data-session={opas.hasSession ? "true" : "false"}
        aria-label="Open Opas"
        onClick={() => opas.open()}
        style={{
          position: "fixed", right: 24, bottom: 24, width: 56, height: 56, border: 0, padding: 0,
          borderRadius: "50%", background: "radial-gradient(circle at 36% 30%,#3c3c3c 0,#181818 42%,#060606 78%)",
          boxShadow: opas.hasSession
            ? "0 18px 36px rgba(0,0,0,.75), 0 0 18px 2px rgba(214,214,214,.30)"
            : "0 18px 36px rgba(0,0,0,.75), 0 0 16px 2px rgba(138,164,189,.30)",
          cursor: "pointer", zIndex: 45,
          opacity: opas.isOpen ? 0 : 1,
          transform: opas.isOpen ? "scale(.7)" : "none",
          pointerEvents: opas.isOpen ? "none" : "auto",
          transition: "opacity .2s cubic-bezier(0.2,0,0.1,1), transform .2s cubic-bezier(0.2,0,0.1,1)",
        }}
      />
    </>
  )
}
