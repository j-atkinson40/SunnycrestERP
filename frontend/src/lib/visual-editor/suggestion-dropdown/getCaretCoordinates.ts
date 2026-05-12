/**
 * Arc 4b.2b — getCaretCoordinates companion utility.
 *
 * Computes the caret pixel position (top + left) inside an
 * HTMLTextAreaElement OR HTMLInputElement at a given character
 * position. Returned coordinates are absolute viewport
 * coordinates (in CSS pixels relative to the document) so consumers
 * can pass them directly into `SuggestionDropdown.position`, which
 * renders `position: fixed` and expects viewport coordinates.
 *
 * Mirror-element technique:
 *   - Create a hidden `<div>` whose styling matches the textarea
 *     /input character-by-character (font, padding, border, line-height,
 *     letter-spacing, white-space, word-wrap, box-sizing, width).
 *   - Insert content up to the target caret position; append a
 *     marker `<span>` at the target position.
 *   - Read the marker `<span>`'s offsetTop + offsetLeft inside the
 *     mirror.
 *   - Add the textarea's `getBoundingClientRect()` viewport origin
 *     and subtract its `scrollTop` / `scrollLeft`.
 *   - Remove the mirror.
 *
 * Cross-element-kind support: both `HTMLTextAreaElement` and
 * `HTMLInputElement` are accepted. Inputs render single-line
 * (white-space: pre, no word-wrap) which the mirror styling
 * replicates. Textareas use pre-wrap.
 *
 * Companion-utility canon (Q-ARC4B2-4 settled outcome b):
 *   SuggestionDropdown stays presentation-only — consumer owns
 *   position resolution. This helper is the canonical resolver for
 *   textarea/input consumers; future contenteditable / rich-text
 *   consumers will warrant their own resolver per CLAUDE.md
 *   per-consumer endpoint shaping canon (different surface kind,
 *   different mechanism).
 *
 * Mirror-element technique reference: widely-documented pattern
 * (see e.g. https://github.com/component/textarea-caret-position).
 * This is an in-source implementation — no third-party dependency —
 * so the registry's no-runtime-cost discipline is preserved.
 *
 * jsdom note: getComputedStyle works in jsdom; offset measurements
 * are largely 0 because jsdom doesn't compute layout. Tests use
 * monkey-patches to validate the math; production runtime relies
 * on a real browser layout engine.
 */


/** Result shape. Top + left are absolute viewport coordinates in
 *  CSS pixels (suitable for `position: fixed`). */
export interface CaretCoordinates {
  top: number
  left: number
}


/** CSS properties the mirror element must copy verbatim from the
 *  source input/textarea to produce a character-accurate layout. */
const MIRROR_PROPERTIES = [
  "boxSizing",
  "width",
  // box model
  "borderTopWidth",
  "borderRightWidth",
  "borderBottomWidth",
  "borderLeftWidth",
  "paddingTop",
  "paddingRight",
  "paddingBottom",
  "paddingLeft",
  // typography
  "fontStyle",
  "fontVariant",
  "fontWeight",
  "fontStretch",
  "fontSize",
  "fontSizeAdjust",
  "lineHeight",
  "fontFamily",
  "textAlign",
  "textTransform",
  "textIndent",
  "textDecoration",
  "letterSpacing",
  "wordSpacing",
  "tabSize",
  // wrapping
  "whiteSpace",
  "wordWrap",
  "wordBreak",
  "overflowWrap",
] as const


/** True when `el` is single-line (HTMLInputElement) rather than
 *  multi-line (HTMLTextAreaElement). Inputs collapse newlines to
 *  spaces; mirror must use white-space: pre. */
function isSingleLineInput(
  el: HTMLTextAreaElement | HTMLInputElement,
): el is HTMLInputElement {
  return el.tagName === "INPUT"
}


/**
 * Compute the caret pixel coordinates for `position` (0-indexed
 * character offset into `el.value`) inside the textarea/input,
 * returned as absolute viewport coordinates.
 *
 * The returned top corresponds to the TOP of the line the caret
 * is on. Consumers wanting to anchor a dropdown BELOW the line
 * should add the line-height (read from computed style) to top.
 */
export function getCaretCoordinates(
  el: HTMLTextAreaElement | HTMLInputElement,
  position: number,
): CaretCoordinates {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return { top: 0, left: 0 }
  }
  // Guardrails — clamp position into [0, value.length].
  const value = el.value ?? ""
  const safePos = Math.max(0, Math.min(position, value.length))

  const computed = window.getComputedStyle(el)
  const singleLine = isSingleLineInput(el)

  const mirror = document.createElement("div")
  // Position off-screen but in-flow for offsetTop/Left measurement.
  mirror.style.position = "absolute"
  mirror.style.visibility = "hidden"
  mirror.style.top = "0"
  mirror.style.left = "-9999px"
  mirror.style.overflow = "hidden"
  // Copy mirror-matching properties.
  for (const prop of MIRROR_PROPERTIES) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(mirror.style as any)[prop] = (computed as any)[prop]
  }
  // Override white-space for single-line inputs.
  if (singleLine) {
    mirror.style.whiteSpace = "pre"
    mirror.style.wordWrap = "normal"
    mirror.style.overflowWrap = "normal"
  } else {
    mirror.style.whiteSpace = "pre-wrap"
    mirror.style.wordWrap = "break-word"
  }

  // Insert text up to the caret, then a marker.
  // Use a Text node + <span> to keep DOM minimal.
  const before = value.substring(0, safePos)
  // For input elements, replace newlines with spaces (inputs collapse).
  const renderedBefore = singleLine ? before.replace(/\n/g, " ") : before
  mirror.appendChild(document.createTextNode(renderedBefore))

  const marker = document.createElement("span")
  // A zero-width content prevents the marker from affecting layout
  // beyond what a real caret would. Browsers render zero-width
  // spans with the line-height of surrounding text.
  marker.textContent = "​"
  mirror.appendChild(marker)

  document.body.appendChild(mirror)

  const markerTop = marker.offsetTop
  const markerLeft = marker.offsetLeft

  document.body.removeChild(mirror)

  // Map mirror-relative coordinates to viewport coordinates via
  // the source element's bounding rect, subtracting its scroll.
  const rect = el.getBoundingClientRect()
  const top = rect.top + markerTop - el.scrollTop
  const left = rect.left + markerLeft - el.scrollLeft

  return { top, left }
}


// Re-export internals for unit tests.
export const __testing__ = {
  MIRROR_PROPERTIES,
  isSingleLineInput,
}
