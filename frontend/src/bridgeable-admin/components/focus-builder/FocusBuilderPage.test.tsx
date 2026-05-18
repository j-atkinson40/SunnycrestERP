/**
 * FocusBuilderPage integration tests (sub-arc F-1).
 *
 * Covers: three-region layout mount, tree selection updates URL,
 * subject param drives canvas, empty state when no subject.
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
  focusCoresService: { list: vi.fn(), get: vi.fn() },
}))
vi.mock("@/bridgeable-admin/services/focus-templates-service", () => ({
  focusTemplatesService: { list: vi.fn(), get: vi.fn() },
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
    await waitFor(() =>
      expect(screen.getByTestId("focus-builder-canvas-empty")).toBeInTheDocument(),
    )
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
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-canvas-core"),
      ).toBeInTheDocument(),
    )
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
    await waitFor(() =>
      expect(
        screen.getByTestId("focus-builder-canvas-template"),
      ).toBeInTheDocument(),
    )
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
})
