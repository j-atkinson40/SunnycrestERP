/**
 * Vitest — InvokeReviewFocusConfig (R-6.0b).
 *
 * Covers review_focus_id input wiring, reviewer role select,
 * decision_actions checkbox toggling preserves canonical order,
 * input binding parse/format round-trip.
 */

import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import {
  DECISION_ACTIONS,
  InvokeReviewFocusConfig,
  REVIEWER_ROLES,
} from "./InvokeReviewFocusConfig"


describe("InvokeReviewFocusConfig — R-6.0b", () => {
  it("mounts with the data-testid root", () => {
    const onChange = vi.fn()
    render(
      <InvokeReviewFocusConfig config={{}} onChange={onChange} />,
    )
    expect(
      screen.getByTestId("wf-invoke-review-focus-config"),
    ).toBeTruthy()
  })

  it("review_focus_id input round-trips through onChange", () => {
    const onChange = vi.fn()
    render(
      <InvokeReviewFocusConfig
        config={{ review_focus_id: "decedent_info_review" }}
        onChange={onChange}
      />,
    )
    const input = screen.getByTestId(
      "wf-invoke-review-focus-slug",
    ) as HTMLInputElement
    expect(input.value).toBe("decedent_info_review")
    fireEvent.change(input, { target: { value: "new_slug" } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ review_focus_id: "new_slug" }),
    )
  })

  it("ships the canonical 7-role catalog", () => {
    expect(REVIEWER_ROLES.length).toBe(7)
    expect(REVIEWER_ROLES.map((r) => r.value)).toContain("fh_director")
    expect(REVIEWER_ROLES.map((r) => r.value)).toContain("admin")
  })

  it("renders 3 decision-action checkboxes by default", () => {
    const onChange = vi.fn()
    render(
      <InvokeReviewFocusConfig config={{}} onChange={onChange} />,
    )
    for (const action of DECISION_ACTIONS) {
      const checkbox = screen.getByTestId(
        `wf-invoke-review-focus-decision-${action.id}`,
      ) as HTMLInputElement
      expect(checkbox.checked).toBe(true)
    }
  })

  it("toggling a decision action preserves canonical order in onChange", () => {
    const onChange = vi.fn()
    render(
      <InvokeReviewFocusConfig
        config={{ decision_actions: ["approve", "edit_and_approve", "reject"] }}
        onChange={onChange}
      />,
    )
    fireEvent.click(
      screen.getByTestId("wf-invoke-review-focus-decision-edit_and_approve"),
    )
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        decision_actions: ["approve", "reject"],
      }),
    )
  })
})
