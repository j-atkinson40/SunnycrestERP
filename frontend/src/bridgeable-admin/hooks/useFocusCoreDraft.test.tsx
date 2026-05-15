/**
 * useFocusCoreDraft tests — sub-arc C-2.1.
 *
 * Uses real timers + waitFor for stable async semantics. Vitest's
 * fake-timer + promise-microtask interaction was brittle here.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, renderHook, waitFor } from "@testing-library/react"

vi.mock("@/bridgeable-admin/services/focus-cores-service", () => ({
  focusCoresService: {
    get: vi.fn(),
    update: vi.fn(),
    list: vi.fn(),
    create: vi.fn(),
  },
}))

import { focusCoresService } from "@/bridgeable-admin/services/focus-cores-service"
import { useFocusCoreDraft } from "./useFocusCoreDraft"

const SAMPLE_CORE = {
  id: "core-001",
  core_slug: "test-core",
  display_name: "Test Core",
  description: null,
  registered_component_kind: "focus-template",
  registered_component_name: "TestCore",
  default_starting_column: 0,
  default_column_span: 12,
  default_row_index: 0,
  min_column_span: 6,
  max_column_span: 12,
  canvas_config: {},
  chrome: { preset: "card", elevation: 50 },
  version: 1,
  is_active: true,
  created_at: "2026-05-15T00:00:00Z",
  updated_at: "2026-05-15T00:00:00Z",
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe("useFocusCoreDraft", () => {
  it("starts empty when coreId is null", () => {
    const { result } = renderHook(() => useFocusCoreDraft(null))
    expect(result.current.core).toBeNull()
    expect(result.current.draft).toEqual({})
    expect(result.current.isDirty).toBe(false)
    expect(result.current.isLoading).toBe(false)
  })

  it("loads core on mount when coreId provided", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.core?.id).toBe("core-001")
    expect(result.current.draft).toEqual({ preset: "card", elevation: 50 })
    expect(result.current.isDirty).toBe(false)
  })

  it("surfaces load error when fetch fails", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("network"),
    )
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => {
      expect(result.current.error).toBe("network")
    })
  })

  it("updateDraft marks dirty", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateDraft({ elevation: 75 })
    })
    expect(result.current.draft).toEqual({ preset: "card", elevation: 75 })
    expect(result.current.isDirty).toBe(true)
  })

  it("auto-saves after debounce", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    ;(focusCoresService.update as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      chrome: { preset: "card", elevation: 75 },
    })
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateDraft({ elevation: 75 })
    })
    await waitFor(
      () => {
        expect(focusCoresService.update).toHaveBeenCalled()
      },
      { timeout: 2000 },
    )
  })

  it("multiple rapid updates coalesce into single save", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    ;(focusCoresService.update as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...SAMPLE_CORE,
      chrome: { preset: "card", elevation: 75 },
    })
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateDraft({ elevation: 70 })
    })
    act(() => {
      result.current.updateDraft({ elevation: 72 })
    })
    act(() => {
      result.current.updateDraft({ elevation: 75 })
    })
    await waitFor(
      () => {
        expect(focusCoresService.update).toHaveBeenCalled()
      },
      { timeout: 2000 },
    )
    // Only one save should fire (final value).
    expect(
      (focusCoresService.update as ReturnType<typeof vi.fn>).mock.calls.length,
    ).toBe(1)
  })

  it("discard reverts draft to last-saved snapshot", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateDraft({ elevation: 99 })
    })
    expect(result.current.isDirty).toBe(true)
    act(() => {
      result.current.discard()
    })
    expect(result.current.draft).toEqual({ preset: "card", elevation: 50 })
    expect(result.current.isDirty).toBe(false)
  })

  it("save() commits immediately", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    ;(focusCoresService.update as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      chrome: { preset: "card", elevation: 60 },
    })
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateDraft({ elevation: 60 })
    })
    await act(async () => {
      await result.current.save()
    })
    expect(focusCoresService.update).toHaveBeenCalled()
  })

  it("clears state when coreId becomes null", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useFocusCoreDraft(id),
      { initialProps: { id: "core-001" as string | null } },
    )
    await waitFor(() => expect(result.current.core?.id).toBe("core-001"))
    rerender({ id: null })
    expect(result.current.core).toBeNull()
    expect(result.current.draft).toEqual({})
  })
})
