/**
 * Quote Focus registration — S-3a (§4.5 Act→Decide escalation).
 *
 * Side-effect module: importing this file registers the quote Focus so
 * `useFocus().open(QUOTE_FOCUS_ID, { params: { extraction } })` resolves
 * to QuoteFocusWithAccessories. Imported once at App bootstrap (mirrors
 * the scheduling-focus register.ts pattern).
 *
 * mode = "editCanvas" is the §5.2 assignment for quote-building — the
 * FORWARD-STABLE identity. S-3a mounts a DISPLAY core (coreComponent
 * override); S-3b swaps coreComponent for the real edit-canvas line-item
 * editor without touching the mode, id, escalation seam, or params
 * contract. (The disabled `EditCanvasCore` placeholder is NOT used — the
 * coreComponent override takes precedence in mode-dispatcher.)
 */

import { registerFocus } from "@/contexts/focus-registry"

import { QuoteFocusWithAccessories } from "./QuoteFocusWithAccessories"

/** Stable id — shared by S-3a (display core) and S-3b (editable core). */
export const QUOTE_FOCUS_ID = "quote-building"

registerFocus({
  id: QUOTE_FOCUS_ID,
  mode: "editCanvas",
  displayName: "Quote",
  coreComponent: QuoteFocusWithAccessories,
})
