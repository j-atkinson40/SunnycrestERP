/**
 * VariantSwitcher tests — WB-8 segmented control.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render } from "@testing-library/react"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import { VariantSwitcher } from "./VariantSwitcher"


function mkBlob(): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {},
    variants: [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
      },
    ],
    bindings_catalog: {},
  }
}


describe("VariantSwitcher", () => {
  it("renders the 4-canonical-variant + All atoms segments", () => {
    const { getByTestId } = render(
      <VariantSwitcher
        blob={mkBlob()}
        currentVariantId={undefined}
        onChange={vi.fn()}
      />,
    )
    expect(
      getByTestId("widget-builder-variant-switcher-all"),
    ).toBeTruthy()
    for (const v of ["glance", "brief", "detail", "deep"] as const) {
      expect(
        getByTestId(`widget-builder-variant-switcher-${v}`),
      ).toBeTruthy()
    }
  })

  it("marks declared variants clickable + undeclared as disabled", () => {
    const { getByTestId } = render(
      <VariantSwitcher
        blob={mkBlob()}
        currentVariantId={undefined}
        onChange={vi.fn()}
      />,
    )
    const briefBtn = getByTestId("widget-builder-variant-switcher-brief")
    const glanceBtn = getByTestId("widget-builder-variant-switcher-glance")
    expect(briefBtn.getAttribute("data-declared")).toBe("true")
    expect(glanceBtn.getAttribute("data-declared")).toBe("false")
    expect(glanceBtn.hasAttribute("disabled")).toBe(true)
  })

  it("highlights the active variant", () => {
    const { getByTestId } = render(
      <VariantSwitcher
        blob={mkBlob()}
        currentVariantId="brief"
        onChange={vi.fn()}
      />,
    )
    expect(
      getByTestId("widget-builder-variant-switcher-brief").getAttribute(
        "data-active",
      ),
    ).toBe("true")
    expect(
      getByTestId("widget-builder-variant-switcher-all").getAttribute(
        "data-active",
      ),
    ).toBe("false")
  })

  it("clicking All atoms dispatches undefined", () => {
    const onChange = vi.fn()
    const { getByTestId } = render(
      <VariantSwitcher
        blob={mkBlob()}
        currentVariantId="brief"
        onChange={onChange}
      />,
    )
    fireEvent.click(getByTestId("widget-builder-variant-switcher-all"))
    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it("clicking a declared variant dispatches its variantId", () => {
    const onChange = vi.fn()
    const { getByTestId } = render(
      <VariantSwitcher
        blob={mkBlob()}
        currentVariantId={undefined}
        onChange={onChange}
      />,
    )
    fireEvent.click(getByTestId("widget-builder-variant-switcher-brief"))
    expect(onChange).toHaveBeenCalledWith("brief")
  })

  it("clicking an undeclared variant does NOT dispatch", () => {
    const onChange = vi.fn()
    const { getByTestId } = render(
      <VariantSwitcher
        blob={mkBlob()}
        currentVariantId={undefined}
        onChange={onChange}
      />,
    )
    fireEvent.click(getByTestId("widget-builder-variant-switcher-detail"))
    expect(onChange).not.toHaveBeenCalled()
  })

  it("shows empty state when no variants are declared", () => {
    const blob: CompositionBlob = {
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {},
      variants: [],
      bindings_catalog: {},
    }
    const { getByTestId } = render(
      <VariantSwitcher
        blob={blob}
        currentVariantId={undefined}
        onChange={vi.fn()}
      />,
    )
    expect(
      getByTestId("widget-builder-variant-switcher-empty"),
    ).toBeTruthy()
  })
})
