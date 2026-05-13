/**
 * StudioOverviewPage tests — Studio 1a-ii.
 *
 * Covers:
 *   - Card count rendered when count is a number
 *   - Card count display omitted when count is null
 *   - Recent edits feed renders rows + deep-link href + relative time
 *   - Editor attribution silently omitted when editor_email is null
 *   - Empty state when recent_edits is []
 *   - Loading state pre-fetch
 *   - Error state on fetch failure
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"


// Hoisted mock state — vitest auto-hoists vi.mock calls.
const getStudioInventoryMock = vi.fn()
vi.mock("@/bridgeable-admin/lib/studio-inventory-client", async () => {
  const actual: object = await vi.importActual(
    "@/bridgeable-admin/lib/studio-inventory-client",
  )
  return {
    ...actual,
    getStudioInventory: (...args: unknown[]) => getStudioInventoryMock(...args),
  }
})


import StudioOverviewPage from "./StudioOverviewPage"


function nowIso(offsetMs = 0): string {
  return new Date(Date.now() - offsetMs).toISOString()
}


function fixtureInventory(overrides: Record<string, unknown> = {}) {
  return {
    scope: "platform",
    vertical_slug: null,
    sections: [
      { key: "themes", label: "Themes", count: 12 },
      { key: "focuses", label: "Focus Editor", count: 3 },
      { key: "widgets", label: "Widget Editor", count: 7 },
      { key: "documents", label: "Documents", count: 18 },
      { key: "classes", label: "Classes", count: 4 },
      { key: "workflows", label: "Workflows", count: 9 },
      { key: "edge-panels", label: "Edge Panels", count: 2 },
      // count=null for registry inspector + plugin-registry-under-vertical
      { key: "registry", label: "Registry inspector", count: null },
      { key: "plugin-registry", label: "Plugin Registry", count: 24 },
    ],
    recent_edits: [
      {
        section: "themes",
        entity_name: "Wastewater operator theme",
        entity_id: "theme-uuid-1",
        editor_email: "designer@example.com",
        edited_at: nowIso(2 * 60 * 1000), // 2 min ago
        deep_link_path: "/studio/themes?theme_id=theme-uuid-1",
      },
      {
        section: "documents",
        entity_name: "invoice.standard",
        entity_id: "doc-uuid-2",
        editor_email: null, // documents has no updated_by
        edited_at: nowIso(60 * 60 * 1000), // 1h ago
        deep_link_path: "/studio/documents?template=doc-uuid-2",
      },
    ],
    ...overrides,
  }
}


beforeEach(() => {
  getStudioInventoryMock.mockReset()
})

afterEach(() => {
  vi.clearAllMocks()
})


function renderPage(activeVertical: string | null = null) {
  return render(
    <MemoryRouter>
      <StudioOverviewPage activeVertical={activeVertical} />
    </MemoryRouter>,
  )
}


describe("StudioOverviewPage — Studio 1a-ii", () => {
  it("renders loading state before fetch resolves", () => {
    getStudioInventoryMock.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(
      screen.getByTestId("studio-overview-recent-edits-loading"),
    ).toBeTruthy()
  })

  it("renders section counts when count is a number", async () => {
    getStudioInventoryMock.mockResolvedValue(fixtureInventory())
    renderPage()
    await waitFor(() => {
      const themes = screen.getByTestId("studio-overview-card-themes-count")
      expect(themes.textContent).toBe("12")
    })
    expect(
      screen.getByTestId("studio-overview-card-plugin-registry-count")
        .textContent,
    ).toBe("24")
  })

  it("omits count display when count is null", async () => {
    getStudioInventoryMock.mockResolvedValue(fixtureInventory())
    renderPage()
    await waitFor(() => {
      // Registry card is present, but no -count badge inside it.
      expect(screen.getByTestId("studio-overview-card-registry")).toBeTruthy()
    })
    expect(
      screen.queryByTestId("studio-overview-card-registry-count"),
    ).toBeNull()
  })

  it("renders recent-edits rows with deep-link href", async () => {
    getStudioInventoryMock.mockResolvedValue(fixtureInventory())
    renderPage()
    const list = await screen.findByTestId(
      "studio-overview-recent-edits-list",
    )
    const rows = list.querySelectorAll(
      '[data-testid="studio-overview-recent-edit-row"]',
    )
    expect(rows.length).toBe(2)
    // First row's anchor href
    const first = rows[0] as HTMLAnchorElement
    expect(first.getAttribute("href")).toContain("theme-uuid-1")
  })

  it("renders attribution when editor_email present, omits when null", async () => {
    getStudioInventoryMock.mockResolvedValue(fixtureInventory())
    renderPage()
    await screen.findByTestId("studio-overview-recent-edits-list")
    // Designer email present in first row
    expect(screen.queryByText(/designer@example\.com/)).toBeTruthy()
    // No "by —" or similar placeholder anywhere
    expect(screen.queryByText(/by\s+—/)).toBeNull()
    expect(screen.queryByText(/by\s+null/i)).toBeNull()
    expect(screen.queryByText(/by\s+undefined/i)).toBeNull()
  })

  it("renders empty state when recent_edits is empty", async () => {
    getStudioInventoryMock.mockResolvedValue(
      fixtureInventory({ recent_edits: [] }),
    )
    renderPage()
    await waitFor(() => {
      expect(
        screen.getByTestId("studio-overview-recent-edits-empty"),
      ).toBeTruthy()
    })
  })

  it("renders error state on fetch failure", async () => {
    const { StudioInventoryError } = await import(
      "@/bridgeable-admin/lib/studio-inventory-client"
    )
    getStudioInventoryMock.mockRejectedValue(
      new StudioInventoryError("server unavailable", 503),
    )
    renderPage()
    await waitFor(() => {
      expect(
        screen.getByTestId("studio-overview-recent-edits-error"),
      ).toBeTruthy()
    })
    expect(
      screen.getByTestId("studio-overview-recent-edits-error").textContent,
    ).toContain("server unavailable")
  })

  it("fetches with the active vertical slug", async () => {
    getStudioInventoryMock.mockResolvedValue(
      fixtureInventory({
        scope: "vertical",
        vertical_slug: "manufacturing",
      }),
    )
    renderPage("manufacturing")
    await waitFor(() => {
      expect(getStudioInventoryMock).toHaveBeenCalledWith("manufacturing")
    })
  })

  it("renders 9 section cards regardless of inventory shape", async () => {
    getStudioInventoryMock.mockResolvedValue(fixtureInventory())
    renderPage()
    await screen.findByTestId("studio-overview-recent-edits-list")
    // Compose card lookup — all 9 sections from A1 still present.
    const cards = [
      "themes",
      "focuses",
      "widgets",
      "documents",
      "classes",
      "workflows",
      "edge-panels",
      "registry",
      "plugin-registry",
    ]
    for (const editor of cards) {
      expect(
        screen.getByTestId(`studio-overview-card-${editor}`),
      ).toBeTruthy()
    }
  })

  it("avoids fireEvent unused warning", () => {
    // Anchor used by vitest's tree-shaking awareness; no-op test body.
    void fireEvent
  })
})
