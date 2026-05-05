/**
 * Personalization Studio Step 2 — Urn Vault frontend substrate tests.
 *
 * Phase 1A pattern-establisher discipline: Step 2 inherits Step 1's
 * canvas + canvas-state context + types substrate via discriminator
 * differentiation. These tests verify the discriminator dispatch points
 * — emptyCanvasState factory + canvas-state-context provider +
 * PersonalizationCanvas template_type prop — operate symmetrically for
 * the urn template alongside the burial template.
 *
 * Substrate-consumption-follower scope: NO net-new component shipped
 * for Step 2. Tests confirm Step 1 substrate accommodates the urn
 * discriminator value without bespoke chrome. Per §3.26.11.12.16
 * Anti-pattern 4 (primitive count expansion against fifth Focus type
 * rejected) — discriminator differentiation is the canonical extension
 * mechanism.
 */

import { act, render, renderHook, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { PersonalizationCanvas } from "./PersonalizationCanvas"
import {
  PersonalizationCanvasStateProvider,
  usePersonalizationCanvasState,
} from "./canvas-state-context"
import {
  emptyCanvasState,
  TEMPLATE_TYPES,
  type CanvasState,
  type TemplateType,
} from "@/types/personalization-studio"


// ─────────────────────────────────────────────────────────────────────
// Layer 1 — emptyCanvasState factory dispatch
// ─────────────────────────────────────────────────────────────────────


describe("emptyCanvasState — Step 2 urn vault factory dispatch", () => {
  it("returns urn-shaped canvas state for `urn_vault_personalization_studio`", () => {
    const state = emptyCanvasState("urn_vault_personalization_studio")

    expect(state.schema_version).toBe(1)
    expect(state.template_type).toBe("urn_vault_personalization_studio")
    expect(state.canvas_layout.elements).toEqual([])

    // Step 2 substrate-consumption-follower shape: urn_product slot
    // present with null product reference; vault_product slot absent
    // (per Phase 2A factory dispatch).
    expect(state.urn_product).toEqual({
      urn_product_id: null,
      urn_product_name: null,
    })
    expect(state.vault_product).toBeUndefined()

    // 4-options vocabulary preserved per §3.26.11.12.19.6 scope freeze.
    expect(Object.keys(state.options).sort()).toEqual([
      "legacy_print",
      "physical_emblem",
      "physical_nameplate",
      "vinyl",
    ])
    expect(state.options.legacy_print).toBe(null)
    expect(state.options.physical_nameplate).toBe(null)
    expect(state.options.physical_emblem).toBe(null)
    expect(state.options.vinyl).toBe(null)

    // Canonical default fields shared across templates per Step 2 scope-
    // freeze inheritance.
    expect(state.emblem_key).toBe(null)
    expect(state.name_display).toBe(null)
    expect(state.font).toBe(null)
    expect(state.birth_date_display).toBe(null)
    expect(state.death_date_display).toBe(null)
    expect(state.nameplate_text).toBe(null)
    expect(state.family_approval_status).toBe("not_requested")
  })

  it("returns burial-shaped canvas state for `burial_vault_personalization_studio`", () => {
    // Pattern-establisher symmetry: Step 1 shape unchanged post-Step-2.
    const state = emptyCanvasState("burial_vault_personalization_studio")

    expect(state.template_type).toBe("burial_vault_personalization_studio")
    expect(state.vault_product).toEqual({
      vault_product_id: null,
      vault_product_name: null,
    })
    expect(state.urn_product).toBeUndefined()
  })

  it("urn + burial factories share identical 4-options vocabulary keys", () => {
    // §3.26.11.12.19.6 scope freeze: urn vault inherits 4-options
    // vocabulary at category scope; per-template options key set is
    // identical across templates.
    const burial = emptyCanvasState("burial_vault_personalization_studio")
    const urn = emptyCanvasState("urn_vault_personalization_studio")

    expect(Object.keys(urn.options).sort()).toEqual(
      Object.keys(burial.options).sort(),
    )
  })

  it("rejects unknown template_type with helpful canonical error", () => {
    expect(() =>
      emptyCanvasState("future_unknown_template" as unknown as TemplateType),
    ).toThrow(/Unknown template_type/)
  })

  it("TEMPLATE_TYPES constant enumerates Step 1 + Step 2 templates only", () => {
    // Anti-pattern 4 guard: no parallel Focus type substrate; Step 2
    // extends template enum, not Focus type set.
    expect(TEMPLATE_TYPES).toEqual([
      "burial_vault_personalization_studio",
      "urn_vault_personalization_studio",
    ])
  })
})


// ─────────────────────────────────────────────────────────────────────
// Layer 2 — canvas-state-context provider parameterization on urn
// template_type
// ─────────────────────────────────────────────────────────────────────


function makeUrnWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    const initial = emptyCanvasState("urn_vault_personalization_studio")
    return (
      <PersonalizationCanvasStateProvider initialCanvasState={initial}>
        {children}
      </PersonalizationCanvasStateProvider>
    )
  }
}


describe("PersonalizationCanvasStateProvider — Step 2 urn template", () => {
  it("exposes urn-shaped canvas state with urn_product slot", () => {
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeUrnWrapper(),
    })

    expect(result.current.canvasState.template_type).toBe(
      "urn_vault_personalization_studio",
    )
    expect(result.current.canvasState.urn_product).toEqual({
      urn_product_id: null,
      urn_product_name: null,
    })
    expect(result.current.canvasState.vault_product).toBeUndefined()
  })

  it("4-options vocabulary inherited at category scope per scope freeze", () => {
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeUrnWrapper(),
    })

    expect(Object.keys(result.current.canvasState.options).sort()).toEqual([
      "legacy_print",
      "physical_emblem",
      "physical_nameplate",
      "vinyl",
    ])
  })

  it("ephemeral state defaults symmetrical with burial template", () => {
    // Pattern-establisher symmetry: ephemeral substrate (selection +
    // drag + viewport + editing) is template-type-agnostic.
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeUrnWrapper(),
    })

    expect(result.current.selectedElementId).toBe(null)
    expect(result.current.dragInProgress).toBe(null)
    expect(result.current.editing).toBe(null)
    expect(result.current.viewport).toEqual({ zoom: 1, panX: 0, panY: 0 })
  })

  it("applyDragEnd updates urn-canvas element x/y identical to burial", () => {
    // Pattern-establisher inheritance: drag-end mutation is template-
    // type-agnostic. urn_product element drags identically.
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeUrnWrapper(),
    })

    act(() => {
      result.current.setCanvasState({
        ...result.current.canvasState,
        canvas_layout: {
          elements: [
            {
              id: "urn-1",
              element_type: "urn_product",
              x: 100,
              y: 100,
              config: { urn_product_name: "Brass Heritage" },
            },
          ],
        },
      })
    })
    act(() => {
      result.current.applyDragEnd("urn-1", 40, 25)
    })

    expect(result.current.canvasState.canvas_layout.elements[0].x).toBe(140)
    expect(result.current.canvasState.canvas_layout.elements[0].y).toBe(125)
    expect(result.current.dragInProgress).toBe(null)
  })

  it("applyElementUpdate merges config on urn elements", () => {
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeUrnWrapper(),
    })

    act(() => {
      result.current.setCanvasState({
        ...result.current.canvasState,
        canvas_layout: {
          elements: [
            {
              id: "urn-1",
              element_type: "urn_product",
              x: 0,
              y: 0,
              config: { urn_product_name: "Original Urn" },
            },
          ],
        },
      })
    })
    act(() => {
      result.current.applyElementUpdate("urn-1", {
        config: { urn_product_name: "Updated Urn" },
      })
    })

    const el = result.current.canvasState.canvas_layout.elements[0]
    const config = el.config as { urn_product_name: string }
    expect(config.urn_product_name).toBe("Updated Urn")
  })
})


// ─────────────────────────────────────────────────────────────────────
// Layer 3 — PersonalizationCanvas templateType prop dispatch
// ─────────────────────────────────────────────────────────────────────


function renderUrnCanvas(opts: {
  canvasState?: CanvasState
  readOnly?: boolean
} = {}) {
  const initial =
    opts.canvasState ?? emptyCanvasState("urn_vault_personalization_studio")
  return render(
    <PersonalizationCanvasStateProvider initialCanvasState={initial}>
      <PersonalizationCanvas
        templateType="urn_vault_personalization_studio"
        readOnly={opts.readOnly}
      />
    </PersonalizationCanvasStateProvider>,
  )
}


describe("PersonalizationCanvas — Step 2 urn templateType dispatch", () => {
  it("renders canvas root with urn template_type data attr", () => {
    renderUrnCanvas()
    const root = document.querySelector(
      "[data-slot='personalization-canvas']",
    ) as HTMLElement
    expect(root).toBeInTheDocument()
    expect(root.getAttribute("data-template-type")).toBe(
      "urn_vault_personalization_studio",
    )
    expect(root.getAttribute("data-tier")).toMatch(/canvas|stack|icon/)
  })

  it("renders empty-state chrome on urn canvas with no elements", () => {
    // Empty-state chrome is template-type-agnostic per pattern-
    // establisher discipline.
    renderUrnCanvas()
    expect(screen.getByText("Empty canvas")).toBeInTheDocument()
    expect(
      screen.getByText("Drag elements from the palette to begin"),
    ).toBeInTheDocument()
  })

  it("read-only chrome surfaces on urn template at manufacturer_from_fh_share", () => {
    // Read-only banner is canvas-substrate-level chrome inherited from
    // Step 1; surfaces identically on urn template.
    renderUrnCanvas({ readOnly: true })
    const root = document.querySelector(
      "[data-slot='personalization-canvas']",
    ) as HTMLElement
    expect(root.getAttribute("data-read-only")).toBe("true")
    expect(
      screen.getByText(/Read-only — shared from funeral home/),
    ).toBeInTheDocument()
  })

  it("template_type mismatch surfaces error chrome (urn prop vs burial state)", () => {
    // Sanity-check guard at canvas component substrate operates
    // symmetrically across templates.
    const burialState = emptyCanvasState("burial_vault_personalization_studio")
    render(
      <PersonalizationCanvasStateProvider initialCanvasState={burialState}>
        <PersonalizationCanvas templateType="urn_vault_personalization_studio" />
      </PersonalizationCanvasStateProvider>,
    )
    expect(
      document.querySelector("[data-slot='personalization-canvas-mismatch']"),
    ).toBeInTheDocument()
  })

  it("urn-shaped canvas state with urn_product element renders without crash", () => {
    // Step 2 element_type extension: urn_product canvas element renders
    // via shared CanvasElement dispatch substrate (no bespoke chrome
    // needed at Step 2 — pattern-establisher inheritance).
    const state = emptyCanvasState("urn_vault_personalization_studio")
    state.canvas_layout.elements = [
      {
        id: "urn-1",
        element_type: "urn_product",
        x: 200,
        y: 200,
        config: { urn_product_name: "Brass Heritage" },
      },
    ]
    renderUrnCanvas({ canvasState: state })
    expect(
      document.querySelectorAll("[data-slot='personalization-canvas-element']"),
    ).toHaveLength(1)
  })
})
