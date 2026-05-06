/**
 * Phase R-0 — EditModeProvider + useEditMode unit tests.
 *
 * Asserts the contract every R-1+ consumer depends on:
 *   - Provider props populate context state correctly.
 *   - useEditMode outside a provider returns the stub (no crash).
 *   - Staging an override updates draftOverrides keyed by overrideKey.
 *   - Multiple stages on same key replace; differing keys accumulate.
 *   - clearStaged removes only the matching (type, target) entries.
 *   - discardDraft resets without touching backend (writers not called).
 *   - commitDraft routes per-type to the correct writer.
 *   - Successful commit clears staged state.
 *   - Failed commit retains staged state + surfaces commitError.
 *   - setEditing(false) clears the per-element selection.
 */
import { act, render, renderHook, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { type ReactNode } from "react"

import {
  EditModeProvider,
  useEditMode,
  __edit_mode_internals,
  type EditModeContextValue,
  type OverrideWriter,
  type RuntimeOverride,
  type RuntimeOverrideType,
} from "./edit-mode-context"


describe("useEditMode outside provider returns stub", () => {
  it("isEditing=false and stub setters don't crash", () => {
    const { result } = renderHook(() => useEditMode())
    expect(result.current.isEditing).toBe(false)
    expect(result.current.tenantSlug).toBeNull()
    expect(result.current.impersonatedUserId).toBeNull()
    expect(result.current.draftOverrides.size).toBe(0)
    expect(() => result.current.setEditing(true)).not.toThrow()
    expect(() => result.current.selectComponent("foo")).not.toThrow()
    expect(() =>
      result.current.stageOverride({
        type: "token",
        target: "accent",
        prop: "value",
        value: "x",
      }),
    ).not.toThrow()
    expect(() => result.current.discardDraft()).not.toThrow()
  })

  it("commitDraft on stub resolves with empty outcome", async () => {
    const { result } = renderHook(() => useEditMode())
    const outcome = await result.current.commitDraft()
    expect(outcome.succeeded).toBe(0)
    expect(outcome.failed).toBe(0)
    expect(outcome.results).toEqual({})
  })
})


function wrapWithProvider(
  override?: Partial<React.ComponentProps<typeof EditModeProvider>>,
) {
  function Wrap({ children }: { children: ReactNode }) {
    return (
      <EditModeProvider
        tenantSlug="hopkins-fh"
        impersonatedUserId="user-123"
        {...override}
      >
        {children}
      </EditModeProvider>
    )
  }
  return Wrap
}


describe("EditModeProvider populates context", () => {
  it("seeds tenantSlug + impersonatedUserId from props", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider(),
    })
    expect(result.current.tenantSlug).toBe("hopkins-fh")
    expect(result.current.impersonatedUserId).toBe("user-123")
  })

  it("initial isEditing matches initialMode prop", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider({ initialMode: "edit" }),
    })
    expect(result.current.isEditing).toBe(true)
  })

  it("initial pageContext matches initialPageContext prop", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider({ initialPageContext: "ops_board" }),
    })
    expect(result.current.pageContext).toBe("ops_board")
  })

  it("setEditing toggles isEditing", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider(),
    })
    expect(result.current.isEditing).toBe(false)
    act(() => result.current.setEditing(true))
    expect(result.current.isEditing).toBe(true)
    act(() => result.current.setEditing(false))
    expect(result.current.isEditing).toBe(false)
  })

  it("setEditing(false) clears per-element selection", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider({ initialMode: "edit" }),
    })
    act(() => result.current.selectComponent("today"))
    expect(result.current.selectedComponentName).toBe("today")
    act(() => result.current.setEditing(false))
    expect(result.current.selectedComponentName).toBeNull()
  })
})


describe("Override staging", () => {
  it("stageOverride adds to draftOverrides", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider(),
    })
    const override: RuntimeOverride = {
      type: "token",
      target: "accent",
      prop: "value",
      value: "oklch(0.5 0.12 39)",
    }
    act(() => result.current.stageOverride(override))
    expect(result.current.draftOverrides.size).toBe(1)
    expect(
      result.current.draftOverrides.get("token::accent::value"),
    ).toEqual(override)
  })

  it("re-staging same key replaces", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider(),
    })
    act(() =>
      result.current.stageOverride({
        type: "token",
        target: "accent",
        prop: "value",
        value: "first",
      }),
    )
    act(() =>
      result.current.stageOverride({
        type: "token",
        target: "accent",
        prop: "value",
        value: "second",
      }),
    )
    expect(result.current.draftOverrides.size).toBe(1)
    expect(
      result.current.draftOverrides.get("token::accent::value")?.value,
    ).toBe("second")
  })

  it("differing prop on same target accumulates", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider(),
    })
    act(() =>
      result.current.stageOverride({
        type: "component_prop",
        target: "widget:today",
        prop: "showRowBreakdown",
        value: false,
      }),
    )
    act(() =>
      result.current.stageOverride({
        type: "component_prop",
        target: "widget:today",
        prop: "refreshIntervalSeconds",
        value: 600,
      }),
    )
    expect(result.current.draftOverrides.size).toBe(2)
  })

  it("clearStaged removes only matching (type, target)", () => {
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider(),
    })
    act(() => {
      result.current.stageOverride({
        type: "component_prop",
        target: "widget:today",
        prop: "showRowBreakdown",
        value: false,
      })
      result.current.stageOverride({
        type: "component_prop",
        target: "widget:today",
        prop: "refreshIntervalSeconds",
        value: 600,
      })
      result.current.stageOverride({
        type: "component_prop",
        target: "widget:anomalies",
        prop: "severityFilter",
        value: "critical",
      })
    })
    expect(result.current.draftOverrides.size).toBe(3)
    act(() => result.current.clearStaged("component_prop", "widget:today"))
    expect(result.current.draftOverrides.size).toBe(1)
    expect(
      result.current.draftOverrides.get(
        "component_prop::widget:anomalies::severityFilter",
      ),
    ).toBeDefined()
  })

  it("discardDraft drops everything without touching backend", async () => {
    const writer = vi.fn()
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider({ writers: { token: writer } }),
    })
    act(() =>
      result.current.stageOverride({
        type: "token",
        target: "accent",
        prop: "value",
        value: "x",
      }),
    )
    expect(result.current.draftOverrides.size).toBe(1)
    act(() => result.current.discardDraft())
    expect(result.current.draftOverrides.size).toBe(0)
    expect(writer).not.toHaveBeenCalled()
  })
})


describe("commitDraft routing", () => {
  function setup() {
    const tokenWriter = vi.fn(async () => {
      /* ok */
    })
    const compPropWriter = vi.fn(async () => {
      /* ok */
    })
    const compClassWriter = vi.fn(async () => {
      /* ok */
    })
    const layoutWriter = vi.fn(async () => {
      /* ok */
    })
    const writers: Record<RuntimeOverrideType, OverrideWriter> = {
      token: tokenWriter,
      component_prop: compPropWriter,
      component_class: compClassWriter,
      dashboard_layout: layoutWriter,
    }
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider({ writers }),
    })
    return { result, tokenWriter, compPropWriter, compClassWriter, layoutWriter }
  }

  it("routes each override type to its writer", async () => {
    const t = setup()
    act(() => {
      t.result.current.stageOverride({
        type: "token",
        target: "accent",
        prop: "value",
        value: "x",
      })
      t.result.current.stageOverride({
        type: "component_prop",
        target: "widget:today",
        prop: "showRowBreakdown",
        value: false,
      })
      t.result.current.stageOverride({
        type: "component_class",
        target: "widget",
        prop: "shadowToken",
        value: "shadow-level-1",
      })
      t.result.current.stageOverride({
        type: "dashboard_layout",
        target: "dashboard",
        prop: "layout_config",
        value: [],
      })
    })

    let outcome: Awaited<ReturnType<EditModeContextValue["commitDraft"]>>
    await act(async () => {
      outcome = await t.result.current.commitDraft()
    })

    expect(t.tokenWriter).toHaveBeenCalledTimes(1)
    expect(t.compPropWriter).toHaveBeenCalledTimes(1)
    expect(t.compClassWriter).toHaveBeenCalledTimes(1)
    expect(t.layoutWriter).toHaveBeenCalledTimes(1)
    expect(outcome!.succeeded).toBe(4)
    expect(outcome!.failed).toBe(0)
    // All-success commit clears staged state.
    expect(t.result.current.draftOverrides.size).toBe(0)
    expect(t.result.current.commitError).toBeNull()
  })

  it("retains staged state + surfaces commitError when a writer fails", async () => {
    const okWriter = vi.fn(async () => {
      /* ok */
    })
    const badWriter = vi.fn(async () => {
      throw new Error("write rejected")
    })
    const { result } = renderHook(() => useEditMode(), {
      wrapper: wrapWithProvider({
        writers: { token: badWriter, component_prop: okWriter },
      }),
    })

    act(() => {
      result.current.stageOverride({
        type: "token",
        target: "accent",
        prop: "value",
        value: "x",
      })
      result.current.stageOverride({
        type: "component_prop",
        target: "widget:today",
        prop: "showRowBreakdown",
        value: false,
      })
    })

    let outcome: Awaited<ReturnType<EditModeContextValue["commitDraft"]>>
    await act(async () => {
      outcome = await result.current.commitDraft()
    })

    expect(outcome!.succeeded).toBe(1)
    expect(outcome!.failed).toBe(1)
    expect(outcome!.errors).toHaveLength(1)
    expect(outcome!.errors[0].reason).toBe("write rejected")
    // Failure leaves staged state intact for retry/correction.
    expect(result.current.draftOverrides.size).toBe(2)
    expect(result.current.commitError).toContain("failed to commit")
  })
})


describe("Component consumes useEditMode", () => {
  function MockConsumer() {
    const ctx = useEditMode()
    return (
      <>
        <span data-testid="is-editing">{ctx.isEditing ? "yes" : "no"}</span>
        <span data-testid="tenant">{ctx.tenantSlug ?? "(none)"}</span>
        <span data-testid="staged-count">{ctx.draftOverrides.size}</span>
        <button
          type="button"
          data-testid="toggle"
          onClick={() => ctx.setEditing(!ctx.isEditing)}
        >
          toggle
        </button>
      </>
    )
  }

  it("renders provider state + responds to actions", () => {
    render(
      <EditModeProvider
        tenantSlug="hopkins-fh"
        impersonatedUserId="u-1"
      >
        <MockConsumer />
      </EditModeProvider>,
    )
    expect(screen.getByTestId("is-editing").textContent).toBe("no")
    expect(screen.getByTestId("tenant").textContent).toBe("hopkins-fh")
    act(() => {
      ;(screen.getByTestId("toggle") as HTMLButtonElement).click()
    })
    expect(screen.getByTestId("is-editing").textContent).toBe("yes")
  })

  it("renders with stub when consumed outside provider", () => {
    render(<MockConsumer />)
    expect(screen.getByTestId("is-editing").textContent).toBe("no")
    expect(screen.getByTestId("tenant").textContent).toBe("(none)")
    expect(screen.getByTestId("staged-count").textContent).toBe("0")
  })
})


describe("overrideKey helper", () => {
  it("encodes (type, target, prop) to a stable string", () => {
    const k = __edit_mode_internals.overrideKey({
      type: "component_prop",
      target: "widget:today",
      prop: "showRowBreakdown",
    })
    expect(k).toBe("component_prop::widget:today::showRowBreakdown")
  })

  it("differs across types for same target/prop", () => {
    const a = __edit_mode_internals.overrideKey({
      type: "component_prop",
      target: "widget:today",
      prop: "value",
    })
    const b = __edit_mode_internals.overrideKey({
      type: "token",
      target: "widget:today",
      prop: "value",
    })
    expect(a).not.toBe(b)
  })
})
