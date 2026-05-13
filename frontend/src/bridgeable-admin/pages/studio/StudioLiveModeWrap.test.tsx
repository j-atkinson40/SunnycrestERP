/**
 * StudioLiveModeWrap smoke tests — Studio 1a-i.A2 + Studio test maintenance.
 *
 * Verifies:
 *   - Mounts RuntimeEditorShell with studioContext=true
 *   - Forwards `vertical` prop to RuntimeEditorShell.verticalFilter
 *   - Renders the wrap test id so Studio shell test can locate it
 *
 * The wrap loads RuntimeEditorShell via React.lazy() (lazy boundary
 * restored in Studio test maintenance, 2026-05-13). Tests await the
 * Suspense resolution via `findByTestId` for assertions on the
 * RuntimeEditorShell stub.
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"


vi.mock("@/bridgeable-admin/pages/runtime-editor/RuntimeEditorShell", () => ({
  default: (props: { studioContext?: boolean; verticalFilter?: string | null }) => (
    <div
      data-testid="runtime-editor-shell-stub"
      data-studio-context={props.studioContext ? "true" : "false"}
      data-vertical-filter={props.verticalFilter ?? "any"}
    >
      stub
    </div>
  ),
}))


import StudioLiveModeWrap from "./StudioLiveModeWrap"


function renderWith(vertical: string | null) {
  return render(
    <MemoryRouter>
      <StudioLiveModeWrap vertical={vertical} />
    </MemoryRouter>,
  )
}


describe("StudioLiveModeWrap", () => {
  it("renders the wrap container", () => {
    renderWith(null)
    expect(screen.getByTestId("studio-live-mode-wrap")).toBeTruthy()
  })

  it("mounts RuntimeEditorShell with studioContext=true", async () => {
    renderWith(null)
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-studio-context")).toBe("true")
  })

  it("forwards null vertical as 'any' filter", () => {
    renderWith(null)
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("any")
  })

  it("forwards a vertical slug as verticalFilter", async () => {
    renderWith("manufacturing")
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("manufacturing")
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-vertical-filter")).toBe("manufacturing")
  })

  it("does NOT mount the placeholder page (cleanup invariant)", () => {
    renderWith(null)
    expect(screen.queryByTestId("studio-live-placeholder")).toBeNull()
  })
})
