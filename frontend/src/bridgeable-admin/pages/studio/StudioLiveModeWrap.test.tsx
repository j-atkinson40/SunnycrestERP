/**
 * StudioLiveModeWrap smoke tests — Studio 1a-i.A2 + Studio test maintenance
 * + Studio 1a-i.B follow-up #3 (vertical via useParams).
 *
 * Verifies:
 *   - Mounts RuntimeEditorShell with studioContext=true
 *   - Reads `:vertical` from URL params (no longer a prop) and forwards
 *     it as RuntimeEditorShell.verticalFilter
 *   - Bare `live` or `live/<tail>` (no vertical) forwards verticalFilter=null
 *   - Renders the wrap test id so Studio shell test can locate it
 *
 * The wrap loads RuntimeEditorShell via React.lazy() (lazy boundary
 * restored in Studio test maintenance, 2026-05-13). Tests await the
 * Suspense resolution via `findByTestId` for assertions on the
 * RuntimeEditorShell stub.
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"


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


function renderAtPath(pathname: string) {
  // Simulate StudioShell's nested-Routes mounting pattern:
  //   <Route path="/studio/*"> consumes /studio (the outer router level)
  //     <Route path="live/:vertical/*"> consumes live/<vertical>
  //     <Route path="live/*"> or <Route path="live"> for no-vertical cases
  // The wrap reads useParams<{ vertical }>() based on the matched route.
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <Routes>
        <Route path="/studio/*" element={
          <Routes>
            <Route path="live/:vertical/*" element={<StudioLiveModeWrap />} />
            <Route path="live/*" element={<StudioLiveModeWrap />} />
            <Route path="live" element={<StudioLiveModeWrap />} />
          </Routes>
        } />
      </Routes>
    </MemoryRouter>,
  )
}


describe("StudioLiveModeWrap", () => {
  it("renders the wrap container", () => {
    renderAtPath("/studio/live")
    expect(screen.getByTestId("studio-live-mode-wrap")).toBeTruthy()
  })

  it("mounts RuntimeEditorShell with studioContext=true", async () => {
    renderAtPath("/studio/live")
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-studio-context")).toBe("true")
  })

  it("bare /studio/live forwards verticalFilter=any (null vertical)", () => {
    renderAtPath("/studio/live")
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("any")
  })

  it("/studio/live/manufacturing forwards verticalFilter=manufacturing", async () => {
    renderAtPath("/studio/live/manufacturing")
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("manufacturing")
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-vertical-filter")).toBe("manufacturing")
  })

  it("/studio/live/manufacturing/dispatch/funeral-schedule forwards verticalFilter=manufacturing (deep tail)", async () => {
    renderAtPath("/studio/live/manufacturing/dispatch/funeral-schedule")
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("manufacturing")
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-vertical-filter")).toBe("manufacturing")
  })

  it("/studio/live/dispatch/funeral-schedule matches live/:vertical/* greedily (deep tail flows through)", () => {
    // React Router scores `live/:vertical/*` higher than `live/*` for any
    // path with at least two segments after `live`, so the `:vertical`
    // param greedily captures "dispatch" here. This is the pre-resolution
    // state — the picker (TenantUserPicker) detects the unresolved-vertical
    // case post-impersonation by inspecting `useLocation().pathname` and
    // replaces "dispatch" with the actual resolved vertical via
    // pickup-and-replay (Step 4). Under that flow the URL becomes
    // /studio/live/<resolved>/dispatch/funeral-schedule and the inner
    // tenant route tree then matches `dispatch/funeral-schedule` cleanly.
    renderAtPath("/studio/live/dispatch/funeral-schedule")
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("dispatch")
  })

  it("does NOT mount the placeholder page (cleanup invariant)", () => {
    renderAtPath("/studio/live")
    expect(screen.queryByTestId("studio-live-placeholder")).toBeNull()
  })
})
