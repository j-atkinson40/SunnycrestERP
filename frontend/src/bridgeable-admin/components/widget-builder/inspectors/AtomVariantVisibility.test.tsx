/**
 * AtomVariantVisibility tests — WB-8 chip-toggle group.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render } from "@testing-library/react"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import { useVariantAuthoring } from "../useVariantAuthoring"
import { AtomVariantVisibility } from "./AtomVariantVisibility"


function mkBlob(): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column" },
        children: ["leaf"],
      },
      leaf: {
        atom_id: "leaf",
        atom_type: "text_label",
        config: { text: "x" },
      },
    },
    variants: [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
      {
        variant_id: "detail",
        variant_name: "Detail",
        target_surface: "focus_canvas",
      },
    ],
    bindings_catalog: {},
  }
}


function Harness(props: {
  blob: CompositionBlob
  atomId: string
  setDraft: (next: CompositionBlob) => void
}) {
  const auth = useVariantAuthoring(props.blob, props.setDraft)
  return (
    <AtomVariantVisibility
      blob={props.blob}
      atomId={props.atomId}
      variantAuthoring={auth}
    />
  )
}


describe("AtomVariantVisibility", () => {
  it("renders empty-state when no variants declared", () => {
    const blob = mkBlob()
    blob.variants = []
    const { getByTestId } = render(
      <Harness blob={blob} atomId="leaf" setDraft={vi.fn()} />,
    )
    expect(getByTestId("atom-variant-visibility-empty")).toBeTruthy()
  })

  it("renders a chip per declared variant", () => {
    const { getByTestId } = render(
      <Harness blob={mkBlob()} atomId="leaf" setDraft={vi.fn()} />,
    )
    expect(getByTestId("atom-variant-visibility-chip-brief")).toBeTruthy()
    expect(getByTestId("atom-variant-visibility-chip-detail")).toBeTruthy()
  })

  it("empty visible_in_variants → mode=all + sentinel hint visible", () => {
    const { getByTestId } = render(
      <Harness blob={mkBlob()} atomId="leaf" setDraft={vi.fn()} />,
    )
    expect(
      getByTestId("atom-variant-visibility").getAttribute("data-mode"),
    ).toBe("all")
    expect(
      getByTestId("atom-variant-visibility-all-variants-hint"),
    ).toBeTruthy()
  })

  it("selecting a chip adds it to visible_in_variants", () => {
    const setDraft = vi.fn()
    const { getByTestId } = render(
      <Harness blob={mkBlob()} atomId="leaf" setDraft={setDraft} />,
    )
    fireEvent.click(getByTestId("atom-variant-visibility-chip-brief"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.atom_tree.leaf.visible_in_variants).toEqual(["brief"])
  })

  it("deselecting the last chip drops the field (default-all sentinel)", () => {
    const blob = mkBlob()
    blob.atom_tree.leaf.visible_in_variants = ["brief"]
    const setDraft = vi.fn()
    const { getByTestId } = render(
      <Harness blob={blob} atomId="leaf" setDraft={setDraft} />,
    )
    fireEvent.click(getByTestId("atom-variant-visibility-chip-brief"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.atom_tree.leaf.visible_in_variants).toBeUndefined()
  })

  it("explicit non-empty selection → mode=explicit (no sentinel hint)", () => {
    const blob = mkBlob()
    blob.atom_tree.leaf.visible_in_variants = ["brief"]
    const { getByTestId, queryByTestId } = render(
      <Harness blob={blob} atomId="leaf" setDraft={vi.fn()} />,
    )
    expect(
      getByTestId("atom-variant-visibility").getAttribute("data-mode"),
    ).toBe("explicit")
    expect(
      queryByTestId("atom-variant-visibility-all-variants-hint"),
    ).toBeNull()
  })

  it("returns null for unknown atom_id", () => {
    const { container } = render(
      <Harness blob={mkBlob()} atomId="missing" setDraft={vi.fn()} />,
    )
    expect(container.firstChild).toBeNull()
  })
})
