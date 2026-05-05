/**
 * AIExtractionReviewPanel tests — canonical Pattern 2 sub-cards
 * container + canonical batch operations + canonical operator-decision
 * tracking + canonical anti-pattern 1 guard at canonical batch substrate.
 */

import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AIExtractionReviewPanel } from "./AIExtractionReviewPanel"
import type {
  SuggestionLineItem,
  SuggestionPayload,
} from "@/types/personalization-studio"
import type {
  LineItemDecisionRecord,
  UseAIExtractionReviewValue,
} from "./useAIExtractionReview"


function makeReview(
  overrides: Partial<UseAIExtractionReviewValue> = {},
): UseAIExtractionReviewValue {
  return {
    activeSuggestionType: null,
    payload: null,
    isLoading: false,
    error: null,
    decisions: [],
    requestSuggestLayout: vi.fn(),
    requestSuggestTextStyle: vi.fn(),
    requestExtractDecedentInfo: vi.fn(),
    confirm: vi.fn(),
    edit: vi.fn(),
    reject: vi.fn(),
    skip: vi.fn(),
    reset: vi.fn(),
    ...overrides,
  }
}


function makePayload(items: Partial<SuggestionLineItem>[]): SuggestionPayload {
  return {
    line_items: items.map((item, idx) => ({
      line_item_key: item.line_item_key ?? `line-${idx}`,
      value: item.value ?? "test value",
      confidence: item.confidence ?? 0.85,
      rationale: item.rationale ?? "rationale",
      confidence_tier: item.confidence_tier ?? "high",
    })),
    execution_id: "exec-1",
    model_used: "claude-haiku-4-5-20250514",
    latency_ms: 350,
  }
}


describe("AIExtractionReviewPanel — canonical empty state", () => {
  it("returns null when no canonical suggestion requested + no payload + no error + not loading", () => {
    const { container } = render(
      <AIExtractionReviewPanel review={makeReview()} />,
    )
    expect(container.firstChild).toBeNull()
  })
})


describe("AIExtractionReviewPanel — canonical loading + error states", () => {
  it("renders canonical loading state per §14.14.3 visual canon", () => {
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          isLoading: true,
        })}
      />,
    )
    expect(
      document.querySelector("[data-slot='ai-extraction-review-loading']"),
    ).toBeInTheDocument()
  })

  it("renders canonical error state with canonical error message", () => {
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          error: "Suggestion request failed",
        })}
      />,
    )
    expect(screen.getByText(/Suggestion request failed/)).toBeInTheDocument()
  })
})


describe("AIExtractionReviewPanel — canonical Pattern 2 sub-cards rendering", () => {
  it("renders canonical N line items as canonical SuggestionLineItem chrome", () => {
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          payload: makePayload([
            { line_item_key: "name_text_position", confidence: 0.92, confidence_tier: "high" },
            { line_item_key: "date_text_position", confidence: 0.78, confidence_tier: "medium" },
            { line_item_key: "emblem_position", confidence: 0.55, confidence_tier: "low" },
          ]),
        })}
      />,
    )
    const items = document.querySelectorAll(
      "[data-slot='ai-extraction-suggestion-line-item']",
    )
    expect(items).toHaveLength(3)
  })

  it("renders canonical title per canonical activeSuggestionType discriminator", () => {
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          payload: makePayload([{}]),
        })}
      />,
    )
    expect(screen.getByText("Layout suggestions")).toBeInTheDocument()
  })

  it.each([
    ["suggest_layout", "Layout suggestions"],
    ["suggest_text_style", "Text style suggestions"],
    ["extract_decedent_info", "Decedent info — extracted from source materials"],
  ])(
    "activeSuggestionType=%s renders canonical title=%s",
    (suggestionType, expectedTitle) => {
      render(
        <AIExtractionReviewPanel
          review={makeReview({
            activeSuggestionType:
              suggestionType as UseAIExtractionReviewValue["activeSuggestionType"],
            payload: makePayload([{}]),
          })}
        />,
      )
      expect(screen.getByText(expectedTitle)).toBeInTheDocument()
    },
  )

  it("renders canonical empty-payload chrome when canonical line_items=[]", () => {
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          payload: { line_items: [], execution_id: "x", model_used: "m", latency_ms: 0 },
        })}
      />,
    )
    expect(
      document.querySelector("[data-slot='ai-extraction-review-empty']"),
    ).toBeInTheDocument()
  })
})


describe("AIExtractionReviewPanel — canonical batch operations + Anti-pattern 1 guard", () => {
  it("'Confirm all high-confidence' canonical button surfaces with canonical high-count canonical", () => {
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          payload: makePayload([
            { line_item_key: "a", confidence: 0.92, confidence_tier: "high" },
            { line_item_key: "b", confidence: 0.88, confidence_tier: "high" },
            { line_item_key: "c", confidence: 0.65, confidence_tier: "low" },
          ]),
        })}
      />,
    )
    expect(
      document.querySelector("[data-slot='batch-confirm-all-high-confidence']"),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Confirm all high-confidence \(2\)/),
    ).toBeInTheDocument()
  })

  it("§3.26.11.12.16 Anti-pattern 1 guard: 'Confirm all high-confidence' batch requires canonical operator click", () => {
    const confirm = vi.fn()
    const review = makeReview({
      activeSuggestionType: "suggest_layout",
      payload: makePayload([
        { line_item_key: "a", confidence: 0.92, confidence_tier: "high" },
        { line_item_key: "b", confidence: 0.88, confidence_tier: "high" },
      ]),
      confirm,
    })
    render(<AIExtractionReviewPanel review={review} />)

    // Canonical anti-pattern 1 guard: NO confirm fires on render.
    expect(confirm).not.toHaveBeenCalled()

    // Canonical operator click triggers canonical batch confirm.
    fireEvent.click(
      document.querySelector("[data-slot='batch-confirm-all-high-confidence']")!,
    )
    expect(confirm).toHaveBeenCalledTimes(2)
  })

  it("'Confirm all high-confidence' canonical NOT shown when canonical no high-confidence items", () => {
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          payload: makePayload([
            { line_item_key: "a", confidence: 0.65, confidence_tier: "low" },
            { line_item_key: "b", confidence: 0.55, confidence_tier: "low" },
          ]),
        })}
      />,
    )
    expect(
      document.querySelector("[data-slot='batch-confirm-all-high-confidence']"),
    ).toBeNull()
  })

  it("'Reject all' canonical batch requires canonical operator click", () => {
    const reject = vi.fn()
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          payload: makePayload([
            { line_item_key: "a", confidence: 0.92, confidence_tier: "high" },
            { line_item_key: "b", confidence: 0.55, confidence_tier: "low" },
          ]),
          reject,
        })}
      />,
    )
    expect(reject).not.toHaveBeenCalled()
    fireEvent.click(document.querySelector("[data-slot='batch-reject-all']")!)
    expect(reject).toHaveBeenCalledTimes(2)
  })

  it("canonical batch 'Confirm all high-confidence' canonically skips already-decided line items", () => {
    const confirm = vi.fn()
    const decisions: LineItemDecisionRecord[] = [
      { line_item_key: "a", decision: "reject" },
    ]
    render(
      <AIExtractionReviewPanel
        review={makeReview({
          activeSuggestionType: "suggest_layout",
          payload: makePayload([
            { line_item_key: "a", confidence: 0.92, confidence_tier: "high" },
            { line_item_key: "b", confidence: 0.88, confidence_tier: "high" },
          ]),
          decisions,
          confirm,
        })}
      />,
    )
    fireEvent.click(
      document.querySelector("[data-slot='batch-confirm-all-high-confidence']")!,
    )
    // Canonical only 1 fires — canonical "a" canonical already-decided.
    expect(confirm).toHaveBeenCalledTimes(1)
  })
})
