/**
 * The sphere's arithmetic, separated from its DOM so it can be tested.
 *
 * ⚠️ **WHY THIS FILE EXISTS.** A drag test driven through jsdom asserts nothing
 * useful: `getBoundingClientRect` returns all zeros there, so the snap would
 * always compute "left" and a test watching it would pass for a reason
 * unrelated to the rule (CLAUDE.md §11, mechanism B). The geometry is pure, so
 * it is tested as arithmetic against stated viewports, and the component is
 * tested for the thing a DOM can actually show: that a click opens Opas and a
 * drag does not.
 *
 * Values are the prototype's — see `docs/prototypes/2026-11-17-opas-sphere.html`.
 */

export const SPHERE_SIZE = 56
export const SPHERE_GUTTER = 16
export const DRAG_THRESHOLD = 5
export const SPEC_RETURN_MS = 2200
export const SPEC_REST_X = 34
export const SPEC_REST_Y = 28

export type SphereSide = "left" | "right"

export const clampv = (v: number, a: number, b: number) =>
  Math.min(Math.max(v, a), Math.max(a, b))

/** Which edge does a sphere whose LEFT is at `left` snap to?
 *
 * ⚠️ THE COMPARISON IS ON THE SPHERE'S CENTRE, NOT ITS LEFT EDGE. Using the
 * left edge would make the midpoint behave asymmetrically — a sphere straddling
 * the centre line would snap right while looking left-of-centre.
 */
export function snapSide(left: number, viewportWidth: number): SphereSide {
  return left + SPHERE_SIZE / 2 < viewportWidth / 2 ? "left" : "right"
}

/** The x the sphere rests at once snapped to `side`. */
export function edgeX(side: SphereSide, viewportWidth: number): number {
  return side === "left" ? SPHERE_GUTTER : viewportWidth - SPHERE_GUTTER - SPHERE_SIZE
}

/** The y for a stored vertical FRACTION, kept inside the gutter.
 *
 * ⚠️ THE BOTTOM BOUND IS 8px TIGHTER THAN THE TOP. That asymmetry is the
 * prototype's (`st.height - GT - SZ - 8`) and is kept rather than tidied: the
 * extra room is for the shadow the ball casts, which a symmetric clamp would
 * push off-screen.
 */
export function clampY(fraction: number, viewportHeight: number): number {
  return clampv(fraction * viewportHeight, SPHERE_GUTTER,
                viewportHeight - SPHERE_GUTTER - SPHERE_SIZE - 8)
}

/** Has a press travelled far enough to be a drag rather than a click? */
export function isDrag(dx: number, dy: number): boolean {
  return Math.hypot(dx, dy) > DRAG_THRESHOLD
}

/** Where the specular highlight is aimed for a pointer at `(dx, dy)` from the
 *  sphere's centre. Falls back to rest when the pointer is exactly centred. */
export function specTarget(dx: number, dy: number): { x: number; y: number } {
  const d = Math.hypot(dx, dy) || 1
  const k = Math.min(1, d / 260)
  return { x: 50 + (dx / d) * 20 * k, y: 46 + (dy / d) * 20 * k }
}
