/**
 * useReturnPillCountdown — vitest tests.
 *
 * Covers:
 * - Initial state is full duration when resetKey set.
 * - resetKey=null disables the countdown.
 * - Tick decrements remainingMs.
 * - Hover pauses; mouse-leave resumes.
 * - Tab visibility hidden pauses.
 * - Tab visibility restore re-arms to FULL duration.
 * - resetKey change re-arms.
 * - onExpire fires once at zero.
 */

import { renderHook, act } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useReturnPillCountdown } from "./useReturnPillCountdown"


describe("useReturnPillCountdown", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it("initial remainingMs equals totalMs when resetKey set", () => {
    const onExpire = vi.fn()
    const { result } = renderHook(() =>
      useReturnPillCountdown({
        onExpire,
        resetKey: "a",
        totalMs: 15_000,
      }),
    )
    expect(result.current.remainingMs).toBe(15_000)
    expect(result.current.totalMs).toBe(15_000)
    expect(result.current.isPaused).toBe(false)
  })

  it("tick decrements remainingMs in 100ms steps", () => {
    const onExpire = vi.fn()
    const { result } = renderHook(() =>
      useReturnPillCountdown({
        onExpire,
        resetKey: "a",
        totalMs: 1_000,
      }),
    )
    act(() => {
      vi.advanceTimersByTime(300)
    })
    // After 3 ticks (100ms each) — 1000 - 300 = 700.
    expect(result.current.remainingMs).toBe(700)
  })

  it("hover pauses the countdown; mouse-leave resumes", () => {
    const onExpire = vi.fn()
    const { result } = renderHook(() =>
      useReturnPillCountdown({
        onExpire,
        resetKey: "a",
        totalMs: 1_000,
      }),
    )
    act(() => {
      vi.advanceTimersByTime(200)
    })
    const beforePause = result.current.remainingMs
    act(() => {
      result.current.onHoverStart()
    })
    expect(result.current.isPaused).toBe(true)
    act(() => {
      vi.advanceTimersByTime(500)
    })
    // No change while paused.
    expect(result.current.remainingMs).toBe(beforePause)
    act(() => {
      result.current.onHoverEnd()
    })
    expect(result.current.isPaused).toBe(false)
    act(() => {
      vi.advanceTimersByTime(100)
    })
    // Resumes from paused value — 1 tick later.
    expect(result.current.remainingMs).toBe(beforePause - 100)
  })

  it("fires onExpire exactly once when countdown reaches zero", () => {
    const onExpire = vi.fn()
    renderHook(() =>
      useReturnPillCountdown({
        onExpire,
        resetKey: "a",
        totalMs: 500,
      }),
    )
    act(() => {
      vi.advanceTimersByTime(700)
    })
    expect(onExpire).toHaveBeenCalledTimes(1)
  })

  it("resetKey change re-arms to full duration", () => {
    const onExpire = vi.fn()
    const { result, rerender } = renderHook(
      ({ resetKey }: { resetKey: string }) =>
        useReturnPillCountdown({
          onExpire,
          resetKey,
          totalMs: 1_000,
        }),
      { initialProps: { resetKey: "a" } },
    )
    act(() => {
      vi.advanceTimersByTime(400)
    })
    expect(result.current.remainingMs).toBe(600)
    rerender({ resetKey: "b" })
    expect(result.current.remainingMs).toBe(1_000)
  })

  it("resetKey=null halts the countdown", () => {
    const onExpire = vi.fn()
    const { result, rerender } = renderHook(
      ({ resetKey }: { resetKey: string | null }) =>
        useReturnPillCountdown({
          onExpire,
          resetKey,
          totalMs: 1_000,
        }),
      { initialProps: { resetKey: "a" as string | null } },
    )
    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(result.current.remainingMs).toBe(800)
    rerender({ resetKey: null })
    // Tick loop halts immediately; remainingMs stays at current value.
    act(() => {
      vi.advanceTimersByTime(500)
    })
    expect(result.current.remainingMs).toBe(800)
    expect(onExpire).not.toHaveBeenCalled()
  })

  it("tab visibility hidden pauses; visibility return re-arms to full", () => {
    const onExpire = vi.fn()
    const { result } = renderHook(() =>
      useReturnPillCountdown({
        onExpire,
        resetKey: "a",
        totalMs: 1_000,
      }),
    )
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(result.current.remainingMs).toBe(700)

    // Simulate tab hidden.
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "hidden",
    })
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"))
    })
    expect(result.current.isPaused).toBe(true)

    // Countdown halts while hidden.
    act(() => {
      vi.advanceTimersByTime(2_000)
    })
    expect(result.current.remainingMs).toBe(700)

    // Simulate tab visible again — should RE-ARM to full (not resume).
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    })
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"))
    })
    expect(result.current.remainingMs).toBe(1_000)
    expect(result.current.isPaused).toBe(false)
  })
})
