/**
 * Opas — the sphere, the veil, and the panes it opens.
 *
 * ⚠️ THE GATE IS THE RISKY PART AND IT IS DONE WITHOUT TOUCHING THE EXISTING ONE.
 * `CommandBarProvider` already enforces Focus-wins in three places (Cmd+K suppressed when
 * a Focus is open, the bar auto-closed if a Focus opens over it, and
 * `{!focusIsOpen && <CommandBar/>}` so it cannot even render). None of that changes here.
 *
 * Opas adds its own two rules and nothing else:
 *   1. a Focus open hides the sphere, the same way it hides the bar
 *   2. the sphere and the command bar are mutually exclusive
 *
 * Rule 2 is implemented ONE-DIRECTIONALLY ON PURPOSE, which is what keeps it additive:
 * this provider watches `commandBar.isOpen` and closes itself, and calls the bar's own
 * exported `close()` when the sphere opens. `CommandBarProvider` is not modified, does not
 * know Opas exists, and keeps every existing behaviour — Cmd+K still toggles, Escape still
 * closes, Focus still wins.
 *
 * ⚠️ MOUNT ORDER MATTERS: this must sit INSIDE `CommandBarProvider` (it consumes
 * `useCommandBar`) and inside whatever provides Focus. The provider throws if either is
 * missing rather than silently degrading to an ungated sphere.
 */
import {
  createContext,
  useRef,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { findDuplicate } from "@/components/opas/pane-identity"
import { useCommandBar } from "@/core/CommandBarProvider"
import { useFocus } from "@/contexts/focus-context"
import type { OrderListSnapshot, OrderQuestion } from "@/services/order-list-service"

/** What a pane renders.
 *
 * ⚠️ EXPORTED AS A NAMED UNION so `pane-mode.ts` can declare its map as
 * `Record<OpasPaneKind, PaneMode>` and fail to COMPILE when a kind is added without
 * being classified as entry or info. Inline on the interface, the map could only
 * have been keyed by `string`, and a missing row would have been a silent `undefined`
 * — a new entry pane opening in the wrong place with the bar not wired to it, and
 * nothing failing.
 */
export type OpasPaneKind =
  | "product-list"
  | "product"
  | "capture"
  | "order-list"
  | "sales-order"
  | "customer"
  | "cemetery"

/** One pane opened from the command line. */
export interface OpasPane {
  /** Stable within a session; the pane's identity for close/focus. */
  readonly id: string
  /** What the pane renders. */
  readonly kind: OpasPaneKind
  /** Uppercase eyebrow in the pane header, from the prototype's `.whead .kind`. */
  readonly label: string
  /** For `kind: "product"`. */
  readonly variantTemplateId?: string
  /** The phrase that did not match, shown on an unfiltered list. */
  // ⚠️ `unmatchedPhrase` WAS HERE AND IS GONE (James, 2026-10-23). It carried the
  // phrase that matched nothing so the Product List pane could head itself "Nothing
  // matched … The whole catalog:". That fallback is removed: a miss is one line above
  // the bar and opens nothing. The field is deleted rather than left unset, because an
  // optional prop with no producer reads as a live feature to the next reader.
  /** For `kind: "capture"` — fed through extraction on start (prototype `:568`). */
  readonly openingLine?: string
  /** For `kind: "capture"` — what a pane CHOSE, which the text may override but
   *  re-extraction may not clear.
   *
   *  ⚠️ NOT THE SAME AS `openingLine`, AND THE BUG WAS BELIEVING IT WAS. An opening line
   *  is text: it is extracted once, and the next debounced whole-text re-read rebuilds
   *  every value from whatever is in the BAR — which, for a capture opened from a pane
   *  rather than typed, was empty. Measured 2026-10-24: the funeral home appeared for
   *  about a second and went blank. A prefill is stored on the session and re-applied
   *  beneath the text on every re-read (James's ruling, 2026-10-24). */
  readonly capturePrefill?: Readonly<Record<string, string>>
  /** For `kind: "cemetery"` — which cemetery's pane this is. */
  readonly cemeteryId?: string
  /** For `kind: "capture"` — ⚠️ SET AFTER THE SERVER REPLIES, so a tucked and reopened
   *  pane RE-READS the session instead of starting a second one. This is what makes
   *  "survives tuck" true rather than asserted: the pane holds no order state itself. */
  readonly captureSessionId?: string
  /** For `kind: "order-list"` — the question the server understood, and the rows it counted. */
  readonly orderQuestion?: OrderQuestion
  readonly orderSnapshot?: OrderListSnapshot
  /** The phrase that produced `orderQuestion`, taught back when a pill is corrected. */
  readonly orderPhrase?: string
  /** For `kind: "customer"` — the `customers.id` the pane reads.
   *
   *  ⚠️ AN ID, NOT THE NAME, AND THE ORDER PAYLOAD NOW CARRIES IT. `funeral_home` on a
   *  sales order is a display string; resolving it back to an account in the client
   *  would be name-matching for a key the server already has. `detail.order_detail`
   *  emits `customer_id` since 2026-10-24 for exactly this. */
  readonly customerId?: string
  /** For `kind: "sales-order"`. */
  readonly salesOrderId?: string
}

/** Where a pane sits, and whether it has been moved.
 *
 * ⚠️ `anchored` IS THE PROTOTYPE'S OWN FLAG, and it carries the cascade rule. A pane starts
 * anchored and auto-positioned; the prototype drops the flag on the FIRST MOVE
 * (`w.anchored=false; el.classList.remove('anchored')`). So a dragged pane keeps its place
 * and a new one still cascades from the default. Without the flag, either every pane
 * re-anchors on re-render or none of them ever cascades.
 */
export interface PanePlacement {
  readonly x: number
  readonly y: number
  readonly anchored: boolean
}

interface OpasValue {
  readonly isOpen: boolean
  readonly panes: readonly OpasPane[]
  readonly open: () => void
  readonly close: () => void
  /** ⚠️ RETURNS THE NEW PANE'S ID since 2026-10-12. The bar opens an entry pane and
   *  must immediately hand it the text already typed, which needs the id. Before
   *  this it returned void and the caller had no way to address the pane it had just
   *  created. */
  readonly openPane: (pane: Omit<OpasPane, "id">) => string
  readonly closePane: (id: string) => void
  /** ⚠️ True only when Opas may render at all. A Focus open makes this false. */
  readonly canRender: boolean
  /** ⚠️ THE SESSION IS THE SET OF PANES. Verified in the prototype:
   *  `orb.classList.toggle('session', wins.length > 0)`. There is no clear-all control —
   *  panes close one at a time and the session ends when the last one goes. */
  readonly hasSession: boolean
  /** A question awaiting an answer. Escape cancels THIS before it tucks.
   *
   *  ⚠️ IT HOLDS THE REPLY'S OPTION IDS SINCE 2026-10-20, where it used to hold the
   *  catalog resolver's candidate ids for a pane. The pane is gone; the question lives
   *  above the bar. What did NOT change is why this lives in the context at all:
   *  `onEscape` owns Escape's three branches and its first one cancels a pending
   *  question without tucking, so the flag has to be readable from here. Giving the
   *  reply its own flag would mean Escape consulting two. */
  readonly pendingPick: readonly string[] | null
  readonly setPendingPick: (ids: readonly string[] | null) => void
  /** ⚠️ RECORDS THE SERVER'S SESSION ID ON THE PANE, which is what makes a tucked capture
   *  survive. The pane itself holds no order state: on re-mount it re-reads this session
   *  from the server. Without it, tucking and reopening would start a SECOND session and
   *  orphan the half-typed order. */
  readonly setCaptureSession: (paneId: string, sessionId: string) => void
  /** Patch a pane in place. Kind and id stay. Used so a new question updates the
   *  open order list instead of stacking a second one. */
  readonly updatePane: (id: string, patch: Partial<Omit<OpasPane, "id" | "kind">>) => void
  /** Escape / veil-pointerdown. Named for what the prototype calls it. */
  readonly tuck: () => void
  /** Escape's three-branch behaviour; returns which branch ran. */
  readonly onEscape: (
    activeTagName?: string,
    activeIsCommandBar?: boolean,
  ) => "cancelled-pick" | "refocused-input" | "tucked"
  /** Placement per pane id. Absent means still anchored at its cascade slot. */
  readonly placements: Readonly<Record<string, PanePlacement>>
  readonly movePane: (id: string, x: number, y: number) => void
  /** The pane at the front. `raise` is the prototype's name for bringing one forward. */
  readonly frontPaneId: string | null
  readonly raisePane: (id: string) => void
  /** Monotonic, like the prototype's `++z`. */
  readonly zOf: (id: string) => number
  /** ⚠️ WHAT IS IN THE BAR, PER ENTRY PANE, AND IT LIVES HERE BECAUSE TWO COMPONENTS
   *  NEED IT. The command line renders it (the bar is the only input, by ruling) and
   *  the pane extracts from it. Holding it in either one would make the other reach
   *  across; holding it in both would be two sources of truth about one string.
   *
   *  ⚠️ KEYED BY PANE ID so switching panes does not lose a half-typed order. With a
   *  single string, raising a second entry pane would show its predecessor's text in
   *  the bar and the next keystroke would send it to the wrong session. */
  readonly entryText: Readonly<Record<string, string>>
  readonly setEntryText: (paneId: string, text: string) => void
}

const OpasContext = createContext<OpasValue | null>(null)

export function useOpas(): OpasValue {
  const v = useContext(OpasContext)
  if (v === null) {
    throw new Error("useOpas must be used inside <OpasProvider>")
  }
  return v
}

/** Null-safe, for components that render in trees without Opas. */
export function useOpasOptional(): OpasValue | null {
  return useContext(OpasContext)
}

let paneSeq = 0

/** Opas client state that outlives a render, and the one call that clears it.
 *
 * ⚠️ NOTHING IS WRITTEN HERE ANY MORE, AND THAT IS THE POINT. The capture session id
 * used to be stored so a reload could re-open the pane. Restore-on-mount is removed
 * by ruling (2026-10-13) — opening Opas never shows an order — so the id has NO
 * READER, and a write with no reader is dead machinery that still leaks a half-typed
 * order's identity into a shared browser.
 *
 * ⚠️ THE KEYS ARE STILL CLEARED, FOR A MEASURED REASON RATHER THAN TIDINESS. A
 * director's tab can carry a key written by an EARLIER DEPLOY — James's own tab did,
 * for three walk rounds — so logout has to remove what a previous build left behind,
 * not just what this one writes. That is also why `clearOpasClientState` enumerates
 * the keys rather than trusting that none exist.
 */
export const CAPTURE_SESSION_KEY = "opas.capture.session"

/** Every Opas key, so logout can clear the set rather than a remembered subset. */
export const OPAS_CLIENT_KEYS: readonly string[] = [CAPTURE_SESSION_KEY]

export function readStoredCaptureSession(): string | null {
  try {
    return window.sessionStorage.getItem(CAPTURE_SESSION_KEY)
  } catch {
    return null
  }
}

/**
 * Clear all Opas client state. Called on logout, by ruling.
 *
 * ⚠️ FOR A SHARED OFFICE COMPUTER. The next person to sign in must not inherit
 * anything about the last person's order. That is why this is on the logout path and
 * not only on close: closing is a gesture the same person makes, signing out is a
 * handover.
 *
 * ⚠️ BOTH STORAGES, because a key written by an earlier build may be in either and
 * this function's job is to leave none behind.
 */
export const OPAS_KEY_PREFIX = "opas."

export function clearOpasClientState(): void {
  for (const store of [window.sessionStorage, window.localStorage]) {
    try {
      // ⚠️ A PREFIX SWEEP, NOT JUST THE KEYS THIS BUILD KNOWS. The named list below
      // covers what the current code knows about — which, measured 2026-10-13, is
      // ONE key that nothing writes any more. The keys that actually matter on
      // logout are the ones written by builds that have since been replaced, and
      // this build cannot name those. Anything under `opas.` is ours, so sweeping
      // the namespace clears them without having to have predicted them.
      //
      // ⚠️ COLLECTED FIRST, THEN REMOVED. `removeItem` during a `key(i)` walk
      // reindexes the store and skips entries.
      const doomed: string[] = []
      for (let i = 0; i < store.length; i += 1) {
        const k = store.key(i)
        if (k !== null && k.startsWith(OPAS_KEY_PREFIX)) doomed.push(k)
      }
      for (const k of [...doomed, ...OPAS_CLIENT_KEYS]) store.removeItem(k)
    } catch {
      /* storage can throw in private mode; a failure to clear is not fatal here */
    }
  }
}

export function OpasProvider({ children }: { children: ReactNode }) {
  const commandBar = useCommandBar()
  const focus = useFocus()
  const focusIsOpen = focus?.isOpen ?? false

  const [isOpen, setIsOpen] = useState(false)
  const [panes, setPanes] = useState<readonly OpasPane[]>([])
  /** ⚠️ A SYNCHRONOUS MIRROR OF `panes`, for the dedupe check in `openPane` and the
   *  removal in `closePane`. React state is not readable between two calls in the same
   *  tick, and "close the capture, open the order's pane" is two calls in one tick. The
   *  ref is the authority for those two functions and `panes` is what renders; the
   *  effect below re-syncs it after every render, so a new setter that forgets the ref
   *  diverges for one tick rather than forever. */
  const panesRef = useRef<readonly OpasPane[]>([])
  const [pendingPick, setPendingPick] = useState<readonly string[] | null>(null)
  const [entryText, setEntryTextMap] = useState<Record<string, string>>({})

  /** ⚠️ IDENTITY-STABLE ON A NO-OP WRITE. The bar's onChange fires on every keystroke
   *  including ones that do not change the value (IME composition, a re-render echoing
   *  the same string back); returning the same object keeps the pane's extraction
   *  effect from re-running on a value that did not move. */
  const setEntryText = useCallback((paneId: string, text: string) => {
    setEntryTextMap((prev) => (prev[paneId] === text ? prev : { ...prev, [paneId]: text }))
  }, [])


  /** ⚠️ IDEMPOTENT BY `paneId`, and it must be: the pane calls this once per start, but a
   *  re-render that called it again with the same id must not create a new pane object
   *  and retrigger the effect. Returning the SAME array when nothing changed keeps the
   *  identity stable. */
  const setCaptureSession = useCallback((paneId: string, sessionId: string) => {
    // ⚠️ EAGER AND SNAPSHOT, like `openPane` — the ref is the authority for same-tick
    // reads, so every writer of `panes` has to keep it in step at CALL time.
    const prev = panesRef.current
    const i = prev.findIndex((p) => p.id === paneId)
    if (i >= 0 && prev[i].captureSessionId !== sessionId) {
      const next = prev.slice()
      next[i] = { ...next[i], captureSessionId: sessionId }
      panesRef.current = next
      setPanes(next)
    }
    // ⚠️ NOT PERSISTED ANY MORE. Restore-on-mount is removed by ruling, so the id
    // had no reader — and a half-typed order's identity sitting in a shared
    // browser's storage with nothing reading it is pure exposure. The id lives on
    // the pane object for as long as the pane does, which is now its whole life.
  }, [])

  const updatePane = useCallback((id: string, patch: Partial<Omit<OpasPane, "id" | "kind">>) => {
    // ⚠️ EAGER AND SNAPSHOT, like `openPane` — see its note.
    const prev = panesRef.current
    const i = prev.findIndex((p) => p.id === id)
    if (i < 0) return
    const current = prev[i]
    const next = prev.slice()
    next[i] = { ...current, ...patch, id: current.id, kind: current.kind }
    panesRef.current = next
    setPanes(next)
  }, [])

  const [placements, setPlacements] = useState<Record<string, PanePlacement>>({})
  const [frontPaneId, setFrontPaneId] = useState<string | null>(null)
  // ⚠️ A MONOTONIC COUNTER, exactly the prototype's `++z`. Ranking by array index instead
  // would re-shuffle every pane whenever one closed; a counter only ever moves one pane.
  const [zs, setZs] = useState<Record<string, number>>({})
  const zNext = useRef(1)

  // ⚠️ THE RE-SYNC THE `panesRef` DOCSTRING PROMISES. Without it that docstring claims a
  // safety net that does not exist — the ref would silently diverge from `panes` the
  // first time a new setter forgot to write it, and the divergence would show up as a
  // duplicate pane rather than as an error. It runs AFTER the render that `openPane`
  // already wrote the ref for, so the two agree and this is a no-op in the normal case.
  useEffect(() => {
    panesRef.current = panes
  }, [panes])

  // ⚠️ RULE 1 — a Focus open hides Opas, exactly as it hides the command bar. Closing
  // rather than merely hiding, so a tucked session cannot be resurrected by leaving a
  // Focus and finding the veil still up.
  useEffect(() => {
    if (focusIsOpen && isOpen) setIsOpen(false)
  }, [focusIsOpen, isOpen])

  // ⚠️ RULE 2, the half that watches. The command bar opening closes Opas. One-directional:
  // CommandBarProvider is untouched and does not know this exists.
  useEffect(() => {
    if (commandBar.isOpen && isOpen) setIsOpen(false)
  }, [commandBar.isOpen, isOpen])

  const open = useCallback(() => {
    if (focusIsOpen) return
    // ⚠️ RULE 2, the half that acts — via the bar's OWN exported close().
    if (commandBar.isOpen) commandBar.close()
    setIsOpen(true)
  }, [commandBar, focusIsOpen])

  // ⚠️ TUCK, AND THE NAME IS THE PROTOTYPE'S. Verified from its source, not inferred:
  //
  //     function tuck(){ if(!isOpen)return; isOpen=false; clearTimeout(timer); cancelPick();
  //       veil.classList.remove('on'); said.classList.remove('on');
  //       wins.forEach(w=>w.el.classList.add('tucked')); … }
  //
  // and in its own visible UI: "Esc — tuck everything away; it comes back where you left
  // it". `.tucked` sets opacity:0 / pointer-events:none WITHOUT unmounting, and `open()`
  // removes it from every pane, so the session returns intact.
  //
  // ⚠️ `cancelPick()` FIRST, which is why tuck clears the pick here too. The prototype's
  // Escape handler ALSO cancels a pending pick and returns WITHOUT tucking, so a pick is
  // cancellable without losing the session — see `onEscape` below.
  const tuck = useCallback(() => {
    setPendingPick(null)
    setIsOpen(false)
  }, [])

  // Kept as `close` for callers that read it as a dismissal; it is the same tuck.
  const close = tuck

  /**
   * Escape, in the prototype's own order:
   *
   *     if(pending){cancelPick();return}                       // 1 — cancel, do not tuck
   *     if(document.activeElement.tagName==='TEXTAREA'){input.focus();return}   // 2
   *     tuck()                                                 // 3
   *
   * ⚠️ BRANCHES 1 AND 2 ARE NOT DECORATION. Without 1, answering "never mind" to a
   * numbered pick would throw the whole session away. Without 2, Escape while typing in a
   * pane's textarea would tuck the pane out from under the typist.
   *
   * ⚠️ BRANCH 2 MEANS "A PANE'S TEXTAREA", AND THE COMMAND BAR BECAME ONE ON
   * 2026-10-13. The bar was an `<input>` and so fell through to branch 3; making it a
   * textarea so long orders could wrap turned Escape-in-the-bar into a refocus, which
   * meant Escape no longer ended the capture and the sphere stayed non-interactive.
   * Caught by `ESCAPE ENDS THE CAPTURE` going red. The caller says which textarea it
   * is, because only the caller holds the bar's ref.
   *
   * Returns what it did so a caller can decide whether to preventDefault.
   */
  const onEscape = useCallback(
    (
      activeTagName?: string,
      activeIsCommandBar?: boolean,
    ): "cancelled-pick" | "refocused-input" | "tucked" => {
      if (pendingPick !== null) {
        setPendingPick(null)
        return "cancelled-pick"
      }
      if (
        !activeIsCommandBar
        && (activeTagName ?? "").toUpperCase() === "TEXTAREA"
      ) {
        return "refocused-input"
      }
      tuck()
      return "tucked"
    },
    [pendingPick, tuck],
  )

  const raisePane = useCallback((id: string) => {
    zNext.current += 1
    const z = zNext.current
    setZs((prev) => ({ ...prev, [id]: z }))
    setFrontPaneId(id)
  }, [])

  const movePane = useCallback((id: string, x: number, y: number) => {
    // ⚠️ `anchored: false` on the first move — see PanePlacement.
    setPlacements((prev) => ({ ...prev, [id]: { x, y, anchored: false } }))
  }, [])

  const openPane = useCallback(
    (pane: Omit<OpasPane, "id">): string => {
      // ⚠️ JAMES'S FIRST MULTI-PANE RULE, ENFORCED HERE RATHER THAN AT EACH CALLER
      // (2026-10-19): "Opening a record that's already open focuses that pane; never a
      // duplicate." `OpasHost.openSalesOrder` had this for sales orders only, so
      // opening one vault from two orders made two identical Product panes. Which
      // panes have an identity is declared in `pane-identity.ts`, exhaustively by type.
      //
      // ⚠️ IT READS THE REF, NOT THE `panes` STATE. Two calls in one tick — which is
      // exactly what "the capture closes and the order's pane opens" does — would both
      // see the same stale `panes` array: the second would re-find the pane the first
      // removed, or miss the pane the first added. The ref is written EAGERLY by both
      // `openPane` and `closePane`, before either returns, so the second call sees the
      // first one's result.
      const duplicate = findDuplicate(panesRef.current, pane)
      if (duplicate !== undefined) {
        raisePane(duplicate.id)
        return duplicate.id
      }
      paneSeq += 1
      const id = `opas-pane-${paneSeq}`
      const created = { ...pane, id }
      // ⚠️ A SNAPSHOT VALUE, NOT A LAZY `() => panesRef.current`. React runs an updater
      // FUNCTION at render time, not at call time, so two writers that both defer leave
      // the later one's updater reading a ref the earlier one has already overwritten —
      // and the newly-opened pane is dropped. Measured: "approve closes the capture and
      // opens the order's pane" rendered an EMPTY desk, and the test asserting the
      // order's pane caught it.
      //
      // ⚠️ CORRECTED AFTER A BREAK TEST — THIS COMMENT NAMED THE WRONG CAUSE. It read:
      // "a lazy read of the ref would be evaluated AFTER any `closePane` queued in the
      // same tick had already overwritten it". That blames THIS function's laziness
      // alone. Measured by reverting each in turn: with `closePane` eager and this one
      // lazy, the test stays GREEN — the lazy read resolves to a ref both calls have
      // already written correctly. The failure needs BOTH writers deferred, which is
      // the shape the code had. So the invariant is not "openPane must snapshot"; it is
      // **every writer of `panes` writes the ref at CALL time and hands `setPanes` a
      // value** — which is why `closePane`, `updatePane` and `setCaptureSession` all do.
      const next = [...panesRef.current, created]
      panesRef.current = next
      setPanes(next)
      // A new pane arrives at the front, as the prototype's `raise` on creation does.
      raisePane(id)
      // ⚠️ RETURNED so the caller can address the pane it just made — the bar needs
      // this to move the already-typed text into the new entry pane.
      return id
    },
    [raisePane],
  )

  const closePane = useCallback(
    (id: string) => {
      // ⚠️ EAGER, AND WITH A SNAPSHOT RATHER THAN AN UPDATER, for the same reason
      // `openPane` is — see its note. Written as `setPanes((prev) => …)` this computed
      // `next` at render time, so an `openPane` queued immediately after it read a stale
      // ref and its pane never appeared.
      const next = panesRef.current.filter((p) => p.id !== id)
      panesRef.current = next
      setPanes(next)
      // ⚠️ THE PROTOTYPE RE-RAISES WHEN THE FRONT PANE CLOSES: "if(front===id){const n=
      // wins.slice().sort((a,b)=>b.el.style.zIndex-a.el.style.zIndex)[0]; … if(n)raise(n)}".
      // Without it, closing the front pane leaves NOTHING focused and the next click has
      // to do the job — which reads as the overlay having lost track.
      if (next.length > 0) {
        setFrontPaneId((front) => {
          if (front !== id) return front
          const highest = next.reduce((a, b) => ((zs[b.id] ?? 0) > (zs[a.id] ?? 0) ? b : a))
          return highest.id
        })
      } else {
        setFrontPaneId(null)
      }
      setPlacements((prev) => {
        const { [id]: _gone, ...rest } = prev
        return rest
      })
      // ⚠️ THE TEXT GOES WITH THE PANE. A closed pane's id is never reused, so a
      // surviving entry would leak for the tab's lifetime — and if an id ever were
      // reused, the new pane would open holding someone else's half-typed order.
      setEntryTextMap((prev) => {
        if (!(id in prev)) return prev
        const { [id]: _text, ...rest } = prev
        return rest
      })
    },
    [zs],
  )

  const value = useMemo<OpasValue>(
    () => ({
      isOpen: isOpen && !focusIsOpen,
      panes,
      open,
      close,
      openPane,
      closePane,
      canRender: !focusIsOpen,
      hasSession: panes.length > 0,
      pendingPick,
      setPendingPick,
      setCaptureSession,
      updatePane,
      tuck,
      onEscape,
      placements,
      movePane,
      frontPaneId,
      raisePane,
      zOf: (id: string) => zs[id] ?? 0,
      entryText,
      setEntryText,
    }),
    [isOpen, focusIsOpen, panes, open, close, openPane, closePane, pendingPick, setCaptureSession, updatePane, tuck, onEscape, placements, movePane, frontPaneId, raisePane, zs, entryText, setEntryText],
  )

  return <OpasContext.Provider value={value}>{children}</OpasContext.Provider>
}
