/**
 * FocusBuilderSelectionContext unit tests (sub-arc FF-7).
 *
 * Coverage of the multi-select transitions: add / remove / clear /
 * setMulti / isInSelection across single / multi / none cases.
 */
import { describe, expect, it } from "vitest"
import { act, renderHook } from "@testing-library/react"

import {
  FocusBuilderSelectionProvider,
  useFocusBuilderSelection,
} from "./FocusBuilderSelectionContext"

function wrap({ children }: { children: React.ReactNode }) {
  return <FocusBuilderSelectionProvider>{children}</FocusBuilderSelectionProvider>
}

describe("FocusBuilderSelectionContext (multi-select extensions)", () => {
  it("addToSelection promotes single → multi", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    act(() => result.current.setSelection({ kind: "widget", id: "a" }))
    act(() => result.current.addToSelection("b"))
    expect(result.current.selection.kind).toBe("widgets-multi")
    if (result.current.selection.kind === "widgets-multi") {
      expect(result.current.selection.ids).toEqual(["a", "b"])
    }
  })

  it("addToSelection on already-multi adds id", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    act(() => result.current.setMultiSelection(["a", "b"]))
    act(() => result.current.addToSelection("c"))
    if (result.current.selection.kind === "widgets-multi") {
      expect(result.current.selection.ids).toEqual(["a", "b", "c"])
    } else {
      expect.fail("expected multi-selection")
    }
  })

  it("addToSelection on same-id single is a no-op", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    act(() => result.current.setSelection({ kind: "widget", id: "a" }))
    act(() => result.current.addToSelection("a"))
    expect(result.current.selection.kind).toBe("widget")
    if (result.current.selection.kind === "widget") {
      expect(result.current.selection.id).toBe("a")
    }
  })

  it("removeFromSelection collapses multi-of-2 to single", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    act(() => result.current.setMultiSelection(["a", "b"]))
    act(() => result.current.removeFromSelection("a"))
    expect(result.current.selection.kind).toBe("widget")
    if (result.current.selection.kind === "widget") {
      expect(result.current.selection.id).toBe("b")
    }
  })

  it("removeFromSelection on single matches → none", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    act(() => result.current.setSelection({ kind: "widget", id: "a" }))
    act(() => result.current.removeFromSelection("a"))
    expect(result.current.selection.kind).toBe("none")
  })

  it("clearSelection resets to none", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    act(() => result.current.setMultiSelection(["a", "b", "c"]))
    act(() => result.current.clearSelection())
    expect(result.current.selection.kind).toBe("none")
  })

  it("setMultiSelection length 1 collapses to single", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    act(() => result.current.setMultiSelection(["only-one"]))
    expect(result.current.selection.kind).toBe("widget")
  })

  it("setMultiSelection length 0 collapses to none", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    act(() => result.current.setMultiSelection([]))
    expect(result.current.selection.kind).toBe("none")
  })

  it("isInSelection works across single + multi + none cases", () => {
    const { result } = renderHook(() => useFocusBuilderSelection(), { wrapper: wrap })
    expect(result.current.isInSelection("a")).toBe(false)
    act(() => result.current.setSelection({ kind: "widget", id: "a" }))
    expect(result.current.isInSelection("a")).toBe(true)
    expect(result.current.isInSelection("b")).toBe(false)
    act(() => result.current.setMultiSelection(["a", "b"]))
    expect(result.current.isInSelection("a")).toBe(true)
    expect(result.current.isInSelection("b")).toBe(true)
    expect(result.current.isInSelection("c")).toBe(false)
  })
})
