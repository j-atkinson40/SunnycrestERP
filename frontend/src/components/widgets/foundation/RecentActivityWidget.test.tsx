/**
 * RecentActivityWidget — vitest unit tests.
 *
 * Phase W-3a contract:
 *   • Glance + Brief + Detail variants with shared chrome vocabulary
 *   • Activity rows render actor_name + verb + entity + timestamp
 *   • Detail variant filter chips toggle category visibility
 *   • Click navigation + View All CTA work
 *   • Empty/loading/error states
 *   • Cross-widget chrome continuity (bezel-grip on Glance)
 */

import { render, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"


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


import { RecentActivityWidget } from "./RecentActivityWidget"


function renderWidget(props: Parameters<typeof RecentActivityWidget>[0]) {
  return render(
    <MemoryRouter>
      <RecentActivityWidget {...props} />
    </MemoryRouter>,
  )
}


function makeActivity(overrides: Record<string, unknown> = {}) {
  return {
    id: `act-${Math.random().toString(36).slice(2, 8)}`,
    activity_type: "note",
    title: "Test note",
    body: "Body content",
    is_system_generated: false,
    company_id: "co-acme",
    company_name: "ACME Corp",
    created_at: new Date().toISOString(),
    logged_by: "u-1",
    actor_name: "James Atkinson",
    ...overrides,
  }
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


// ── Glance variant ──────────────────────────────────────────────────


describe("RecentActivityWidget — Glance variant", () => {
  it("renders Glance when surface=spaces_pin", () => {
    mockData = { activities: [makeActivity()] }
    renderWidget({ surface: "spaces_pin" })

    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget"][data-variant="glance"]',
      ),
    ).toBeInTheDocument()
    // Pattern 1 chrome — bezel grip column
    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget-bezel-grip"]',
      ),
    ).toBeInTheDocument()
  })

  it("Glance shows count chip when activities present", () => {
    mockData = {
      activities: [
        makeActivity(),
        makeActivity(),
        makeActivity(),
      ],
    }
    renderWidget({ surface: "spaces_pin" })

    const chip = document.querySelector(
      '[data-slot="recent-activity-widget-count"]',
    )
    expect(chip?.textContent).toBe("3")
  })

  it("Glance hides count chip when activities empty + 'Nothing recent' subtext", () => {
    mockData = { activities: [] }
    renderWidget({ surface: "spaces_pin" })

    expect(
      document.querySelector('[data-slot="recent-activity-widget-count"]'),
    ).toBeNull()
    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget-subtext"]',
      )?.textContent,
    ).toMatch(/Nothing recent/)
  })

  it("Glance singular wording when count = 1", () => {
    mockData = { activities: [makeActivity()] }
    renderWidget({ surface: "spaces_pin" })

    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget-subtext"]',
      )?.textContent,
    ).toMatch(/1 event/)
  })

  it("Glance click summons /vault/crm", () => {
    mockData = { activities: [makeActivity()] }
    renderWidget({ surface: "spaces_pin" })

    const tablet = document.querySelector(
      '[data-slot="recent-activity-widget"][data-variant="glance"]',
    ) as HTMLElement
    fireEvent.click(tablet)
    expect(mockNavigate).toHaveBeenCalledWith("/vault/crm")
  })
})


// ── Brief variant ──────────────────────────────────────────────────


describe("RecentActivityWidget — Brief variant", () => {
  it("renders Brief by default", () => {
    mockData = {
      activities: [
        makeActivity({ activity_type: "note" }),
        makeActivity({ activity_type: "call" }),
      ],
    }
    renderWidget({})

    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget"][data-variant="brief"]',
      ),
    ).toBeInTheDocument()
  })

  it("Brief renders top 5 activity rows", () => {
    mockData = {
      activities: [
        makeActivity({ id: "1" }),
        makeActivity({ id: "2" }),
        makeActivity({ id: "3" }),
        makeActivity({ id: "4" }),
        makeActivity({ id: "5" }),
        makeActivity({ id: "6" }),
        makeActivity({ id: "7" }),
      ],
    }
    renderWidget({})

    const rows = document.querySelectorAll(
      '[data-slot="recent-activity-widget-row"]',
    )
    expect(rows.length).toBe(5)
  })

  it("Brief row click navigates to entity (CRM company)", () => {
    mockData = {
      activities: [makeActivity({ id: "act-1", company_id: "co-acme" })],
    }
    renderWidget({})

    const row = document.querySelector(
      '[data-activity-id="act-1"]',
    ) as HTMLElement
    fireEvent.click(row)
    expect(mockNavigate).toHaveBeenCalledWith("/vault/crm/companies/co-acme")
  })

  it("Brief 'View all' CTA navigates to /vault/crm", () => {
    mockData = { activities: [makeActivity()] }
    renderWidget({})

    const cta = document.querySelector(
      '[data-slot="recent-activity-widget-view-all"]',
    ) as HTMLElement
    fireEvent.click(cta)
    expect(mockNavigate).toHaveBeenCalledWith("/vault/crm")
  })

  it("Brief empty state when activities = []", () => {
    mockData = { activities: [] }
    renderWidget({})

    expect(
      document.querySelector('[data-slot="recent-activity-widget-empty"]'),
    ).toBeInTheDocument()
  })

  it("Brief renders actor name + verb + company in row", () => {
    mockData = {
      activities: [
        makeActivity({
          actor_name: "James Atkinson",
          activity_type: "call",
          company_name: "Hopkins FH",
        }),
      ],
    }
    renderWidget({})

    const row = document.querySelector(
      '[data-slot="recent-activity-widget-row"]',
    )
    expect(row?.textContent).toContain("James Atkinson")
    expect(row?.textContent).toContain("logged a call")
    expect(row?.textContent).toContain("Hopkins FH")
  })

  it("Brief falls back to 'System' for system-generated activity", () => {
    mockData = {
      activities: [
        makeActivity({
          actor_name: null,
          is_system_generated: true,
          activity_type: "status_change",
        }),
      ],
    }
    renderWidget({})

    const row = document.querySelector(
      '[data-slot="recent-activity-widget-row"]',
    )
    expect(row?.textContent).toContain("System")
  })

  it("Brief error state when fetch fails", () => {
    mockError = "Network error"
    renderWidget({})

    expect(
      document.querySelector('[data-slot="recent-activity-widget-error"]'),
    ).toBeInTheDocument()
  })
})


// ── Detail variant ──────────────────────────────────────────────────


describe("RecentActivityWidget — Detail variant", () => {
  it("renders Detail when variant_id=detail", () => {
    mockData = { activities: [makeActivity()] }
    renderWidget({ variant_id: "detail" })

    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget"][data-variant="detail"]',
      ),
    ).toBeInTheDocument()
  })

  it("Detail renders all 4 filter chips (All / Comms / Work / System)", () => {
    mockData = { activities: [makeActivity()] }
    renderWidget({ variant_id: "detail" })

    const chips = document.querySelectorAll(
      '[data-slot="recent-activity-widget-filter-chip"]',
    )
    expect(chips.length).toBe(4)
    const keys = Array.from(chips).map((c) =>
      c.getAttribute("data-filter-key"),
    )
    expect(keys).toEqual(["all", "comms", "work", "system"])
  })

  it("Detail All filter shows all activities by default", () => {
    mockData = {
      activities: [
        makeActivity({ id: "1", activity_type: "call" }), // comms
        makeActivity({ id: "2", activity_type: "delivery" }), // work
        makeActivity({ id: "3", activity_type: "system_event" }), // system
      ],
    }
    renderWidget({ variant_id: "detail" })

    const rows = document.querySelectorAll(
      '[data-slot="recent-activity-widget-row"]',
    )
    expect(rows.length).toBe(3)
  })

  it("Detail Comms filter shows only call/email/meeting/note", () => {
    mockData = {
      activities: [
        makeActivity({ id: "1", activity_type: "call" }), // comms
        makeActivity({ id: "2", activity_type: "delivery" }), // work
        makeActivity({ id: "3", activity_type: "note" }), // comms
      ],
    }
    renderWidget({ variant_id: "detail" })

    const commsChip = document.querySelector(
      '[data-filter-key="comms"]',
    ) as HTMLElement
    fireEvent.click(commsChip)

    const rows = document.querySelectorAll(
      '[data-slot="recent-activity-widget-row"]',
    )
    expect(rows.length).toBe(2) // call + note, not delivery
  })

  it("Detail Work filter excludes comms + system", () => {
    mockData = {
      activities: [
        makeActivity({ id: "1", activity_type: "call" }), // comms
        makeActivity({ id: "2", activity_type: "delivery" }), // work
        makeActivity({ id: "3", activity_type: "invoice" }), // work
      ],
    }
    renderWidget({ variant_id: "detail" })

    const workChip = document.querySelector(
      '[data-filter-key="work"]',
    ) as HTMLElement
    fireEvent.click(workChip)

    const rows = document.querySelectorAll(
      '[data-slot="recent-activity-widget-row"]',
    )
    expect(rows.length).toBe(2)
  })

  it("Detail filter chip carries aria-selected for a11y", () => {
    mockData = { activities: [makeActivity()] }
    renderWidget({ variant_id: "detail" })

    const allChip = document.querySelector(
      '[data-filter-key="all"]',
    ) as HTMLElement
    expect(allChip.getAttribute("aria-selected")).toBe("true")

    const workChip = document.querySelector(
      '[data-filter-key="work"]',
    ) as HTMLElement
    expect(workChip.getAttribute("aria-selected")).toBe("false")

    fireEvent.click(workChip)
    expect(workChip.getAttribute("aria-selected")).toBe("true")
    expect(allChip.getAttribute("aria-selected")).toBe("false")
  })

  it("Detail empty-filter shows 'No activity in this filter'", () => {
    mockData = {
      activities: [makeActivity({ activity_type: "call" })],
    }
    renderWidget({ variant_id: "detail" })

    const workChip = document.querySelector(
      '[data-filter-key="work"]',
    ) as HTMLElement
    fireEvent.click(workChip)

    const empty = document.querySelector(
      '[data-slot="recent-activity-widget-empty"]',
    )
    expect(empty?.textContent).toMatch(/No activity in this filter/)
  })

  it("Detail empty when activities = []", () => {
    mockData = { activities: [] }
    renderWidget({ variant_id: "detail" })

    const empty = document.querySelector(
      '[data-slot="recent-activity-widget-empty"]',
    )
    expect(empty?.textContent).toMatch(/No recent activity/)
  })
})


// ── Cross-surface visual continuity ─────────────────────────────────


describe("RecentActivityWidget — chrome continuity", () => {
  it("Glance carries the same Pattern 1 bezel-grip + eyebrow + count shape", () => {
    mockData = { activities: [makeActivity()] }
    renderWidget({ surface: "spaces_pin" })

    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget-bezel-grip"]',
      ),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget-eyebrow"]',
      ),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="recent-activity-widget-subtext"]',
      ),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="recent-activity-widget-count"]'),
    ).toBeInTheDocument()
  })
})
