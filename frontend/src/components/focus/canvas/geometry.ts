/**
 * Canvas geometry — Phase A Session 3.5.
 *
 * Pure-function utilities for the Focus canvas. Zone-relative
 * (anchor-based) positioning replaces Session 3's absolute-pixel
 * model — widgets anchored to "right-rail" always land in the right
 * rail regardless of viewport width.
 *
 * Two coordinate spaces:
 *   - Anchor space — stored in WidgetPosition. Viewport-independent.
 *     `{ anchor, offsetX, offsetY, width, height }`.
 *   - Resolved space — computed at render time via
 *     `resolvePosition(pos, vw, vh)`. A viewport-absolute `Rect`
 *     used for overlap math, hit testing, CSS `left/top/width/
 *     height` styling, and as the intermediate space for drag/
 *     resize computation.
 *
 * Drag flow:
 *   1. Compute current resolved rect.
 *   2. Apply drag delta.
 *   3. Pick new anchor from drop point via
 *      `determineAnchorFromDrop`.
 *   4. Re-project to anchor-offset via `computeOffsetsForAnchor`.
 *   5. Clamp offsets (widget stays fully visible).
 *   6. Reject if resolved rect overlaps the core; else persist.
 *
 * Resize flow (per zone):
 *   1. Compute current resolved rect.
 *   2. Apply zone-specific delta (which edges/corners move).
 *   3. Enforce min size + clamp to canvas.
 *   4. Re-project to anchor-offset, preserving original anchor.
 */

import type {
  WidgetAnchor,
  WidgetPosition,
} from "@/contexts/focus-registry"


export const GRID_STEP = 8


/** Resolved viewport-absolute rect. */
export interface Rect {
  x: number
  y: number
  width: number
  height: number
}


/** Snap a raw pixel value to the nearest 8px increment. Normalizes
 *  negative-zero to +0 so callers + tests don't worry about sign. */
export function snapTo8px(value: number): number {
  return Math.round(value / GRID_STEP) * GRID_STEP + 0
}


/** Exclusive-boundary overlap. Edge-touching (a.right === b.left) is
 *  NOT overlap. */
export function rectsOverlap(a: Rect, b: Rect): boolean {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  )
}


// ── Anchor resolution ────────────────────────────────────────────

/** Resolve an anchor-based WidgetPosition to a viewport-absolute
 *  rect. Pure — no clamping. Callers that need the widget visible
 *  on a narrower viewport should `clampRectToCanvas` afterward. */
export function resolvePosition(
  pos: WidgetPosition,
  viewportWidth: number,
  viewportHeight: number,
): Rect {
  const { anchor, offsetX, offsetY, width, height } = pos

  let x = 0
  let y = 0

  switch (anchor) {
    case "top-left":
    case "left-rail":
      x = offsetX
      y = offsetY
      break
    case "top-center":
      x = (viewportWidth - width) / 2 + offsetX
      y = offsetY
      break
    case "top-right":
    case "right-rail":
      x = viewportWidth - width - offsetX
      y = offsetY
      break
    case "bottom-left":
      x = offsetX
      y = viewportHeight - height - offsetY
      break
    case "bottom-center":
      x = (viewportWidth - width) / 2 + offsetX
      y = viewportHeight - height - offsetY
      break
    case "bottom-right":
      x = viewportWidth - width - offsetX
      y = viewportHeight - height - offsetY
      break
  }

  return { x, y, width, height }
}


/** Invert resolution: given a desired absolute rect + a target
 *  anchor, compute the offsets needed to land the widget there.
 *
 *  Offsets are the DISTANCE from the anchor edge(s) — always
 *  non-negative under typical use (clamping keeps them in range).
 *  This function doesn't clamp; `clampPositionOffsets` does.
 */
export function computeOffsetsForAnchor(
  anchor: WidgetAnchor,
  rect: Rect,
  viewportWidth: number,
  viewportHeight: number,
): { offsetX: number; offsetY: number } {
  let offsetX = 0
  let offsetY = 0

  switch (anchor) {
    case "top-left":
    case "left-rail":
      offsetX = rect.x
      offsetY = rect.y
      break
    case "top-center":
      offsetX = rect.x - (viewportWidth - rect.width) / 2
      offsetY = rect.y
      break
    case "top-right":
    case "right-rail":
      offsetX = viewportWidth - rect.x - rect.width
      offsetY = rect.y
      break
    case "bottom-left":
      offsetX = rect.x
      offsetY = viewportHeight - rect.y - rect.height
      break
    case "bottom-center":
      offsetX = rect.x - (viewportWidth - rect.width) / 2
      offsetY = viewportHeight - rect.y - rect.height
      break
    case "bottom-right":
      offsetX = viewportWidth - rect.x - rect.width
      offsetY = viewportHeight - rect.y - rect.height
      break
  }

  return { offsetX, offsetY }
}


/** Given a drop point (absolute screen x/y) + viewport dims, pick
 *  the most appropriate anchor. Used by the drag-end handler to
 *  determine which zone the widget landed in.
 *
 *  Zone rules:
 *    - Edge rails: if drop.x is within 100px of left/right edge,
 *      pick left-rail / right-rail. Rails take precedence over
 *      corner zones because they provide stable vertical positioning
 *      regardless of where along the rail the drop landed.
 *    - Top/bottom half: drop.y < vh/2 → top-*, else bottom-*.
 *    - Horizontal third within top/bottom: drop.x < vw/3 → *-left;
 *      drop.x > 2*vw/3 → *-right; else *-center.
 *
 *  The 100px edge-rail threshold is a heuristic — wide enough to
 *  capture "user meant to dock to this edge" without forcing rail
 *  mode on every near-edge drop. */
export function determineAnchorFromDrop(
  dropX: number,
  dropY: number,
  viewportWidth: number,
  viewportHeight: number,
  railThreshold = 100,
): WidgetAnchor {
  // Edge rails first.
  if (dropX < railThreshold) return "left-rail"
  if (dropX > viewportWidth - railThreshold) return "right-rail"

  const topHalf = dropY < viewportHeight / 2
  const leftThird = dropX < viewportWidth / 3
  const rightThird = dropX > (viewportWidth * 2) / 3

  if (topHalf) {
    if (leftThird) return "top-left"
    if (rightThird) return "top-right"
    return "top-center"
  } else {
    if (leftThird) return "bottom-left"
    if (rightThird) return "bottom-right"
    return "bottom-center"
  }
}


// ── Clamping ────────────────────────────────────────────────────

/** Clamp an absolute rect so it fits fully within the canvas.
 *  Output x/y keep top/left edges in range; width/height are not
 *  changed here. Callers must `enforceMinSize` before clamping if
 *  they want a minimum-respecting result.
 *
 *  If the widget is wider/taller than the canvas, x/y = 0 (upper-
 *  left corner anchored) and width/height overflow rightward/
 *  downward — caller should clamp dimensions separately via
 *  `clampRectDimensions` if visual occlusion must be avoided. */
export function clampRectToCanvas(
  rect: Rect,
  canvasWidth: number,
  canvasHeight: number,
): Rect {
  const maxX = Math.max(0, canvasWidth - rect.width)
  const maxY = Math.max(0, canvasHeight - rect.height)
  return {
    ...rect,
    x: Math.max(0, Math.min(rect.x, maxX)),
    y: Math.max(0, Math.min(rect.y, maxY)),
  }
}


/** Clamp a rect's width/height so it fits within the canvas bounds.
 *  Used when a viewport is narrower than the widget — reduce width
 *  but respect minWidth. */
export function clampRectDimensions(
  rect: Rect,
  canvasWidth: number,
  canvasHeight: number,
  minWidth: number,
  minHeight: number,
): Rect {
  return {
    ...rect,
    width: Math.max(minWidth, Math.min(rect.width, canvasWidth)),
    height: Math.max(minHeight, Math.min(rect.height, canvasHeight)),
  }
}


/** Enforce min width/height on a rect (keep dimensions ≥ min). */
export function enforceMinRect(
  rect: Rect,
  minWidth: number,
  minHeight: number,
): Rect {
  return {
    ...rect,
    width: Math.max(minWidth, rect.width),
    height: Math.max(minHeight, rect.height),
  }
}


/** Clamp a WidgetPosition's offsets so the widget stays fully within
 *  the viewport. Preserves anchor + width + height; adjusts offsetX
 *  and offsetY only. Used at persistence time (drop-end, resize-end)
 *  to keep stored positions valid.
 *
 *  Inverse-of-resolve: the resolved rect goes through clampRectTo
 *  Canvas, then re-projects to the same anchor. */
export function clampPositionOffsets(
  pos: WidgetPosition,
  viewportWidth: number,
  viewportHeight: number,
): WidgetPosition {
  const resolved = resolvePosition(pos, viewportWidth, viewportHeight)
  const clamped = clampRectToCanvas(resolved, viewportWidth, viewportHeight)
  const offsets = computeOffsetsForAnchor(
    pos.anchor,
    clamped,
    viewportWidth,
    viewportHeight,
  )
  return {
    ...pos,
    offsetX: Math.max(0, offsets.offsetX),
    offsetY: Math.max(0, offsets.offsetY),
  }
}


// ── Zone resize ──────────────────────────────────────────────────

export type ResizeZone = "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w"


/** Apply a pointer delta (cursor movement since pointer-down) to an
 *  absolute rect, given which resize zone the user is dragging.
 *
 *  Each zone constrains which edges of the rect move:
 *    nw/n/ne → top edge moves
 *    nw/w/sw → left edge moves
 *    sw/s/se → bottom edge moves
 *    ne/e/se → right edge moves
 *
 *  This function is pure. Caller enforces min size + canvas clamp
 *  separately via enforceMinRect + clampRectToCanvas. */
export function applyResizeDelta(
  zone: ResizeZone,
  startRect: Rect,
  dx: number,
  dy: number,
): Rect {
  let { x, y, width, height } = startRect

  // Horizontal: left edge moves (w/sw/nw) OR right edge moves (e/se/ne)
  if (zone === "w" || zone === "sw" || zone === "nw") {
    x = startRect.x + dx
    width = startRect.width - dx
  } else if (zone === "e" || zone === "se" || zone === "ne") {
    width = startRect.width + dx
  }

  // Vertical: top edge moves (n/nw/ne) OR bottom edge moves (s/sw/se)
  if (zone === "n" || zone === "nw" || zone === "ne") {
    y = startRect.y + dy
    height = startRect.height - dy
  } else if (zone === "s" || zone === "sw" || zone === "se") {
    height = startRect.height + dy
  }

  return { x, y, width, height }
}


// ── Smart positioning engine ─────────────────────────────────────

export interface OpenZoneInput {
  canvasWidth: number
  canvasHeight: number
  /** Forbidden zone (anchored core). */
  coreRect: Rect
  /** All existing widget resolved rects; new widget must not
   *  overlap any. */
  existing: Rect[]
  widgetWidth: number
  widgetHeight: number
  /** Minimum gap between widget and canvas edge. Default 8px. */
  margin?: number
}


/** Anchor-aware smart positioning. Scans preferred zones in order
 *  (top-left → top-center → top-right → left-rail → right-rail →
 *  bottom-left → bottom-center → bottom-right) and returns the first
 *  anchor + offsets that fit without overlap.
 *
 *  Returns null if no zone can hold the widget.
 *
 *  Session 3.5 heuristic — Session 5+ refines with data-relationship
 *  context once real pins exist. */
export function findOpenZone(
  input: OpenZoneInput,
): WidgetPosition | null {
  const {
    canvasWidth,
    canvasHeight,
    coreRect,
    existing,
    widgetWidth,
    widgetHeight,
    margin = GRID_STEP,
  } = input

  const PREFERENCE: WidgetAnchor[] = [
    "top-left",
    "top-center",
    "top-right",
    "left-rail",
    "right-rail",
    "bottom-left",
    "bottom-center",
    "bottom-right",
  ]

  for (const anchor of PREFERENCE) {
    // Scan 8px at a time — offsetX/offsetY start at margin and grow.
    for (let offY = margin; offY < canvasHeight; offY += GRID_STEP) {
      for (let offX = margin; offX < canvasWidth; offX += GRID_STEP) {
        const candidate: WidgetPosition = {
          anchor,
          offsetX: snapTo8px(offX),
          offsetY: snapTo8px(offY),
          width: widgetWidth,
          height: widgetHeight,
        }
        const rect = resolvePosition(candidate, canvasWidth, canvasHeight)

        // Reject if out of bounds.
        if (
          rect.x < 0 ||
          rect.y < 0 ||
          rect.x + rect.width > canvasWidth ||
          rect.y + rect.height > canvasHeight
        ) {
          // For top anchors scanning offsetY, once we exceed the
          // anchor's available vertical extent, stop — higher offY
          // won't help for this anchor.
          break
        }

        // Reject if overlapping core or existing widgets.
        if (rectsOverlap(rect, coreRect)) continue
        if (existing.some((r) => rectsOverlap(rect, r))) continue

        return candidate
      }
    }
  }

  return null
}


/** Compute the anchored core's viewport rect from CSS constants —
 *  matches the Focus.tsx Popup dimensions. */
export function computeCoreRect(
  viewportWidth: number,
  viewportHeight: number,
): Rect {
  const width = Math.min(1400, viewportWidth * 0.9)
  const height = Math.min(900, viewportHeight * 0.85)
  return {
    x: (viewportWidth - width) / 2,
    y: (viewportHeight - height) / 2,
    width,
    height,
  }
}
