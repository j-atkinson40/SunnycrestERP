/**
 * useBindingPreview tests — debounced executeSavedView + resolveBinding
 * composition.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"

import { useBindingPreview } from "./useBindingPreview"

vi.mock("@/services/saved-views-service", () => ({
  executeSavedView: vi.fn(),
}))


describe("useBindingPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("idle when no saved_view_id", () => {
    const { result } = renderHook(() =>
      useBindingPreview({
        savedViewId: null,
        fieldPath: "amount",
        iterationMode: "per_row",
      }),
    )
    expect(result.current.kind).toBe("idle")
  })

  it("idle when no field_path", () => {
    const { result } = renderHook(() =>
      useBindingPreview({
        savedViewId: "v1",
        fieldPath: null,
        iterationMode: "per_row",
      }),
    )
    expect(result.current.kind).toBe("idle")
  })

  it("resolves to a value for per_row mode with rows", async () => {
    const svc = await import("@/services/saved-views-service")
    vi.mocked(svc.executeSavedView).mockResolvedValue({
      total_count: 3,
      rows: [{ amount: 100 }, { amount: 200 }, { amount: 300 }],
      groups: null,
      aggregations: null,
      permission_mode: "full",
      masked_fields: [],
    })
    const { result } = renderHook(() =>
      useBindingPreview({
        savedViewId: "v1",
        fieldPath: "amount",
        iterationMode: "per_row",
        debounceMs: 0,
      }),
    )
    await waitFor(() => expect(result.current.kind).toBe("value"))
    if (result.current.kind === "value") {
      expect(result.current.preview).toBe("100")
      expect(result.current.description).toContain("3 total")
    }
  })

  it("renders empty when rows is empty", async () => {
    const svc = await import("@/services/saved-views-service")
    vi.mocked(svc.executeSavedView).mockResolvedValue({
      total_count: 0,
      rows: [],
      groups: null,
      aggregations: null,
      permission_mode: "full",
      masked_fields: [],
    })
    const { result } = renderHook(() =>
      useBindingPreview({
        savedViewId: "v1",
        fieldPath: "amount",
        iterationMode: "per_row",
        debounceMs: 0,
      }),
    )
    await waitFor(() => expect(result.current.kind).toBe("empty"))
  })

  it("resolves single_summary against aggregations", async () => {
    const svc = await import("@/services/saved-views-service")
    vi.mocked(svc.executeSavedView).mockResolvedValue({
      total_count: 5,
      rows: [],
      groups: null,
      aggregations: { value: 42 },
      permission_mode: "full",
      masked_fields: [],
    })
    const { result } = renderHook(() =>
      useBindingPreview({
        savedViewId: "v1",
        fieldPath: "value",
        iterationMode: "single_summary",
        debounceMs: 0,
      }),
    )
    await waitFor(() => expect(result.current.kind).toBe("value"))
    if (result.current.kind === "value") {
      expect(result.current.preview).toBe("42")
    }
  })

  it("surfaces error on fetch failure", async () => {
    const svc = await import("@/services/saved-views-service")
    vi.mocked(svc.executeSavedView).mockRejectedValue(new Error("403"))
    const { result } = renderHook(() =>
      useBindingPreview({
        savedViewId: "v1",
        fieldPath: "amount",
        iterationMode: "per_row",
        debounceMs: 0,
      }),
    )
    await waitFor(() => expect(result.current.kind).toBe("error"))
    if (result.current.kind === "error") {
      expect(result.current.message).toBe("403")
    }
  })
})
