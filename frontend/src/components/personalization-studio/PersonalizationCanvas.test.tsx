/**
 * PersonalizationCanvas tests — Phase A 3.8.3 canonical compositor
 * pattern verification at canvas root + canonical viewport canonical
 * + canonical-pattern-establisher discipline.
 */

import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { PersonalizationCanvas } from "./PersonalizationCanvas"
import { PersonalizationCanvasStateProvider } from "./canvas-state-context"
import {
  emptyCanvasState,
  type CanvasState,
} from "@/types/personalization-studio"


function renderCanvas(opts: {
  canvasState?: CanvasState
  templateType?: "burial_vault_personalization_studio"
  readOnly?: boolean
} = {}) {
  const initialState =
    opts.canvasState ??
    emptyCanvasState("burial_vault_personalization_studio")
  return render(
    <PersonalizationCanvasStateProvider initialCanvasState={initialState}>
      <PersonalizationCanvas
        templateType={opts.templateType ?? "burial_vault_personalization_studio"}
        readOnly={opts.readOnly}
      />
    </PersonalizationCanvasStateProvider>,
  )
}


describe("PersonalizationCanvas — canonical chrome + Phase A 3.8.3 pattern", () => {
  it("renders canonical canvas root with template_type + tier data attrs", () => {
    renderCanvas()
    const root = document.querySelector(
      "[data-slot='personalization-canvas']",
    ) as HTMLElement
    expect(root).toBeInTheDocument()
    expect(root.getAttribute("data-template-type")).toBe(
      "burial_vault_personalization_studio",
    )
    expect(root.getAttribute("data-tier")).toMatch(/canvas|stack|icon/)
    expect(root.getAttribute("data-read-only")).toBe("false")
  })

  it("renders canonical empty-state chrome when no elements present", () => {
    renderCanvas()
    expect(screen.getByText("Empty canvas")).toBeInTheDocument()
    expect(
      screen.getByText("Drag elements from the palette to begin"),
    ).toBeInTheDocument()
  })

  it("renders canonical CanvasElement per canvas state element", () => {
    const state = emptyCanvasState("burial_vault_personalization_studio")
    state.canvas_layout.elements = [
      {
        id: "el-1",
        element_type: "name_text",
        x: 100,
        y: 100,
        config: { name_display: "Test Name" },
      },
    ]
    renderCanvas({ canvasState: state })
    expect(screen.getByText("Test Name")).toBeInTheDocument()
    expect(
      document.querySelectorAll("[data-slot='personalization-canvas-element']"),
    ).toHaveLength(1)
  })

  it("renders multiple canvas elements canonically (per element_type dispatch)", () => {
    const state = emptyCanvasState("burial_vault_personalization_studio")
    state.canvas_layout.elements = [
      {
        id: "el-1",
        element_type: "name_text",
        x: 100,
        y: 100,
        config: { name_display: "Name" },
      },
      {
        id: "el-2",
        element_type: "emblem",
        x: 200,
        y: 200,
        config: { emblem_key: "rose" },
      },
      {
        id: "el-3",
        element_type: "date_text",
        x: 300,
        y: 300,
        config: { birth_date_display: "1945", death_date_display: "2024" },
      },
    ]
    renderCanvas({ canvasState: state })
    expect(screen.getByText("Name")).toBeInTheDocument()
    expect(screen.getByText("rose")).toBeInTheDocument()
    // Date element composes birth + death in single parent with separator;
    // assert via parent text content per canonical date_text chrome.
    const dateEl = document.querySelector(
      "[data-element-type='date_text']",
    ) as HTMLElement
    expect(dateEl.textContent).toContain("1945")
    expect(dateEl.textContent).toContain("2024")
  })

  it("read-only chrome surfaces canonical banner per `manufacturer_from_fh_share`", () => {
    renderCanvas({ readOnly: true })
    const root = document.querySelector(
      "[data-slot='personalization-canvas']",
    ) as HTMLElement
    expect(root.getAttribute("data-read-only")).toBe("true")
    expect(screen.getByText(/Read-only — shared from funeral home/)).toBeInTheDocument()
  })

  it("template_type mismatch surfaces canonical error chrome", () => {
    // Canvas state template_type and prop template_type must match
    // canonical per Phase 1B discipline.
    const state = emptyCanvasState("burial_vault_personalization_studio")
    // Simulate canonical mismatch by tampering with state shape.
    const mismatched = {
      ...state,
      template_type: "urn_vault_personalization_studio" as const,
    } as unknown as CanvasState
    render(
      <PersonalizationCanvasStateProvider initialCanvasState={mismatched}>
        <PersonalizationCanvas templateType="burial_vault_personalization_studio" />
      </PersonalizationCanvasStateProvider>,
    )
    expect(
      document.querySelector("[data-slot='personalization-canvas-mismatch']"),
    ).toBeInTheDocument()
  })
})


describe("PersonalizationCanvas — canonical-pattern-establisher discipline", () => {
  it("template_type prop dispatches canonical canvas substrate (Step 2 inheritance point)", () => {
    // Canonical-pattern-establisher: Step 2 inherits canvas via
    // template_type prop dispatch. Phase 1B canonical value:
    // burial_vault_personalization_studio.
    renderCanvas({ templateType: "burial_vault_personalization_studio" })
    const root = document.querySelector(
      "[data-slot='personalization-canvas']",
    ) as HTMLElement
    expect(root.getAttribute("data-template-type")).toBe(
      "burial_vault_personalization_studio",
    )
  })

  it("canvas surface uses canonical scale + pan transform composition", () => {
    renderCanvas()
    const surface = document.querySelector(
      "[data-slot='personalization-canvas-surface']",
    ) as HTMLElement
    // Default viewport: zoom=1, panX=0, panY=0.
    expect(surface.style.transform).toContain("translate3d(0px, 0px, 0)")
    expect(surface.style.transform).toContain("scale(1)")
  })
})
