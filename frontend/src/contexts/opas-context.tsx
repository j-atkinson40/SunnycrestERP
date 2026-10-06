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

import { useCommandBar } from "@/core/CommandBarProvider"
import { useFocus } from "@/contexts/focus-context"

/** One pane opened from the command line. */
export interface OpasPane {
  /** Stable within a session; the pane's identity for close/focus. */
  readonly id: string
  /** What the pane renders. The slice has two. */
  readonly kind: "product-list" | "product"
  /** Uppercase eyebrow in the pane header, from the prototype's `.whead .kind`. */
  readonly label: string
  /** For `kind: "product"`. */
  readonly variantTemplateId?: string
  /** For `kind: "product-list"` — a numbered pick when the resolver was ambiguous. */
  readonly candidateIds?: readonly string[]
  /** The phrase that did not match, shown on an unfiltered list. */
  readonly unmatchedPhrase?: string
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
  readonly openPane: (pane: Omit<OpasPane, "id">) => void
  readonly closePane: (id: string) => void
  /** ⚠️ True only when Opas may render at all. A Focus open makes this false. */
  readonly canRender: boolean
  /** ⚠️ THE SESSION IS THE SET OF PANES. Verified in the prototype:
   *  `orb.classList.toggle('session', wins.length > 0)`. There is no clear-all control —
   *  panes close one at a time and the session ends when the last one goes. */
  readonly hasSession: boolean
  /** A numbered pick awaiting an answer. Escape cancels THIS before it tucks. */
  readonly pendingPick: readonly string[] | null
  readonly setPendingPick: (ids: readonly string[] | null) => void
  /** Escape / veil-pointerdown. Named for what the prototype calls it. */
  readonly tuck: () => void
  /** Escape's three-branch behaviour; returns which branch ran. */
  readonly onEscape: (activeTagName?: string) => "cancelled-pick" | "refocused-input" | "tucked"
  /** Placement per pane id. Absent means still anchored at its cascade slot. */
  readonly placements: Readonly<Record<string, PanePlacement>>
  readonly movePane: (id: string, x: number, y: number) => void
  /** The pane at the front. `raise` is the prototype's name for bringing one forward. */
  readonly frontPaneId: string | null
  readonly raisePane: (id: string) => void
  /** Monotonic, like the prototype's `++z`. */
  readonly zOf: (id: string) => number
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

export function OpasProvider({ children }: { children: ReactNode }) {
  const commandBar = useCommandBar()
  const focus = useFocus()
  const focusIsOpen = focus?.isOpen ?? false

  const [isOpen, setIsOpen] = useState(false)
  const [panes, setPanes] = useState<readonly OpasPane[]>([])
  const [pendingPick, setPendingPick] = useState<readonly string[] | null>(null)
  const [placements, setPlacements] = useState<Record<string, PanePlacement>>({})
  const [frontPaneId, setFrontPaneId] = useState<string | null>(null)
  // ⚠️ A MONOTONIC COUNTER, exactly the prototype's `++z`. Ranking by array index instead
  // would re-shuffle every pane whenever one closed; a counter only ever moves one pane.
  const [zs, setZs] = useState<Record<string, number>>({})
  const zNext = useRef(1)

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
   * Returns what it did so a caller can decide whether to preventDefault.
   */
  const onEscape = useCallback(
    (activeTagName?: string): "cancelled-pick" | "refocused-input" | "tucked" => {
      if (pendingPick !== null) {
        setPendingPick(null)
        return "cancelled-pick"
      }
      if ((activeTagName ?? "").toUpperCase() === "TEXTAREA") {
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
    (pane: Omit<OpasPane, "id">) => {
      paneSeq += 1
      const id = `opas-pane-${paneSeq}`
      setPanes((prev) => [...prev, { ...pane, id }])
      // A new pane arrives at the front, as the prototype's `raise` on creation does.
      raisePane(id)
    },
    [raisePane],
  )

  const closePane = useCallback(
    (id: string) => {
      setPanes((prev) => {
        const next = prev.filter((p) => p.id !== id)
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
        return next
      })
      setPlacements((prev) => {
        const { [id]: _gone, ...rest } = prev
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
      tuck,
      onEscape,
      placements,
      movePane,
      frontPaneId,
      raisePane,
      zOf: (id: string) => zs[id] ?? 0,
    }),
    [isOpen, focusIsOpen, panes, open, close, openPane, closePane, pendingPick, tuck, onEscape, placements, movePane, frontPaneId, raisePane, zs],
  )

  return <OpasContext.Provider value={value}>{children}</OpasContext.Provider>
}
