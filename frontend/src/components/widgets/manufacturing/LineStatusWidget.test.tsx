/**
 * LineStatusWidget — vitest unit tests (Phase W-3d Commit 2).
 *
 * Phase W-3d cross-line aggregator contract:
 *   • Brief + Detail variants — NO Glance per §12.10
 *   • Multi-line: renders one row per active line
 *   • Status indicator (on_track / behind / blocked / idle / unknown)
 *   • Mode badges (Production / Purchase / Hybrid)
 *   • Click-through navigation per row when navigation_target set
 *   • Empty state when no lines active
 */

import { render } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest"


// Mock useWidgetData
let mockResult: {
  data: LineStatusData | null
  isLoading: boolean
  error: string | null
} = { data: null, isLoading: false, error: null }
const mockRefresh = vi.fn()
const mockUseWidgetData = vi.fn((_url: string) => ({
  ...mockResult,
  refresh: mockRefresh,
  lastUpdated: null,
}))

vi.mock("../useWidgetData", () => ({
  useWidgetData: (url: string) => mockUseWidgetData(url),
}))


import { LineStatusWidget } from "./LineStatusWidget"


type LineStatus = "on_track" | "behind" | "blocked" | "idle" | "unknown"

interface LineHealthRow {
  line_key: string
  display_name: string
  operating_mode: string
  status: LineStatus
  headline: string
  metrics: Record<string, unknown>
  navigation_target: string | null
}

interface LineStatusData {
  date: string
  lines: LineHealthRow[]
  total_active_lines: number
  any_attention_needed: boolean
}


function renderWidget(props: Parameters<typeof LineStatusWidget>[0]) {
  return render(
    <MemoryRouter>
      <LineStatusWidget {...props} />
    </MemoryRouter>,
  )
}


function makeData(
  lines: Partial<LineHealthRow>[] = [],
): LineStatusData {
  const fullLines: LineHealthRow[] = lines.map((p, i) => ({
    line_key: `line-${i}`,
    display_name: `Line ${i}`,
    operating_mode: "production",
    status: "on_track",
    headline: "0 today",
    metrics: {},
    navigation_target: "/dispatch",
    ...p,
  }))
  return {
    date: "2026-04-27",
    lines: fullLines,
    total_active_lines: fullLines.length,
    any_attention_needed: fullLines.some((ln) =>
      ["behind", "blocked"].includes(ln.status),
    ),
  }
}


beforeEach(() => {
  mockResult = { data: null, isLoading: false, error: null }
  mockUseWidgetData.mockClear()
  mockRefresh.mockClear()
})


afterEach(() => {
  vi.clearAllMocks()
})


// ── Endpoint URL ────────────────────────────────────────────────────


describe("LineStatusWidget — endpoint", () => {
  it("calls /widget-data/line-status", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({})
    expect(mockUseWidgetData).toHaveBeenCalledWith(
      "/widget-data/line-status",
    )
  })
})


// ── Brief variant ──────────────────────────────────────────────────


describe("LineStatusWidget — Brief variant", () => {
  it("default variant is Brief", () => {
    mockResult = {
      data: makeData([{ line_key: "vault", display_name: "Burial vault" }]),
      isLoading: false,
      error: null,
    }
    renderWidget({})
    expect(
      document.querySelector(
        '[data-slot="line-status-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })

  it("Brief renders one row per active line", () => {
    mockResult = {
      data: makeData([
        {
          line_key: "vault",
          display_name: "Burial vault",
          status: "on_track",
        },
        {
          line_key: "redi_rock",
          display_name: "Redi-Rock",
          status: "unknown",
        },
        {
          line_key: "urn_sales",
          display_name: "Urn sales",
          status: "idle",
        },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const rows = document.querySelectorAll(
      '[data-slot="line-status-row"]',
    )
    expect(rows.length).toBe(3)
    const lineKeys = Array.from(rows).map((r) =>
      r.getAttribute("data-line-key"),
    )
    expect(lineKeys).toEqual(["vault", "redi_rock", "urn_sales"])
  })

  it("Brief shows status data attribute per row", () => {
    mockResult = {
      data: makeData([
        { line_key: "vault", status: "behind" },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const row = document.querySelector(
      '[data-slot="line-status-row"][data-line-key="vault"]',
    )
    expect(row?.getAttribute("data-status")).toBe("behind")
  })

  it("Brief reflects attention needed when any line behind", () => {
    mockResult = {
      data: makeData([
        { line_key: "vault", status: "behind" },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const tablet = document.querySelector(
      '[data-slot="line-status-widget"][data-variant="brief"]',
    )
    expect(tablet?.getAttribute("data-attention")).toBe("true")
  })

  it("Brief renders empty state when no lines", () => {
    mockResult = {
      data: makeData([]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const empty = document.querySelector('[data-slot="line-status-empty"]')
    expect(empty?.textContent).toContain("No product lines active")
  })

  it("Brief renders headline per row", () => {
    mockResult = {
      data: makeData([
        {
          line_key: "vault",
          display_name: "Burial vault",
          status: "on_track",
          headline: "8 pours today",
        },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const row = document.querySelector(
      '[data-slot="line-status-row"][data-line-key="vault"]',
    )
    expect(row?.textContent).toContain("8 pours today")
  })

  it("Brief shows navigation CTA when target present", () => {
    mockResult = {
      data: makeData([
        {
          line_key: "vault",
          navigation_target: "/dispatch",
        },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    expect(
      document.querySelector('[data-slot="line-status-row-cta"]'),
    ).toBeInTheDocument()
  })

  it("Brief hides CTA when navigation_target null (placeholder rows)", () => {
    mockResult = {
      data: makeData([
        {
          line_key: "redi_rock",
          status: "unknown",
          navigation_target: null,
        },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    expect(
      document.querySelector('[data-slot="line-status-row-cta"]'),
    ).toBeNull()
  })

  it("Brief renders error state when error set", () => {
    mockResult = {
      data: null,
      isLoading: false,
      error: "Network error",
    }
    renderWidget({ variant_id: "brief" })
    const err = document.querySelector('[data-slot="line-status-error"]')
    expect(err?.textContent).toContain("Network error")
  })
})


// ── Detail variant ─────────────────────────────────────────────────


describe("LineStatusWidget — Detail variant", () => {
  it("Detail renders mode badges per row", () => {
    mockResult = {
      data: makeData([
        {
          line_key: "vault",
          display_name: "Burial vault",
          operating_mode: "production",
        },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    const badge = document.querySelector(
      '[data-slot="line-status-mode-badge"]',
    )
    expect(badge).toBeInTheDocument()
    expect(badge?.textContent).toBe("Production")
  })

  it("Detail surfaces metrics grid when populated", () => {
    mockResult = {
      data: makeData([
        {
          line_key: "vault",
          display_name: "Burial vault",
          status: "on_track",
          metrics: {
            production_today: 8,
            production_assigned: 7,
            production_unassigned: 1,
          },
        },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    const metrics = document.querySelector(
      '[data-slot="line-status-metrics"]',
    )
    expect(metrics).toBeInTheDocument()
    expect(metrics?.textContent).toContain("Today (pour)")
    expect(metrics?.textContent).toContain("8")
  })

  it("Detail hides metrics block when all zero", () => {
    mockResult = {
      data: makeData([
        {
          line_key: "redi_rock",
          status: "unknown",
          metrics: {},
        },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    const metrics = document.querySelector(
      '[data-slot="line-status-metrics"]',
    )
    expect(metrics).toBeNull()
  })

  it("Detail click-through CTA targets navigation_target", () => {
    mockResult = {
      data: makeData([
        {
          line_key: "vault",
          navigation_target: "/dispatch",
        },
      ]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    const cta = document.querySelector(
      '[data-slot="line-status-row-cta"]',
    )
    expect(cta?.textContent).toContain("Open schedule")
  })
})


// ── Variant fallback discipline ────────────────────────────────────


describe("LineStatusWidget — variant fallback", () => {
  it("glance variant_id falls back to Brief (no Glance per §12.10)", () => {
    mockResult = {
      data: makeData([{ line_key: "vault" }]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })
    // Falls back to Brief
    expect(
      document.querySelector(
        '[data-slot="line-status-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })

  it("deep variant_id falls back to Brief (no Deep declared)", () => {
    mockResult = {
      data: makeData([{ line_key: "vault" }]),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "deep" })
    expect(
      document.querySelector(
        '[data-slot="line-status-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })
})
