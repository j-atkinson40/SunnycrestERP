/**
 * canvas-state-context tests — Phase 1B canonical canvas-state context
 * + canonical drag-end + edit-finish helpers + canonical ephemeral
 * state separation from canonical Document substrate.
 */

import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import {
  PersonalizationCanvasStateProvider,
  usePersonalizationCanvasState,
  usePersonalizationCanvasStateOptional,
} from "./canvas-state-context"
import { emptyCanvasState } from "@/types/personalization-studio"


function makeWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    const initial = emptyCanvasState("burial_vault_personalization_studio")
    return (
      <PersonalizationCanvasStateProvider initialCanvasState={initial}>
        {children}
      </PersonalizationCanvasStateProvider>
    )
  }
}


describe("PersonalizationCanvasStateProvider", () => {
  it("exposes canonical empty canvas state with post-r74 4-options vocabulary", () => {
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeWrapper(),
    })
    expect(result.current.canvasState.template_type).toBe(
      "burial_vault_personalization_studio",
    )
    // Canonical 4-options vocabulary post-r74 per §3.26.11.12.19.2.
    expect(Object.keys(result.current.canvasState.options).sort()).toEqual([
      "legacy_print",
      "physical_emblem",
      "physical_nameplate",
      "vinyl",
    ])
    // Canonical post-r74 vocabulary: NO legacy vocabulary.
    expect("nameplate" in result.current.canvasState.options).toBe(false)
    expect("cover_emblem" in result.current.canvasState.options).toBe(false)
    expect("lifes_reflections" in result.current.canvasState.options).toBe(false)
  })

  it("ephemeral state (selection + drag + viewport) starts at canonical defaults", () => {
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeWrapper(),
    })
    expect(result.current.selectedElementId).toBe(null)
    expect(result.current.dragInProgress).toBe(null)
    expect(result.current.editing).toBe(null)
    expect(result.current.viewport).toEqual({ zoom: 1, panX: 0, panY: 0 })
  })

  it("applyDragEnd canonically updates element x/y + clears dragInProgress", () => {
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeWrapper(),
    })
    // Seed canonical canvas with one element.
    act(() => {
      result.current.setCanvasState({
        ...result.current.canvasState,
        canvas_layout: {
          elements: [
            {
              id: "el-1",
              element_type: "name_text",
              x: 100,
              y: 100,
              config: { name_display: "Test" },
            },
          ],
        },
      })
    })
    // Set drag-in-progress state (canonical compositor pattern).
    act(() => {
      result.current.setDragInProgress({ elementId: "el-1", dx: 50, dy: 30 })
    })
    expect(result.current.dragInProgress).toEqual({
      elementId: "el-1",
      dx: 50,
      dy: 30,
    })
    // Canonical drag-end commits dx/dy to canvas state + clears
    // dragInProgress.
    act(() => {
      result.current.applyDragEnd("el-1", 50, 30)
    })
    expect(result.current.canvasState.canvas_layout.elements[0].x).toBe(150)
    expect(result.current.canvasState.canvas_layout.elements[0].y).toBe(130)
    expect(result.current.dragInProgress).toBe(null)
  })

  it("applyElementUpdate canonically merges config updates at edit-finish", () => {
    const { result } = renderHook(() => usePersonalizationCanvasState(), {
      wrapper: makeWrapper(),
    })
    act(() => {
      result.current.setCanvasState({
        ...result.current.canvasState,
        canvas_layout: {
          elements: [
            {
              id: "el-1",
              element_type: "name_text",
              x: 0,
              y: 0,
              config: { name_display: "Original", font: "serif" },
            },
          ],
        },
      })
    })
    act(() => {
      result.current.applyElementUpdate("el-1", {
        config: {
          name_display: "Updated",
          font: "italic",
        },
      })
    })
    const el = result.current.canvasState.canvas_layout.elements[0]
    const config = el.config as { name_display: string; font: string }
    expect(config.name_display).toBe("Updated")
    expect(config.font).toBe("italic")
  })

  it("usePersonalizationCanvasStateOptional returns null when no provider mounted", () => {
    const { result } = renderHook(() => usePersonalizationCanvasStateOptional())
    expect(result.current).toBe(null)
  })

  it("usePersonalizationCanvasState throws when no provider mounted", () => {
    // Mock console.error to suppress React warning about thrown errors
    // during render in test environment.
    const originalError = console.error
    console.error = () => {}
    try {
      expect(() => renderHook(() => usePersonalizationCanvasState())).toThrow()
    } finally {
      console.error = originalError
    }
  })
})
