/**
 * StudioScopeSwitcher smoke tests — Studio 1a-i.A1.
 *
 * Verifies:
 *   - Fetches verticals on mount
 *   - Renders Platform + every published vertical
 *   - Excludes archived
 *   - Clicking a scope navigates to the right Studio URL
 *   - Preserves active editor when switching scopes
 *   - Drops vertical for platform-only editors
 *   - Disabled mode renders without dropdown
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom"


vi.mock("@/bridgeable-admin/services/verticals-service", () => ({
  verticalsService: {
    list: vi.fn().mockResolvedValue([
      {
        slug: "manufacturing",
        display_name: "Manufacturing",
        description: null,
        status: "published",
        icon: null,
        sort_order: 10,
        created_at: "",
        updated_at: "",
      },
      {
        slug: "funeral_home",
        display_name: "Funeral Home",
        description: null,
        status: "published",
        icon: null,
        sort_order: 20,
        created_at: "",
        updated_at: "",
      },
      {
        slug: "deprecated_vertical",
        display_name: "Old",
        description: null,
        status: "archived",
        icon: null,
        sort_order: 99,
        created_at: "",
        updated_at: "",
      },
    ]),
    get: vi.fn(),
    update: vi.fn(),
  },
}))


import { StudioScopeSwitcher } from "./StudioScopeSwitcher"


function LocationProbe() {
  const location = useLocation()
  return (
    <div data-testid="probe" data-pathname={location.pathname} />
  )
}


function renderWith(
  props: React.ComponentProps<typeof StudioScopeSwitcher>,
  initialEntry = "/studio",
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <StudioScopeSwitcher {...props} />
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}


afterEach(() => {
  window.localStorage.clear()
})


describe("StudioScopeSwitcher", () => {
  it("renders Platform label by default", async () => {
    renderWith({ activeVertical: null, activeEditor: null })
    const btn = screen.getByTestId("studio-scope-switcher")
    expect(btn.textContent).toMatch(/Platform/)
    expect(btn.getAttribute("data-active-vertical")).toBe("platform")
  })

  it("opens menu + lists Platform + non-archived verticals", async () => {
    renderWith({ activeVertical: null, activeEditor: null })
    fireEvent.click(screen.getByTestId("studio-scope-switcher"))
    await waitFor(() => {
      expect(screen.getByTestId("studio-scope-item-manufacturing")).toBeTruthy()
    })
    expect(screen.getByTestId("studio-scope-item-platform")).toBeTruthy()
    expect(screen.getByTestId("studio-scope-item-funeral_home")).toBeTruthy()
    expect(screen.queryByTestId("studio-scope-item-deprecated_vertical")).toBeNull()
  })

  it("clicking a vertical navigates to /studio/:vertical", async () => {
    renderWith({ activeVertical: null, activeEditor: null })
    fireEvent.click(screen.getByTestId("studio-scope-switcher"))
    await waitFor(() => screen.getByTestId("studio-scope-item-manufacturing"))
    fireEvent.click(screen.getByTestId("studio-scope-item-manufacturing"))
    await waitFor(() => {
      expect(screen.getByTestId("probe").getAttribute("data-pathname")).toBe(
        "/studio/manufacturing",
      )
    })
  })

  it("preserves active editor when switching scopes", async () => {
    renderWith({ activeVertical: null, activeEditor: "themes" })
    fireEvent.click(screen.getByTestId("studio-scope-switcher"))
    await waitFor(() => screen.getByTestId("studio-scope-item-funeral_home"))
    fireEvent.click(screen.getByTestId("studio-scope-item-funeral_home"))
    await waitFor(() => {
      expect(screen.getByTestId("probe").getAttribute("data-pathname")).toBe(
        "/studio/funeral_home/themes",
      )
    })
  })

  it("drops platform-only editor when switching to Platform scope", async () => {
    renderWith({ activeVertical: "manufacturing", activeEditor: "themes" })
    fireEvent.click(screen.getByTestId("studio-scope-switcher"))
    await waitFor(() => screen.getByTestId("studio-scope-item-platform"))
    fireEvent.click(screen.getByTestId("studio-scope-item-platform"))
    await waitFor(() => {
      expect(screen.getByTestId("probe").getAttribute("data-pathname")).toBe(
        "/studio/themes",
      )
    })
  })

  it("disabled mode renders but doesn't open the menu", () => {
    renderWith({ activeVertical: null, activeEditor: null, disabled: true })
    const btn = screen.getByTestId("studio-scope-switcher")
    fireEvent.click(btn)
    expect(screen.queryByTestId("studio-scope-switcher-menu")).toBeNull()
  })

  it("writes lastVertical on switch", async () => {
    renderWith({ activeVertical: null, activeEditor: null })
    fireEvent.click(screen.getByTestId("studio-scope-switcher"))
    await waitFor(() => screen.getByTestId("studio-scope-item-manufacturing"))
    fireEvent.click(screen.getByTestId("studio-scope-item-manufacturing"))
    await waitFor(() => {
      expect(window.localStorage.getItem("studio.lastVertical")).toBe(
        "manufacturing",
      )
    })
  })
})
