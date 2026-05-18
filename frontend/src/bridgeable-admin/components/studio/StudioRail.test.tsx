/**
 * StudioRail — sub-arc F-1.1 Focus Builder rail affordance tests (Q-41).
 *
 * Verifies:
 *   - Focus Builder entry renders alongside existing Focuses entry
 *   - Click navigates to /studio/builder/focuses (not studioPath-built)
 *   - "New" badge renders when localStorage key absent
 *   - Dismiss × persists to localStorage and hides the badge in place
 *   - Direct route still works after dismissal (entry remains clickable)
 */
import { describe, expect, it, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom"

import {
  StudioRail,
  FOCUS_BUILDER_RAIL_BANNER_KEY,
} from "./StudioRail"


function LocationProbe() {
  const loc = useLocation()
  return <div data-testid="location-probe" data-pathname={loc.pathname} />
}


function renderRail(initialEntries: string[] = ["/bridgeable-admin/studio"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <StudioRail
                expanded={true}
                onExpandedChange={() => {}}
                activeVertical={null}
                activeEditor={null}
                mode="edit"
              />
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}


describe("StudioRail — F-1.1 Focus Builder affordance", () => {
  beforeEach(() => {
    window.localStorage.removeItem(FOCUS_BUILDER_RAIL_BANNER_KEY)
  })

  it("renders the Focus Builder rail entry alongside Focuses", () => {
    renderRail()
    expect(screen.getByTestId("studio-rail-entry-focuses")).toBeTruthy()
    expect(screen.getByTestId("studio-rail-entry-focus-builder")).toBeTruthy()
  })

  it("renders the New badge when affordance is not dismissed", () => {
    renderRail()
    expect(
      screen.getByTestId("studio-rail-new-badge-focus-builder"),
    ).toBeTruthy()
  })

  it("clicking the Focus Builder entry navigates to /studio/builder/focuses", () => {
    renderRail()
    fireEvent.click(screen.getByTestId("studio-rail-entry-focus-builder"))
    const probe = screen.getByTestId("location-probe")
    expect(probe.getAttribute("data-pathname")).toContain(
      "/studio/builder/focuses",
    )
  })

  it("dismissing the New badge persists to localStorage", () => {
    renderRail()
    fireEvent.click(
      screen.getByTestId("studio-rail-new-badge-dismiss-focus-builder"),
    )
    expect(window.localStorage.getItem(FOCUS_BUILDER_RAIL_BANNER_KEY)).toBe(
      "1",
    )
  })

  it("hides the New badge after dismissal (without remount)", () => {
    renderRail()
    expect(
      screen.getByTestId("studio-rail-new-badge-focus-builder"),
    ).toBeTruthy()
    fireEvent.click(
      screen.getByTestId("studio-rail-new-badge-dismiss-focus-builder"),
    )
    expect(
      screen.queryByTestId("studio-rail-new-badge-focus-builder"),
    ).toBeNull()
  })

  it("does not render the New badge on remount when localStorage is set", () => {
    window.localStorage.setItem(FOCUS_BUILDER_RAIL_BANNER_KEY, "1")
    renderRail()
    expect(
      screen.queryByTestId("studio-rail-new-badge-focus-builder"),
    ).toBeNull()
    // Entry itself still renders + remains clickable.
    expect(screen.getByTestId("studio-rail-entry-focus-builder")).toBeTruthy()
  })

  it("dismiss click does not navigate (stopPropagation)", () => {
    renderRail(["/bridgeable-admin/studio/somewhere"])
    fireEvent.click(
      screen.getByTestId("studio-rail-new-badge-dismiss-focus-builder"),
    )
    const probe = screen.getByTestId("location-probe")
    // Should remain at the start path, not navigated to /studio/builder/focuses.
    expect(probe.getAttribute("data-pathname")).not.toContain(
      "/studio/builder/focuses",
    )
  })
})
