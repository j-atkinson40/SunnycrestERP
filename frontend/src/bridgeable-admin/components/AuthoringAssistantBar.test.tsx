/**
 * AuthoringAssistantBar (Shell-1) — omnipresent across surfaces, page-aware,
 * context-appropriate, hidden on login. (The survives-navigation property is the
 * above-Routes mount in BridgeableAdminApp — witnessed visually in the preview.)
 */
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, it, expect } from "vitest"

import { AuthoringAssistantBar } from "./AuthoringAssistantBar"
import { AdminCommandBarProvider } from "./AdminCommandBar"

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AdminCommandBarProvider>
        <AuthoringAssistantBar />
      </AdminCommandBarProvider>
    </MemoryRouter>,
  )
}

describe("AuthoringAssistantBar", () => {
  it("is present on a MoC page, armed, with the vertical context", () => {
    renderAt("/maps/manufacturing")
    expect(screen.getByTestId("authoring-assistant-bar")).toBeInTheDocument()
    expect(screen.getByText("Author")).toBeInTheDocument()
    expect(screen.getByTestId("authoring-assistant-context")).toHaveTextContent("manufacturing")
  })

  it("is present on a Studio editor page, armed, showing the editor", () => {
    renderAt("/studio/manufacturing/workflows")
    expect(screen.getByTestId("authoring-assistant-bar")).toBeInTheDocument()
    expect(screen.getByText("Author")).toBeInTheDocument()
    expect(screen.getByTestId("authoring-assistant-context")).toHaveTextContent(/workflow editor/i)
  })

  it("is present on an operational page but generic (not armed)", () => {
    renderAt("/health")
    expect(screen.getByTestId("authoring-assistant-bar")).toBeInTheDocument()
    expect(screen.getByText("Assistant")).toBeInTheDocument()
    expect(screen.getByTestId("authoring-assistant-context")).toHaveTextContent("Operational")
  })

  it("hides on the login route", () => {
    renderAt("/login")
    expect(screen.queryByTestId("authoring-assistant-bar")).not.toBeInTheDocument()
  })
})
