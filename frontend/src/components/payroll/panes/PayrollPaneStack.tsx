/**
 * Payroll panes — the draggable, closable detail surface inside the Focus.
 *
 * ⚠️ **THIS IS THE ONE PLACE I DEPARTED FROM THE 5a-UI BRIEF, AND WHY.**
 *
 * The brief says to use `lib/edge-panel`. As shipped, `EdgePanel` is a SINGLE
 * right-rail panel whose content comes from a tenant COMPOSITION of widget
 * placements (`EdgePanel.tsx` renders `CompositionRenderer` over
 * `ResolvedEdgePanel.pages`). It has no entity scope, opens one at a time, and
 * is not draggable — so "the union member pane for Stevenson, opened by
 * clicking his name, draggable, with the timecard open beside it" cannot be
 * expressed through it without first registering payroll widgets in the visual
 * editor, which is a different piece of work.
 *
 * The `peek` layer DOES open from a name, and was ruled against for exactly
 * this content on 2026-09-09: the peek "opened on cursor travel, pinned itself
 * on pointer entry, and at 360px could not show a day's schedule anyway — so
 * it summarised and the user clicked through regardless." That ruling is
 * recorded in `app/services/note/types.py`.
 *
 * So the panes are local to the payroll Focus: several at once, dragged by the
 * title bar, closed with the button or Escape. Nothing tenant-wide is invented.
 *
 * ⚠️ TO BE REPLACED BY EdgePanel PLACEMENTS WHEN PANES GENERALISE — ruled by
 * James 2026-11-16, keeping pane generalisation off Susan's critical path.
 * Recorded in STATE.md under "Active deferred items" with the same date.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react"


export interface PayrollPaneSpec {
  /** Stable per pane so opening the same thing twice re-focuses rather than
   *  stacking a duplicate — clicking a name twice is a slip, not a request. */
  key: string
  title: string
  subtitle?: string
  body: ReactNode
}


interface Placed {
  spec: PayrollPaneSpec
  x: number
  y: number
}


const clamp = (v: number, lo: number, hi: number) =>
  Math.min(Math.max(v, lo), Math.max(lo, hi))

const STEP = 26
const WIDTH = 380


export function PayrollPaneStack({
  panes,
  onClose,
}: {
  panes: PayrollPaneSpec[]
  onClose: (key: string) => void
}) {
  const [placed, setPlaced] = useState<Placed[]>([])
  const drag = useRef<{ key: string; dx: number; dy: number } | null>(null)
  // ⚠️ **MEASURED FROM THE CONTAINER, NOT FROM `window`.**
  // The Focus dialog is a TRANSFORMED ancestor, so `position: fixed` resolves
  // against it rather than against the viewport. Coordinates computed from
  // `window.innerWidth` put the panes off the right-hand edge — visible in the
  // walkthrough screenshot and in nothing else.
  const host = useRef<HTMLDivElement | null>(null)
  const box = () => host.current?.getBoundingClientRect()

  // Cascade a newly opened pane rather than covering the last one exactly.
  useEffect(() => {
    setPlaced((prev) => {
      const byKey = new Map(prev.map((p) => [p.spec.key, p]))
      return panes.map((spec, i) => {
        const existing = byKey.get(spec.key)
        // ⚠️ Keep the POSITION and take the new body: a pane whose data
        // refreshed must not jump back to its opening coordinates.
        if (existing) return { ...existing, spec }
        // Opened top-right and cascaded: the Focus's own content runs down the
        // left, so a pane starting at 24,24 covered the week heading.
        const r = box()
        const right = r ? r.width : WIDTH + 96
        return {
          spec,
          x: Math.max(8, right - WIDTH - 24 - i * STEP),
          y: 24 + i * STEP,
        }
      })
    })
  }, [panes])

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLElement>, key: string) => {
      const p = placed.find((q) => q.spec.key === key)
      if (!p) return
      const r = box()
      drag.current = {
        key,
        dx: e.clientX - (r?.left ?? 0) - p.x,
        dy: e.clientY - (r?.top ?? 0) - p.y,
      }
      ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
    },
    [placed],
  )

  const onPointerMove = useCallback((e: ReactPointerEvent<HTMLElement>) => {
    const d = drag.current
    if (!d) return
    setPlaced((prev) =>
      prev.map((p) =>
        p.spec.key === d.key
          ? // Clamped on all four sides so a pane cannot be dragged somewhere
            // it cannot be dragged back from. The right/bottom clamps keep a
            // grabbable strip of the title bar on screen.
            {
              ...p,
              x: clamp(e.clientX - (box()?.left ?? 0) - d.dx, 0,
                       (box()?.width ?? WIDTH) - 80),
              y: clamp(e.clientY - (box()?.top ?? 0) - d.dy, 0,
                       (box()?.height ?? 200) - 40),
            }
          : p,
      ),
    )
  }, [])

  const onPointerUp = useCallback(() => {
    drag.current = null
  }, [])

  useEffect(() => {
    if (panes.length === 0) return
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return
      const last = panes[panes.length - 1]
      if (last) {
        // ⚠️ Stops here. Escape inside the Focus closes the TOP PANE; letting
        // it through would also dismiss the Focus, so one keypress would shut
        // a pane and the week behind it.
        e.stopPropagation()
        onClose(last.key)
      }
    }
    window.addEventListener("keydown", onKey, true)
    return () => window.removeEventListener("keydown", onKey, true)
  }, [panes, onClose])

  if (placed.length === 0) return null

  return (
    // ⚠️ `fixed`, NOT `absolute`. Absolutely positioned inside the Focus's
    // scrolling column, a pane SCROLLED WITH THE CONTENT and clipped off the
    // top of the screen — opened from a name near the bottom of the week
    // table, it was already half out of view. A pane is a viewport object, so
    // it is positioned against the viewport.
    <div
      ref={host}
      data-slot="payroll-pane-stack"
      className="pointer-events-none absolute inset-0 z-50 overflow-hidden"
    >
      {placed.map((p, i) => (
        <section
          key={p.spec.key}
          data-testid={`payroll-pane-${p.spec.key}`}
          aria-label={p.spec.title}
          className="pointer-events-auto absolute flex max-h-[70vh] flex-col overflow-hidden rounded-xl border border-border-subtle bg-surface-raised shadow-lg"
          // ⚠️ **THE SECOND CAP IS WHAT MAKES THE BODY'S SCROLLBAR REACHABLE.**
          // `max-h-[70vh]` bounds the pane against the VIEWPORT; this host is
          // `absolute inset-0 overflow-hidden` inside the Focus, which is
          // shorter than 70vh, so a pane taller than the host was PAINTED
          // CLIPPED — its body scrolled, and the scrollbar was cut away with
          // the content, leaving no cue that anything was below. Capping the
          // pane at the host's remaining height from its own top makes the
          // existing `overflow-y-auto` below do the job it was added for.
          //
          // Found 2026-11-23 by reading a walk-through screenshot: the member
          // pane, which had always fit, gained a Status row and both that
          // row's button and the long-standing Timecard button vanished. No
          // test could see it — Playwright and testing-library both scroll an
          // element into view before clicking it.
          style={{
            left: p.x,
            top: p.y,
            width: WIDTH,
            zIndex: 10 + i,
            maxHeight: `calc(100% - ${p.y}px)`,
          }}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          <header
            className="flex cursor-grab items-start justify-between gap-3 border-b border-border-subtle bg-surface-elevated px-4 py-2.5"
            onPointerDown={(e) => onPointerDown(e, p.spec.key)}
          >
            <div className="min-w-0">
              <h3 className="truncate text-body-sm font-medium text-content-strong">
                {p.spec.title}
              </h3>
              {p.spec.subtitle ? (
                <p className="truncate text-caption text-content-muted">
                  {p.spec.subtitle}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              aria-label={`Close ${p.spec.title}`}
              data-testid={`payroll-pane-close-${p.spec.key}`}
              className="rounded px-1.5 text-content-muted hover:text-content-strong"
              onClick={() => onClose(p.spec.key)}
            >
              ×
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 [font-variant-numeric:tabular-nums]">
            {p.spec.body}
          </div>
        </section>
      ))}
    </div>
  )
}
