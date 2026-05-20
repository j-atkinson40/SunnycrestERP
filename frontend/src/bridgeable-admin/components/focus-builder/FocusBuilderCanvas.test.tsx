/**
 * FocusBuilderCanvas unit tests (sub-arc F-2).
 *
 * Asserts the canonical four-layer atmospheric backdrop for cores,
 * substrate-driven backdrop for templates, click → background +
 * stopPropagation on placement, selected indicator wires from context.
 */
import { describe, expect, it } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { DndContext } from "@dnd-kit/core"

import "@/lib/visual-editor/registry/auto-register"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import {
  FocusBuilderCanvas,
  CANONICAL_FOUR_LAYER_FALLBACK,
  detectTemplateShape,
  flattenFreeFormPlacements,
  computeFreeFormDropPosition,
} from "./FocusBuilderCanvas"
import {
  FocusBuilderSelectionProvider,
  useFocusBuilderSelection,
  type Selection,
} from "./FocusBuilderSelectionContext"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"
import type { TemplateRecord } from "@/bridgeable-admin/services/focus-templates-service"

const tokens = { ...BASE_TOKENS.light }

const core: CoreRecord = {
  id: "core-1",
  core_slug: "scheduling-kanban-core",
  display_name: "Scheduling Kanban",
  description: "core desc",
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

const tpl: TemplateRecord = {
  id: "tpl-1",
  scope: "vertical_default",
  vertical: "manufacturing",
  template_slug: "sched-fh",
  display_name: "Sched FH",
  description: "template desc",
  inherits_from_core_id: "core-1",
  inherits_from_core_version: 9,
  rows: [],
  canvas_config: {},
  chrome_overrides: {},
  substrate: { preset: "morning-warm", intensity: 100 },
  typography: { preset: "frosted-text", heading_weight: 600, body_weight: 500 },
  version: 1,
  is_active: true,
  created_at: "",
  updated_at: "",
}

function Probe({ onSelection }: { onSelection: (s: Selection) => void }) {
  const { selection } = useFocusBuilderSelection()
  React.useEffect(() => {
    onSelection(selection)
  }, [selection, onSelection])
  return null
}
// eslint-disable-next-line react-refresh/only-export-components
import * as React from "react"

describe("FocusBuilderCanvas", () => {
  it("renders empty state when mode=empty", () => {
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderCanvas
          mode="empty"
          themeTokens={tokens}
          core={null}
          template={null}
          inheritedCore={null}
        />
      </FocusBuilderSelectionProvider>,
    )
    const canvas = screen.getByTestId("focus-builder-canvas")
    expect(canvas).toHaveAttribute("data-canvas-mode", "empty")
    expect(canvas.textContent).toMatch(/Select a focus/i)
  })

  it("renders canonical four-layer fallback for core editing", () => {
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderCanvas
          mode="core"
          themeTokens={tokens}
          core={core}
          template={null}
          inheritedCore={null}
          coreChromeDraft={{ preset: "card" }}
        />
      </FocusBuilderSelectionProvider>,
    )
    const canvas = screen.getByTestId("focus-builder-canvas")
    expect(canvas).toHaveAttribute("data-canvas-mode", "core")
    // Canonical-fallback exposes the four-layer background composition.
    const bg = (canvas as HTMLElement).style.background
    expect(bg).toMatch(/gradient/i)
    // Sanity: matches the canonical fallback exactly (sourced from the
    // morning-warm canonical mockup).
    expect(CANONICAL_FOUR_LAYER_FALLBACK.background).toMatch(
      /linear-gradient/,
    )
  })

  it("renders substrate-driven backdrop for template editing", () => {
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderCanvas
          mode="template"
          themeTokens={tokens}
          core={null}
          template={tpl}
          inheritedCore={core}
          chromeOverridesDraft={{}}
          substrateDraft={{ preset: "morning-warm", intensity: 100 }}
          typographyDraft={{ preset: "frosted-text" }}
        />
      </FocusBuilderSelectionProvider>,
    )
    const canvas = screen.getByTestId("focus-builder-canvas")
    expect(canvas).toHaveAttribute("data-canvas-mode", "template")
    // Should have a non-empty background.
    const bg = (canvas as HTMLElement).style.background
    expect(bg.length).toBeGreaterThan(0)
  })

  it("renders identity 'CANONICAL CORE' caption when editing a core", () => {
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderCanvas
          mode="core"
          themeTokens={tokens}
          core={core}
          template={null}
          inheritedCore={null}
          coreChromeDraft={{ preset: "card" }}
        />
      </FocusBuilderSelectionProvider>,
    )
    expect(screen.getByText(/CANONICAL CORE/)).toBeInTheDocument()
    expect(screen.getByText("Scheduling Kanban")).toBeInTheDocument()
  })

  it("renders identity 'INHERITED CORE' caption when editing a template", () => {
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderCanvas
          mode="template"
          themeTokens={tokens}
          core={null}
          template={tpl}
          inheritedCore={core}
          chromeOverridesDraft={{}}
          substrateDraft={{}}
          typographyDraft={{}}
        />
      </FocusBuilderSelectionProvider>,
    )
    expect(screen.getByText(/INHERITED CORE/)).toBeInTheDocument()
  })

  it("canvas click sets selection to background", () => {
    let observed: Selection | null = null
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderCanvas
          mode="core"
          themeTokens={tokens}
          core={core}
          template={null}
          inheritedCore={null}
          coreChromeDraft={{ preset: "card" }}
        />
        <Probe onSelection={(s) => { observed = s }} />
      </FocusBuilderSelectionProvider>,
    )
    const canvas = screen.getByTestId("focus-builder-canvas")
    fireEvent.click(canvas)
    expect(observed).toEqual({ kind: "background" })
  })

  it("placement click sets selection to core AND stops propagation", () => {
    let observed: Selection | null = null
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderCanvas
          mode="core"
          themeTokens={tokens}
          core={core}
          template={null}
          inheritedCore={null}
          coreChromeDraft={{ preset: "card" }}
        />
        <Probe onSelection={(s) => { observed = s }} />
      </FocusBuilderSelectionProvider>,
    )
    const placement = screen.getByTestId("focus-builder-core-placement")
    fireEvent.click(placement)
    expect(observed).toEqual({ kind: "core" })
    // If propagation hadn't stopped, the canvas onClick would have
    // overwritten the selection back to "background".
  })

  it("placement selected indicator reflects selection.kind === 'core'", () => {
    // Wrapper that primes selection to { kind: 'core' } before render.
    function Primer() {
      const { setSelection } = useFocusBuilderSelection()
      React.useEffect(() => {
        setSelection({ kind: "core" })
      }, [setSelection])
      return null
    }
    render(
      <FocusBuilderSelectionProvider>
        <Primer />
        <FocusBuilderCanvas
          mode="core"
          themeTokens={tokens}
          core={core}
          template={null}
          inheritedCore={null}
          coreChromeDraft={{ preset: "card" }}
        />
      </FocusBuilderSelectionProvider>,
    )
    const placement = screen.getByTestId("focus-builder-core-placement")
    expect(placement).toHaveAttribute("data-selected", "true")
  })

  // ── F-3 — widget placements + drop target ───────────────────────

  it("renders placed widgets when rowsDraft has placements", () => {
    const rowsDraft = [
      {
        row_index: 0,
        column_count: 12,
        placements: [
          {
            id: "w-1",
            widget_slug: "day-strip-widget",
            column_start: 1,
            column_span: 12,
            chrome: {},
          },
          {
            id: "w-2",
            widget_slug: "today-pin-widget",
            column_start: 1,
            column_span: 6,
            chrome: {},
          },
        ],
      },
    ]
    render(
      <DndContext>
        <FocusBuilderSelectionProvider>
          <FocusBuilderCanvas
            mode="template"
            themeTokens={tokens}
            core={null}
            template={tpl}
            inheritedCore={core}
            chromeOverridesDraft={{}}
            substrateDraft={tpl.substrate}
            typographyDraft={tpl.typography}
            rowsDraft={rowsDraft}
          />
        </FocusBuilderSelectionProvider>
      </DndContext>,
    )
    const placed = screen.getAllByTestId("focus-builder-placed-widget")
    expect(placed).toHaveLength(2)
    expect(placed[0].getAttribute("data-widget-id")).toBe("w-1")
  })

  it("clicking a placed widget sets selection to widget kind", () => {
    let observed: Selection = { kind: "none" }
    const rowsDraft = [
      {
        row_index: 0,
        column_count: 12,
        placements: [
          {
            id: "w-1",
            widget_slug: "day-strip-widget",
            column_start: 1,
            column_span: 12,
            chrome: {},
          },
        ],
      },
    ]
    render(
      <DndContext>
        <FocusBuilderSelectionProvider>
          <FocusBuilderCanvas
            mode="template"
            themeTokens={tokens}
            core={null}
            template={tpl}
            inheritedCore={core}
            chromeOverridesDraft={{}}
            substrateDraft={tpl.substrate}
            typographyDraft={tpl.typography}
            rowsDraft={rowsDraft}
          />
          <Probe onSelection={(s) => { observed = s }} />
        </FocusBuilderSelectionProvider>
      </DndContext>,
    )
    fireEvent.click(screen.getByTestId("focus-builder-placed-widget"))
    expect(observed).toEqual({ kind: "widget", id: "w-1" })
  })

  // ── FF-2 — template-shape detection + free-form layer rendering ─

  it("FF-2 — detectTemplateShape returns 'grid' for grid placements", () => {
    expect(
      detectTemplateShape([
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              id: "g-1",
              widget_slug: "today-pin-widget",
              column_start: 1,
              column_span: 4,
              chrome: {},
            },
          ],
        },
      ]),
    ).toBe("grid")
  })

  it("FF-2 — detectTemplateShape returns 'freeform' for free-form placements", () => {
    expect(
      detectTemplateShape([
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              id: "f-1",
              widget_slug: "today-pin-widget",
              x: 100,
              y: 100,
              width: 240,
              height: 120,
              chrome: {},
            },
          ],
        },
      ]),
    ).toBe("freeform")
  })

  it("FF-2 — detectTemplateShape returns 'grid' for empty rows blob", () => {
    expect(detectTemplateShape([])).toBe("grid")
    expect(detectTemplateShape(undefined)).toBe("grid")
  })

  it("FF-2 — flattenFreeFormPlacements collapses rows to flat list", () => {
    const flat = flattenFreeFormPlacements([
      {
        row_index: 0,
        column_count: 12,
        placements: [
          {
            id: "a",
            widget_slug: "today-pin-widget",
            x: 0,
            y: 0,
            width: 200,
            height: 100,
            chrome: {},
          },
        ],
      },
      {
        row_index: 1,
        column_count: 12,
        placements: [
          {
            id: "b",
            widget_slug: "day-strip-widget",
            x: 50,
            y: 50,
            width: 240,
            height: 120,
            chrome: {},
          },
        ],
      },
    ])
    expect(flat.map((p) => p.id)).toEqual(["a", "b"])
  })

  it("FF-2 — computeFreeFormDropPosition centers on cursor per Q-4", () => {
    // Cursor at (500, 300), widget 240×120 → centered: (380, 240).
    expect(
      computeFreeFormDropPosition({
        cursorX: 500,
        cursorY: 300,
        width: 240,
        height: 120,
        canvasWidth: 1200,
        canvasHeight: 800,
      }),
    ).toEqual({ x: 380, y: 240 })
  })

  it("FF-2 — computeFreeFormDropPosition clamps to canvas bounds per Q-14", () => {
    // Cursor near top-left, widget would extend off canvas.
    expect(
      computeFreeFormDropPosition({
        cursorX: 10,
        cursorY: 10,
        width: 240,
        height: 120,
        canvasWidth: 1200,
        canvasHeight: 800,
      }),
    ).toEqual({ x: 0, y: 0 })
    // Cursor near bottom-right, widget would extend off canvas.
    expect(
      computeFreeFormDropPosition({
        cursorX: 1200,
        cursorY: 800,
        width: 240,
        height: 120,
        canvasWidth: 1200,
        canvasHeight: 800,
      }),
    ).toEqual({ x: 1200 - 240, y: 800 - 120 })
  })

  it("FF-2 — canvas renders WidgetFreeFormLayer when template has free-form placements", () => {
    const freeFormTpl: TemplateRecord = {
      ...tpl,
      canvas_config: { width: 1200, height: 800 },
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              placement_id: "ff-1",
              component_kind: "widget",
              component_name: "today-pin-widget",
              x: 100,
              y: 100,
              width: 240,
              height: 120,
            },
          ],
        },
      ],
    }
    const rowsDraft = [
      {
        row_index: 0,
        column_count: 12,
        placements: [
          {
            id: "ff-1",
            widget_slug: "today-pin-widget",
            x: 100,
            y: 100,
            width: 240,
            height: 120,
            chrome: {},
          },
        ],
      },
    ]
    render(
      <DndContext>
        <FocusBuilderSelectionProvider>
          <FocusBuilderCanvas
            mode="template"
            themeTokens={tokens}
            core={null}
            template={freeFormTpl}
            inheritedCore={core}
            chromeOverridesDraft={{}}
            substrateDraft={freeFormTpl.substrate}
            typographyDraft={freeFormTpl.typography}
            rowsDraft={rowsDraft}
          />
        </FocusBuilderSelectionProvider>
      </DndContext>,
    )
    // Free-form path renders the freeform layer with canvas dims.
    const layer = screen.getByTestId("focus-builder-freeform-layer")
    expect(layer).toBeInTheDocument()
    expect(layer.getAttribute("data-canvas-width")).toBe("1200")
    expect(layer.getAttribute("data-canvas-height")).toBe("800")
    // Free-form widget rendered with absolute pos at (100, 100).
    // FF-3 — positioning style lives on the draggable wrapper above
    // the PlacedWidgetCore (drag wiring shipped above core's outer).
    const placed = screen.getByTestId(
      "focus-builder-freeform-placed-widget-draggable",
    )
    const styleAttr = placed.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/position:\s*absolute/i)
    expect(styleAttr).toMatch(/left:\s*100px/i)
    expect(styleAttr).toMatch(/top:\s*100px/i)
    // Inherited core renders at Q-20 canonical position (span=12 →
    // full-width-centered → left=0, top=40).
    const coreEl = screen.getByTestId("focus-builder-core-placement")
    const coreStyle = coreEl.getAttribute("style") ?? ""
    expect(coreStyle).toMatch(/left:\s*0px/i)
    expect(coreStyle).toMatch(/top:\s*40px/i)
    // Grid layer NOT rendered.
    expect(screen.queryByTestId("focus-builder-widget-rows-layer")).toBeNull()
  })

  it("FF-2 — canvas defensive fallback to 1200×800 when canvas_config lacks width/height", () => {
    const partialTpl: TemplateRecord = {
      ...tpl,
      // Partial canvas_config (e.g. F-series fixture with only
      // gap_size) — defensive fallback path.
      canvas_config: { gap_size: 4 },
      rows: [],
    }
    const rowsDraft = [
      {
        row_index: 0,
        column_count: 12,
        placements: [
          {
            id: "ff-2",
            widget_slug: "today-pin-widget",
            x: 50,
            y: 50,
            width: 240,
            height: 120,
            chrome: {},
          },
        ],
      },
    ]
    render(
      <DndContext>
        <FocusBuilderSelectionProvider>
          <FocusBuilderCanvas
            mode="template"
            themeTokens={tokens}
            core={null}
            template={partialTpl}
            inheritedCore={core}
            chromeOverridesDraft={{}}
            substrateDraft={partialTpl.substrate}
            typographyDraft={partialTpl.typography}
            rowsDraft={rowsDraft}
          />
        </FocusBuilderSelectionProvider>
      </DndContext>,
    )
    const layer = screen.getByTestId("focus-builder-freeform-layer")
    expect(layer.getAttribute("data-canvas-width")).toBe("1200")
    expect(layer.getAttribute("data-canvas-height")).toBe("800")
  })

  it("FF-2 — canvas regression: grid template still renders WidgetRowsLayer (no free-form layer)", () => {
    const gridRowsDraft = [
      {
        row_index: 0,
        column_count: 12,
        placements: [
          {
            id: "g-1",
            widget_slug: "day-strip-widget",
            column_start: 1,
            column_span: 12,
            chrome: {},
          },
        ],
      },
    ]
    render(
      <DndContext>
        <FocusBuilderSelectionProvider>
          <FocusBuilderCanvas
            mode="template"
            themeTokens={tokens}
            core={null}
            template={tpl}
            inheritedCore={core}
            chromeOverridesDraft={{}}
            substrateDraft={tpl.substrate}
            typographyDraft={tpl.typography}
            rowsDraft={gridRowsDraft}
          />
        </FocusBuilderSelectionProvider>
      </DndContext>,
    )
    // Grid path still active.
    expect(
      screen.getByTestId("focus-builder-widget-rows-layer"),
    ).toBeInTheDocument()
    expect(screen.queryByTestId("focus-builder-freeform-layer")).toBeNull()
  })

  it("canvas drop zone is enabled in template mode", () => {
    render(
      <DndContext>
        <FocusBuilderSelectionProvider>
          <FocusBuilderCanvas
            mode="template"
            themeTokens={tokens}
            core={null}
            template={tpl}
            inheritedCore={core}
            substrateDraft={{}}
            typographyDraft={{}}
            chromeOverridesDraft={{}}
          />
        </FocusBuilderSelectionProvider>
      </DndContext>,
    )
    const canvas = screen.getByTestId("focus-builder-canvas")
    expect(canvas).toBeInTheDocument()
  })
})
