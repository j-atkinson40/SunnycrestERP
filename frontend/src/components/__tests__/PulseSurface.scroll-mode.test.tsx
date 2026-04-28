/**
 * PulseSurface scroll mode + tier-three threshold + sub-pixel
 * boundary buffer — Phase W-4a Step 6 Commit 3.
 *
 * Tests the §13.3.4 Step 5 scroll-mode dispatch chain:
 *   • Mobile fallback (viewport_width < 600 px → always scroll)
 *   • Tier-three threshold (cell_height < 80 px on tablet+ → scroll)
 *   • Resize transitions (viewport-fit ↔ scroll mode dynamic)
 *   • Sub-pixel boundary buffer (99.5 / 119.5 thresholds prevent
 *     incorrect tier firing at canon integer boundaries due to
 *     Chromium sub-pixel rounding)
 *
 * Test classes per the Commit 3 spec:
 *   • TestScrollModeDispatchMobile — mobile width fires scroll mode
 *   • TestScrollModeDispatchTierThree — tablet+ at <80 cell fires
 *   • TestScrollModeRendering — root data attr + style + CSS override
 *   • TestScrollModeTransition — dynamic recompute on resize
 *   • TestSubPixelBoundaryBuffer — 99.5 / 119.5 thresholds in CSS
 */

/// <reference types="node" />
import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { render } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { __viewport_fit_internals } from "@/hooks/useViewportFitMath"
import {
  MIN_READABLE_CELL_HEIGHT,
  MOBILE_BREAKPOINT,
} from "@/components/spaces/viewport-fit-constants"
import type {
  IntelligenceStream,
  LayerContent,
  LayerItem,
  TimeOfDaySignal,
} from "@/types/pulse"


// Vitest config has `css: false`, so `?raw` imports of CSS files
// return empty strings. Read the CSS file directly via Node's
// fs.readFileSync — keeps the boundary-buffer tests honest against
// the actual file ship contents rather than a transformed view.
const PULSE_DENSITY_CSS_PATH = resolve(
  __dirname,
  "../../styles/pulse-density.css",
)
function loadPulseDensityCss(): string {
  return readFileSync(PULSE_DENSITY_CSS_PATH, "utf8")
}


const {
  computeAvailablePulseHeight,
  solveCellHeight,
  getViewportTier,
  getColumnCountForTier,
} = __viewport_fit_internals


// ── Helper ────────────────────────────────────────────────────────


/** Compose the same scroll_mode_active check the hook performs.
 *  Pure-function port for parametric testing across viewport
 *  shapes without going through the full React lifecycle. */
function deriveScrollModeActive(
  viewport_width: number,
  viewport_height: number,
  populated_layer_count: number,
  total_row_count: number,
  empty_with_advisory_layer_count: number = 0,
  has_operational_layer: boolean = false,
  banner_visible: boolean = false,
): {
  scroll_mode_active: boolean
  tier: ReturnType<typeof getViewportTier>
  cell_height: number
  tier_three_threshold_breached: boolean
} {
  const tier = getViewportTier(viewport_width)
  const available = computeAvailablePulseHeight(
    viewport_height,
    viewport_width,
    banner_visible,
    empty_with_advisory_layer_count,
    has_operational_layer,
    populated_layer_count,
  )
  const cell_height = solveCellHeight(
    available,
    total_row_count,
    populated_layer_count,
  )
  const tier_three_threshold_breached =
    (tier === "tablet" || tier === "desktop") &&
    cell_height > 0 &&
    cell_height < MIN_READABLE_CELL_HEIGHT
  return {
    scroll_mode_active: tier === "mobile" || tier_three_threshold_breached,
    tier,
    cell_height,
    tier_three_threshold_breached,
  }
}


function makeWidgetItem(
  overrides: Partial<LayerItem> = {},
): LayerItem {
  return {
    item_id: "widget:test",
    kind: "widget",
    component_key: "test",
    variant_id: "brief",
    cols: 2,
    rows: 1,
    priority: 50,
    payload: {},
    dismissed: false,
    ...overrides,
  }
}


// Stub widget data fetch to keep PulseLayer / PulseSurface mountable.
vi.mock("@/components/widgets/useWidgetData", () => ({
  useWidgetData: () => ({
    data: null,
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  }),
}))


// ── TestScrollModeDispatchMobile ──────────────────────────────────────


describe("TestScrollModeDispatchMobile", () => {
  it("dispatches scroll mode at mobile width 320 (well below MOBILE_BREAKPOINT)", () => {
    const result = deriveScrollModeActive(320, 568, 2, 4)
    expect(result.tier).toBe("mobile")
    expect(result.scroll_mode_active).toBe(true)
  })

  it("dispatches scroll mode at viewport_width = MOBILE_BREAKPOINT - 1 (599)", () => {
    const result = deriveScrollModeActive(599, 800, 2, 4)
    expect(result.tier).toBe("mobile")
    expect(result.scroll_mode_active).toBe(true)
  })

  it("does NOT dispatch at viewport_width = MOBILE_BREAKPOINT (600 = tablet)", () => {
    // Tablet with comfortable height + light composition → cell_height
    // well above 80, no tier-three breach.
    const result = deriveScrollModeActive(MOBILE_BREAKPOINT, 1024, 1, 1)
    expect(result.tier).toBe("tablet")
    expect(result.tier_three_threshold_breached).toBe(false)
    expect(result.scroll_mode_active).toBe(false)
  })

  it("mobile dispatch is regardless of cell math (light composition)", () => {
    // Even with tiny composition that would have huge cell_height on
    // desktop, mobile dispatches scroll mode by viewport-width alone.
    const result = deriveScrollModeActive(375, 667, 1, 1)
    expect(result.tier).toBe("mobile")
    expect(result.cell_height).toBeGreaterThan(0)
    // Mobile fallback fires regardless of cell math.
    expect(result.scroll_mode_active).toBe(true)
  })
})


// ── TestScrollModeDispatchTierThree ──────────────────────────────────


describe("TestScrollModeDispatchTierThree", () => {
  it("dispatches at tablet 800x500 with heavy composition (cell_height < 80)", () => {
    // Heavy: 6 populated layers × 2 rows = 12 total rows, only 500
    // viewport height. Chrome ~136 (no banner, no op, no advisory)
    // + 5 layer gaps × 16 = 80, total chrome 216. Available 284px.
    // 12 rows × cell + 8 gaps × 12 = 284 → cell ~14.8px.
    const result = deriveScrollModeActive(800, 500, 6, 12)
    expect(result.tier).toBe("tablet")
    expect(result.cell_height).toBeLessThan(MIN_READABLE_CELL_HEIGHT)
    expect(result.tier_three_threshold_breached).toBe(true)
    expect(result.scroll_mode_active).toBe(true)
  })

  it("does NOT dispatch at tablet 800x800 with comfortable composition", () => {
    const result = deriveScrollModeActive(800, 800, 2, 3)
    expect(result.tier).toBe("tablet")
    expect(result.cell_height).toBeGreaterThanOrEqual(
      MIN_READABLE_CELL_HEIGHT,
    )
    expect(result.tier_three_threshold_breached).toBe(false)
    expect(result.scroll_mode_active).toBe(false)
  })

  it("dispatches at desktop 1440x400 (very compressed height)", () => {
    // 1440×400 desktop, 4 layers × 2 rows = 8 rows.
    const result = deriveScrollModeActive(1440, 400, 4, 8)
    expect(result.tier).toBe("desktop")
    expect(result.cell_height).toBeLessThan(MIN_READABLE_CELL_HEIGHT)
    expect(result.tier_three_threshold_breached).toBe(true)
    expect(result.scroll_mode_active).toBe(true)
  })

  it("does NOT dispatch at desktop 1440x900 with light composition", () => {
    const result = deriveScrollModeActive(1440, 900, 2, 3)
    expect(result.tier).toBe("desktop")
    expect(result.cell_height).toBeGreaterThanOrEqual(
      MIN_READABLE_CELL_HEIGHT,
    )
    expect(result.scroll_mode_active).toBe(false)
  })

  it("tier-three threshold is INERT on mobile (mobile fallback wins on its own)", () => {
    // Mobile with crushed cell_height — scroll mode dispatches via
    // mobile fallback, NOT via tier-three breach (which only fires
    // for tablet+).
    const result = deriveScrollModeActive(320, 400, 4, 8)
    expect(result.tier).toBe("mobile")
    expect(result.tier_three_threshold_breached).toBe(false)
    expect(result.scroll_mode_active).toBe(true)
  })

  it("tier-three threshold checks cell_height>0 (avoids dispatch when no rows)", () => {
    // No populated rows → cell_height = 0 → not "breached"; just empty.
    const result = deriveScrollModeActive(1440, 200, 0, 0)
    expect(result.cell_height).toBe(0)
    expect(result.tier_three_threshold_breached).toBe(false)
    expect(result.scroll_mode_active).toBe(false)
  })
})


// ── TestScrollModeRendering ──────────────────────────────────────────


describe("TestScrollModeRendering", () => {
  // PulseSurface integration tests — mock usePulseComposition + check
  // root attributes / inline style.

  async function renderPulseSurfaceMobile() {
    // Set viewport BEFORE module import so useViewportDimensions()
    // initial state reads the mobile width. jsdom's default is 1024×768.
    Object.defineProperty(window, "innerWidth", {
      value: 375,
      configurable: true,
    })
    Object.defineProperty(window, "innerHeight", {
      value: 667,
      configurable: true,
    })

    vi.doMock("@/hooks/usePulseComposition", () => ({
      usePulseComposition: () => ({
        composition: {
          user_id: "u1",
          composed_at: "2026-04-29T07:30:00Z",
          layers: [
            {
              layer: "personal",
              items: [
                makeWidgetItem({ item_id: "p1", cols: 2, rows: 1 }),
              ],
              advisory: null,
            },
            {
              layer: "operational",
              items: [
                makeWidgetItem({
                  item_id: "o1",
                  component_key: "vault_schedule",
                  cols: 2,
                  rows: 1,
                }),
              ],
              advisory: null,
            },
            { layer: "anomaly", items: [], advisory: null },
            { layer: "activity", items: [], advisory: null },
          ],
          intelligence_streams: [],
          metadata: {
            work_areas_used: ["Production Scheduling"],
            vertical_default_applied: false,
            time_of_day_signal: "morning",
          },
        },
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        pulseLoadedAt: 1000,
      }),
    }))
    vi.doMock("@/services/pulse-service", () => ({
      recordDismiss: vi.fn(),
      recordNavigation: vi.fn(),
      fetchPulseComposition: vi.fn(),
    }))
    vi.doMock("@/components/focus/canvas/widget-renderers", () => ({
      getWidgetRenderer: () => () =>
        <div data-testid="mock-widget-renderer">mock</div>,
    }))
    vi.resetModules()
    const { PulseSurface } = await import(
      "@/components/spaces/PulseSurface"
    )
    return render(
      <MemoryRouter>
        <PulseSurface />
      </MemoryRouter>,
    )
  }

  it("sets data-scroll-mode='true' on PulseSurface root at mobile viewport", async () => {
    const { container } = await renderPulseSurfaceMobile()
    const surface = container.querySelector(
      '[data-slot="pulse-surface"]',
    )
    expect(surface).not.toBeNull()
    expect(surface!.getAttribute("data-scroll-mode")).toBe("true")
  })

  it("sets --pulse-cell-height to 'auto' sentinel in scroll mode", async () => {
    const { container } = await renderPulseSurfaceMobile()
    const surface = container.querySelector(
      '[data-slot="pulse-surface"]',
    ) as HTMLElement
    const styleAttr = surface.getAttribute("style") ?? ""
    expect(styleAttr).toContain("--pulse-cell-height: auto")
  })

  it("still sets --pulse-content-height + --pulse-column-count + --pulse-scale", async () => {
    const { container } = await renderPulseSurfaceMobile()
    const surface = container.querySelector(
      '[data-slot="pulse-surface"]',
    ) as HTMLElement
    const styleAttr = surface.getAttribute("style") ?? ""
    expect(styleAttr).toContain("--pulse-content-height:")
    expect(styleAttr).toContain("--pulse-column-count: 2")
    expect(styleAttr).toContain("--pulse-scale:")
  })

  it("data-viewport-tier reflects mobile tier", async () => {
    const { container } = await renderPulseSurfaceMobile()
    const surface = container.querySelector(
      '[data-slot="pulse-surface"]',
    )
    expect(surface!.getAttribute("data-viewport-tier")).toBe("mobile")
    expect(surface!.getAttribute("data-column-count")).toBe("2")
  })
})


// ── TestScrollModeTransition ──────────────────────────────────────────


describe("TestScrollModeTransition", () => {
  it("derived state flips correctly across desktop → mobile transition", () => {
    // Desktop comfortable: scroll mode false
    const desktop = deriveScrollModeActive(1440, 900, 2, 3)
    expect(desktop.scroll_mode_active).toBe(false)
    // Mobile: scroll mode true
    const mobile = deriveScrollModeActive(375, 667, 2, 3)
    expect(mobile.scroll_mode_active).toBe(true)
    // Same composition, different viewport → different scroll-mode
    // outcome (dynamic recompute, not session-sticky).
  })

  it("derived state releases scroll mode on tablet → comfortable resize", () => {
    // Compressed tablet: scroll mode true (tier-three breach)
    const compressed = deriveScrollModeActive(800, 500, 4, 8)
    expect(compressed.scroll_mode_active).toBe(true)
    // Resize to comfortable height: scroll mode releases
    const comfortable = deriveScrollModeActive(800, 1024, 4, 8)
    expect(comfortable.scroll_mode_active).toBe(false)
  })

  it("column count tracks viewport tier independent of scroll mode", () => {
    // Mobile in scroll mode: column_count=2 still resolved
    expect(getColumnCountForTier(getViewportTier(375))).toBe(2)
    // Tablet (regardless of breach): column_count=4
    expect(getColumnCountForTier(getViewportTier(800))).toBe(4)
    // Desktop (regardless of breach): column_count=6
    expect(getColumnCountForTier(getViewportTier(1440))).toBe(6)
  })
})


// ── TestSubPixelBoundaryBuffer ───────────────────────────────────────


describe("TestSubPixelBoundaryBuffer", () => {
  // The buffer adjusts CSS @container thresholds 100→99.5 and
  // 120→119.5 to handle Chromium sub-pixel rounding edge cases. Test
  // by reading the compiled CSS file string contents — assertions
  // verify the canonical buffered values are what ship.

  it("pulse-density.css uses (max-height: 117.5px) for compact tier threshold", () => {
    // Threshold = 117.5 px content-area = canon 120 piece-outer
    //   − 2 px Pattern 2 border − 0.5 px sub-pixel buffer.
    const css = loadPulseDensityCss()
    expect(css).toContain("max-height: 117.5px")
  })

  it("pulse-density.css uses (max-height: 97.5px) for ultra-compact tier threshold", () => {
    // Threshold = 97.5 px content-area = canon 100 piece-outer
    //   − 2 px Pattern 2 border − 0.5 px sub-pixel buffer.
    const css = loadPulseDensityCss()
    expect(css).toContain("max-height: 97.5px")
  })

  it("pulse-density.css does NOT use the unbuffered 100px / 120px thresholds in @container rules", () => {
    const css = loadPulseDensityCss()
    // Strip block comments so prose mentioning "100px" / "120px" in
    // the rationale doesn't false-positive. Only the @container
    // RULES (uncommented CSS) need to use the buffered values.
    const codeOnly = css.replace(/\/\*[\s\S]*?\*\//g, "")
    expect(codeOnly).not.toMatch(/@container[^{]*max-height:\s*100px/)
    expect(codeOnly).not.toMatch(/@container[^{]*max-height:\s*120px/)
    // Also verify the intermediate 99.5/119.5 values from earlier in
    // Commit 3 development aren't lingering — we shipped 97.5/117.5.
    expect(codeOnly).not.toMatch(/@container[^{]*max-height:\s*99\.5px/)
    expect(codeOnly).not.toMatch(/@container[^{]*max-height:\s*119\.5px/)
  })

  it("pulse-density.css declares the scroll-mode override selector", () => {
    const css = loadPulseDensityCss()
    // Scroll-mode CSS override flips PulseLayer's grid → flex-column
    // when PulseSurface root carries data-scroll-mode="true".
    expect(css).toContain(
      '[data-slot="pulse-surface"][data-scroll-mode="true"]',
    )
    expect(css).toContain("flex-direction: column")
  })
})


// ── TestPulseLayerScrollModeIntegration ─────────────────────────────


describe("TestPulseLayerScrollModeIntegration", () => {
  // PulseLayer always renders with grid display + grid-template-* in
  // its inline style — the scroll-mode override is via CSS attribute
  // selector on the parent PulseSurface. Verify the PulseLayer DOM
  // doesn't conditionally render different shapes — same DOM, CSS
  // dispatches.

  it("PulseLayer renders the same grid markup regardless of scroll mode", async () => {
    const { PulseLayer } = await import(
      "@/components/spaces/PulseLayer"
    )
    const layer: LayerContent = {
      layer: "personal",
      items: [makeWidgetItem({ cols: 2, rows: 1 })],
      advisory: null,
    }
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
    // Grid present + inline grid-template-* still set. Scroll mode is
    // a parent-level CSS override, not a PulseLayer prop branch.
    const grid = container.querySelector(
      '[data-slot="pulse-layer-grid"]',
    ) as HTMLElement | null
    expect(grid).not.toBeNull()
    const styleAttr = grid!.getAttribute("style") ?? ""
    expect(styleAttr).toContain("grid-template-rows")
    expect(styleAttr).toContain("grid-template-columns")
  })
})
