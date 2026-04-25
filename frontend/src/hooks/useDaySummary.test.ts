/**
 * useDaySummary — Phase B Session 4.4.3 cache + lifecycle tests.
 *
 * Focus: the module-scoped TTL cache behavior. Component-level
 * rendering of the summary is exercised in DateBox.test.tsx.
 */

import { renderHook, waitFor } from "@testing-library/react"
import { act } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/services/dispatch-service", () => ({
  fetchDaySummary: vi.fn(),
}))

import { fetchDaySummary } from "@/services/dispatch-service"
import { useDaySummary, _resetDaySummaryCache } from "./useDaySummary"


describe("useDaySummary", () => {
  beforeEach(() => {
    vi.mocked(fetchDaySummary).mockResolvedValue({
      date: "2026-04-25",
      total_deliveries: 3,
      unassigned_count: 1,
      finalize_status: "draft",
      finalized_at: null,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    _resetDaySummaryCache()
  })

  it("fires fetchDaySummary on mount with the given date", async () => {
    renderHook(() => useDaySummary("2026-04-25"))
    await waitFor(() => {
      expect(fetchDaySummary).toHaveBeenCalledWith("2026-04-25")
    })
  })

  it("returns the resolved summary after fetch completes", async () => {
    const { result } = renderHook(() => useDaySummary("2026-04-25"))
    await waitFor(() => {
      expect(result.current.summary).not.toBeNull()
    })
    expect(result.current.summary?.total_deliveries).toBe(3)
    expect(result.current.summary?.unassigned_count).toBe(1)
    expect(result.current.loading).toBe(false)
  })

  it("returns null + does not fetch when date is null", async () => {
    const { result } = renderHook(() => useDaySummary(null))
    expect(result.current.summary).toBeNull()
    expect(result.current.loading).toBe(false)
    // No fetch fired.
    expect(fetchDaySummary).not.toHaveBeenCalled()
  })

  it("serves a second hook instance from cache (no second fetch)", async () => {
    // First hook — fires the fetch.
    const { result: first, unmount: unmountFirst } = renderHook(() =>
      useDaySummary("2026-04-25"),
    )
    await waitFor(() => {
      expect(first.current.summary).not.toBeNull()
    })
    expect(fetchDaySummary).toHaveBeenCalledTimes(1)
    unmountFirst()

    // Second hook for the same date — should resolve synchronously
    // from cache, no additional fetch.
    const { result: second } = renderHook(() => useDaySummary("2026-04-25"))
    expect(second.current.summary?.total_deliveries).toBe(3)
    expect(fetchDaySummary).toHaveBeenCalledTimes(1)
  })

  it("reload() invalidates cache and refetches", async () => {
    const { result } = renderHook(() => useDaySummary("2026-04-25"))
    await waitFor(() => {
      expect(result.current.summary).not.toBeNull()
    })
    expect(fetchDaySummary).toHaveBeenCalledTimes(1)

    // Reprogram mock with new counts.
    vi.mocked(fetchDaySummary).mockResolvedValue({
      date: "2026-04-25",
      total_deliveries: 5,
      unassigned_count: 0,
      finalize_status: "finalized",
      finalized_at: "2026-04-24T13:00:00Z",
    })

    act(() => {
      result.current.reload()
    })

    await waitFor(() => {
      expect(result.current.summary?.total_deliveries).toBe(5)
    })
    expect(fetchDaySummary).toHaveBeenCalledTimes(2)
  })

  it("handles fetch errors gracefully without crashing", async () => {
    vi.mocked(fetchDaySummary).mockRejectedValue(new Error("server error"))
    const { result } = renderHook(() => useDaySummary("2026-04-25"))
    await waitFor(() => {
      expect(result.current.error).not.toBeNull()
    })
    expect(result.current.summary).toBeNull()
    expect(result.current.loading).toBe(false)
  })

  it("date-change triggers a new fetch", async () => {
    const { result, rerender } = renderHook(
      ({ d }: { d: string | null }) => useDaySummary(d),
      { initialProps: { d: "2026-04-25" } },
    )
    await waitFor(() => {
      expect(result.current.summary).not.toBeNull()
    })
    expect(fetchDaySummary).toHaveBeenCalledWith("2026-04-25")

    rerender({ d: "2026-04-26" })
    await waitFor(() => {
      expect(fetchDaySummary).toHaveBeenCalledWith("2026-04-26")
    })
  })
})
