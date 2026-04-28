/**
 * PinnedSection — Widget Library Phase W-2 widget pin tests.
 *
 * Scope: vitest unit-level coverage of the widget-pin rendering branch
 * added in Commit 3. Widget pins should:
 *   • Render via `getWidgetRenderer(widget_id)` with `surface="spaces_pin"`
 *   • Click → summon the matching Focus via `useFocus().open(focusId)`
 *   • Drag-to-reorder works alongside other pin types
 *   • Hover → reveal an unpin X (absolute-positioned over the tablet)
 *   • Unavailable widget → graceful icon-row fallback
 *
 * Out of scope here (covered by Playwright `spaces-phase-3.spec.ts` +
 * the upcoming Phase W-2 spec): full mixed-pin rendering across an
 * actual server-fetched space, real drag motion via pointer events.
 */

import { render } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  registerWidgetRenderer,
  _resetWidgetRendererRegistryForTests,
} from "@/components/focus/canvas/widget-renderers"
import type { ResolvedPin, Space } from "@/types/spaces"


// ── Module mocks ────────────────────────────────────────────────────


// Mock useSpaces / useAffinityVisit / useFocus so we can drive the
// PinnedSection without setting up the full provider stack.
const mockOpen = vi.fn()
const mockRemovePin = vi.fn()
const mockReorderPins = vi.fn()
const mockRecordVisit = vi.fn()


// State the mocked useSpaces() returns. Tests mutate `mockActiveSpace`
// before render to drive what's pinned.
let mockActiveSpace: Space | null = null


vi.mock("@/contexts/space-context", () => ({
  useSpaces: () => ({
    activeSpace: mockActiveSpace,
    removePin: mockRemovePin,
    reorderPins: mockReorderPins,
  }),
}))

vi.mock("@/hooks/useAffinityVisit", () => ({
  useAffinityVisit: () => ({ recordVisit: mockRecordVisit }),
}))

vi.mock("@/contexts/focus-context", () => ({
  useFocus: () => ({
    open: mockOpen,
    close: vi.fn(),
    dismissReturnPill: vi.fn(),
    currentFocus: null,
    isOpen: false,
    lastClosedFocus: null,
    updateSessionLayout: vi.fn(),
    removeWidget: vi.fn(),
  }),
}))


// Import PinnedSection AFTER vi.mock declarations so the mocked
// modules are wired in.
import { PinnedSection } from "./PinnedSection"


// ── Helpers ─────────────────────────────────────────────────────────


function makeWidgetPin(overrides: Partial<ResolvedPin> = {}): ResolvedPin {
  return {
    pin_id: "pn_widget1",
    pin_type: "widget",
    target_id: "scheduling.ancillary-pool",
    display_order: 0,
    label: "Ancillary Pool",
    icon: "Inbox",
    href: null,
    unavailable: false,
    widget_id: "scheduling.ancillary-pool",
    variant_id: "glance",
    config: null,
    ...overrides,
  }
}


function makeNavPin(overrides: Partial<ResolvedPin> = {}): ResolvedPin {
  return {
    pin_id: "pn_nav1",
    pin_type: "nav_item",
    target_id: "/cases",
    display_order: 1,
    label: "Cases",
    icon: "FolderOpen",
    href: "/cases",
    unavailable: false,
    ...overrides,
  }
}


function makeSpace(pins: ResolvedPin[]): Space {
  return {
    space_id: "sp_test123",
    name: "Test Space",
    icon: "home",
    accent: "warm",
    display_order: 0,
    is_default: true,
    density: "comfortable",
    is_system: false,
    default_home_route: null,
    pins,
    created_at: null,
    updated_at: null,
  }
}


// Test stub component for the widget renderer. Registered before
// each test so we can verify dispatch + props without depending on
// AncillaryPoolPin (which would couple this test to its impl).
const widgetRendered = vi.fn()
function TestStubWidget({
  widgetId,
  variant_id,
  surface,
  config,
}: {
  widgetId: string
  variant_id?: string
  surface?: string
  config?: Record<string, unknown>
}) {
  widgetRendered({ widgetId, variant_id, surface, config })
  return (
    <div
      data-testid="test-stub-widget"
      data-widget-id={widgetId}
      data-variant-id={variant_id ?? ""}
      data-surface={surface ?? ""}
      data-config={config ? JSON.stringify(config) : ""}
    >
      stub
    </div>
  )
}


beforeEach(() => {
  mockActiveSpace = null
  mockOpen.mockClear()
  mockRemovePin.mockClear()
  mockReorderPins.mockClear()
  mockRecordVisit.mockClear()
  widgetRendered.mockClear()
  _resetWidgetRendererRegistryForTests()
  registerWidgetRenderer("scheduling.ancillary-pool", TestStubWidget)
})


afterEach(() => {
  vi.clearAllMocks()
})


function renderInRouter(ui: React.ReactNode) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}


// ── Tests ───────────────────────────────────────────────────────────


describe("PinnedSection — widget pin rendering (Phase W-2)", () => {
  it("renders widget pin via getWidgetRenderer with surface=spaces_pin", () => {
    mockActiveSpace = makeSpace([makeWidgetPin()])
    renderInRouter(<PinnedSection />)

    const stub = document.querySelector('[data-testid="test-stub-widget"]')
    expect(stub).toBeInTheDocument()
    expect(stub?.getAttribute("data-widget-id")).toBe(
      "scheduling.ancillary-pool",
    )
    expect(stub?.getAttribute("data-variant-id")).toBe("glance")
    expect(stub?.getAttribute("data-surface")).toBe("spaces_pin")
  })

  it("widget renderer receives variant_id from pin config", () => {
    mockActiveSpace = makeSpace([
      makeWidgetPin({ variant_id: "brief" }),
    ])
    renderInRouter(<PinnedSection />)

    expect(widgetRendered).toHaveBeenCalledWith(
      expect.objectContaining({
        widgetId: "scheduling.ancillary-pool",
        variant_id: "brief",
        surface: "spaces_pin",
      }),
    )
  })

  it("default variant_id is 'glance' when pin has no variant_id", () => {
    mockActiveSpace = makeSpace([
      makeWidgetPin({ variant_id: null }),
    ])
    renderInRouter(<PinnedSection />)

    expect(widgetRendered).toHaveBeenCalledWith(
      expect.objectContaining({ variant_id: "glance" }),
    )
  })

  it("widget pin click summons matching Focus", () => {
    mockActiveSpace = makeSpace([makeWidgetPin()])
    renderInRouter(<PinnedSection />)

    const wrapper = document.querySelector(
      '[data-pin-type="widget"]',
    ) as HTMLElement
    wrapper.click()

    expect(mockOpen).toHaveBeenCalledWith("funeral-scheduling")
    expect(mockOpen).toHaveBeenCalledTimes(1)
  })

  it("widget pin click does NOT record affinity (decision deferred)", () => {
    // Section 12.6a: widget summons are Focus opens, not navigates.
    // Phase 8e.1 affinity target_type whitelist excludes "widget".
    mockActiveSpace = makeSpace([makeWidgetPin()])
    renderInRouter(<PinnedSection />)

    const wrapper = document.querySelector(
      '[data-pin-type="widget"]',
    ) as HTMLElement
    wrapper.click()

    expect(mockRecordVisit).not.toHaveBeenCalled()
  })

  it("nav pin click still records affinity (regression guard)", () => {
    mockActiveSpace = makeSpace([makeNavPin()])
    renderInRouter(<PinnedSection />)

    const link = document.querySelector(
      '[data-pin-id="pn_nav1"]',
    ) as HTMLElement
    link.click()

    expect(mockRecordVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        targetType: "nav_item",
        targetId: "/cases",
      }),
    )
  })

  it("widget pin without summon mapping is a no-op click (graceful)", () => {
    // A widget that doesn't appear in WIDGET_FOCUS_SUMMON should
    // render but click should not throw and not call focus.open.
    registerWidgetRenderer("unknown.widget", TestStubWidget)
    mockActiveSpace = makeSpace([
      makeWidgetPin({
        target_id: "unknown.widget",
        widget_id: "unknown.widget",
      }),
    ])
    renderInRouter(<PinnedSection />)

    const wrapper = document.querySelector(
      '[data-pin-type="widget"]',
    ) as HTMLElement
    wrapper.click()

    expect(mockOpen).not.toHaveBeenCalled()
  })

  it("unavailable widget pin renders icon-row fallback", () => {
    mockActiveSpace = makeSpace([
      makeWidgetPin({ unavailable: true }),
    ])
    renderInRouter(<PinnedSection />)

    // Stub widget should NOT render — fallback icon-row instead.
    expect(
      document.querySelector('[data-testid="test-stub-widget"]'),
    ).toBeNull()
    const fallback = document.querySelector(
      '[data-pin-type="widget"][data-unavailable="true"]',
    )
    expect(fallback).toBeInTheDocument()
    expect(fallback?.textContent).toContain("Ancillary Pool")
  })

  it("widget pin row carries data attributes for Playwright drag tests", () => {
    mockActiveSpace = makeSpace([makeWidgetPin()])
    renderInRouter(<PinnedSection />)

    const row = document.querySelector(
      '[data-pin-type="widget"]',
    ) as HTMLElement
    expect(row.getAttribute("data-pin-id")).toBe("pn_widget1")
    expect(row.getAttribute("data-pin-widget-id")).toBe(
      "scheduling.ancillary-pool",
    )
    expect(row.getAttribute("data-pin-variant-id")).toBe("glance")
    // draggable attribute for HTML5 drag-and-drop reorder.
    expect(row.getAttribute("draggable")).toBe("true")
  })

  it("widget pins coexist with other pin types in same space", () => {
    mockActiveSpace = makeSpace([
      makeWidgetPin({ display_order: 0 }),
      makeNavPin({ display_order: 1 }),
    ])
    renderInRouter(<PinnedSection />)

    expect(
      document.querySelector('[data-testid="test-stub-widget"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-pin-id="pn_nav1"]'),
    ).toBeInTheDocument()
    // Widget pin's wrapper has data-pin-type="widget"; nav pin
    // does not (it's the standard PinRow shape).
    const allPinRows = document.querySelectorAll('[data-pin-id]')
    expect(allPinRows.length).toBeGreaterThanOrEqual(2)
  })

  it("MissingWidgetEmptyState fallback when widget_id has no registered component", () => {
    // Phase W-4a Step 5 (May 2026): when a widget pin's id isn't in
    // the renderer registry (registration module failed to import,
    // backend/frontend widget_id mismatch, etc.), fallback is
    // MissingWidgetEmptyState — an honest "Widget unavailable"
    // empty state. Pre-Step-5 the fallback was MockSavedViewWidget
    // (a dev fixture rendering fake "Recent Cases" mock data); that
    // masked widget-id mismatches as "looks like contamination" in
    // production. Split: undefined widgetType → MockSavedViewWidget
    // (legacy/test path); set-but-unknown widgetType → this new
    // empty state.
    _resetWidgetRendererRegistryForTests()
    // Don't re-register scheduling.ancillary-pool; should fall back.
    mockActiveSpace = makeSpace([makeWidgetPin()])
    renderInRouter(<PinnedSection />)

    // Stub didn't render (we cleared its registration);
    // MissingWidgetEmptyState renders in its place.
    expect(
      document.querySelector('[data-testid="test-stub-widget"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-slot="missing-widget-empty"]'),
    ).toBeInTheDocument()
    // Empty state surfaces the offending widget_id for QA
    // observability.
    expect(document.body.textContent).toContain("Widget unavailable")
    // Wrapper still renders with widget data attributes — fallback
    // doesn't hide the pin.
    expect(
      document.querySelector('[data-pin-type="widget"]'),
    ).toBeInTheDocument()
  })

  // ── Phase W-3b Commit 0 — config plumbing ─────────────────────────

  it("Phase W-3b: pin.config passes through to widget component", () => {
    // The W-3b config plumbing fix — PinConfig.config storage existed
    // since Phase W-2 but was not passed to the widget component.
    // saved_view + future config-driven widgets depend on this.
    const customConfig = { view_id: "abc-123", filter: "open" }
    mockActiveSpace = makeSpace([
      makeWidgetPin({ config: customConfig }),
    ])
    renderInRouter(<PinnedSection />)

    expect(widgetRendered).toHaveBeenCalledWith(
      expect.objectContaining({
        widgetId: "scheduling.ancillary-pool",
        variant_id: "glance",
        surface: "spaces_pin",
        config: customConfig,
      }),
    )

    // Also verify via DOM data attribute
    const stub = document.querySelector(
      '[data-testid="test-stub-widget"]',
    )
    const dataConfig = stub?.getAttribute("data-config") ?? ""
    expect(JSON.parse(dataConfig)).toEqual(customConfig)
  })

  it("Phase W-3b: pin without config passes config=undefined to widget", () => {
    // Backward-compat: pins that don't carry per-instance config
    // (every W-3a foundation widget pin) receive undefined. Widgets
    // that ignore the prop (today, operator_profile, recent_activity,
    // anomalies) continue to work unchanged.
    mockActiveSpace = makeSpace([makeWidgetPin({ config: null })])
    renderInRouter(<PinnedSection />)

    expect(widgetRendered).toHaveBeenCalledWith(
      expect.objectContaining({
        widgetId: "scheduling.ancillary-pool",
        config: undefined,
      }),
    )
  })
})
