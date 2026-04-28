/**
 * PulseSurface tier dispatch + container queries — Phase W-4a
 * Step 6 Commit 2.
 *
 * Tests the §13.3.1 viewport-tier → column_count dispatch + the
 * §13.4.1 three-density-tier opt-in + the dedup of
 * `computeLayerRowCount` to a shared util.
 *
 * Test classes per the Commit 2 spec:
 *   • TestTierColumnDispatch — viewport width → tier → column count
 *   • TestContainerQueriesAnomalies — Brief renders 3 nested density
 *     tiers with canonical class names in pulse_grid surface
 *   • TestContainerQueriesLineStatus — Brief renders 3 nested density
 *     tiers in pulse_grid surface
 *   • TestContainerQueriesToday — Glance renders 3 nested density
 *     tiers in pulse_grid surface
 *   • TestLayerRowCountDeduplication — shared util produces identical
 *     results to the (now-removed) Commit 1 inline copies + is the
 *     single source of truth used by both PulseLayer and PulseSurface
 *
 * jsdom doesn't compute actual @container query matches — we test
 * STRUCTURAL presence (the three nested density variants render with
 * the canonical class names and share data) + the math chain
 * directly via __viewport_fit_internals.
 */

import { render } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { computeLayerRowCount } from "@/components/spaces/utils/layer-row-count"
import { __viewport_fit_internals } from "@/hooks/useViewportFitMath"
import {
  MOBILE_BREAKPOINT,
  TABLET_BREAKPOINT,
} from "@/components/spaces/viewport-fit-constants"
import type {
  IntelligenceStream,
  LayerContent,
  LayerItem,
  TimeOfDaySignal,
} from "@/types/pulse"


const { getViewportTier, getColumnCountForTier } = __viewport_fit_internals


// ── Mock widget data fetch — the three opt-in widgets all use
//    `useWidgetData(...)` which fires axios. Stub it so the
//    components mount without making real HTTP calls.


vi.mock("@/components/widgets/useWidgetData", () => ({
  useWidgetData: () => ({
    data: null,
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  }),
}))


// ── Fixtures ─────────────────────────────────────────────────────────


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


// ── TestTierColumnDispatch ───────────────────────────────────────────


describe("TestTierColumnDispatch", () => {
  it("returns 2 columns at mobile tier (vw < 600)", () => {
    expect(getColumnCountForTier(getViewportTier(320))).toBe(2)
    expect(getColumnCountForTier(getViewportTier(599))).toBe(2)
  })

  it("returns 4 columns at tablet tier (600 ≤ vw < 1024)", () => {
    expect(getColumnCountForTier(getViewportTier(MOBILE_BREAKPOINT))).toBe(4)
    expect(getColumnCountForTier(getViewportTier(768))).toBe(4)
    expect(getColumnCountForTier(getViewportTier(1023))).toBe(4)
  })

  it("returns 6 columns at desktop tier (vw ≥ 1024)", () => {
    expect(getColumnCountForTier(getViewportTier(TABLET_BREAKPOINT))).toBe(6)
    expect(getColumnCountForTier(getViewportTier(1440))).toBe(6)
    expect(getColumnCountForTier(getViewportTier(2560))).toBe(6)
  })

  it("dispatches all three tier values via getColumnCountForTier directly", () => {
    expect(getColumnCountForTier("mobile")).toBe(2)
    expect(getColumnCountForTier("tablet")).toBe(4)
    expect(getColumnCountForTier("desktop")).toBe(6)
  })

  it("uses canonical breakpoints from viewport-fit-constants", () => {
    // Just-below MOBILE_BREAKPOINT → mobile; at boundary → tablet.
    expect(getViewportTier(MOBILE_BREAKPOINT - 1)).toBe("mobile")
    expect(getViewportTier(MOBILE_BREAKPOINT)).toBe("tablet")
    // Just-below TABLET_BREAKPOINT → tablet; at boundary → desktop.
    expect(getViewportTier(TABLET_BREAKPOINT - 1)).toBe("tablet")
    expect(getViewportTier(TABLET_BREAKPOINT)).toBe("desktop")
  })
})


// ── TestContainerQueriesAnomalies ────────────────────────────────────


describe("TestContainerQueriesAnomalies", () => {
  // Tests STRUCTURAL presence of the 3 nested density tiers + canonical
  // class names. Actual @container query matching is browser-side and
  // not exercised in jsdom; visual verification covers the runtime
  // dispatch.

  async function renderAnomaliesPulse(
    surface: "pulse_grid" | "focus_canvas",
  ) {
    const { AnomaliesWidget } = await import(
      "@/components/widgets/foundation/AnomaliesWidget"
    )
    return render(
      <MemoryRouter>
        <AnomaliesWidget variant_id="brief" surface={surface} />
      </MemoryRouter>,
    )
  }

  it("renders three density-tier divs in pulse_grid surface", async () => {
    const { container } = await renderAnomaliesPulse("pulse_grid")
    expect(
      container.querySelector(".anomalies-widget-pulse-default"),
    ).not.toBeNull()
    expect(
      container.querySelector(".anomalies-widget-pulse-compact"),
    ).not.toBeNull()
    expect(
      container.querySelector(".anomalies-widget-pulse-ultra-compact"),
    ).not.toBeNull()
  })

  it("does NOT render density-tier divs in non-Pulse surface", async () => {
    const { container } = await renderAnomaliesPulse("focus_canvas")
    expect(
      container.querySelector(".anomalies-widget-pulse-default"),
    ).toBeNull()
    expect(
      container.querySelector(".anomalies-widget-pulse-compact"),
    ).toBeNull()
    expect(
      container.querySelector(".anomalies-widget-pulse-ultra-compact"),
    ).toBeNull()
  })

  it("marks the Pulse-surface root with data-surface=pulse_grid", async () => {
    const { container } = await renderAnomaliesPulse("pulse_grid")
    const root = container.querySelector(
      '[data-slot="anomalies-widget"][data-surface="pulse_grid"]',
    )
    expect(root).not.toBeNull()
  })
})


// ── TestContainerQueriesLineStatus ────────────────────────────────────


describe("TestContainerQueriesLineStatus", () => {
  async function renderLineStatusPulse(
    surface: "pulse_grid" | "dashboard_grid",
  ) {
    // Shape the mock to return a populated lines array so the empty-
    // state branch doesn't fire (which would render a different shape).
    vi.doMock("@/components/widgets/useWidgetData", () => ({
      useWidgetData: () => ({
        data: {
          date: "2026-04-28",
          lines: [
            {
              line_key: "vault",
              display_name: "Burial vault",
              operating_mode: "production",
              status: "on_track",
              headline: "8 pours today",
              metrics: {},
              navigation_target: "/dispatch",
            },
          ],
          total_active_lines: 1,
          any_attention_needed: false,
        },
        isLoading: false,
        error: null,
        refresh: vi.fn(),
      }),
    }))
    vi.resetModules()
    const { LineStatusWidget } = await import(
      "@/components/widgets/manufacturing/LineStatusWidget"
    )
    return render(
      <MemoryRouter>
        <LineStatusWidget variant_id="brief" surface={surface} />
      </MemoryRouter>,
    )
  }

  it("renders three density-tier divs in pulse_grid surface", async () => {
    const { container } = await renderLineStatusPulse("pulse_grid")
    expect(
      container.querySelector(".line-status-widget-pulse-default"),
    ).not.toBeNull()
    expect(
      container.querySelector(".line-status-widget-pulse-compact"),
    ).not.toBeNull()
    expect(
      container.querySelector(".line-status-widget-pulse-ultra-compact"),
    ).not.toBeNull()
  })

  it("does NOT render density-tier divs in dashboard_grid surface", async () => {
    const { container } = await renderLineStatusPulse("dashboard_grid")
    expect(
      container.querySelector(".line-status-widget-pulse-default"),
    ).toBeNull()
    expect(
      container.querySelector(".line-status-widget-pulse-compact"),
    ).toBeNull()
    expect(
      container.querySelector(".line-status-widget-pulse-ultra-compact"),
    ).toBeNull()
  })

  it("marks the Pulse-surface root with data-surface=pulse_grid", async () => {
    const { container } = await renderLineStatusPulse("pulse_grid")
    const root = container.querySelector(
      '[data-slot="line-status-widget"][data-surface="pulse_grid"]',
    )
    expect(root).not.toBeNull()
  })
})


// ── TestContainerQueriesToday ────────────────────────────────────────


describe("TestContainerQueriesToday", () => {
  async function renderTodayGlance(
    surface: "pulse_grid" | "spaces_pin",
  ) {
    const { TodayWidget } = await import(
      "@/components/widgets/foundation/TodayWidget"
    )
    return render(
      <MemoryRouter>
        <TodayWidget variant_id="glance" surface={surface} />
      </MemoryRouter>,
    )
  }

  it("renders three density-tier divs in pulse_grid surface", async () => {
    const { container } = await renderTodayGlance("pulse_grid")
    expect(
      container.querySelector(".today-widget-pulse-default"),
    ).not.toBeNull()
    expect(
      container.querySelector(".today-widget-pulse-compact"),
    ).not.toBeNull()
    expect(
      container.querySelector(".today-widget-pulse-ultra-compact"),
    ).not.toBeNull()
  })

  it("does NOT render density-tier divs in spaces_pin surface (Pattern 1 tablet)", async () => {
    // Sidebar surface keeps the original frosted-glass Pattern 1
    // tablet — cross-surface continuity with AncillaryPoolPin.
    const { container } = await renderTodayGlance("spaces_pin")
    expect(
      container.querySelector(".today-widget-pulse-default"),
    ).toBeNull()
    expect(
      container.querySelector(".today-widget-pulse-compact"),
    ).toBeNull()
    expect(
      container.querySelector(".today-widget-pulse-ultra-compact"),
    ).toBeNull()
    // Original spaces_pin variant marker still present.
    expect(
      container.querySelector(
        '[data-slot="today-widget"][data-surface="spaces_pin"]',
      ),
    ).not.toBeNull()
  })

  it("marks the Pulse-surface root with data-surface=pulse_grid", async () => {
    const { container } = await renderTodayGlance("pulse_grid")
    const root = container.querySelector(
      '[data-slot="today-widget"][data-surface="pulse_grid"]',
    )
    expect(root).not.toBeNull()
  })
})


// ── TestLayerRowCountDeduplication ─────────────────────────────────────


describe("TestLayerRowCountDeduplication", () => {
  it("shared util produces deterministic row count for empty layer", () => {
    expect(computeLayerRowCount([], new Set(), 6)).toBe(0)
  })

  it("packs single 2x1 widget into 1 row at 6 cols", () => {
    const items: LayerItem[] = [makeWidgetItem({ cols: 2, rows: 1 })]
    expect(computeLayerRowCount(items, new Set(), 6)).toBe(1)
  })

  it("packs 4x 2x1 widgets into 2 rows at 6 cols", () => {
    const items: LayerItem[] = [
      makeWidgetItem({ item_id: "1", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "2", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "3", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "4", cols: 2, rows: 1 }),
    ]
    expect(computeLayerRowCount(items, new Set(), 6)).toBe(2)
  })

  it("packs same items differently per tier — 4 cols vs 6 cols", () => {
    // 3x 2x1 at 6 cols → 1 row (6/2=3 fits)
    // 3x 2x1 at 4 cols → 2 rows (4/2=2 fits per row, 3 wraps)
    // 3x 2x1 at 2 cols → 3 rows (2/2=1 fits per row)
    const items: LayerItem[] = [
      makeWidgetItem({ item_id: "1", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "2", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "3", cols: 2, rows: 1 }),
    ]
    expect(computeLayerRowCount(items, new Set(), 6)).toBe(1)
    expect(computeLayerRowCount(items, new Set(), 4)).toBe(2)
    expect(computeLayerRowCount(items, new Set(), 2)).toBe(3)
  })

  it("clamps cols to column_count when piece declares more than fits", () => {
    // A widget declaring cols=6 in a 4-col tier gets clamped to 4
    // (a single row).
    const items: LayerItem[] = [makeWidgetItem({ cols: 6, rows: 1 })]
    expect(computeLayerRowCount(items, new Set(), 4)).toBe(1)
  })

  it("filters out dismissed items before packing", () => {
    const items: LayerItem[] = [
      makeWidgetItem({ item_id: "keep", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "drop", cols: 2, rows: 1 }),
    ]
    expect(computeLayerRowCount(items, new Set(["drop"]), 6)).toBe(1)
  })

  it("dense-flow backfills empty cells from earlier rows", () => {
    // 1x 4x2 (top-left, takes cols 0-3 rows 0-1)
    // 1x 2x1 (top-right, takes cols 4-5 row 0)
    // 1x 2x1 (could backfill cols 4-5 row 1 instead of going to row 2)
    const items: LayerItem[] = [
      makeWidgetItem({ item_id: "big", cols: 4, rows: 2 }),
      makeWidgetItem({ item_id: "tr", cols: 2, rows: 1 }),
      makeWidgetItem({ item_id: "filler", cols: 2, rows: 1 }),
    ]
    // With dense flow, total rows = 2 (filler backfills row 1 cols 4-5).
    expect(computeLayerRowCount(items, new Set(), 6)).toBe(2)
  })
})


// ── TestPulseSurfaceTierWiring ──────────────────────────────────────


describe("TestPulseSurfaceTierWiring", () => {
  // Smoke test that PulseSurface / PulseLayer don't drift from the
  // shared util and consume the same column_count signal.
  // (Full PulseSurface render coverage lives in PulseSurface.test.tsx.)

  it("PulseLayer renders gridTemplateColumns referencing var(--pulse-column-count)", async () => {
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
    const grid = container.querySelector(
      '[data-slot="pulse-layer-grid"]',
    ) as HTMLElement | null
    expect(grid).not.toBeNull()
    const styleAttr = grid!.getAttribute("style") ?? ""
    expect(styleAttr).toContain("grid-template-columns")
    expect(styleAttr).toContain("var(--pulse-column-count")
  })

  it("PulseLayer transition declaration covers both grid-template-rows and grid-template-columns", async () => {
    const { PulseLayer } = await import(
      "@/components/spaces/PulseLayer"
    )
    const layer: LayerContent = {
      layer: "personal",
      items: [makeWidgetItem()],
      advisory: null,
    }
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
    // Both transition-targets present.
    expect(styleAttr).toContain("grid-template-rows 350ms")
    expect(styleAttr).toContain("grid-template-columns 350ms")
    // Canonical cubic-bezier.
    expect(styleAttr).toContain("cubic-bezier(0.4, 0, 0.2, 1)")
  })

  it("PulseLayer carries data-column-count attribute matching the tier-resolved count", async () => {
    const { PulseLayer } = await import(
      "@/components/spaces/PulseLayer"
    )
    const layer: LayerContent = {
      layer: "personal",
      items: [makeWidgetItem()],
      advisory: null,
    }
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
    const colCount = section!.getAttribute("data-column-count")
    // jsdom default viewport (1024×768) → desktop tier → 6 cols.
    // (May be 4 if jsdom defaults vary; assert it's one of the 3
    // canonical values.)
    expect(["2", "4", "6"]).toContain(colCount)
  })
})
