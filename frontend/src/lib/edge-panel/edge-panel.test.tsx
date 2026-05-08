/**
 * R-5.0 — edge panel vitest coverage.
 *
 * Tests cover:
 *   - EdgePanelProvider — initial state, open/close/toggle, auth gating
 *   - EdgePanelHandle — render conditions (auth gated, hidden when
 *     editor edit-mode active, hidden when panel open)
 *   - EdgePanel — open/close transform, page navigation via dots,
 *     empty composition fallback
 *   - useEdgePanelKeyboard — Cmd+Shift+E toggles, Esc closes,
 *     ArrowLeft/Right cycle pages, typing-into-input gate
 *   - useEdgePanelGesture — pointerdown→pointerup leftward swipe opens
 *   - CompositionRenderer — edge-panel-label + edge-panel-divider
 *     primitive render branches
 */
import { render, screen, act, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"


// ─── Module mocks ─────────────────────────────────────────────────


const mockResolveEdgePanel = vi.fn()
const mockGetTenantConfig = vi.fn()


vi.mock("./edge-panel-service", () => ({
  resolveEdgePanel: (...args: unknown[]) => mockResolveEdgePanel(...args),
  getEdgePanelTenantConfig: (...args: unknown[]) =>
    mockGetTenantConfig(...args),
  getEdgePanelPreferences: vi.fn(),
  patchEdgePanelPreferences: vi.fn(),
}))


const mockUseAuth = vi.fn()
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => mockUseAuth(),
}))


// CompositionRenderer is heavy; mock with a stub for the EdgePanel
// rendering tests. The unit tests for the dispatch branches live
// inside the dedicated dispatch tests below.
vi.mock("@/lib/visual-editor/compositions/CompositionRenderer", () => ({
  CompositionRenderer: ({ composition }: { composition: { rows: unknown[] } }) => (
    <div data-testid="mock-composition-renderer">
      rows={composition.rows.length}
    </div>
  ),
}))


// ─── Imports happen AFTER mocks ───────────────────────────────────


import {
  EdgePanelProvider,
  useEdgePanel,
  useEdgePanelOptional,
} from "./EdgePanelProvider"
import { EdgePanel } from "./EdgePanel"
import { EdgePanelHandle } from "./EdgePanelHandle"
import { useEdgePanelKeyboard } from "./useEdgePanelKeyboard"
import { useEdgePanelGesture } from "./useEdgePanelGesture"


function makeResolved(pages: Array<{ page_id: string; name: string }> = []) {
  return {
    panel_key: "default",
    vertical: "manufacturing",
    tenant_id: null,
    source: pages.length > 0 ? "platform_default" : null,
    source_id: null,
    source_version: null,
    pages: pages.map((p) => ({
      page_id: p.page_id,
      name: p.name,
      rows: [],
      canvas_config: {},
    })),
    canvas_config: {},
  }
}


function setAuthLoaded() {
  mockUseAuth.mockReturnValue({
    user: { id: "u1", email: "u@x.com", role_slug: "admin" },
    company: { id: "co1", slug: "testco", vertical: "manufacturing" },
    isLoading: false,
  })
}


function setAuthLoading() {
  mockUseAuth.mockReturnValue({ user: null, company: null, isLoading: true })
}


beforeEach(() => {
  mockResolveEdgePanel.mockReset()
  mockGetTenantConfig.mockReset()
  mockUseAuth.mockReset()
  setAuthLoaded()
  mockResolveEdgePanel.mockResolvedValue(
    makeResolved([{ page_id: "p1", name: "Quick Actions" }]),
  )
  mockGetTenantConfig.mockResolvedValue({ enabled: true, width: 320 })
})

afterEach(() => {
  document.body.removeAttribute("data-runtime-editor-mode")
  document.body.removeAttribute("data-edge-panel-open")
})


// ─── EdgePanelProvider ────────────────────────────────────────────


describe("EdgePanelProvider", () => {
  function Probe({ onState }: { onState: (s: ReturnType<typeof useEdgePanel>) => void }) {
    const ctx = useEdgePanel()
    onState(ctx)
    return null
  }

  it("starts closed and resolves composition on mount", async () => {
    let captured: ReturnType<typeof useEdgePanel> | null = null
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Probe onState={(s) => (captured = s)} />
        </EdgePanelProvider>,
      )
    })
    // Wait for resolve to settle.
    await act(async () => {
      await Promise.resolve()
    })
    expect(captured).not.toBeNull()
    expect(captured!.isOpen).toBe(false)
    expect(captured!.tenantConfig.width).toBe(320)
    expect(mockResolveEdgePanel).toHaveBeenCalledWith("default")
  })

  it("openPanel + closePanel toggles isOpen", async () => {
    let captured: ReturnType<typeof useEdgePanel> | null = null
    render(
      <EdgePanelProvider>
        <Probe onState={(s) => (captured = s)} />
      </EdgePanelProvider>,
    )
    await act(async () => {
      await Promise.resolve()
    })
    expect(captured!.isOpen).toBe(false)
    await act(async () => {
      captured!.openPanel()
    })
    expect(captured!.isOpen).toBe(true)
    await act(async () => {
      captured!.closePanel()
    })
    expect(captured!.isOpen).toBe(false)
  })

  it("does not fetch composition while auth is loading", async () => {
    setAuthLoading()
    render(
      <EdgePanelProvider>
        <div>child</div>
      </EdgePanelProvider>,
    )
    await act(async () => {
      await Promise.resolve()
    })
    expect(mockResolveEdgePanel).not.toHaveBeenCalled()
  })

  it("useEdgePanelOptional returns null outside provider tree", () => {
    let captured: ReturnType<typeof useEdgePanelOptional> | null | undefined =
      undefined

    function Probe() {
      const ctx = useEdgePanelOptional()
      captured = ctx
      return null
    }

    render(<Probe />)
    expect(captured).toBeNull()
  })

  it("sets data-edge-panel-open on body when open", async () => {
    let captured: ReturnType<typeof useEdgePanel> | null = null
    render(
      <EdgePanelProvider>
        <Probe onState={(s) => (captured = s)} />
      </EdgePanelProvider>,
    )
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      captured!.openPanel()
    })
    expect(document.body.getAttribute("data-edge-panel-open")).toBe("true")
    await act(async () => {
      captured!.closePanel()
    })
    expect(document.body.getAttribute("data-edge-panel-open")).toBeNull()
  })
})


// ─── EdgePanelHandle ──────────────────────────────────────────────


describe("EdgePanelHandle", () => {
  it("renders a clickable handle when ready + enabled + closed", async () => {
    await act(async () => {
      render(
        <EdgePanelProvider>
          <EdgePanelHandle />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByTestId("edge-panel-handle")).toBeInTheDocument()
  })

  it("renders nothing when tenantConfig.enabled is false", async () => {
    mockGetTenantConfig.mockResolvedValue({ enabled: false, width: 320 })
    await act(async () => {
      render(
        <EdgePanelProvider>
          <EdgePanelHandle />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.queryByTestId("edge-panel-handle")).toBeNull()
  })

  it("hides when runtime-editor mode is edit", async () => {
    document.body.setAttribute("data-runtime-editor-mode", "edit")
    await act(async () => {
      render(
        <EdgePanelProvider>
          <EdgePanelHandle />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.queryByTestId("edge-panel-handle")).toBeNull()
  })

  it("hides when panel is open", async () => {
    function Trigger() {
      const ctx = useEdgePanel()
      return (
        <div>
          <button onClick={ctx.openPanel} data-testid="open-trig">
            open
          </button>
          <EdgePanelHandle />
        </div>
      )
    }
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Trigger />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    // Initially handle is present.
    expect(screen.queryByTestId("edge-panel-handle")).toBeInTheDocument()
    await act(async () => {
      fireEvent.click(screen.getByTestId("open-trig"))
    })
    expect(screen.queryByTestId("edge-panel-handle")).toBeNull()
  })
})


// ─── EdgePanel ────────────────────────────────────────────────────


describe("EdgePanel", () => {
  it("renders pages + dots when composition has multiple pages", async () => {
    mockResolveEdgePanel.mockResolvedValue(
      makeResolved([
        { page_id: "p1", name: "Quick" },
        { page_id: "p2", name: "Dispatch" },
      ]),
    )
    function Trigger() {
      const ctx = useEdgePanel()
      return (
        <div>
          <button onClick={ctx.openPanel} data-testid="open-trig">
            open
          </button>
          <EdgePanel />
        </div>
      )
    }
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Trigger />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("open-trig"))
    })
    expect(screen.getByTestId("edge-panel")).toBeInTheDocument()
    expect(screen.getByTestId("edge-panel-dots")).toBeInTheDocument()
    expect(screen.getByTestId("edge-panel-dot-0")).toHaveAttribute(
      "data-active",
      "true",
    )
    expect(screen.getByTestId("edge-panel-dot-1")).toHaveAttribute(
      "data-active",
      "false",
    )
  })

  it("dot click switches active page", async () => {
    mockResolveEdgePanel.mockResolvedValue(
      makeResolved([
        { page_id: "p1", name: "A" },
        { page_id: "p2", name: "B" },
      ]),
    )
    function Trigger() {
      const ctx = useEdgePanel()
      return (
        <div>
          <button onClick={ctx.openPanel} data-testid="open-trig">
            open
          </button>
          <EdgePanel />
        </div>
      )
    }
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Trigger />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("open-trig"))
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("edge-panel-dot-1"))
    })
    expect(screen.getByTestId("edge-panel-dot-1")).toHaveAttribute(
      "data-active",
      "true",
    )
  })

  it("dots only render when 2+ pages", async () => {
    mockResolveEdgePanel.mockResolvedValue(
      makeResolved([{ page_id: "p1", name: "Solo" }]),
    )
    function Trigger() {
      const ctx = useEdgePanel()
      return (
        <div>
          <button onClick={ctx.openPanel} data-testid="open-trig">
            open
          </button>
          <EdgePanel />
        </div>
      )
    }
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Trigger />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("open-trig"))
    })
    expect(screen.queryByTestId("edge-panel-dots")).toBeNull()
  })

  it("renders empty placeholder when composition has no pages", async () => {
    mockResolveEdgePanel.mockResolvedValue(makeResolved([]))
    function Trigger() {
      const ctx = useEdgePanel()
      return (
        <div>
          <button onClick={ctx.openPanel} data-testid="open-trig">
            open
          </button>
          <EdgePanel />
        </div>
      )
    }
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Trigger />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("open-trig"))
    })
    expect(screen.getByTestId("edge-panel-empty")).toBeInTheDocument()
  })
})


// ─── Keyboard hook ────────────────────────────────────────────────


describe("useEdgePanelKeyboard", () => {
  function HostWithKeyboard() {
    useEdgePanelKeyboard()
    const ctx = useEdgePanel()
    return (
      <div>
        <span data-testid="open-state">{ctx.isOpen ? "open" : "closed"}</span>
        <span data-testid="page-idx">{ctx.currentPageIndex}</span>
      </div>
    )
  }

  it("Cmd+Shift+E toggles open", async () => {
    await act(async () => {
      render(
        <EdgePanelProvider>
          <HostWithKeyboard />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByTestId("open-state").textContent).toBe("closed")
    await act(async () => {
      fireEvent.keyDown(window, { key: "e", metaKey: true, shiftKey: true })
    })
    expect(screen.getByTestId("open-state").textContent).toBe("open")
    await act(async () => {
      fireEvent.keyDown(window, { key: "e", metaKey: true, shiftKey: true })
    })
    expect(screen.getByTestId("open-state").textContent).toBe("closed")
  })

  it("Esc closes when open", async () => {
    function Trigger() {
      const ctx = useEdgePanel()
      useEdgePanelKeyboard()
      return (
        <div>
          <button onClick={ctx.openPanel} data-testid="open-trig">
            open
          </button>
          <span data-testid="open-state">{ctx.isOpen ? "open" : "closed"}</span>
        </div>
      )
    }
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Trigger />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("open-trig"))
    })
    expect(screen.getByTestId("open-state").textContent).toBe("open")
    await act(async () => {
      fireEvent.keyDown(window, { key: "Escape" })
    })
    expect(screen.getByTestId("open-state").textContent).toBe("closed")
  })

  it("ArrowRight cycles pages when open", async () => {
    mockResolveEdgePanel.mockResolvedValue(
      makeResolved([
        { page_id: "p1", name: "A" },
        { page_id: "p2", name: "B" },
      ]),
    )
    function Trigger() {
      const ctx = useEdgePanel()
      useEdgePanelKeyboard()
      return (
        <div>
          <button onClick={ctx.openPanel} data-testid="open-trig">
            open
          </button>
          <span data-testid="page-idx">{ctx.currentPageIndex}</span>
        </div>
      )
    }
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Trigger />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("open-trig"))
    })
    expect(screen.getByTestId("page-idx").textContent).toBe("0")
    await act(async () => {
      fireEvent.keyDown(window, { key: "ArrowRight" })
    })
    expect(screen.getByTestId("page-idx").textContent).toBe("1")
    // Wraps to 0.
    await act(async () => {
      fireEvent.keyDown(window, { key: "ArrowRight" })
    })
    expect(screen.getByTestId("page-idx").textContent).toBe("0")
  })

  it("ignores Cmd+Shift+E when typing in INPUT", async () => {
    function Trigger() {
      const ctx = useEdgePanel()
      useEdgePanelKeyboard()
      return (
        <div>
          <input data-testid="input-target" />
          <span data-testid="open-state">{ctx.isOpen ? "open" : "closed"}</span>
        </div>
      )
    }
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Trigger />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    const input = screen.getByTestId("input-target")
    await act(async () => {
      input.focus()
      fireEvent.keyDown(input, {
        key: "e",
        metaKey: true,
        shiftKey: true,
      })
    })
    expect(screen.getByTestId("open-state").textContent).toBe("closed")
  })
})


// ─── Gesture hook ─────────────────────────────────────────────────


describe("useEdgePanelGesture", () => {
  it("opens on right-edge leftward swipe", async () => {
    function Host() {
      const ctx = useEdgePanel()
      useEdgePanelGesture({ edgeZonePx: 24, thresholdPx: 50 })
      return <span data-testid="open-state">{ctx.isOpen ? "open" : "closed"}</span>
    }
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1000,
    })
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Host />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      // Pointer down within right edge zone.
      const downEv = new PointerEvent("pointerdown", {
        clientX: 990,
        clientY: 400,
        pointerId: 1,
      })
      window.dispatchEvent(downEv)
      // Pointer up significantly leftward.
      const upEv = new PointerEvent("pointerup", {
        clientX: 800,
        clientY: 405,
        pointerId: 1,
      })
      window.dispatchEvent(upEv)
    })
    expect(screen.getByTestId("open-state").textContent).toBe("open")
  })

  it("does NOT open on small leftward swipe (below threshold)", async () => {
    function Host() {
      const ctx = useEdgePanel()
      useEdgePanelGesture({ edgeZonePx: 24, thresholdPx: 50 })
      return <span data-testid="open-state">{ctx.isOpen ? "open" : "closed"}</span>
    }
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1000,
    })
    await act(async () => {
      render(
        <EdgePanelProvider>
          <Host />
        </EdgePanelProvider>,
      )
    })
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      const downEv = new PointerEvent("pointerdown", {
        clientX: 990,
        clientY: 400,
        pointerId: 2,
      })
      window.dispatchEvent(downEv)
      const upEv = new PointerEvent("pointerup", {
        clientX: 970,
        clientY: 400,
        pointerId: 2,
      })
      window.dispatchEvent(upEv)
    })
    expect(screen.getByTestId("open-state").textContent).toBe("closed")
  })
})


// ─── CompositionRenderer edge-panel-* primitive branches ─────────


describe("CompositionRenderer edge-panel primitives", () => {
  it("renders edge-panel-label with text from prop_overrides", async () => {
    // Unmock the renderer for this branch test.
    vi.doUnmock("@/lib/visual-editor/compositions/CompositionRenderer")
    const mod = await import(
      "@/lib/visual-editor/compositions/CompositionRenderer"
    )
    const { CompositionRenderer } = mod
    render(
      <CompositionRenderer
        composition={{
          focus_type: "default",
          vertical: null,
          tenant_id: null,
          source: null,
          source_id: null,
          source_version: null,
          rows: [
            {
              row_id: "r1",
              column_count: 12,
              row_height: "auto",
              column_widths: null,
              nested_rows: null,
              placements: [
                {
                  placement_id: "p-label",
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  component_kind: "edge-panel-label" as any,
                  component_name: "default",
                  starting_column: 0,
                  column_span: 12,
                  prop_overrides: { text: "QUICK ACTIONS" },
                  display_config: {},
                  nested_rows: null,
                },
              ],
            },
          ],
          canvas_config: {},
        }}
      />,
    )
    // The label renders its text.
    expect(
      screen.getByTestId("edge-panel-label").textContent,
    ).toContain("QUICK ACTIONS")
  })

  it("renders edge-panel-divider as a hairline", async () => {
    vi.doUnmock("@/lib/visual-editor/compositions/CompositionRenderer")
    const mod = await import(
      "@/lib/visual-editor/compositions/CompositionRenderer"
    )
    const { CompositionRenderer } = mod
    render(
      <CompositionRenderer
        composition={{
          focus_type: "default",
          vertical: null,
          tenant_id: null,
          source: null,
          source_id: null,
          source_version: null,
          rows: [
            {
              row_id: "r-div",
              column_count: 12,
              row_height: "auto",
              column_widths: null,
              nested_rows: null,
              placements: [
                {
                  placement_id: "p-div",
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  component_kind: "edge-panel-divider" as any,
                  component_name: "default",
                  starting_column: 0,
                  column_span: 12,
                  prop_overrides: {},
                  display_config: {},
                  nested_rows: null,
                },
              ],
            },
          ],
          canvas_config: {},
        }}
      />,
    )
    expect(screen.getByTestId("edge-panel-divider")).toBeInTheDocument()
  })
})
