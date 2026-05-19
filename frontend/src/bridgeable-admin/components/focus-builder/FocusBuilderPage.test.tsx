/**
 * FocusBuilderPage integration tests (sub-arcs F-1 + F-2).
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import FocusBuilderPage from "./FocusBuilderPage"
import type { Vertical } from "@/bridgeable-admin/services/verticals-service"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"
import type { TemplateRecord } from "@/bridgeable-admin/services/focus-templates-service"


vi.mock("@/bridgeable-admin/services/verticals-service", () => ({
  verticalsService: { list: vi.fn() },
}))
vi.mock("@/bridgeable-admin/services/focus-cores-service", () => ({
  focusCoresService: { list: vi.fn(), get: vi.fn(), update: vi.fn() },
}))
vi.mock("@/bridgeable-admin/services/focus-templates-service", () => ({
  focusTemplatesService: {
    list: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    resolve: vi.fn(),
  },
}))
vi.mock("@/bridgeable-admin/lib/studio-routes", async () => {
  const actual = await vi.importActual<
    typeof import("@/bridgeable-admin/lib/studio-routes")
  >("@/bridgeable-admin/lib/studio-routes")
  return {
    ...actual,
    readLastVertical: vi.fn(() => null),
  }
})

import { verticalsService } from "@/bridgeable-admin/services/verticals-service"
import { focusCoresService } from "@/bridgeable-admin/services/focus-cores-service"
import { focusTemplatesService } from "@/bridgeable-admin/services/focus-templates-service"


const v: Vertical = {
  slug: "manufacturing",
  display_name: "Manufacturing",
  description: null,
  status: "published",
  icon: null,
  sort_order: 1,
  created_at: "",
  updated_at: "",
}

const c: CoreRecord = {
  id: "core-1",
  core_slug: "scheduling-kanban-core",
  display_name: "Scheduling Kanban",
  description: null,
  registered_component_kind: "focus-template",
  registered_component_name: "SchedulingKanbanCore",
  default_starting_column: 0,
  default_column_span: 12,
  default_row_index: 0,
  min_column_span: 1,
  max_column_span: 12,
  canvas_config: {},
  chrome: { preset: "card" },
  version: 9,
  is_active: true,
  created_at: "",
  updated_at: "",
}

const t: TemplateRecord = {
  id: "tpl-1",
  scope: "vertical_default",
  vertical: "manufacturing",
  template_slug: "sched-fh",
  display_name: "Sched FH",
  description: null,
  inherits_from_core_id: "core-1",
  inherits_from_core_version: 9,
  rows: [],
  canvas_config: {},
  chrome_overrides: {},
  substrate: {},
  typography: {},
  version: 1,
  is_active: true,
  created_at: "",
  updated_at: "",
}


afterEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
})


function defaultMocks() {
  ;(verticalsService.list as ReturnType<typeof vi.fn>).mockResolvedValue([v])
  ;(focusCoresService.list as ReturnType<typeof vi.fn>).mockResolvedValue([c])
  ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValue(c)
  ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue([t])
  ;(focusTemplatesService.get as ReturnType<typeof vi.fn>).mockResolvedValue(t)
  ;(focusTemplatesService.resolve as ReturnType<typeof vi.fn>).mockResolvedValue({
    template_id: "tpl-1",
    template_slug: "sched-fh",
    template_version: 1,
    template_scope: "vertical_default",
    template_vertical: "manufacturing",
    core_id: "core-1",
    core_slug: "scheduling-kanban-core",
    core_version: 9,
    core_registered_component: {},
    rows: [],
    canvas_config: {},
    resolved_chrome: { preset: "card" },
    resolved_substrate: null,
    resolved_typography: null,
    sources: {
      template: {},
      core: {},
      tenant: null,
      chrome_sources: { preset: "tier1" },
      substrate_sources: {},
      typography_sources: {},
    },
  })
}


describe("FocusBuilderPage", () => {
  it("mounts all three regions", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-page")).toBeInTheDocument(),
    )
    expect(screen.getByTestId("focus-builder-tree-region")).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-canvas-region"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-right-rail-region"),
    ).toBeInTheDocument()
  })

  it("shows empty canvas when no subject in URL", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      const canvas = screen.getByTestId("focus-builder-canvas")
      expect(canvas).toHaveAttribute("data-canvas-mode", "empty")
    })
  })

  it("loads a core into the canvas when ?subject=core:<id>", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=core:core-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      const canvas = screen.getByTestId("focus-builder-canvas")
      expect(canvas).toHaveAttribute("data-canvas-mode", "core")
    })
    expect(focusCoresService.get).toHaveBeenCalledWith("core-1")
  })

  it("loads a template into the canvas when ?subject=template:<id>", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      const canvas = screen.getByTestId("focus-builder-canvas")
      expect(canvas).toHaveAttribute("data-canvas-mode", "template")
    })
    expect(focusTemplatesService.get).toHaveBeenCalledWith("tpl-1")
  })

  it("clicking a core in the tree updates URL with ?subject=core:<id>", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByText("Scheduling Kanban")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByText("Scheduling Kanban"))
    await waitFor(() => {
      expect(focusCoresService.get).toHaveBeenCalledWith("core-1")
    })
  })

  it("inspector starts in empty state when subject loaded but no selection", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-inspector-empty"),
      ).toBeInTheDocument()
    })
  })

  it("clicking core placement opens chrome inspector", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument()
    })
    // Chrome preset picker rendered.
    expect(screen.getAllByText(/Chrome/i).length).toBeGreaterThan(0)
  })

  it("clicking canvas background opens substrate + typography sections (template mode)", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-canvas")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-canvas"))
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument()
    })
    expect(screen.getAllByText(/Substrate/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Typography/i).length).toBeGreaterThan(0)
  })

  it("core-placement click stops propagation (does not flip to background)", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() => {
      const placement = screen.getByTestId("focus-builder-core-placement")
      expect(placement).toHaveAttribute("data-selected", "true")
    })
    // Substrate section should NOT be visible — chrome section is.
    expect(screen.queryByText(/Substrate$/)).not.toBeInTheDocument()
  })

  it("Esc deselects (returns inspector to empty state)", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument(),
    )
    fireEvent.keyDown(window, { key: "Escape" })
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector-empty"),
      ).toBeInTheDocument(),
    )
  })

  it("'View canonical core' button visible for templates only", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    // Click placement to surface the inspector.
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() => {
      expect(
        screen.getByTestId("view-canonical-core-button"),
      ).toBeInTheDocument()
    })
  })

  it("'View canonical core' button NOT shown for cores", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=core:core-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument(),
    )
    expect(
      screen.queryByTestId("view-canonical-core-button"),
    ).not.toBeInTheDocument()
  })

  it("'View canonical core' button opens InheritedCoreInspectorPanel", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() =>
      expect(
        screen.getByTestId("view-canonical-core-button"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("view-canonical-core-button"))
    await waitFor(() =>
      expect(
        screen.getByTestId("inherited-core-inspector-panel"),
      ).toBeInTheDocument(),
    )
  })

  it("widget palette + theme placeholders render", async () => {
    defaultMocks()
    render(
      <MemoryRouter initialEntries={["/studio/builder/focuses"]}>
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-widget-palette-region"),
      ).toBeInTheDocument(),
    )
    expect(
      screen.getByTestId("focus-builder-theme-region"),
    ).toBeInTheDocument()
    expect(screen.getByText(/Arrives in F-3/)).toBeInTheDocument()
    expect(screen.getByText(/Arrives in F-4/)).toBeInTheDocument()
  })

  it("subject change resets selection to none", async () => {
    defaultMocks()
    render(
      <MemoryRouter
        initialEntries={["/studio/builder/focuses?subject=template:tpl-1"]}
      >
        <FocusBuilderPage />
      </MemoryRouter>,
    )
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-core-placement"),
      ).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId("focus-builder-core-placement"))
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-inspector"),
      ).toBeInTheDocument(),
    )
    // Switch subject via tree click — use the tree node testid to
    // disambiguate from the canvas card's title that also contains
    // "Scheduling Kanban".
    const coreNode = screen.getByTestId(
      "tree-node-vertical:manufacturing::focus-type:decision::core:core-1",
    )
    fireEvent.click(coreNode)
    await waitFor(() => {
      expect(
        screen.getByTestId("focus-builder-inspector-empty"),
      ).toBeInTheDocument()
    })
  })
})
