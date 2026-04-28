/**
 * VaultScheduleWidget — vitest unit tests (Phase W-3d Commit 1).
 *
 * Phase W-3d contract:
 *   • Glance + Brief + Detail + Deep variants per §12.10
 *   • Mode-aware rendering: production / purchase / hybrid
 *   • Workspace-core widget per §12.6 — same data as scheduling Focus
 *   • Bounded edits per §12.6a — view + click-through to Focus
 *   • Empty states for: no vault enabled, vault enabled with no work
 *   • Cards enrich Delivery rows with SalesOrder context (deceased,
 *     etc.) at render time
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


// Mock the useWidgetData hook — drives all variant rendering.
let mockResult: {
  data: VaultScheduleData | null
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


import { VaultScheduleWidget } from "./VaultScheduleWidget"


type OperatingMode = "production" | "purchase" | "hybrid"

interface VaultScheduleData {
  date: string
  operating_mode: OperatingMode | null
  production: {
    deliveries: Array<{
      delivery_id: string
      order_id: string | null
      deceased_name: string | null
      customer_id: string | null
      primary_assignee_id: string | null
      helper_user_id: string | null
      status: string
      driver_start_time: string | null
      service_time: string | null
      service_location: string | null
      eta: string | null
      hole_dug_status: string
      delivery_address: string | null
      attached_ancillary_count: number
      priority: string
    }>
    total_count: number
    unassigned_count: number
    assigned_count: number
    driver_count: number
  } | null
  purchase: {
    transfers: Array<{
      transfer_id: string
      transfer_number: string
      status: string
      service_date: string | null
      deceased_name: string | null
      funeral_home_name: string | null
      cemetery_name: string | null
      cemetery_city: string | null
      cemetery_state: string | null
      transfer_items: unknown
      home_tenant_id: string | null
    }>
    total_count: number
    by_status: Record<string, number>
  } | null
  primary_navigation_target: string | null
  is_vault_enabled: boolean
}


function renderWidget(props: Parameters<typeof VaultScheduleWidget>[0]) {
  return render(
    <MemoryRouter>
      <VaultScheduleWidget {...props} />
    </MemoryRouter>,
  )
}


function makeProductionData(
  overrides: Partial<VaultScheduleData> = {},
): VaultScheduleData {
  return {
    date: "2026-04-27",
    operating_mode: "production",
    production: {
      deliveries: [
        {
          delivery_id: "d-1",
          order_id: "o-1",
          deceased_name: "John Smith",
          customer_id: "c-1",
          primary_assignee_id: "u-1",
          helper_user_id: null,
          status: "scheduled",
          driver_start_time: "09:00:00",
          service_time: null,
          service_location: "graveside",
          eta: null,
          hole_dug_status: "yes",
          delivery_address: "123 Main St",
          attached_ancillary_count: 0,
          priority: "normal",
        },
        {
          delivery_id: "d-2",
          order_id: "o-2",
          deceased_name: "Jane Doe",
          customer_id: "c-2",
          primary_assignee_id: null,
          helper_user_id: null,
          status: "pending",
          driver_start_time: null,
          service_time: null,
          service_location: null,
          eta: null,
          hole_dug_status: "unknown",
          delivery_address: null,
          attached_ancillary_count: 2,
          priority: "normal",
        },
      ],
      total_count: 2,
      unassigned_count: 1,
      assigned_count: 1,
      driver_count: 1,
    },
    purchase: null,
    primary_navigation_target: "/dispatch",
    is_vault_enabled: true,
    ...overrides,
  }
}


function makePurchaseData(): VaultScheduleData {
  return {
    date: "2026-04-27",
    operating_mode: "purchase",
    production: null,
    purchase: {
      transfers: [
        {
          transfer_id: "t-1",
          transfer_number: "LT-2026-001",
          status: "accepted",
          service_date: "2026-04-29",
          deceased_name: "Brown Family",
          funeral_home_name: "Hopkins FH",
          cemetery_name: "Oakwood",
          cemetery_city: "Auburn",
          cemetery_state: "NY",
          transfer_items: [],
          home_tenant_id: "supplier-1",
        },
      ],
      total_count: 1,
      by_status: { accepted: 1 },
    },
    primary_navigation_target: "/licensee-transfers/incoming",
    is_vault_enabled: true,
  }
}


function makeHybridData(): VaultScheduleData {
  return {
    date: "2026-04-27",
    operating_mode: "hybrid",
    production: makeProductionData().production,
    purchase: makePurchaseData().purchase,
    primary_navigation_target: "/dispatch",
    is_vault_enabled: true,
  }
}


function makeDisabledData(): VaultScheduleData {
  return {
    date: "2026-04-27",
    operating_mode: null,
    production: null,
    purchase: null,
    primary_navigation_target: null,
    is_vault_enabled: false,
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


// ── Config plumbing — target_date ───────────────────────────────────


describe("VaultScheduleWidget — target_date config", () => {
  it("calls /widget-data/vault-schedule without param when no config", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({})
    expect(mockUseWidgetData).toHaveBeenCalledWith(
      "/widget-data/vault-schedule",
    )
  })

  it("appends target_date query param when config provides it", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ config: { target_date: "2026-05-01" } })
    expect(mockUseWidgetData).toHaveBeenCalledWith(
      "/widget-data/vault-schedule?target_date=2026-05-01",
    )
  })
})


// ── Glance variant ──────────────────────────────────────────────────


describe("VaultScheduleWidget — Glance variant", () => {
  it("renders Glance with mode + delivery count", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })

    const tablet = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="glance"]',
    )
    expect(tablet).toBeInTheDocument()
    expect(tablet?.getAttribute("data-mode")).toBe("production")
    expect(tablet?.textContent).toContain("2")
  })

  it("Glance shows unassigned dot when production has unassigned deliveries", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })
    expect(
      document.querySelector('[data-slot="vault-schedule-unassigned-dot"]'),
    ).toBeInTheDocument()
  })

  it("Glance hides unassigned dot when all assigned", () => {
    const data = makeProductionData()
    data.production!.unassigned_count = 0
    mockResult = { data, isLoading: false, error: null }
    renderWidget({ variant_id: "glance" })
    expect(
      document.querySelector('[data-slot="vault-schedule-unassigned-dot"]'),
    ).toBeNull()
  })

  it("Glance reports 'incoming' for purchase mode", () => {
    mockResult = {
      data: makePurchaseData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })
    const tablet = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="glance"]',
    )
    expect(tablet?.textContent).toContain("incoming")
    expect(tablet?.getAttribute("data-mode")).toBe("purchase")
  })

  it("Glance shows 'Vault not enabled' when is_vault_enabled=false", () => {
    mockResult = {
      data: makeDisabledData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })
    const tablet = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="glance"]',
    )
    expect(tablet?.textContent).toContain("Vault not enabled")
  })
})


// ── Brief variant ──────────────────────────────────────────────────


describe("VaultScheduleWidget — Brief variant", () => {
  it("default variant (no variant_id) renders Brief", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({})
    expect(
      document.querySelector(
        '[data-slot="vault-schedule-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })

  it("Brief renders production section with assigned/unassigned breakdown", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })

    const section = document.querySelector(
      '[data-slot="vault-schedule-production-section"]',
    )
    expect(section).toBeInTheDocument()
    expect(section?.textContent).toContain("Production")
    expect(section?.textContent).toContain("Unassigned")
    expect(section?.textContent).toContain("Assigned to drivers")
  })

  it("Brief renders purchase section in purchase mode", () => {
    mockResult = {
      data: makePurchaseData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const section = document.querySelector(
      '[data-slot="vault-schedule-purchase-section"]',
    )
    expect(section).toBeInTheDocument()
    expect(section?.textContent).toContain("Brown Family")
  })

  it("Brief in hybrid mode renders BOTH sections", () => {
    mockResult = {
      data: makeHybridData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    expect(
      document.querySelector(
        '[data-slot="vault-schedule-production-section"]',
      ),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="vault-schedule-purchase-section"]',
      ),
    ).toBeInTheDocument()
  })

  it("Brief renders mode badge", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const badge = document.querySelector(
      '[data-slot="vault-schedule-mode-badge"]',
    )
    expect(badge).toBeInTheDocument()
    expect(badge?.textContent).toBe("Production")
  })

  it("Brief renders empty state when vault disabled", () => {
    mockResult = {
      data: makeDisabledData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const empty = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="brief"]',
    )
    expect(empty?.textContent).toContain("Vault not enabled")
  })

  it("Brief preserves kanban frame in zero-work empty state", () => {
    // DESIGN_LANGUAGE §13 amendment (Phase W-4a Step 2.A): workspace-
    // core widgets preserve workspace shape in empty data states.
    // The kanban shape (header + section eyebrow + driver-lane
    // placeholder) IS the cognitive affordance — operators identify
    // the widget by structural shape, not by data presence.
    const data = makeProductionData()
    data.production!.total_count = 0
    data.production!.deliveries = []
    data.production!.assigned_count = 0
    data.production!.unassigned_count = 0
    mockResult = { data, isLoading: false, error: null }
    renderWidget({ variant_id: "brief" })
    const widget = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="brief"]',
    )
    // Workspace shape preserved: data-empty marker + section eyebrow +
    // dashed-placeholder lane. NOT a centered "Nothing scheduled".
    expect(widget?.getAttribute("data-empty")).toBe("true")
    expect(widget?.querySelector('[data-slot="vault-schedule-empty-section"]'))
      .toBeTruthy()
    expect(
      widget?.querySelector(
        '[data-slot="vault-schedule-empty-lane-placeholder"]',
      ),
    ).toBeTruthy()
    // Section eyebrow should still read "Production · Driver lanes"
    // — same chrome as populated state.
    expect(widget?.textContent).toContain("Production · Driver lanes")
    expect(widget?.textContent).toContain("0 total")
    // The "Open in scheduling Focus" footer link survives.
    expect(widget?.querySelector('[data-slot="vault-schedule-open-focus"]'))
      .toBeTruthy()
  })

  it("Detail preserves kanban frame in zero-work empty state", () => {
    const data = makeProductionData()
    data.production!.total_count = 0
    data.production!.deliveries = []
    data.production!.assigned_count = 0
    data.production!.unassigned_count = 0
    mockResult = { data, isLoading: false, error: null }
    renderWidget({ variant_id: "detail" })
    const widget = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="detail"]',
    )
    expect(widget?.getAttribute("data-empty")).toBe("true")
    expect(widget?.querySelector('[data-slot="vault-schedule-empty-section"]'))
      .toBeTruthy()
    expect(widget?.textContent).toContain("Production · Driver lanes")
  })

  it("'Vault not enabled' still renders centered empty state", () => {
    // The centered-icon + body-text + CTA generic empty state stays
    // for STRUCTURAL gaps (vault product line not active) — distinct
    // from data-empty kanban-frame.
    const data = makeProductionData()
    data.is_vault_enabled = false
    mockResult = { data, isLoading: false, error: null }
    renderWidget({ variant_id: "brief" })
    const widget = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="brief"]',
    )
    expect(widget?.textContent).toContain("Vault not enabled")
    // Centered empty state has the dedicated CTA slot, NOT the
    // workspace shape's empty-section slots.
    expect(widget?.querySelector('[data-slot="vault-schedule-empty-cta"]'))
      .toBeTruthy()
    expect(
      widget?.querySelector('[data-slot="vault-schedule-empty-section"]'),
    ).toBeFalsy()
  })

  it("Brief renders Open in Focus link", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const link = document.querySelector(
      '[data-slot="vault-schedule-open-focus"]',
    )
    expect(link).toBeInTheDocument()
    expect(link?.textContent).toContain("Open in scheduling Focus")
  })

  it("Brief shows error state when error set", () => {
    mockResult = {
      data: null,
      isLoading: false,
      error: "Network error",
    }
    renderWidget({ variant_id: "brief" })
    const err = document.querySelector('[data-slot="vault-schedule-error"]')
    expect(err?.textContent).toContain("Network error")
  })
})


// ── Detail variant ─────────────────────────────────────────────────


describe("VaultScheduleWidget — Detail variant", () => {
  it("Detail renders production driver lanes", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    const lanes = document.querySelectorAll(
      '[data-slot="vault-schedule-driver-lane"]',
    )
    expect(lanes.length).toBeGreaterThan(0)
  })

  it("Detail flags unassigned lane with data attribute", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    const unassigned = document.querySelector(
      '[data-slot="vault-schedule-driver-lane"][data-unassigned="true"]',
    )
    expect(unassigned).toBeInTheDocument()
    expect(unassigned?.textContent).toContain("Unassigned")
  })

  it("Detail in purchase mode renders date buckets", () => {
    mockResult = {
      data: makePurchaseData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    const buckets = document.querySelectorAll(
      '[data-slot="vault-schedule-date-bucket"]',
    )
    expect(buckets.length).toBe(1)
  })

  it("Detail surfaces deceased names in cards", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    const tablet = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="detail"]',
    )
    expect(tablet?.textContent).toContain("John Smith")
    expect(tablet?.textContent).toContain("Jane Doe")
  })
})


// ── Deep variant ───────────────────────────────────────────────────


describe("VaultScheduleWidget — Deep variant", () => {
  it("Deep renders detail-level content (workspace-core canon)", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "deep" })
    // Deep wraps Detail, so it carries the detail variant attribute
    const detail = document.querySelector(
      '[data-slot="vault-schedule-widget"][data-variant="detail"]',
    )
    expect(detail).toBeInTheDocument()
  })
})


// ── Workspace-core canon — view + click-through, no in-place edits ─


describe("VaultScheduleWidget — workspace-core canon (§12.6 + §12.6a)", () => {
  it("widget surfaces an Open-in-Focus affordance (Detail)", () => {
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "detail" })
    expect(
      document.querySelector('[data-slot="vault-schedule-open-focus"]'),
    ).toBeInTheDocument()
  })

  it("widget does NOT render finalize/day-switch/bulk-reassignment controls", () => {
    // Per §12.6a: heavy actions belong in Focus, not the widget.
    // Regression guard: searching for affordances that should NEVER
    // appear in the widget rendering.
    mockResult = {
      data: makeProductionData(),
      isLoading: false,
      error: null,
    }
    const { container } = renderWidget({ variant_id: "detail" })
    const text = container.textContent ?? ""
    expect(text).not.toMatch(/finalize/i)
    expect(text).not.toMatch(/rebuild schedule/i)
    expect(text).not.toMatch(/bulk reassign/i)
  })
})


// ── Per-mode data path verification ────────────────────────────────


describe("VaultScheduleWidget — mode dispatch verification", () => {
  it("widget reflects whatever operating_mode the endpoint returns", () => {
    // The widget itself doesn't dispatch — it renders whatever the
    // backend returns. Regression guard: prove the widget surfaces
    // each mode end-to-end.
    for (const mode of ["production", "purchase", "hybrid"] as const) {
      mockResult = {
        data:
          mode === "production"
            ? makeProductionData()
            : mode === "purchase"
            ? makePurchaseData()
            : makeHybridData(),
        isLoading: false,
        error: null,
      }
      const { unmount } = renderWidget({ variant_id: "brief" })
      const tablet = document.querySelector(
        '[data-slot="vault-schedule-widget"][data-variant="brief"]',
      )
      expect(tablet?.getAttribute("data-mode")).toBe(mode)
      unmount()
    }
  })
})
