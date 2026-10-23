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

  it("⚠️ THIS PANE IS NO LONGER A PICK — it shows the whole catalog, unnumbered", async () => {
    // ⚠️ RE-POINTED 2026-10-20, AND THE OLD ASSERTION IS THE CONTRAST. It was "a
    // numbered pick shows ONLY the candidates, numbered" and rendered
    // `<ProductListPane candidateIds={["a","c"]}>`, asserting an `opas-list-pick` line
    // and that row "b" was filtered out. James retired that surface: "Replace the
    // floating pick pane... Remove the old pick pane and its code; the bug where it
    // stayed open goes with it." The pick now lives above the bar
    // (`opas-multipane.test.tsx` and `reply.test.ts` cover it).
    //
    // ⚠️ SO THIS ASSERTS THE REMOVAL, which is a claim worth holding: a `candidateIds`
    // prop quietly coming back would restore the stale-list bug, and nothing else
    // would notice.
    listVariants.mockResolvedValue(ROWS)
    render(<ProductListPane onOpenProduct={() => {}} />)
    await waitFor(() => expect(screen.getByTestId("opas-list-row-a")).toBeTruthy())
    expect(screen.queryByTestId("opas-list-pick"), "the pick line came back").toBeNull()
    // every row, not a filtered subset
    expect(screen.getByTestId("opas-list-row-b")).toBeTruthy()
    expect(screen.getByTestId("opas-list-row-c")).toBeTruthy()
  })

  it("⚠️ THE UNMATCHED-PHRASE HEADING IS GONE, by ruling", async () => {
    /**
     * ⚠️ SUPERSEDED BY JAMES 2026-10-23. This test read "an unmatched phrase is SAID,
     * over the whole catalog" and asserted `opas-list-unmatched` carried the phrase
     * while every row stayed on screen. Its original body is preserved in the commit.
     *
     * He typed "anything going to st. marys coming up?" and got that pane: "Nothing
     * matched … The whole catalog:" over every vault the platform sells. The ruling:
     * "A miss should be one honest line above the bar … not a pane full of every vault."
     *
     * ⚠️ THE PROP IS DELETED, NOT LEFT UNSET, so what survives here is that the pane
     * cannot be asked to head itself that way at all. An optional prop with no producer
     * reads as a live feature to the next reader.
     */
    listVariants.mockResolvedValue(ROWS)
    render(<ProductListPane onOpenProduct={() => {}} />)
    await waitFor(() => expect(screen.getByTestId("opas-list-row-b")).toBeTruthy())
    expect(screen.queryByTestId("opas-list-unmatched")).toBeNull()
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
    // ⚠️ RE-POINTED 2026-10-20. It waited on `opas-list-pick` — a line inside the
    // product-list PANE — and that pane is no longer a pick. "Choices sit with the
    // question, not in a floating pane" (James), so the options are above the bar and
    // the pane does not open at all.
    await waitFor(() => expect(screen.getByTestId("opas-options")).toBeTruthy())
    expect(screen.getByTestId("opas-said").textContent).toContain("differ by form")
    // the rows carry the product NAMES, which uuids could not
    expect(screen.getByTestId("opas-option-1").textContent).toContain("A")
    expect(screen.getByTestId("opas-option-2").textContent).toContain("B")
    // ⚠️ AND NO PANE OPENED. This is the removal, asserted: the old branch opened a
    // `product-list` pane alongside the message, and that pane stayed up after the
    // choice was made.
    expect(screen.queryByTestId("opas-list-pick")).toBeNull()
    expect(screen.getByTestId("opas-desk").children.length).toBe(0)
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

describe("⚠️ drag, bring-to-front, and bounds", () => {
  async function mountWithPane() {
    const { OpasProvider } = await import("@/contexts/opas-context")
    const { OpasHost } = await import("./OpasHost")
    listVariants.mockResolvedValue([
      { variant_template_id: "a", name: "Vault A", kind: "burial_vault" },
    ])
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    fireEvent.click(screen.getByTestId("opas-sphere"))
    const input = screen.getByTestId("opas-input")
    fireEvent.change(input, { target: { value: "the catalog" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    await waitFor(() => expect(screen.getByTestId("opas-product-list")).toBeTruthy())
    const pane = screen.getByTestId("opas-desk").firstElementChild as HTMLElement
    const handle = pane.querySelector("[data-testid^='opas-pane-handle-']") as HTMLElement
    return { pane, handle, input }
  }

  /**
   * jsdom has no layout, so the element reports 0×0 and setPointerCapture is absent.
   *
   * ⚠️ CAPTURE IS STUBBED ON THE PANE, NOT ON `target`. Since round 3 the whole pane is the
   * drag surface, so `e.currentTarget` inside the handler is the pane whatever descendant
   * was pressed — and the pointermove listeners are attached there too.
   */
  function drag(
    pane: HTMLElement, from: [number, number], to: [number, number], target?: HTMLElement,
  ) {
    pane.setPointerCapture = () => {}
    pane.releasePointerCapture = () => {}
    const on = target ?? pane
    fireEvent.pointerDown(on, { button: 0, clientX: from[0], clientY: from[1], pointerId: 1 })
    fireEvent.pointerMove(pane, { clientX: to[0], clientY: to[1], pointerId: 1 })
    fireEvent.pointerUp(pane, { pointerId: 1 })
  }

  it("a dragged pane moves to left/top and keeps the position through a tuck and back", async () => {
    const { pane } = await mountWithPane()
    // ⚠️ THE ANCHORED SLOT IS READ FIRST, AND IT IS THE DISCRIMINATOR. Until 2026-10-19
    // an anchored pane used `right` and a dragged one used `left`, so `right === ""`
    // proved the pane had not re-anchored. Anchored panes now use `left` too
    // (`pane-placement.ts`), so that assertion became one that cannot fail — see
    // CLAUDE.md §11, "if a check cannot be made to fail, it is documentation". Comparing
    // against the slot the pane WOULD occupy if it re-anchored is the claim that remains.
    const anchoredLeft = pane.style.left
    expect(anchoredLeft, "an anchored pane has no placement at all").not.toBe("")
    await act(async () => drag(pane, [500, 300], [300, 200]))
    const left = pane.style.left
    expect(left, "the pane did not switch to left/top addressing").not.toBe("")
    expect(left, "the drag did not move it off its anchored slot").not.toBe(anchoredLeft)

    // Esc tucks…
    await act(async () => {
      fireEvent.keyDown(document, { key: "Escape" })
    })
    expect(pane.getAttribute("data-tucked")).toBe("true")
    // …and reopening returns it where it was, not to the cascade slot.
    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-sphere"))
    })
    expect(pane.style.left, "the position did not survive the tuck").toBe(left)
    expect(pane.style.left, "the pane re-anchored across the tuck").not.toBe(anchoredLeft)
  })

  it("⚠️ the 4px dead zone — a 2px nudge is a click, not a drag", async () => {
    const { pane } = await mountWithPane()
    // ⚠️ RE-POINTED 2026-10-19, AND IT USED TO ASSERT `left === ""`. An anchored pane was
    // positioned with `right`, so an empty `left` meant "never dragged". Anchored panes
    // now carry a `left` from the first-free-space placement (`pane-placement.ts`), so
    // that discriminator is gone — and it was never the thing this test was about. The
    // claim is that the position DID NOT MOVE, which is now asserted directly, against
    // the value the pane actually had before the nudge.
    const before = { left: pane.style.left, top: pane.style.top, right: pane.style.right }
    await act(async () => drag(pane, [500, 300], [501, 301]))
    expect(
      { left: pane.style.left, top: pane.style.top, right: pane.style.right },
      "a sub-threshold move became a drag",
    ).toEqual(before)
  })

  it("a pane cannot be dragged fully off screen", async () => {
    const { pane } = await mountWithPane()
    // far past the top-left corner
    await act(async () => drag(pane, [500, 300], [-5000, -5000]))
    const x = parseFloat(pane.style.left)
    const y = parseFloat(pane.style.top)
    expect(y, "clamped below 0").toBeGreaterThanOrEqual(0)
    // KEEP - width, and width is 0 in jsdom, so the floor is KEEP itself
    expect(x, "x was not clamped").toBeGreaterThanOrEqual(-1000)
    expect(Number.isFinite(x)).toBe(true)
  })

  it("clicking a pane brings it to front and marks it focused", async () => {
    const { pane, input } = await mountWithPane()
    // open a second pane
    fireEvent.change(input, { target: { value: "the catalog" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    const panes = Array.from(screen.getByTestId("opas-desk").children) as HTMLElement[]
    expect(panes).toHaveLength(2)
    // the newest arrives at the front
    expect(panes[1].getAttribute("data-focused")).toBe("true")
    expect(panes[0].getAttribute("data-focused")).toBe("false")
    // clicking the first raises it
    await act(async () => {
      fireEvent.pointerDown(pane)
    })
    expect(panes[0].getAttribute("data-focused")).toBe("true")
    expect(panes[1].getAttribute("data-focused")).toBe("false")
    expect(Number(panes[0].style.zIndex)).toBeGreaterThan(Number(panes[1].style.zIndex))
  })

  it("a new pane is placed away from a dragged one, not on top of it", async () => {
    // ⚠️ RENAMED AND RE-POINTED 2026-10-19. It was "a new pane still cascades even after
    // another has been dragged" and asserted `panes[1].style.right !== ""` — the cascade
    // positioned anchored panes with `right`. The cascade is GONE, by James's second
    // multi-pane rule ("A new pane is placed in the first free space, not on top of
    // another"), so `right` is empty on an anchored pane and the old assertion could
    // only fail. What it was protecting — the dragged pane keeps its place and the new
    // one does not land under it — is what is asserted now.
    const { pane, input } = await mountWithPane()
    await act(async () => drag(pane, [500, 300], [300, 200]))
    const draggedLeft = pane.style.left
    fireEvent.change(input, { target: { value: "the catalog" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    const panes = Array.from(screen.getByTestId("opas-desk").children) as HTMLElement[]
    expect(panes[0].style.left, "the dragged pane lost its place").toBe(draggedLeft)
    expect(panes[1].style.left, "the new pane got no placement at all").not.toBe("")
    expect(panes[1].style.left, "the new pane landed on the dragged one").not.toBe(draggedLeft)
  })

  it("⚠️ A CLICK ON A CATALOG ROW OPENS THE PRODUCT AND NEVER STARTS A DRAG", () => {
    // The guarantee whole-pane dragging has to earn. The row is a <button>, so the
    // exclusion catches it — and `closest` catches a click on anything inside it too.
    // Without this the catalog would be unusable: every row click would drag the pane.
    return (async () => {
      const { pane } = await mountWithPane()
      getVariant.mockResolvedValue({
        variant_template_id: "a", name: "Vault A", kind: "burial_vault",
      })
      const rowBtn = screen.getByTestId("opas-list-row-a")
      // ⚠️ SAME RE-POINTING AS THE DEAD ZONE: the claim is that the pane did not MOVE,
      // not that it has no `left`. See that test's note.
      const before = pane.style.left
      await act(async () => drag(pane, [500, 300], [300, 200], rowBtn))
      expect(pane.style.left, "a row click started a drag").toBe(before)
      fireEvent.click(rowBtn)
      await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())
    })()
  })

  it("dragging still works when started on the header", async () => {
    const { pane } = await mountWithPane()
    const header = pane.querySelector("[data-testid^='opas-pane-handle-']") as HTMLElement
    await act(async () => drag(pane, [500, 300], [320, 210], header))
    expect(pane.style.left, "a header drag stopped working").not.toBe("")
  })

  it("and from the pane's own background", async () => {
    const { pane } = await mountWithPane()
    await act(async () => drag(pane, [500, 300], [320, 210], pane))
    expect(pane.style.left).not.toBe("")
  })

  it("⚠️ the close button is excluded too — pressing × must not drag", async () => {
    const { pane } = await mountWithPane()
    const close = pane.querySelector("[data-testid^='opas-pane-close-']") as HTMLElement
    // ⚠️ SAME RE-POINTING AS THE DEAD ZONE. See that test's note.
    const before = pane.style.left
    await act(async () => drag(pane, [500, 300], [300, 200], close))
    expect(pane.style.left).toBe(before)
  })
})

describe("⚠️ Cmd+K — Opas takes it, for sphere-users only", () => {
  async function mountHost2() {
    const { OpasProvider } = await import("@/contexts/opas-context")
    const { OpasHost } = await import("./OpasHost")
    return render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
  }

  it("an admin's Cmd+K opens Opas", async () => {
    await mountHost2()
    expect(screen.queryByTestId("opas-command-line")).toBeNull()
    await act(async () => {
      fireEvent.keyDown(document, { key: "k", metaKey: true })
    })
    expect(screen.getByTestId("opas-command-line")).toBeTruthy()
  })

  it("and a second Cmd+K tucks it — the prototype's isOpen ? tuck() : open()", async () => {
    await mountHost2()
    await act(async () => {
      fireEvent.keyDown(document, { key: "k", metaKey: true })
    })
    await act(async () => {
      fireEvent.keyDown(document, { key: "k", metaKey: true })
    })
    expect(screen.queryByTestId("opas-command-line")).toBeNull()
  })

  it("Ctrl+K works too, for non-Mac", async () => {
    await mountHost2()
    await act(async () => {
      fireEvent.keyDown(document, { key: "K", ctrlKey: true })
    })
    expect(screen.getByTestId("opas-command-line")).toBeTruthy()
  })

  it("⚠️ a NON-ADMIN's Cmd+K is untouched — the listener is never attached", async () => {
    isAdmin = false
    await mountHost2()
    await act(async () => {
      fireEvent.keyDown(document, { key: "k", metaKey: true })
    })
    // nothing of Opas exists at all for a non-admin
    expect(screen.queryByTestId("opas-command-line")).toBeNull()
    expect(screen.queryByTestId("opas-sphere")).toBeNull()
  })

  it("⚠️ modified combinations are left alone — Cmd+Shift+K is not ours", async () => {
    await mountHost2()
    await act(async () => {
      fireEvent.keyDown(document, { key: "k", metaKey: true, shiftKey: true })
    })
    expect(screen.queryByTestId("opas-command-line")).toBeNull()
  })
})

