/**
 * UrnCatalogStatusWidget — vitest unit tests (Phase W-3d Commit 3).
 *
 * Phase W-3d extension-gated contract:
 *   • Glance + Brief variants per §12.10
 *   • Renders catalog health: SKU counts, low-stock, recent orders
 *   • Click-through to /urns/catalog
 *   • Empty state + low-stock highlighting
 *
 * NOTE: extension-gating is enforced at the backend 5-axis filter
 * (verified in test_urn_catalog_status_widget.py). The frontend
 * widget itself is dumb-render — receives data from the endpoint
 * and renders. Tests here cover the rendering contract.
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
  data: UrnCatalogStatusData | null
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


import { UrnCatalogStatusWidget } from "./UrnCatalogStatusWidget"


interface LowStockItem {
  product_id: string
  sku: string | null
  name: string
  qty_on_hand: number
  qty_reserved: number
  reorder_point: number
}

interface UrnCatalogStatusData {
  total_skus: number
  stocked_skus: number
  drop_ship_skus: number
  low_stock_count: number
  low_stock_items: LowStockItem[]
  recent_order_count: number
  navigation_target: string
}


function renderWidget(
  props: Parameters<typeof UrnCatalogStatusWidget>[0],
) {
  return render(
    <MemoryRouter>
      <UrnCatalogStatusWidget {...props} />
    </MemoryRouter>,
  )
}


function makeData(
  overrides: Partial<UrnCatalogStatusData> = {},
): UrnCatalogStatusData {
  return {
    total_skus: 23,
    stocked_skus: 8,
    drop_ship_skus: 15,
    low_stock_count: 0,
    low_stock_items: [],
    recent_order_count: 5,
    navigation_target: "/urns/catalog",
    ...overrides,
  }
}


function makeLowStockItem(
  overrides: Partial<LowStockItem> = {},
): LowStockItem {
  return {
    product_id: "p-1",
    sku: "P-LOW",
    name: "Cloisonne Opal",
    qty_on_hand: 2,
    qty_reserved: 0,
    reorder_point: 5,
    ...overrides,
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


describe("UrnCatalogStatusWidget — endpoint", () => {
  it("calls /widget-data/urn-catalog-status", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({})
    expect(mockUseWidgetData).toHaveBeenCalledWith(
      "/widget-data/urn-catalog-status",
    )
  })
})


// ── Glance variant ──────────────────────────────────────────────────


describe("UrnCatalogStatusWidget — Glance variant", () => {
  it("renders Glance with SKU count", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({ variant_id: "glance" })
    const tablet = document.querySelector(
      '[data-slot="urn-catalog-status-widget"][data-variant="glance"]',
    )
    expect(tablet).toBeInTheDocument()
    expect(tablet?.textContent).toContain("23 SKUs")
  })

  it("Glance shows low-stock dot when low_stock_count > 0", () => {
    mockResult = {
      data: makeData({ low_stock_count: 3 }),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })
    expect(
      document.querySelector('[data-slot="urn-catalog-low-stock-dot"]'),
    ).toBeInTheDocument()
  })

  it("Glance hides low-stock dot when zero", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({ variant_id: "glance" })
    expect(
      document.querySelector('[data-slot="urn-catalog-low-stock-dot"]'),
    ).toBeNull()
  })

  it("Glance reports 'No catalog yet' when total_skus=0", () => {
    mockResult = {
      data: makeData({ total_skus: 0 }),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "glance" })
    const tablet = document.querySelector(
      '[data-slot="urn-catalog-status-widget"][data-variant="glance"]',
    )
    expect(tablet?.textContent).toContain("No catalog yet")
  })
})


// ── Brief variant ──────────────────────────────────────────────────


describe("UrnCatalogStatusWidget — Brief variant", () => {
  it("default variant is Brief", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({})
    expect(
      document.querySelector(
        '[data-slot="urn-catalog-status-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })

  it("Brief renders 4 metric rows", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({ variant_id: "brief" })
    expect(
      document.querySelector('[data-slot="urn-catalog-row-stocked"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="urn-catalog-row-drop-ship"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="urn-catalog-row-low-stock"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="urn-catalog-row-recent-orders"]',
      ),
    ).toBeInTheDocument()
  })

  it("Brief data-low-stock attribute reflects state", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({ variant_id: "brief" })
    let tablet = document.querySelector(
      '[data-slot="urn-catalog-status-widget"][data-variant="brief"]',
    )
    expect(tablet?.getAttribute("data-low-stock")).toBe("false")

    mockResult = {
      data: makeData({ low_stock_count: 3 }),
      isLoading: false,
      error: null,
    }
    const { container } = renderWidget({ variant_id: "brief" })
    tablet = container.querySelector(
      '[data-slot="urn-catalog-status-widget"][data-variant="brief"]',
    )
    expect(tablet?.getAttribute("data-low-stock")).toBe("true")
  })

  it("Brief renders low-stock list when items present", () => {
    mockResult = {
      data: makeData({
        low_stock_count: 2,
        low_stock_items: [
          makeLowStockItem(),
          makeLowStockItem({
            product_id: "p-2",
            sku: "P-LOW2",
            name: "Crystal Heart",
            qty_on_hand: 1,
          }),
        ],
      }),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const list = document.querySelector(
      '[data-slot="urn-catalog-low-stock-list"]',
    )
    expect(list).toBeInTheDocument()
    const items = document.querySelectorAll(
      '[data-slot="urn-catalog-low-stock-item"]',
    )
    expect(items.length).toBe(2)
  })

  it("Brief shows SKU + name + qty/reorder format", () => {
    mockResult = {
      data: makeData({
        low_stock_count: 1,
        low_stock_items: [
          makeLowStockItem({
            sku: "P-LOW",
            name: "Cloisonne Opal",
            qty_on_hand: 2,
            reorder_point: 5,
          }),
        ],
      }),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const item = document.querySelector(
      '[data-slot="urn-catalog-low-stock-item"]',
    )
    expect(item?.textContent).toContain("P-LOW")
    expect(item?.textContent).toContain("Cloisonne Opal")
    expect(item?.textContent).toContain("2/5")
  })

  it("Brief renders empty state when total_skus=0", () => {
    mockResult = {
      data: makeData({ total_skus: 0 }),
      isLoading: false,
      error: null,
    }
    renderWidget({ variant_id: "brief" })
    const empty = document.querySelector(
      '[data-slot="urn-catalog-empty"]',
    )
    expect(empty?.textContent).toContain("Catalog is empty")
    expect(
      document.querySelector('[data-slot="urn-catalog-empty-cta"]'),
    ).toBeInTheDocument()
  })

  it("Brief renders error state when error set", () => {
    mockResult = {
      data: null,
      isLoading: false,
      error: "Network error",
    }
    renderWidget({ variant_id: "brief" })
    const err = document.querySelector('[data-slot="urn-catalog-error"]')
    expect(err?.textContent).toContain("Network error")
  })

  it("Brief renders Open catalog link", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({ variant_id: "brief" })
    const link = document.querySelector(
      '[data-slot="urn-catalog-open-link"]',
    )
    expect(link).toBeInTheDocument()
    expect(link?.textContent).toContain("Open catalog")
  })
})


// ── Variant fallback discipline ────────────────────────────────────


describe("UrnCatalogStatusWidget — variant fallback", () => {
  it("detail/deep variant_id falls back to Brief (no Detail/Deep declared)", () => {
    mockResult = { data: makeData(), isLoading: false, error: null }
    renderWidget({ variant_id: "detail" })
    expect(
      document.querySelector(
        '[data-slot="urn-catalog-status-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })
})
