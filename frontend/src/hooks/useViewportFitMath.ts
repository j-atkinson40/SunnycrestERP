/**
 * useViewportFitMath — Phase W-4a Step 6 Commit 1.
 *
 * Implements the §13.3.4 viewport-fit math chain end-to-end:
 *   Step 1 — chrome budget → available_pulse_height
 *   Step 2 — viewport tier → column_count (Commit 1 returns tier;
 *            grid wiring lands in Commit 2)
 *   Step 3 — total_row_count from composition shape (caller-supplied)
 *   Step 4 — cell_height solver
 *   Step 5 — tier-three threshold check (caller-handled in Commit 3)
 *   Step 6 — --pulse-scale clamp formula
 *
 * Output is a stable object the caller (PulseSurface) writes to its
 * outer DOM via inline CSS variables. Children (PulseLayer,
 * PulsePiece, widget renderers) consume the variables — no React
 * context needed.
 *
 * All computations track the §13.3.4 constants table verbatim;
 * drift between this hook and the canon is a defect (mirror
 * discipline).
 */
import { useEffect, useMemo, useState } from "react"

import {
  APP_HEADER_HEIGHT,
  BANNER_HEIGHT,
  BASELINE_AVAILABLE_HEIGHT,
  BRASS_THREAD_OVERHEAD,
  CELL_GAP_Y,
  DOT_NAV_HEIGHT,
  EMPTY_LAYER_ADVISORY_HEIGHT,
  LAYER_SPACING,
  MIN_READABLE_CELL_HEIGHT,
  MOBILE_BREAKPOINT,
  MOBILE_TAB_BAR_HEIGHT,
  PULSE_PAGE_PADDING_Y,
  RESIZE_DEBOUNCE_MS,
  SCALE_CEILING,
  SCALE_FLOOR,
  TABLET_BREAKPOINT,
} from "@/components/spaces/viewport-fit-constants"


// ── Types ────────────────────────────────────────────────────────────


export type ViewportTier = "mobile" | "tablet" | "desktop"


/** Layer measurement input for the cell_height solver. The caller
 *  (PulseSurface) walks its composition once and feeds these numbers.
 *  Empty-with-advisory layers contribute nothing to row_count but
 *  count toward `empty_layer_count` so their fixed 32 px advisory
 *  allowance is subtracted from the budget. */
export interface LayerMeasurement {
  /** Number of populated layers (item count > 0). Each contributes its
   *  rows × cell_height + (rows−1) × gap to the layer height total. */
  populated_layer_count: number
  /** Sum of `layer_row_count` across populated layers. The §13.3.4
   *  Step 4 denominator. */
  total_row_count: number
  /** Number of empty-with-advisory layers (count > 0 only when
   *  `layer.advisory` is non-null). Each takes the fixed 32 px
   *  EMPTY_LAYER_ADVISORY_HEIGHT outside the row-count-weighted
   *  allocation. */
  empty_with_advisory_layer_count: number
  /** Whether the operational layer is populated (impacts brass-thread
   *  overhead). */
  has_operational_layer: boolean
}


export interface ViewportFitMath {
  /** Step 1 result. Available height for Pulse content within the
   *  AppLayout chrome budget. */
  available_pulse_height: number
  /** Step 2 result. Current viewport tier. */
  tier: ViewportTier
  /** Step 2 result (Commit 2). Tier-resolved column count per
   *  §13.3.1: mobile=2 / tablet=4 / desktop=6. PulseSurface writes
   *  this to `--pulse-column-count` on its root; PulseLayer's
   *  `grid-template-columns: repeat(var(--pulse-column-count), 1fr)`
   *  consumes it. Tetris packing in `computeLayerRowCount` also
   *  consumes it (a piece's `cols` count clamps to the tier's
   *  column count). */
  column_count: number
  /** Step 4 result. Cell height that makes the composition fit the
   *  viewport. May be 0 when caller has no populated layers. */
  cell_height: number
  /** Step 5 result. True when cell_height fell below the
   *  MIN_READABLE_CELL_HEIGHT (80 px) on tablet+ — caller dispatches
   *  to natural-height + scroll mode in Commit 3. */
  tier_three_threshold_breached: boolean
  /** Step 6 result. The --pulse-scale clamped value (0.875–1.25). */
  pulse_scale: number
  /** Raw viewport_height used in the chrome budget — exposed for
   *  tests + observability. */
  viewport_height: number
  /** Raw viewport_width — exposed for tests + future tier transitions. */
  viewport_width: number
}


export interface UseViewportFitMathInput {
  measurement: LayerMeasurement
  /** True when first-login banner is visible — adds BANNER_HEIGHT
   *  to chrome budget. */
  banner_visible: boolean
}


// ── Helpers ──────────────────────────────────────────────────────────


function getViewportTier(viewport_width: number): ViewportTier {
  if (viewport_width < MOBILE_BREAKPOINT) return "mobile"
  if (viewport_width < TABLET_BREAKPOINT) return "tablet"
  return "desktop"
}


/** §13.3.1 tier → column count mapping. Mobile = 2, tablet = 4,
 *  desktop = 6. Single source of truth for the dispatch — both
 *  PulseSurface (writes the CSS variable) and `computeLayerRowCount`
 *  (clamps piece cols to fit the tier) consume this. */
function getColumnCountForTier(tier: ViewportTier): number {
  if (tier === "mobile") return 2
  if (tier === "tablet") return 4
  return 6
}


function isMobileTabBarVisible(viewport_width: number): boolean {
  // MobileTabBar shows below the md: breakpoint (768 px) per Tailwind
  // default. Stricter than Pulse's mobile breakpoint (600 px), so on
  // viewports between 600-767 px the bar is still in the chrome
  // budget even though Pulse is in tablet tier.
  return viewport_width < 768
}


/** §13.3.4 Step 1 — solve available_pulse_height from chrome budget. */
function computeAvailablePulseHeight(
  viewport_height: number,
  viewport_width: number,
  banner_visible: boolean,
  empty_with_advisory_layer_count: number,
  has_operational_layer: boolean,
  populated_layer_count: number,
): number {
  const chrome =
    APP_HEADER_HEIGHT +
    (isMobileTabBarVisible(viewport_width) ? MOBILE_TAB_BAR_HEIGHT : 0) +
    DOT_NAV_HEIGHT +
    PULSE_PAGE_PADDING_Y +
    (banner_visible ? BANNER_HEIGHT : 0) +
    // Inter-layer spacing: (visible_layers − 1) × LAYER_SPACING.
    // Visible = populated + empty-with-advisory. Operate on the sum
    // so empty layers without advisory (suppressed entirely) don't
    // claim spacing.
    Math.max(0, populated_layer_count + empty_with_advisory_layer_count - 1) *
      LAYER_SPACING +
    (has_operational_layer ? BRASS_THREAD_OVERHEAD : 0) +
    empty_with_advisory_layer_count * EMPTY_LAYER_ADVISORY_HEIGHT

  return Math.max(0, viewport_height - chrome)
}


/** §13.3.4 Step 4 — solve cell_height. Returns 0 when no populated
 *  rows (caller renders empty surface). */
function solveCellHeight(
  available_pulse_height: number,
  total_row_count: number,
  populated_layer_count: number,
): number {
  if (total_row_count <= 0) return 0
  // Total vertical gaps inside grids: (rows−1) × CELL_GAP_Y per
  // populated layer. Each layer's grid has its own internal gaps;
  // empty advisories don't have grids.
  // Approximation for Commit 1: assume each populated layer contributes
  // (rows_in_layer − 1) gaps → total gaps = (total_row_count − populated_layer_count) × gap.
  // Exact per-layer breakdown isn't needed for the solve since the
  // sum is what matters.
  const total_vertical_gaps =
    Math.max(0, total_row_count - populated_layer_count) * CELL_GAP_Y
  const usable = available_pulse_height - total_vertical_gaps
  return Math.max(0, usable / total_row_count)
}


/** §13.3.4 Step 6 — clamp --pulse-scale to [SCALE_FLOOR, SCALE_CEILING]
 *  using BASELINE_AVAILABLE_HEIGHT as the 1.0 anchor. */
function computePulseScale(available_pulse_height: number): number {
  if (BASELINE_AVAILABLE_HEIGHT <= 0) return 1
  const raw = available_pulse_height / BASELINE_AVAILABLE_HEIGHT
  return Math.min(SCALE_CEILING, Math.max(SCALE_FLOOR, raw))
}


// ── Hook ─────────────────────────────────────────────────────────────


/**
 * Tiny standalone primitive that owns the debounced window-resize
 * subscription. Returns viewport dimensions + tier + tier-resolved
 * column count.
 *
 * Phase W-4a Step 6 Commit 2 extracted this from `useViewportFitMath`
 * so callers (PulseSurface) can compute layer-row-count walks
 * tier-aware BEFORE feeding the result back into `useViewportFitMath`.
 * Without this split, PulseSurface would hit a chicken-and-egg —
 * measurement needs column_count, but column_count was previously
 * only available as the math hook's output.
 *
 * SSR safety: returns desktop defaults (1440 × 900) when `window`
 * is undefined.
 */
export function useViewportDimensions(): {
  width: number
  height: number
  tier: ViewportTier
  column_count: number
} {
  const [viewport, setViewport] = useState(() => {
    if (typeof window === "undefined") {
      return { width: 1440, height: 900 }
    }
    return { width: window.innerWidth, height: window.innerHeight }
  })

  useEffect(() => {
    if (typeof window === "undefined") return
    let timer: number | undefined
    const onResize = () => {
      if (timer !== undefined) {
        window.clearTimeout(timer)
      }
      timer = window.setTimeout(() => {
        setViewport({
          width: window.innerWidth,
          height: window.innerHeight,
        })
        timer = undefined
      }, RESIZE_DEBOUNCE_MS)
    }
    window.addEventListener("resize", onResize)
    return () => {
      window.removeEventListener("resize", onResize)
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [])

  const tier = getViewportTier(viewport.width)
  const column_count = getColumnCountForTier(tier)
  return { width: viewport.width, height: viewport.height, tier, column_count }
}


/**
 * Subscribes to viewport resize via a debounced window listener.
 * Returns the full §13.3.4 math result plus the raw viewport
 * dimensions for downstream consumers.
 *
 * Callers (PulseSurface) typically write the result to inline CSS
 * variables on the surface root:
 *
 *   <div style={{
 *     "--pulse-content-height": `${math.available_pulse_height}px`,
 *     "--pulse-cell-height":    `${math.cell_height}px`,
 *     "--pulse-scale":          math.pulse_scale,
 *     "--pulse-column-count":   math.column_count,
 *   }}>
 *
 * Children (PulseLayer, PulsePiece, widget renderers) consume the
 * variables via `var(--pulse-cell-height)` etc. — no React context
 * threading needed.
 *
 * SSR safety: when `window` is undefined (test fixtures, SSR
 * pre-hydration), returns conservative defaults (desktop tier,
 * 900 baseline) so initial render doesn't blank.
 */
export function useViewportFitMath(
  input: UseViewportFitMathInput,
): ViewportFitMath {
  const { measurement, banner_visible } = input
  const viewport = useViewportDimensions()

  return useMemo<ViewportFitMath>(() => {
    const { tier, column_count, width, height } = viewport
    const available_pulse_height = computeAvailablePulseHeight(
      height,
      width,
      banner_visible,
      measurement.empty_with_advisory_layer_count,
      measurement.has_operational_layer,
      measurement.populated_layer_count,
    )
    const cell_height = solveCellHeight(
      available_pulse_height,
      measurement.total_row_count,
      measurement.populated_layer_count,
    )
    const tier_three_threshold_breached =
      (tier === "tablet" || tier === "desktop") &&
      cell_height > 0 &&
      cell_height < MIN_READABLE_CELL_HEIGHT
    const pulse_scale = computePulseScale(available_pulse_height)

    return {
      available_pulse_height,
      tier,
      column_count,
      cell_height,
      tier_three_threshold_breached,
      pulse_scale,
      viewport_height: height,
      viewport_width: width,
    }
  }, [
    viewport,
    banner_visible,
    measurement.populated_layer_count,
    measurement.total_row_count,
    measurement.empty_with_advisory_layer_count,
    measurement.has_operational_layer,
  ])
}


// ── Test-only exports ────────────────────────────────────────────────


/**
 * Exported for unit tests so each math step can be exercised
 * independently of the React hook lifecycle. Production code uses
 * `useViewportFitMath` exclusively.
 */
export const __viewport_fit_internals = {
  computeAvailablePulseHeight,
  solveCellHeight,
  computePulseScale,
  getViewportTier,
  getColumnCountForTier,
  isMobileTabBarVisible,
}
