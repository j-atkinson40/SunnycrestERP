/**
 * StudioLiveModeWrap smoke tests — Studio 1a-i.A2 + Studio test maintenance
 * + Studio 1a-i.B follow-up #3 (vertical via useParams)
 * + Studio 1a-i.B follow-up #4 (verticals-registry disambiguation).
 *
 * Verifies:
 *   - Mounts RuntimeEditorShell with studioContext=true
 *   - Disambiguates the first post-`live` segment against the verticals
 *     registry: known slug → vertical scope; unknown slug → tail
 *   - Bare `/studio/live` reports vertical=null + tail=""
 *   - Blocks initial render until verticals load resolves
 *
 * The wrap loads RuntimeEditorShell via React.lazy() and useVerticals()
 * which fires verticalsService.list() on mount. Tests mock both.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
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


vi.mock("@/bridgeable-admin/services/verticals-service", () => ({
  verticalsService: {
    list: vi.fn(async () => [
      {
        slug: "manufacturing",
        display_name: "Manufacturing",
        description: null,
        status: "published",
        icon: null,
        sort_order: 1,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        slug: "funeral_home",
        display_name: "Funeral Home",
        description: null,
        status: "published",
        icon: null,
        sort_order: 2,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        slug: "cemetery",
        display_name: "Cemetery",
        description: null,
        status: "published",
        icon: null,
        sort_order: 3,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        slug: "crematory",
        display_name: "Crematory",
        description: null,
        status: "published",
        icon: null,
        sort_order: 4,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]),
  },
}))


import StudioLiveModeWrap from "./StudioLiveModeWrap"
import { __resetVerticalsCacheForTests } from "@/bridgeable-admin/hooks/useVerticals"


beforeEach(() => {
  __resetVerticalsCacheForTests()
})


function renderAtPath(pathname: string) {
  // Simulate StudioShell's nested-Routes mounting pattern:
  //   <Route path="/studio/*"> consumes /studio (the outer router level)
  //     <Route path="live/:vertical/*"> consumes live/<vertical>
  //     <Route path="live/*"> or <Route path="live"> for no-vertical cases
  // The wrap uses useLocation() to read the full pathname (does NOT
  // depend on useParams() any more — disambiguation is registry-driven).
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
  it("renders the wrap container", async () => {
    renderAtPath("/studio/live")
    // First mount: loading state.
    expect(screen.getByTestId("studio-live-mode-wrap")).toBeTruthy()
    // Once verticals load resolves, vertical-filter data attribute is present.
    await waitFor(() => {
      const wrap = screen.getByTestId("studio-live-mode-wrap")
      expect(wrap.getAttribute("data-loading")).not.toBe("true")
    })
  })

  it("mounts RuntimeEditorShell with studioContext=true", async () => {
    renderAtPath("/studio/live")
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-studio-context")).toBe("true")
  })

  it("bare /studio/live forwards verticalFilter=any (null vertical) + empty tail", async () => {
    renderAtPath("/studio/live")
    await waitFor(() => {
      const wrap = screen.getByTestId("studio-live-mode-wrap")
      expect(wrap.getAttribute("data-loading")).not.toBe("true")
    })
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("any")
    expect(wrap.getAttribute("data-deep-tail")).toBe("none")
  })

  it("/studio/live/manufacturing forwards verticalFilter=manufacturing (known slug, no tail)", async () => {
    renderAtPath("/studio/live/manufacturing")
    await waitFor(() => {
      const wrap = screen.getByTestId("studio-live-mode-wrap")
      expect(wrap.getAttribute("data-loading")).not.toBe("true")
    })
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("manufacturing")
    expect(wrap.getAttribute("data-deep-tail")).toBe("none")
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-vertical-filter")).toBe("manufacturing")
  })

  it("/studio/live/manufacturing/dashboard forwards vertical=manufacturing + tail=dashboard", async () => {
    renderAtPath("/studio/live/manufacturing/dashboard")
    await waitFor(() => {
      const wrap = screen.getByTestId("studio-live-mode-wrap")
      expect(wrap.getAttribute("data-loading")).not.toBe("true")
    })
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("manufacturing")
    expect(wrap.getAttribute("data-deep-tail")).toBe("dashboard")
  })

  it("/studio/live/dispatch/funeral-schedule (spurious vertical capture) → vertical=null + tail=dispatch/funeral-schedule", async () => {
    // Follow-up #4 canonical bug fix. React Router captures `:vertical
    // = "dispatch"` greedily, but `dispatch` is NOT a known vertical
    // slug. Wrap disambiguates via verticals registry: vertical is
    // null + the full post-`live` content is the tail.
    renderAtPath("/studio/live/dispatch/funeral-schedule")
    await waitFor(() => {
      const wrap = screen.getByTestId("studio-live-mode-wrap")
      expect(wrap.getAttribute("data-loading")).not.toBe("true")
    })
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("any")
    expect(wrap.getAttribute("data-deep-tail")).toBe("dispatch/funeral-schedule")
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-vertical-filter")).toBe("any")
  })

  it("/studio/live/dispatch (single spurious segment) → vertical=null + tail=dispatch", async () => {
    renderAtPath("/studio/live/dispatch")
    await waitFor(() => {
      const wrap = screen.getByTestId("studio-live-mode-wrap")
      expect(wrap.getAttribute("data-loading")).not.toBe("true")
    })
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("any")
    expect(wrap.getAttribute("data-deep-tail")).toBe("dispatch")
  })

  it("blocks initial render with data-loading until verticals resolve", () => {
    renderAtPath("/studio/live/manufacturing")
    // Synchronously after render the hook hasn't resolved yet.
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-loading")).toBe("true")
    // The vertical-filter data attribute is not yet present.
    expect(wrap.getAttribute("data-vertical-filter")).toBeNull()
  })

  it("does NOT mount the placeholder page (cleanup invariant)", () => {
    renderAtPath("/studio/live")
    expect(screen.queryByTestId("studio-live-placeholder")).toBeNull()
  })
})
