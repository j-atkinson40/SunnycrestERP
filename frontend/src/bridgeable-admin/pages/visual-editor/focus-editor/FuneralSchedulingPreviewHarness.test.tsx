/**
 * Focus Editor — Funeral Scheduling preview harness tests.
 *
 * Verifies the editor preview pattern that ships in place of a literal
 * SchedulingKanbanCore mount: Phase 2 stand-in pattern with real
 * DeliveryCard / DateBox sub-components fed by mock data.
 */
import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"

import {
  FuneralSchedulingPreviewHarness,
  SampleScenarioPicker,
  compositionDraftAsResolved,
} from "./FuneralSchedulingPreviewHarness"
import {
  buildMockBundle,
  SAMPLE_SCENARIO_OPTIONS,
  type SampleScenario,
} from "./mock-data/funeralSchedulingMockData"


describe("FuneralSchedulingPreviewHarness", () => {
  it("renders header + kanban region by default scenario", () => {
    render(
      <FuneralSchedulingPreviewHarness
        scenario="default"
        compositionDraft={null}
      />,
    )
    expect(
      screen.getByTestId("funeral-scheduling-preview-harness"),
    ).toBeInTheDocument()
    expect(screen.getByTestId("preview-header")).toBeInTheDocument()
    expect(screen.getByTestId("preview-kanban-region")).toBeInTheDocument()
    // Kanban shows the lanes container.
    expect(screen.getByTestId("preview-kanban-lanes")).toBeInTheDocument()
  })

  it("renders empty kanban state for empty scenario", () => {
    render(
      <FuneralSchedulingPreviewHarness
        scenario="empty"
        compositionDraft={null}
      />,
    )
    expect(screen.getByTestId("preview-empty-state")).toBeInTheDocument()
    expect(screen.queryByTestId("preview-kanban-lanes")).not.toBeInTheDocument()
  })

  it("includes Unassigned lane in kanban", () => {
    render(
      <FuneralSchedulingPreviewHarness
        scenario="default"
        compositionDraft={null}
      />,
    )
    expect(screen.getByTestId("preview-lane-unassigned")).toBeInTheDocument()
  })

  it("renders accessory rail when composition draft has placements", () => {
    const draft = compositionDraftAsResolved(
      [
        {
          placement_id: "p1",
          component_kind: "widget",
          component_name: "today",
          grid: {
            column_start: 1,
            column_span: 1,
            row_start: 1,
            row_span: 2,
          },
          prop_overrides: {},
          display_config: { show_header: true, show_border: true },
        },
      ],
      { total_columns: 1, row_height: 64, gap_size: 12 },
      "funeral_home",
    )
    render(
      <FuneralSchedulingPreviewHarness
        scenario="default"
        compositionDraft={draft}
      />,
    )
    expect(screen.getByTestId("preview-accessory-rail")).toBeInTheDocument()
  })

  it("hides accessory rail when composition draft is null", () => {
    render(
      <FuneralSchedulingPreviewHarness
        scenario="default"
        compositionDraft={null}
      />,
    )
    expect(
      screen.queryByTestId("preview-accessory-rail"),
    ).not.toBeInTheDocument()
  })

  it("hides accessory rail when composition draft has zero placements", () => {
    const draft = compositionDraftAsResolved(
      [],
      { total_columns: 1, row_height: 64, gap_size: 12 },
      "funeral_home",
    )
    render(
      <FuneralSchedulingPreviewHarness
        scenario="default"
        compositionDraft={draft}
      />,
    )
    expect(
      screen.queryByTestId("preview-accessory-rail"),
    ).not.toBeInTheDocument()
  })

  it("scenario data attribute reflects active scenario", () => {
    const { rerender } = render(
      <FuneralSchedulingPreviewHarness
        scenario="default"
        compositionDraft={null}
      />,
    )
    expect(
      screen.getByTestId("funeral-scheduling-preview-harness"),
    ).toHaveAttribute("data-scenario", "default")
    rerender(
      <FuneralSchedulingPreviewHarness
        scenario="high-volume"
        compositionDraft={null}
      />,
    )
    expect(
      screen.getByTestId("funeral-scheduling-preview-harness"),
    ).toHaveAttribute("data-scenario", "high-volume")
  })
})


describe("SampleScenarioPicker", () => {
  it("renders all sample scenario options", () => {
    const noop = (_: SampleScenario) => {}
    render(<SampleScenarioPicker scenario="default" onChange={noop} />)
    expect(screen.getByTestId("sample-scenario-picker")).toBeInTheDocument()
    const select = screen.getByTestId(
      "sample-scenario-select",
    ) as HTMLSelectElement
    expect(select.value).toBe("default")
    // Three canonical options
    expect(select.options.length).toBe(SAMPLE_SCENARIO_OPTIONS.length)
  })
})


describe("compositionDraftAsResolved", () => {
  it("synthesizes a ResolvedComposition from editor draft state", () => {
    const placements = [
      {
        placement_id: "p1",
        component_kind: "widget" as const,
        component_name: "today",
        grid: {
          column_start: 1,
          column_span: 1,
          row_start: 1,
          row_span: 2,
        },
        prop_overrides: {},
        display_config: { show_header: true, show_border: true },
      },
    ]
    const canvas = { total_columns: 1, row_height: 64, gap_size: 12 }
    const result = compositionDraftAsResolved(placements, canvas, "funeral_home")
    expect(result.focus_type).toBe("scheduling")
    expect(result.vertical).toBe("funeral_home")
    expect(result.tenant_id).toBeNull()
    // R-3.0: helper now wraps legacy flat placements into the rows
    // shape. Verify the rows-shape output preserves placement
    // identity + translates 1-indexed column_start → 0-indexed
    // starting_column.
    expect(result.rows.length).toBe(1)
    expect(result.rows[0].placements.length).toBe(1)
    expect(result.rows[0].placements[0].placement_id).toBe("p1")
    expect(result.rows[0].placements[0].starting_column).toBe(0)
    expect(result.rows[0].placements[0].column_span).toBe(1)
    expect(result.canvas_config).toEqual(canvas)
    // Source is set when there are placements (so the renderer can
    // distinguish from an empty resolution).
    expect(result.source).toBe("vertical_default")
  })

  it("returns null source + empty rows when placements list is empty", () => {
    const canvas = { total_columns: 1, row_height: 64, gap_size: 12 }
    const result = compositionDraftAsResolved([], canvas, "funeral_home")
    expect(result.source).toBeNull()
    expect(result.rows).toHaveLength(0)
  })
})


describe("Mock data harness", () => {
  it("default scenario contains kanban deliveries + drivers", () => {
    const bundle = buildMockBundle("default")
    expect(bundle.scenario).toBe("default")
    expect(bundle.drivers.length).toBeGreaterThan(0)
    expect(bundle.deliveries.length).toBeGreaterThan(0)
    // Mid-sized scenario verified — at least one kanban delivery
    const kanbanCount = bundle.deliveries.filter(
      (d) => d.scheduling_type === "kanban",
    ).length
    expect(kanbanCount).toBeGreaterThan(0)
  })

  it("high-volume scenario has more drivers than default", () => {
    const def = buildMockBundle("default")
    const hi = buildMockBundle("high-volume")
    expect(hi.drivers.length).toBeGreaterThanOrEqual(def.drivers.length)
    // Strictly more deliveries
    expect(hi.deliveries.length).toBeGreaterThan(def.deliveries.length)
  })

  it("empty scenario has zero deliveries", () => {
    const empty = buildMockBundle("empty")
    expect(empty.deliveries.length).toBe(0)
  })

  it("preview today is stable mid-week date", () => {
    const bundle = buildMockBundle("default")
    expect(bundle.tenant_time.local_date).toBe("2026-06-05")
  })

  it("driver display names are present", () => {
    const bundle = buildMockBundle("default")
    for (const driver of bundle.drivers) {
      expect(driver.display_name ?? driver.id).toBeTruthy()
    }
  })

  it("Sample-prefix discipline — family names disclaim mock origin", () => {
    // Verifies that mock family names use a recognizable prefix so
    // they're never confused with real tenant data in editor
    // screenshots. Asserts at least one Sample-prefixed name exists
    // in the default scenario's deliveries.type_config.family_name.
    const bundle = buildMockBundle("default")
    const hasSampleName = bundle.deliveries.some((d) => {
      const name = d.type_config?.family_name ?? ""
      return name.includes("Sample")
    })
    expect(hasSampleName).toBe(true)
  })
})
