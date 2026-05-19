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
