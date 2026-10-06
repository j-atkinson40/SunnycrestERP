/**
 * The slice, end to end: sphere -> "the catalog" -> list -> product.
 *
 * ⚠️ THE LAST BLOCK GOES THROUGH THE REAL PROVIDER TREE, deliberately. Everything above it
 * mounts a pane directly, which tests the pane and NOT the composition — CLAUDE.md §11: a
 * test that assembles the pieces itself tests its own assembly. One test drives the real
 * `OpasProvider` + `OpasHost` with only the service and the three contexts doubled.
 *
 * ⚠️ MEASURED FIXTURE, NOT INVENTED. The shapes below are what the endpoints actually
 * return: keys are OMITTED when NULL, so `specs` is absent on a variant with none rather
 * than `{}`. A fixture that sent `specs: {}` would let a bug that renders empty sections
 * pass.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ProductPane } from "./ProductPane"
import { ProductListPane } from "./ProductListPane"

const listVariants = vi.fn()
const getVariant = vi.fn()
const resolvePhrase = vi.fn()

vi.mock("@/services/opas-catalog-service", () => ({
  listVariants: (...a: unknown[]) => listVariants(...a),
  getVariant: (...a: unknown[]) => getVariant(...a),
  resolvePhrase: (...a: unknown[]) => resolvePhrase(...a),
}))

let isAdmin = true
vi.mock("@/contexts/auth-context", () => ({ useAuth: () => ({ isAdmin }) }))
vi.mock("@/core/CommandBarProvider", () => ({
  useCommandBar: () => ({ isOpen: false, open: vi.fn(), close: vi.fn() }),
}))
vi.mock("@/contexts/focus-context", () => ({ useFocus: () => ({ isOpen: false }) }))

const WITH_EVERYTHING = {
  variant_template_id: "v-full",
  name: "Wilbert Bronze Burial Vault",
  kind: "burial_vault",
  sku: "BV-WBR",
  specs: { outside_length_in: "88.5", weight_lb: "3000", spec_source: "2026-02 spec sheet" },
  aliases: ["bronze", "wilbert bronze"],
}
const WITH_NOTHING = {
  variant_template_id: "v-bare",
  name: "Plain Liner",
  kind: "grave_liner",
}

beforeEach(() => {
  listVariants.mockReset()
  getVariant.mockReset()
  resolvePhrase.mockReset()
  isAdmin = true
})

describe("ProductPane renders only what exists", () => {
  it("a variant with specs, a SKU and aliases shows all three sections", async () => {
    getVariant.mockResolvedValue(WITH_EVERYTHING)
    render(<ProductPane variantTemplateId="v-full" />)
    await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())
    expect(screen.getByTestId("opas-product-sku").textContent).toBe("BV-WBR")
    expect(screen.getByTestId("opas-product-specs")).toBeTruthy()
    expect(screen.getByTestId("opas-product-aliases")).toBeTruthy()
    // ⚠️ `spec_source` must travel with the specs — a dimension with no provenance is a
    // number somebody could have typed.
    expect(screen.getByTestId("opas-product-spec-source").textContent).toContain(
      "2026-02 spec sheet",
    )
  })

  it("⚠️ a variant with none of them shows NO sections at all — not empty ones", async () => {
    getVariant.mockResolvedValue(WITH_NOTHING)
    render(<ProductPane variantTemplateId="v-bare" />)
    await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())
    expect(screen.queryByTestId("opas-product-specs")).toBeNull()
    expect(screen.queryByTestId("opas-product-aliases")).toBeNull()
    expect(screen.queryByTestId("opas-product-sku")).toBeNull()
    expect(screen.queryByTestId("opas-product-personalization")).toBeNull()
  })

  it("the personalization pill is absent when the server omits the key — which is always, today", async () => {
    getVariant.mockResolvedValue(WITH_EVERYTHING)
    render(<ProductPane variantTemplateId="v-full" />)
    await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())
    expect(screen.queryByTestId("opas-product-personalization")).toBeNull()
  })

  it("and it DOES render when availability arrives — so the absence above is data, not a stub", async () => {
    getVariant.mockResolvedValue({
      ...WITH_EVERYTHING,
      personalization: [
        { question_id: "legacy_print", label: "Legacy Series™ Print", permitted_answers: ["flag"] },
      ],
    })
    render(<ProductPane variantTemplateId="v-full" />)
    await waitFor(() => expect(screen.getByTestId("opas-product-personalization")).toBeTruthy())
  })

  it("a read failure says so rather than rendering an empty pane", async () => {
    getVariant.mockRejectedValue(new Error("boom"))
    render(<ProductPane variantTemplateId="v-full" />)
    await waitFor(() => expect(screen.getByTestId("opas-product-failed")).toBeTruthy())
  })
})

describe("ProductListPane", () => {
  const ROWS = [
    { variant_template_id: "a", name: "Vault A", kind: "burial_vault", option_label: "Bronze" },
    { variant_template_id: "b", name: "Vault B", kind: "burial_vault" },
    { variant_template_id: "c", name: "Liner C", kind: "grave_liner" },
  ]

  it("groups by kind, preserving the server's order", async () => {
    listVariants.mockResolvedValue(ROWS)
    render(<ProductListPane onOpenProduct={() => {}} />)
    await waitFor(() => expect(screen.getByTestId("opas-product-list")).toBeTruthy())
    expect(screen.getByTestId("opas-list-group-burial_vault")).toBeTruthy()
    expect(screen.getByTestId("opas-list-group-grave_liner")).toBeTruthy()
  })

  it("a row click opens that product", async () => {
    listVariants.mockResolvedValue(ROWS)
    const onOpen = vi.fn()
    render(<ProductListPane onOpenProduct={onOpen} />)
    await waitFor(() => expect(screen.getByTestId("opas-list-row-b")).toBeTruthy())
    fireEvent.click(screen.getByTestId("opas-list-row-b"))
    expect(onOpen).toHaveBeenCalledWith("b")
  })

  it("a numbered pick shows ONLY the candidates, numbered", async () => {
    listVariants.mockResolvedValue(ROWS)
    render(<ProductListPane candidateIds={["a", "c"]} onOpenProduct={() => {}} />)
    await waitFor(() => expect(screen.getByTestId("opas-list-pick")).toBeTruthy())
    expect(screen.getByTestId("opas-list-row-a")).toBeTruthy()
    expect(screen.getByTestId("opas-list-row-c")).toBeTruthy()
    expect(screen.queryByTestId("opas-list-row-b"), "a non-candidate leaked into the pick").toBeNull()
  })

  it("an unmatched phrase is SAID, over the whole catalog", async () => {
    listVariants.mockResolvedValue(ROWS)
    render(<ProductListPane unmatchedPhrase="zzz" onOpenProduct={() => {}} />)
    await waitFor(() => expect(screen.getByTestId("opas-list-unmatched")).toBeTruthy())
    expect(screen.getByTestId("opas-list-unmatched").textContent).toContain("zzz")
    // the whole list is still there
    expect(screen.getByTestId("opas-list-row-b")).toBeTruthy()
  })
})

describe("⚠️ through the REAL provider tree", () => {
  async function mountHost() {
    const { OpasProvider } = await import("@/contexts/opas-context")
    const { OpasHost } = await import("./OpasHost")
    return render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
  }

  it("the sphere is absent for a non-admin", async () => {
    isAdmin = false
    await mountHost()
    expect(screen.queryByTestId("opas-sphere")).toBeNull()
  })

  it("sphere -> 'the catalog' -> the list pane, with no resolver call", async () => {
    listVariants.mockResolvedValue([
      { variant_template_id: "a", name: "Vault A", kind: "burial_vault" },
    ])
    await mountHost()
    fireEvent.click(screen.getByTestId("opas-sphere"))
    const input = screen.getByTestId("opas-input")
    fireEvent.change(input, { target: { value: "the catalog" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    await waitFor(() => expect(screen.getByTestId("opas-product-list")).toBeTruthy())
    // ⚠️ A fixed phrase must not cost a round trip.
    expect(resolvePhrase).not.toHaveBeenCalled()
  })

  it("a product phrase resolving to one candidate opens the Product pane", async () => {
    resolvePhrase.mockResolvedValue({
      phrase: "wilbert bronze", normalized: "wilbert bronze", resolved: true,
      candidates: [{ variant_template_id: "v-full", name: "Wilbert Bronze", kind: "burial_vault" }],
      discriminators: [],
    })
    getVariant.mockResolvedValue(WITH_EVERYTHING)
    await mountHost()
    fireEvent.click(screen.getByTestId("opas-sphere"))
    const input = screen.getByTestId("opas-input")
    fireEvent.change(input, { target: { value: "wilbert bronze" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())
  })

  it("two candidates open a numbered pick and SAY what would narrow it", async () => {
    resolvePhrase.mockResolvedValue({
      phrase: "bronze triune", normalized: "bronze triune", resolved: false,
      candidates: [
        { variant_template_id: "a", name: "A", kind: "burial_vault" },
        { variant_template_id: "b", name: "B", kind: "urn_vault" },
      ],
      discriminators: ["form"],
    })
    listVariants.mockResolvedValue([
      { variant_template_id: "a", name: "A", kind: "burial_vault" },
      { variant_template_id: "b", name: "B", kind: "urn_vault" },
    ])
    await mountHost()
    fireEvent.click(screen.getByTestId("opas-sphere"))
    const input = screen.getByTestId("opas-input")
    fireEvent.change(input, { target: { value: "bronze triune" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    await waitFor(() => expect(screen.getByTestId("opas-list-pick")).toBeTruthy())
    expect(screen.getByTestId("opas-said").textContent).toContain("differs by form")
  })

  it("the veil tucks on POINTERDOWN, and the pane survives", async () => {
    listVariants.mockResolvedValue([
      { variant_template_id: "a", name: "Vault A", kind: "burial_vault" },
    ])
    await mountHost()
    fireEvent.click(screen.getByTestId("opas-sphere"))
    const input = screen.getByTestId("opas-input")
    fireEvent.change(input, { target: { value: "the catalog" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    await waitFor(() => expect(screen.getByTestId("opas-product-list")).toBeTruthy())
    fireEvent.pointerDown(screen.getByTestId("opas-veil"))
    // the command line goes…
    await waitFor(() => expect(screen.queryByTestId("opas-command-line")).toBeNull())
    // …and the pane is still mounted, marked tucked, and the sphere holds the session
    const pane = screen.getByTestId("opas-desk").firstElementChild
    expect(pane?.getAttribute("data-tucked")).toBe("true")
    expect(screen.getByTestId("opas-sphere").getAttribute("data-session")).toBe("true")
  })
})
