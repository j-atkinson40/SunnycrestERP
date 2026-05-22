/**
 * VariantsInspectorSection tests — WB-8 CRUD surface.
 *
 * Wraps a real `useVariantAuthoring` hook so the dispatch flow into
 * setDraft is exercised end-to-end. Asserts on DOM affordances +
 * dispatched payloads (operator-observable canon).
 */
import { describe, it, expect, vi } from "vitest"
import { act, fireEvent, render } from "@testing-library/react"
import { renderHook } from "@testing-library/react"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import { useVariantAuthoring } from "../useVariantAuthoring"
import { VariantsInspectorSection } from "./VariantsInspectorSection"


function mkBlob(): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column" },
        children: [],
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


function Harness(props: {
  blob: CompositionBlob
  setDraft: (next: CompositionBlob) => void
  variantWarnings?: Record<string, string[]>
  variantErrors?: string[]
}) {
  const auth = useVariantAuthoring(props.blob, props.setDraft)
  return (
    <VariantsInspectorSection
      blob={props.blob}
      variantAuthoring={auth}
      variantWarnings={props.variantWarnings}
      variantErrors={props.variantErrors}
    />
  )
}


describe("VariantsInspectorSection", () => {
  it("shows empty state when no variants declared", () => {
    const { getByTestId } = render(
      <Harness blob={mkBlob()} setDraft={vi.fn()} />,
    )
    expect(
      getByTestId("widget-builder-variants-inspector-empty"),
    ).toBeTruthy()
  })

  it("renders add buttons for undeclared canonical variants", () => {
    const { getByTestId } = render(
      <Harness blob={mkBlob()} setDraft={vi.fn()} />,
    )
    for (const v of ["glance", "brief", "detail", "deep"]) {
      expect(
        getByTestId(`widget-builder-variants-inspector-add-${v}`),
      ).toBeTruthy()
    }
  })

  it("clicking Add Brief dispatches a declareVariant payload", () => {
    const setDraft = vi.fn()
    const { getByTestId } = render(
      <Harness blob={mkBlob()} setDraft={setDraft} />,
    )
    fireEvent.click(
      getByTestId("widget-builder-variants-inspector-add-brief"),
    )
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants.map((v) => v.variant_id)).toEqual(["brief"])
  })

  it("renders a variant row with default radio + delete button", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const { getByTestId } = render(
      <Harness blob={blob} setDraft={vi.fn()} />,
    )
    expect(
      getByTestId("widget-builder-variant-row-brief"),
    ).toBeTruthy()
    expect(
      getByTestId("widget-builder-variant-row-brief-default-radio"),
    ).toBeTruthy()
    expect(
      getByTestId("widget-builder-variant-row-brief-delete"),
    ).toBeTruthy()
  })

  it("setting default-radio dispatches setDefaultVariantId", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { getByTestId } = render(
      <Harness blob={blob} setDraft={setDraft} />,
    )
    fireEvent.click(
      getByTestId("widget-builder-variant-row-brief-default-radio"),
    )
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.default_variant_id).toBe("brief")
  })

  it("delete button on the default variant is disabled", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    blob.default_variant_id = "brief"
    const { getByTestId } = render(
      <Harness blob={blob} setDraft={vi.fn()} />,
    )
    expect(
      getByTestId(
        "widget-builder-variant-row-brief-delete",
      ).hasAttribute("disabled"),
    ).toBe(true)
  })

  it("delete confirmation flow dispatches removeVariant", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "glance",
        variant_name: "Glance",
        target_surface: "focus_canvas",
      },
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { getByTestId } = render(
      <Harness blob={blob} setDraft={setDraft} />,
    )
    fireEvent.click(getByTestId("widget-builder-variant-row-glance-delete"))
    fireEvent.click(
      getByTestId("widget-builder-variant-row-glance-confirm-delete-yes"),
    )
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants.map((v) => v.variant_id)).toEqual(["brief"])
  })

  it("warnings prop renders per-variant warning chip", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const { getByTestId } = render(
      <Harness
        blob={blob}
        setDraft={vi.fn()}
        variantWarnings={{ brief: ["Mismatched surface"] }}
      />,
    )
    expect(
      getByTestId("widget-builder-variant-row-brief-warnings").textContent,
    ).toMatch(/Mismatched surface/)
  })

  it("variantErrors prop renders blocking error chip", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const { getByTestId } = render(
      <Harness
        blob={blob}
        setDraft={vi.fn()}
        variantErrors={["Missing Glance"]}
      />,
    )
    expect(
      getByTestId("widget-builder-variants-inspector-errors").textContent,
    ).toMatch(/Missing Glance/)
  })

  it("reorder up button moves the variant down in index", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "glance",
        variant_name: "Glance",
        target_surface: "focus_canvas",
      },
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const { getByTestId } = render(
      <Harness blob={blob} setDraft={setDraft} />,
    )
    fireEvent.click(getByTestId("widget-builder-variant-row-brief-up"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants.map((v) => v.variant_id)).toEqual([
      "brief",
      "glance",
    ])
  })

  it("changing target_surface dispatches setTargetSurface", () => {
    const blob = mkBlob()
    blob.variants = [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ]
    const setDraft = vi.fn()
    const setDraftHook = renderHook(() =>
      useVariantAuthoring(blob, setDraft),
    )
    act(() => setDraftHook.result.current.setTargetSurface("brief", "page_canvas"))
    const next = setDraft.mock.calls[0][0] as CompositionBlob
    expect(next.variants[0].target_surface).toBe("page_canvas")
  })
})
