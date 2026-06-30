/**
 * AuthoringAssistantBar — Shell-1 (omnipresent, page-aware) + Shell-2 (workflow
 * draft routing). The draft request rides the shared AuthoringRequestContext;
 * from MoC the bar also navigates into the workflow editor. Armed-only.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, it, expect, vi, beforeEach } from "vitest"

const navigateMock = vi.fn()
vi.mock("react-router-dom", async (orig) => {
  const actual = await orig<typeof import("react-router-dom")>()
  return { ...actual, useNavigate: () => navigateMock }
})

const submitMock = vi.fn()
vi.mock("../contexts/AuthoringRequestContext", () => ({
  useAuthoringRequest: () => ({ request: null, submit: submitMock, consume: vi.fn() }),
}))

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

beforeEach(() => {
  navigateMock.mockClear()
  submitMock.mockClear()
})

describe("AuthoringAssistantBar — Shell-1 presence + context", () => {
  it("present on a MoC vertical page, armed, with context", () => {
    renderAt("/maps/manufacturing")
    expect(screen.getByTestId("authoring-assistant-bar")).toBeInTheDocument()
    expect(screen.getByText("Author")).toBeInTheDocument()
    expect(screen.getByTestId("authoring-assistant-context")).toHaveTextContent("manufacturing")
  })

  it("present on the Studio workflow editor, armed", () => {
    renderAt("/studio/manufacturing/workflows")
    expect(screen.getByText("Author")).toBeInTheDocument()
    expect(screen.getByTestId("authoring-assistant-context")).toHaveTextContent(/workflow editor/i)
  })

  it("present but generic on an operational page (not armed)", () => {
    renderAt("/health")
    expect(screen.getByText("Assistant")).toBeInTheDocument()
  })

  it("generic on a NON-workflow Studio editor — scope guard (focus brain doesn't exist)", () => {
    renderAt("/studio/manufacturing/focuses")
    expect(screen.getByText("Assistant")).toBeInTheDocument()
  })

  it("hides on the login route", () => {
    renderAt("/login")
    expect(screen.queryByTestId("authoring-assistant-bar")).not.toBeInTheDocument()
  })
})

describe("AuthoringAssistantBar — Shell-2 workflow draft routing", () => {
  it("from a MoC vertical: submits the request to the context + navigates into the workflow editor", () => {
    renderAt("/maps/manufacturing")
    fireEvent.click(screen.getByRole("button")) // expand → input
    fireEvent.change(screen.getByTestId("authoring-assistant-input"), {
      target: { value: "invoice a funeral home at month end" },
    })
    fireEvent.submit(screen.getByTestId("authoring-assistant-input-form"))

    expect(submitMock).toHaveBeenCalledWith("invoice a funeral home at month end")
    expect(navigateMock).toHaveBeenCalledTimes(1)
    expect(navigateMock.mock.calls[0][0]).toMatch(/\/studio\/manufacturing\/workflows$/)
  })

  it("from the workflow editor: submits to the context WITHOUT navigating (in-place)", () => {
    renderAt("/studio/manufacturing/workflows")
    fireEvent.click(screen.getByRole("button"))
    fireEvent.change(screen.getByTestId("authoring-assistant-input"), {
      target: { value: "a quote to pour workflow" },
    })
    fireEvent.submit(screen.getByTestId("authoring-assistant-input-form"))

    expect(submitMock).toHaveBeenCalledWith("a quote to pour workflow")
    expect(navigateMock).not.toHaveBeenCalled() // in-place — no navigation
  })

  it("armed-only: an operational page does NOT show the draft input + does NOT route", () => {
    renderAt("/health")
    fireEvent.click(screen.getByRole("button")) // generic launcher → opens overlay
    expect(screen.queryByTestId("authoring-assistant-input")).not.toBeInTheDocument()
    expect(submitMock).not.toHaveBeenCalled()
    expect(navigateMock).not.toHaveBeenCalled()
  })
})
