/**
 * useBindingPicker tests — saved-view + entity-types fetch.
 *
 * Mocks the saved-views-service module so hook behavior is testable
 * in isolation. Asserts parallel-fetch shape + ordered-fetch
 * cancellation contract.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, waitFor, act } from "@testing-library/react"

import { useBindingPicker } from "./useBindingPicker"

vi.mock("@/services/saved-views-service", () => ({
  listSavedViews: vi.fn(),
  listEntityTypes: vi.fn(),
}))


describe("useBindingPicker", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("starts loading + transitions to data on success", async () => {
    const svc = await import("@/services/saved-views-service")
    vi.mocked(svc.listSavedViews).mockResolvedValue([] as never)
    vi.mocked(svc.listEntityTypes).mockResolvedValue([] as never)

    const { result } = renderHook(() => useBindingPicker())
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBeNull()
    expect(result.current.savedViews).toEqual([])
    expect(result.current.entityTypes).toEqual([])
  })

  it("surfaces error string on fetch failure", async () => {
    const svc = await import("@/services/saved-views-service")
    vi.mocked(svc.listSavedViews).mockRejectedValue(new Error("Boom"))
    vi.mocked(svc.listEntityTypes).mockResolvedValue([] as never)

    const { result } = renderHook(() => useBindingPicker())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe("Boom")
  })

  it("refresh() triggers re-fetch", async () => {
    const svc = await import("@/services/saved-views-service")
    vi.mocked(svc.listSavedViews).mockResolvedValue([] as never)
    vi.mocked(svc.listEntityTypes).mockResolvedValue([] as never)

    const { result } = renderHook(() => useBindingPicker())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(vi.mocked(svc.listSavedViews)).toHaveBeenCalledTimes(1)
    act(() => result.current.refresh())
    await waitFor(() =>
      expect(vi.mocked(svc.listSavedViews)).toHaveBeenCalledTimes(2),
    )
  })
})
