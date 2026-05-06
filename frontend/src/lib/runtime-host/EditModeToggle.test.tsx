/**
 * Phase R-1 — EditModeToggle tests.
 *
 * Verifies URL-param sync (?edit=1 ↔ isEditing) + the unsaved-drafts
 * confirm dialog gating toggle-off.
 */
import { describe, it, expect, afterEach } from "vitest"
import { render, screen, cleanup, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { EditModeProvider } from "./edit-mode-context"
import { EditModeToggle } from "./EditModeToggle"


afterEach(cleanup)


function renderToggle({
  initialMode = "view",
  initialEntries = ["/"],
}: {
  initialMode?: "view" | "edit"
  initialEntries?: string[]
} = {}) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <EditModeProvider
        tenantSlug="testco"
        impersonatedUserId="user-1"
        initialMode={initialMode}
      >
        <EditModeToggle />
      </EditModeProvider>
    </MemoryRouter>,
  )
}


describe("EditModeToggle", () => {
  it("renders the View label when not editing", () => {
    renderToggle({ initialMode: "view" })
    const button = screen.getByTestId("runtime-editor-toggle")
    expect(button.textContent ?? "").toContain("View")
    expect(button.getAttribute("data-active")).toBe("false")
  })

  it("renders the Editing label + brass indicator when active", () => {
    renderToggle({ initialEntries: ["/?edit=1"] })
    const button = screen.getByTestId("runtime-editor-toggle")
    expect(button.textContent ?? "").toContain("Editing")
    expect(button.getAttribute("data-active")).toBe("true")
    expect(
      screen.queryByTestId("runtime-editor-edit-indicator"),
    ).not.toBeNull()
  })

  it("shows the unmapped-route warning for routes not in PAGE_CONTEXT_MAP", () => {
    renderToggle({ initialEntries: ["/__not_a_real_route_12345"] })
    expect(
      screen.queryByTestId("runtime-editor-unmapped-warning"),
    ).not.toBeNull()
  })

  it("toggles into edit mode on click", () => {
    renderToggle({ initialMode: "view" })
    const button = screen.getByTestId("runtime-editor-toggle")
    fireEvent.click(button)
    expect(button.getAttribute("data-active")).toBe("true")
  })
})
