/**
 * canvas-pan-zoom — Phase B integration-phase sub-arc (pan + zoom).
 *
 * Pure-function math for the workflow graph canvas's view transform. The
 * GraphCanvas owns an ephemeral `{panX, panY, zoom}` view state (NOT
 * persisted in canvas_state — view state, never authored state); this
 * module owns the coordinate math so `GraphCanvas.tsx` stays a thin
 * gesture shell.
 *
 * Mirrors the `canvas-layout.ts` + `simulate-trace.ts` precedent: pure
 * functions keep the zoom-to-cursor + boundary-clamp math unit-testable
 * in vitest WITHOUT DOM (Q-40 — JSDOM doesn't compute CSS transforms into
 * layout, but these are coordinate computations, not layout reads). The
 * GraphCanvas integration test asserts the resulting inline
 * `style.transform` string; the exact numeric correctness lives here.
 *
 * View-transform model (Option A-direct per the grounding map): the
 * content surface div gets `transform: translate(panX, panY) scale(zoom)`
 * with `transform-origin: 0 0`. A world point `(wx, wy)` maps to the
 * screen point `(panX + wx*zoom, panY + wy*zoom)`.
 */

import { CANVAS_BBOX_PADDING } from "./canvas-layout"

// ─── Zoom bounds + wheel sensitivity ────────────────────────────────

/** Operator-locked zoom range. */
export const ZOOM_MIN = 0.25
export const ZOOM_MAX = 2.0

/**
 * Wheel-delta → zoom factor sensitivity. Multiplicative (exp) so zoom
 * feels uniform across the range + composes cleanly with zoom-to-cursor.
 * A wheel-up notch (deltaY ≈ −100) → factor ≈ exp(0.15) ≈ 1.16 (zoom in).
 */
export const ZOOM_WHEEL_SENSITIVITY = 0.0015

/** Default view (reset target). */
export const DEFAULT_VIEW: ViewTransform = { panX: 0, panY: 0, zoom: 1 }

/** Pan drag-threshold in px — mirrors the DndContext PointerSensor (3px)
 *  so node-drag and background-pan activation stay consistent. */
export const PAN_DRAG_THRESHOLD = 3


// ─── Types ──────────────────────────────────────────────────────────

export interface ViewTransform {
  panX: number
  panY: number
  zoom: number
}

export interface ContentBounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

export interface ViewportSize {
  width: number
  height: number
}


// ─── clampZoom ──────────────────────────────────────────────────────

/** Clamp a zoom value to the operator-locked [ZOOM_MIN, ZOOM_MAX] range. */
export function clampZoom(zoom: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom))
}


// ─── computeZoomToCursor ────────────────────────────────────────────

/**
 * Apply a wheel-delta zoom anchored at the cursor: the world point under
 * the cursor before the zoom maps to the SAME screen point after.
 *
 * `cursorX/cursorY` are the cursor coordinates relative to the viewport
 * origin (caller subtracts the viewport's bounding-rect left/top). Returns
 * the next view; when the zoom is already clamped at a bound, pan is left
 * unchanged (no drift while scrolling against the limit).
 *
 * Formula (transform-origin 0,0): worldUnderCursor = (cursorScreen − pan)
 * / zoom; we want cursorScreen = newPan + worldUnderCursor·newZoom, so
 * newPan = cursorScreen − (cursorScreen − oldPan)·(newZoom/oldZoom).
 */
export function computeZoomToCursor(
  view: ViewTransform,
  cursorX: number,
  cursorY: number,
  deltaY: number,
): ViewTransform {
  const factor = Math.exp(-deltaY * ZOOM_WHEEL_SENSITIVITY)
  const nextZoom = clampZoom(view.zoom * factor)
  // At a bound (or no-op delta) → zoom unchanged, pan untouched.
  if (nextZoom === view.zoom) {
    return { ...view }
  }
  const ratio = nextZoom / view.zoom
  return {
    panX: cursorX - (cursorX - view.panX) * ratio,
    panY: cursorY - (cursorY - view.panY) * ratio,
    zoom: nextZoom,
  }
}


// ─── clampPan ───────────────────────────────────────────────────────

/**
 * Clamp pan so the content (the node bounding box, scaled by zoom) can
 * never leave the viewport entirely — at least `margin` px of content
 * stays visible on every edge. Zoom-aware: the content's screen extent is
 * `bbox · zoom`, so the clamp range shifts as zoom changes.
 *
 * Content screen-x spans [panX + minX·zoom, panX + maxX·zoom]. Constraints:
 *   - content right edge ≥ margin            → panX ≥ margin − maxX·zoom
 *   - content left edge ≤ viewport − margin   → panX ≤ W − margin − minX·zoom
 * When the two bounds cross (content smaller than the margin budget), pin
 * to the lower bound (keeps the content's far edge at the margin).
 */
export function clampPan(
  view: ViewTransform,
  content: ContentBounds,
  viewport: ViewportSize,
  margin: number = CANVAS_BBOX_PADDING,
): { panX: number; panY: number } {
  const z = view.zoom
  const loX = margin - content.maxX * z
  const hiX = viewport.width - margin - content.minX * z
  const loY = margin - content.maxY * z
  const hiY = viewport.height - margin - content.minY * z
  return {
    panX: loX > hiX ? loX : Math.max(loX, Math.min(view.panX, hiX)),
    panY: loY > hiY ? loY : Math.max(loY, Math.min(view.panY, hiY)),
  }
}


// ─── formatZoomPercent ──────────────────────────────────────────────

/** Render a zoom value as an integer percent string (e.g. 1 → "100%"). */
export function formatZoomPercent(zoom: number): string {
  return `${Math.round(zoom * 100)}%`
}
