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
import { useCallback, useEffect, useRef, useState } from "react"

import { useAuth } from "@/contexts/auth-context"
import { useOpas } from "@/contexts/opas-context"
import { abandonCapture } from "@/services/opas-capture-service"
import { CapturePane, type EntryPaneStatus } from "./CapturePane"
import { CAPTURE_START, isCatalogRequest, routeResolution } from "./opas-routing"
import { isEntryPane } from "./pane-mode"
import { EXTRACT_DEBOUNCE_MS } from "./capture-sequence"

import { consumePickDigit } from "./pick-digit"
import { resolvePhrase } from "@/services/opas-catalog-service"
import { askOrderList, type OrderListSnapshot, type OrderPick } from "@/services/order-list-service"
import { ProductListPane } from "./ProductListPane"
import { ProductPane } from "./ProductPane"
import { OrderListPane } from "./order-list/OrderListPane"
import { isOrderListPhrase, isOrderRefinement } from "./order-list/order-list-routing"
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

const ORDER_TRY = "Try: Hopkins orders this month · going out Friday"
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
  const [barH, setBarH] = useState(0)
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
  // ⚠️ PANE IDS THAT HOLD A CREATED ORDER. The opening effect reads this so the next
  // phrase closes the receipt instead of being typed into a finished order.
  const approvedPanes = useRef<Set<string>>(new Set())
  // ⚠️ A COUNTER-STAMPED REQUEST, NOT A BOOLEAN, for the same reason `pickRequest`
  // is: the pane must act on the SECOND Enter as well as the first, and a bare flag
  // would be compared by value and the repeat would be a no-op.
  const [completeRequest, setCompleteRequest] = useState<Record<string, number>>({})
  const completeNonce = useRef(0)
  const narrow = useNarrowScreen()

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
      if (
        cur !== undefined &&
        cur.placeholder === next.placeholder &&
        cur.capturing === next.capturing &&
        cur.ready === next.ready &&
        cur.picks.length === next.picks.length &&
        cur.picks.every((p, i) => p.field_id === next.picks[i].field_id &&
          p.options.length === next.picks[i].options.length)
      ) {
        return prev
      }
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

  const [said, setSaid] = useState<string | null>(null)

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
      if ((e.target as HTMLElement).closest("button,textarea,input,a") !== null) return
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
  const picks = status?.picks ?? []

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
    if (!CAPTURE_START.test(phrase.toLowerCase())) return
    const id = opas.openPane({ kind: "capture", label: "Order" })
    opas.setEntryText(id, phrase)
    setText("")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, entryMode, opas.isOpen])

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
  const onApproved = useCallback(
    (paneId: string) => {
      setText("")
      opas.setEntryText(paneId, "")
      approvedPanes.current.add(paneId)
      window.setTimeout(() => {
        opas.closePane(paneId)
        approvedPanes.current.delete(paneId)
      }, APPROVED_VISIBLE_MS)
    },
    [opas, setText],
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

  const openSalesOrder = useCallback((orderId: string) => {
    const same = opas.panes.find((p) => p.kind === "sales-order" && p.salesOrderId === orderId)
    if (same) {
      opas.raisePane(same.id)
      return
    }
    for (const pane of opas.panes) {
      if (pane.kind === "sales-order") opas.closePane(pane.id)
    }
    opas.openPane({ kind: "sales-order", label: "Sales order", salesOrderId: orderId })
  }, [opas])

  const settleOrderAnswer = useCallback((result: OrderListSnapshot, spoken: string | undefined) => {
    if (result.kind === "unrecognized" || result.kind === "total") {
      setSaid(result.hint ?? ORDER_TRY)
      return
    }
    if (result.kind === "open_order" && result.open_order_id) {
      openSalesOrder(result.open_order_id)
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
    if (result.kind === "question") {
      for (const pane of opas.panes) {
        if (pane.kind === "sales-order") opas.closePane(pane.id)
      }
    }
    if (result.hint) setSaid(result.hint)
  }, [opas, openSalesOrder])

  const removeOrderPill = useCallback(async (paneId: string, pillId: string) => {
    const pane = opas.panes.find((p) => p.id === paneId)
    if (!pane?.orderQuestion) return
    try {
      const result = await askOrderList({
        question: pane.orderQuestion,
        remove_pill: pillId,
        ...(pane.orderPhrase ? { teach_phrase: pane.orderPhrase } : {}),
      })
      settleOrderAnswer(result, undefined)
    } catch {
      setSaid(ORDER_TRY)
    }
  }, [opas, settleOrderAnswer])

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
      setSaid(ORDER_TRY)
    }
  }, [openSalesOrder, settleOrderAnswer])

  const submit = useCallback(async () => {
    const phrase = text.trim()
    if (phrase === "" || busy) return
    setBusy(true)
    setSaid(null)
    try {
      // ⚠️ THE CAPTURE ENTRANCE IS CHECKED BEFORE THE CATALOG AND BEFORE THE RESOLVER.
      // "start an order for Hopkins" contains no catalog phrase, but sending it to the
      // vault resolver would resolve "order" against product names and open the wrong
      // thing. The whole line is passed through so the funeral home is captured on the
      // opening keystroke (prototype `:568`).
      if (CAPTURE_START.test(phrase.toLowerCase())) {
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
          })
          settleOrderAnswer(result, phrase)
        } catch {
          setSaid(ORDER_TRY)
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
        opas.setPendingPick(route.candidateIds)
        opas.openPane({
          kind: "product-list",
          label: "Which one?",
          candidateIds: route.candidateIds,
        })
        setSaid(
          route.discriminators.length > 0
            ? `${route.candidateIds.length} match — differs by ${route.discriminators.join(", ")}`
            : `${route.candidateIds.length} match`,
        )
      } else {
        opas.openPane({ kind: "product-list", label: "Catalog", unmatchedPhrase: phrase })
        setSaid(`no match for “${phrase}”`)
      }
      setText("")
    } finally {
      setBusy(false)
    }
  }, [text, busy, opas, settleOrderAnswer])

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
        {opas.panes.filter((pane) => !(narrow && (pane.kind === "order-list" || pane.kind === "sales-order"))).map((pane, i) => {
          const placed = opas.placements[pane.id]
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
                  ? { right: 24, bottom: 24 + (barH || 46) }
                  : { right: 24 + i * 18, top: 72 + i * 22 }),
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
                  candidateIds={pane.candidateIds}
                  unmatchedPhrase={pane.unmatchedPhrase}
                  onOpenProduct={(id) => {
                    opas.setPendingPick(null)
                    opas.openPane({ kind: "product", label: "Product", variantTemplateId: id })
                  }}
                />
              ) : pane.kind === "capture" ? (
                <CapturePane
                  openingLine={pane.openingLine}
                  onSessionStarted={(id) => opas.setCaptureSession(pane.id, id)}
                  text={opas.entryText[pane.id] ?? ""}
                  onStatus={(st) => reportStatus(pane.id, st)}
                  pickRequest={pickRequest[pane.id]}
                  onApproved={() => onApproved(pane.id)}
                  completeRequest={completeRequest[pane.id]}
                />
              ) : pane.kind === "order-list" && pane.orderSnapshot ? (
                <OrderListPane
                  snapshot={pane.orderSnapshot}
                  selectedId={opas.panes.find((p) => p.kind === "sales-order")?.salesOrderId}
                  onOpenOrder={openSalesOrder}
                  onRemovePill={(pillId) => void removeOrderPill(pane.id, pillId)}
                  onAskHint={() => setSaid(ORDER_CHANGE)}
                  onChoosePick={(pick) => void chooseOrderPick(pick)}
                />
              ) : pane.kind === "sales-order" && pane.salesOrderId ? (
                <SalesOrderPane orderId={pane.salesOrderId} />
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
                      onAskHint={() => setSaid(ORDER_CHANGE)}
                      onChoosePick={(pick) => void chooseOrderPick(pick)}
                    />
                  ) : pane.kind === "sales-order" && pane.salesOrderId ? (
                    <SalesOrderPane orderId={pane.salesOrderId} />
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
            <textarea
              ref={inputRef}
              rows={1}
              data-testid="opas-input"
              data-entry-mode={entryMode ? "true" : "false"}
              value={entryMode ? entryValue : text}
              onChange={(e) => {
                if (entryMode && entryPane !== undefined) {
                  opas.setEntryText(entryPane.id, e.target.value)
                } else {
                  setText(e.target.value)
                }
              }}
              onKeyDown={(e) => {
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
                void submit()
              }}
              placeholder={entryMode ? (status?.placeholder ?? "Starting the order…") : "orders · the catalog"}
              aria-label={entryMode ? "Say what the director said" : "Ask Opas"}
              style={{
                flex: 1, minWidth: 0, background: "transparent", border: 0, padding: "10px 0",
                color: "#f2f2f2", fontFamily: "'IBM Plex Mono', ui-monospace, Menlo, monospace",
                fontSize: 15, outline: "none",
                // ⚠️ THE BAR GROWS INSTEAD OF SCROLLING. `resize: none` keeps the
                // drag handle off a chrome element; `overflow: hidden` matters because
                // the height is set from `scrollHeight` and a visible scrollbar would
                // feed its own width back into the measurement.
                resize: "none",
                overflow: "hidden",
                lineHeight: 1.45,
                // ⚠️ A CEILING, SO ONE PASTED PAGE CANNOT PUSH THE PANE OFF SCREEN.
                // Past this the bar scrolls, which is the lesser evil — but an order
                // read aloud on a call does not reach it.
                maxHeight: "40vh",
              }}
            />
          </div>
          {said !== null && (
            <div data-testid="opas-said" style={{ padding: "0 0 6px 52px", fontSize: 12, color: "#9a9a9a" }}>
              {said}
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
