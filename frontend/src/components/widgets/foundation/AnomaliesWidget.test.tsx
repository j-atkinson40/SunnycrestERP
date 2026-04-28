/**
 * AnomaliesWidget — vitest unit tests.
 *
 * Phase W-3a contract:
 *   • Brief + Detail variants (NO Glance per §12.10)
 *   • Severity colors map to locked tokens
 *   • Acknowledge action calls correct endpoint + refreshes
 *   • Detail filter chips toggle severity visibility
 *   • Empty state ("All clear") + sage check icon
 *   • Click row navigates to investigation
 *   • Loading + error states
 */

import { render, fireEvent, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"


let mockData: unknown = null
let mockIsLoading = false
let mockError: string | null = null
const mockRefresh = vi.fn()


vi.mock("@/components/widgets/useWidgetData", () => ({
  useWidgetData: () => ({
    data: mockData,
    isLoading: mockIsLoading,
    error: mockError,
    refresh: mockRefresh,
    lastUpdated: new Date(),
  }),
}))


// Mock apiClient.post for the acknowledge action
const mockApiPost = vi.fn(
  (..._args: unknown[]) => Promise.resolve({ data: {} }),
)
vi.mock("@/lib/api-client", () => ({
  default: {
    post: (url: string, body?: unknown) => mockApiPost(url, body),
  },
}))


const mockNavigate = vi.fn()
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  )
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})


import { AnomaliesWidget } from "./AnomaliesWidget"


function makeAnomaly(overrides: Record<string, unknown> = {}) {
  return {
    id: `an-${Math.random().toString(36).slice(2, 8)}`,
    severity: "warning",
    anomaly_type: "balance_mismatch",
    description: "Test anomaly description",
    entity_type: null,
    entity_id: null,
    amount: null,
    source_agent_job_id: "job-1",
    source_agent_type: "month_end_close",
    created_at: new Date().toISOString(),
    resolved: false,
    resolved_by: null,
    resolved_at: null,
    resolution_note: null,
    ...overrides,
  }
}


function renderWidget(props: Parameters<typeof AnomaliesWidget>[0]) {
  return render(
    <MemoryRouter>
      <AnomaliesWidget {...props} />
    </MemoryRouter>,
  )
}


beforeEach(() => {
  mockData = null
  mockIsLoading = false
  mockError = null
  mockRefresh.mockClear()
  mockApiPost.mockClear()
  mockApiPost.mockImplementation(() => Promise.resolve({ data: {} }))
  mockNavigate.mockClear()
})


afterEach(() => {
  vi.clearAllMocks()
})


// ── Brief variant ──────────────────────────────────────────────────


describe("AnomaliesWidget — Brief variant (default)", () => {
  it("renders Brief by default (no variant_id)", () => {
    mockData = {
      anomalies: [makeAnomaly()],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({})

    expect(
      document.querySelector('[data-slot="anomalies-widget"][data-variant="brief"]'),
    ).toBeInTheDocument()
  })

  it("Brief renders surface=spaces_pin as Brief (NO Glance variant per §12.10)", () => {
    mockData = {
      anomalies: [makeAnomaly()],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({ surface: "spaces_pin" })

    // Falls through to Brief — no Glance variant exists
    expect(
      document.querySelector(
        '[data-slot="anomalies-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="anomalies-widget"][data-variant="glance"]',
      ),
    ).toBeNull()
  })

  it("Brief in pulse_grid renders three §13.4.1 density tiers with canonical class names", () => {
    // Phase W-4a Step 6 Commit 2 — supersedes Step 2.D's single-tier
    // compaction. Pulse-surface Brief opts INTO §13.4.1 density tiers:
    // three nested density variants (default / compact /
    // ultra-compact) render in DOM simultaneously; @container query
    // CSS in pulse-density.css dispatches which one displays at each
    // cell-height range. jsdom doesn't compute @container matches, so
    // we assert STRUCTURAL presence + content shape per tier.
    mockData = {
      anomalies: [
        makeAnomaly({ id: "1" }),
        makeAnomaly({ id: "2" }),
        makeAnomaly({ id: "3" }),
      ],
      total_unresolved: 264,
      critical_count: 12,
    }
    renderWidget({ surface: "pulse_grid" })

    const widget = document.querySelector(
      '[data-slot="anomalies-widget"][data-variant="brief"]',
    )
    expect(widget?.getAttribute("data-surface")).toBe("pulse_grid")
    // All three density tiers render with canonical class names.
    const defaultTier = document.querySelector(
      ".anomalies-widget-pulse-default",
    )
    const compactTier = document.querySelector(
      ".anomalies-widget-pulse-compact",
    )
    const ultraTier = document.querySelector(
      ".anomalies-widget-pulse-ultra-compact",
    )
    expect(defaultTier).toBeInTheDocument()
    expect(compactTier).toBeInTheDocument()
    expect(ultraTier).toBeInTheDocument()
    // Default tier contains the full body (rows + count breakdown).
    expect(defaultTier?.textContent).toContain("12 critical")
    expect(defaultTier?.querySelector('[data-slot="anomalies-widget-body"]'))
      .toBeInTheDocument()
    // Compact tier contains the "Investigate N →" footer copy.
    expect(compactTier?.textContent).toContain("Investigate 264 →")
    // Ultra-compact tier renders the single-line dense readout.
    expect(ultraTier?.textContent).toContain("264 unresolved")
    expect(ultraTier?.textContent).toContain("12 critical")
  })

  it("Brief in dashboard_grid renders full 4-row body (no compaction)", () => {
    // Dashboard surface gets the rich rendering — same widget,
    // surface-specific compaction.
    mockData = {
      anomalies: [
        makeAnomaly({ id: "1" }),
        makeAnomaly({ id: "2" }),
        makeAnomaly({ id: "3" }),
      ],
      total_unresolved: 264,
      critical_count: 12,
    }
    renderWidget({ surface: "dashboard_grid" } as never)
    expect(
      document.querySelector('[data-slot="anomalies-widget-body"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="anomalies-widget-rows"]'),
    ).toBeInTheDocument()
    // Dashboard footer carries "View all" copy.
    const footer = document.querySelector(
      '[data-slot="anomalies-widget-footer"]',
    )
    expect(footer?.textContent).toContain("View all 264 →")
  })

  it("Brief renders top 4 rows", () => {
    mockData = {
      anomalies: [
        makeAnomaly({ id: "1" }),
        makeAnomaly({ id: "2" }),
        makeAnomaly({ id: "3" }),
        makeAnomaly({ id: "4" }),
        makeAnomaly({ id: "5" }),
        makeAnomaly({ id: "6" }),
      ],
      total_unresolved: 6,
      critical_count: 0,
    }
    renderWidget({})

    const rows = document.querySelectorAll(
      '[data-slot="anomalies-widget-row"]',
    )
    expect(rows.length).toBe(4)
  })

  it("Brief shows critical count + total when critical present", () => {
    mockData = {
      anomalies: [makeAnomaly({ severity: "critical" })],
      total_unresolved: 5,
      critical_count: 2,
    }
    renderWidget({})

    const header = document.querySelector(
      '[data-slot="anomalies-widget-header"]',
    )
    expect(header?.textContent).toMatch(/2 critical/)
    expect(header?.textContent).toMatch(/5 total/)
  })

  it("Brief shows 'All clear' empty state with sage check icon", () => {
    mockData = {
      anomalies: [],
      total_unresolved: 0,
      critical_count: 0,
    }
    renderWidget({})

    const empty = document.querySelector(
      '[data-slot="anomalies-widget-empty"]',
    )
    expect(empty).toBeInTheDocument()
    expect(empty?.textContent).toMatch(/All clear/)
  })

  it("Brief View All footer shows when total > displayed", () => {
    mockData = {
      anomalies: Array.from({ length: 4 }, (_, i) =>
        makeAnomaly({ id: `a${i}` }),
      ),
      total_unresolved: 12,
      critical_count: 0,
    }
    renderWidget({})

    const footer = document.querySelector(
      '[data-slot="anomalies-widget-view-all"]',
    )
    expect(footer?.textContent).toMatch(/View all 12/)
  })

  it("Brief footer hidden when all anomalies fit", () => {
    mockData = {
      anomalies: [makeAnomaly()],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({})

    expect(
      document.querySelector('[data-slot="anomalies-widget-view-all"]'),
    ).toBeNull()
  })

  it("Brief row click navigates to investigation target", () => {
    mockData = {
      anomalies: [
        makeAnomaly({
          id: "an-1",
          source_agent_job_id: "job-abc",
        }),
      ],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({})

    const investigateBtn = document.querySelector(
      '[data-slot="anomalies-widget-row-investigate"]',
    ) as HTMLElement
    fireEvent.click(investigateBtn)
    expect(mockNavigate).toHaveBeenCalledWith("/admin/agents/jobs/job-abc")
  })

  it("Brief acknowledge button calls correct endpoint + refreshes", async () => {
    mockData = {
      anomalies: [makeAnomaly({ id: "an-ack" })],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({})

    const ackBtn = document.querySelector(
      '[data-slot="anomalies-widget-row-acknowledge"]',
    ) as HTMLElement
    fireEvent.click(ackBtn)

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        "/widget-data/anomalies/an-ack/acknowledge",
        {},
      )
    })
    await waitFor(() => {
      expect(mockRefresh).toHaveBeenCalled()
    })
  })

  it("Brief acknowledge disabled when anomaly already resolved", () => {
    mockData = {
      anomalies: [makeAnomaly({ resolved: true })],
      total_unresolved: 0,
      critical_count: 0,
    }
    renderWidget({})

    const ackBtn = document.querySelector(
      '[data-slot="anomalies-widget-row-acknowledge"]',
    ) as HTMLButtonElement
    expect(ackBtn.disabled).toBe(true)
  })

  it("Brief error state when fetch fails", () => {
    mockError = "Network error"
    renderWidget({})

    expect(
      document.querySelector('[data-slot="anomalies-widget-error"]'),
    ).toBeInTheDocument()
  })
})


// ── Severity colors ────────────────────────────────────────────────


describe("AnomaliesWidget — severity color tokens", () => {
  it("critical row carries border-l-status-error class", () => {
    mockData = {
      anomalies: [makeAnomaly({ severity: "critical", id: "crit" })],
      total_unresolved: 1,
      critical_count: 1,
    }
    renderWidget({})

    const row = document.querySelector(
      '[data-anomaly-id="crit"]',
    ) as HTMLElement
    expect(row.className).toMatch(/border-l-status-error/)
  })

  it("warning row carries border-l-status-warning class", () => {
    mockData = {
      anomalies: [makeAnomaly({ severity: "warning", id: "warn" })],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({})

    const row = document.querySelector(
      '[data-anomaly-id="warn"]',
    ) as HTMLElement
    expect(row.className).toMatch(/border-l-status-warning/)
  })

  it("info row carries border-l-status-info class", () => {
    mockData = {
      anomalies: [makeAnomaly({ severity: "info", id: "inf" })],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({})

    const row = document.querySelector(
      '[data-anomaly-id="inf"]',
    ) as HTMLElement
    expect(row.className).toMatch(/border-l-status-info/)
  })

  it("data-severity attribute matches anomaly severity", () => {
    mockData = {
      anomalies: [
        makeAnomaly({ severity: "critical", id: "1" }),
        makeAnomaly({ severity: "warning", id: "2" }),
        makeAnomaly({ severity: "info", id: "3" }),
      ],
      total_unresolved: 3,
      critical_count: 1,
    }
    renderWidget({})

    expect(
      document
        .querySelector('[data-anomaly-id="1"]')
        ?.getAttribute("data-severity"),
    ).toBe("critical")
    expect(
      document
        .querySelector('[data-anomaly-id="2"]')
        ?.getAttribute("data-severity"),
    ).toBe("warning")
    expect(
      document
        .querySelector('[data-anomaly-id="3"]')
        ?.getAttribute("data-severity"),
    ).toBe("info")
  })
})


// ── Detail variant ──────────────────────────────────────────────────


describe("AnomaliesWidget — Detail variant", () => {
  it("renders Detail when variant_id=detail", () => {
    mockData = {
      anomalies: [makeAnomaly()],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({ variant_id: "detail" })

    expect(
      document.querySelector(
        '[data-slot="anomalies-widget"][data-variant="detail"]',
      ),
    ).toBeInTheDocument()
  })

  it("Detail renders 4 filter chips (All / Critical / Warning / Info)", () => {
    mockData = {
      anomalies: [makeAnomaly()],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({ variant_id: "detail" })

    const chips = document.querySelectorAll(
      '[data-slot="anomalies-widget-filter-chip"]',
    )
    expect(chips.length).toBe(4)
    const keys = Array.from(chips).map((c) =>
      c.getAttribute("data-filter-key"),
    )
    expect(keys).toEqual(["all", "critical", "warning", "info"])
  })

  it("Detail Critical filter shows only critical anomalies", () => {
    mockData = {
      anomalies: [
        makeAnomaly({ severity: "critical", id: "c1" }),
        makeAnomaly({ severity: "warning", id: "w1" }),
        makeAnomaly({ severity: "info", id: "i1" }),
        makeAnomaly({ severity: "critical", id: "c2" }),
      ],
      total_unresolved: 4,
      critical_count: 2,
    }
    renderWidget({ variant_id: "detail" })

    const criticalChip = document.querySelector(
      '[data-filter-key="critical"]',
    ) as HTMLElement
    fireEvent.click(criticalChip)

    const rows = document.querySelectorAll(
      '[data-slot="anomalies-widget-row"]',
    )
    expect(rows.length).toBe(2)
    Array.from(rows).forEach((r) => {
      expect(r.getAttribute("data-severity")).toBe("critical")
    })
  })

  it("Detail filter chip aria-selected reflects active state", () => {
    mockData = {
      anomalies: [],
      total_unresolved: 0,
      critical_count: 0,
    }
    renderWidget({ variant_id: "detail" })

    const allChip = document.querySelector(
      '[data-filter-key="all"]',
    ) as HTMLElement
    expect(allChip.getAttribute("aria-selected")).toBe("true")

    const criticalChip = document.querySelector(
      '[data-filter-key="critical"]',
    ) as HTMLElement
    fireEvent.click(criticalChip)
    expect(criticalChip.getAttribute("aria-selected")).toBe("true")
    expect(allChip.getAttribute("aria-selected")).toBe("false")
  })

  it("Detail empty when filter excludes all anomalies", () => {
    mockData = {
      anomalies: [makeAnomaly({ severity: "warning" })],
      total_unresolved: 1,
      critical_count: 0,
    }
    renderWidget({ variant_id: "detail" })

    const criticalChip = document.querySelector(
      '[data-filter-key="critical"]',
    ) as HTMLElement
    fireEvent.click(criticalChip)

    const empty = document.querySelector(
      '[data-slot="anomalies-widget-empty"]',
    )
    expect(empty?.textContent).toMatch(/No anomalies in this filter/)
  })

  it("Detail empty when no anomalies at all (All clear)", () => {
    mockData = {
      anomalies: [],
      total_unresolved: 0,
      critical_count: 0,
    }
    renderWidget({ variant_id: "detail" })

    const empty = document.querySelector(
      '[data-slot="anomalies-widget-empty"]',
    )
    expect(empty?.textContent).toMatch(/All clear/)
  })
})
