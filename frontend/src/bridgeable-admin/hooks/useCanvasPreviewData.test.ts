/**
 * Tests for useCanvasPreviewData (WB-5).
 *
 * Pure-logic + behavioral coverage:
 *  1. extractSavedViewIds dedupes + skips literals.
 *  2. classifyError correctly classes 404 / 403 / network / generic.
 *  3. Per-saved-view fetchId discriminator prevents stale-response
 *     overwrite (the Lock 6a invariant). Covered via direct
 *     simulation against the public ResolverViewState shape.
 *
 * Behavioral tests use `debounceMs=0` to avoid real-timer waits
 * (they were a source of cross-file parallel-test flakiness — the
 * Tier2TemplatesEditor test asserts a sync expectation right after
 * a `waitFor`-resolved render, and any worker that pegs the CPU
 * during that window can push the assertion past the next animation
 * frame). The 0-debounce path exercises the exact same control flow
 * minus the timer wait.
 */
import { renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type {
  BindingRef,
  CompositionBlob,
} from "@/lib/widget-builder/types/composition-blob"
import type { SavedViewResult } from "@/types/saved-views"

import {
  CANVAS_PREVIEW_DEBOUNCE_MS,
  extractSavedViewIds,
  useCanvasPreviewData,
} from "./useCanvasPreviewData"


vi.mock("@/services/saved-views-service", () => ({
  executeSavedView: vi.fn(),
}))


import { executeSavedView } from "@/services/saved-views-service"
const executeSavedViewMock = executeSavedView as unknown as ReturnType<typeof vi.fn>


function makeBlob(catalog: Record<string, BindingRef>): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: {},
        children: [],
      },
    },
    variants: [],
    bindings_catalog: catalog,
  }
}


function fieldPathBinding(
  binding_id: string,
  saved_view_id: string,
  field_path = "value",
): BindingRef {
  return {
    binding_id,
    binding_type: "field_path",
    saved_view_id,
    field_path,
    iteration_mode: "single_record",
  }
}


function fakeResult(rowCount: number, marker = "row"): SavedViewResult {
  return {
    total_count: rowCount,
    rows: Array.from({ length: rowCount }, (_, i) => ({
      id: `${marker}-${i}`,
      value: `${marker}-${i}-value`,
    })),
    aggregations: { value: rowCount },
    permission_mode: "full",
    masked_fields: [],
  }
}


describe("extractSavedViewIds", () => {
  it("dedupes saved_view_ids across multiple field_path bindings", () => {
    const catalog: Record<string, BindingRef> = {
      a: fieldPathBinding("a", "view1", "field_a"),
      b: fieldPathBinding("b", "view1", "field_b"),
      c: fieldPathBinding("c", "view2", "field_c"),
    }
    const ids = extractSavedViewIds(catalog)
    expect(ids).toEqual(["view1", "view2"])
  })

  it("skips literal bindings", () => {
    const catalog: Record<string, BindingRef> = {
      lit: { binding_id: "lit", binding_type: "literal", literal_value: "hi" },
      fp: fieldPathBinding("fp", "view1"),
    }
    expect(extractSavedViewIds(catalog)).toEqual(["view1"])
  })

  it("returns [] for undefined / empty catalog", () => {
    expect(extractSavedViewIds(undefined)).toEqual([])
    expect(extractSavedViewIds({})).toEqual([])
  })

  it("debounce constant is 200ms per WB-5 lock", () => {
    expect(CANVAS_PREVIEW_DEBOUNCE_MS).toBe(200)
  })
})


function makeDeferred<T>(): {
  promise: Promise<T>
  resolve: (v: T) => void
  reject: (e: unknown) => void
} {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}


describe("useCanvasPreviewData (debounceMs=0)", () => {
  beforeEach(() => {
    executeSavedViewMock.mockReset()
  })

  it("returns success map for a single binding", async () => {
    const result = fakeResult(2)
    executeSavedViewMock.mockResolvedValueOnce(result)
    const blob = makeBlob({ b1: fieldPathBinding("b1", "viewA") })

    const { result: hook } = renderHook(() => useCanvasPreviewData(blob, 0))

    await waitFor(
      () => {
        expect(hook.current["viewA"]?.status).toBe("success")
      },
      { timeout: 1000 },
    )
    expect(hook.current["viewA"]?.data).toEqual(result)
    expect(executeSavedViewMock).toHaveBeenCalledTimes(1)
    expect(executeSavedViewMock).toHaveBeenCalledWith("viewA")
  })

  it("dedupes shared saved_view_id at the fetch level", async () => {
    executeSavedViewMock.mockResolvedValue(fakeResult(1))
    const blob = makeBlob({
      a: fieldPathBinding("a", "viewX", "field_a"),
      b: fieldPathBinding("b", "viewX", "field_b"),
      c: fieldPathBinding("c", "viewX", "field_c"),
    })
    const { result } = renderHook(() => useCanvasPreviewData(blob, 0))
    await waitFor(
      () => {
        expect(result.current["viewX"]?.status).toBe("success")
      },
      { timeout: 1000 },
    )
    expect(executeSavedViewMock).toHaveBeenCalledTimes(1)
  })

  it("classifies 404 as view_not_found (not network_class)", async () => {
    executeSavedViewMock.mockRejectedValueOnce({
      response: { status: 404, data: { detail: "missing" } },
      message: "Request failed",
    })
    const blob = makeBlob({ b: fieldPathBinding("b", "v404") })
    const { result } = renderHook(() => useCanvasPreviewData(blob, 0))
    await waitFor(
      () => {
        expect(result.current["v404"]?.status).toBe("error")
      },
      { timeout: 1000 },
    )
    expect(result.current["v404"]?.error?.code).toBe("view_not_found")
    expect(result.current["v404"]?.error?.network_class).toBe(false)
  })

  it("classifies 403 as permission_denied (not network_class)", async () => {
    executeSavedViewMock.mockRejectedValueOnce({
      response: { status: 403, data: { detail: "no access" } },
    })
    const blob = makeBlob({ b: fieldPathBinding("b", "v403") })
    const { result } = renderHook(() => useCanvasPreviewData(blob, 0))
    await waitFor(
      () => {
        expect(result.current["v403"]?.status).toBe("error")
      },
      { timeout: 1000 },
    )
    expect(result.current["v403"]?.error?.code).toBe("permission_denied")
    expect(result.current["v403"]?.error?.network_class).toBe(false)
  })

  it("classifies ERR_NETWORK as network_error (network_class=true)", async () => {
    executeSavedViewMock.mockRejectedValueOnce({
      code: "ERR_NETWORK",
      message: "Network Error",
    })
    const blob = makeBlob({ b: fieldPathBinding("b", "vNet") })
    const { result } = renderHook(() => useCanvasPreviewData(blob, 0))
    await waitFor(
      () => {
        expect(result.current["vNet"]?.status).toBe("error")
      },
      { timeout: 1000 },
    )
    expect(result.current["vNet"]?.error?.code).toBe("network_error")
    expect(result.current["vNet"]?.error?.network_class).toBe(true)
  })

  it("optimistic stale: prior success kept as `previous` during refresh", async () => {
    const firstResult = fakeResult(2, "first")
    executeSavedViewMock.mockResolvedValueOnce(firstResult)

    const blob1 = makeBlob({ b: fieldPathBinding("b", "vOpt") })
    const { result, rerender } = renderHook(
      ({ blob }) => useCanvasPreviewData(blob, 0),
      { initialProps: { blob: blob1 } },
    )
    await waitFor(
      () => {
        expect(result.current["vOpt"]?.status).toBe("success")
      },
      { timeout: 1000 },
    )

    const deferred = makeDeferred<SavedViewResult>()
    executeSavedViewMock.mockReturnValueOnce(deferred.promise)
    executeSavedViewMock.mockResolvedValueOnce(fakeResult(1, "other"))
    const blob2 = makeBlob({
      b: fieldPathBinding("b", "vOpt"),
      b2: fieldPathBinding("b2", "vOther"),
    })
    rerender({ blob: blob2 })

    await waitFor(
      () => {
        expect(result.current["vOpt"]?.status).toBe("loading")
      },
      { timeout: 1000 },
    )
    expect(result.current["vOpt"]?.previous).toEqual(firstResult)

    const secondResult = fakeResult(3, "second")
    deferred.resolve(secondResult)
    await waitFor(
      () => {
        expect(result.current["vOpt"]?.status).toBe("success")
      },
      { timeout: 1000 },
    )
    expect(result.current["vOpt"]?.data).toEqual(secondResult)
  })

  it("cancellation: later fetch supersedes earlier (fetchId)", async () => {
    const first = makeDeferred<SavedViewResult>()
    const second = makeDeferred<SavedViewResult>()
    executeSavedViewMock.mockReturnValueOnce(first.promise)
    executeSavedViewMock.mockReturnValueOnce(second.promise)
    executeSavedViewMock.mockResolvedValue(fakeResult(0, "noop"))

    const blob1 = makeBlob({ b: fieldPathBinding("b", "vRace") })
    const { result, rerender } = renderHook(
      ({ blob }) => useCanvasPreviewData(blob, 0),
      { initialProps: { blob: blob1 } },
    )
    await waitFor(
      () => {
        expect(result.current["vRace"]?.status).toBe("loading")
      },
      { timeout: 1000 },
    )

    const blob2 = makeBlob({
      b: fieldPathBinding("b", "vRace"),
      b2: fieldPathBinding("b2", "vSecondary"),
    })
    rerender({ blob: blob2 })
    await waitFor(
      () => {
        expect(executeSavedViewMock.mock.calls.length).toBeGreaterThanOrEqual(2)
      },
      { timeout: 1000 },
    )

    const secondResult = fakeResult(7, "second")
    const firstResult = fakeResult(1, "first")
    second.resolve(secondResult)
    await waitFor(
      () => {
        expect(result.current["vRace"]?.status).toBe("success")
      },
      { timeout: 1000 },
    )
    expect(result.current["vRace"]?.data).toEqual(secondResult)

    // Now resolve the OLDER (cancelled) — must NOT overwrite.
    first.resolve(firstResult)
    // Microtask-only flush — no real timer wait.
    await Promise.resolve()
    await Promise.resolve()
    expect(result.current["vRace"]?.data).toEqual(secondResult)
  })

  it("empty bindings catalog → no fetches fired", async () => {
    const blob = makeBlob({})
    renderHook(() => useCanvasPreviewData(blob, 0))
    // Microtask flush; nothing to wait on.
    await Promise.resolve()
    await Promise.resolve()
    expect(executeSavedViewMock).not.toHaveBeenCalled()
  })

  it("null blob → no fetches fired", async () => {
    renderHook(() => useCanvasPreviewData(null, 0))
    await Promise.resolve()
    await Promise.resolve()
    expect(executeSavedViewMock).not.toHaveBeenCalled()
  })
})
