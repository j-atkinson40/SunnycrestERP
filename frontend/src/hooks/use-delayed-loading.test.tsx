/**
 * useDelayedLoading — §18.1 150ms-arm / 300ms-min-display (fake timers).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { act, renderHook } from "@testing-library/react"

import { useDelayedLoading } from "./use-delayed-loading"

describe("useDelayedLoading", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it("a sub-150ms operation NEVER shows loading UI", () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useDelayedLoading(loading),
      { initialProps: { loading: true } },
    )
    expect(result.current).toBe(false)
    act(() => vi.advanceTimersByTime(100)) // resolves before the 150ms arm
    rerender({ loading: false })
    act(() => vi.advanceTimersByTime(1000))
    expect(result.current).toBe(false) // never shown
  })

  it("arms at 150ms of continuous loading", () => {
    const { result } = renderHook(() => useDelayedLoading(true))
    expect(result.current).toBe(false)
    act(() => vi.advanceTimersByTime(149))
    expect(result.current).toBe(false)
    act(() => vi.advanceTimersByTime(1))
    expect(result.current).toBe(true)
  })

  it("once shown, holds at least 300ms even if loading ends immediately", () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useDelayedLoading(loading),
      { initialProps: { loading: true } },
    )
    act(() => vi.advanceTimersByTime(150))
    expect(result.current).toBe(true)
    // Loading ends 10ms after the skeleton appeared.
    act(() => vi.advanceTimersByTime(10))
    rerender({ loading: false })
    act(() => vi.advanceTimersByTime(289)) // 299ms total visible
    expect(result.current).toBe(true) // still held
    act(() => vi.advanceTimersByTime(1)) // 300ms total
    expect(result.current).toBe(false)
  })

  it("hides immediately when the minimum display already elapsed", () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useDelayedLoading(loading),
      { initialProps: { loading: true } },
    )
    act(() => vi.advanceTimersByTime(150))
    expect(result.current).toBe(true)
    act(() => vi.advanceTimersByTime(400)) // visible well past 300ms
    rerender({ loading: false })
    act(() => vi.advanceTimersByTime(0))
    expect(result.current).toBe(false)
  })
})
