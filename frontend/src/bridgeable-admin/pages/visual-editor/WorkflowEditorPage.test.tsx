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

  it("A3 shape-treatment: a seeded start node renders as a uniform card with its type-icon + lifecycle family (no silhouette)", async () => {
    // End-to-end through the page: the B-3b silhouette system is retired —
    // a seeded start node renders the A3 uniform card (per-type icon +
    // family tone), NOT a circle backdrop. data-node-shape is gone;
    // data-node-family carries the family.
    const result = renderWithTemplate()
    const startNode = await waitFor(() =>
      result.getByTestId("canvas-node-n_node_1"),
    )
    expect(startNode).not.toHaveAttribute("data-node-shape")
    expect(startNode).toHaveAttribute("data-node-family", "lifecycle")
    expect(
      result.getByTestId("canvas-node-n_node_1-icon").querySelector("svg"),
    ).toBeInTheDocument()
  })

  it("B-4: the reachability-overlay toggle is reachable through the page (default off)", async () => {
    const result = renderWithTemplate()
    const toggle = await waitFor(() =>
      result.getByTestId("trace-overlay-toggle"),
    )
    expect(toggle).toHaveAttribute("data-trace-overlay", "off")
  })

  it("rail-palette add renders a new positioned node card through GraphCanvas", async () => {
    const result = renderWithTemplate()
    await waitFor(() => {
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument()
    })
    // Initial selection is none → the rail action palette is the add
    // surface (the center-top "Add:" chip-row was retired 2026-05-29).
    fireEvent.click(result.getByTestId("node-palette-item-action"))
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


// ── Container-arc Phase 0 — multi-node selection (shift/⌘+click) ───────
//
// End-to-end through the page: drives the real union-transition handler
// (handleSelectNode). Rule: plain click → single { kind:"node" }
// (data-selected); shift/⌘+click → { kind:"nodes" } (data-multi-selected,
// data-selected false — card editing dormant). A subsequent plain click
// demotes to single. The single-select path is byte-identical.

describe("WorkflowEditorPage — Container-arc Phase 0 multi-select", () => {
  it("shift+click accumulates a second node into a multi-selection", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    // Single-select n1.
    fireEvent.click(n1)
    await waitFor(() =>
      expect(n1).toHaveAttribute("data-selected", "true"),
    )
    // Shift-click n2 → both become multi-members; neither is single-selected.
    fireEvent.click(n2, { shiftKey: true })
    await waitFor(() => {
      expect(n1).toHaveAttribute("data-multi-selected", "true")
      expect(n2).toHaveAttribute("data-multi-selected", "true")
    })
    expect(n1).toHaveAttribute("data-selected", "false")
    expect(n2).toHaveAttribute("data-selected", "false")
  })

  it("shift+clicking an existing member toggles it out of the selection", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    fireEvent.click(n1)
    fireEvent.click(n2, { shiftKey: true })
    await waitFor(() =>
      expect(n2).toHaveAttribute("data-multi-selected", "true"),
    )
    // Shift-click n2 again → removed; n1 stays in the multi-of-1.
    fireEvent.click(n2, { shiftKey: true })
    await waitFor(() =>
      expect(n2).toHaveAttribute("data-multi-selected", "false"),
    )
    expect(n1).toHaveAttribute("data-multi-selected", "true")
  })

  it("a plain click while multi-selected demotes to single-select", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    fireEvent.click(n1)
    fireEvent.click(n2, { shiftKey: true })
    await waitFor(() =>
      expect(n1).toHaveAttribute("data-multi-selected", "true"),
    )
    // Plain click n2 → single-select n2; the multi clears.
    fireEvent.click(n2)
    await waitFor(() => {
      expect(n2).toHaveAttribute("data-selected", "true")
    })
    expect(n2).toHaveAttribute("data-multi-selected", "false")
    expect(n1).toHaveAttribute("data-multi-selected", "false")
    expect(n1).toHaveAttribute("data-selected", "false")
  })

  it("under multi-select the right rail shows the group panel (P1 — the first multi consumer)", async () => {
    // P0 shipped multi-select with the rail falling through to the palette;
    // P1 adds the first consumer — the {kind:"nodes"} rail arm now shows the
    // group panel instead of the palette.
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    fireEvent.click(n1)
    fireEvent.click(n2, { shiftKey: true })
    await waitFor(() =>
      expect(n1).toHaveAttribute("data-multi-selected", "true"),
    )
    expect(
      result.getByTestId("workflow-multi-selection-panel"),
    ).toBeInTheDocument()
    expect(
      result.queryByTestId("workflow-node-palette"),
    ).not.toBeInTheDocument()
  })
})


// ── Container-arc Phase 1 — group / render / ungroup (end-to-end) ──────
//
// Drives the real container CRUD through the page: multi-select → group →
// a labeled box renders around the members → ungroup removes it (nodes stay).

describe("WorkflowEditorPage — Container-arc Phase 1 containers", () => {
  it("groups a multi-selection into a container that renders a box around the members", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    fireEvent.click(n1)
    fireEvent.click(n2, { shiftKey: true })
    const groupBtn = await waitFor(() =>
      result.getByTestId("workflow-group-into-container"),
    )
    fireEvent.click(groupBtn)
    // A container box appears (first id c_group_1); selection clears → palette.
    await waitFor(() => {
      expect(
        result.getByTestId("canvas-container-c_group_1"),
      ).toBeInTheDocument()
    })
    // Selection cleared → the rail returns to the palette (none-state).
    expect(result.getByTestId("workflow-node-palette")).toBeInTheDocument()
    // The box's label placeholder is editable inline on the canvas.
    expect(
      result.getByTestId("canvas-container-c_group_1-label-placeholder"),
    ).toBeInTheDocument()
  })

  it("ungroup removes the container but keeps the member nodes", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    fireEvent.click(n1)
    fireEvent.click(n2, { shiftKey: true })
    fireEvent.click(
      await waitFor(() => result.getByTestId("workflow-group-into-container")),
    )
    const ungroup = await waitFor(() =>
      result.getByTestId("canvas-container-c_group_1-ungroup"),
    )
    fireEvent.click(ungroup)
    // Container gone; the nodes remain on the canvas.
    await waitFor(() => {
      expect(
        result.queryByTestId("canvas-container-c_group_1"),
      ).not.toBeInTheDocument()
    })
    expect(result.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()
    expect(result.getByTestId("canvas-node-n_node_2")).toBeInTheDocument()
  })

  it("editing a container label commits via inline double-click", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    fireEvent.click(n1)
    fireEvent.click(n2, { shiftKey: true })
    fireEvent.click(
      await waitFor(() => result.getByTestId("workflow-group-into-container")),
    )
    const placeholder = await waitFor(() =>
      result.getByTestId("canvas-container-c_group_1-label-placeholder"),
    )
    fireEvent.doubleClick(placeholder)
    const input = await waitFor(() =>
      result.getByTestId("canvas-container-c_group_1-label-input"),
    )
    fireEvent.change(input, { target: { value: "Burial path" } })
    fireEvent.keyDown(input, { key: "Enter" })
    await waitFor(() => {
      expect(
        result.getByTestId("canvas-container-c_group_1-label"),
      ).toHaveTextContent("Burial path")
    })
  })

  it("Phase 2b — collapse hides members; expand restores them (round-trip through the page)", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    fireEvent.click(n1)
    fireEvent.click(n2, { shiftKey: true })
    fireEvent.click(
      await waitFor(() => result.getByTestId("workflow-group-into-container")),
    )
    // Collapse via the expanded chrome's collapse button.
    fireEvent.click(
      await waitFor(() => result.getByTestId("canvas-container-c_group_1-collapse")),
    )
    // Members hidden; the collapsed card shows.
    await waitFor(() => {
      expect(
        result.queryByTestId("canvas-node-n_node_1"),
      ).not.toBeInTheDocument()
    })
    expect(result.getByTestId("canvas-container-c_group_1")).toHaveAttribute(
      "data-collapsed",
      "true",
    )
    // Expand restores the members.
    fireEvent.click(result.getByTestId("canvas-container-c_group_1-expand"))
    await waitFor(() => {
      expect(result.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()
    })
    expect(result.getByTestId("canvas-node-n_node_2")).toBeInTheDocument()
  })
})


// ── Container-arc Phase 3c — the authoring gesture (mixed node+container) ──
//
// End-to-end through the page: make nesting AUTHORABLE. Group nodes → a
// container; then mix-select a loose node + that container → group → a parent
// nesting the child by reference (the child keeps its own members). Proves the
// union extension + handleSelectContainer + handleCreateContainer mixed
// emission produce state P3a validates + P3b renders.

describe("WorkflowEditorPage — Container-arc Phase 3c authoring gesture", () => {
  it("groups a MIXED node+container selection → a parent nesting the child by reference", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    // Group n_node_1 alone → c_group_1 (n_node_2 stays loose).
    fireEvent.click(n1, { shiftKey: true })
    fireEvent.click(
      await waitFor(() => result.getByTestId("workflow-group-into-container")),
    )
    await waitFor(() =>
      expect(result.getByTestId("canvas-container-c_group_1")).toBeInTheDocument(),
    )
    // Mixed-select: shift-click loose n_node_2 + shift-click c_group_1's select
    // handle → { nodes, ids:[n_node_2], containerIds:[c_group_1] }.
    fireEvent.click(result.getByTestId("canvas-node-n_node_2"), { shiftKey: true })
    fireEvent.click(
      await waitFor(() => result.getByTestId("canvas-container-c_group_1-select")),
      { shiftKey: true },
    )
    // The panel reflects the mixed selection (1 node + 1 group).
    expect(
      result.getByTestId("workflow-multi-selection-panel"),
    ).toHaveTextContent(/1 node.*1 group/)
    // Group → c_group_2 = [node n_node_2, container c_group_1].
    fireEvent.click(result.getByTestId("workflow-group-into-container"))
    await waitFor(() =>
      expect(result.getByTestId("canvas-container-c_group_2")).toBeInTheDocument(),
    )
    // The child container persists (nested), keeping its own member n_node_1.
    expect(result.getByTestId("canvas-container-c_group_1")).toBeInTheDocument()
    expect(result.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()
    // No validation error (the produced nesting passes P3a's validators).
    expect(
      result.queryByTestId("workflow-editor-validation-badge"),
    ).not.toBeInTheDocument()
  })

  it("a plain NODE click clears a container selection (clean transition)", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    // Make a container, then select it (plain → one-item multi).
    fireEvent.click(n1, { shiftKey: true })
    fireEvent.click(
      await waitFor(() => result.getByTestId("workflow-group-into-container")),
    )
    fireEvent.click(
      await waitFor(() => result.getByTestId("canvas-container-c_group_1-select")),
    )
    await waitFor(() =>
      expect(
        result.getByTestId("workflow-multi-selection-panel"),
      ).toBeInTheDocument(),
    )
    // Plain-click the loose node → single-select; the container selection clears.
    fireEvent.click(result.getByTestId("canvas-node-n_node_2"))
    await waitFor(() =>
      expect(result.getByTestId("canvas-node-n_node_2")).toHaveAttribute(
        "data-selected",
        "true",
      ),
    )
    expect(
      result.queryByTestId("workflow-multi-selection-panel"),
    ).not.toBeInTheDocument()
    expect(
      result.getByTestId("canvas-container-c_group_1"),
    ).toHaveAttribute("data-multi-selected", "false")
  })

  it("REGRESSION — a node-only group still produces a flat container (no nesting)", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    const n2 = result.getByTestId("canvas-node-n_node_2")
    fireEvent.click(n1)
    fireEvent.click(n2, { shiftKey: true })
    fireEvent.click(
      await waitFor(() => result.getByTestId("workflow-group-into-container")),
    )
    // The container renders; both nodes are its (flat node) members — visible,
    // no nested container, no validation error (P1/P2 behavior unchanged).
    await waitFor(() =>
      expect(result.getByTestId("canvas-container-c_group_1")).toBeInTheDocument(),
    )
    expect(result.getByTestId("canvas-node-n_node_1")).toBeInTheDocument()
    expect(result.getByTestId("canvas-node-n_node_2")).toBeInTheDocument()
    expect(
      result.queryByTestId("workflow-editor-validation-badge"),
    ).not.toBeInTheDocument()
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
  it("renders all 31 registered workflow-node types in the rail palette (32 minus the retired generation-focus-invocation, P2)", async () => {
    const result = renderWithTemplate()
    await waitFor(() => {
      expect(result.getByTestId("workflow-node-palette")).toBeInTheDocument()
    })
    const items = result
      .getAllByRole("button")
      .filter((b) =>
        b.getAttribute("data-testid")?.startsWith("node-palette-item-"),
      )
    expect(items.length).toBe(31)
  })

  it("exposes node types absent from the pre-B-2 16-tuple (create_record, wait, output)", async () => {
    const result = renderWithTemplate()
    await waitFor(() => {
      expect(result.getByTestId("workflow-node-palette")).toBeInTheDocument()
    })
    // None of these were in the old hardcoded palette.
    expect(result.getByTestId("node-palette-item-create_record")).toBeInTheDocument()
    expect(result.getByTestId("node-palette-item-wait")).toBeInTheDocument()
    expect(result.getByTestId("node-palette-item-output")).toBeInTheDocument()
  })

  it("rail-palette add of a newly-registry-exposed type renders it on the graph canvas", async () => {
    const result = renderWithTemplate()
    // Wait for the TEMPLATE to load (its 2 seeded nodes) before clicking —
    // the none-state palette renders immediately (even on the empty initial
    // draft), so gating on the palette alone would race the async template
    // load and add against a 0-node draft. graph-canvas-surface only renders
    // once nodes exist.
    await waitFor(() => {
      expect(result.getByTestId("canvas-node-n_node_2")).toBeInTheDocument()
    })
    fireEvent.click(result.getByTestId("node-palette-item-create_record"))
    await waitFor(() => {
      // 3rd node (2 seeded) auto-generated as n_node_3 with the clicked type.
      const node = result.getByTestId("canvas-node-n_node_3")
      expect(node).toHaveAttribute("data-node-type", "create_record")
    })
  })
})


// ── B-5 + P3c + E-3 — selection-driven right-rail dispatch ───────────
//
// 4-state selection (none/node/edge/background) drives the right rail.
// P3c retired NodeConfigForm from the card-editor rail; E-3 relocated the 2
// bespoke invoke_* types' config into the card expand panel. So node-selection
// now shows the palette for ALL types (edits happen on the card). none →
// palette; node → palette; edge → EdgeConditionInspector; background →
// TriggerInspector. (NodeConfigForm lives on for the runtime-host WorkflowsTab,
// tested separately.)

describe("WorkflowEditorPage — B-5/P3c selection-driven inspector dispatch", () => {
  it("initial selection is 'none' → the rail action palette renders", async () => {
    const result = renderWithTemplate()
    await waitFor(() =>
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument(),
    )
    // none-state now renders the WorkflowNodePalette (was the
    // "workflow-inspector-empty" placeholder pre-2026-05-29).
    expect(result.getByTestId("workflow-node-palette")).toBeInTheDocument()
    expect(result.queryByTestId("node-config-form")).not.toBeInTheDocument()
  })

  it("node-click (normal type) → palette stays (P3c — edits on the card); NodeConfigForm gone", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    fireEvent.click(n1)
    // P3c: the node IS selected (card highlight), and the rail shows the
    // palette — node edits happen on the card, NOT in a NodeConfigForm.
    await waitFor(() =>
      expect(result.getByTestId("canvas-node-n_node_1")).toHaveAttribute(
        "data-selected",
        "true",
      ),
    )
    expect(result.getByTestId("workflow-node-palette")).toBeInTheDocument()
    expect(result.queryByTestId("node-config-form")).not.toBeInTheDocument()
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

  it("transitions node → edge → background → node swap the rail cleanly (no stale panes)", async () => {
    const result = renderWithTemplate()
    const n1 = await waitFor(() => result.getByTestId("canvas-node-n_node_1"))
    fireEvent.click(n1)
    // P3c: node(normal) → palette.
    await waitFor(() => expect(result.getByTestId("workflow-node-palette")).toBeInTheDocument())

    fireEvent.click(result.getByTestId("edge-hit-e_n_node_1_n_node_2"))
    await waitFor(() => expect(result.getByTestId("edge-condition-inspector")).toBeInTheDocument())
    // edge arm replaces the palette.
    expect(result.queryByTestId("workflow-node-palette")).not.toBeInTheDocument()

    fireEvent.click(result.getByTestId("graph-canvas-surface"))
    await waitFor(() => expect(result.getByTestId("trigger-inspector")).toBeInTheDocument())
    expect(result.queryByTestId("edge-condition-inspector")).not.toBeInTheDocument()

    fireEvent.click(result.getByTestId("canvas-node-n_node_2"))
    // back to a node → palette again (no stale trigger pane).
    await waitFor(() => expect(result.getByTestId("workflow-node-palette")).toBeInTheDocument())
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

describe("WorkflowEditorPage — Builder Craft 1a shared chrome (smoke)", () => {
  it("renders with the shared chrome mounted: PanelHeader top bar + role=toolbar + shared Select trigger", async () => {
    const result = renderWithTemplate()
    await waitFor(() =>
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument(),
    )
    // Shared PanelHeader chrome hosts the top bar.
    const header = document.querySelector('[data-slot="panel-header"]')
    expect(header).toBeTruthy()
    // The actions cluster is a real toolbar (AT grouping semantics).
    expect(
      result.getByRole("toolbar", { name: "Workflow editor actions" }),
    ).toBeInTheDocument()
    // Existing action testids preserved through the adoption (parity guard).
    expect(result.getByTestId("workflow-editor-save")).toBeInTheDocument()
    expect(result.getByTestId("workflow-editor-discard")).toBeInTheDocument()
    expect(result.getByTestId("workflow-editor-save-notify")).toBeInTheDocument()
  })

  it("the vertical picker is the shared Select (combobox trigger, testid preserved)", async () => {
    const result = renderWithTemplate()
    await waitFor(() =>
      expect(result.getByTestId("graph-canvas-surface")).toBeInTheDocument(),
    )
    // scope defaults to platform_default in this fixture URL; switch to
    // vertical_default so the picker renders.
    fireEvent.click(result.getByTestId("scope-vertical_default"))
    const trigger = await waitFor(() => result.getByTestId("vertical-select"))
    // base-ui Select trigger is a button with combobox-style semantics,
    // not a native <select> — the raw-select drift is gone.
    expect(trigger.tagName.toLowerCase()).not.toBe("select")
  })
})
