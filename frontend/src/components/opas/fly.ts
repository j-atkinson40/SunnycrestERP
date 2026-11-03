/**
 * A recognized word on its way into the order. Slice 2, clause 1.
 *
 * James, 2026-10-28: *"words leave the bar when typed past and fly into their field (the
 * prototype's animation)"*.
 *
 * ⚠️ EVERY NUMBER HERE IS THE PROTOTYPE'S, QUOTED RATHER THAN CHOSEN.
 * `docs/prototypes/2026-10-27-guided-order-capture.html` (92,138 bytes), its `fly()`:
 *
 *     const h=el.offsetHeight,x0=rect.x,y0=rect.y-h/2;
 *     const tr=tgt.getBoundingClientRect();
 *     const x1=tr.left,y1=tr.top+Math.min(tr.height,24)/2-h/2;
 *     const mx=x0+(x1-x0)*.55,my=Math.min(y0,y1)-(field?26:12)+(y1-y0)*.5;
 *     el.animate([…],{duration:580,easing:'cubic-bezier(.35,.55,.2,1)',fill:'forwards'})
 *
 * and its landing: `r.classList.add('landed'); setTimeout(…,950)` against
 * `@keyframes landed{0%{background:rgba(74,166,115,.28)…}}`.
 *
 * ⚠️ THE MID-POINT IS WHAT MAKES IT AN ARC RATHER THAN A SLIDE, and it is the one part
 * a reimplementation would be most likely to drop: `my` lifts the chip ABOVE both
 * endpoints (`Math.min(y0,y1) - 26`), so the word rises out of the bar and falls into
 * the row. A two-keyframe animation between the same endpoints travels the same
 * distance and reads as a glitch.
 *
 * ⚠️ IT IS A MODULE RATHER THAN A HOOK, AND THE REASON IS TESTABILITY. The DOM work is
 * imperative — create a node, measure two rects, drive the Web Animations API — and
 * none of it belongs in a render. A pure-ish function taking the two rects can be
 * asserted on without a browser; what cannot be is left to the component test.
 *
 * ⚠️ AND `prefers-reduced-motion` SKIPS STRAIGHT TO THE LANDING, which is the
 * prototype's own `if(REDUCE||!tgt||!rect){land(field);return}`. The word still arrives
 * and the row still flashes; only the travel is dropped. A reduced-motion path that
 * skipped the landing too would make the gesture invisible to the people who need it
 * most legible.
 */

/** The prototype's `.fly` chip, as its own class so the CSS lives with the component. */
export const FLY_CLASS = "opas-fly"

/** The prototype's `duration:580`. */
export const FLY_MS = 580

/** The prototype's `easing:'cubic-bezier(.35,.55,.2,1)'`. */
export const FLY_EASING = "cubic-bezier(.35,.55,.2,1)"

/** The prototype's `setTimeout(…,950)` on `.row.landed`. */
export const LANDED_MS = 950

/** The prototype's `-(field?26:12)` lift at the arc's midpoint. */
export const ARC_LIFT_FIELD = 26
export const ARC_LIFT_TITLE = 12

/** The prototype's `.55` — the midpoint sits past half way, so the fall is shorter. */
const ARC_BIAS = 0.55

/** The prototype's `Math.min(tr.height,24)` — centre on the first line of a tall row. */
const TARGET_LINE_PX = 24

export interface Box {
  readonly left: number
  readonly top: number
  readonly width: number
  readonly height: number
}

export interface FlightFrames {
  readonly from: { readonly x: number; readonly y: number }
  readonly mid: { readonly x: number; readonly y: number }
  readonly to: { readonly x: number; readonly y: number }
}

/**
 * The three points of the arc, from the word's rect in the bar to its row.
 *
 * ⚠️ PURE, SO THE GEOMETRY IS TESTABLE WITHOUT A DOM. `fly()` below does the node work;
 * this does the arithmetic, which is the half that can be wrong in a way nobody sees —
 * a chip that flies to the wrong row looks like a parser bug.
 *
 * `chipHeight` is the flying node's own height, which the prototype reads as
 * `el.offsetHeight` AFTER appending it. Both endpoints centre the chip vertically on
 * their anchor, which is why it is a parameter rather than a constant.
 */
export function flightFrames(
  from: Box,
  to: Box,
  chipHeight: number,
  toTitle = false,
): FlightFrames {
  const x0 = from.left
  const y0 = from.top - chipHeight / 2
  const x1 = to.left
  const y1 = to.top + Math.min(to.height, TARGET_LINE_PX) / 2 - chipHeight / 2
  const mx = x0 + (x1 - x0) * ARC_BIAS
  const lift = toTitle ? ARC_LIFT_TITLE : ARC_LIFT_FIELD
  const my = Math.min(y0, y1) - lift + (y1 - y0) * 0.5
  return { from: { x: x0, y: y0 }, mid: { x: mx, y: my }, to: { x: x1, y: y1 } }
}

/** Does this environment ask for less motion? */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches
  } catch {
    // ⚠️ SWALLOWED NARROWLY AND ON PURPOSE. `matchMedia` throws on a malformed query in
    // some jsdom versions, and a motion preference must never be able to take the pane
    // down. Reading "no preference" is the behaviour-preserving answer.
    return false
  }
}

/**
 * The on-screen rect of `[start,end)` in the bar, read off the mirror.
 *
 * ⚠️ THE MIRROR IS THE ONLY THING THAT KNOWS WHERE A CHARACTER IS. A textarea exposes
 * no per-character geometry, which is why the mirror exists at all — it renders the
 * same text in the same box behind the input so spans can be tinted. Slice 2's flight
 * needs the same measurement for its start point.
 *
 * ⚠️ AND IT MUST BE TAKEN BEFORE THE WORD IS REMOVED, which is the design review's own
 * finding: `spans_for_text` describes the text the server was handed, and clause 1 cuts
 * the word out of that text in the same gesture. A rect measured after the cut is the
 * rect of whatever moved into its place.
 *
 * ⚠️ MATCHED ON THE RANGE, NOT THE FIELD, because two pieces can carry the same field —
 * a director who names the funeral home twice — and the flight is about one of them.
 */
export function rectOfRange(
  mirror: Element | null | undefined,
  start: number,
  end: number,
): Box | null {
  if (!mirror) return null
  const el = mirror.querySelector(`[data-span-range="${start}-${end}"]`)
  if (!el) return null
  const r = el.getBoundingClientRect()
  // ⚠️ A ZERO-SIZE RECT IS REFUSED RATHER THAN FLOWN FROM. jsdom returns all zeros for
  // every element, and a real browser returns zeros for a node that has not been laid
  // out — flying from 0,0 would send the chip across the whole window from the corner.
  // `fly` lands immediately when there is no rect, which is the honest outcome.
  if (r.width === 0 && r.height === 0) return null
  return { left: r.left, top: r.top, width: r.width, height: r.height }
}

export interface FlyArgs {
  /** The word's rect in the bar, measured BEFORE it is removed from the text.
   *
   *  ⚠️ NULLABLE, because `rectOfRange` refuses a zero-size rect — jsdom has no
   *  layout, and a real browser returns zeros for a node not yet laid out. A null
   *  rect lands immediately rather than flying from the window's corner. */
  readonly from: Box | null
  /** The receiving row's value element. */
  readonly target: Element | null
  readonly text: string
  /** True when the destination is a pane TITLE rather than a field row. */
  readonly toTitle?: boolean
  /** Called when the chip arrives — the caller flashes the row here. */
  readonly onLanded?: () => void
  /** Injected in tests. Defaults to `document`. */
  readonly doc?: Document
}

/**
 * Fly `text` from `from` to `target`, then call `onLanded`.
 *
 * Returns a function that cancels the flight — the caller uses it on unmount, so a
 * chip cannot outlive the pane it was flying into.
 *
 * ⚠️ IT LANDS EVEN WHEN IT CANNOT FLY, which is the prototype's rule and the important
 * one: no target, no rect, reduced motion, or no `Element.animate` in this environment
 * all skip to `onLanded`. The value has already been recorded by the time this runs —
 * the animation is a report, not the write — so a browser that cannot animate must
 * still show the result.
 */
export function fly({
  from,
  target,
  text,
  toTitle = false,
  onLanded,
  doc,
}: FlyArgs): () => void {
  const d = doc ?? (typeof document === "undefined" ? null : document)
  const land = () => onLanded?.()

  if (d === null || target === null || from === null || prefersReducedMotion()) {
    land()
    return () => {}
  }

  const el = d.createElement("div")
  el.className = FLY_CLASS
  el.setAttribute("data-testid", "opas-fly")
  el.setAttribute("aria-hidden", "true")
  el.textContent = text
  d.body.appendChild(el)

  // ⚠️ MEASURED AFTER APPENDING, as the prototype does. An unattached node has no
  // height, so centring on it would put every chip half a line out.
  const chipHeight = el.offsetHeight || 22
  const frames = flightFrames(from, target.getBoundingClientRect(), chipHeight, toTitle)

  let cancelled = false
  const finish = () => {
    if (cancelled) return
    cancelled = true
    el.remove()
    land()
  }

  // ⚠️ `Element.animate` IS FEATURE-CHECKED BECAUSE jsdom DOES NOT HAVE IT. Without
  // this the component tests would throw inside a gesture rather than exercising it,
  // and the fallback is the same one reduced motion takes: land immediately.
  if (typeof el.animate !== "function") {
    finish()
    return () => {}
  }

  const anim = el.animate(
    [
      {
        transform: `translate(${frames.from.x}px,${frames.from.y}px) scale(1)`,
        opacity: 1,
      },
      {
        transform: `translate(${frames.mid.x}px,${frames.mid.y}px) scale(1.05)`,
        opacity: 1,
        offset: 0.5,
      },
      {
        transform: `translate(${frames.to.x}px,${frames.to.y}px) scale(.94)`,
        opacity: 0.1,
      },
    ],
    { duration: FLY_MS, easing: FLY_EASING, fill: "forwards" },
  )
  anim.onfinish = finish

  return () => {
    if (cancelled) return
    cancelled = true
    try {
      anim.cancel()
    } catch {
      // a cancelled animation that was already finished throws in some engines
    }
    el.remove()
  }
}

/**
 * The value element of the row that shows `fieldId`.
 *
 * ⚠️ MATCHED ON THE ROW'S FIELD LIST, NOT ON ITS ID, AND MY FIRST VERSION GOT THIS
 * WRONG IN A WAY NO TEST COULD HAVE SEEN. The leave effect queried
 * `[data-testid="capture-row-<fieldId>"]`, and a row's testid carries its `row_id` —
 * which equals its field id for only **6 of the 12** capture rows, measured against
 * `surfaces.CAPTURE_SALES_ORDER`. The other six are composed:
 *
 *     row_id 'cemetery'           fields cemetery, cemetery_city, eta
 *     row_id 'cemetery_equipment' fields cemetery_equipment, chairs_total, chairs_extra
 *     row_id 'dates'              fields date_of_birth, date_of_death, …
 *     row_id 'service'            fields service_location_other, service_location
 *     row_id 'personalization'    fields personalization, lifes_reflections_symbol
 *     row_id 'legacy_print'       fields legacy_series, legacy_print_name
 *
 * So a word landing in `cemetery_city`, `eta`, `chairs_total`, either date, or any
 * other composed field found NO target, and `fly` correctly fell through to its
 * land-immediately path. The word still arrived and the row still flashed — the
 * feature looked finished and simply never flew, for half the fields on the surface.
 *
 * ⚠️ AND IT WAS INVISIBLE TO EVERY TEST BY CONSTRUCTION. jsdom has no
 * `Element.animate`, so the component tests take the same land-immediately path
 * whatever the target is; `fly.test.ts` supplies its target directly and never looks
 * one up. A check that cannot tell a flight from a non-flight cannot report this.
 * Found by reading the row markup while wiring Tab, not by a failure.
 *
 * `~=` is the whitespace-separated-list match, which is exactly what `data-fields`
 * is — so one attribute selector answers "which row shows this field".
 */
export function rowValueFor(fieldId: string, doc?: Document): Element | null {
  const d = doc ?? (typeof document === "undefined" ? null : document)
  if (d === null || fieldId === "") return null
  // ⚠️ ESCAPED, BECAUSE A FIELD ID REACHES THIS FROM THE SERVER. A quote in the value
  // would otherwise end the attribute selector early and throw a SyntaxError inside a
  // gesture — the whole pane would stop rather than one word failing to fly.
  const safe = fieldId.replace(/["\\]/g, "\\$&")
  return d.querySelector(`[data-fields~="${safe}"] [data-testid="capture-row-value"]`)
}
