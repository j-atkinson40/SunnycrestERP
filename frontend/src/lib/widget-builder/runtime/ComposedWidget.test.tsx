/**
 * ComposedWidget tests — WB-2 runtime renderer integration coverage.
 *
 * Covers: root-atom dispatch, inner-div data attributes (load-bearing
 * for hover-fix d9ffd90 hit-test boundary), variant filtering, codec
 * parse-on-input, malformed blob throws.
 */

import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"

import type { CompositionBlob } from "../types/composition-blob"
import { ComposedWidget } from "./ComposedWidget"


function mkBlob(overrides: Partial<CompositionBlob> = {}): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: { atom_id: "root", atom_type: "text_label", config: {} },
    },
    variants: [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ],
    bindings_catalog: {},
    ...overrides,
  }
}


describe("ComposedWidget", () => {
  it("renders inner-div with data-composed-widget-root + data-widget-id", () => {
    const { container } = render(
      <ComposedWidget
        widgetDefinition={{
          widget_id: "composed.test_1",
          composition_blob: mkBlob(),
        }}
      />,
    )
    const innerDiv = container.querySelector(
      "[data-composed-widget-root='true']",
    )
    expect(innerDiv).not.toBeNull()
    expect(innerDiv?.getAttribute("data-widget-id")).toBe("composed.test_1")
  })

  it("renders the root atom via AtomRenderer", () => {
    const { container } = render(
      <ComposedWidget
        widgetDefinition={{
          widget_id: "wid",
          composition_blob: mkBlob({
            root_atom_id: "root",
            atom_tree: {
              root: {
                atom_id: "root",
                atom_type: "text_label",
                config: {},
              },
            },
          }),
        }}
      />,
    )
    expect(container.querySelector("[data-atom-id='root']")).not.toBeNull()
  })

  it("respects variantId prop for atom visibility filtering", () => {
    const { container } = render(
      <ComposedWidget
        widgetDefinition={{
          widget_id: "wid",
          composition_blob: mkBlob({
            root_atom_id: "container",
            atom_tree: {
              container: {
                atom_id: "container",
                atom_type: "conditional_container",
                config: { direction: "row" },
                children: ["glance_only", "detail_only"],
              },
              glance_only: {
                atom_id: "glance_only",
                atom_type: "text_label",
                config: {},
                visible_in_variants: ["glance"],
              },
              detail_only: {
                atom_id: "detail_only",
                atom_type: "text_label",
                config: {},
                visible_in_variants: ["detail"],
              },
            },
          }),
        }}
        variantId="glance"
      />,
    )
    expect(
      container.querySelector("[data-atom-id='glance_only']"),
    ).not.toBeNull()
    expect(container.querySelector("[data-atom-id='detail_only']")).toBeNull()
  })

  it("throws when composition_blob is null (dispatch contract violation)", () => {
    expect(() =>
      render(
        <ComposedWidget
          widgetDefinition={{
            widget_id: "wid",
            composition_blob: null,
          }}
        />,
      ),
    ).toThrow(/no composition_blob/)
  })

  it("throws CompositionBlobParseError on malformed blob (via codec)", () => {
    expect(() =>
      render(
        <ComposedWidget
          widgetDefinition={{
            widget_id: "wid",
            composition_blob: { schema_version: 1 } as unknown,
          }}
        />,
      ),
    ).toThrow()
  })

  it("throws when root_atom_id is not in atom_tree (defense-in-depth)", () => {
    // Construct a blob with valid structural shape but referencing a
    // root_atom_id that doesn't exist in atom_tree. WB-1 codec
    // validates structural shape only; semantic validation lives on
    // the backend. ComposedWidget surfaces clearly at render time.
    expect(() =>
      render(
        <ComposedWidget
          widgetDefinition={{
            widget_id: "wid",
            composition_blob: mkBlob({
              root_atom_id: "missing",
              atom_tree: {
                other: {
                  atom_id: "other",
                  atom_type: "text_label",
                  config: {},
                },
              },
            }),
          }}
        />,
      ),
    ).toThrow(/not found in atom_tree/)
  })

  it("renders a tree with multiple atoms", () => {
    const { container } = render(
      <ComposedWidget
        widgetDefinition={{
          widget_id: "wid",
          composition_blob: mkBlob({
            root_atom_id: "container",
            atom_tree: {
              container: {
                atom_id: "container",
                atom_type: "conditional_container",
                config: { direction: "column" },
                children: ["title", "value"],
              },
              title: {
                atom_id: "title",
                atom_type: "text_label",
                config: {},
              },
              value: {
                atom_id: "value",
                atom_type: "value_display",
                config: { format: "currency", format_config: {} },
              },
            },
          }),
        }}
      />,
    )
    expect(container.querySelector("[data-atom-id='container']")).not.toBeNull()
    expect(container.querySelector("[data-atom-id='title']")).not.toBeNull()
    expect(container.querySelector("[data-atom-id='value']")).not.toBeNull()
  })
})
