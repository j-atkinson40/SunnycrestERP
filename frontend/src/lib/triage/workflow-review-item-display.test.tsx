/**
 * Vitest — WorkflowReviewItemDisplay (R-6.0b).
 *
 * Covers approve/reject/edit_and_approve action flows, advance
 * callback firing on success, error toast on failure, line-item
 * confidence badge rendering.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("@/services/triage-service", () => ({
  commitWorkflowReviewDecision: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { commitWorkflowReviewDecision } from "@/services/triage-service"
import { toast } from "sonner"
import type { TriageItem } from "@/types/triage"

import { WorkflowReviewItemDisplay } from "./workflow-review-item-display"


function makeItem(
  overrides: Partial<TriageItem> = {},
  inputData: unknown = { decedent_name: "John Smith" },
): TriageItem {
  return {
    entity_type: "workflow_review_item",
    entity_id: "item_42",
    title: "decedent_info_review",
    subtitle: "FH Intake Workflow",
    extras: {
      trigger_source: "manual",
      created_at: "2026-05-08T12:00:00Z",
      input_data: inputData,
    },
    ...overrides,
  }
}


describe("WorkflowReviewItemDisplay — R-6.0b", () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it("renders the canonical item id testid + 3 actions", () => {
    render(<WorkflowReviewItemDisplay item={makeItem()} />)
    expect(screen.getByTestId("workflow-review-item-item_42")).toBeTruthy()
    expect(screen.getByTestId("workflow-review-approve")).toBeTruthy()
    expect(screen.getByTestId("workflow-review-edit")).toBeTruthy()
    expect(screen.getByTestId("workflow-review-reject")).toBeTruthy()
  })

  it("Approve fires commitWorkflowReviewDecision + advances on success", async () => {
    vi.mocked(commitWorkflowReviewDecision).mockResolvedValue({
      ok: true,
      data: {
        item_id: "item_42",
        decision: "approve",
        review_focus_id: "decedent_info_review",
        run_id: "run_99",
      },
    })
    const onAdvance = vi.fn()
    render(<WorkflowReviewItemDisplay item={makeItem()} onAdvance={onAdvance} />)
    fireEvent.click(screen.getByTestId("workflow-review-approve"))
    await waitFor(() => {
      expect(commitWorkflowReviewDecision).toHaveBeenCalledWith(
        "item_42",
        "approve",
      )
    })
    await waitFor(() => {
      expect(onAdvance).toHaveBeenCalled()
    })
    expect(toast.success).toHaveBeenCalled()
  })

  it("Approve failure surfaces error toast + does NOT advance", async () => {
    vi.mocked(commitWorkflowReviewDecision).mockResolvedValue({
      ok: false,
      error: "boom",
    })
    const onAdvance = vi.fn()
    render(<WorkflowReviewItemDisplay item={makeItem()} onAdvance={onAdvance} />)
    fireEvent.click(screen.getByTestId("workflow-review-approve"))
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("boom")
    })
    expect(onAdvance).not.toHaveBeenCalled()
  })

  it("Reject opens reason dialog + posts decision_notes on confirm", async () => {
    vi.mocked(commitWorkflowReviewDecision).mockResolvedValue({
      ok: true,
      data: {
        item_id: "item_42",
        decision: "reject",
        review_focus_id: "x",
        run_id: "y",
      },
    })
    render(<WorkflowReviewItemDisplay item={makeItem()} />)
    fireEvent.click(screen.getByTestId("workflow-review-reject"))
    const reason = screen.getByTestId(
      "workflow-review-reject-reason",
    ) as HTMLTextAreaElement
    fireEvent.change(reason, { target: { value: "decedent name wrong" } })
    fireEvent.click(screen.getByTestId("workflow-review-reject-confirm"))
    await waitFor(() => {
      expect(commitWorkflowReviewDecision).toHaveBeenCalledWith(
        "item_42",
        "reject",
        undefined,
        "decedent name wrong",
      )
    })
  })

  it("Edit & Approve opens JSON editor + posts edited payload", async () => {
    vi.mocked(commitWorkflowReviewDecision).mockResolvedValue({
      ok: true,
      data: {
        item_id: "item_42",
        decision: "edit_and_approve",
        review_focus_id: "x",
        run_id: "y",
      },
    })
    render(<WorkflowReviewItemDisplay item={makeItem()} />)
    fireEvent.click(screen.getByTestId("workflow-review-edit"))
    const ta = screen.getByTestId(
      "json-textarea-editor-textarea",
    ) as HTMLTextAreaElement
    fireEvent.change(ta, {
      target: { value: '{"decedent_name": "Edited Name"}' },
    })
    fireEvent.click(screen.getByTestId("json-textarea-editor-save"))
    await waitFor(() => {
      expect(commitWorkflowReviewDecision).toHaveBeenCalledWith(
        "item_42",
        "edit_and_approve",
        { decedent_name: "Edited Name" },
      )
    })
  })

  it("renders confidence-scored line items with badges", () => {
    const item = makeItem(
      {},
      {
        line_items: [
          { label: "Decedent name", value: "John Smith", confidence: 0.92 },
          { label: "DOB", value: "1942-03-14", confidence: 0.65 },
          { label: "Service date", value: "2026-05-12", confidence: 0.42 },
        ],
      },
    )
    render(<WorkflowReviewItemDisplay item={item} />)
    expect(screen.getByText("Decedent name")).toBeTruthy()
    expect(screen.getByText("92%")).toBeTruthy()
    expect(screen.getByText("65%")).toBeTruthy()
    expect(screen.getByText("42%")).toBeTruthy()
  })

  it("falls back to JSON pre tag for non-object input_data", () => {
    const item = makeItem({}, "raw string payload")
    render(<WorkflowReviewItemDisplay item={item} />)
    const preview = screen.getByTestId("workflow-review-input-data")
    expect(preview.textContent).toContain("raw string payload")
  })

  it("renders empty payload caption when input_data is null", () => {
    const item = makeItem({}, null)
    render(<WorkflowReviewItemDisplay item={item} />)
    expect(
      screen.queryByTestId("workflow-review-input-data"),
    ).toBeNull()
  })

  it("humanizes the focus_id slug in the title", async () => {
    const item = makeItem({ title: "decedent_info_review" })
    render(<WorkflowReviewItemDisplay item={item} />)
    // "decedent_info_review" → "Decedent Info Review"
    await waitFor(() => {
      expect(
        screen.getByText(/Review Decedent Info Review/i),
      ).toBeTruthy()
    })
  })
})
