/**
 * CompositionRenderer runtime-mode tests (R-3.0 rows shape).
 *
 * The runtime path (editorMode={false}) dispatches widget-kind
 * placements via `getWidgetRenderer(component_name)` from the canvas
 * widget registry — same path Pulse + Focus canvas use. Editor mode
 * (editorMode={true}) preserves the existing stylized stand-in
 * renderer. These tests pin both behaviors + the kind-fallback shape.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import {
  registerWidgetRenderer,
  _resetWidgetRendererRegistryForTests,
} from "@/components/focus/canvas/widget-renderers"
import { CompositionRenderer } from "./CompositionRenderer"
import type { ResolvedComposition } from "./types"


function makeResolved(
  rows: ResolvedComposition["rows"] = [],
): ResolvedComposition {
  return {
    focus_type: "scheduling",
    vertical: "funeral_home",
    tenant_id: null,
    source: "vertical_default",
    source_id: "test-id",
    source_version: 1,
    rows,
    canvas_config: {
      gap_size: 12,
      background_treatment: "surface-base",
    },
  }
}


function makeWidgetRow(
  row_id: string,
  placement_id: string,
  component_name: string,
  prop_overrides: Record<string, unknown> = {},
): ResolvedComposition["rows"][number] {
  return {
    row_id,
    column_count: 1,
    row_height: "auto",
    column_widths: null,
    nested_rows: null,
    placements: [
      {
        placement_id,
        component_kind: "widget",
        component_name,
        starting_column: 0,
        column_span: 1,
        prop_overrides,
        display_config: { show_header: true, show_border: true },
        nested_rows: null,
      },
    ],
  }
}


describe("CompositionRenderer runtime widget dispatch (R-3.0)", () => {
  it("dispatches widget-kind placements via getWidgetRenderer in runtime mode", () => {
    _resetWidgetRendererRegistryForTests()
    function MockToday(props: {
      widgetId: string
      surface?: string
      config?: Record<string, unknown>
    }) {
      return (
        <div
          data-testid="mock-today-widget"
          data-widget-id={props.widgetId}
          data-surface={props.surface}
          data-config-keys={JSON.stringify(Object.keys(props.config ?? {}))}
        >
          today widget
        </div>
      )
    }
    registerWidgetRenderer("today", MockToday)

    render(
      <CompositionRenderer
        composition={makeResolved([makeWidgetRow("r1", "p1", "today")])}
        editorMode={false}
      />,
    )

    const widget = screen.getByTestId("mock-today-widget")
    expect(widget).toBeTruthy()
    expect(widget.getAttribute("data-widget-id")).toBe("today")
    expect(widget.getAttribute("data-surface")).toBe("focus_canvas")
  })

  it("passes prop_overrides as config (excluding variant_id) at runtime", () => {
    _resetWidgetRendererRegistryForTests()
    function MockSavedView(props: {
      widgetId: string
      variant_id?: string
      config?: Record<string, unknown>
    }) {
      return (
        <div
          data-testid="mock-saved-view"
          data-widget-id={props.widgetId}
          data-variant-id={props.variant_id ?? ""}
          data-config={JSON.stringify(props.config ?? {})}
        >
          saved view
        </div>
      )
    }
    registerWidgetRenderer("saved_view", MockSavedView)

    render(
      <CompositionRenderer
        composition={makeResolved([
          makeWidgetRow("r1", "p1", "saved_view", {
            variant_id: "brief",
            view_id: "abc-123",
            extra: "passed-through",
          }),
        ])}
        editorMode={false}
      />,
    )

    const widget = screen.getByTestId("mock-saved-view")
    expect(widget.getAttribute("data-variant-id")).toBe("brief")
    const config = JSON.parse(widget.getAttribute("data-config") ?? "{}")
    expect(config).toEqual({ view_id: "abc-123", extra: "passed-through" })
    expect(config.variant_id).toBeUndefined()
  })

  it("falls back to MissingWidgetEmptyState for unregistered widget at runtime", () => {
    _resetWidgetRendererRegistryForTests()
    render(
      <CompositionRenderer
        composition={makeResolved([
          makeWidgetRow("r1", "p1", "no-such-widget"),
        ])}
        editorMode={false}
      />,
    )
    expect(screen.getByTestId("composition-placement-p1")).toBeTruthy()
    expect(screen.queryByTestId("mock-today-widget")).toBeNull()
  })

  it("uses preview stand-in renderer in editor mode (not getWidgetRenderer)", () => {
    _resetWidgetRendererRegistryForTests()
    function MockToday() {
      return <div data-testid="should-not-render-in-editor-mode">no</div>
    }
    registerWidgetRenderer("today", MockToday)

    render(
      <CompositionRenderer
        composition={makeResolved([makeWidgetRow("r1", "p1", "today")])}
        editorMode={true}
      />,
    )
    expect(screen.queryByTestId("should-not-render-in-editor-mode")).toBeNull()
    expect(screen.getByTestId("composition-placement-p1")).toBeTruthy()
  })

  it("renders a graceful runtime placeholder for non-widget kinds", () => {
    _resetWidgetRendererRegistryForTests()
    render(
      <CompositionRenderer
        composition={makeResolved([
          {
            row_id: "r1",
            column_count: 1,
            row_height: "auto",
            column_widths: null,
            nested_rows: null,
            placements: [
              {
                placement_id: "p1",
                component_kind: "focus",
                component_name: "decision",
                starting_column: 0,
                column_span: 1,
                prop_overrides: {},
                display_config: { show_header: true, show_border: true },
                nested_rows: null,
              },
            ],
          },
        ])}
        editorMode={false}
      />,
    )
    expect(screen.getByTestId("composition-runtime-non-widget")).toBeTruthy()
  })

  it("explicit renderPlacement prop wins over both default paths", () => {
    _resetWidgetRendererRegistryForTests()
    function MockToday() {
      return <div data-testid="should-not-render">no</div>
    }
    registerWidgetRenderer("today", MockToday)

    render(
      <CompositionRenderer
        composition={makeResolved([makeWidgetRow("r1", "p1", "today")])}
        editorMode={false}
        renderPlacement={(p) => (
          <div data-testid="custom-render">custom: {p.component_name}</div>
        )}
      />,
    )

    expect(screen.getByTestId("custom-render")).toBeTruthy()
    expect(screen.queryByTestId("should-not-render")).toBeNull()
  })
})
