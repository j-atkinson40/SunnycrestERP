/**
 * Arc-3.x-deep-link-retrofit — WorkflowEditorPage return-to banner tests.
 *
 * Verifies bidirectional deep-link contract (mirrors Arc 3a
 * FocusEditorPage canon):
 * - Banner hidden when no return_to URL param.
 * - Banner renders when return_to present.
 * - Click navigates to decoded return_to value.
 * - When launched with `?workflow_type=X`, initial workflowType seeds
 *   from URL.
 * - When launched with `?scope=platform_default`, initial scope seeds.
 *
 * Mocks `workflowTemplatesService` so tests don't hit the network.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"

// Phase B sub-arc B-2 — palette renders from the registry; populate it.
import "@/lib/visual-editor/registry/auto-register"
import WorkflowEditorPage from "./WorkflowEditorPage"


vi.mock(
  "@/bridgeable-admin/services/workflow-templates-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/bridgeable-admin/services/workflow-templates-service")
    >("@/bridgeable-admin/services/workflow-templates-service")
    return {
      ...actual,
      workflowTemplatesService: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
        update: vi.fn(),
        create: vi.fn(),
        getDependentForks: vi.fn().mockResolvedValue([]),
      },
    }
  },
)


function LocationProbe({ onLocation }: { onLocation: (path: string) => void }) {
  const loc = useLocation()
  onLocation(loc.pathname + loc.search)
  return null
}


afterEach(() => {
  vi.clearAllMocks()
})


describe("WorkflowEditorPage — Arc-3.x-deep-link-retrofit return-to banner", () => {
  it("does NOT render return-to banner when no return_to URL param", async () => {
    const result = render(
      <MemoryRouter initialEntries={["/visual-editor/workflows"]}>
        <WorkflowEditorPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(result.getByTestId("workflow-editor-page")).toBeTruthy()
    })
    expect(
      result.queryByTestId("workflow-editor-return-to-banner"),
    ).toBeFalsy()
  })

  it("renders 'Back to runtime editor' affordance when return_to param present", async () => {
    const returnTo = encodeURIComponent(
      "/bridgeable-admin/runtime-editor/?tenant=hopkins-fh&user=u1",
    )
    const result = render(
      <MemoryRouter
        initialEntries={[
          `/visual-editor/workflows?return_to=${returnTo}&workflow_type=month_end_close&scope=vertical_default`,
        ]}
      >
        <WorkflowEditorPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(
        result.getByTestId("workflow-editor-return-to-banner"),
      ).toBeTruthy()
    })
    expect(
      result.getByTestId("workflow-editor-return-to-back"),
    ).toBeTruthy()
  })

  it("click 'Back to runtime editor' navigates to decoded return_to value", async () => {
    let capturedPath = ""
    const returnTo =
      "/bridgeable-admin/runtime-editor/?tenant=hopkins-fh&user=u1"
    const encoded = encodeURIComponent(returnTo)

    const result = render(
      <MemoryRouter
        initialEntries={[
          `/visual-editor/workflows?return_to=${encoded}`,
        ]}
      >
        <Routes>
          <Route
            path="/visual-editor/workflows"
            element={
              <>
                <LocationProbe onLocation={(p) => (capturedPath = p)} />
                <WorkflowEditorPage />
              </>
            }
          />
          <Route
            path="/bridgeable-admin/runtime-editor/"
            element={
              <LocationProbe onLocation={(p) => (capturedPath = p)} />
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    const backBtn = await waitFor(() =>
      result.getByTestId("workflow-editor-return-to-back"),
    )
    fireEvent.click(backBtn)
    await waitFor(() => {
      expect(capturedPath).toContain("/bridgeable-admin/runtime-editor")
      expect(capturedPath).toContain("tenant=hopkins-fh")
    })
  })

  it("decodes a malformed return_to gracefully (falls back to raw)", async () => {
    let capturedPath = ""
    // %ZZ is not a valid escape; component falls back to raw navigate.
    const malformed = "/bridgeable-admin/runtime-editor/%ZZ"
    const result = render(
      <MemoryRouter
        initialEntries={[`/visual-editor/workflows?return_to=${malformed}`]}
      >
        <Routes>
          <Route
            path="/visual-editor/workflows"
            element={<WorkflowEditorPage />}
          />
          <Route
            path="*"
            element={
              <LocationProbe onLocation={(p) => (capturedPath = p)} />
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    const backBtn = await waitFor(() =>
      result.getByTestId("workflow-editor-return-to-back"),
    )
    fireEvent.click(backBtn)
    await waitFor(() => {
      // Navigation fired (router moved off the workflow editor route);
      // exact path encoding is implementation-defined when decode fails.
      expect(capturedPath).toBeTruthy()
    })
  })
})


// ── Phase B sub-arc B-1 — graph-canvas integration ────────────────────
//
// Asserts the page mounts GraphCanvas (not the pre-B-1 <ol><li> list),
// that palette-add mutations render through the graph surface as
// positioned node cards, and that selection wiring opens the config
// pane. dnd-kit pointer-drag commit math is covered in canvas-layout +
// GraphCanvas unit suites; per Q-40 pointer-drag DOM defers to Playwright.

import { workflowTemplatesService } from "@/bridgeable-admin/services/workflow-templates-service"

const TEST_TEMPLATE_META = {
  id: "wt_1",
  scope: "platform_default" as const,
  vertical: null,
  workflow_type: "test_wf",
  display_name: "Test Workflow",
  description: null,
  version: 1,
  is_active: true,
  created_at: "2026-05-27T00:00:00Z",
  updated_at: "2026-05-27T00:00:00Z",
  created_by: null,
  updated_by: null,
}

const TEST_TEMPLATE_FULL = {
  ...TEST_TEMPLATE_META,
  canvas_state: {
    version: 1,
    nodes: [
      { id: "n_node_1", type: "start", label: "Begin", position: { x: 40, y: 40 }, config: {} },
      { id: "n_node_2", type: "action", label: "Work", position: { x: 40, y: 200 }, config: {} },
    ],
    edges: [{ id: "e_n_node_1_n_node_2", source: "n_node_1", target: "n_node_2" }],
  },
}

function renderWithTemplate() {
  vi.mocked(workflowTemplatesService.list).mockResolvedValue([TEST_TEMPLATE_META])
  vi.mocked(workflowTemplatesService.get).mockResolvedValue(TEST_TEMPLATE_FULL)
  return render(
    <MemoryRouter
      initialEntries={[
        "/visual-editor/workflows?scope=platform_default&workflow_type=test_wf",
      ]}
    >
      <WorkflowEditorPage />
    </MemoryRouter>,
  )
}

describe("WorkflowEditorPage — B-1 graph-canvas integration", () => {
  it("mounts GraphCanvas (graph surface) instead of the pre-B-1 node list", async () => {
    const result = renderWithTemplate()
    await waitFor(() => {
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument()
    })
    // Edge layer present; node cards positioned via inline style.
    expect(result.getByTestId("graph-canvas-edges")).toBeInTheDocument()
    const n2 = result.getByTestId("canvas-node-n_node_2")
    expect(n2.style.top).toBe("200px")
  })

  it("renders the authored edge as an SVG path in the graph surface", async () => {
    const result = renderWithTemplate()
    const edge = await waitFor(() =>
      result.getByTestId("edge-e_n_node_1_n_node_2"),
    )
    expect(edge.querySelector("path")).toBeInTheDocument()
  })

  it("B-3 completion: a seeded node with no config.nodeShape renders its registry genre shape (start → circle)", async () => {
    // End-to-end: the page threads the real getByName-backed
    // resolveTypeDefaultShape into GraphCanvas, so a seeded start node
    // (config:{}) renders circle — the funeral_cascade fix proven through
    // the page (auto-register is imported at the top of this file).
    const result = renderWithTemplate()
    const startNode = await waitFor(() =>
      result.getByTestId("canvas-node-n_node_1"),
    )
    expect(startNode).toHaveAttribute("data-node-shape", "circle")
  })

  it("B-4: the reachability-overlay toggle is reachable through the page (default off)", async () => {
    const result = renderWithTemplate()
    const toggle = await waitFor(() =>
      result.getByTestId("trace-overlay-toggle"),
    )
    expect(toggle).toHaveAttribute("data-trace-overlay", "off")
  })

  it("palette-add renders a new positioned node card through GraphCanvas", async () => {
    const result = renderWithTemplate()
    await waitFor(() => {
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument()
    })
    fireEvent.click(result.getByTestId("palette-action"))
    await waitFor(() => {
      // 3rd node id auto-generated as n_node_3 (stack-below-lowest).
      expect(result.getByTestId("canvas-node-n_node_3")).toBeInTheDocument()
    })
    // Auto-placed below the lowest existing node (y 200 + stride 120).
    expect(result.getByTestId("canvas-node-n_node_3").style.top).toBe("320px")
  })

  it("clicking a node card opens the node-config pane (selection wiring)", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    fireEvent.click(n1)
    await waitFor(() => {
      expect(n1).toHaveAttribute("data-selected", "true")
    })
  })
})


// ── Phase B sub-arc B-2 — registry-driven palette (16 → 32) ───────────
//
// Asserts the palette renders from getByType("workflow-node") (all 32
// registrations) instead of the pre-B-2 hardcoded 16-tuple, and that
// node types absent from the old tuple (e.g. create_record) are now
// addable. Adding a registry-typed node flows into the B-1 GraphCanvas
// without GraphCanvas changes (§2.B.2 invariant).

describe("WorkflowEditorPage — B-2 registry-driven palette", () => {
  it("renders all 32 registered workflow-node types in the palette", async () => {
    const result = renderWithTemplate()
    await waitFor(() => {
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument()
    })
    const buttons = result
      .getAllByRole("button")
      .filter((b) => b.getAttribute("data-testid")?.startsWith("palette-"))
    expect(buttons.length).toBe(32)
  })

  it("exposes node types absent from the pre-B-2 16-tuple (create_record, wait, output)", async () => {
    const result = renderWithTemplate()
    await waitFor(() => {
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument()
    })
    // None of these were in the old hardcoded palette.
    expect(result.getByTestId("palette-create_record")).toBeInTheDocument()
    expect(result.getByTestId("palette-wait")).toBeInTheDocument()
    expect(result.getByTestId("palette-output")).toBeInTheDocument()
  })

  it("palette-add of a newly-registry-exposed type renders it on the graph canvas", async () => {
    const result = renderWithTemplate()
    await waitFor(() => {
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument()
    })
    fireEvent.click(result.getByTestId("palette-create_record"))
    await waitFor(() => {
      // 3rd node (2 seeded) auto-generated as n_node_3 with the clicked type.
      const node = result.getByTestId("canvas-node-n_node_3")
      expect(node).toHaveAttribute("data-node-type", "create_record")
    })
  })
})


// ── Phase B sub-arc B-5 — selection-driven right-rail dispatch ────────
//
// 4-state selection (none/node/edge/background) drives the right rail:
// none → "Nothing selected"; node → NodeConfigForm; edge →
// EdgeConditionInspector; background → TriggerInspector.

describe("WorkflowEditorPage — B-5 selection-driven inspector dispatch", () => {
  it("initial selection is 'none' → Nothing-selected placeholder", async () => {
    const result = renderWithTemplate()
    await waitFor(() =>
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument(),
    )
    expect(result.getByTestId("workflow-inspector-empty")).toBeInTheDocument()
    expect(result.queryByTestId("node-config-form")).not.toBeInTheDocument()
  })

  it("node-click → NodeConfigForm (B-3 inspector, unchanged)", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    fireEvent.click(n1)
    await waitFor(() =>
      expect(result.getByTestId("node-config-form")).toBeInTheDocument(),
    )
    expect(result.queryByTestId("workflow-inspector-empty")).not.toBeInTheDocument()
  })

  it("edge-click → EdgeConditionInspector", async () => {
    const result = renderWithTemplate()
    const edgeHit = await waitFor(() =>
      result.getByTestId("edge-hit-e_n_node_1_n_node_2"),
    )
    fireEvent.click(edgeHit)
    await waitFor(() =>
      expect(result.getByTestId("edge-condition-inspector")).toBeInTheDocument(),
    )
    expect(result.getByTestId("edge-inspector-id")).toHaveTextContent("e_n_node_1_n_node_2")
  })

  it("background-click → TriggerInspector", async () => {
    const result = renderWithTemplate()
    const surface = await waitFor(() =>
      result.getByTestId("graph-canvas-surface"),
    )
    fireEvent.click(surface)
    await waitFor(() =>
      expect(result.getByTestId("trigger-inspector")).toBeInTheDocument(),
    )
  })

  it("transitions node → edge → background → node swap the inspector cleanly (no stale panes)", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    fireEvent.click(n1)
    await waitFor(() => expect(result.getByTestId("node-config-form")).toBeInTheDocument())

    fireEvent.click(result.getByTestId("edge-hit-e_n_node_1_n_node_2"))
    await waitFor(() => expect(result.getByTestId("edge-condition-inspector")).toBeInTheDocument())
    expect(result.queryByTestId("node-config-form")).not.toBeInTheDocument()

    fireEvent.click(result.getByTestId("graph-canvas-surface"))
    await waitFor(() => expect(result.getByTestId("trigger-inspector")).toBeInTheDocument())
    expect(result.queryByTestId("edge-condition-inspector")).not.toBeInTheDocument()

    fireEvent.click(result.getByTestId("canvas-node-n_node_2"))
    await waitFor(() => expect(result.getByTestId("node-config-form")).toBeInTheDocument())
    expect(result.queryByTestId("trigger-inspector")).not.toBeInTheDocument()
  })

  it("selection transitions do not mutate the canvas (node count stable across selects)", async () => {
    const result = renderWithTemplate()
    await waitFor(() => expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument())
    const before = result.getAllByTestId(/^canvas-node-n_node_/).length
    fireEvent.click(result.getByTestId("canvas-node-n_node_1"))
    fireEvent.click(result.getByTestId("edge-hit-e_n_node_1_n_node_2"))
    fireEvent.click(result.getByTestId("graph-canvas-surface"))
    const after = result.getAllByTestId(/^canvas-node-n_node_/).length
    expect(after).toBe(before)
  })
})
