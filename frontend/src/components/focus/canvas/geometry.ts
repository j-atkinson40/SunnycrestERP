/**
 * Canvas geometry — Phase A Session 3.
 *
 * Pure-function utilities for the Focus canvas coordinate system.
 *
 * Coordinate system:
 *   - Origin (0, 0) at viewport top-left.
 *   - All widget positions + sizes are pixel values, snapped to 8px
 *     increments (PA §5.1 "snaps to 8px grid").
 *   - Canvas bounds = full viewport (`window.innerWidth` x
 *     `window.innerHeight`).
 *   - The anchored core is a forbidden zone centered in the viewport.
 *
 * These functions are pure — no DOM access, no side effects. The
 * Canvas component reads `window.innerWidth/Height` + the core's
 * measured rect and passes them to these helpers.
 */

import type { WidgetPosition } from "@/contexts/focus-registry"


/** The 8-pixel snap step per PA §5.1. Exported for tests + external
 *  consumers that need to know the grid size. */
export const GRID_STEP = 8


/** Rect abstraction — a position + size without the widget's
 *  identity. Used for overlap math and for passing rects between
 *  helpers. */
export interface Rect {
  x: number
  y: number
  width: number
  height: number
}


/** Snap a raw pixel value to the nearest 8px increment. Input may be
 *  fractional (from cursor deltas); output is always a multiple of
 *  GRID_STEP. */
export function snapTo8px(value: number): number {
  // `+ 0` normalizes `-0` (Math.round of a small-negative can yield
  // negative zero) to positive zero so callers + tests don't have
  // to care about the sign-of-zero distinction.
  return Math.round(value / GRID_STEP) * GRID_STEP + 0
}


/** Return true if two rects share any area. Edge-touching is NOT
 *  considered overlap (widget at x=100 with width=50 does not overlap
 *  a widget starting at x=150). */
export function rectsOverlap(a: Rect, b: Rect): boolean {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  )
}


/** Clamp a widget's x/y so the whole widget stays within canvas
 *  bounds. Does not resize — too-large widgets retain their width/
 *  height and are pushed to the upper-left edge. Output is already
 *  8px-snapped on input assumption; callers who pass fractional
 *  inputs should `snapTo8px()` each field first. */
export function clampToCanvas(
  widget: WidgetPosition,
  canvasWidth: number,
  canvasHeight: number,
): WidgetPosition {
  const maxX = Math.max(0, canvasWidth - widget.width)
  const maxY = Math.max(0, canvasHeight - widget.height)
  return {
    ...widget,
    x: Math.max(0, Math.min(widget.x, maxX)),
    y: Math.max(0, Math.min(widget.y, maxY)),
  }
}


/** Enforce minimum width/height (both 8px-snapped) on a proposed
 *  widget size. */
export function enforceMinSize(
  widget: WidgetPosition,
  minWidth: number,
  minHeight: number,
): WidgetPosition {
  return {
    ...widget,
    width: Math.max(minWidth, widget.width),
    height: Math.max(minHeight, widget.height),
  }
}


/** Parameters for smart positioning. The engine considers the core
 *  rect (forbidden zone) + existing widget rects (avoid overlap) when
 *  placing a new widget.
 *
 *  Edge preference order: top → left → right → bottom. Scans 8px at
 *  a time along each edge looking for the first non-overlapping slot
 *  that fits the widget size. */
export interface OpenZoneInput {
  canvasWidth: number
  canvasHeight: number
  /** Rect of the anchored core. Widgets must not overlap this. */
  coreRect: Rect
  /** All widget rects currently placed. The new widget must not
   *  overlap any of these. */
  existing: Rect[]
  /** Requested width/height of the new widget. */
  widgetWidth: number
  widgetHeight: number
  /** Minimum gap between the widget and the canvas edge. Default 8px. */
  margin?: number
}


/** Scan open zones around the anchored core + existing widgets and
 *  return the first position that fits. Returns null if no zone can
 *  hold the widget.
 *
 *  Edge preference: top → left → right → bottom. Within each edge,
 *  scans from center-outward to prefer positions near the axis of
 *  related content (rough approximation of PA §5.1 "near relevant
 *  content" — Session 5+ will refine this once real pins exist). */
export function findOpenZone(input: OpenZoneInput): WidgetPosition | null {
  const {
    canvasWidth,
    canvasHeight,
    coreRect,
    existing,
    widgetWidth,
    widgetHeight,
    margin = GRID_STEP,
  } = input

  // Candidate zones — ordered by preference. Each zone is a rect
  // within which we scan 8px at a time for a fitting position.
  const zones: Rect[] = [
    // Top rail — above the core
    {
      x: margin,
      y: margin,
      width: canvasWidth - margin * 2,
      height: Math.max(0, coreRect.y - margin * 2),
    },
    // Left rail — to the left of the core
    {
      x: margin,
      y: margin,
      width: Math.max(0, coreRect.x - margin * 2),
      height: canvasHeight - margin * 2,
    },
    // Right rail — to the right of the core
    {
      x: coreRect.x + coreRect.width + margin,
      y: margin,
      width: Math.max(
        0,
        canvasWidth - (coreRect.x + coreRect.width + margin * 2),
      ),
      height: canvasHeight - margin * 2,
    },
    // Bottom rail — below the core
    {
      x: margin,
      y: coreRect.y + coreRect.height + margin,
      width: canvasWidth - margin * 2,
      height: Math.max(
        0,
        canvasHeight - (coreRect.y + coreRect.height + margin * 2),
      ),
    },
  ]

  for (const zone of zones) {
    if (zone.width < widgetWidth || zone.height < widgetHeight) continue

    // Scan 8px at a time within the zone. Start from the zone's
    // origin (edge) and move inward; scanning top-to-bottom,
    // left-to-right is a good-enough heuristic for Session 3.
    for (
      let y = snapTo8px(zone.y);
      y + widgetHeight <= zone.y + zone.height;
      y += GRID_STEP
    ) {
      for (
        let x = snapTo8px(zone.x);
        x + widgetWidth <= zone.x + zone.width;
        x += GRID_STEP
      ) {
        const candidate: Rect = {
          x,
          y,
          width: widgetWidth,
          height: widgetHeight,
        }
        // Reject if overlapping core or any existing widget.
        if (rectsOverlap(candidate, coreRect)) continue
        if (existing.some((r) => rectsOverlap(candidate, r))) continue
        return {
          x,
          y,
          width: widgetWidth,
          height: widgetHeight,
        }
      }
    }
  }

  return null
}


/** Compute the anchored core's viewport rect from CSS constants —
 *  matches the Focus.tsx Popup dimensions. Exported so Canvas can
 *  derive the forbidden zone without duplicating constants. */
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
