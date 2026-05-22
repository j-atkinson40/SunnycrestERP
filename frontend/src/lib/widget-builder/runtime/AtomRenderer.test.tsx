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

  it("resolves field_path binding to null when no dataContext provided (WB-6)", () => {
    // Per WB-6: field_path bindings with no per-row / summary dataContext
    // resolve to null. The atom renderer surfaces an empty render.
    // (WB-2's `[bound:case.deceased]` placeholder string is retired.)
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
    // No dataContext → resolves to null → text_label falls back to its
    // default placeholder copy ("Text label").
    expect(container.textContent).toBe("Text label")
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
  it("dispatches to RepeaterAtomRenderer + renders one mock row when no dataContext (WB-6 authoring fallback)", () => {
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
    // WB-6 authoring fallback: 1 structural mock row when no
    // dataContext.rows supplied.
    expect(root?.getAttribute("data-row-count")).toBe("1")
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


describe("AtomRenderer — WB-6 real iteration", () => {
  function renderWithContext(
    atomTree: Record<string, AtomNode>,
    rootId: string,
    bindings: Record<string, BindingRef>,
    dataContext: unknown,
  ) {
    return render(
      <AtomRenderer
        atom={atomTree[rootId]}
        atomTree={atomTree}
        bindingsCatalog={bindings}
        dataContext={dataContext}
      />,
    )
  }

  it("repeater iterates real rows when dataContext.rows is supplied", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: { binding_id: "rows", children: ["row_label"] },
        children: ["row_label"],
        binding_refs: { rows: "rows" },
      },
      row_label: {
        atom_id: "row_label",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "rowTitle" },
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
      rowTitle: {
        binding_id: "rowTitle",
        binding_type: "field_path",
        saved_view_id: "sv1",
        field_path: "title",
        iteration_mode: "per_row",
      },
    }
    const dataContext = {
      rows: [
        { title: "First" },
        { title: "Second" },
        { title: "Third" },
      ],
    }
    const { container } = renderWithContext(tree, "rep", bindings, dataContext)
    const root = container.querySelector("[data-atom-id='rep']")
    expect(root?.getAttribute("data-row-count")).toBe("3")
    expect(container.textContent).toContain("First")
    expect(container.textContent).toContain("Second")
    expect(container.textContent).toContain("Third")
  })

  it("repeater surfaces empty_state when dataContext.rows is empty", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: {
          binding_id: "rows",
          children: ["row_label"],
          empty_state: "Nothing here",
        },
        children: ["row_label"],
        binding_refs: { rows: "rows" },
      },
      row_label: {
        atom_id: "row_label",
        atom_type: "text_label",
        config: { text: "x" },
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
    const { container } = renderWithContext(tree, "rep", bindings, { rows: [] })
    expect(container.textContent).toContain("Nothing here")
  })

  it("repeater respects config.max_rows cap on supplied rows", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: { binding_id: "rows", children: ["row_label"], max_rows: 2 },
        children: ["row_label"],
        binding_refs: { rows: "rows" },
      },
      row_label: {
        atom_id: "row_label",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "rowTitle" },
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
      rowTitle: {
        binding_id: "rowTitle",
        binding_type: "field_path",
        saved_view_id: "sv1",
        field_path: "title",
        iteration_mode: "per_row",
      },
    }
    const dataContext = {
      rows: [
        { title: "First" },
        { title: "Second" },
        { title: "Third" },
        { title: "Fourth" },
      ],
    }
    const { container } = renderWithContext(tree, "rep", bindings, dataContext)
    const root = container.querySelector("[data-atom-id='rep']")
    expect(root?.getAttribute("data-row-count")).toBe("2")
    expect(container.textContent).toContain("First")
    expect(container.textContent).toContain("Second")
    expect(container.textContent).not.toContain("Third")
  })

  it("non-repeater leaf atom resolves single_summary against summary context", () => {
    const tree: Record<string, AtomNode> = {
      v: {
        atom_id: "v",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "sum" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      sum: {
        binding_id: "sum",
        binding_type: "field_path",
        saved_view_id: "sv1",
        field_path: "value",
        iteration_mode: "single_summary",
      },
    }
    const dataContext = {
      __summary: true,
      aggregations: { value: "42 total" },
    }
    const { container } = renderWithContext(tree, "v", bindings, dataContext)
    expect(container.textContent).toBe("42 total")
  })

  it("non-repeater leaf atom resolves single_record against row context", () => {
    const tree: Record<string, AtomNode> = {
      v: {
        atom_id: "v",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "single" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      single: {
        binding_id: "single",
        binding_type: "field_path",
        saved_view_id: "sv1",
        field_path: "title",
        iteration_mode: "single_record",
      },
    }
    const dataContext = {
      __row: true,
      __index: 0,
      title: "First record only",
    }
    const { container } = renderWithContext(tree, "v", bindings, dataContext)
    expect(container.textContent).toBe("First record only")
  })

  it("per-row context spreads row dict so field_path resolves real data", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: { binding_id: "rows", children: ["row_amt"] },
        children: ["row_amt"],
        binding_refs: { rows: "rows" },
      },
      row_amt: {
        atom_id: "row_amt",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "amt" },
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
      amt: {
        binding_id: "amt",
        binding_type: "field_path",
        saved_view_id: "sv1",
        field_path: "amount",
        iteration_mode: "per_row",
      },
    }
    const dataContext = {
      rows: [{ amount: "100 USD" }, { amount: "250 USD" }],
    }
    const { container } = renderWithContext(tree, "rep", bindings, dataContext)
    expect(container.textContent).toContain("100 USD")
    expect(container.textContent).toContain("250 USD")
  })
})


describe("AtomRenderer — WB-5 canvas-preview discriminator", () => {
  function renderWithContext(
    atomTree: Record<string, AtomNode>,
    rootId: string,
    bindings: Record<string, BindingRef>,
    dataContext: unknown,
  ) {
    return render(
      <AtomRenderer
        atom={atomTree[rootId]}
        atomTree={atomTree}
        bindingsCatalog={bindings}
        dataContext={dataContext}
      />,
    )
  }

  it("repeater reads canvas-preview rows via byView[saved_view_id]", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: { binding_id: "rows" },
        children: ["row_label"],
        binding_refs: { rows: "rowsBinding" },
      },
      row_label: {
        atom_id: "row_label",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "labelBinding" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      rowsBinding: {
        binding_id: "rowsBinding",
        binding_type: "field_path",
        saved_view_id: "vRows",
        field_path: "items",
        iteration_mode: "per_row",
      },
      labelBinding: {
        binding_id: "labelBinding",
        binding_type: "field_path",
        saved_view_id: "vRows",
        field_path: "label",
        iteration_mode: "per_row",
      },
    }
    const dataContext = {
      __canvas_preview: true,
      byView: {
        vRows: {
          status: "success",
          data: {
            rows: [{ label: "Alpha" }, { label: "Bravo" }],
            aggregations: null,
            total_count: 2,
            permission_mode: "full",
            masked_fields: [],
          },
        },
      },
    }
    const { container } = renderWithContext(tree, "rep", bindings, dataContext)
    expect(container.textContent).toContain("Alpha")
    expect(container.textContent).toContain("Bravo")
  })

  it("repeater falls back to 1-mock-row when canvas-preview view is loading without previous", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: {},
        children: ["row_label"],
        binding_refs: { rows: "rowsBinding" },
      },
      row_label: {
        atom_id: "row_label",
        atom_type: "text_label",
        config: { text: "row" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      rowsBinding: {
        binding_id: "rowsBinding",
        binding_type: "field_path",
        saved_view_id: "vLoading",
        field_path: "items",
        iteration_mode: "per_row",
      },
    }
    const dataContext = {
      __canvas_preview: true,
      byView: { vLoading: { status: "loading" } },
    }
    // No real rows yet → 1 structural mock row.
    const { container } = renderWithContext(tree, "rep", bindings, dataContext)
    // Renders the row template with the literal "row" placeholder text.
    expect(container.textContent).toContain("row")
  })

  it("single_record leaf at root resolves via canvas-preview map", () => {
    const tree: Record<string, AtomNode> = {
      v: {
        atom_id: "v",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "b" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      b: {
        binding_id: "b",
        binding_type: "field_path",
        saved_view_id: "vSingle",
        field_path: "title",
        iteration_mode: "single_record",
      },
    }
    const dataContext = {
      __canvas_preview: true,
      byView: {
        vSingle: {
          status: "success",
          data: {
            rows: [{ title: "First Record Title" }],
            aggregations: null,
            total_count: 1,
            permission_mode: "full",
            masked_fields: [],
          },
        },
      },
    }
    const { container } = renderWithContext(tree, "v", bindings, dataContext)
    expect(container.textContent).toContain("First Record Title")
  })

  it("uses `previous` rows during optimistic stale refresh", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: {},
        children: ["row_label"],
        binding_refs: { rows: "rowsBinding" },
      },
      row_label: {
        atom_id: "row_label",
        atom_type: "text_label",
        config: {},
        binding_refs: { text: "labelBinding" },
      },
    }
    const bindings: Record<string, BindingRef> = {
      rowsBinding: {
        binding_id: "rowsBinding",
        binding_type: "field_path",
        saved_view_id: "vStale",
        field_path: "items",
        iteration_mode: "per_row",
      },
      labelBinding: {
        binding_id: "labelBinding",
        binding_type: "field_path",
        saved_view_id: "vStale",
        field_path: "label",
        iteration_mode: "per_row",
      },
    }
    const dataContext = {
      __canvas_preview: true,
      byView: {
        vStale: {
          status: "loading",
          previous: {
            rows: [{ label: "StaleOne" }],
            aggregations: null,
            total_count: 1,
            permission_mode: "full",
            masked_fields: [],
          },
        },
      },
    }
    const { container } = renderWithContext(tree, "rep", bindings, dataContext)
    expect(container.textContent).toContain("StaleOne")
  })

  it("preserves WB-6 1-mock-row fallback when dataContext is undefined", () => {
    const tree: Record<string, AtomNode> = {
      rep: {
        atom_id: "rep",
        atom_type: "repeater_atom",
        config: {},
        children: ["row_label"],
      },
      row_label: {
        atom_id: "row_label",
        atom_type: "text_label",
        config: { text: "fallback-row" },
      },
    }
    const { container } = renderWithContext(tree, "rep", {}, undefined)
    expect(container.textContent).toContain("fallback-row")
  })
})
