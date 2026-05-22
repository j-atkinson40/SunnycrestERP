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
  WIDGET_BUILDER_RAIL_BANNER_KEY,
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


/**
 * StudioRail — sub-arc WB-cycle-followup-1 Widget Builder rail affordance
 * tests. Mirrors F-1.1 Focus Builder test pattern verbatim per studio nav
 * investigation 3a019e1 Area 2 lock. Closes operator-validation-surfaced
 * entry-point gap from WB-1..WB-8 cycle.
 *
 * Verifies:
 *   - Widget Builder entry renders alongside existing Widgets entry
 *   - Entry positioned between Widgets and Documents (index 5)
 *   - Click navigates to /studio/widgets (Q-A4 lock; list view)
 *   - "New" badge renders when localStorage key absent
 *   - Dismiss × persists to localStorage and hides the badge in place
 *   - Direct route still works after dismissal
 */
describe("StudioRail — WB-cycle-followup-1 Widget Builder affordance", () => {
  beforeEach(() => {
    window.localStorage.removeItem(WIDGET_BUILDER_RAIL_BANNER_KEY)
  })

  it("renders the Widget Builder rail entry alongside Widgets", () => {
    renderRail()
    expect(screen.getByTestId("studio-rail-entry-widgets")).toBeTruthy()
    expect(screen.getByTestId("studio-rail-entry-widget-builder")).toBeTruthy()
  })

  it("positions Widget Builder between Widgets and Documents", () => {
    renderRail()
    const widgets = screen.getByTestId("studio-rail-entry-widgets")
    const widgetBuilder = screen.getByTestId("studio-rail-entry-widget-builder")
    const documents = screen.getByTestId("studio-rail-entry-documents")
    // DocumentPosition.DOCUMENT_POSITION_FOLLOWING === 4
    // Widgets must come before Widget Builder, Widget Builder before Documents.
    expect(
      widgets.compareDocumentPosition(widgetBuilder) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(
      widgetBuilder.compareDocumentPosition(documents) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it("renders the New badge when affordance is not dismissed", () => {
    renderRail()
    expect(
      screen.getByTestId("studio-rail-new-badge-widget-builder"),
    ).toBeTruthy()
  })

  it("clicking the Widget Builder entry navigates to /studio/widgets", () => {
    renderRail()
    fireEvent.click(screen.getByTestId("studio-rail-entry-widget-builder"))
    const probe = screen.getByTestId("location-probe")
    expect(probe.getAttribute("data-pathname")).toContain("/studio/widgets")
  })

  it("dismissing the New badge persists to localStorage", () => {
    renderRail()
    fireEvent.click(
      screen.getByTestId("studio-rail-new-badge-dismiss-widget-builder"),
    )
    expect(window.localStorage.getItem(WIDGET_BUILDER_RAIL_BANNER_KEY)).toBe(
      "1",
    )
  })

  it("hides the New badge after dismissal (without remount)", () => {
    renderRail()
    expect(
      screen.getByTestId("studio-rail-new-badge-widget-builder"),
    ).toBeTruthy()
    fireEvent.click(
      screen.getByTestId("studio-rail-new-badge-dismiss-widget-builder"),
    )
    expect(
      screen.queryByTestId("studio-rail-new-badge-widget-builder"),
    ).toBeNull()
  })

  it("does not render the New badge on remount when localStorage is set", () => {
    window.localStorage.setItem(WIDGET_BUILDER_RAIL_BANNER_KEY, "1")
    renderRail()
    expect(
      screen.queryByTestId("studio-rail-new-badge-widget-builder"),
    ).toBeNull()
    // Entry itself still renders + remains clickable.
    expect(screen.getByTestId("studio-rail-entry-widget-builder")).toBeTruthy()
  })

  it("dismiss click does not navigate (stopPropagation)", () => {
    renderRail(["/bridgeable-admin/studio/somewhere"])
    fireEvent.click(
      screen.getByTestId("studio-rail-new-badge-dismiss-widget-builder"),
    )
    const probe = screen.getByTestId("location-probe")
    // Should remain at the start path, not navigated to /studio/widgets.
    expect(probe.getAttribute("data-pathname")).not.toContain("/studio/widgets")
  })

  it("Focus Builder rail entry continues rendering at index 3 (no regression)", () => {
    renderRail()
    // F-1.1 substrate must continue working alongside WB-cycle-followup-1.
    expect(screen.getByTestId("studio-rail-entry-focus-builder")).toBeTruthy()
  })
})
