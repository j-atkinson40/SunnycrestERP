/**
 * useAIExtractionReview tests — canonical operator-initiated suggestion
 * request handling + canonical Confirm/Edit/Reject/Skip handlers +
 * canonical anti-pattern 1 guard at hook substrate.
 */

import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { useAIExtractionReview } from "./useAIExtractionReview"
import {
  PersonalizationCanvasStateProvider,
  usePersonalizationCanvasState,
} from "./canvas-state-context"
import { emptyCanvasState } from "@/types/personalization-studio"


// Mock canonical service module canonical at module substrate.
vi.mock("@/services/personalization-studio-service", () => ({
  suggestLayout: vi.fn().mockResolvedValue({
    line_items: [
      {
        line_item_key: "name_text_position",
        value: { x: 200, y: 150, width: 400, height: 60 },
        confidence: 0.92,
        rationale: "Centered upper-third placement",
        confidence_tier: "high",
      },
      {
        line_item_key: "emblem_position",
        value: { x: 350, y: 320, width: 100, height: 100 },
        confidence: 0.55,
        rationale: "Limited info",
        confidence_tier: "low",
      },
    ],
    execution_id: "exec-1",
    model_used: "claude-haiku-4-5-20250514",
    latency_ms: 350,
  }),
  suggestTextStyle: vi.fn().mockResolvedValue({
    line_items: [
      {
        line_item_key: "name_text_font",
        value: { font: "serif", size: 42, color: "#1A1715" },
        confidence: 0.88,
        rationale: "Family preference 'traditional' implies serif",
        confidence_tier: "high",
      },
    ],
    execution_id: "exec-2",
    model_used: "claude-haiku-4-5-20250514",
    latency_ms: 320,
  }),
  extractDecedentInfo: vi.fn().mockResolvedValue({
    line_items: [
      {
        line_item_key: "decedent_first_name",
        value: "John",
        confidence: 0.96,
        rationale: "Explicit text match",
        confidence_tier: "high",
      },
      {
        line_item_key: "birth_date",
        value: "1945-03-12",
        confidence: 0.90,
        rationale: "ISO date inferred",
        confidence_tier: "high",
      },
    ],
    execution_id: "exec-3",
    model_used: "claude-haiku-4-5-20250514",
    latency_ms: 1100,
  }),
}))


function makeWrapper() {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <PersonalizationCanvasStateProvider
        initialCanvasState={emptyCanvasState("burial_vault_personalization_studio")}
      >
        {children}
      </PersonalizationCanvasStateProvider>
    )
  }
}


describe("useAIExtractionReview — canonical operator-initiated request handling", () => {
  it("requestSuggestLayout canonically updates canonical state with canonical payload", async () => {
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper: makeWrapper(),
    })
    await act(async () => {
      await result.current.requestSuggestLayout()
    })
    expect(result.current.activeSuggestionType).toBe("suggest_layout")
    expect(result.current.payload).not.toBeNull()
    expect(result.current.payload?.line_items).toHaveLength(2)
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it("requestSuggestTextStyle canonically updates canonical state", async () => {
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper: makeWrapper(),
    })
    await act(async () => {
      await result.current.requestSuggestTextStyle({
        family_preferences: "traditional",
      })
    })
    expect(result.current.activeSuggestionType).toBe("suggest_text_style")
    expect(result.current.payload?.line_items[0].line_item_key).toBe(
      "name_text_font",
    )
  })

  it("requestExtractDecedentInfo canonically forwards canonical content_blocks", async () => {
    const service = await import(
      "@/services/personalization-studio-service"
    )
    vi.clearAllMocks()
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper: makeWrapper(),
    })
    const contentBlock = {
      type: "image" as const,
      source: {
        type: "base64" as const,
        media_type: "image/jpeg",
        data: "base64-data",
      },
    }
    await act(async () => {
      await result.current.requestExtractDecedentInfo({
        content_blocks: [contentBlock],
        context_summary: "Death certificate",
      })
    })
    expect(service.extractDecedentInfo).toHaveBeenCalledWith(
      "instance-1",
      expect.objectContaining({
        content_blocks: [contentBlock],
        context_summary: "Death certificate",
      }),
    )
  })

  it("canonical request canonical resets canonical decisions on canonical new suggestion", async () => {
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper: makeWrapper(),
    })
    await act(async () => {
      await result.current.requestSuggestLayout()
    })
    // Canonical record canonical decision.
    act(() => {
      result.current.skip(result.current.payload!.line_items[0])
    })
    expect(result.current.decisions).toHaveLength(1)
    // Canonical second canonical request canonical resets canonical decisions.
    await act(async () => {
      await result.current.requestSuggestTextStyle({})
    })
    expect(result.current.decisions).toHaveLength(0)
  })
})


describe("useAIExtractionReview — canonical Confirm action canonical applies to canvas state", () => {
  it("canonical Confirm canonical applies canonical layout suggestion canonical to canvas state per canonical Anti-pattern 1 discipline", async () => {
    type CanvasStateType = ReturnType<typeof emptyCanvasState>
    let capturedCanvasState: CanvasStateType | undefined = undefined as CanvasStateType | undefined
    const wrapper = ({ children }: { children: ReactNode }) => (
      <PersonalizationCanvasStateProvider
        initialCanvasState={emptyCanvasState("burial_vault_personalization_studio")}
      >
        <CanvasStateProbe
          onState={(s) => {
            capturedCanvasState = s
          }}
        />
        {children}
      </PersonalizationCanvasStateProvider>
    )
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper,
    })

    await act(async () => {
      await result.current.requestSuggestLayout()
    })

    // Canonical anti-pattern 1 guard: canvas state canonical EMPTY before
    // canonical Confirm action.
    expect(capturedCanvasState?.canvas_layout.elements).toHaveLength(0)

    // Canonical operator agency: explicit canonical Confirm action.
    act(() => {
      result.current.confirm(result.current.payload!.line_items[0])
    })

    // Canonical Confirm action canonical applied canonical line item.
    expect(capturedCanvasState?.canvas_layout.elements).toHaveLength(1)
    expect(capturedCanvasState?.canvas_layout.elements[0].element_type).toBe(
      "name_text",
    )
    expect(capturedCanvasState?.canvas_layout.elements[0].x).toBe(200)
    expect(capturedCanvasState?.canvas_layout.elements[0].y).toBe(150)
    expect(result.current.decisions).toHaveLength(1)
    expect(result.current.decisions[0].decision).toBe("confirm")
  })
})


describe("useAIExtractionReview — canonical anti-pattern 1 guard at hook substrate", () => {
  it("§3.26.11.12.16 Anti-pattern 1: canonical service-layer call canonical does NOT canonically auto-confirm", async () => {
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper: makeWrapper(),
    })
    await act(async () => {
      await result.current.requestSuggestLayout()
    })
    // Canonical anti-pattern 1 guard: canonical line items canonical
    // available canonical at canonical state; canonical decisions
    // canonical EMPTY (no canonical auto-confirm).
    expect(result.current.payload?.line_items).toHaveLength(2)
    expect(result.current.decisions).toHaveLength(0)
  })

  it("canonical Reject action canonical does NOT canonically apply canonical line item to canvas state", async () => {
    type CanvasStateType = ReturnType<typeof emptyCanvasState>
    let capturedCanvasState: CanvasStateType | undefined = undefined as CanvasStateType | undefined
    const wrapper = ({ children }: { children: ReactNode }) => (
      <PersonalizationCanvasStateProvider
        initialCanvasState={emptyCanvasState("burial_vault_personalization_studio")}
      >
        <CanvasStateProbe
          onState={(s) => {
            capturedCanvasState = s
          }}
        />
        {children}
      </PersonalizationCanvasStateProvider>
    )
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper,
    })
    await act(async () => {
      await result.current.requestSuggestLayout()
    })
    act(() => {
      result.current.reject(result.current.payload!.line_items[0])
    })
    // Canonical Reject action canonical does NOT canonically apply
    // canonical line item to canvas state.
    expect(capturedCanvasState?.canvas_layout.elements).toHaveLength(0)
    expect(result.current.decisions[0].decision).toBe("reject")
  })

  it("canonical Skip action canonical defers canonical line item review", async () => {
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper: makeWrapper(),
    })
    await act(async () => {
      await result.current.requestSuggestLayout()
    })
    act(() => {
      result.current.skip(result.current.payload!.line_items[0])
    })
    expect(result.current.decisions[0].decision).toBe("skip")
  })

  it("canonical Edit action canonical records canonical edit decision (without canvas mutation)", async () => {
    type CanvasStateType = ReturnType<typeof emptyCanvasState>
    let capturedCanvasState: CanvasStateType | undefined = undefined as CanvasStateType | undefined
    const wrapper = ({ children }: { children: ReactNode }) => (
      <PersonalizationCanvasStateProvider
        initialCanvasState={emptyCanvasState("burial_vault_personalization_studio")}
      >
        <CanvasStateProbe
          onState={(s) => {
            capturedCanvasState = s
          }}
        />
        {children}
      </PersonalizationCanvasStateProvider>
    )
    const { result } = renderHook(() => useAIExtractionReview("instance-1"), {
      wrapper,
    })
    await act(async () => {
      await result.current.requestSuggestLayout()
    })
    act(() => {
      result.current.edit(result.current.payload!.line_items[0])
    })
    expect(result.current.decisions[0].decision).toBe("edit")
    // Canonical Edit canonical does NOT canonically apply to canvas state.
    expect(capturedCanvasState?.canvas_layout.elements).toHaveLength(0)
  })
})


/** Test-only canvas state probe — canonically captures canonical canvas
 *  state at each render so canonical tests verify canonical canvas
 *  state mutation discipline. */
function CanvasStateProbe({
  onState,
}: {
  onState: (state: ReturnType<typeof emptyCanvasState>) => void
}) {
  const { canvasState } = usePersonalizationCanvasState()
  onState(canvasState)
  return null
}
