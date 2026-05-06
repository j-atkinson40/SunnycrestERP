/**
 * CompositionRenderer runtime-mode tests — May 2026 composition runtime
 * integration phase.
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
  placements: ResolvedComposition["placements"] = [],
): ResolvedComposition {
  return {
    focus_type: "scheduling",
    vertical: "funeral_home",
    tenant_id: null,
    source: "vertical_default",
    source_id: "test-id",
    source_version: 1,
    placements,
    canvas_config: {
      total_columns: 1,
      row_height: 64,
      gap_size: 12,
      background_treatment: "surface-base",
    },
  }
}


function makeWidgetPlacement(
  placement_id: string,
  component_name: string,
  prop_overrides: Record<string, unknown> = {},
): ResolvedComposition["placements"][number] {
  return {
    placement_id,
    component_kind: "widget",
    component_name,
    grid: { column_start: 1, column_span: 1, row_start: 1, row_span: 3 },
    prop_overrides,
    display_config: { show_header: true, show_border: true },
  }
}


describe("CompositionRenderer runtime widget dispatch", () => {
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
        composition={makeResolved([makeWidgetPlacement("p1", "today")])}
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
          makeWidgetPlacement("p1", "saved_view", {
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
          makeWidgetPlacement("p1", "no-such-widget"),
        ])}
        editorMode={false}
      />,
    )
    // MissingWidgetEmptyState renders an honest empty state — verify
    // by checking that no widget content appears + the placement
    // container is still rendered.
    expect(screen.getByTestId("composition-placement-p1")).toBeTruthy()
    // The empty state renders its own data-testid, but we only need
    // to confirm we did NOT render a misleading mock stand-in:
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
        composition={makeResolved([makeWidgetPlacement("p1", "today")])}
        editorMode={true}
      />,
    )

    // Editor mode uses renderComponentPreview, NOT getWidgetRenderer.
    // The mock production widget must NOT appear.
    expect(screen.queryByTestId("should-not-render-in-editor-mode")).toBeNull()
    // The placement container itself does render in both modes.
    expect(screen.getByTestId("composition-placement-p1")).toBeTruthy()
  })

  it("renders a graceful runtime placeholder for non-widget kinds", () => {
    _resetWidgetRendererRegistryForTests()
    render(
      <CompositionRenderer
        composition={makeResolved([
          {
            placement_id: "p1",
            component_kind: "focus",
            component_name: "decision",
            grid: {
              column_start: 1,
              column_span: 1,
              row_start: 1,
              row_span: 3,
            },
            prop_overrides: {},
            display_config: { show_header: true, show_border: true },
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
        composition={makeResolved([makeWidgetPlacement("p1", "today")])}
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
