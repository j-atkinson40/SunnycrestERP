/**
 * FocusBuilderTree unit + integration tests (sub-arc F-1).
 *
 * Covers:
 *   - buildFocusBuilderTree pure function shape.
 *   - defaultExpansionForTree (Studio active vertical + alpha fallback).
 *   - integration: fetches mocked, tree renders, scope chip surfaces,
 *     localStorage persistence on toggle, click handler fires.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import {
  buildFocusBuilderTree,
  defaultExpansionForTree,
  FocusBuilderTree,
} from "./FocusBuilderTree"
import type { Vertical } from "@/bridgeable-admin/services/verticals-service"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"
import type { TemplateRecord } from "@/bridgeable-admin/services/focus-templates-service"


vi.mock("@/bridgeable-admin/services/verticals-service", () => ({
  verticalsService: {
    list: vi.fn(),
  },
}))
vi.mock("@/bridgeable-admin/services/focus-cores-service", () => ({
  focusCoresService: {
    list: vi.fn(),
    get: vi.fn(),
  },
}))
vi.mock("@/bridgeable-admin/services/focus-templates-service", () => ({
  focusTemplatesService: {
    list: vi.fn(),
    get: vi.fn(),
  },
}))
vi.mock("@/bridgeable-admin/lib/studio-routes", () => ({
  readLastVertical: vi.fn(() => null),
}))

import { verticalsService } from "@/bridgeable-admin/services/verticals-service"
import { focusCoresService } from "@/bridgeable-admin/services/focus-cores-service"
import { focusTemplatesService } from "@/bridgeable-admin/services/focus-templates-service"


function vertical(slug: string, name: string, sort_order = 0): Vertical {
  return {
    slug,
    display_name: name,
    description: null,
    status: "published",
    icon: null,
    sort_order,
    created_at: "",
    updated_at: "",
  }
}

function core(id: string, slug: string, name = slug): CoreRecord {
  return {
    id,
    core_slug: slug,
    display_name: name,
    description: null,
    registered_component_kind: "focus-template",
    registered_component_name: "X",
    default_starting_column: 0,
    default_column_span: 12,
    default_row_index: 0,
    min_column_span: 1,
    max_column_span: 12,
    canvas_config: {},
    chrome: { preset: "card" },
    version: 1,
    is_active: true,
    created_at: "",
    updated_at: "",
  }
}

function template(
  id: string,
  slug: string,
  inherits_from_core_id: string,
  scope: "platform_default" | "vertical_default",
  vert: string | null,
): TemplateRecord {
  return {
    id,
    scope,
    vertical: vert,
    template_slug: slug,
    display_name: slug,
    description: null,
    inherits_from_core_id,
    inherits_from_core_version: 1,
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
}


beforeEach(() => {
  if (typeof window !== "undefined") {
    window.localStorage.clear()
  }
})

afterEach(() => {
  vi.clearAllMocks()
  if (typeof window !== "undefined") {
    window.localStorage.clear()
  }
})


describe("buildFocusBuilderTree (pure)", () => {
  it("renders vertical_default template under matching vertical only", () => {
    const groups = buildFocusBuilderTree({
      verticals: [vertical("manufacturing", "Manufacturing")],
      cores: [core("c1", "scheduling-kanban-core")],
      templates: [template("t1", "sched-fh", "c1", "vertical_default", "manufacturing")],
    })
    expect(groups).toHaveLength(1)
    expect(groups[0].id).toBe("vertical:manufacturing")
    // Drill: vertical → focus-type (production) → core → template
    const ft = groups[0].children![0]
    expect(ft.label).toBe("Production")
    const coreNode = ft.children![0]
    expect(coreNode.label).toBe("scheduling-kanban-core")
    const labels = coreNode.children!.map((n) => n.label)
    expect(labels).toContain("sched-fh")
    expect(labels.some((l) => l.startsWith("+ New "))).toBe(true)
  })

  it("renders platform_default template across every published vertical", () => {
    const groups = buildFocusBuilderTree({
      verticals: [
        vertical("manufacturing", "Manufacturing", 1),
        vertical("funeral_home", "Funeral Home", 2),
      ],
      cores: [core("c1", "scheduling-kanban-core")],
      templates: [template("t1", "p-default", "c1", "platform_default", null)],
    })
    expect(groups.map((g) => g.id)).toEqual([
      "vertical:manufacturing",
      "vertical:funeral_home",
    ])
    for (const g of groups) {
      expect(g.children!.length).toBeGreaterThan(0)
    }
  })

  it("buckets cores with NO templates into 'Unclassified' pseudo-vertical at bottom", () => {
    const groups = buildFocusBuilderTree({
      verticals: [vertical("manufacturing", "Manufacturing")],
      cores: [core("c1", "orphan-core")],
      templates: [],
    })
    expect(groups[groups.length - 1].label).toBe("Unclassified")
  })

  it("emits a '+ New <Core>-based template' pseudo-child under each core", () => {
    const groups = buildFocusBuilderTree({
      verticals: [vertical("manufacturing", "Manufacturing")],
      cores: [core("c1", "scheduling-kanban-core", "Scheduling Kanban")],
      templates: [
        template("t1", "x", "c1", "vertical_default", "manufacturing"),
      ],
    })
    const coreNode = groups[0].children![0].children![0]
    const newNode = coreNode.children!.find((n) => n.label.startsWith("+ New"))
    expect(newNode?.label).toBe("+ New Scheduling Kanban-based template")
    expect((newNode?.metadata as { kind: string })?.kind).toBe("new-template")
  })

  it("attaches scope metadata to template nodes", () => {
    const groups = buildFocusBuilderTree({
      verticals: [vertical("manufacturing", "Manufacturing")],
      cores: [core("c1", "scheduling-kanban-core")],
      templates: [
        template("t1", "x", "c1", "vertical_default", "manufacturing"),
      ],
    })
    const tNode = groups[0].children![0].children![0].children![0]
    expect((tNode.metadata as { scope: string }).scope).toBe("vertical_default")
  })
})


describe("defaultExpansionForTree", () => {
  it("expands studio active vertical and its focus-types", () => {
    const groups = buildFocusBuilderTree({
      verticals: [
        vertical("manufacturing", "Manufacturing", 1),
        vertical("funeral_home", "Funeral Home", 2),
      ],
      cores: [core("c1", "scheduling-kanban-core")],
      templates: [template("t1", "x", "c1", "vertical_default", "manufacturing")],
    })
    const exp = defaultExpansionForTree(groups, "manufacturing")
    expect(exp.has("vertical:manufacturing")).toBe(true)
    expect(exp.has("vertical:funeral_home")).toBe(false)
    // focus-type level should also be expanded
    const ftId = "vertical:manufacturing::focus-type:production"
    expect(exp.has(ftId)).toBe(true)
    // core-level NOT expanded
    expect(
      [...exp].some((id) => id.includes("::core:") && !id.endsWith("::new")),
    ).toBe(false)
  })

  it("falls back to alphabetical-first vertical when no studio scope", () => {
    const groups = buildFocusBuilderTree({
      verticals: [
        vertical("manufacturing", "Manufacturing", 1),
        vertical("funeral_home", "Funeral Home", 2),
      ],
      cores: [core("c1", "scheduling-kanban-core")],
      templates: [template("t1", "x", "c1", "vertical_default", "manufacturing")],
    })
    const exp = defaultExpansionForTree(groups, null)
    // Funeral Home < Manufacturing alphabetically.
    expect(exp.has("vertical:funeral_home")).toBe(true)
    expect(exp.has("vertical:manufacturing")).toBe(false)
  })
})


describe("FocusBuilderTree (integration)", () => {
  beforeEach(() => {
    ;(verticalsService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      vertical("manufacturing", "Manufacturing", 1),
      vertical("funeral_home", "Funeral Home", 2),
    ])
    ;(focusCoresService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      core("c1", "scheduling-kanban-core", "Scheduling Kanban"),
    ])
    ;(focusTemplatesService.list as ReturnType<typeof vi.fn>).mockResolvedValue([
      template("t1", "sched-fh", "c1", "vertical_default", "manufacturing"),
    ])
  })

  it("renders verticals + focus-type + core + template after fetch", async () => {
    render(
      <FocusBuilderTree
        selectedSubject={null}
        onSelectSubject={() => {}}
        studioActiveVertical="manufacturing"
      />,
    )
    await waitFor(() =>
      expect(screen.getByText("Manufacturing")).toBeInTheDocument(),
    )
    // Studio scope expanded by default → focus-type + core visible.
    await waitFor(() =>
      expect(screen.getByText("Production")).toBeInTheDocument(),
    )
    expect(screen.getByText("Scheduling Kanban")).toBeInTheDocument()
  })

  it("surfaces scope chip on template nodes", async () => {
    render(
      <FocusBuilderTree
        selectedSubject={{ kind: "template", id: "t1" }}
        onSelectSubject={() => {}}
        studioActiveVertical="manufacturing"
      />,
    )
    // Auto-expansion of trail because subject is template → core
    // children should expand.
    await waitFor(() =>
      expect(screen.getByText("sched-fh")).toBeInTheDocument(),
    )
    expect(screen.getByTestId("scope-chip-vertical_default")).toBeInTheDocument()
  })

  it("invokes onSelectSubject when a template leaf is clicked", async () => {
    const onSelectSubject = vi.fn()
    // Pre-select the template so the trail (vertical → focus-type →
    // core) auto-expands and the template leaf is rendered.
    render(
      <FocusBuilderTree
        selectedSubject={{ kind: "template", id: "t1" }}
        onSelectSubject={onSelectSubject}
        studioActiveVertical="manufacturing"
      />,
    )
    await waitFor(() =>
      expect(screen.getByText("sched-fh")).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByText("sched-fh"))
    expect(onSelectSubject).toHaveBeenCalledWith({ kind: "template", id: "t1" })
  })

  it("persists expansion state to localStorage on toggle", async () => {
    // Seed localStorage with a single known expanded id BEFORE mount
    // so the default-expansion path is bypassed (pre-existing stored
    // state wins). Now toggling that id should result in its removal.
    window.localStorage.setItem(
      "bridgeable.focus-builder.tree-expanded",
      JSON.stringify(["vertical:manufacturing"]),
    )
    render(
      <FocusBuilderTree
        selectedSubject={null}
        onSelectSubject={() => {}}
        studioActiveVertical={null}
      />,
    )
    await waitFor(() =>
      expect(screen.getByText("Manufacturing")).toBeInTheDocument(),
    )
    // Manufacturing is expanded — clicking its chevron collapses.
    const chevron = screen.getByTestId("tree-chevron-vertical:manufacturing")
    fireEvent.click(chevron)

    const stored = window.localStorage.getItem(
      "bridgeable.focus-builder.tree-expanded",
    )
    expect(stored).toBeTruthy()
    const parsed = JSON.parse(stored!) as string[]
    expect(parsed).not.toContain("vertical:manufacturing")
  })
})
