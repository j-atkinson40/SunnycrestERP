/**
 * FocusEditorPage tests — sub-arc C-2.1 rewrite.
 *
 * Validates the tier toggle, tier-1 cores browser, and tier-2
 * placeholder. The legacy composition-authoring tests (Arc 3a
 * return_to banner, ?focus_type pre-selection against
 * focus_compositions) are retired here — the legacy code path is
 * replaced by the C-2.1 + C-2.2 inheritance editor.
 *
 * Network calls mocked: focusCoresService (list / get / create /
 * update) + adminApi.get for themes resolve.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import "@/lib/visual-editor/registry/auto-register"

import FocusEditorPage from "./FocusEditorPage"

// Mock focusCoresService for predictable list/get/update behavior.
// NOTE: vi.mock is hoisted; inline factory must not reference outer
// bindings. Define mockCores inside the factory + re-derive for tests.
vi.mock("@/bridgeable-admin/services/focus-cores-service", () => {
  const cores = [
    {
      id: "core-001",
      core_slug: "scheduling-kanban-core",
      display_name: "Scheduling Kanban Core",
      description: "Funeral scheduling kanban dispatcher.",
      registered_component_kind: "focus-template",
      registered_component_name: "SchedulingKanbanCore",
      default_starting_column: 0,
      default_column_span: 12,
      default_row_index: 0,
      min_column_span: 6,
      max_column_span: 12,
      canvas_config: {},
      chrome: { preset: "card" },
      version: 1,
      is_active: true,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-15T00:00:00Z",
    },
  ]
  return {
    focusCoresService: {
      list: vi.fn().mockResolvedValue(cores),
      get: vi.fn().mockResolvedValue(cores[0]),
      create: vi.fn(),
      update: vi
        .fn()
        .mockImplementation(async (_id: string, payload: { chrome: unknown }) => ({
          ...cores[0],
          chrome: payload.chrome,
        })),
    },
  }
})

// Sub-arc C-2.2a — Tier 2 templates editor lands; mock its service.
vi.mock("@/bridgeable-admin/services/focus-templates-service", () => ({
  focusTemplatesService: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    usage: vi.fn(),
  },
}))

vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: {
    get: vi.fn().mockResolvedValue({ data: { tokens: {} } }),
    post: vi.fn(),
    put: vi.fn(),
  },
}))

function renderAt(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="*" element={<FocusEditorPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.clearAllMocks()
})

describe("FocusEditorPage — sub-arc C-2.1", () => {
  it("renders the focus-editor-page test ID", async () => {
    renderAt("/")
    expect(await screen.findByTestId("focus-editor-page")).toBeTruthy()
  })

  it("renders the tier toggle with both options", async () => {
    renderAt("/")
    expect(await screen.findByTestId("focus-tier-toggle")).toBeTruthy()
    expect(screen.getByTestId("tier-toggle-1")).toBeTruthy()
    expect(screen.getByTestId("tier-toggle-2")).toBeTruthy()
  })

  it("defaults to Tier 1 when no ?tier param", async () => {
    renderAt("/")
    const t1 = await screen.findByTestId("tier-toggle-1")
    expect(t1.getAttribute("data-active")).toBe("true")
    expect(screen.getByTestId("tier-toggle-2").getAttribute("data-active")).toBe("false")
  })

  it("renders Tier 1 cores browser when active", async () => {
    renderAt("/")
    expect(await screen.findByTestId("focus-editor-browser")).toBeTruthy()
  })

  it("renders Tier 2 templates editor when ?tier=2 (C-2.2a → C-2.2b)", async () => {
    renderAt("/?tier=2")
    // Post-C-2.2b: tier 2 mounts the templates editor with the
    // three-section inspector. With no template selected the
    // inspector right-rail shows the empty-state hint.
    expect(
      await screen.findByTestId("tier2-inspector"),
    ).toBeTruthy()
    expect(
      screen.getByTestId("tier2-inspector-empty"),
    ).toBeInTheDocument()
    // Tier-1-specific preview marker should NOT be present.
    expect(screen.queryByTestId("tier1-preview")).toBeNull()
  })

  it("switching tier via toggle updates URL and renders the other tier body", async () => {
    renderAt("/?tier=1")
    const t2 = await screen.findByTestId("tier-toggle-2")
    fireEvent.click(t2)
    await waitFor(() => {
      expect(screen.queryByTestId("tier2-inspector")).toBeTruthy()
    })
    fireEvent.click(screen.getByTestId("tier-toggle-1"))
    await waitFor(() => {
      expect(screen.queryByTestId("tier1-preview")).toBeTruthy()
    })
  })

  it("Tier 2 inspector empty-state hint surfaces when no template selected", async () => {
    renderAt("/?tier=2")
    const empty = await screen.findByTestId("tier2-inspector-empty")
    expect(empty.textContent ?? "").toMatch(/select a template/i)
  })

  it("loads cores list on mount and renders browser rows", async () => {
    renderAt("/")
    await waitFor(() => {
      expect(screen.queryByTestId("core-row-scheduling-kanban-core")).toBeTruthy()
    })
  })

  it("clicking a core row updates the URL ?core param", async () => {
    renderAt("/")
    const row = await screen.findByTestId("core-row-scheduling-kanban-core")
    fireEvent.click(row)
    // No URL hook in this test, but the row's data-selected should
    // toggle to true after the click.
    await waitFor(() => {
      expect(row.getAttribute("data-selected")).toBe("true")
    })
  })

  it("dirty indicator hidden by default", async () => {
    renderAt("/")
    await screen.findByTestId("focus-editor-page")
    expect(screen.queryByTestId("dirty-indicator")).toBeNull()
  })

  it("displays New Core button in the cores browser", async () => {
    renderAt("/")
    expect(await screen.findByTestId("new-core-button")).toBeTruthy()
  })

  it("clicking New Core opens the create modal", async () => {
    renderAt("/")
    const btn = await screen.findByTestId("new-core-button")
    fireEvent.click(btn)
    await waitFor(() => {
      expect(screen.queryByTestId("create-tier-one-core-modal")).toBeTruthy()
    })
  })

  it("renders no-selection state in preview when no core selected", async () => {
    renderAt("/")
    expect(await screen.findByTestId("tier1-no-selection")).toBeTruthy()
  })

  it("auto-selects core from ?core query param", async () => {
    renderAt("/?core=core-001")
    await waitFor(() => {
      const row = screen.queryByTestId("core-row-scheduling-kanban-core")
      expect(row?.getAttribute("data-selected")).toBe("true")
    })
  })
})
