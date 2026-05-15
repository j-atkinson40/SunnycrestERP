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

  // ─── Sub-arc C-2.1.1: session-aware update semantics ────────────

  it("generates a session token when coreId becomes real", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.editSessionId).toBeTruthy()
    expect(typeof result.current.editSessionId).toBe("string")
    // Looks like a UUID v4-ish (hyphenated, 36 chars).
    expect(result.current.editSessionId!.length).toBe(36)
  })

  it("preserves session token across re-renders with same coreId", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    const { result, rerender } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    const firstToken = result.current.editSessionId
    rerender()
    expect(result.current.editSessionId).toBe(firstToken)
  })

  it("generates a fresh session token when coreId switches", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      id: "core-002",
    })
    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useFocusCoreDraft(id),
      { initialProps: { id: "core-001" } },
    )
    await waitFor(() => expect(result.current.core?.id).toBe("core-001"))
    const tokenA = result.current.editSessionId
    rerender({ id: "core-002" })
    await waitFor(() => expect(result.current.core?.id).toBe("core-002"))
    const tokenB = result.current.editSessionId
    expect(tokenB).toBeTruthy()
    expect(tokenB).not.toBe(tokenA)
  })

  it("clears session token when coreId becomes null", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useFocusCoreDraft(id),
      { initialProps: { id: "core-001" as string | null } },
    )
    await waitFor(() => expect(result.current.editSessionId).toBeTruthy())
    rerender({ id: null })
    expect(result.current.editSessionId).toBeNull()
  })

  it("save includes edit_session_id in PUT payload", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    ;(focusCoresService.update as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      chrome: { preset: "card", elevation: 80 },
    })
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    const sessionToken = result.current.editSessionId
    act(() => {
      result.current.updateDraft({ elevation: 80 })
    })
    await act(async () => {
      await result.current.save()
    })
    expect(focusCoresService.update).toHaveBeenCalledWith(
      "core-001",
      expect.objectContaining({
        edit_session_id: sessionToken,
        chrome: expect.objectContaining({ elevation: 80 }),
      }),
    )
  })

  // ─── Sub-arc C-2.1.2: dirty-state-clear regression ─────────────
  //
  // Pre-fix the hook used `JSON.stringify(a) !== JSON.stringify(b)`
  // for the dirty check. JSONB round-trips through PostgreSQL do
  // NOT preserve object-key order — the backend can legitimately
  // return chrome with the same values in a different key sequence,
  // and the JSON.stringify equality check would consider that
  // "dirty" forever, breaking "Auto-saved Xs ago" + the Unsaved
  // indicator.
  //
  // The fix is `deepEqualChrome` — recursive key-order-insensitive
  // equality. These tests pin the contract.

  it("clears isDirty after successful save even when response key order differs", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    // Mock the backend returning the same chrome values in a
    // different key order — simulates JSONB round-trip behavior.
    ;(focusCoresService.update as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      // Note: keys reversed from { preset: "card", elevation: 75 }
      chrome: { elevation: 75, preset: "card" },
    })
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateDraft({ elevation: 75 })
    })
    expect(result.current.isDirty).toBe(true)
    await act(async () => {
      await result.current.save()
    })
    // Regression assertion: dirty must clear despite key-order
    // mismatch between draft + savedSnapshot.
    expect(result.current.isDirty).toBe(false)
    expect(result.current.lastSavedAt).not.toBeNull()
  })

  it("becomes dirty again after further updates following a save", async () => {
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
    await act(async () => {
      await result.current.save()
    })
    expect(result.current.isDirty).toBe(false)
    // Now make another change — must register as dirty.
    act(() => {
      result.current.updateDraft({ elevation: 80 })
    })
    expect(result.current.isDirty).toBe(true)
  })

  // ─── Sub-arc C-2.1.3: real dirty-state regression ──────────────
  //
  // C-2.1.2's deepEqualChrome was key-order-tolerant but key-set-
  // strict. Production response from `_core_to_response` was
  // stripping null/unset chrome fields, so the response carried
  // fewer keys than the draft. C-2.1.2's check returned !equal
  // forever, isDirty stuck at true, "Unsaved" indicator never
  // cleared after save.
  //
  // C-2.1.3 fix: (a) backend response normalized to full canonical
  // shape with explicit nulls, (b) frontend deepEqualChrome treats
  // missing-key and explicit-null-value as equivalent (defensive).
  //
  // This test reproduces the production bug: mock response has
  // FEWER keys than draft. Pre-C-2.1.3 it would FAIL. Post-C-2.1.3
  // it passes.

  it("clears isDirty after save when response chrome has fewer keys than draft (C-2.1.3)", async () => {
    // Mock GET returns sparse chrome (matches pre-C-2.1.3 backend
    // shape: only the non-null fields).
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      chrome: {
        preset: "card",
        elevation: 30,
        corner_radius: 10,
        backdrop_blur: 0,
        // background_token, border_token, padding_token absent
      },
    })
    // Mock PUT returns the same sparse shape (after bumping elevation).
    ;(focusCoresService.update as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      chrome: {
        preset: "card",
        elevation: 50,
        corner_radius: 10,
        backdrop_blur: 0,
      },
    })

    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    // User interacts with sliders — populates the full 7-field shape
    // because every slider has an onChange that writes its own key.
    // This is the production-reality draft: 7 keys, some null.
    act(() => {
      result.current.updateDraft({
        elevation: 50,
        background_token: null,
        border_token: null,
        padding_token: null,
      })
    })
    expect(result.current.isDirty).toBe(true)

    await act(async () => {
      await result.current.save()
    })

    // CRITICAL: dirty must clear even though response carries only
    // 4 keys while draft has 7 (3 explicit nulls). Pre-C-2.1.3 fix
    // this assertion FAILS.
    expect(result.current.isDirty).toBe(false)
    expect(result.current.lastSavedAt).not.toBeNull()
  })

  it("treats missing key and explicit null as equivalent for dirty check", async () => {
    // Set up a saved snapshot with one explicit-null field, then
    // mark dirty by ALSO setting that same field to null in the draft
    // (no semantic change). Should NOT be dirty.
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      chrome: { preset: "card", elevation: 50 }, // 2 keys
    })
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isDirty).toBe(false)

    // Add a null-valued key — no semantic change.
    act(() => {
      result.current.updateDraft({ background_token: null })
    })
    expect(result.current.isDirty).toBe(false)
  })

  it("normalized full-shape response (post-backend-fix) also clears dirty", async () => {
    // Backend post-C-2.1.3 returns full canonical shape with explicit
    // nulls. Frontend draft already has full shape. Equal sets, equal
    // values → not dirty after save.
    const FULL_CHROME = {
      preset: "card",
      elevation: 50,
      corner_radius: null,
      backdrop_blur: null,
      background_token: null,
      border_token: null,
      padding_token: null,
    }
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      chrome: { preset: "card", elevation: 30, corner_radius: null,
                backdrop_blur: null, background_token: null,
                border_token: null, padding_token: null },
    })
    ;(focusCoresService.update as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...SAMPLE_CORE,
      chrome: FULL_CHROME,
    })
    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateDraft({ elevation: 50 })
    })
    expect(result.current.isDirty).toBe(true)
    await act(async () => {
      await result.current.save()
    })
    expect(result.current.isDirty).toBe(false)
  })

  it("on 410 Gone, swaps to active_core_id and retries", async () => {
    ;(focusCoresService.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      SAMPLE_CORE,
    )
    const staleError = Object.assign(new Error("Gone"), {
      response: {
        status: 410,
        data: {
          detail: {
            message: "stale",
            inactive_core_id: "core-001",
            active_core_id: "core-001-v2",
            slug: "test-core",
          },
        },
      },
    })
    ;(focusCoresService.update as ReturnType<typeof vi.fn>)
      .mockRejectedValueOnce(staleError)
      .mockResolvedValueOnce({
        ...SAMPLE_CORE,
        id: "core-001-v2",
        chrome: { preset: "card", elevation: 90 },
      })

    const { result } = renderHook(() => useFocusCoreDraft("core-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateDraft({ elevation: 90 })
    })
    await act(async () => {
      await result.current.save()
    })
    // Two update calls: first with stale id, retry with active id.
    const calls = (focusCoresService.update as ReturnType<typeof vi.fn>).mock
      .calls
    expect(calls.length).toBe(2)
    expect(calls[0][0]).toBe("core-001")
    expect(calls[1][0]).toBe("core-001-v2")
    // Both calls carried the same session token.
    expect(calls[0][1].edit_session_id).toBe(calls[1][1].edit_session_id)
    // Final core state reflects the swapped id.
    expect(result.current.core?.id).toBe("core-001-v2")
    expect(result.current.error).toBeNull()
  })
})
