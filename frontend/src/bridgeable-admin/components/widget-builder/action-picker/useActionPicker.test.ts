/**
 * useActionPicker — verb-switch state machine tests (Lock 4c).
 */
import { describe, expect, it, vi } from "vitest"
import { renderHook, act } from "@testing-library/react"

import type { ActionRef } from "@/lib/widget-builder/types/composition-blob"

import { useActionPicker } from "./useActionPicker"
import { makeDefaultAction } from "./types"


describe("useActionPicker", () => {
  it("first verb selection wires defaults (no confirm)", () => {
    const onChange = vi.fn()
    const { result } = renderHook(() =>
      useActionPicker({ value: null, onChange }),
    )
    act(() => result.current.selectVerb("navigate"))
    expect(onChange).toHaveBeenCalled()
    expect(onChange.mock.calls[0][0].action_kind).toBe("navigate")
    expect(result.current.pendingVerb).toBeNull()
  })

  it("same-verb selection is a no-op", () => {
    const onChange = vi.fn()
    const action: ActionRef = makeDefaultAction("navigate")
    const { result } = renderHook(() =>
      useActionPicker({ value: action, onChange }),
    )
    act(() => result.current.selectVerb("navigate"))
    expect(onChange).not.toHaveBeenCalled()
  })

  it("switch from non-default content surfaces pendingVerb", () => {
    const onChange = vi.fn()
    const action: ActionRef = {
      action_kind: "navigate",
      href: "/x",
      params: [],
      confirm_before: false,
    }
    const { result } = renderHook(() =>
      useActionPicker({ value: action, onChange }),
    )
    act(() => result.current.selectVerb("trigger_workflow"))
    expect(result.current.pendingVerb).toBe("trigger_workflow")
    expect(onChange).not.toHaveBeenCalled()
    act(() => result.current.commitPendingVerb())
    expect(onChange).toHaveBeenCalled()
    expect(onChange.mock.calls[0][0].action_kind).toBe("trigger_workflow")
    expect(result.current.pendingVerb).toBeNull()
  })

  it("cancelPendingVerb clears the pending state", () => {
    const onChange = vi.fn()
    const action: ActionRef = {
      action_kind: "navigate",
      href: "/x",
      params: [],
      confirm_before: false,
    }
    const { result } = renderHook(() =>
      useActionPicker({ value: action, onChange }),
    )
    act(() => result.current.selectVerb("mutate"))
    expect(result.current.pendingVerb).toBe("mutate")
    act(() => result.current.cancelPendingVerb())
    expect(result.current.pendingVerb).toBeNull()
    expect(onChange).not.toHaveBeenCalled()
  })

  it("switch from default content does NOT show pendingVerb (direct wipe)", () => {
    const onChange = vi.fn()
    const action: ActionRef = makeDefaultAction("navigate")
    const { result } = renderHook(() =>
      useActionPicker({ value: action, onChange }),
    )
    act(() => result.current.selectVerb("open_focus"))
    expect(result.current.pendingVerb).toBeNull()
    expect(onChange).toHaveBeenCalled()
    expect(onChange.mock.calls[0][0].action_kind).toBe("open_focus")
  })
})
