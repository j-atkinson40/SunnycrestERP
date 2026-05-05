/**
 * useCanvasViewport tests — Phase A Session 3.8.2 canonical rAF-coalesced
 * resize discipline + canonical three-tier responsive cascade.
 *
 * **Canonical Phase A Session 3.8.2 rAF-coalesced canonical**: window.resize
 * event listener canonical at rAF-coalesced single setDims call per
 * animation frame. Canvas jank carry-forward verification — multiple
 * resize events within a single rAF should collapse to ONE setDims call.
 */

import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useCanvasViewport } from "./useCanvasViewport"


describe("useCanvasViewport — canonical viewport hook", () => {
  it("returns canonical initial dims from window.innerWidth/innerHeight", () => {
    const { result } = renderHook(() => useCanvasViewport())
    expect(result.current.width).toBe(window.innerWidth)
    expect(result.current.height).toBe(window.innerHeight)
  })

  it("returns canonical tier per Phase A canonical three-tier cascade", () => {
    const { result } = renderHook(() => useCanvasViewport())
    expect(["canvas", "stack", "icon"]).toContain(result.current.tier)
  })
})


describe("useCanvasViewport — canonical rAF-coalesced canonical resize discipline (Phase A 3.8.2)", () => {
  let rafCallbacks: FrameRequestCallback[] = []
  let originalRaf: typeof window.requestAnimationFrame
  let originalCancelRaf: typeof window.cancelAnimationFrame

  beforeEach(() => {
    rafCallbacks = []
    originalRaf = window.requestAnimationFrame
    originalCancelRaf = window.cancelAnimationFrame
    // Replace rAF with manual scheduling so test can drive frames.
    window.requestAnimationFrame = ((cb: FrameRequestCallback) => {
      rafCallbacks.push(cb)
      return rafCallbacks.length
    }) as typeof window.requestAnimationFrame
    window.cancelAnimationFrame = vi.fn() as typeof window.cancelAnimationFrame
  })

  afterEach(() => {
    window.requestAnimationFrame = originalRaf
    window.cancelAnimationFrame = originalCancelRaf
  })

  it("multiple resize events within single rAF collapse to ONE setDims call (canvas jank carry-forward)", () => {
    const { result } = renderHook(() => useCanvasViewport())
    const initialWidth = result.current.width

    // Fire 5 resize events synchronously — without rAF coalescing this
    // would trigger 5 re-renders. Per Phase A 3.8.2 canonical, all 5
    // collapse into a single rAF callback.
    act(() => {
      Object.defineProperty(window, "innerWidth", {
        value: 1000,
        configurable: true,
      })
      window.dispatchEvent(new Event("resize"))
      window.dispatchEvent(new Event("resize"))
      window.dispatchEvent(new Event("resize"))
      window.dispatchEvent(new Event("resize"))
      window.dispatchEvent(new Event("resize"))
    })
    // Only one rAF was queued (multiple resize events collapsed).
    expect(rafCallbacks.length).toBe(1)
    // Until rAF fires, hook still reports stale value (no re-render
    // yet). This canonical behavior: re-render matches browser paint
    // cadence, NOT event firing rate.
    expect(result.current.width).toBe(initialWidth)
    // Fire the canonical rAF callback.
    act(() => {
      rafCallbacks[0](performance.now())
    })
    expect(result.current.width).toBe(1000)
  })

  it("subsequent resize after rAF fires queues new rAF (canonical no permanent block)", () => {
    const { result } = renderHook(() => useCanvasViewport())

    act(() => {
      Object.defineProperty(window, "innerWidth", {
        value: 800,
        configurable: true,
      })
      window.dispatchEvent(new Event("resize"))
    })
    expect(rafCallbacks.length).toBe(1)
    act(() => {
      rafCallbacks[0](performance.now())
    })
    expect(result.current.width).toBe(800)

    // Second resize canonically queues new rAF.
    act(() => {
      Object.defineProperty(window, "innerWidth", {
        value: 1200,
        configurable: true,
      })
      window.dispatchEvent(new Event("resize"))
    })
    expect(rafCallbacks.length).toBe(2)
    act(() => {
      rafCallbacks[1](performance.now())
    })
    expect(result.current.width).toBe(1200)
  })
})
