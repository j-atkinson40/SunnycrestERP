/**
 * "Not placed yet" — the words Opas could not file, parked under the order.
 *
 * Slice 2, item 3 (James, 2026-10-28): *"the 'Not placed yet' strip — drag a held word
 * onto a field, edit inline, × to drop, held words matching the open question are its
 * first pill."*
 *
 * ⚠️ IT IS THE OTHER HALF OF CLAUSE 1 AND NOT A SEPARATE FEATURE. The prototype's own
 * header states the division: *"Words Opas understands fly into the order … anything
 * Opas can't place waits under the order."* Without this strip, clause 1 is a feature
 * that silently deletes everything it does not recognise — so the two shipped together
 * on purpose.
 *
 * ⚠️ THREE WAYS OUT OF A CHIP, WHICH IS THE PROTOTYPE'S OWN SET AND NOT A MENU OF
 * OPTIONS. Each answers a different reason a word failed to place:
 *
 *     drag onto a line   Opas does not know the term, but the DIRECTOR knows the field
 *     click to edit      it was a typo — "montecello" — and the term is real
 *     ×                  it was noise, or it has been typed again properly
 *
 * ⚠️ AND THE CHIP SHOWS THE DIRECTOR'S OWN TEXT, never a normalised form. The strip's
 * job is "here is what I could not file"; rewriting the words would make a director
 * hunt for something they did not type.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import { GHOST_DX, GHOST_DY, dropTargetAt, isADrag } from "./held-drag"
import { FLY_CLASS } from "./fly"
import type { HeldWord } from "@/services/opas-capture-service"

/** The prototype's `.hl` label, verbatim. */
export const HELD_LABEL = "Not placed yet"

/** The prototype's `.hhint`, verbatim. */
export const HELD_HINT = "Drag onto a line, or click to fix it"

export interface HeldStripProps {
  readonly held: readonly HeldWord[]
  /** Drag landed on a row: put this chip's word in that field. */
  readonly onPlace: (heldId: string, fieldId: string) => void
  /** × — the word was noise. */
  readonly onDrop: (heldId: string) => void
  /** The inline edit was committed with a different word. */
  readonly onEdit: (heldId: string, word: string) => void
  /** A request is in flight; the strip refuses new gestures rather than queueing. */
  readonly busy?: boolean
}

export function HeldStrip({ held, onPlace, onDrop, onEdit, busy }: HeldStripProps) {
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  /** The row the pointer is over mid-drag, so it can be un-highlighted. */
  const overRef = useRef<Element | null>(null)
  const ghostRef = useRef<HTMLElement | null>(null)

  // ⚠️ THE GHOST AND THE HIGHLIGHT ARE CLEANED UP ON UNMOUNT, because a pane that
  // closes mid-drag would otherwise leave a chip fixed over the page and a row lit up
  // with nothing dragging. Both are direct DOM nodes outside React's tree, so nothing
  // else will tidy them.
  useEffect(
    () => () => {
      ghostRef.current?.remove()
      overRef.current?.removeAttribute("data-drop-over")
      document.body.removeAttribute("data-opas-dragging")
    },
    [],
  )

  const stopEdit = useCallback(() => {
    setEditing(null)
    setDraft("")
  }, [])

  const commit = useCallback(
    (heldId: string, was: string) => {
      const next = draft.trim()
      stopEdit()
      // ⚠️ AN EMPTY EDIT DROPS THE CHIP, matching the prototype's `commitEdit`:
      // `if(text)h.text=text;else S.held=S.held.filter(…)`. Clearing the box is the
      // obvious way to say "forget this word", and keeping an empty chip would leave
      // an undraggable, uneditable blank in the strip.
      if (next === "") {
        onDrop(heldId)
        return
      }
      // ⚠️ AND AN UNCHANGED EDIT SENDS NOTHING. Clicking a chip to look at it, then
      // clicking away, is the common case; a PATCH per glance would re-run extraction
      // and could move the order's rows under the director for no reason.
      if (next === was) return
      onEdit(heldId, next)
    },
    [draft, onDrop, onEdit, stopEdit],
  )

  const startDrag = useCallback(
    (e: React.PointerEvent, heldId: string, word: string) => {
      if (busy === true || e.button !== 0) return
      // ⚠️ `preventDefault` SO THE PRESS DOES NOT SELECT TEXT, which on a touchscreen
      // is the difference between carrying a word and summoning the copy/paste bar.
      e.preventDefault()
      const from = { x: e.clientX, y: e.clientY }
      let dragging = false

      const move = (ev: PointerEvent) => {
        const at = { x: ev.clientX, y: ev.clientY }
        if (!dragging) {
          if (!isADrag(from, at)) return
          dragging = true
          const g = document.createElement("div")
          g.className = `${FLY_CLASS} opas-held-ghost`
          g.setAttribute("aria-hidden", "true")
          g.setAttribute("data-testid", "opas-held-ghost")
          g.textContent = word
          document.body.appendChild(g)
          ghostRef.current = g
          // ⚠️ SET ONLY ONCE THE PRESS BECOMES A DRAG, not on pointerdown. Dashing
          // every row the instant a finger touches a chip would flicker the whole
          // pane on each click-to-edit.
          document.body.setAttribute("data-opas-dragging", "true")
        }
        const g = ghostRef.current
        if (g !== null) {
          g.style.transform = `translate(${at.x + GHOST_DX}px,${at.y + GHOST_DY}px)`
        }
        const hit = dropTargetAt(at.x, at.y)
        const row = hit?.row ?? null
        if (row !== overRef.current) {
          overRef.current?.removeAttribute("data-drop-over")
          overRef.current = row
          row?.setAttribute("data-drop-over", "true")
        }
      }

      const up = (ev: PointerEvent) => {
        window.removeEventListener("pointermove", move)
        window.removeEventListener("pointerup", up)
        window.removeEventListener("pointercancel", up)
        ghostRef.current?.remove()
        ghostRef.current = null
        document.body.removeAttribute("data-opas-dragging")
        const row = overRef.current
        overRef.current?.removeAttribute("data-drop-over")
        overRef.current = null
        // ⚠️ A PRESS THAT NEVER BECAME A DRAG IS A CLICK, AND OPENS THE EDIT. One
        // gesture, two outcomes, decided by distance — the prototype's own
        // `if(!d.ghost){if(ev.type==='pointerup')startEdit(id);return}`.
        if (!dragging) {
          if (ev.type === "pointerup") {
            setEditing(heldId)
            setDraft(word)
          }
          return
        }
        if (row === null) return
        // ⚠️ ONLY A DELIBERATE RELEASE FILES THE WORD, AND THIS IS A DELIBERATE
        // DIVERGENCE FROM THE PROTOTYPE. Its `up` is bound to both `pointerup` and
        // `pointercancel` and checks the event type only for the click-to-edit branch:
        //
        //     if(!d.ghost){if(ev.type==='pointerup')startEdit(id);return}
        //     d.ghost.remove();
        //     if(d.over){…dropHeld(id,d.over.dataset.field,…)}
        //
        // so a cancelled drag drops the word wherever the finger happened to be. The
        // browser cancels a pointer when the SYSTEM takes the gesture over — a
        // notification, a scroll handoff, a palm touch on an iPad — which is to say
        // the director never chose that row. Filing on it writes a wrong answer into
        // the order and takes the chip away, so the director has to notice the error
        // before they can fix it.
        //
        // ⚠️ THE PROTOTYPE IS THE REFERENCE FOR LOOK AND MOTION, which this does not
        // change: the ghost, the threshold, the highlight and the arc are all its own.
        // Found by a test written for the touch case, not by reading its code.
        if (ev.type !== "pointerup") return
        // ⚠️ NOT RE-CHECKED FOR EMPTINESS HERE, AND THAT IS MEASURED RATHER THAN
        // ASSUMED. `overRef` is only ever set from `dropTargetAt`, which already
        // refuses a row whose `data-drop-field` is "" — so a guard here is unreachable.
        // It was written, break-tested, and found to turn no test red; deleting it is
        // better than documenting it, because a second place deciding what counts as a
        // valid drop target is a second place that can disagree.
        const fieldId = row.getAttribute("data-drop-field") ?? ""
        onPlace(heldId, fieldId)
      }

      window.addEventListener("pointermove", move)
      window.addEventListener("pointerup", up)
      window.addEventListener("pointercancel", up)
    },
    [busy, onPlace],
  )

  if (held.length === 0) return null

  return (
    <div
      data-testid="capture-held"
      /* The prototype's `.held` — a DASHED amber box, and dashed is doing work: these
         words are not in the order yet. A solid border would read as another section
         of it. */
      className="flex flex-wrap items-center gap-1.5 rounded-xl border border-dashed border-[rgba(224,168,74,0.45)] px-2.5 py-2"
    >
      <span className="mr-1 text-micro uppercase tracking-[0.13em] text-[rgb(224,168,74)]">
        {HELD_LABEL}
      </span>
      {held.map((h) => {
        if (editing === h.id) {
          return (
            <span
              key={h.id}
              data-testid={`capture-held-chip-${h.id}`}
              data-editing="true"
              className="inline-flex items-center rounded-full border border-[rgb(224,168,74)] bg-[rgba(224,168,74,0.08)] px-2.5 py-0.5 shadow-[0_0_0_3px_rgba(224,168,74,0.15)]"
            >
              <label className="sr-only" htmlFor={`held-edit-${h.id}`}>
                Fix the typo
              </label>
              <input
                id={`held-edit-${h.id}`}
                data-testid="capture-held-edit"
                autoFocus
                value={draft}
                spellCheck={false}
                autoComplete="off"
                /* ⚠️ WIDTH IN `ch` FROM THE DRAFT, as the prototype does. A fixed-width
                   box either clips a cemetery's name or leaves a gap beside "smith". */
                style={{ width: `${Math.max(4, draft.length + 1)}ch` }}
                className="border-0 bg-transparent p-0 font-plex-mono text-body-sm text-content-strong outline-none"
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => commit(h.id, h.word)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    commit(h.id, h.word)
                    return
                  }
                  if (e.key === "Escape") {
                    // ⚠️ `stopPropagation` BECAUSE ESCAPE ALSO CLOSES THE PANE. Without
                    // it, abandoning a typo fix would tear down the whole order.
                    e.preventDefault()
                    e.stopPropagation()
                    stopEdit()
                  }
                }}
              />
            </span>
          )
        }
        return (
          <span
            key={h.id}
            data-testid={`capture-held-chip-${h.id}`}
            className="inline-flex items-center rounded-full border border-[rgba(224,168,74,0.4)] bg-[rgba(224,168,74,0.08)]"
          >
            <button
              type="button"
              data-testid={`capture-held-word-${h.id}`}
              title={HELD_HINT}
              /* `touch-none` is Tailwind's `touch-action:none` — without it a drag on a
                 touchscreen scrolls the pane instead of carrying the word. */
              className="cursor-grab touch-none select-none border-0 bg-transparent py-0.5 pl-2.5 pr-1 font-plex-mono text-body-sm text-content-strong"
              onPointerDown={(e) => startDrag(e, h.id, h.word)}
            >
              {h.word}
            </button>
            <button
              type="button"
              data-testid={`capture-held-drop-${h.id}`}
              aria-label={`Drop ${h.word}`}
              disabled={busy === true}
              className="border-0 bg-transparent py-0.5 pl-1 pr-2 text-body-sm leading-none text-content-muted hover:text-content-strong focus-ring-accent"
              onClick={() => onDrop(h.id)}
            >
              ×
            </button>
          </span>
        )
      })}
      <span className="ml-auto text-micro text-content-subtle">{HELD_HINT}</span>
    </div>
  )
}
