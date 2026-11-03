/**
 * Dragging a held word onto a line: the parts that are not React.
 *
 * Slice 2, item 3 (James, 2026-10-28): *"the 'Not placed yet' strip — drag a held word
 * onto a field, edit inline, × to drop."*
 *
 * ⚠️ POINTER EVENTS, NOT HTML5 DRAG AND DROP, FOLLOWING THE PROTOTYPE EXACTLY.
 * `docs/prototypes/2026-10-27-guided-order-capture.html` listens on `pointerdown` /
 * `pointermove` / `pointerup` and resolves the target with `elementFromPoint`. Three
 * reasons it is not `draggable`:
 *
 *   1. **Touch.** HTML5 drag-and-drop does not fire on iOS Safari at all. The office
 *      uses iPads, and a gesture that silently does nothing there is worse than none.
 *   2. **The ghost.** `dataTransfer.setDragImage` cannot be styled; the prototype's
 *      drag ghost is the same `.fly` chip the flight uses, so one visual language
 *      covers a word flying on its own and a word being carried.
 *   3. **The click.** A pointer press that moves less than the threshold is a CLICK,
 *      which opens the inline edit. One gesture, two outcomes, decided by distance —
 *      which `draggable` cannot express because it consumes the press.
 *
 * ⚠️ AND THE THRESHOLD IS WHAT MAKES CLICK-TO-EDIT POSSIBLE AT ALL. Without it every
 * press is a drag, every chip needs a separate edit affordance, and a director who
 * meant to fix a typo drops the word on whichever row their finger was over.
 */

/** The prototype's `Math.hypot(…) < 5`. */
export const DRAG_THRESHOLD_PX = 5

/** Has this press travelled far enough to be a drag rather than a click? */
export function isADrag(
  from: { readonly x: number; readonly y: number },
  to: { readonly x: number; readonly y: number },
): boolean {
  return Math.hypot(to.x - from.x, to.y - from.y) >= DRAG_THRESHOLD_PX
}

/** The prototype's ghost offset — `translate(clientX+12, clientY-16)`. */
export const GHOST_DX = 12
export const GHOST_DY = -16

/**
 * Which field the pointer is over, and the row element to highlight.
 *
 * ⚠️ IT READS `data-drop-field`, NOT `data-fields`, and the two are different
 * questions. `data-fields` is every field a row DISPLAYS — the cemetery row shows
 * `cemetery`, `cemetery_city` and `eta` — and is what a flight uses to find its
 * destination. `data-drop-field` is the one field a drop WRITES, which is the row's
 * own `edit_target`: the same field clicking the row asks about. Dropping onto the
 * first displayed field would send a cemetery name to the Service row's free-text
 * slot.
 *
 * ⚠️ AND IT USES `elementFromPoint` RATHER THAN THE EVENT'S TARGET, because the drag
 * ghost is under the pointer for the whole gesture. `event.target` would be the ghost
 * every time; the prototype hits the same wall and solves it the same way.
 */
export function dropTargetAt(
  x: number,
  y: number,
  doc?: Document,
): { readonly fieldId: string; readonly row: Element } | null {
  const d = doc ?? (typeof document === "undefined" ? null : document)
  if (d === null || typeof d.elementFromPoint !== "function") return null
  const el = d.elementFromPoint(x, y)
  if (el === null) return null
  const row = el.closest("[data-drop-field]")
  if (row === null) return null
  const fieldId = row.getAttribute("data-drop-field") ?? ""
  // ⚠️ AN EMPTY `data-drop-field` IS REFUSED RATHER THAN DROPPED ONTO. A row whose
  // `edit_target` is absent and whose `field_ids` are empty renders the attribute as
  // "", and placing against a field id of "" is a write with no row to show it in.
  if (fieldId === "") return null
  return { fieldId, row }
}
