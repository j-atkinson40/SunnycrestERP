/**
 * TodayWidget — vitest unit tests.
 *
 * Covers Phase W-3a contract:
 *   • Glance variant for spaces_pin surface
 *   • Brief variant for non-sidebar surfaces (default)
 *   • Vertical-aware data display (Sunnycrest manufacturing+vault
 *     vs. funeral_home empty state)
 *   • Click navigation handlers (summon + per-row navigate)
 *   • Loading + error states
 *   • Three-component shape preserved per AncillaryPoolPin precedent
 *   • Pattern 1 chrome on Glance / Pattern 2 content shape on Brief
 */

import { render, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"


// ── Mock useWidgetData hook so tests don't issue real HTTP calls ────


let mockData: unknown = null
let mockIsLoading = false
let mockError: string | null = null


vi.mock("@/components/widgets/useWidgetData", () => ({
  useWidgetData: () => ({
    data: mockData,
    isLoading: mockIsLoading,
    error: mockError,
    refresh: vi.fn(),
    lastUpdated: new Date(),
  }),
}))


// Mock useNavigate to capture navigation intents
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


import { TodayWidget } from "./TodayWidget"


function renderWidget(props: Parameters<typeof TodayWidget>[0]) {
  return render(
    <MemoryRouter>
      <TodayWidget {...props} />
    </MemoryRouter>,
  )
}


beforeEach(() => {
  mockData = null
  mockIsLoading = false
  mockError = null
  mockNavigate.mockClear()
})


afterEach(() => {
  vi.clearAllMocks()
})


// ── Glance variant tests ────────────────────────────────────────────


describe("TodayWidget — Glance variant (Phase W-3a)", () => {
  it("renders Glance when surface=spaces_pin", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 3,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ surface: "spaces_pin" })

    const tablet = document.querySelector(
      '[data-slot="today-widget"][data-variant="glance"]',
    )
    expect(tablet).toBeInTheDocument()
    // Pattern 1 chrome — bezel grip column
    expect(
      document.querySelector('[data-slot="today-widget-bezel-grip"]'),
    ).toBeInTheDocument()
  })

  it("renders Glance when variant_id=glance", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 0,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ variant_id: "glance" })

    expect(
      document.querySelector(
        '[data-slot="today-widget"][data-variant="glance"]',
      ),
    ).toBeInTheDocument()
  })

  it("Glance shows count chip when total > 0", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 5,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ surface: "spaces_pin" })

    const chip = document.querySelector(
      '[data-slot="today-widget-count"]',
    )
    expect(chip).toBeInTheDocument()
    expect(chip?.textContent).toBe("5")
  })

  it("Glance hides count chip when total = 0 + shows 'Nothing scheduled' subtext", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 0,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ surface: "spaces_pin" })

    expect(
      document.querySelector('[data-slot="today-widget-count"]'),
    ).toBeNull()
    const subtext = document.querySelector(
      '[data-slot="today-widget-glance-subtext"]',
    )
    expect(subtext?.textContent).toMatch(/Nothing scheduled/)
  })

  it("Glance singular wording when total = 1", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 1,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ surface: "spaces_pin" })

    const subtext = document.querySelector(
      '[data-slot="today-widget-glance-subtext"]',
    )
    expect(subtext?.textContent).toMatch(/1 item today/)
    // Should NOT pluralize when 1.
    expect(subtext?.textContent).not.toMatch(/items today/)
  })

  it("Glance click summons navigation to primary_navigation_target", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 5,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ surface: "spaces_pin" })

    const tablet = document.querySelector(
      '[data-slot="today-widget"][data-variant="glance"]',
    ) as HTMLElement
    fireEvent.click(tablet)
    expect(mockNavigate).toHaveBeenCalledWith("/dispatch")
  })

  it("Glance falls back to /dashboard when no primary_navigation_target", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 0,
      categories: [],
      primary_navigation_target: null,
    }
    renderWidget({ surface: "spaces_pin" })

    const tablet = document.querySelector(
      '[data-slot="today-widget"][data-variant="glance"]',
    ) as HTMLElement
    fireEvent.click(tablet)
    expect(mockNavigate).toHaveBeenCalledWith("/dashboard")
  })

  it("Glance carries role=button + tabIndex=0 for keyboard summon", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 1,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ surface: "spaces_pin" })

    const tablet = document.querySelector(
      '[data-slot="today-widget"][data-variant="glance"]',
    ) as HTMLElement
    expect(tablet.getAttribute("role")).toBe("button")
    expect(tablet.getAttribute("tabIndex")).toBe("0")
    expect(tablet.getAttribute("aria-label")).toMatch(/Open for details/)
  })
})


// ── Brief variant tests ────────────────────────────────────────────


describe("TodayWidget — Brief variant (Phase W-3a)", () => {
  it("renders Brief by default (no surface, no variant_id)", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 3,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({})

    expect(
      document.querySelector('[data-slot="today-widget"][data-variant="brief"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="today-widget-header"]'),
    ).toBeInTheDocument()
  })

  it("renders date in long form for Brief header", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 3,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({})

    const header = document.querySelector(
      '[data-slot="today-widget-header"]',
    )
    // Long-form weekday + month + day; locale-dependent but should
    // include "April" or "Apr" + "27" for our fixture date
    expect(header?.textContent).toMatch(/April|Apr/)
    expect(header?.textContent).toMatch(/27/)
  })

  it("Brief renders category breakdown rows", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 7,
      categories: [
        {
          key: "vault_deliveries",
          label: "5 vault deliveries",
          count: 5,
          navigation_target: "/dispatch",
        },
        {
          key: "ancillary_pool",
          label: "2 ancillary items waiting",
          count: 2,
          navigation_target: "/dispatch",
        },
      ],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({})

    const rows = document.querySelectorAll(
      '[data-slot^="today-widget-category-"]',
    )
    expect(rows.length).toBe(2)
    expect(rows[0].textContent).toMatch(/5 vault deliveries/)
    expect(rows[1].textContent).toMatch(/2 ancillary items waiting/)
  })

  it("Brief category click navigates to category-specific target", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 5,
      categories: [
        {
          key: "vault_deliveries",
          label: "5 vault deliveries",
          count: 5,
          navigation_target: "/dispatch",
        },
      ],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({})

    const row = document.querySelector(
      '[data-slot="today-widget-category-vault_deliveries"]',
    ) as HTMLElement
    fireEvent.click(row)
    expect(mockNavigate).toHaveBeenCalledWith("/dispatch")
  })

  it("Brief empty state when total = 0 + CTA to primary target", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 0,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({})

    expect(
      document.querySelector('[data-slot="today-widget-empty"]'),
    ).toBeInTheDocument()
    const cta = document.querySelector(
      '[data-slot="today-widget-empty-cta"]',
    )
    expect(cta).toBeInTheDocument()
    expect(cta?.textContent).toMatch(/Open schedule/)

    fireEvent.click(cta as HTMLElement)
    expect(mockNavigate).toHaveBeenCalledWith("/dispatch")
  })

  it("Brief empty state hides CTA when no primary_navigation_target", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 0,
      categories: [],
      primary_navigation_target: null,
    }
    renderWidget({})

    expect(
      document.querySelector('[data-slot="today-widget-empty"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="today-widget-empty-cta"]'),
    ).toBeNull()
  })

  it("Brief shows error state when fetch fails", () => {
    mockError = "Network error"
    renderWidget({})

    expect(
      document.querySelector('[data-slot="today-widget-error"]'),
    ).toBeInTheDocument()
  })

  it("Brief loading state dims content", () => {
    mockIsLoading = true
    mockData = null
    renderWidget({})

    const root = document.querySelector(
      '[data-slot="today-widget"][data-variant="brief"]',
    ) as HTMLElement
    expect(root.className).toMatch(/opacity-80/)
  })
})


// ── Cross-surface visual continuity ─────────────────────────────────


describe("TodayWidget — chrome continuity with AncillaryPoolPin", () => {
  it("Glance carries the same Pattern 1 bezel-grip structural element", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 0,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ surface: "spaces_pin" })

    // Same data-slot the AncillaryPoolPin Glance uses; cross-widget
    // visual vocabulary check.
    expect(
      document.querySelector('[data-slot="today-widget-bezel-grip"]'),
    ).toBeInTheDocument()
  })

  it("Glance carries the eyebrow + count + subtext shape", () => {
    mockData = {
      date: "2026-04-27",
      total_count: 4,
      categories: [],
      primary_navigation_target: "/dispatch",
    }
    renderWidget({ surface: "spaces_pin" })

    expect(
      document.querySelector('[data-slot="today-widget-eyebrow"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="today-widget-glance-subtext"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="today-widget-count"]'),
    ).toBeInTheDocument()
  })
})
