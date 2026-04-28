/**
 * PulseSurface — vitest unit tests (Phase W-4a Commit 5).
 *
 * Test classes (per the user's spec):
 *   • TestPulseSurface — top-level rendering + loading/error/layer
 *     ordering / brass-thread divider
 *   • TestPulsePiece — widget vs stream dispatch + size hints +
 *     pulse_grid surface
 *   • TestAnomalyIntelligenceStream — synthesized text + chips +
 *     brass-thread accent
 *   • TestSignalCollection — dismiss + navigation tracking
 *   • TestFirstLoginBanner — vertical-default-applied gating
 *   • TestVisualChrome — brass thread above operational, accents
 *     on intelligence stream pieces
 */

import { render, waitFor, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest"

import type {
  IntelligenceStream,
  LayerContent,
  LayerItem,
  PulseComposition,
} from "@/types/pulse"


// ── Mocks ───────────────────────────────────────────────────────────


let mockComposition: PulseComposition | null = null
let mockLoading = false
let mockError: string | null = null
const mockRefresh = vi.fn(async () => {})
const mockUseHook = vi.fn(() => ({
  composition: mockComposition,
  isLoading: mockLoading,
  error: mockError,
  refresh: mockRefresh,
  pulseLoadedAt: 1000,
}))

vi.mock("@/hooks/usePulseComposition", () => ({
  usePulseComposition: () => mockUseHook(),
}))


const mockRecordDismiss = vi.fn(async (..._args: unknown[]) => {})
const mockRecordNavigation = vi.fn(async (..._args: unknown[]) => {})
vi.mock("@/services/pulse-service", () => ({
  recordDismiss: (...args: unknown[]) => mockRecordDismiss(...args),
  recordNavigation: (...args: unknown[]) => mockRecordNavigation(...args),
  fetchPulseComposition: vi.fn(),
}))


// Mock the widget renderer registry so tests don't need real
// widget components mounted.
const mockRendererCalls: Array<Record<string, unknown>> = []
function MockWidgetRenderer(props: Record<string, unknown>) {
  mockRendererCalls.push(props)
  return (
    <div
      data-testid="mock-widget-renderer"
      data-widget-id={String(props.widgetId)}
      data-variant-id={String(props.variant_id)}
      data-surface={String(props.surface)}
    >
      mock widget {String(props.widgetId)}
    </div>
  )
}
vi.mock("@/components/focus/canvas/widget-renderers", () => ({
  getWidgetRenderer: () => MockWidgetRenderer,
}))


const mockUseOnboardingTouch = vi.fn(() => ({
  shouldShow: true,
  dismiss: vi.fn(),
}))
vi.mock("@/hooks/useOnboardingTouch", () => ({
  useOnboardingTouch: (_key: string) => mockUseOnboardingTouch(),
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


function makeStreamItem(
  overrides: Partial<LayerItem> = {},
): LayerItem {
  return {
    item_id: "stream:anomaly_intelligence",
    kind: "stream",
    component_key: "anomaly_intelligence",
    variant_id: "brief",
    cols: 2,
    rows: 1,
    priority: 95,
    payload: {},
    ...overrides,
  }
}


function makeIntelligenceStream(
  overrides: Partial<IntelligenceStream> = {},
): IntelligenceStream {
  return {
    stream_id: "anomaly_intelligence",
    layer: "anomaly",
    title: "Today's watch list",
    synthesized_text:
      "2 critical anomalies. Most urgent: Hopkins invoice balance mismatch.",
    referenced_items: [
      {
        kind: "anomaly",
        entity_id: "a1",
        label: "Hopkins invoice balance mismatch",
        href: null,
      },
      {
        kind: "anomaly",
        entity_id: "a2",
        label: "Smith FH duplicate payment",
        href: null,
      },
    ],
    priority: 95,
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


function makeComposition(
  overrides: Partial<PulseComposition> = {},
): PulseComposition {
  return {
    user_id: "u1",
    composed_at: "2026-04-29T07:30:00Z",
    layers: [
      makeLayer("personal"),
      makeLayer("operational"),
      makeLayer("anomaly"),
      makeLayer("activity"),
    ],
    intelligence_streams: [],
    metadata: {
      work_areas_used: ["Production Scheduling"],
      vertical_default_applied: false,
      time_of_day_signal: "morning",
    },
    ...overrides,
  }
}


function renderWithRouter(component: React.ReactElement) {
  return render(<MemoryRouter>{component}</MemoryRouter>)
}


beforeEach(() => {
  mockComposition = null
  mockLoading = false
  mockError = null
  mockRefresh.mockClear()
  mockRecordDismiss.mockClear()
  mockRecordNavigation.mockClear()
  mockRendererCalls.length = 0
  mockUseHook.mockClear()
  mockUseOnboardingTouch.mockReturnValue({
    shouldShow: true,
    dismiss: vi.fn(),
  })
})


afterEach(() => {
  vi.clearAllMocks()
})


// Lazy-import after mocks set up
async function importPulseSurface() {
  const mod = await import("@/components/spaces/PulseSurface")
  return mod.PulseSurface
}


// ── TestPulseSurface ───────────────────────────────────────────────


describe("TestPulseSurface", () => {
  it("shows loading state while composition fetching", async () => {
    mockLoading = true
    mockComposition = null
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    expect(
      document.querySelector('[data-slot="pulse-surface"][data-state="loading"]'),
    ).toBeInTheDocument()
  })

  it("shows error state with retry on fetch failure", async () => {
    mockLoading = false
    mockError = "Network down"
    mockComposition = null
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    expect(
      document.querySelector('[data-slot="pulse-surface"][data-state="error"]'),
    ).toBeInTheDocument()
  })

  it("renders all four layers in canonical order", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal", [makeWidgetItem({ item_id: "widget:p1" })]),
        makeLayer("operational", [
          makeWidgetItem({ item_id: "widget:o1", component_key: "vault_schedule" }),
        ]),
        makeLayer("anomaly", [
          makeWidgetItem({ item_id: "widget:a1", component_key: "anomalies" }),
        ]),
        makeLayer("activity", [
          makeWidgetItem({
            item_id: "widget:act1",
            component_key: "recent_activity",
          }),
        ]),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)

    const layers = Array.from(
      document.querySelectorAll('[data-slot="pulse-layer"]'),
    )
    const layerNames = layers.map((el) => el.getAttribute("data-layer"))
    expect(layerNames).toEqual([
      "personal",
      "operational",
      "anomaly",
      "activity",
    ])
  })

  it("empty layers with no advisory render as null", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),  // empty + no advisory
        makeLayer("operational", [makeWidgetItem()]),
        makeLayer("anomaly"),  // empty + no advisory
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const layers = Array.from(
      document.querySelectorAll('[data-slot="pulse-layer"]'),
    )
    // Only operational renders; the others suppress entirely
    expect(layers.length).toBe(1)
    expect(layers[0].getAttribute("data-layer")).toBe("operational")
  })

  it("empty layer with advisory renders the advisory message", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal", [], "Nothing addressed to you right now."),
        makeLayer("operational", [makeWidgetItem()]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const advisory = document.querySelector(
      '[data-slot="pulse-layer-advisory"]',
    )
    expect(advisory?.textContent).toContain("Nothing addressed to you")
  })
})


// ── TestPulsePiece ─────────────────────────────────────────────────


describe("TestPulsePiece", () => {
  it("widget piece resolves via getWidgetRenderer + passes pulse_grid surface", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("operational"),
        makeLayer(
          "operational",
          [
            makeWidgetItem({
              component_key: "vault_schedule",
              variant_id: "detail",
              cols: 2,
              rows: 2,
            }),
          ],
        ),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const renderer = document.querySelector('[data-testid="mock-widget-renderer"]')
    expect(renderer).toBeInTheDocument()
    expect(renderer?.getAttribute("data-widget-id")).toBe("vault_schedule")
    expect(renderer?.getAttribute("data-variant-id")).toBe("detail")
    expect(renderer?.getAttribute("data-surface")).toBe("pulse_grid")
  })

  it("piece honors size hints via grid-column/row span styles", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational", [
          makeWidgetItem({ cols: 4, rows: 2, item_id: "widget:big" }),
        ]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const piece = document.querySelector(
      '[data-slot="pulse-piece"][data-item-id="widget:big"]',
    ) as HTMLElement
    expect(piece).toBeInTheDocument()
    expect(piece.style.gridColumn).toBe("span 4")
    expect(piece.style.gridRow).toBe("span 2")
  })

  it("stream piece renders AnomalyIntelligenceStream when stream exists in composition", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational"),
        makeLayer("anomaly", [makeStreamItem()]),
        makeLayer("activity"),
      ],
      intelligence_streams: [makeIntelligenceStream()],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    expect(
      document.querySelector('[data-slot="anomaly-intelligence-stream"]'),
    ).toBeInTheDocument()
  })

  it("stream piece renders nothing when corresponding stream missing from composition", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational"),
        makeLayer("anomaly", [makeStreamItem()]),
        makeLayer("activity"),
      ],
      intelligence_streams: [],  // stream item references missing stream
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    // PulsePiece wrapper still renders (has data-kind="stream"), but
    // the inner content is null
    const piece = document.querySelector(
      '[data-slot="pulse-piece"][data-kind="stream"]',
    )
    expect(piece).toBeInTheDocument()
    expect(
      piece?.querySelector('[data-slot="anomaly-intelligence-stream"]'),
    ).toBeNull()
  })

  it("piece data-component-key + data-layer attributes carry signal context", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational", [
          makeWidgetItem({ component_key: "vault_schedule" }),
        ]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const piece = document.querySelector('[data-slot="pulse-piece"]')
    expect(piece?.getAttribute("data-component-key")).toBe("vault_schedule")
    expect(piece?.getAttribute("data-layer")).toBe("operational")
  })
})


// ── TestAnomalyIntelligenceStream ──────────────────────────────────


describe("TestAnomalyIntelligenceStream", () => {
  it("renders synthesized text", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational"),
        makeLayer("anomaly", [makeStreamItem()]),
        makeLayer("activity"),
      ],
      intelligence_streams: [makeIntelligenceStream()],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const text = document.querySelector(
      '[data-slot="anomaly-intelligence-text"]',
    )
    expect(text?.textContent).toContain(
      "Hopkins invoice balance mismatch",
    )
  })

  it("renders title", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational"),
        makeLayer("anomaly", [makeStreamItem()]),
        makeLayer("activity"),
      ],
      intelligence_streams: [makeIntelligenceStream()],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const title = document.querySelector(
      '[data-slot="anomaly-intelligence-title"]',
    )
    expect(title?.textContent).toBe("Today's watch list")
  })

  it("referenced items render as clickable chips (top 5)", async () => {
    const stream = makeIntelligenceStream({
      referenced_items: Array.from({ length: 7 }, (_, i) => ({
        kind: "anomaly",
        entity_id: `a${i}`,
        label: `Anomaly ${i}`,
        href: null,
      })),
    })
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational"),
        makeLayer("anomaly", [makeStreamItem()]),
        makeLayer("activity"),
      ],
      intelligence_streams: [stream],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const chips = document.querySelectorAll(
      '[data-slot="anomaly-intelligence-reference-chip"]',
    )
    // Cap at 5 per the component's `.slice(0, 5)`
    expect(chips.length).toBe(5)
  })

  it("zero referenced items renders without chip list", async () => {
    const stream = makeIntelligenceStream({ referenced_items: [] })
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational"),
        makeLayer("anomaly", [makeStreamItem()]),
        makeLayer("activity"),
      ],
      intelligence_streams: [stream],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    expect(
      document.querySelector(
        '[data-slot="anomaly-intelligence-references"]',
      ),
    ).toBeNull()
  })
})


// ── TestSignalCollection ───────────────────────────────────────────


describe("TestSignalCollection", () => {
  it("dismiss button click fires recordDismiss with correct args", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational", [
          makeWidgetItem({
            item_id: "widget:vs",
            component_key: "vault_schedule",
          }),
        ]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
      metadata: {
        work_areas_used: ["Production Scheduling"],
        vertical_default_applied: false,
        time_of_day_signal: "morning",
      },
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const dismissBtn = document.querySelector(
      '[data-slot="pulse-piece-dismiss"]',
    ) as HTMLButtonElement
    fireEvent.click(dismissBtn)
    expect(mockRecordDismiss).toHaveBeenCalledWith(
      "vault_schedule",
      "operational",
      "morning",
      ["Production Scheduling"],
    )
  })

  it("after dismiss click, piece is removed from render", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational", [
          makeWidgetItem({ item_id: "widget:vs" }),
        ]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const dismissBtn = document.querySelector(
      '[data-slot="pulse-piece-dismiss"]',
    ) as HTMLButtonElement
    fireEvent.click(dismissBtn)
    // PulsePiece schedules an unmount via setTimeout(200ms) — wait
    // for the parent's dismissed-set update to remove it.
    await waitFor(
      () => {
        expect(
          document.querySelector(
            '[data-slot="pulse-piece"][data-item-id="widget:vs"]',
          ),
        ).toBeNull()
      },
      { timeout: 500 },
    )
  })

  it("dwell time signal is non-negative integer seconds", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational", [
          makeWidgetItem({
            item_id: "widget:vs",
            component_key: "vault_schedule",
          }),
        ]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const piece = document.querySelector(
      '[data-slot="pulse-piece"]',
    ) as HTMLElement
    // Synthesize a click on the piece's interior; the
    // onClickCapture handler reads the closest <a href> ancestor —
    // but the mock widget renderer doesn't render an <a>, so no
    // navigation signal fires. Construct an anchor inside the
    // piece for the test.
    const anchor = document.createElement("a")
    anchor.setAttribute("href", "/dispatch")
    piece.appendChild(anchor)
    fireEvent.click(anchor)
    // Verify the navigation signal fired with non-negative dwell
    expect(mockRecordNavigation).toHaveBeenCalled()
    const args = mockRecordNavigation.mock.calls[0]
    expect(args[0]).toBe("vault_schedule")  // from_component_key
    expect(args[1]).toBe("/dispatch")  // to_route
    expect(typeof args[2]).toBe("number")
    expect(args[2]).toBeGreaterThanOrEqual(0)
    expect(Number.isInteger(args[2])).toBe(true)
    expect(args[3]).toBe("operational")  // layer
  })
})


// ── TestFirstLoginBanner ───────────────────────────────────────────


describe("TestFirstLoginBanner", () => {
  it("banner renders when vertical_default_applied=true and onboarding-touch shouldShow=true", async () => {
    mockComposition = makeComposition({
      metadata: {
        work_areas_used: [],
        vertical_default_applied: true,
        time_of_day_signal: "morning",
      },
    })
    mockUseOnboardingTouch.mockReturnValue({
      shouldShow: true,
      dismiss: vi.fn(),
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    expect(
      document.querySelector('[data-slot="pulse-first-login-banner"]'),
    ).toBeInTheDocument()
  })

  it("banner suppressed when vertical_default_applied=false", async () => {
    mockComposition = makeComposition({
      metadata: {
        work_areas_used: ["Production Scheduling"],
        vertical_default_applied: false,
        time_of_day_signal: "morning",
      },
    })
    mockUseOnboardingTouch.mockReturnValue({
      shouldShow: true,
      dismiss: vi.fn(),
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    expect(
      document.querySelector('[data-slot="pulse-first-login-banner"]'),
    ).toBeNull()
  })

  it("banner suppressed when onboarding-touch shouldShow=false (already dismissed)", async () => {
    mockComposition = makeComposition({
      metadata: {
        work_areas_used: [],
        vertical_default_applied: true,
        time_of_day_signal: "morning",
      },
    })
    mockUseOnboardingTouch.mockReturnValue({
      shouldShow: false,
      dismiss: vi.fn(),
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    expect(
      document.querySelector('[data-slot="pulse-first-login-banner"]'),
    ).toBeNull()
  })

  it("banner CTA links to /onboarding/operator-profile", async () => {
    mockComposition = makeComposition({
      metadata: {
        work_areas_used: [],
        vertical_default_applied: true,
        time_of_day_signal: "morning",
      },
    })
    mockUseOnboardingTouch.mockReturnValue({
      shouldShow: true,
      dismiss: vi.fn(),
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    // base-ui's render={<Link to="..."/>} pattern merges the Link into the
    // Button — the rendered element is itself an <a> carrying the data-slot.
    // Either the data-slot element OR a descendant <a> may carry the href
    // depending on how render-prop merging resolves; check both.
    const cta = document.querySelector(
      '[data-slot="pulse-first-login-banner-cta"]',
    ) as HTMLElement | null
    const href =
      cta?.getAttribute("href") ??
      cta?.querySelector("a")?.getAttribute("href")
    expect(href).toBe("/onboarding/operator-profile")
  })

  it("Pulse content still renders below the banner", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational", [makeWidgetItem()]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
      metadata: {
        work_areas_used: [],
        vertical_default_applied: true,
        time_of_day_signal: "morning",
      },
    })
    mockUseOnboardingTouch.mockReturnValue({
      shouldShow: true,
      dismiss: vi.fn(),
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    expect(
      document.querySelector('[data-slot="pulse-first-login-banner"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="pulse-layer"][data-layer="operational"]',
      ),
    ).toBeInTheDocument()
  })
})


// ── TestVisualChrome (per §13.3.2 + §13.4.2) ───────────────────────


describe("TestVisualChrome", () => {
  it("operational layer carries brass-thread top-edge class (border-t border-accent)", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational", [makeWidgetItem()]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const opLayer = document.querySelector(
      '[data-slot="pulse-layer"][data-layer="operational"]',
    ) as HTMLElement
    // Brass-thread divider per §13.3.2 — Tailwind class includes
    // "border-t" + accent color via `border-accent/30`. The layer
    // applies these via the `_hasBrassThread` branch.
    expect(opLayer.className).toMatch(/border-t/)
    expect(opLayer.className).toMatch(/border-accent/)
  })

  it("non-operational layers do NOT carry the brass-thread divider", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal", [makeWidgetItem({ item_id: "widget:p" })]),
        makeLayer("operational"),
        makeLayer("anomaly", [makeWidgetItem({ item_id: "widget:a" })]),
        makeLayer("activity", [
          makeWidgetItem({ item_id: "widget:act" }),
        ]),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)

    for (const layerName of ["personal", "anomaly", "activity"]) {
      const el = document.querySelector(
        `[data-slot="pulse-layer"][data-layer="${layerName}"]`,
      ) as HTMLElement | null
      expect(el).toBeInTheDocument()
      expect(el!.className).not.toMatch(/border-t border-accent/)
    }
  })

  it("intelligence stream piece carries brass-thread accent (before:bg-accent class)", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational"),
        makeLayer("anomaly", [makeStreamItem()]),
        makeLayer("activity"),
      ],
      intelligence_streams: [makeIntelligenceStream()],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const stream = document.querySelector(
      '[data-slot="anomaly-intelligence-stream"]',
    ) as HTMLElement
    // Brass-thread accent at top edge per §13.4.2 — uses
    // ::before pseudo with bg-accent. We can't query CSS but we
    // can verify the class is present.
    expect(stream.className).toMatch(/before:bg-accent/)
    expect(stream.className).toMatch(/before:h-px/)
  })

  it("layer grid uses CSS Grid with auto-fit + auto-rows for tetris layout", async () => {
    mockComposition = makeComposition({
      layers: [
        makeLayer("personal"),
        makeLayer("operational", [makeWidgetItem()]),
        makeLayer("anomaly"),
        makeLayer("activity"),
      ],
    })
    const PulseSurface = await importPulseSurface()
    renderWithRouter(<PulseSurface />)
    const grid = document.querySelector(
      '[data-slot="pulse-layer-grid"]',
    ) as HTMLElement
    expect(grid).toBeInTheDocument()
    expect(grid.className).toMatch(/grid/)
    // Grid auto-fit columns + auto-rows per §13.3.1 breathing-room
    // composition rule
    expect(grid.className).toMatch(/auto-fit/)
    expect(grid.className).toMatch(/auto-rows/)
  })
})
