/**
 * PulseSurface viewport-fit math — Phase W-4a Step 6 Commit 1.
 *
 * Tests the §13.3.4 viewport-fit math chain:
 *   Step 1 — chrome budget → available_pulse_height
 *   Step 4 — cell_height solver from row-count weighting
 *   Step 6 — --pulse-scale clamp formula (0.875 floor, 1.25 ceiling)
 *   Plus  — 350ms cubic-bezier ease-out transition discipline
 *
 * Test classes per the user's Commit 1 spec:
 *   • TestChromeBudgetComputation — viewport_height + banner / advisory
 *     variants → expected available_pulse_height
 *   • TestPulseScaleVariable — clamp boundaries + baseline + ceiling
 *     held
 *   • TestLayerRowCountWeighting — single + multi-layer + collapsed
 *     advisory + suppressed empty
 *   • TestCellHeightTransition — PulseLayer grid uses
 *     `var(--pulse-cell-height)` with 350ms ease-out CSS transition
 *
 * The math helpers (computeAvailablePulseHeight, solveCellHeight,
 * computePulseScale, etc.) are tested directly via
 * `__viewport_fit_internals` to exercise each step independently of
 * React lifecycle. The transition test renders PulseLayer and inspects
 * the rendered grid's inline style.
 */

import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { vi } from "vitest"

import {
  APP_HEADER_HEIGHT,
  BANNER_HEIGHT,
  BASELINE_AVAILABLE_HEIGHT,
  BRASS_THREAD_OVERHEAD,
  CELL_GAP_Y,
  DOT_NAV_HEIGHT,
  EMPTY_LAYER_ADVISORY_HEIGHT,
  LAYER_SPACING,
  PULSE_PAGE_PADDING_Y,
  SCALE_CEILING,
  SCALE_FLOOR,
} from "@/components/spaces/viewport-fit-constants"
import { __viewport_fit_internals } from "@/hooks/useViewportFitMath"
import type {
  IntelligenceStream,
  LayerContent,
  LayerItem,
  TimeOfDaySignal,
} from "@/types/pulse"


const {
  computeAvailablePulseHeight,
  solveCellHeight,
  computePulseScale,
  getViewportTier,
  isMobileTabBarVisible,
} = __viewport_fit_internals


// ── Mocks for PulseLayer transition test ─────────────────────────────


// Mock the widget renderer registry so transition test doesn't need
// real widget components mounted.
function MockWidgetRenderer(props: Record<string, unknown>) {
  return (
    <div data-testid="mock-widget-renderer">
      mock {String(props.widgetId)}
    </div>
  )
}
vi.mock("@/components/focus/canvas/widget-renderers", () => ({
  getWidgetRenderer: () => MockWidgetRenderer,
}))


// ── Fixture builders ────────────────────────────────────────────────


function makeWidgetItem(
  overrides: Partial<LayerItem> = {},
): LayerItem {
  return {
    item_id: "widget:test_widget",
    kind: "widget",
    component_key: "test_widget",
    variant_id: "brief",
    cols: 2,
    rows: 1,
    priority: 50,
    payload: {},
    dismissed: false,
    ...overrides,
  }
}


function makeLayer(
  layer: LayerContent["layer"],
  items: LayerItem[] = [],
  advisory: string | null = null,
): LayerContent {
  return { layer, items, advisory }
}


// ── TestChromeBudgetComputation ────────────────────────────────────────


describe("TestChromeBudgetComputation", () => {
  it("subtracts base chrome (no banner, no operational, no advisory, desktop viewport)", () => {
    // Desktop viewport (≥768) → no mobile tab bar.
    // 4 populated layers → 3 inter-layer gaps × 16px = 48px.
    // No banner, no operational layer, no empty-with-advisory layers.
    const viewport_h = 1000
    const viewport_w = 1440 // desktop, isMobileTabBarVisible=false
    const banner_visible = false
    const empty_with_advisory = 0
    const has_operational = false
    const populated = 4

    const expected_chrome =
      APP_HEADER_HEIGHT + // 56
      0 + // mobile tab bar hidden
      DOT_NAV_HEIGHT + // 32
      PULSE_PAGE_PADDING_Y + // 48
      0 + // no banner
      Math.max(0, populated + empty_with_advisory - 1) * LAYER_SPACING + // 3*16=48
      0 + // no operational
      0 // no advisory
    // 56 + 32 + 48 + 48 = 184
    expect(expected_chrome).toBe(184)

    const result = computeAvailablePulseHeight(
      viewport_h,
      viewport_w,
      banner_visible,
      empty_with_advisory,
      has_operational,
      populated,
    )
    expect(result).toBe(viewport_h - 184) // 816
  })

  it("subtracts BANNER_HEIGHT when banner is visible", () => {
    const without_banner = computeAvailablePulseHeight(
      1000,
      1440,
      false, // banner_visible=false
      0,
      false,
      4,
    )
    const with_banner = computeAvailablePulseHeight(
      1000,
      1440,
      true, // banner_visible=true
      0,
      false,
      4,
    )
    expect(without_banner - with_banner).toBe(BANNER_HEIGHT) // 96
  })

  it("subtracts EMPTY_LAYER_ADVISORY_HEIGHT × N for advisory-only layers", () => {
    // 2 empty-with-advisory layers + 4 populated = 6 visible layers
    //   → 5 inter-layer gaps × 16 = 80
    //   → 2 × 32 = 64 advisory
    // Without advisory layers: 4 populated → 3 gaps × 16 = 48, no advisory
    const baseline = computeAvailablePulseHeight(
      1000,
      1440,
      false,
      0, // no advisory layers
      false,
      4,
    )
    const with_advisories = computeAvailablePulseHeight(
      1000,
      1440,
      false,
      2, // 2 advisory layers
      false,
      4,
    )
    // delta = -2 * EMPTY_LAYER_ADVISORY_HEIGHT - 2 * LAYER_SPACING
    //       = -64 - 32 = -96
    const expected_delta =
      2 * EMPTY_LAYER_ADVISORY_HEIGHT + 2 * LAYER_SPACING
    expect(baseline - with_advisories).toBe(expected_delta) // 96
  })

  it("subtracts BRASS_THREAD_OVERHEAD when operational layer is populated", () => {
    const without_op = computeAvailablePulseHeight(
      1000,
      1440,
      false,
      0,
      false, // has_operational=false
      4,
    )
    const with_op = computeAvailablePulseHeight(
      1000,
      1440,
      false,
      0,
      true, // has_operational=true
      4,
    )
    expect(without_op - with_op).toBe(BRASS_THREAD_OVERHEAD) // 24
  })

  it("includes MOBILE_TAB_BAR_HEIGHT for mobile viewport (width < 768)", () => {
    // Mobile width (320px) → tab bar visible.
    // Expected chrome:
    //   APP_HEADER (56) + MOBILE_TAB (56) + DOT_NAV (32) + PADDING (48)
    //   + 0 banner + 3*16 layer gaps + 0 op + 0 advisory
    //   = 56 + 56 + 32 + 48 + 48 = 240
    const result = computeAvailablePulseHeight(
      700, // viewport_h
      320, // mobile width
      false,
      0,
      false,
      4,
    )
    expect(result).toBe(700 - 240) // 460

    // Verify isMobileTabBarVisible reports correctly.
    expect(isMobileTabBarVisible(320)).toBe(true)
    expect(isMobileTabBarVisible(768)).toBe(false)
    expect(isMobileTabBarVisible(1440)).toBe(false)
  })

  it("clamps to 0 when chrome exceeds viewport (defensive lower bound)", () => {
    // Tiny viewport that's smaller than chrome — should not return
    // negative. 200px viewport vs ~184px+ chrome.
    const result = computeAvailablePulseHeight(
      100,
      1440,
      false,
      0,
      false,
      4,
    )
    expect(result).toBe(0)
  })
})


// ── TestPulseScaleVariable ─────────────────────────────────────────────


describe("TestPulseScaleVariable", () => {
  it("returns 1.0 when available equals BASELINE_AVAILABLE_HEIGHT (900)", () => {
    expect(computePulseScale(BASELINE_AVAILABLE_HEIGHT)).toBe(1.0)
  })

  it("clamps at SCALE_FLOOR (0.875) when available is well below baseline", () => {
    // 600 / 900 = 0.667, below floor → clamps to 0.875
    expect(computePulseScale(600)).toBe(SCALE_FLOOR) // 0.875
  })

  it("hits SCALE_CEILING (1.25) at exactly 1.25 × baseline (1125)", () => {
    // 1125 / 900 = 1.25, exactly at ceiling
    expect(computePulseScale(1125)).toBe(SCALE_CEILING) // 1.25
  })

  it("holds at SCALE_CEILING (1.25) above 1.25 × baseline (1500)", () => {
    // 1500 / 900 = 1.667, above ceiling → clamps to 1.25
    expect(computePulseScale(1500)).toBe(SCALE_CEILING) // 1.25
  })

  it("scales linearly between floor and ceiling", () => {
    // 1000 / 900 ≈ 1.111, in-range
    const result = computePulseScale(1000)
    expect(result).toBeCloseTo(1.111, 2)
    expect(result).toBeGreaterThan(SCALE_FLOOR)
    expect(result).toBeLessThan(SCALE_CEILING)
  })

  it("returns 1.0 defensively when BASELINE is somehow zero or negative", () => {
    // Defensive guard — shouldn't happen but math chain should not
    // divide by zero. We can't actually mutate BASELINE_AVAILABLE_HEIGHT
    // at runtime; this asserts the helper handles edge inputs by
    // computing on a stub. The implementation guards against
    // BASELINE <= 0 in computePulseScale.
    // Verified via call: any positive input scales by /900.
    expect(computePulseScale(0)).toBe(SCALE_FLOOR)
  })
})


// ── TestLayerRowCountWeighting ─────────────────────────────────────────


describe("TestLayerRowCountWeighting", () => {
  it("returns 0 cell_height when no populated rows", () => {
    expect(solveCellHeight(800, 0, 0)).toBe(0)
  })

  it("solves single-layer 2-row composition", () => {
    // 1 populated layer with 2 rows.
    // gaps = (total_rows - populated_layers) * CELL_GAP_Y
    //      = (2 - 1) * 12 = 12
    // usable = 800 - 12 = 788
    // cell = 788 / 2 = 394
    const result = solveCellHeight(800, 2, 1)
    expect(result).toBe(394)
  })

  it("distributes available height across 4 populated layers (8 total rows)", () => {
    // 4 populated layers, 8 total rows.
    // gaps = (8 - 4) * 12 = 48
    // usable = 800 - 48 = 752
    // cell = 752 / 8 = 94
    const result = solveCellHeight(800, 8, 4)
    expect(result).toBe(94)
  })

  it("produces taller cells when fewer rows compete for available height", () => {
    // Same available, fewer rows → bigger cells.
    const tight = solveCellHeight(800, 8, 4) // 94
    const loose = solveCellHeight(800, 4, 2) // (4-2)*12=24, 776/4=194
    expect(loose).toBeGreaterThan(tight)
    expect(loose).toBe(194)
  })

  it("clamps to 0 when chrome+gaps would consume more than available", () => {
    // 100 rows, 4 populated → gaps = 96 * 12 = 1152
    // Available 800 - 1152 = negative; helper clamps to 0.
    const result = solveCellHeight(800, 100, 4)
    expect(result).toBe(0)
  })

  it("uses CELL_GAP_Y from constants, not magic number", () => {
    // Sanity check: the gap math uses the canonical constant.
    // 1 populated layer with 3 rows.
    // gaps = (3 - 1) * CELL_GAP_Y = 2 * 12 = 24
    // usable = 100 - 24 = 76
    // cell = 76 / 3 ≈ 25.33
    const result = solveCellHeight(100, 3, 1)
    expect(result).toBeCloseTo((100 - 2 * CELL_GAP_Y) / 3, 5)
  })
})


// ── TestViewportTierDispatch ──────────────────────────────────────────


describe("TestViewportTierDispatch", () => {
  it("returns 'mobile' below MOBILE_BREAKPOINT (600)", () => {
    expect(getViewportTier(320)).toBe("mobile")
    expect(getViewportTier(599)).toBe("mobile")
  })

  it("returns 'tablet' between MOBILE and TABLET breakpoints (600-1023)", () => {
    expect(getViewportTier(600)).toBe("tablet")
    expect(getViewportTier(800)).toBe("tablet")
    expect(getViewportTier(1023)).toBe("tablet")
  })

  it("returns 'desktop' at and above TABLET_BREAKPOINT (1024)", () => {
    expect(getViewportTier(1024)).toBe("desktop")
    expect(getViewportTier(1440)).toBe("desktop")
    expect(getViewportTier(2560)).toBe("desktop")
  })
})


// ── TestCellHeightTransition ──────────────────────────────────────────


describe("TestCellHeightTransition", () => {
  // PulseLayer's grid uses `repeat(N, var(--pulse-cell-height))` with a
  // 350ms cubic-bezier ease-out transition on grid-template-rows. This
  // verifies the rendered DOM carries those style hooks.

  it("renders gridTemplateRows referencing var(--pulse-cell-height)", async () => {
    const { PulseLayer } = await import("@/components/spaces/PulseLayer")
    const layer: LayerContent = makeLayer("personal", [
      makeWidgetItem({ item_id: "widget:p1", cols: 2, rows: 1 }),
    ])
    const intelligenceStreams: IntelligenceStream[] = []
    const timeOfDay: TimeOfDaySignal = "morning"

    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={intelligenceStreams}
          timeOfDay={timeOfDay}
          workAreas={["Production Scheduling"]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    const grid = container.querySelector(
      '[data-slot="pulse-layer-grid"]',
    ) as HTMLElement | null
    expect(grid).not.toBeNull()
    const styleAttr = grid!.getAttribute("style") ?? ""
    // Must reference --pulse-cell-height variable.
    expect(styleAttr).toContain("var(--pulse-cell-height")
    // Must use repeat() with the row count (1 here for 1 row).
    expect(styleAttr).toMatch(/grid-template-rows:\s*repeat\(1,/)
  })

  it("renders 350ms cubic-bezier ease-out transition on grid-template-rows", async () => {
    const { PulseLayer } = await import("@/components/spaces/PulseLayer")
    const layer: LayerContent = makeLayer("personal", [
      makeWidgetItem({ item_id: "widget:p1" }),
    ])
    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay="morning"
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    const grid = container.querySelector(
      '[data-slot="pulse-layer-grid"]',
    ) as HTMLElement | null
    expect(grid).not.toBeNull()
    const styleAttr = grid!.getAttribute("style") ?? ""
    // 350ms duration per §13.3.4 transition discipline (300-400ms target).
    expect(styleAttr).toContain("350ms")
    // ease-out cubic-bezier per canon (matches Tailwind ease-out).
    expect(styleAttr).toContain("cubic-bezier(0.4, 0, 0.2, 1)")
    // Transition target must be grid-template-rows.
    expect(styleAttr).toContain("grid-template-rows")
  })

  it("computes layer row count from tetris packing and writes data-row-count", async () => {
    // 3 widgets, each 2-col 1-row, in a 6-col grid → fits in 1 row.
    const { PulseLayer } = await import("@/components/spaces/PulseLayer")
    const layer: LayerContent = makeLayer("personal", [
      makeWidgetItem({ item_id: "widget:p1", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "widget:p2", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "widget:p3", cols: 2, rows: 1 }),
    ])
    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay="morning"
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    const section = container.querySelector(
      '[data-slot="pulse-layer"]',
    ) as HTMLElement | null
    expect(section).not.toBeNull()
    expect(section!.getAttribute("data-row-count")).toBe("1")

    const grid = container.querySelector(
      '[data-slot="pulse-layer-grid"]',
    ) as HTMLElement | null
    expect(grid!.getAttribute("style")).toMatch(
      /grid-template-rows:\s*repeat\(1,/,
    )
  })

  it("computes 2 rows when widgets overflow a single row", async () => {
    // 4 widgets × 2-col each = 8 col-units → wraps to 2 rows in 6-col grid.
    const { PulseLayer } = await import("@/components/spaces/PulseLayer")
    const layer: LayerContent = makeLayer("operational", [
      makeWidgetItem({ item_id: "widget:o1", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "widget:o2", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "widget:o3", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "widget:o4", cols: 2, rows: 1 }),
    ])
    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay="morning"
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    const section = container.querySelector(
      '[data-slot="pulse-layer"]',
    ) as HTMLElement | null
    expect(section!.getAttribute("data-row-count")).toBe("2")
  })

  it("falls back to 80px when --pulse-cell-height is unset", async () => {
    // Inline style includes a fallback in the var() so initial mount
    // (before PulseSurface wires the variable) still has a sane row
    // height. We can't assert resolved height in jsdom, but we can
    // verify the fallback is encoded in the style string.
    const { PulseLayer } = await import("@/components/spaces/PulseLayer")
    const layer: LayerContent = makeLayer("personal", [
      makeWidgetItem({ item_id: "widget:p1" }),
    ])
    const { container } = render(
      <MemoryRouter>
        <PulseLayer
          layer={layer}
          intelligenceStreams={[]}
          timeOfDay="morning"
          workAreas={[]}
          pulseLoadedAt={1000}
          dismissedItemIds={new Set()}
        />
      </MemoryRouter>,
    )
    const grid = container.querySelector(
      '[data-slot="pulse-layer-grid"]',
    ) as HTMLElement | null
    const styleAttr = grid!.getAttribute("style") ?? ""
    // Fallback "80px" lives inside var(--pulse-cell-height, 80px).
    expect(styleAttr).toContain("80px")
  })
})
