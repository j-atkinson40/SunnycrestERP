/**
 * AtomRenderer tests — WB-2 recursive dispatch + variant filtering +
 * binding resolution coverage.
 *
 * Locks the dispatch contract so WB-3+ can replace leaf renderer
 * UI without breaking AtomRenderer's responsibilities.
 */

import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"

import type {
  AtomNode,
  BindingRef,
  VariantId,
} from "../types/composition-blob"
import { AtomRenderer } from "./AtomRenderer"


function renderAtom(
  atomTree: Record<string, AtomNode>,
  rootId: string,
  options: {
    bindingsCatalog?: Record<string, BindingRef>
    variantId?: VariantId
  } = {},
) {
  return render(
    <AtomRenderer
      atom={atomTree[rootId]}
      atomTree={atomTree}
      bindingsCatalog={options.bindingsCatalog ?? {}}
      variantId={options.variantId}
    />,
  )
}


describe("AtomRenderer — dispatch", () => {
  it("dispatches to TextLabelRenderer for atom_type='text_label'", () => {
    const tree: Record<string, AtomNode> = {
      a1: { atom_id: "a1", atom_type: "text_label", config: {} },
    }
    const { container } = renderAtom(tree, "a1")
    const el = container.querySelector("[data-atom-id='a1']")
    expect(el?.getAttribute("data-atom-type")).toBe("text_label")
  })

  it("dispatches to ValueDisplayRenderer for atom_type='value_display'", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "value_display",
        config: { format: "number", format_config: {} },
      },
    }
    const { container } = renderAtom(tree, "a1")
    expect(
      container
        .querySelector("[data-atom-id='a1']")
        ?.getAttribute("data-atom-type"),
    ).toBe("value_display")
  })

  it("dispatches to IconRenderer for atom_type='icon'", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "icon",
        config: { icon_name: "star" },
      },
    }
    const { container } = renderAtom(tree, "a1")
    expect(
      container
        .querySelector("[data-atom-id='a1']")
        ?.getAttribute("data-atom-type"),
    ).toBe("icon")
  })

  it("dispatches to StatusBadgeRenderer for atom_type='status_badge'", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "status_badge",
        config: { status_map: {}, show_icon: false },
      },
    }
    const { container } = renderAtom(tree, "a1")
    expect(
      container
        .querySelector("[data-atom-id='a1']")
        ?.getAttribute("data-atom-type"),
    ).toBe("status_badge")
  })

  it("dispatches to DividerRenderer for atom_type='divider'", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "divider",
        config: { orientation: "horizontal" },
      },
    }
    const { container } = renderAtom(tree, "a1")
    expect(container.querySelector("hr")?.getAttribute("data-atom-id")).toBe(
      "a1",
    )
  })

  it("dispatches to ButtonRenderer for atom_type='button'", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "button",
        config: { action_kind: "navigate", action_config: {} },
      },
    }
    const { container } = renderAtom(tree, "a1")
    expect(
      container.querySelector("button")?.getAttribute("data-atom-id"),
    ).toBe("a1")
  })

  it("dispatches to ImageRenderer for atom_type='image'", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "image",
        config: { source_kind: "url", fit: "cover" },
      },
    }
    const { container } = renderAtom(tree, "a1")
    expect(
      container
        .querySelector("[data-atom-id='a1']")
        ?.getAttribute("data-atom-type"),
    ).toBe("image")
  })

  it("dispatches to ConditionalContainerRenderer with registerComponent wrap", () => {
    const tree: Record<string, AtomNode> = {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "row" },
        children: ["c1"],
      },
      c1: {
        atom_id: "c1",
        atom_type: "text_label",
        config: {},
      },
    }
    const { container } = renderAtom(tree, "root")
    // ConditionalContainer wrapped via registerComponent — should
    // carry a `data-component-name` boundary.
    const wrapper = container.querySelector(
      "[data-component-name='wb-conditional-container-atom']",
    )
    expect(wrapper).not.toBeNull()
    // Inner container div present.
    const containerDiv = container.querySelector("[data-atom-id='root']")
    expect(containerDiv).not.toBeNull()
    expect(containerDiv?.getAttribute("data-atom-type")).toBe(
      "conditional_container",
    )
  })
})


describe("AtomRenderer — variant filtering", () => {
  it("renders all atoms when variantId is undefined", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "text_label",
        config: {},
        visible_in_variants: ["glance"],
      },
    }
    // variantId undefined → renders even though list excludes
    const { container } = renderAtom(tree, "a1")
    expect(container.querySelector("[data-atom-id='a1']")).not.toBeNull()
  })

  it("renders atom when variantId is in visible_in_variants", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "text_label",
        config: {},
        visible_in_variants: ["glance", "brief"],
      },
    }
    const { container } = renderAtom(tree, "a1", { variantId: "glance" })
    expect(container.querySelector("[data-atom-id='a1']")).not.toBeNull()
  })

  it("hides atom when variantId is set but not in visible_in_variants", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "text_label",
        config: {},
        visible_in_variants: ["detail"],
      },
    }
    const { container } = renderAtom(tree, "a1", { variantId: "glance" })
    expect(container.querySelector("[data-atom-id='a1']")).toBeNull()
  })

  it("renders atom when variantId is set and visible_in_variants is omitted", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "text_label",
        config: {},
      },
    }
    const { container } = renderAtom(tree, "a1", { variantId: "brief" })
    expect(container.querySelector("[data-atom-id='a1']")).not.toBeNull()
  })
})


describe("AtomRenderer — recursive conditional_container", () => {
  it("renders single-level children inside container", () => {
    const tree: Record<string, AtomNode> = {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "row" },
        children: ["c1", "c2"],
      },
      c1: { atom_id: "c1", atom_type: "text_label", config: {} },
      c2: {
        atom_id: "c2",
        atom_type: "value_display",
        config: { format: "number", format_config: {} },
      },
    }
    const { container } = renderAtom(tree, "root")
    expect(container.querySelector("[data-atom-id='c1']")).not.toBeNull()
    expect(container.querySelector("[data-atom-id='c2']")).not.toBeNull()
  })

  it("respects 2-level nesting (Phase 1 substrate doesn't crash)", () => {
    const tree: Record<string, AtomNode> = {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "row" },
        children: ["inner"],
      },
      inner: {
        atom_id: "inner",
        atom_type: "conditional_container",
        config: { direction: "column" },
        children: ["leaf"],
      },
      leaf: { atom_id: "leaf", atom_type: "text_label", config: {} },
    }
    const { container } = renderAtom(tree, "root")
    expect(container.querySelector("[data-atom-id='leaf']")).not.toBeNull()
    // 3 nested data-atom-id markers
    expect(container.querySelectorAll("[data-atom-id]").length).toBe(3)
  })

  it("filters child atoms by variant before recursive descent", () => {
    const tree: Record<string, AtomNode> = {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "row" },
        children: ["c1", "c2"],
      },
      c1: {
        atom_id: "c1",
        atom_type: "text_label",
        config: {},
        visible_in_variants: ["glance"],
      },
      c2: {
        atom_id: "c2",
        atom_type: "text_label",
        config: {},
        visible_in_variants: ["detail"],
      },
    }
    const { container } = renderAtom(tree, "root", { variantId: "glance" })
    expect(container.querySelector("[data-atom-id='c1']")).not.toBeNull()
    expect(container.querySelector("[data-atom-id='c2']")).toBeNull()
  })

  it("gracefully skips dangling child references", () => {
    const tree: Record<string, AtomNode> = {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "row" },
        children: ["missing", "ok"],
      },
      ok: { atom_id: "ok", atom_type: "text_label", config: {} },
    }
    const { container } = renderAtom(tree, "root")
    expect(container.querySelector("[data-atom-id='ok']")).not.toBeNull()
  })
})


describe("AtomRenderer — binding resolution", () => {
  it("resolves literal binding and passes to renderer", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "b1" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      b1: {
        binding_id: "b1",
        binding_type: "literal",
        literal_value: "Hello bound",
      },
    }
    const { container } = renderAtom(tree, "a1", {
      bindingsCatalog: bindings,
    })
    expect(container.textContent).toBe("Hello bound")
  })

  it("resolves field_path binding to placeholder string", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "b1" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      b1: {
        binding_id: "b1",
        binding_type: "field_path",
        saved_view_id: "sv-1",
        field_path: "case.deceased",
        iteration_mode: "single_record",
      },
    }
    const { container } = renderAtom(tree, "a1", {
      bindingsCatalog: bindings,
    })
    expect(container.textContent).toBe("[bound:case.deceased]")
  })

  it("surfaces placeholder for dangling binding_id without crashing", () => {
    const tree: Record<string, AtomNode> = {
      a1: {
        atom_id: "a1",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "missing-binding" },
      },
    }
    const { container } = renderAtom(tree, "a1", { bindingsCatalog: {} })
    expect(container.textContent).toBe("[unbound:missing-binding]")
  })
})


describe("AtomRenderer — repeater_atom dispatch (WB-3)", () => {
  it("dispatches to RepeaterAtomRenderer + renders one mock row in Phase 1", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: {
          binding_id: "rows",
          children: ["row_label"],
          direction: "column",
          spacing: "normal",
        },
        children: ["row_label"],
        binding_refs: { rows: "rows" },
      },
      row_label: {
        atom_id: "row_label",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "rowLabel" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      rows: {
        binding_id: "rows",
        binding_type: "field_path",
        saved_view_id: "sv1",
        field_path: "items",
        iteration_mode: "per_row",
      },
      rowLabel: {
        binding_id: "rowLabel",
        binding_type: "field_path",
        saved_view_id: "sv1",
        field_path: "title",
        iteration_mode: "per_row",
      },
    }
    const { container } = renderAtom(tree, "rep", {
      bindingsCatalog: bindings,
    })
    const root = container.querySelector("[data-atom-id='rep']")
    expect(root).not.toBeNull()
    expect(root?.getAttribute("data-atom-type")).toBe("repeater_atom")
    // 1 mock row in Phase 1.
    expect(root?.getAttribute("data-row-count")).toBe("1")
    // Per-row binding context surfaces via resolveBinding marker.
    expect(container.textContent).toMatch(/\[bound:row\.title#0\]/)
  })

  it("throws at render time when a repeater contains a repeater (defense-in-depth)", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: { binding_id: "rows", children: ["inner"] },
        children: ["inner"],
        binding_refs: { rows: "rows" },
      },
      inner: {
        atom_id: "inner",
        atom_type: "repeater_atom",
        config: { binding_id: "rows", children: [] },
        children: [],
        binding_refs: { rows: "rows" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      rows: {
        binding_id: "rows",
        binding_type: "field_path",
        saved_view_id: "sv1",
        field_path: "items",
        iteration_mode: "per_row",
      },
    }
    expect(() => renderAtom(tree, "rep", { bindingsCatalog: bindings })).toThrow(
      /repeater_atom .* may not contain another repeater_atom/,
    )
  })
})
