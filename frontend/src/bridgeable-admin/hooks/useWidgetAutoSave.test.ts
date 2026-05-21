/**
 * Tests for useWidgetAutoSave (WB-4a).
 */
import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"

// We mock the service so the hook tests stay synchronous + isolated.
vi.mock("@/bridgeable-admin/services/widget-builder-service", () => ({
  widgetBuilderService: {
    saveDraft: vi.fn(),
  },
}))

import { widgetBuilderService } from "@/bridgeable-admin/services/widget-builder-service"
import { useWidgetAutoSave } from "./useWidgetAutoSave"


function mkBlob(label = "a"): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: `root-${label}`,
    atom_tree: {
      [`root-${label}`]: {
        atom_id: `root-${label}`,
        atom_type: "conditional_container",
        config: { direction: "column", gap_token: "sm" },
        children: [],
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


function mkRecord(blob: CompositionBlob) {
  return {
    widget_id: "test-widget",
    title: "Test",
    description: null,
    icon: null,
    category: null,
    composition_blob: blob,
    composition_version: 1,
    published_composition_blob: null,
    tier_scope: "vertical" as const,
    supported_surfaces: ["dashboard_grid"],
    default_size: "1x1",
    supported_sizes: ["1x1"],
    last_edit_session_id: null,
    last_edit_session_at: null,
  }
}


describe("useWidgetAutoSave", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(widgetBuilderService.saveDraft).mockReset()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it("initial status is idle; draft seeded from server snapshot", () => {
    const blob = mkBlob("init")
    const { result } = renderHook(() =>
      useWidgetAutoSave({
        slug: "test-widget",
        lastServerSnapshot: blob,
        onSaved: () => {},
      }),
    )
    expect(result.current.status).toBe("idle")
    expect(result.current.draft).toBe(blob)
  })

  it("setDraft transitions to dirty then debounces to saved", async () => {
    const onSaved = vi.fn()
    const blob = mkBlob("a")
    const blob2 = mkBlob("b")
    vi.mocked(widgetBuilderService.saveDraft).mockResolvedValueOnce(
      mkRecord(blob2),
    )

    const { result } = renderHook(() =>
      useWidgetAutoSave({
        slug: "test-widget",
        lastServerSnapshot: blob,
        onSaved,
      }),
    )

    act(() => {
      result.current.setDraft(blob2)
    })
    expect(result.current.status).toBe("dirty")
    expect(result.current.draft).toBe(blob2)

    // Advance past debounce.
    await act(async () => {
      vi.advanceTimersByTime(250)
    })

    await waitFor(() => {
      expect(widgetBuilderService.saveDraft).toHaveBeenCalledTimes(1)
    })
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it("rapid edits coalesce into a single save (debounce)", async () => {
    const blob = mkBlob("a")
    vi.mocked(widgetBuilderService.saveDraft).mockResolvedValue(
      mkRecord(blob),
    )
    const { result } = renderHook(() =>
      useWidgetAutoSave({
        slug: "test-widget",
        lastServerSnapshot: blob,
        onSaved: () => {},
      }),
    )

    act(() => {
      result.current.setDraft(mkBlob("1"))
    })
    act(() => {
      result.current.setDraft(mkBlob("2"))
    })
    act(() => {
      result.current.setDraft(mkBlob("3"))
    })
    // Only the last edit's timer is active.
    await act(async () => {
      vi.advanceTimersByTime(250)
    })
    await waitFor(() => {
      expect(widgetBuilderService.saveDraft).toHaveBeenCalledTimes(1)
    })
  })

  it("network failure surfaces error status without losing draft", async () => {
    const blob = mkBlob("a")
    vi.mocked(widgetBuilderService.saveDraft).mockRejectedValueOnce(
      new Error("boom"),
    )
    const { result } = renderHook(() =>
      useWidgetAutoSave({
        slug: "test-widget",
        lastServerSnapshot: blob,
        onSaved: () => {},
      }),
    )

    const updated = mkBlob("b")
    act(() => {
      result.current.setDraft(updated)
    })
    await act(async () => {
      vi.advanceTimersByTime(250)
    })
    await waitFor(() => {
      expect(result.current.status).toBe("error")
    })
    // Draft preserved.
    expect(result.current.draft).toBe(updated)
    expect(result.current.error).toBe("boom")
  })

  it("flush bypasses the debounce", async () => {
    const blob = mkBlob("a")
    vi.mocked(widgetBuilderService.saveDraft).mockResolvedValueOnce(
      mkRecord(blob),
    )
    const { result } = renderHook(() =>
      useWidgetAutoSave({
        slug: "test-widget",
        lastServerSnapshot: blob,
        onSaved: () => {},
      }),
    )
    act(() => {
      result.current.setDraft(mkBlob("b"))
    })
    // No timer advance; flush directly.
    await act(async () => {
      await result.current.flush()
    })
    expect(widgetBuilderService.saveDraft).toHaveBeenCalledTimes(1)
  })

  it("regenerates editSessionId when slug changes", () => {
    const blob = mkBlob("a")
    const { result, rerender } = renderHook(
      (props: { slug: string | null }) =>
        useWidgetAutoSave({
          slug: props.slug,
          lastServerSnapshot: blob,
          onSaved: () => {},
        }),
      { initialProps: { slug: "widget-1" } },
    )
    const first = result.current.editSessionId
    rerender({ slug: "widget-2" })
    expect(result.current.editSessionId).not.toBe(first)
  })
})
