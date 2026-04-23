/**
 * Canvas geometry — Phase A Session 3.5, extended Session 3.8.
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
 *
 * Tier detection (Session 3.8 continuous cascade):
 *   Layout is continuous. The three render paths (canvas, stack,
 *   icon) remain but the SWITCH between them happens at geometric
 *   constraints, not fixed viewport pixel thresholds. Core size is
 *   a continuous function of viewport within each tier's min/max
 *   bounds. Transitions between tiers happen exactly when the next
 *   tier's geometric requirement stops being satisfied:
 *
 *     canvas  — widgets fit in reserved margin around core
 *     stack   — stack rail fits alongside a minimum-sized core
 *     icon    — neither fits; floating button + bottom-sheet
 *
 *   Session 3.7.1 introduced content-aware canvas↔stack detection
 *   via `widgetsFitInCanvas`. Session 3.8 extends the same principle
 *   to stack↔icon via `stackFitsAlongsideCore` — replacing the
 *   Session 3.7 `vw < 700` hard pixel threshold. See the matching
 *   "Almost But Not Quite" entry in PLATFORM_QUALITY_BAR.md.
 */

import type {
  WidgetAnchor,
  WidgetId,
  WidgetPosition,
  WidgetState,
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


// ── Tier system (Session 3.7) ───────────────────────────────────

/** Tier identifier for the responsive cascade. Widget rendering
 *  mode + core sizing derive from the current tier.
 *
 *  - `canvas`: full free-form placement (wide viewports)
 *  - `stack`: right-rail Smart Stack (medium-narrow)
 *  - `icon`: floating button with bottom-sheet overlay (phone-narrow) */
export type FocusTier = "canvas" | "stack" | "icon"


/** Floor constant retained for reference + backward compat. Tier
 *  detection is now fully geometric (Session 3.8) — both the
 *  canvas↔stack boundary (content-aware via `widgetsFitInCanvas`,
 *  Session 3.7.1) and the stack↔icon boundary (via
 *  `stackFitsAlongsideCore`, Session 3.8) derive from the actual
 *  geometric requirements of the rendered layout. The derived
 *  stack-fits floor is ~928px (see `stackFitsAlongsideCore`). This
 *  constant previously served as a hard `vw < 700 → icon` pixel
 *  threshold in `determineTier`. */
export const TIER_ICON_MAX_WIDTH = 700

/** Right-rail stack width in stack mode. Reserved on the right side
 *  of the viewport; core takes the rest (minus margin). */
export const STACK_RAIL_WIDTH = 280

/** Core min/max dimensions. Core floors at 600×400 (below this
 *  Kanban + other core modes become unusable) and caps at 1400×900.
 *  These bounds apply in canvas AND stack tiers (Session 3.8 — stack
 *  formula now also respects CORE_MAX so core doesn't grow unbounded
 *  on ultra-wide viewports). Icon tier remains uncapped by design —
 *  narrow viewports define the mode, and clamping to MIN would force
 *  horizontal overflow. */
export const CORE_MIN_WIDTH = 600
export const CORE_MIN_HEIGHT = 400
export const CORE_MAX_WIDTH = 1400
export const CORE_MAX_HEIGHT = 900

/** Reserved canvas margin around the core in canvas mode — each
 *  side reserves this much for widgets. */
export const CANVAS_RESERVED_MARGIN = 100

/** Stack tier layout constants. Extracted so `stackFitsAlongsideCore`
 *  and `computeCoreRect` (stack branch) share the same numbers. */
export const STACK_EDGE_MARGIN = 16
export const STACK_CORE_GAP = 16

/** Breathing-room buffer between widget edge and reserved-space edge
 *  used by `widgetsFitInCanvas`. A widget exactly the size of reserved
 *  space would touch both the viewport edge and the core edge, which
 *  reads as cramped; `+ buffer` keeps a visible gap on each side. */
export const WIDGET_FIT_BUFFER = 16


/** Does each widget's anchor have enough reserved canvas space to
 *  render the widget at its canonical size without clipping?
 *
 *  Content-aware tier-detection primitive (Session 3.7 fix). Per
 *  anchor, the widget must fit in the band it anchors to:
 *
 *  - `*-left`   → width must fit in reservedLeft  (vw[0..coreRect.x])
 *  - `*-right`  → width must fit in reservedRight (vw[coreRect.x+w..vw])
 *  - `top-*`    → height must fit in reservedTop  (vh[0..coreRect.y])
 *  - `bottom-*` → height must fit in reservedBottom (vh[core.y+h..vh])
 *
 *  Corner anchors (top-left, top-right, bottom-left, bottom-right)
 *  check BOTH dimensions — the anchor reserves the corner's overlap
 *  region, so the widget must fit in both bands. Rail anchors
 *  (`left-rail`, `right-rail`) are caught by the `includes("left")` /
 *  `includes("right")` branch; `top-center` + `bottom-center` only
 *  check vertical fit since they span horizontally across the core.
 *
 *  Returns true if ALL widgets fit. Returns true vacuously for empty
 *  widget lists (empty canvas renders fine regardless of viewport).
 *
 *  Accepts either a `Record<WidgetId, WidgetState>` (how focus-context
 *  stores widgets) or a `WidgetState[]` (test-fixture ergonomic). */
export function widgetsFitInCanvas(
  widgets: Record<WidgetId, WidgetState> | WidgetState[],
  viewportWidth: number,
  viewportHeight: number,
  buffer: number = WIDGET_FIT_BUFFER,
): boolean {
  const list = Array.isArray(widgets) ? widgets : Object.values(widgets)
  if (list.length === 0) return true

  const coreRect = computeCoreRect("canvas", viewportWidth, viewportHeight)
  const reservedLeft = coreRect.x
  const reservedRight = viewportWidth - (coreRect.x + coreRect.width)
  const reservedTop = coreRect.y
  const reservedBottom = viewportHeight - (coreRect.y + coreRect.height)

  for (const widget of list) {
    const { anchor, width, height } = widget.position

    if (anchor.includes("left") && width + buffer > reservedLeft) return false
    if (anchor.includes("right") && width + buffer > reservedRight) return false
    if (anchor.startsWith("top") && height + buffer > reservedTop) return false
    if (anchor.startsWith("bottom") && height + buffer > reservedBottom) {
      return false
    }
  }

  return true
}


/** Can a minimum-sized core + stack rail + their margins all fit
 *  alongside each other at the given viewport?
 *
 *  Session 3.8 stack↔icon geometric gate (replaces Session 3.7's
 *  `vw < TIER_ICON_MAX_WIDTH`). A stack layout needs:
 *
 *      core_min_width + left_margin + gap + rail_width + right_margin
 *
 *  Below that width, we can't render a usable stack without widget+
 *  core overlap. It must drop to icon.
 *
 *  Height: needs at least CORE_MIN_HEIGHT + 2×STACK_EDGE_MARGIN of
 *  vertical room to render the rail + core side-by-side. Below
 *  that, icon tier's viewport-filling overlay handles the compression. */
export function stackFitsAlongsideCore(
  viewportWidth: number,
  viewportHeight: number,
): boolean {
  const minStackWidth =
    CORE_MIN_WIDTH +
    STACK_EDGE_MARGIN +
    STACK_CORE_GAP +
    STACK_RAIL_WIDTH +
    STACK_EDGE_MARGIN
  const minStackHeight = CORE_MIN_HEIGHT + STACK_EDGE_MARGIN * 2
  return viewportWidth >= minStackWidth && viewportHeight >= minStackHeight
}


/** Pick the tier for the current viewport + widget set.
 *
 *  Session 3.8 — fully geometric cascade:
 *    1. If stack can't fit alongside a MIN-sized core → icon (floor)
 *    2. Else, if widgets fit canvas reserved space → canvas
 *    3. Else → stack
 *
 *  Canvas is structurally stricter than stack (needs a wider viewport
 *  to leave widgets room). So we check the stack floor first: if
 *  even stack can't fit, canvas won't either, and we fall to icon.
 *  Above that floor, canvas is preferred when widgets fit; otherwise
 *  stack takes over. No fixed pixel thresholds anywhere — the three
 *  render paths (canvas, stack, icon) remain unchanged but the
 *  SWITCH between them tracks the actual geometric constraints of
 *  what's being rendered.
 *
 *  The effective stack↔icon floor lands at ~928px wide / 432px tall
 *  (see `stackFitsAlongsideCore`) instead of Session 3.7's hard
 *  `vw < 700` pixel threshold.
 *
 *  Session 3.7 history: `vw < 700 → icon` was a fixed-viewport gate.
 *  Session 3.7.1 made canvas↔stack content-aware via `widgetsFitInCanvas`.
 *  Session 3.8 extends the same principle to stack↔icon via
 *  `stackFitsAlongsideCore` — user-observed "discrete mode switch"
 *  feel at intermediate viewports is resolved. */
export function determineTier(
  viewportWidth: number,
  viewportHeight: number,
  widgets: Record<WidgetId, WidgetState> | WidgetState[] = [],
): FocusTier {
  if (!stackFitsAlongsideCore(viewportWidth, viewportHeight)) return "icon"
  if (widgetsFitInCanvas(widgets, viewportWidth, viewportHeight)) return "canvas"
  return "stack"
}


/** Compute the anchored core's viewport rect per tier.
 *
 *  All three formulas are continuous within their tier — core size
 *  scales smoothly with viewport between the MIN/MAX bounds. Session
 *  3.8 extended the stack formula to also respect CORE_MAX so core
 *  doesn't grow unbounded on ultra-wide viewports and the canvas↔
 *  stack boundary converges at those widths.
 *
 *  - canvas: clamp(MIN, viewport - 2×CANVAS_RESERVED_MARGIN, MAX) —
 *    reserves 100px on each side for canvas widgets
 *  - stack: clamp(MIN, viewport - (rail + margins), MAX) — core takes
 *    remaining viewport width to the left of the rail; capped at MAX
 *  - icon: fills viewport minus small safe padding — widgets live in
 *    bottom-sheet overlay, not around core. No MIN clamp here: icon
 *    mode is for narrow viewports by definition and clamping to MIN
 *    would force horizontal overflow.
 *
 *  MUST stay in sync with Focus.tsx's Popup inline styling and
 *  `widgetsFitInCanvas`'s implicit use of the canvas branch via
 *  `computeCoreRect("canvas", vw, vh)` — findOpenZone's core-
 *  forbidden-zone math drifts from the rendered core otherwise. */
export function computeCoreRect(
  tier: FocusTier,
  viewportWidth: number,
  viewportHeight: number,
): Rect {
  if (tier === "canvas") {
    const width = Math.min(
      CORE_MAX_WIDTH,
      Math.max(CORE_MIN_WIDTH, viewportWidth - CANVAS_RESERVED_MARGIN * 2),
    )
    const height = Math.min(
      CORE_MAX_HEIGHT,
      Math.max(CORE_MIN_HEIGHT, viewportHeight - CANVAS_RESERVED_MARGIN * 2),
    )
    return {
      x: (viewportWidth - width) / 2,
      y: (viewportHeight - height) / 2,
      width,
      height,
    }
  }
  if (tier === "stack") {
    // Core occupies viewport minus right-rail minus margins.
    const rightReserved =
      STACK_RAIL_WIDTH + STACK_CORE_GAP + STACK_EDGE_MARGIN
    const width = Math.min(
      CORE_MAX_WIDTH,
      Math.max(
        CORE_MIN_WIDTH,
        viewportWidth - rightReserved - STACK_EDGE_MARGIN,
      ),
    )
    const height = Math.min(
      CORE_MAX_HEIGHT,
      Math.max(CORE_MIN_HEIGHT, viewportHeight - STACK_EDGE_MARGIN * 2),
    )
    return {
      x: STACK_EDGE_MARGIN,
      y: (viewportHeight - height) / 2,
      width,
      height,
    }
  }
  // icon: fills viewport (minus small safe padding). No min/max
  // clamp — narrow viewports define icon mode.
  return {
    x: 8,
    y: 8,
    width: Math.max(0, viewportWidth - 16),
    height: Math.max(0, viewportHeight - 16),
  }
}


/** Compute the right-rail stack region in stack mode. Returns the
 *  rect where StackRail renders. */
export function computeStackRailRect(
  viewportWidth: number,
  viewportHeight: number,
): Rect {
  const core = computeCoreRect("stack", viewportWidth, viewportHeight)
  return {
    x: core.x + core.width + STACK_CORE_GAP,
    y: core.y,
    width: STACK_RAIL_WIDTH,
    height: core.height,
  }
}
