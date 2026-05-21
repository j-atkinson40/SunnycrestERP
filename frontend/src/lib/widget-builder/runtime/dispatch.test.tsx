/**
 * WB-2 dispatch + integration tests.
 *
 * Three concerns:
 *   1. dispatchWidgetDefinition routes correctly based on
 *      composition_blob presence.
 *   2. The "composed" widget-renderer registration is wired (the
 *      register side-effect ran).
 *   3. ComposedWidget composes cleanly when embedded in the FF
 *      PlacedWidgetCore-shaped DOM context (Focus Builder substrate
 *      composition correctness).
 */

import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"

import {
  getWidgetRenderer,
  registerWidgetRenderer,
  _resetWidgetRendererRegistryForTests,
} from "@/components/focus/canvas/widget-renderers"

// Side-effect import triggers the WB-2 register call. Imported via
// the canonical path so app-bootstrap parity holds.
import "./register"

import type { CompositionBlob } from "../types/composition-blob"
import { ComposedWidget } from "./ComposedWidget"
import { dispatchWidgetDefinition } from "./dispatch"


function mkBlob(): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "row" },
        children: ["label", "value"],
      },
      label: {
        atom_id: "label",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "lb1" },
      },
      value: {
        atom_id: "value",
        atom_type: "value_display",
        config: { format: "number", format_config: {} },
        binding_refs: { value: "vb1" },
      },
    },
    variants: [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ],
    bindings_catalog: {
      lb1: {
        binding_id: "lb1",
        binding_type: "literal",
        literal_value: "Open cases",
      },
      vb1: {
        binding_id: "vb1",
        binding_type: "literal",
        literal_value: 7,
      },
    },
  }
}


describe("dispatchWidgetDefinition — routing", () => {
  it("routes composition_blob-populated to the 'composed' renderer", () => {
    const result = dispatchWidgetDefinition(
      { widget_id: "composed.cases", composition_blob: mkBlob() },
      { variant_id: "brief", surface: "focus_canvas" },
    )

    // The "composed" key must resolve to a registered renderer
    // (the register side-effect import above wired it).
    expect(result.Renderer).toBe(getWidgetRenderer("composed"))
    // Config carries composition_blob through.
    expect(result.props.config?.composition_blob).toBeDefined()
    expect(result.props.widgetId).toBe("composed.cases")
  })

  it("routes composition_blob-null to widget_id-based renderer (hand-coded path)", () => {
    // Register a fake hand-coded widget so we can confirm dispatch
    // picks it up.
    function FakeHandCoded() {
      return <div data-testid="fake-hand-coded">hand</div>
    }
    registerWidgetRenderer("test.hand_coded", FakeHandCoded)

    try {
      const result = dispatchWidgetDefinition(
        { widget_id: "test.hand_coded", composition_blob: null },
        { surface: "focus_canvas" },
      )
      expect(result.Renderer).toBe(getWidgetRenderer("test.hand_coded"))
      expect(result.props.config?.composition_blob).toBeUndefined()
      expect(result.props.widgetId).toBe("test.hand_coded")
    } finally {
      _resetWidgetRendererRegistryForTests()
      // The composed renderer side-effect import doesn't re-fire after
      // reset; reseat it here so subsequent tests still see it.
      void import("./register")
    }
  })

  it("does NOT mutate the caller's config object when adding composition_blob", () => {
    const callerConfig = { existing: "value" }
    dispatchWidgetDefinition(
      { widget_id: "wid", composition_blob: mkBlob() },
      { config: callerConfig, surface: "focus_canvas" },
    )
    expect(callerConfig).toEqual({ existing: "value" })
    expect((callerConfig as Record<string, unknown>).composition_blob).toBeUndefined()
  })
})


describe("ComposedWidget embedded in FF PlacedWidgetCore-shaped DOM", () => {
  // Mirrors the inner-most shell PlacedWidgetCore wraps its child
  // component with (`<div data-testid="focus-builder-placed-widget-core">`).
  // This verifies that ComposedWidget renders cleanly inside the
  // FF substrate hit-test boundary.
  it("renders inside focus-builder-placed-widget-core wrapper", () => {
    const { container, getByTestId } = render(
      <div
        data-testid="focus-builder-placed-widget"
        style={{ position: "absolute", left: 0, top: 0, width: 200, height: 100 }}
      >
        <div data-testid="focus-builder-placed-widget-core">
          <ComposedWidget
            widgetDefinition={{
              widget_id: "composed.demo",
              composition_blob: mkBlob(),
            }}
            variantId="brief"
          />
        </div>
      </div>,
    )

    // PlacedWidget shell present.
    expect(getByTestId("focus-builder-placed-widget")).not.toBeNull()
    expect(getByTestId("focus-builder-placed-widget-core")).not.toBeNull()

    // ComposedWidget's inner-div (hit-test boundary per hover-fix
    // d9ffd90) is present.
    const innerDiv = container.querySelector(
      "[data-composed-widget-root='true']",
    )
    expect(innerDiv).not.toBeNull()
    expect(innerDiv?.getAttribute("data-widget-id")).toBe("composed.demo")

    // Atom tree rendered.
    expect(container.querySelector("[data-atom-id='root']")).not.toBeNull()
    expect(container.querySelector("[data-atom-id='label']")).not.toBeNull()
    expect(container.querySelector("[data-atom-id='value']")).not.toBeNull()

    // Bindings resolved through to atom output.
    expect(container.textContent).toContain("Open cases")
    expect(container.textContent).toContain("7")
  })
})


describe("Hand-coded widget render path (regression preservation)", () => {
  it("getWidgetRenderer(widget_id) path remains untouched", () => {
    // The existing dispatch contract: callers pass widget_id, get a
    // ComponentType<WidgetRendererProps>. WB-2 must not change this.
    function FakeWidget() {
      return <div data-testid="fake-widget">hand-coded</div>
    }
    registerWidgetRenderer("test.regression", FakeWidget)

    try {
      const Renderer = getWidgetRenderer("test.regression")
      const { getByTestId } = render(
        <Renderer widgetId="test.regression" surface="focus_canvas" />,
      )
      expect(getByTestId("fake-widget").textContent).toBe("hand-coded")
    } finally {
      _resetWidgetRendererRegistryForTests()
      void import("./register")
    }
  })
})
