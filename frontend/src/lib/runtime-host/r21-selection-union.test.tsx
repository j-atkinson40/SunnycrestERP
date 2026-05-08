/**
 * R-2.1 — RuntimeSelection discriminated union + selectSection
 * action + backwards-compat selectedComponentName shim.
 *
 * Mirrors R-3.1's pattern at InteractivePlacementCanvas.tsx:40-46.
 * The shim is essential — InspectorPanel reads selectedComponentName,
 * SelectionOverlay queries `[data-component-name="..."]` against it,
 * runtime-writers may read it. Removal lands in R-2.1.x cleanup.
 */

import { afterEach, describe, expect, it } from "vitest"
import { act, render } from "@testing-library/react"
import { useEffect } from "react"

// R-2.1 — auto-register barrel side-effect-imported so the registry
// is populated before any test touches selectComponent (which walks
// the registry to resolve componentKind).
import "@/lib/visual-editor/registry/auto-register"

import {
  EditModeProvider,
  useEditMode,
  type EditModeContextValue,
} from "./edit-mode-context"


/** Test harness — captures the latest EditModeContextValue into a ref
 *  so each test can drive actions and inspect resulting state. */
function captureCtx(captured: { value: EditModeContextValue | null }) {
  function Inner() {
    const ctx = useEditMode()
    useEffect(() => {
      captured.value = ctx
    })
    return null
  }
  return <Inner />
}


afterEach(() => {
  /* React Testing Library handles unmount cleanup automatically. */
})


describe("R-2.1 — RuntimeSelection discriminated union", () => {
  it("default state is selection={kind:'none'}", () => {
    const captured = { value: null as EditModeContextValue | null }
    render(
      <EditModeProvider tenantSlug="t1" impersonatedUserId="u1">
        {captureCtx(captured)}
      </EditModeProvider>,
    )
    expect(captured.value!.selection).toEqual({ kind: "none" })
    expect(captured.value!.selectedComponentName).toBeNull()
  })

  it("selectComponent transitions to {kind:'component', componentKind, componentName}", async () => {
    const captured = { value: null as EditModeContextValue | null }
    render(
      <EditModeProvider tenantSlug="t1" impersonatedUserId="u1">
        {captureCtx(captured)}
      </EditModeProvider>,
    )
    act(() => {
      captured.value!.selectComponent("delivery-card")
    })
    expect(captured.value!.selection.kind).toBe("component")
    if (captured.value!.selection.kind === "component") {
      expect(captured.value!.selection.componentName).toBe("delivery-card")
      // componentKind resolved via registry lookup
      expect(captured.value!.selection.componentKind).toBe("entity-card")
    }
    // Backwards-compat shim mirrors the new union
    expect(captured.value!.selectedComponentName).toBe("delivery-card")
  })

  it("selectComponent with unknown name still records selection (defensive)", () => {
    const captured = { value: null as EditModeContextValue | null }
    render(
      <EditModeProvider tenantSlug="t1" impersonatedUserId="u1">
        {captureCtx(captured)}
      </EditModeProvider>,
    )
    act(() => {
      captured.value!.selectComponent("unknown-thing")
    })
    expect(captured.value!.selection.kind).toBe("component")
    if (captured.value!.selection.kind === "component") {
      expect(captured.value!.selection.componentName).toBe("unknown-thing")
      // Falls through to "widget" default when registry lookup misses.
      expect(captured.value!.selection.componentKind).toBe("widget")
    }
  })

  it("selectComponent(null) returns to {kind:'none'}", () => {
    const captured = { value: null as EditModeContextValue | null }
    render(
      <EditModeProvider tenantSlug="t1" impersonatedUserId="u1">
        {captureCtx(captured)}
      </EditModeProvider>,
    )
    act(() => {
      captured.value!.selectComponent("delivery-card")
    })
    expect(captured.value!.selection.kind).toBe("component")
    act(() => {
      captured.value!.selectComponent(null)
    })
    expect(captured.value!.selection).toEqual({ kind: "none" })
    expect(captured.value!.selectedComponentName).toBeNull()
  })

  it("selectSection transitions to {kind:'component-section', parentKind, parentName, ...}", () => {
    const captured = { value: null as EditModeContextValue | null }
    render(
      <EditModeProvider tenantSlug="t1" impersonatedUserId="u1">
        {captureCtx(captured)}
      </EditModeProvider>,
    )
    act(() => {
      captured.value!.selectSection(
        "entity-card",
        "delivery-card",
        "delivery-card.header",
      )
    })
    expect(captured.value!.selection.kind).toBe("component-section")
    if (captured.value!.selection.kind === "component-section") {
      expect(captured.value!.selection.parentKind).toBe("entity-card")
      expect(captured.value!.selection.parentName).toBe("delivery-card")
      expect(captured.value!.selection.componentName).toBe(
        "delivery-card.header",
      )
      expect(captured.value!.selection.componentKind).toBe(
        "entity-card-section",
      )
    }
    // Backwards-compat shim returns the SECTION's name (not parent's).
    expect(captured.value!.selectedComponentName).toBe(
      "delivery-card.header",
    )
  })

  it("setEditing(false) clears selection to {kind:'none'}", () => {
    const captured = { value: null as EditModeContextValue | null }
    render(
      <EditModeProvider
        tenantSlug="t1"
        impersonatedUserId="u1"
        initialMode="edit"
      >
        {captureCtx(captured)}
      </EditModeProvider>,
    )
    act(() => {
      captured.value!.selectSection(
        "entity-card",
        "delivery-card",
        "delivery-card.actions",
      )
    })
    expect(captured.value!.selection.kind).toBe("component-section")
    act(() => {
      captured.value!.setEditing(false)
    })
    expect(captured.value!.selection).toEqual({ kind: "none" })
    expect(captured.value!.selectedComponentName).toBeNull()
  })

  it("transitions component → component-section preserve registry-based componentKind", () => {
    const captured = { value: null as EditModeContextValue | null }
    render(
      <EditModeProvider tenantSlug="t1" impersonatedUserId="u1">
        {captureCtx(captured)}
      </EditModeProvider>,
    )
    act(() => {
      captured.value!.selectComponent("delivery-card")
    })
    if (captured.value!.selection.kind === "component") {
      expect(captured.value!.selection.componentKind).toBe("entity-card")
    }
    act(() => {
      captured.value!.selectSection(
        "entity-card",
        "delivery-card",
        "delivery-card.body",
      )
    })
    if (captured.value!.selection.kind === "component-section") {
      // Section's own kind is fixed; parent kind is preserved on section
      // selections.
      expect(captured.value!.selection.componentKind).toBe(
        "entity-card-section",
      )
      expect(captured.value!.selection.parentKind).toBe("entity-card")
    }
  })
})


describe("R-2.1 — useEditMode stub (no provider)", () => {
  it("stub returns selection={kind:'none'} + null selectedComponentName + no-op selectSection", () => {
    const captured = { value: null as EditModeContextValue | null }
    render(captureCtx(captured))
    expect(captured.value!.selection).toEqual({ kind: "none" })
    expect(captured.value!.selectedComponentName).toBeNull()
    // No-op stub — should not throw.
    expect(() =>
      captured.value!.selectSection("entity-card", "x", "x.y"),
    ).not.toThrow()
    // Stub state stays at none after no-op.
    expect(captured.value!.selection).toEqual({ kind: "none" })
  })
})
