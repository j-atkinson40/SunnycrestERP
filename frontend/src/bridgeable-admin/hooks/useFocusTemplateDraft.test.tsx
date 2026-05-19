/**
 * useFocusTemplateDraft tests — sub-arc C-2.2b.
 *
 * Mirrors useFocusCoreDraft.test.tsx with the three-blob shape
 * (chrome_overrides + substrate + typography). Critical regression
 * coverage:
 *
 *   - Stale-closure-in-debounced-save for EACH of the three blobs
 *     (the C-2.1.4 discipline applied to substrate + typography in
 *     addition to chrome_overrides).
 *   - Cross-blob: rapid updates across all three blobs reach the PUT
 *     body with the latest committed values.
 *   - 410 Gone retry path with the templates error shape.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, renderHook, waitFor } from "@testing-library/react"

vi.mock("@/bridgeable-admin/services/focus-templates-service", () => ({
  focusTemplatesService: {
    get: vi.fn(),
    update: vi.fn(),
    list: vi.fn(),
    create: vi.fn(),
    usage: vi.fn(),
  },
}))

import { focusTemplatesService } from "@/bridgeable-admin/services/focus-templates-service"
import { useFocusTemplateDraft } from "./useFocusTemplateDraft"

const SAMPLE_TEMPLATE = {
  id: "tpl-001",
  scope: "platform_default" as const,
  vertical: null,
  template_slug: "test-template",
  display_name: "Test Template",
  description: null,
  inherits_from_core_id: "core-001",
  inherits_from_core_version: 1,
  rows: [],
  canvas_config: {},
  chrome_overrides: { preset: "frosted" } as Record<string, unknown>,
  substrate: { preset: "morning-warm", intensity: 70 } as Record<
    string,
    unknown
  >,
  typography: { preset: "card-text" } as Record<string, unknown>,
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

describe("useFocusTemplateDraft — load / discard / basic dirty", () => {
  it("starts empty when templateId is null", () => {
    const { result } = renderHook(() => useFocusTemplateDraft(null))
    expect(result.current.template).toBeNull()
    expect(result.current.chromeOverridesDraft).toEqual({})
    expect(result.current.substrateDraft).toEqual({})
    expect(result.current.typographyDraft).toEqual({})
    expect(result.current.isDirty).toBe(false)
    expect(result.current.isLoading).toBe(false)
  })

  it("loads template on mount when templateId provided", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.template?.id).toBe("tpl-001")
    expect(result.current.chromeOverridesDraft).toEqual({ preset: "frosted" })
    expect(result.current.substrateDraft).toEqual({
      preset: "morning-warm",
      intensity: 70,
    })
    expect(result.current.typographyDraft).toEqual({ preset: "card-text" })
    expect(result.current.isDirty).toBe(false)
  })

  it("surfaces load error when fetch fails", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce(new Error("network"))
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.error).toBe("network"))
  })

  it("updateChromeOverrides marks dirty", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateChromeOverrides({ elevation: 75 })
    })
    expect(result.current.chromeOverridesDraft).toEqual({
      preset: "frosted",
      elevation: 75,
    })
    expect(result.current.isDirty).toBe(true)
  })

  it("updateSubstrate marks dirty", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateSubstrate({ intensity: 85 })
    })
    expect(result.current.substrateDraft).toEqual({
      preset: "morning-warm",
      intensity: 85,
    })
    expect(result.current.isDirty).toBe(true)
  })

  it("updateTypography marks dirty", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateTypography({ heading_weight: 700 })
    })
    expect(result.current.typographyDraft).toEqual({
      preset: "card-text",
      heading_weight: 700,
    })
    expect(result.current.isDirty).toBe(true)
  })

  it("discard reverts all three drafts to snapshots", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateChromeOverrides({ elevation: 99 })
      result.current.updateSubstrate({ intensity: 99 })
      result.current.updateTypography({ heading_weight: 900 })
    })
    expect(result.current.isDirty).toBe(true)
    act(() => {
      result.current.discard()
    })
    expect(result.current.chromeOverridesDraft).toEqual({ preset: "frosted" })
    expect(result.current.substrateDraft).toEqual({
      preset: "morning-warm",
      intensity: 70,
    })
    expect(result.current.typographyDraft).toEqual({ preset: "card-text" })
    expect(result.current.isDirty).toBe(false)
  })

  // ─── Sub-arc C-2.3: per-field reset methods ───────────────────

  it("resetChromeOverridesField removes the named field + marks dirty", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      chrome_overrides: { preset: "frosted", elevation: 80 },
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.chromeOverridesDraft).toEqual({
      preset: "frosted",
      elevation: 80,
    })
    expect(result.current.isDirty).toBe(false)
    act(() => {
      result.current.resetChromeOverridesField("elevation")
    })
    expect(result.current.chromeOverridesDraft).toEqual({ preset: "frosted" })
    expect(result.current.isDirty).toBe(true)
  })

  it("resetSubstrateField removes the named field + marks dirty", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.resetSubstrateField("intensity")
    })
    expect(result.current.substrateDraft).toEqual({ preset: "morning-warm" })
    expect(result.current.isDirty).toBe(true)
  })

  it("resetTypographyField removes the named field + marks dirty", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      typography: { preset: "card-text", heading_weight: 700 },
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.resetTypographyField("heading_weight")
    })
    expect(result.current.typographyDraft).toEqual({ preset: "card-text" })
    expect(result.current.isDirty).toBe(true)
  })

  it("reset methods are no-op when the named field is absent", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    const before = result.current.chromeOverridesDraft
    act(() => {
      // SAMPLE_TEMPLATE has no `elevation` in chrome_overrides.
      result.current.resetChromeOverridesField("elevation")
    })
    // Object identity preserved when no key was present — preserves
    // React reference equality + avoids triggering a save.
    expect(result.current.chromeOverridesDraft).toBe(before)
    expect(result.current.isDirty).toBe(false)
  })

  it("reset triggers debounced save with the field removed from payload", async () => {
    vi.useFakeTimers()
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      chrome_overrides: { preset: "frosted", elevation: 80 },
    })
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      chrome_overrides: { preset: "frosted" },
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await vi.waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.resetChromeOverridesField("elevation")
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })
    const updateCalls = (
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mock.calls
    expect(updateCalls.length).toBeGreaterThan(0)
    const payload = updateCalls[0][1]
    expect(payload.chrome_overrides).toEqual({ preset: "frosted" })
    expect("elevation" in payload.chrome_overrides).toBe(false)
    vi.useRealTimers()
  })

  it("clears state when templateId becomes null", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useFocusTemplateDraft(id),
      { initialProps: { id: "tpl-001" as string | null } },
    )
    await waitFor(() => expect(result.current.template?.id).toBe("tpl-001"))
    rerender({ id: null })
    expect(result.current.template).toBeNull()
    expect(result.current.chromeOverridesDraft).toEqual({})
    expect(result.current.substrateDraft).toEqual({})
    expect(result.current.typographyDraft).toEqual({})
  })
})

describe("useFocusTemplateDraft — auto-save + debounce", () => {
  it("auto-saves after debounce", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      substrate: { preset: "morning-warm", intensity: 85 },
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateSubstrate({ intensity: 85 })
    })
    await waitFor(
      () => expect(focusTemplatesService.update).toHaveBeenCalled(),
      { timeout: 2000 },
    )
  })

  it("multiple rapid updates coalesce into single save", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      ...SAMPLE_TEMPLATE,
      substrate: { preset: "morning-warm", intensity: 90 },
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateSubstrate({ intensity: 80 })
    })
    act(() => {
      result.current.updateSubstrate({ intensity: 85 })
    })
    act(() => {
      result.current.updateSubstrate({ intensity: 90 })
    })
    await waitFor(
      () => expect(focusTemplatesService.update).toHaveBeenCalled(),
      { timeout: 2000 },
    )
    expect(
      (focusTemplatesService.update as ReturnType<typeof vi.fn>).mock.calls
        .length,
    ).toBe(1)
  })
})

describe("useFocusTemplateDraft — stale-closure regression (C-2.1.4 discipline)", () => {
  /**
   * The CRITICAL regression test. Pre-fix, putting a draft state
   * variable in `save`'s useCallback deps recreates the callback every
   * keystroke. The debounced setTimeout registered in the LATEST
   * update closure captures a save fn that reads the snapshot AT
   * REGISTRATION TIME — but after subsequent updates, the React state
   * has moved on. When the timer fires, it executes a save that
   * persists a stale value. savedSnapshot diverges from draft, isDirty
   * sticks at true.
   *
   * This test must pass for EACH blob independently. We test substrate
   * here (the locked-spec test); the cross-blob test below verifies
   * the same for chrome_overrides + typography in concert.
   *
   * Test-fails-against-pre-fix verification: temporarily added
   * `substrateDraft` to save's useCallback deps in
   * useFocusTemplateDraft.ts, re-ran this suite, observed assertion
   * failure at `expect(payload.substrate.intensity).toBe(75)`
   * (received a stale value), then restored the ref-only deps.
   */
  it("save sends latest substrate value not stale closure value", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockImplementation(
      async (
        _id: string,
        body: {
          chrome_overrides?: Record<string, unknown>
          substrate?: Record<string, unknown>
          typography?: Record<string, unknown>
        },
      ) => ({
        ...SAMPLE_TEMPLATE,
        chrome_overrides: { ...SAMPLE_TEMPLATE.chrome_overrides, ...body.chrome_overrides },
        substrate: { ...SAMPLE_TEMPLATE.substrate, ...body.substrate },
        typography: { ...SAMPLE_TEMPLATE.typography, ...body.typography },
      }),
    )
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    act(() => {
      result.current.updateSubstrate({ intensity: 72 })
    })
    act(() => {
      result.current.updateSubstrate({ intensity: 73 })
    })
    act(() => {
      result.current.updateSubstrate({ intensity: 75 })
    })

    await waitFor(
      () => expect(focusTemplatesService.update).toHaveBeenCalled(),
      { timeout: 2000 },
    )

    const updateMock = focusTemplatesService.update as ReturnType<typeof vi.fn>
    expect(updateMock.mock.calls.length).toBe(1)
    const payload = updateMock.mock.calls[0][1] as {
      substrate: { intensity: number }
    }
    expect(payload.substrate.intensity).toBe(75)

    await waitFor(() => expect(result.current.isDirty).toBe(false))
  })

  it("save sends latest typography value not stale closure value", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockImplementation(
      async (
        _id: string,
        body: {
          chrome_overrides?: Record<string, unknown>
          substrate?: Record<string, unknown>
          typography?: Record<string, unknown>
        },
      ) => ({
        ...SAMPLE_TEMPLATE,
        chrome_overrides: { ...SAMPLE_TEMPLATE.chrome_overrides, ...body.chrome_overrides },
        substrate: { ...SAMPLE_TEMPLATE.substrate, ...body.substrate },
        typography: { ...SAMPLE_TEMPLATE.typography, ...body.typography },
      }),
    )
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    act(() => {
      result.current.updateTypography({ heading_weight: 500 })
    })
    act(() => {
      result.current.updateTypography({ heading_weight: 600 })
    })
    act(() => {
      result.current.updateTypography({ heading_weight: 700 })
    })

    await waitFor(
      () => expect(focusTemplatesService.update).toHaveBeenCalled(),
      { timeout: 2000 },
    )

    const updateMock = focusTemplatesService.update as ReturnType<typeof vi.fn>
    expect(updateMock.mock.calls.length).toBe(1)
    const payload = updateMock.mock.calls[0][1] as {
      typography: { heading_weight: number }
    }
    expect(payload.typography.heading_weight).toBe(700)

    await waitFor(() => expect(result.current.isDirty).toBe(false))
  })

  it("save sends latest values across all three blobs in concert", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockImplementation(
      async (
        _id: string,
        body: {
          chrome_overrides?: Record<string, unknown>
          substrate?: Record<string, unknown>
          typography?: Record<string, unknown>
        },
      ) => ({
        ...SAMPLE_TEMPLATE,
        chrome_overrides: { ...SAMPLE_TEMPLATE.chrome_overrides, ...body.chrome_overrides },
        substrate: { ...SAMPLE_TEMPLATE.substrate, ...body.substrate },
        typography: { ...SAMPLE_TEMPLATE.typography, ...body.typography },
      }),
    )
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    // Rapid updates across all three blobs.
    act(() => {
      result.current.updateChromeOverrides({ elevation: 40 })
      result.current.updateSubstrate({ intensity: 40 })
      result.current.updateTypography({ heading_weight: 400 })
    })
    act(() => {
      result.current.updateChromeOverrides({ elevation: 55 })
      result.current.updateSubstrate({ intensity: 55 })
      result.current.updateTypography({ heading_weight: 550 })
    })
    act(() => {
      result.current.updateChromeOverrides({ elevation: 88 })
      result.current.updateSubstrate({ intensity: 88 })
      result.current.updateTypography({ heading_weight: 800 })
    })

    await waitFor(
      () => expect(focusTemplatesService.update).toHaveBeenCalled(),
      { timeout: 2000 },
    )

    const updateMock = focusTemplatesService.update as ReturnType<typeof vi.fn>
    expect(updateMock.mock.calls.length).toBe(1)
    const payload = updateMock.mock.calls[0][1] as {
      chrome_overrides: { elevation: number }
      substrate: { intensity: number }
      typography: { heading_weight: number }
    }
    // All three latest values must reach the PUT body together.
    expect(payload.chrome_overrides.elevation).toBe(88)
    expect(payload.substrate.intensity).toBe(88)
    expect(payload.typography.heading_weight).toBe(800)

    await waitFor(() => expect(result.current.isDirty).toBe(false))
  })
})

describe("useFocusTemplateDraft — session token + PUT payload", () => {
  it("generates a session token when templateId becomes real", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.editSessionId).toBeTruthy()
    expect(result.current.editSessionId!.length).toBe(36)
  })

  it("preserves session token across re-renders with same templateId", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result, rerender } = renderHook(() =>
      useFocusTemplateDraft("tpl-001"),
    )
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    const firstToken = result.current.editSessionId
    rerender()
    expect(result.current.editSessionId).toBe(firstToken)
  })

  it("generates a fresh session token when templateId switches", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      id: "tpl-002",
    })
    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useFocusTemplateDraft(id),
      { initialProps: { id: "tpl-001" } },
    )
    await waitFor(() => expect(result.current.template?.id).toBe("tpl-001"))
    const tokenA = result.current.editSessionId
    rerender({ id: "tpl-002" })
    await waitFor(() => expect(result.current.template?.id).toBe("tpl-002"))
    const tokenB = result.current.editSessionId
    expect(tokenB).toBeTruthy()
    expect(tokenB).not.toBe(tokenA)
  })

  it("clears session token when templateId becomes null", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useFocusTemplateDraft(id),
      { initialProps: { id: "tpl-001" as string | null } },
    )
    await waitFor(() => expect(result.current.editSessionId).toBeTruthy())
    rerender({ id: null })
    expect(result.current.editSessionId).toBeNull()
  })

  it("save includes edit_session_id and all three blobs in PUT payload", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    const sessionToken = result.current.editSessionId
    act(() => {
      result.current.updateChromeOverrides({ elevation: 50 })
    })
    await act(async () => {
      await result.current.save()
    })
    expect(focusTemplatesService.update).toHaveBeenCalledWith(
      "tpl-001",
      expect.objectContaining({
        edit_session_id: sessionToken,
        chrome_overrides: expect.objectContaining({ elevation: 50 }),
        substrate: expect.any(Object),
        typography: expect.any(Object),
      }),
    )
  })
})

describe("useFocusTemplateDraft — 410 Gone retry", () => {
  it("on 410 Gone, swaps to active_template_id and retries", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const staleError = Object.assign(new Error("Gone"), {
      response: {
        status: 410,
        data: {
          detail: {
            message: "stale",
            inactive_template_id: "tpl-001",
            active_template_id: "tpl-001-v2",
            slug: "test-template",
            scope: "platform_default",
            vertical: null,
          },
        },
      },
    })
    ;(focusTemplatesService.update as ReturnType<typeof vi.fn>)
      .mockRejectedValueOnce(staleError)
      .mockResolvedValueOnce({
        ...SAMPLE_TEMPLATE,
        id: "tpl-001-v2",
        substrate: { preset: "morning-warm", intensity: 95 },
      })

    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.updateSubstrate({ intensity: 95 })
    })
    await act(async () => {
      await result.current.save()
    })
    const calls = (focusTemplatesService.update as ReturnType<typeof vi.fn>)
      .mock.calls
    expect(calls.length).toBe(2)
    expect(calls[0][0]).toBe("tpl-001")
    expect(calls[1][0]).toBe("tpl-001-v2")
    // Both calls carry the same session token.
    expect(calls[0][1].edit_session_id).toBe(calls[1][1].edit_session_id)
    expect(result.current.template?.id).toBe("tpl-001-v2")
    expect(result.current.error).toBeNull()
  })
})

describe("useFocusTemplateDraft — sparse response dirty clear (C-2.1.3 discipline)", () => {
  it("clears isDirty after save when response substrate has fewer keys than draft", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      substrate: { preset: "morning-warm", intensity: 60 }, // 2 keys
    })
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      substrate: { preset: "morning-warm", intensity: 80 }, // still 2 keys
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      // User scrubs intensity AND adds explicit nulls for token fields
      // (full canonical 5-field substrate shape).
      result.current.updateSubstrate({
        intensity: 80,
        base_token: null,
        accent_token_1: null,
        accent_token_2: null,
      })
    })
    expect(result.current.isDirty).toBe(true)
    await act(async () => {
      await result.current.save()
    })
    // Response had 2 keys; draft has 5. Sparse-vs-full equivalence
    // (missing-key == null) keeps isDirty in sync.
    expect(result.current.isDirty).toBe(false)
    expect(result.current.lastSavedAt).not.toBeNull()
  })
})

// ───────────────────────────────────────────────────────────────────
// F-3 — widget placement mutators (addWidget / updateWidget /
// removeWidget / moveWidget) + rows blob round-trip + 4th-blob dirty
// state + stale-closure regression for updateWidget.
// ───────────────────────────────────────────────────────────────────

describe("useFocusTemplateDraft — F-3 widget mutators", () => {
  it("rowsDraft starts empty for a template with no rows", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.rowsDraft).toEqual([])
    expect(result.current.isDirty).toBe(false)
  })

  // F-3.1a — load-side adapter contract. Backend stores canonical
  // shape (`placement_id` / `component_name` / `starting_column` /
  // `prop_overrides`). Hook must adapt back to frontend-typed view
  // for downstream consumers (FocusBuilderCanvas reads
  // `placement.id` + `widget_slug` + `column_start` + `chrome`).
  //
  // Verify-against-pre-fix: comment out the `backendToFrontendRows`
  // call in the hook's load path; this test fails with
  // `placements[0].id === undefined`, `widget_slug === undefined`,
  // `column_start === undefined`, `chrome === undefined`. Restored.
  it("F-3.1a — load adapts canonical backend shape to frontend view", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              placement_id: "w-canonical",
              component_kind: "widget",
              component_name: "day-strip-widget",
              starting_column: 4,
              column_span: 4,
              prop_overrides: { daysVisible: 7 },
            },
          ],
        },
      ],
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.rowsDraft).toHaveLength(1)
    const p = result.current.rowsDraft[0].placements[0]
    expect(p.id).toBe("w-canonical")
    expect(p.widget_slug).toBe("day-strip-widget")
    // starting_column=4 (0-indexed) → column_start=5 (1-indexed).
    expect(p.column_start).toBe(5)
    expect(p.column_span).toBe(4)
    expect(p.chrome).toEqual({ daysVisible: 7 })
    expect(result.current.isDirty).toBe(false)
  })

  it("rowsDraft loads existing rows from server response", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              id: "w-existing",
              widget_slug: "day-strip-widget",
              column_start: 1,
              column_span: 12,
              chrome: {},
            },
          ],
        },
      ],
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.rowsDraft).toHaveLength(1)
    expect(result.current.rowsDraft[0].placements[0].id).toBe("w-existing")
    expect(result.current.isDirty).toBe(false)
  })

  it("addWidget returns a UUID + appends a placement + marks dirty", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    let newId = ""
    act(() => {
      newId = result.current.addWidget("day-strip-widget")
    })
    expect(newId).toBeTruthy()
    expect(typeof newId).toBe("string")
    expect(result.current.rowsDraft).toHaveLength(1)
    expect(result.current.rowsDraft[0].placements[0].id).toBe(newId)
    expect(result.current.rowsDraft[0].placements[0].widget_slug).toBe(
      "day-strip-widget",
    )
    expect(result.current.isDirty).toBe(true)
  })

  it("updateWidget merges chrome + marks dirty", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    let newId = ""
    act(() => {
      newId = result.current.addWidget("day-strip-widget")
    })
    act(() => {
      result.current.updateWidget(newId, { daysVisible: 5 })
    })
    expect(result.current.rowsDraft[0].placements[0].chrome.daysVisible).toBe(5)
  })

  it("removeWidget removes by id + drops empty rows", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    let newId = ""
    act(() => {
      newId = result.current.addWidget("day-strip-widget")
    })
    act(() => {
      result.current.removeWidget(newId)
    })
    expect(result.current.rowsDraft).toEqual([])
  })

  it("moveWidget repositions across rows", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    let id = ""
    act(() => {
      id = result.current.addWidget("day-strip-widget")
    })
    act(() => {
      result.current.moveWidget(id, { rowIndex: 5, columnStart: 3, columnSpan: 6 })
    })
    const row = result.current.rowsDraft.find((r) => r.row_index === 5)
    expect(row).toBeDefined()
    expect(row?.placements[0].id).toBe(id)
    expect(row?.placements[0].column_start).toBe(3)
    expect(row?.placements[0].column_span).toBe(6)
  })

  it("save sends rows in PUT payload + clears dirty", async () => {
    vi.useFakeTimers()
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockImplementation(
      async (_id: string, body: { rows?: unknown }) => ({
        ...SAMPLE_TEMPLATE,
        rows: body.rows ?? [],
      }),
    )
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await vi.waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.addWidget("day-strip-widget")
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })
    const updateMock = focusTemplatesService.update as ReturnType<typeof vi.fn>
    expect(updateMock).toHaveBeenCalled()
    const payload = updateMock.mock.calls[0][1] as { rows?: unknown }
    expect(Array.isArray(payload.rows)).toBe(true)
    expect(payload.rows).toHaveLength(1)
    await vi.waitFor(() => expect(result.current.isDirty).toBe(false))
    vi.useRealTimers()
  })

  /**
   * Stale-closure regression test (C-2.2b discipline) — applies the
   * C-2.1.4 pattern to the rows blob via updateWidget. If
   * `rowsDraft` were added to save's useCallback deps OR save read
   * the rowsDraft closure variable instead of `rowsRef.current`, the
   * latest updateWidget value would NOT reach the PUT body.
   *
   * Test-fails-against-pre-fix verification: temporarily replaced
   * `rowsRef.current` with `rowsDraft` (closure read) in the save
   * payload assembly + added `rowsDraft` to the save deps; this test
   * fails with payload.rows[0].placements[0].chrome.elevation
   * receiving the FIRST updateWidget value (50), not the last (75).
   * Reverted; this test now asserts the canonical ref-only-read path.
   */
  it("save sends latest updateWidget chrome value not stale closure value", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    ;(
      focusTemplatesService.update as ReturnType<typeof vi.fn>
    ).mockImplementation(
      async (_id: string, body: { rows?: unknown }) => ({
        ...SAMPLE_TEMPLATE,
        rows: body.rows ?? [],
      }),
    )
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    let id = ""
    act(() => {
      id = result.current.addWidget("day-strip-widget")
    })
    act(() => {
      result.current.updateWidget(id, { elevation: 50 })
    })
    act(() => {
      result.current.updateWidget(id, { elevation: 60 })
    })
    act(() => {
      result.current.updateWidget(id, { elevation: 75 })
    })
    await waitFor(
      () => expect(focusTemplatesService.update).toHaveBeenCalled(),
      { timeout: 2000 },
    )
    const updateMock = focusTemplatesService.update as ReturnType<typeof vi.fn>
    expect(updateMock.mock.calls.length).toBe(1)
    // F-3.1a — payload is now backend canonical shape (post-adapter).
    // Frontend `chrome.elevation` maps to backend `prop_overrides.elevation`.
    const payload = updateMock.mock.calls[0][1] as {
      rows: Array<{
        placements: Array<{ prop_overrides?: { elevation: number } }>
      }>
    }
    expect(payload.rows[0].placements[0].prop_overrides?.elevation).toBe(75)
    await waitFor(() => expect(result.current.isDirty).toBe(false))
  })

  it("410-retry preserves rows draft state", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(SAMPLE_TEMPLATE)
    const staleError = Object.assign(new Error("Gone"), {
      response: {
        status: 410,
        data: {
          detail: {
            inactive_template_id: "tpl-001",
            active_template_id: "tpl-001-v2",
          },
        },
      },
    })
    ;(focusTemplatesService.update as ReturnType<typeof vi.fn>)
      .mockRejectedValueOnce(staleError)
      .mockImplementationOnce(async (_id: string, body: { rows?: unknown }) => ({
        ...SAMPLE_TEMPLATE,
        id: "tpl-001-v2",
        rows: body.rows ?? [],
      }))
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.addWidget("today-pin-widget")
    })
    await act(async () => {
      await result.current.save()
    })
    expect(focusTemplatesService.update).toHaveBeenCalledTimes(2)
    expect(result.current.template?.id).toBe("tpl-001-v2")
    expect(result.current.rowsDraft).toHaveLength(1)
    expect(result.current.isDirty).toBe(false)
  })

  it("discard restores rows snapshot", async () => {
    ;(
      focusTemplatesService.get as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      ...SAMPLE_TEMPLATE,
      rows: [
        {
          row_index: 0,
          column_count: 12,
          placements: [
            {
              id: "w-pristine",
              widget_slug: "day-strip-widget",
              column_start: 1,
              column_span: 12,
              chrome: {},
            },
          ],
        },
      ],
    })
    const { result } = renderHook(() => useFocusTemplateDraft("tpl-001"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => {
      result.current.addWidget("today-pin-widget")
    })
    expect(result.current.rowsDraft.flatMap((r) => r.placements)).toHaveLength(2)
    act(() => {
      result.current.discard()
    })
    expect(result.current.rowsDraft.flatMap((r) => r.placements)).toHaveLength(1)
    expect(result.current.rowsDraft[0].placements[0].id).toBe("w-pristine")
    expect(result.current.isDirty).toBe(false)
  })
})
