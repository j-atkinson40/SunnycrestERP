/**
 * The Opas sphere — the entrance, and the only always-present chrome in the
 * new shell.
 *
 * ⚠️ MEASURED FROM `docs/prototypes/2026-11-17-opas-sphere.html`. The geometry,
 * the thresholds and the timings below are that file's; where a value appears
 * here it is because it appears there, not because it was chosen. The CSS lives
 * in `styles/opas-sphere.css` because keyframes and `::before`/`::after` cannot
 * be expressed as inline styles, and the six layers need both.
 *
 * ⚠️ **NO GLOW WHEN IDLE.** `quiet` has no rule in the stylesheet at all, so the
 * halo keeps its `opacity: 0`. James, 2026-11-17: "it's canon", and it applies
 * to admin's sphere too — which is why this component replaces the always-lit
 * button in `OpasHost.tsx` rather than sitting beside it.
 *
 * ⚠️ **POSITION IS SESSION-SCOPED AND NOT PERSISTED.** Dragging it is arranging,
 * not configuring — the same rule park follows (CLAUDE.md, act-side spatial
 * discipline: "anything wanting durable placement gets promoted … never
 * silently persisted"). It returns to the right edge on reload, deliberately.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import {
  clampY,
  clampv,
  edgeX,
  isDrag,
  specTarget,
  SPEC_RETURN_MS,
  SPEC_REST_X,
  SPEC_REST_Y,
  SPHERE_SIZE,
  snapSide,
} from "./sphere-geometry"

/** The four states, which are the note's four fragment moods. `quiet` is the
 *  one with no glow, and is where the sphere sits for most of the day. */
export type SphereState = "quiet" | "suggest" | "working" | "needs" | "done"

interface Props {
  state: SphereState
  /** Called on a press that did NOT become a drag. */
  onOpen: () => void
  /** Opas is open; the sphere steps out of the way without unmounting. */
  hidden?: boolean
  /** Right of the hint's label — "· something needs you". Absent renders nothing. */
  hintDetail?: string
  /** Shown in the hint as the shortcut. The new shell binds ⌘K; the admin
   *  shell does not, and passes nothing. */
  shortcut?: string
}

interface Pos { side: "left" | "right"; y: number }

export function Sphere({ state, onOpen, hidden = false, hintDetail, shortcut }: Props) {
  const ref = useRef<HTMLButtonElement | null>(null)
  const hintRef = useRef<HTMLDivElement | null>(null)
  const pos = useRef<Pos>({ side: "right", y: 0.72 })
  const drag = useRef<{ sx: number; sy: number; ox: number; oy: number; moved: boolean } | null>(null)
  const [dragging, setDragging] = useState(false)
  const [settling, setSettling] = useState(false)
  const [hintShown, setHintShown] = useState(false)
  const hintTimer = useRef<number | undefined>(undefined)

  /** Place it against its edge. The viewport is the stage — the prototype used
   *  `#stage` because it had one; `position: fixed` makes the viewport the
   *  equivalent, and the arithmetic is otherwise identical. */
  const place = useCallback((anim: boolean) => {
    const el = ref.current
    if (!el) return
    const w = window.innerWidth
    const h = window.innerHeight
    const x = edgeX(pos.current.side, w)
    const y = clampY(pos.current.y, h)
    if (anim) {
      setSettling(true)
      window.setTimeout(() => setSettling(false), 400)
    }
    el.style.left = `${x}px`
    el.style.top = `${y}px`
  }, [])

  useEffect(() => {
    place(false)
    const onResize = () => place(false)
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [place])

  /** ⚠️ THE SPECULAR HIGHLIGHT IS WRITTEN TO THE DOM, NOT TO REACT STATE. It
   *  moves every frame; a `setState` per frame would re-render the tree at
   *  60fps for a cosmetic gradient. `prefers-reduced-motion` snaps instead of
   *  easing, which is the prototype's own behaviour. */
  useEffect(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false
    let lx = SPEC_REST_X, ly = SPEC_REST_Y, tx = SPEC_REST_X, ty = SPEC_REST_Y, last = 0
    let raf = 0

    const onMove = (e: PointerEvent) => {
      const el = ref.current
      if (!el) return
      const r = el.getBoundingClientRect()
      const t = specTarget(e.clientX - (r.left + r.width / 2),
                           e.clientY - (r.top + r.height / 2))
      tx = t.x
      ty = t.y
      last = performance.now()
    }

    const tick = () => {
      if (performance.now() - last > SPEC_RETURN_MS) { tx = SPEC_REST_X; ty = SPEC_REST_Y }
      if (reduced) { lx = tx; ly = ty } else { lx += (tx - lx) * 0.08; ly += (ty - ly) * 0.08 }
      const el = ref.current
      if (el) {
        el.style.setProperty("--lx", `${lx.toFixed(1)}%`)
        el.style.setProperty("--ly", `${ly.toFixed(1)}%`)
      }
      raf = requestAnimationFrame(tick)
    }

    window.addEventListener("pointermove", onMove, { passive: true })
    raf = requestAnimationFrame(tick)
    return () => {
      window.removeEventListener("pointermove", onMove)
      cancelAnimationFrame(raf)
    }
  }, [])

  const onPointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (e.button !== 0) return
    /* ⚠️ GUARDED BECAUSE A MISSING API HERE CRASHES THE ENTRANCE. The
       prototype called this unconditionally, which is safe in a browser and
       was not safe here: jsdom does not implement pointer capture, so the
       first click on the sphere threw `setPointerCapture is not a function`
       and Opas never opened. 149 Opas tests went red on it — and the same
       throw would reach any real environment missing the API. Capture is an
       improvement to dragging, not a requirement for it: without it a drag
       that leaves the button stops tracking, which is a degradation rather
       than a failure. */
    const el = ref.current
    if (el && typeof el.setPointerCapture === "function") el.setPointerCapture(e.pointerId)
    const r = e.currentTarget.getBoundingClientRect()
    drag.current = {
      sx: e.clientX, sy: e.clientY,
      ox: e.clientX - r.left, oy: e.clientY - r.top,
      moved: false,
    }
    setHintShown(false)
  }

  const onPointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    const d = drag.current
    if (!d) return
    if (!d.moved && isDrag(e.clientX - d.sx, e.clientY - d.sy)) {
      d.moved = true
      setDragging(true)
    }
    if (!d.moved) return
    const el = ref.current
    if (!el) return
    el.style.left = `${clampv(e.clientX - d.ox, 0, window.innerWidth - SPHERE_SIZE)}px`
    el.style.top = `${clampv(e.clientY - d.oy, 0, window.innerHeight - SPHERE_SIZE)}px`
  }

  /** On release: a drag snaps to the NEARER horizontal edge keeping its y
   *  fraction; a press that never moved opens Opas. */
  const end = (e: React.PointerEvent<HTMLButtonElement>) => {
    const d = drag.current
    if (!d) return
    drag.current = null
    setDragging(false)
    if (d.moved) {
      const el = ref.current
      if (!el) return
      const r = el.getBoundingClientRect()
      pos.current = {
        side: snapSide(r.left, window.innerWidth),
        y: r.top / window.innerHeight,
      }
      place(true)
    } else if (e.type === "pointerup") {
      onOpen()
    }
  }

  const onPointerEnter = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (e.pointerType !== "mouse" || drag.current || hidden) return
    hintTimer.current = window.setTimeout(() => {
      const el = ref.current, hint = hintRef.current
      if (!el || !hint) return
      const r = el.getBoundingClientRect()
      hint.style.left = "0px"
      const w = hint.offsetWidth, h = hint.offsetHeight
      const x = pos.current.side === "right" ? r.left - w - 12 : r.right + 12
      hint.style.left = `${clampv(x, 8, window.innerWidth - w - 8)}px`
      hint.style.top = `${r.top + SPHERE_SIZE / 2 - h / 2}px`
      setHintShown(true)
    }, 350)
  }

  const onPointerLeave = () => {
    window.clearTimeout(hintTimer.current)
    setHintShown(false)
  }

  return (
    <>
      <button
        type="button"
        ref={ref}
        className="opas-sphere"
        data-testid="opas-sphere"
        data-state={state}
        data-dragging={dragging ? "true" : "false"}
        data-settling={settling ? "true" : "false"}
        data-hidden={hidden ? "true" : "false"}
        aria-label="Open Opas"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={end}
        onPointerCancel={end}
        onPointerEnter={onPointerEnter}
        onPointerLeave={onPointerLeave}
        /* ⚠️ KEYBOARD GOES THROUGH `onClick`, AND ONLY WHEN THERE WAS NO POINTER.
           `e.detail === 0` is how the prototype tells Enter/Space from a mouse
           click, whose open already happened in `end`. Without the guard a
           mouse click opens Opas twice. */
        onClick={(e) => { if (e.detail === 0) onOpen() }}
      >
        <span className="halo" />
        <span className="ball" />
        <span className="tint" />
        <span className="inner" />
        <span className="spec" />
        <span className="rim" />
      </button>
      <div
        ref={hintRef}
        className="opas-sphere-hint"
        data-testid="opas-sphere-hint"
        data-show={hintShown && !hidden ? "true" : "false"}
        aria-hidden="true"
      >
        <span>Opas</span>
        {hintDetail ? <span className="st">{hintDetail}</span> : null}
        {shortcut ? <kbd>{shortcut}</kbd> : null}
      </div>
    </>
  )
}
