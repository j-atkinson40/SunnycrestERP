/**
 * Whether a typed line means "close the pane in front".
 *
 * ⚠️ JAMES'S FOURTH MULTI-PANE RULE (2026-10-19): "'close' in the bar closes the front
 * pane; Esc behaviour unchanged." Esc still tucks the whole session and comes back where
 * you left it; "close" ends one pane. Two gestures, two meanings, and this file is only
 * the second one — nothing here touches `onEscape`.
 *
 * ⚠️ AN EXACT LIST, NOT A `\bclose\b` TEST, AND THAT IS THE WHOLE DESIGN. The order list
 * already has a "close" vocabulary of its own: an order delivered and not closed out
 * carries the `close` flag, labelled "Delivered, not closed out" with the action "Close
 * it out" (`stage.FLAG_COPY`). A substring rule would make "close it out" close the pane
 * instead of acting on the order — the false-presence-from-a-substring defect, with the
 * two meanings eight characters apart.
 *
 * ⚠️ SO "close it out" IS DELIBERATELY ABSENT FROM THE LIST BELOW, and the test asserts
 * that it is. Adding it later would break the order action.
 */

/** Trim, lower-case, drop trailing punctuation, collapse whitespace. */
function cleaned(text: string): string {
  return text.toLowerCase().trim().replace(/[.!?,;:]+$/g, "").replace(/\s+/g, " ").trim()
}

/** Every phrase that closes the front pane. Exact matches only. */
export const CLOSE_PHRASES: readonly string[] = [
  "close",
  "close it",
  "close this",
  "close that",
  "close pane",
  "close the pane",
  "close this pane",
  "close that pane",
  "dismiss",
]

export function isCloseRequest(text: string): boolean {
  return CLOSE_PHRASES.includes(cleaned(text))
}
