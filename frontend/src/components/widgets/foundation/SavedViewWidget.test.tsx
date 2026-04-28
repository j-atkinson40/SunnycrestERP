/**
 * SavedViewWidget — vitest unit tests (Phase W-3b).
 *
 * Phase W-3b contract:
 *   • Brief + Detail + Deep variants (NO Glance per §12.10)
 *   • Config-driven via `config.view_id` — empty config renders
 *     empty-state CTA pointing to /saved-views
 *   • Reuses V-1c SavedViewWidget as inner renderer
 *   • Surface defaulting: variant_id="detail" when missing/glance
 */

import { render, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"


// Mock the V-1c SavedViewWidget so we don't pull recharts + entire
// saved-view stack into a unit test. We only verify the wrapper
// dispatches correctly.
const mockV1cRendered = vi.fn()
vi.mock("@/components/saved-views/SavedViewWidget", () => ({
  SavedViewWidget: (props: { viewId: string; showHeader?: boolean }) => {
    mockV1cRendered(props)
    return (
      <div
        data-testid="v1c-saved-view-widget"
        data-view-id={props.viewId}
        data-show-header={props.showHeader ? "true" : "false"}
      >
        v1c stub for {props.viewId}
      </div>
    )
  },
}))


import { SavedViewWidget } from "./SavedViewWidget"


function renderWidget(props: Parameters<typeof SavedViewWidget>[0]) {
  return render(
    <MemoryRouter>
      <SavedViewWidget {...props} />
    </MemoryRouter>,
  )
}


beforeEach(() => {
  mockV1cRendered.mockClear()
})


afterEach(() => {
  vi.clearAllMocks()
})


// ── Empty state ─────────────────────────────────────────────────────


describe("SavedViewWidget — empty state (no config)", () => {
  it("renders empty state when config undefined", () => {
    renderWidget({})

    expect(
      document.querySelector('[data-slot="saved-view-widget-empty"]'),
    ).toBeInTheDocument()
    // V-1c widget should NOT render
    expect(
      document.querySelector('[data-testid="v1c-saved-view-widget"]'),
    ).toBeNull()
  })

  it("renders empty state when config has no view_id", () => {
    renderWidget({ config: {} })

    expect(
      document.querySelector('[data-slot="saved-view-widget-empty"]'),
    ).toBeInTheDocument()
  })

  it("renders empty state when view_id is empty string", () => {
    renderWidget({ config: { view_id: "" } })

    expect(
      document.querySelector('[data-slot="saved-view-widget-empty"]'),
    ).toBeInTheDocument()
  })

  it("renders empty state when view_id is non-string type", () => {
    // Defensive: config could carry malformed data from JSONB
    renderWidget({ config: { view_id: 123 as unknown as string } })

    expect(
      document.querySelector('[data-slot="saved-view-widget-empty"]'),
    ).toBeInTheDocument()
  })

  it("empty state CTA links to /saved-views library", () => {
    renderWidget({})

    const cta = document.querySelector(
      '[data-slot="saved-view-widget-empty-cta"]',
    ) as HTMLAnchorElement
    expect(cta).toBeInTheDocument()
    expect(cta?.getAttribute("href")).toBe("/saved-views")
    expect(cta?.textContent).toMatch(/Open saved views library/)
  })

  it("empty state copy is helpful (not just 'No data')", () => {
    renderWidget({})
    const empty = document.querySelector(
      '[data-slot="saved-view-widget-empty"]',
    )
    expect(empty?.textContent).toMatch(/No saved view configured/)
    expect(empty?.textContent).toMatch(/Pick a saved view from the library/)
  })
})


// ── Configured rendering ────────────────────────────────────────────


describe("SavedViewWidget — variants with view_id", () => {
  const viewId = "view-abc-123"

  it("Brief variant renders V-1c with showHeader=false", () => {
    renderWidget({
      variant_id: "brief",
      config: { view_id: viewId },
    })

    const stub = document.querySelector(
      '[data-testid="v1c-saved-view-widget"]',
    )
    expect(stub).toBeInTheDocument()
    expect(stub?.getAttribute("data-view-id")).toBe(viewId)
    expect(stub?.getAttribute("data-show-header")).toBe("false")

    expect(mockV1cRendered).toHaveBeenCalledWith({
      viewId,
      showHeader: false,
    })

    // Wrapper data-variant attribute
    expect(
      document.querySelector(
        '[data-slot="saved-view-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })

  it("Detail variant renders V-1c with showHeader=true", () => {
    renderWidget({
      variant_id: "detail",
      config: { view_id: viewId },
    })

    const stub = document.querySelector(
      '[data-testid="v1c-saved-view-widget"]',
    )
    expect(stub?.getAttribute("data-show-header")).toBe("true")
    expect(
      document.querySelector(
        '[data-slot="saved-view-widget"][data-variant="detail"]',
      ),
    ).toBeInTheDocument()
  })

  it("Deep variant renders V-1c with showHeader=true", () => {
    renderWidget({
      variant_id: "deep",
      config: { view_id: viewId },
    })

    expect(
      document.querySelector(
        '[data-slot="saved-view-widget"][data-variant="deep"]',
      ),
    ).toBeInTheDocument()
    expect(mockV1cRendered).toHaveBeenCalledWith({
      viewId,
      showHeader: true,
    })
  })

  it("default variant (no variant_id) falls back to Detail", () => {
    renderWidget({ config: { view_id: viewId } })

    expect(
      document.querySelector(
        '[data-slot="saved-view-widget"][data-variant="detail"]',
      ),
    ).toBeInTheDocument()
  })

  it("Glance variant fallback (defensive — saved_view declares no Glance) renders Detail", () => {
    // saved_view's WidgetDefinition declares no Glance variant. The
    // dispatcher's defensive fallback renders Detail when Glance is
    // somehow requested (e.g., legacy layout, misconfigured pin).
    renderWidget({
      variant_id: "glance",
      config: { view_id: viewId },
    })

    expect(
      document.querySelector(
        '[data-slot="saved-view-widget"][data-variant="detail"]',
      ),
    ).toBeInTheDocument()
  })
})


// ── Surface awareness ───────────────────────────────────────────────


describe("SavedViewWidget — surface awareness", () => {
  it("surface=spaces_pin still renders empty/Detail (defensive — server filter rejects pinning)", () => {
    // saved_view's supported_surfaces excludes spaces_pin. The Phase
    // W-2 add_pin check rejects sidebar pinning server-side. If the
    // dispatch somehow reaches this widget on spaces_pin (legacy data,
    // race), it shouldn't crash — it falls through to standard
    // empty/Detail rendering.
    renderWidget({
      surface: "spaces_pin",
      config: { view_id: "view-x" },
    })

    // Renders Detail (default fallback) rather than crashing
    expect(
      document.querySelector('[data-slot="saved-view-widget"]'),
    ).toBeInTheDocument()
  })

  it("focus_canvas surface renders Detail with full V-1c chrome", () => {
    renderWidget({
      surface: "focus_canvas",
      variant_id: "detail",
      config: { view_id: "view-x" },
    })

    expect(mockV1cRendered).toHaveBeenCalledWith({
      viewId: "view-x",
      showHeader: true,
    })
  })
})


// ── Config plumbing regression ─────────────────────────────────────


describe("SavedViewWidget — config plumbing (Phase W-3b Commit 0 dependency)", () => {
  it("widget reads view_id from props.config — config flow works end-to-end", () => {
    // This test is the load-bearing verification for Commit 0's
    // widget config plumbing fix. saved_view widget is the FIRST
    // widget that depends on config; if Commit 0's plumbing broke,
    // this test fails.
    renderWidget({
      variant_id: "detail",
      surface: "focus_canvas",
      config: { view_id: "load-bearing-view-id" },
    })

    expect(mockV1cRendered).toHaveBeenCalledWith({
      viewId: "load-bearing-view-id",
      showHeader: true,
    })
  })
})
