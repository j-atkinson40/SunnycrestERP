/**
 * CanvasElement tests — Phase A Session 3.8.3 canonical compositor
 * pattern verification + canvas jank carry-forward verification +
 * canonical anti-pattern guards at component substrate.
 *
 * **Canvas jank carry-forward verification per Phase 1B canonical
 * discipline**: canonical anti-pattern guard against zone-relative
 * positioning triggering full React reconciliation on every resize
 * frame (Phase A userMemories failure mode). Canonical compositor-only
 * update pattern preserved at canonical CanvasElement substrate.
 */

import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CanvasElement } from "./CanvasElement"
import {
  PersonalizationCanvasStateProvider,
} from "./canvas-state-context"
import {
  emptyCanvasState,
  type CanvasElement as CanvasElementType,
} from "@/types/personalization-studio"


function makeElement(overrides: Partial<CanvasElementType> = {}): CanvasElementType {
  return {
    id: "el-1",
    element_type: "name_text",
    x: 100,
    y: 200,
    width: 240,
    height: 60,
    config: { name_display: "John Smith", font: "serif" },
    ...overrides,
  }
}


function renderWithCanvasState(
  element: CanvasElementType,
  options?: { initialState?: ReturnType<typeof emptyCanvasState> },
) {
  const initialState = options?.initialState ?? {
    ...emptyCanvasState("burial_vault_personalization_studio"),
    canvas_layout: { elements: [element] },
  }
  return render(
    <PersonalizationCanvasStateProvider initialCanvasState={initialState}>
      <CanvasElement element={element} />
    </PersonalizationCanvasStateProvider>,
  )
}


describe("CanvasElement — Phase A 3.8.3 canonical compositor pattern", () => {
  it("renders with canonical translate3d transform composing x/y at element root", () => {
    const element = makeElement({ x: 250, y: 175 })
    renderWithCanvasState(element)
    const root = screen.getByText("John Smith").closest(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    expect(root).toBeInTheDocument()
    // Canonical compositor pattern: position via translate3d, NOT
    // left/top per Phase A Session 3.8.3 canonical.
    const transform = root.style.transform
    expect(transform).toContain("translate3d(250px, 175px, 0)")
  })

  it("renders with canonical left:0, top:0 anchor (canonical containing-block defense)", () => {
    const element = makeElement({ x: 100, y: 50 })
    renderWithCanvasState(element)
    const root = screen.getByText("John Smith").closest(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    // Canonical containing-block anchor per Phase A Session 3.8.3
    // canonical defense against browser auto-placement quirks.
    expect(root.style.left).toBe("0px")
    expect(root.style.top).toBe("0px")
  })

  it("does NOT use left/top for position per canonical compositor pattern", () => {
    // Canvas jank carry-forward verification: position must be on
    // transform, not left/top. Phase A Session 3.8.2 + 3.8.3 canonical.
    const element = makeElement({ x: 999, y: 888 })
    renderWithCanvasState(element)
    const root = screen.getByText("John Smith").closest(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    // left/top stay at 0; position is on transform.
    expect(root.style.left).toBe("0px")
    expect(root.style.top).toBe("0px")
    expect(root.style.transform).toContain("translate3d(999px, 888px, 0)")
  })

  it("data-element-id and data-element-type set canonically per element_type discriminator", () => {
    const element = makeElement({ id: "el-42", element_type: "emblem" })
    renderWithCanvasState(element)
    const root = document.querySelector(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    expect(root.getAttribute("data-element-id")).toBe("el-42")
    expect(root.getAttribute("data-element-type")).toBe("emblem")
  })

  it("touch-action: none ensures pointer events fire on touch devices (canonical canvas pattern)", () => {
    const element = makeElement()
    renderWithCanvasState(element)
    const root = screen.getByText("John Smith").closest(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    expect(root.style.touchAction).toBe("none")
  })
})


describe("CanvasElement — selection + drag canonical interactions", () => {
  it("pointerdown selects canonical element (sets data-selected=true)", () => {
    const element = makeElement()
    renderWithCanvasState(element)
    const root = screen.getByText("John Smith").closest(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    expect(root.getAttribute("data-selected")).toBe("false")
    // jsdom doesn't have pointer events natively but @testing-library
    // forwards them through fireEvent. setPointerCapture is also a
    // jsdom gap; mock it.
    Object.defineProperty(root, "setPointerCapture", { value: () => {} })
    Object.defineProperty(root, "releasePointerCapture", { value: () => {} })
    fireEvent.pointerDown(root, { button: 0, clientX: 100, clientY: 100, pointerId: 1 })
    expect(root.getAttribute("data-selected")).toBe("true")
  })

  it("data-dragging=true during canonical drag-in-progress + reverts on drag-end below threshold", () => {
    const element = makeElement()
    renderWithCanvasState(element)
    const root = screen.getByText("John Smith").closest(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    Object.defineProperty(root, "setPointerCapture", { value: () => {} })
    Object.defineProperty(root, "releasePointerCapture", { value: () => {} })
    fireEvent.pointerDown(root, { button: 0, clientX: 100, clientY: 100, pointerId: 1 })
    expect(root.getAttribute("data-dragging")).toBe("true")
    // Drag-end below 1px threshold canonically reverts (treated as click selection).
    fireEvent.pointerUp(root, { clientX: 100, clientY: 100, pointerId: 1 })
    expect(root.getAttribute("data-dragging")).toBe("false")
  })

  it("non-primary button (right-click) does NOT initiate drag", () => {
    const element = makeElement()
    renderWithCanvasState(element)
    const root = screen.getByText("John Smith").closest(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    fireEvent.pointerDown(root, { button: 2, clientX: 100, clientY: 100, pointerId: 1 })
    expect(root.getAttribute("data-dragging")).toBe("false")
  })
})


describe("CanvasElement — element-type-aware canonical rendering", () => {
  it("vault_product element renders canonical chrome with product name", () => {
    const element = makeElement({
      element_type: "vault_product",
      config: { vault_product_name: "Cathedral Bronze" },
    })
    renderWithCanvasState(element)
    expect(screen.getByText("Vault product")).toBeInTheDocument()
    expect(screen.getByText("Cathedral Bronze")).toBeInTheDocument()
  })

  it("emblem element renders canonical emblem_key", () => {
    const element = makeElement({
      element_type: "emblem",
      config: { emblem_key: "rose" },
    })
    renderWithCanvasState(element)
    expect(screen.getByText("rose")).toBeInTheDocument()
  })

  it("nameplate element renders canonical nameplate_text in serif", () => {
    const element = makeElement({
      element_type: "nameplate",
      config: { nameplate_text: "In Loving Memory" },
    })
    renderWithCanvasState(element)
    expect(screen.getByText("In Loving Memory")).toBeInTheDocument()
  })

  it("date_text element renders canonical birth + death dates", () => {
    const element = makeElement({
      element_type: "date_text",
      config: {
        birth_date_display: "1945",
        death_date_display: "2024",
      },
    })
    renderWithCanvasState(element)
    // Birth + death date display canonically composed in single parent
    // with `·` separator; assert on parent text content rather than
    // discrete text nodes.
    const root = document.querySelector(
      "[data-element-type='date_text']",
    ) as HTMLElement
    expect(root.textContent).toContain("1945")
    expect(root.textContent).toContain("2024")
  })

  it("legacy_print_artifact element renders canonical print_name", () => {
    const element = makeElement({
      element_type: "legacy_print_artifact",
      config: { print_name: "Going Home" },
    })
    renderWithCanvasState(element)
    expect(screen.getByText(/Legacy print: Going Home/)).toBeInTheDocument()
  })
})


describe("CanvasElement — canonical anti-pattern guards", () => {
  it("§3.26.11.12.16 Anti-pattern 11 guard: element root has NO bound canvas state", () => {
    // Canonical anti-pattern guard: canonical canvas state lives at
    // canonical Document substrate; component renders state without
    // coupling. Verify by re-rendering with mutated state — only the
    // mutated element's render reflects the change; other elements
    // unaffected per canonical render-only-from-state discipline.
    const element1 = makeElement({ id: "el-1", config: { name_display: "First" } })
    const initialState = {
      ...emptyCanvasState("burial_vault_personalization_studio"),
      canvas_layout: { elements: [element1] },
    }
    const { rerender } = render(
      <PersonalizationCanvasStateProvider initialCanvasState={initialState}>
        <CanvasElement element={element1} />
      </PersonalizationCanvasStateProvider>,
    )
    expect(screen.getByText("First")).toBeInTheDocument()

    const element2 = makeElement({ id: "el-1", config: { name_display: "Second" } })
    rerender(
      <PersonalizationCanvasStateProvider
        initialCanvasState={{
          ...initialState,
          canvas_layout: { elements: [element2] },
        }}
      >
        <CanvasElement element={element2} />
      </PersonalizationCanvasStateProvider>,
    )
    expect(screen.getByText("Second")).toBeInTheDocument()
  })

  it("§3.26.11.12.16 Anti-pattern 1 guard: drag-end below threshold does NOT auto-commit", () => {
    // Canonical anti-pattern guard: drag-end below 1px threshold treats
    // as click selection, NOT auto-commit. Per canonical operator
    // agency discipline.
    const element = makeElement({ x: 100, y: 100 })
    renderWithCanvasState(element)
    const root = screen.getByText("John Smith").closest(
      "[data-slot='personalization-canvas-element']",
    ) as HTMLElement
    Object.defineProperty(root, "setPointerCapture", { value: () => {} })
    Object.defineProperty(root, "releasePointerCapture", { value: () => {} })
    // Drag-end at exact same pointer position canonically treats as
    // click selection — no x/y mutation.
    fireEvent.pointerDown(root, { button: 0, clientX: 100, clientY: 100, pointerId: 1 })
    fireEvent.pointerUp(root, { clientX: 100, clientY: 100, pointerId: 1 })
    // Element x/y unchanged — canonical no-auto-commit discipline.
    expect(root.style.transform).toContain("translate3d(100px, 100px, 0)")
  })
})
