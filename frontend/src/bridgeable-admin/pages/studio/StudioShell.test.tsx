/**
 * StudioShell smoke tests — Studio 1a-i.A1.
 *
 * Verifies:
 *   - Renders with rail expanded by default
 *   - Renders Platform overview at /studio
 *   - Renders vertical overview at /studio/manufacturing
 *   - Renders Live placeholder at /studio/live
 *   - Rail collapses to icon strip when an editor is clicked
 *   - Icon strip click re-expands the rail
 *   - Top bar + rail are mounted
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"


// Mock the admin auth so user is always present.
vi.mock("@/bridgeable-admin/lib/admin-auth-context", () => ({
  useAdminAuth: () => ({
    user: {
      id: "u1",
      email: "test@bridgeable.local",
      first_name: "Test",
      last_name: "Operator",
      role: "platform_admin",
      is_super_admin: false,
    },
    loading: false,
    logout: vi.fn(),
  }),
  AdminAuthProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}))


// Mock the verticals service so the scope switcher doesn't fire fetch.
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
        created_at: "2026-05-13T00:00:00",
        updated_at: "2026-05-13T00:00:00",
      },
      {
        slug: "funeral_home",
        display_name: "Funeral Home",
        description: null,
        status: "published",
        icon: null,
        sort_order: 20,
        created_at: "2026-05-13T00:00:00",
        updated_at: "2026-05-13T00:00:00",
      },
    ]),
    get: vi.fn(),
    update: vi.fn(),
  },
}))


// Lightweight stubs for every editor page — the real components pull in
// massive substrate. The shell test cares about layout, not editor
// internals; per the build prompt editor adaptation is 1a-i.B.
// vi.mock() calls must be top-level (vitest auto-hoists).
vi.mock("@/bridgeable-admin/pages/visual-editor/themes/ThemeEditorPage", () => ({
  default: () => <div data-testid="editor-stub-themes">stub</div>,
}))
vi.mock("@/bridgeable-admin/pages/visual-editor/FocusEditorPage", () => ({
  default: () => <div data-testid="editor-stub-focuses">stub</div>,
}))
vi.mock("@/bridgeable-admin/pages/visual-editor/WidgetEditorPage", () => ({
  default: () => <div data-testid="editor-stub-widgets">stub</div>,
}))
vi.mock("@/bridgeable-admin/pages/visual-editor/DocumentsEditorPage", () => ({
  default: () => <div data-testid="editor-stub-documents">stub</div>,
}))
vi.mock("@/bridgeable-admin/pages/visual-editor/ClassEditorPage", () => ({
  default: () => <div data-testid="editor-stub-classes">stub</div>,
}))
vi.mock("@/bridgeable-admin/pages/visual-editor/WorkflowEditorPage", () => ({
  default: () => <div data-testid="editor-stub-workflows">stub</div>,
}))
vi.mock("@/bridgeable-admin/pages/visual-editor/EdgePanelEditorPage", () => ({
  default: () => <div data-testid="editor-stub-edge-panels">stub</div>,
}))
vi.mock("@/bridgeable-admin/pages/visual-editor/RegistryDebugPage", () => ({
  default: () => <div data-testid="editor-stub-registry">stub</div>,
}))
vi.mock("@/bridgeable-admin/pages/visual-editor/PluginRegistryBrowser", () => ({
  default: () => <div data-testid="editor-stub-plugin-registry">stub</div>,
}))


// Stub RuntimeEditorShell — the real component pulls in TenantProviders
// and the entire tenant route tree. Studio 1a-i.A2's Live mode wrap
// mounts RuntimeEditorShell with studioContext=true; verify the prop
// plumbs through, not the runtime editor internals.
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


import StudioShell from "./StudioShell"


function renderAt(pathname: string) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <StudioShell />
    </MemoryRouter>,
  )
}


beforeEach(() => {
  window.localStorage.clear()
})
afterEach(() => {
  window.localStorage.clear()
})


describe("StudioShell — overview surface", () => {
  it("renders Platform overview at /studio", () => {
    renderAt("/studio")
    expect(screen.getByTestId("studio-overview")).toBeTruthy()
    expect(screen.getByTestId("studio-overview").getAttribute("data-active-vertical")).toBe("platform")
    expect(screen.getByTestId("studio-overview-scope-label").textContent).toMatch(/Platform scope/i)
  })

  it("renders vertical overview at /studio/manufacturing", () => {
    renderAt("/studio/manufacturing")
    expect(screen.getByTestId("studio-overview")).toBeTruthy()
    expect(screen.getByTestId("studio-overview").getAttribute("data-active-vertical")).toBe("manufacturing")
    expect(screen.getByTestId("studio-overview-scope-label").textContent).toMatch(/manufacturing/i)
  })
})


describe("StudioShell — Live mode wrap (1a-i.A2)", () => {
  it("renders the Live mode wrap at /studio/live", () => {
    renderAt("/studio/live")
    expect(screen.getByTestId("studio-live-mode-wrap")).toBeTruthy()
  })

  it("top bar reflects live mode at /studio/live", () => {
    renderAt("/studio/live")
    const toggle = screen.getByTestId("studio-mode-toggle")
    expect(toggle.getAttribute("data-active-mode")).toBe("live")
  })

  it("Live mode mounts RuntimeEditorShell with studioContext=true", async () => {
    renderAt("/studio/live")
    // RuntimeEditorShell is lazy-loaded inside StudioLiveModeWrap;
    // await Suspense resolution before asserting on the stub.
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-studio-context")).toBe("true")
  })

  it("Live mode forwards vertical URL segment as verticalFilter", async () => {
    renderAt("/studio/live/manufacturing")
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("manufacturing")
    const stub = await screen.findByTestId("runtime-editor-shell-stub")
    expect(stub.getAttribute("data-vertical-filter")).toBe("manufacturing")
  })

  it("Live mode without vertical forwards verticalFilter=any", () => {
    renderAt("/studio/live")
    const wrap = screen.getByTestId("studio-live-mode-wrap")
    expect(wrap.getAttribute("data-vertical-filter")).toBe("any")
  })

  it("scope switcher renders read-only in Live mode", () => {
    renderAt("/studio/live/manufacturing")
    const sw = screen.getByTestId("studio-scope-switcher")
    expect(sw.getAttribute("data-read-only")).toBe("true")
  })
})


describe("StudioShell — chrome", () => {
  it("mounts top bar + rail + main", () => {
    renderAt("/studio")
    expect(screen.getByTestId("studio-top-bar")).toBeTruthy()
    expect(screen.getByTestId("studio-rail")).toBeTruthy()
    expect(screen.getByTestId("studio-main")).toBeTruthy()
  })

  it("rail starts expanded by default at overview", () => {
    renderAt("/studio")
    const rail = screen.getByTestId("studio-rail")
    expect(rail.getAttribute("data-rail-expanded")).toBe("true")
  })

  it("rail honors localStorage when set to collapsed", () => {
    window.localStorage.setItem("studio.railExpanded", "false")
    renderAt("/studio")
    const rail = screen.getByTestId("studio-rail")
    expect(rail.getAttribute("data-rail-expanded")).toBe("false")
  })
})


describe("StudioShell — rail collapse behavior", () => {
  it("clicking an editor entry collapses the rail to icon strip", async () => {
    renderAt("/studio")
    const themesEntry = screen.getByTestId("studio-rail-entry-themes")
    fireEvent.click(themesEntry)
    await waitFor(() => {
      const rail = screen.getByTestId("studio-rail")
      expect(rail.getAttribute("data-rail-expanded")).toBe("false")
    })
  })

  it("clicking the icon strip expand button re-expands the rail", async () => {
    window.localStorage.setItem("studio.railExpanded", "false")
    renderAt("/studio")
    const expandBtn = screen.getByTestId("studio-rail-expand")
    fireEvent.click(expandBtn)
    await waitFor(() => {
      const rail = screen.getByTestId("studio-rail")
      expect(rail.getAttribute("data-rail-expanded")).toBe("true")
    })
  })

  it("clicking Overview entry does NOT collapse rail", async () => {
    renderAt("/studio")
    const overviewEntry = screen.getByTestId("studio-rail-entry-overview")
    fireEvent.click(overviewEntry)
    const rail = screen.getByTestId("studio-rail")
    expect(rail.getAttribute("data-rail-expanded")).toBe("true")
  })
})


describe("StudioShell — last vertical persistence", () => {
  it("writes activeVertical to localStorage when URL carries one", () => {
    renderAt("/studio/funeral_home")
    expect(window.localStorage.getItem("studio.lastVertical")).toBe("funeral_home")
  })

  it("does not write when at Platform scope", () => {
    renderAt("/studio")
    expect(window.localStorage.getItem("studio.lastVertical")).toBe(null)
  })
})
