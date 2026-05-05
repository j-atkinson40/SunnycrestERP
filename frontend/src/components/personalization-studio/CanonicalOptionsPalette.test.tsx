/**
 * CanonicalOptionsPalette tests — canonical 4-options vocabulary palette
 * per §3.26.11.12.19.2 post-r74 + DESIGN_LANGUAGE §14.14.2 visual canon.
 */

import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CanonicalOptionsPalette } from "./CanonicalOptionsPalette"
import {
  PersonalizationCanvasStateProvider,
  usePersonalizationCanvasState,
} from "./canvas-state-context"
import { emptyCanvasState } from "@/types/personalization-studio"


function renderPalette(opts: {
  displayLabels?: Partial<Record<string, string>>
  readOnly?: boolean
} = {}) {
  return render(
    <PersonalizationCanvasStateProvider
      initialCanvasState={emptyCanvasState("burial_vault_personalization_studio")}
    >
      <CanonicalOptionsPalette
        displayLabels={opts.displayLabels as never}
        readOnly={opts.readOnly}
      />
    </PersonalizationCanvasStateProvider>,
  )
}


describe("CanonicalOptionsPalette — canonical 4-options vocabulary post-r74", () => {
  it("renders canonical 4 options per §3.26.11.12.19.2 default labels", () => {
    renderPalette()
    expect(screen.getByText("Legacy Print")).toBeInTheDocument()
    expect(screen.getByText("Nameplate")).toBeInTheDocument()
    expect(screen.getByText("Emblem")).toBeInTheDocument()
    expect(screen.getByText("Vinyl")).toBeInTheDocument()
  })

  it("data-option-type attributes use canonical post-r74 vocabulary", () => {
    renderPalette()
    const items = document.querySelectorAll("[data-option-type]")
    const optionTypes = Array.from(items).map((el) =>
      el.getAttribute("data-option-type"),
    )
    expect(optionTypes.sort()).toEqual([
      "legacy_print",
      "physical_emblem",
      "physical_nameplate",
      "vinyl",
    ])
    // Canonical post-r74: NO legacy vocabulary surface in DOM.
    expect(optionTypes).not.toContain("nameplate")
    expect(optionTypes).not.toContain("cover_emblem")
    expect(optionTypes).not.toContain("lifes_reflections")
  })

  it("renders canonical Wilbert tenant Workshop Tune mode display label override", () => {
    // Canonical Wilbert tenant per-tenant Workshop Tune mode customization:
    // canonical `vinyl` substrate value displays as "Life's Reflections".
    renderPalette({
      displayLabels: { vinyl: "Life's Reflections" },
    })
    expect(screen.getByText("Life's Reflections")).toBeInTheDocument()
    // Canonical: "Vinyl" default canonically NOT present (overridden).
    expect(screen.queryByText("Vinyl")).toBeNull()
  })

  it("renders canonical Sunnycrest tenant default Workshop Tune mode (no override)", () => {
    renderPalette()
    expect(screen.getByText("Vinyl")).toBeInTheDocument()
    expect(screen.queryByText("Life's Reflections")).toBeNull()
  })

  it("clicking option canonically activates it (data-active=true)", () => {
    renderPalette()
    const vinylBtn = document.querySelector(
      "[data-option-type='vinyl']",
    ) as HTMLElement
    expect(vinylBtn.getAttribute("data-active")).toBe("false")
    fireEvent.click(vinylBtn)
    expect(vinylBtn.getAttribute("data-active")).toBe("true")
  })

  it("clicking activated option canonically deactivates it (toggle)", () => {
    renderPalette()
    const vinylBtn = document.querySelector(
      "[data-option-type='vinyl']",
    ) as HTMLElement
    fireEvent.click(vinylBtn)
    expect(vinylBtn.getAttribute("data-active")).toBe("true")
    fireEvent.click(vinylBtn)
    expect(vinylBtn.getAttribute("data-active")).toBe("false")
  })

  it("read-only mode disables canonical option toggles per `manufacturer_from_fh_share`", () => {
    renderPalette({ readOnly: true })
    const vinylBtn = document.querySelector(
      "[data-option-type='vinyl']",
    ) as HTMLButtonElement
    expect(vinylBtn.disabled).toBe(true)
    expect(vinylBtn.getAttribute("data-active")).toBe("false")
    fireEvent.click(vinylBtn)
    // No state change in read-only canonical mode.
    expect(vinylBtn.getAttribute("data-active")).toBe("false")
  })

  it("activating legacy_print canonically seeds canonical print_name field", () => {
    function StateProbe() {
      const { canvasState } = usePersonalizationCanvasState()
      return (
        <div data-testid="probe">
          {JSON.stringify(canvasState.options.legacy_print)}
        </div>
      )
    }
    render(
      <PersonalizationCanvasStateProvider
        initialCanvasState={emptyCanvasState("burial_vault_personalization_studio")}
      >
        <CanonicalOptionsPalette />
        <StateProbe />
      </PersonalizationCanvasStateProvider>,
    )
    const legacyBtn = document.querySelector(
      "[data-option-type='legacy_print']",
    ) as HTMLElement
    fireEvent.click(legacyBtn)
    const probe = screen.getByTestId("probe")
    expect(probe.textContent).toContain("print_name")
  })
})
