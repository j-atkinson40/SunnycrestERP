/**
 * SuggestionLineItem tests — canonical Pattern 2 sub-card chrome per
 * §14.14.3 + canonical confidence indicator chrome at canonical
 * thresholds + canonical anti-pattern 1 guard at chrome substrate.
 */

import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SuggestionLineItem } from "./SuggestionLineItem"
import type { SuggestionLineItem as SuggestionLineItemType } from "@/types/personalization-studio"


function makeLineItem(
  overrides: Partial<SuggestionLineItemType> = {},
): SuggestionLineItemType {
  return {
    line_item_key: "name_text_position",
    value: { x: 200, y: 150, width: 400, height: 60 },
    confidence: 0.92,
    rationale: "Centered upper-third placement",
    confidence_tier: "high",
    ...overrides,
  }
}


describe("SuggestionLineItem — canonical Pattern 2 chrome per §14.14.3", () => {
  it("renders canonical line_item_key + value + confidence + rationale", () => {
    const lineItem = makeLineItem()
    render(
      <SuggestionLineItem
        lineItem={lineItem}
        onConfirm={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    expect(screen.getByText("name_text_position")).toBeInTheDocument()
    expect(screen.getByText("0.92")).toBeInTheDocument()
    expect(screen.getByText("Centered upper-third placement")).toBeInTheDocument()
    // Canonical canvas-position rendering canonical "x · y · w · h" format.
    const value = screen.getByText(/x 200/)
    expect(value).toBeInTheDocument()
  })

  it("data-confidence-tier and data-decision attributes set canonically", () => {
    const lineItem = makeLineItem({ confidence_tier: "high" })
    render(
      <SuggestionLineItem
        lineItem={lineItem}
        onConfirm={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    const root = document.querySelector(
      "[data-slot='ai-extraction-suggestion-line-item']",
    ) as HTMLElement
    expect(root.getAttribute("data-confidence-tier")).toBe("high")
    expect(root.getAttribute("data-decision")).toBe("pending")
  })

  it("renders 4 canonical action affordances per §14.14.3 (Confirm/Edit/Reject/Skip)", () => {
    render(
      <SuggestionLineItem
        lineItem={makeLineItem()}
        onConfirm={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    expect(
      document.querySelector("[data-slot='suggestion-confirm']"),
    ).toBeInTheDocument()
    expect(
      document.querySelector("[data-slot='suggestion-edit']"),
    ).toBeInTheDocument()
    expect(
      document.querySelector("[data-slot='suggestion-reject']"),
    ).toBeInTheDocument()
    expect(
      document.querySelector("[data-slot='suggestion-skip']"),
    ).toBeInTheDocument()
  })
})


describe("SuggestionLineItem — canonical confidence indicator chrome per §14.14.3", () => {
  it.each([
    ["high", 0.95, "bg-status-success", "text-status-success"],
    ["medium", 0.75, "bg-status-warning", "text-status-warning"],
    ["low", 0.55, "bg-status-error", "text-status-error"],
  ])(
    "tier=%s confidence=%s renders canonical %s + %s chrome",
    (tier, confidence, bgClass, textClass) => {
      render(
        <SuggestionLineItem
          lineItem={makeLineItem({
            confidence,
            confidence_tier: tier as "high" | "medium" | "low",
          })}
          onConfirm={vi.fn()}
          onEdit={vi.fn()}
          onReject={vi.fn()}
          onSkip={vi.fn()}
        />,
      )
      const indicator = document.querySelector(
        "[data-slot='ai-extraction-confidence-indicator']",
      ) as HTMLElement
      expect(indicator.getAttribute("data-confidence-tier")).toBe(tier)
      // Canonical bg + text chrome per §14.14.3.
      expect(indicator.innerHTML).toContain(bgClass)
      expect(indicator.innerHTML).toContain(textClass)
    },
  )
})


describe("SuggestionLineItem — canonical operator-decision actions", () => {
  it("Confirm action calls canonical onConfirm with canonical line item", () => {
    const onConfirm = vi.fn()
    const lineItem = makeLineItem()
    render(
      <SuggestionLineItem
        lineItem={lineItem}
        onConfirm={onConfirm}
        onEdit={vi.fn()}
        onReject={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    fireEvent.click(
      document.querySelector("[data-slot='suggestion-confirm']")!,
    )
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onConfirm).toHaveBeenCalledWith(lineItem)
  })

  it.each([
    ["Edit", "suggestion-edit", "onEdit"],
    ["Reject", "suggestion-reject", "onReject"],
    ["Skip", "suggestion-skip", "onSkip"],
  ])(
    "%s action calls canonical handler",
    (_label, slot, _handlerKey) => {
      const handlers = {
        onConfirm: vi.fn(),
        onEdit: vi.fn(),
        onReject: vi.fn(),
        onSkip: vi.fn(),
      }
      render(
        <SuggestionLineItem
          lineItem={makeLineItem()}
          onConfirm={handlers.onConfirm}
          onEdit={handlers.onEdit}
          onReject={handlers.onReject}
          onSkip={handlers.onSkip}
        />,
      )
      fireEvent.click(document.querySelector(`[data-slot='${slot}']`)!)
      const targetHandler = handlers[_handlerKey as keyof typeof handlers]
      expect(targetHandler).toHaveBeenCalledTimes(1)
    },
  )
})


describe("SuggestionLineItem — canonical anti-pattern 1 guard", () => {
  it("§3.26.11.12.16 Anti-pattern 1: high confidence does NOT auto-fire onConfirm", () => {
    const onConfirm = vi.fn()
    render(
      <SuggestionLineItem
        lineItem={makeLineItem({ confidence: 0.99, confidence_tier: "high" })}
        onConfirm={onConfirm}
        onEdit={vi.fn()}
        onReject={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    // Canonical anti-pattern 1 guard: chrome substrate renders canonical
    // line item; canonical Confirm action canonical requires canonical
    // operator click. Canonical confidence threshold does NOT trigger
    // canonical auto-commit.
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it("§3.26.11.12.16 Anti-pattern 1: chrome surfaces canonical operator agency for low confidence (no auto-reject)", () => {
    const onReject = vi.fn()
    render(
      <SuggestionLineItem
        lineItem={makeLineItem({ confidence: 0.30, confidence_tier: "low" })}
        onConfirm={vi.fn()}
        onEdit={vi.fn()}
        onReject={onReject}
        onSkip={vi.fn()}
      />,
    )
    // Canonical low-confidence canonical does NOT auto-reject — canonical
    // operator agency canonical at canonical Reject action canonical.
    expect(onReject).not.toHaveBeenCalled()
  })

  it("decision='confirm' canonically locks other actions (canonical operator-decision discipline)", () => {
    render(
      <SuggestionLineItem
        lineItem={makeLineItem()}
        decision="confirm"
        onConfirm={vi.fn()}
        onEdit={vi.fn()}
        onReject={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    const editBtn = document.querySelector(
      "[data-slot='suggestion-edit']",
    ) as HTMLButtonElement
    const rejectBtn = document.querySelector(
      "[data-slot='suggestion-reject']",
    ) as HTMLButtonElement
    const confirmBtn = document.querySelector(
      "[data-slot='suggestion-confirm']",
    ) as HTMLButtonElement
    // Canonical Confirm canonical remains canonical-active; canonical
    // alternates canonical disabled per canonical decision-locked
    // discipline.
    expect(confirmBtn.disabled).toBe(false)
    expect(editBtn.disabled).toBe(true)
    expect(rejectBtn.disabled).toBe(true)
  })
})
