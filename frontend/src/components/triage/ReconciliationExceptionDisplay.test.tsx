import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

const { mockAct } = vi.hoisted(() => ({ mockAct: vi.fn() }))

vi.mock("@/contexts/triage-session-context", () => ({
  useTriageSession: () => ({ act: mockAct, status: "idle" }),
}))

import { ReconciliationExceptionDisplay } from "./ReconciliationExceptionDisplay"
import type { TriageItem } from "@/types/triage"

function rankedItem(): TriageItem {
  return {
    entity_type: "reconciliation_exception",
    entity_id: "txn-1",
    title: "deposit 525.00",
    subtitle: "2026-07-15",
    extras: {
      amount: "525.00",
      candidates: [
        { id: "c1", candidate_record_type: "customer_payment", candidate_record_id: "pay-aaaaaaaa", score: "0.980", rank: 1, rejection_reason: null, rejection_detail: null },
        { id: "c2", candidate_record_type: "customer_payment", candidate_record_id: "pay-bbbbbbbb", score: "0.950", rank: 2, rejection_reason: null, rejection_detail: null },
        { id: "c3", candidate_record_type: "customer_payment", candidate_record_id: "pay-cccccccc", score: "0.000", rank: 3, rejection_reason: "OUTSIDE_DATE_WINDOW", rejection_detail: { days_diff: 6 } },
      ],
    },
  } as unknown as TriageItem
}

function codingItem(): TriageItem {
  return {
    entity_type: "reconciliation_exception",
    entity_id: "txn-8",
    title: "unidentified deposit 377.00",
    subtitle: "2026-07-15",
    extras: { amount: "377.00", candidates: [] },
  } as unknown as TriageItem
}

beforeEach(() => mockAct.mockReset().mockResolvedValue(undefined))
afterEach(cleanup)

describe("ReconciliationExceptionDisplay — form derives from candidate presence", () => {
  it("renders the RANKED card when candidates are present", () => {
    render(<ReconciliationExceptionDisplay item={rankedItem()} />)
    expect(screen.getByTestId("reconciliation-ranked-card")).toBeInTheDocument()
    expect(screen.queryByTestId("reconciliation-coding-card")).not.toBeInTheDocument()
    // three candidates, near-miss shows its reason
    expect(screen.getAllByRole("option")).toHaveLength(3)
    expect(screen.getByText("outside the date window")).toBeInTheDocument()
  })

  it("renders the CODING card when no candidates", () => {
    render(<ReconciliationExceptionDisplay item={codingItem()} />)
    expect(screen.getByTestId("reconciliation-coding-card")).toBeInTheDocument()
    expect(screen.queryByTestId("reconciliation-ranked-card")).not.toBeInTheDocument()
  })
})

describe("ReconciliationExceptionDisplay — Accept commits the SELECTED candidate", () => {
  it("clicking row 2 accepts row 2's candidate (not the top)", () => {
    render(<ReconciliationExceptionDisplay item={rankedItem()} />)
    // row 2 = the second candidate (c2). Click its rendered content.
    fireEvent.click(screen.getByText("pay-bbbb"))
    expect(mockAct).toHaveBeenCalledWith({ action_id: "accept", payload: { candidate_id: "c2" } })
  })

  it("digit '2' selects and accepts the second candidate (RankedRows path)", () => {
    render(<ReconciliationExceptionDisplay item={rankedItem()} />)
    fireEvent.keyDown(document.body, { key: "2", code: "Digit2" })
    expect(mockAct).toHaveBeenCalledWith({ action_id: "accept", payload: { candidate_id: "c2" } })
  })

  it("Enter accepts the top candidate by default (default selection)", () => {
    render(<ReconciliationExceptionDisplay item={rankedItem()} />)
    fireEvent.keyDown(document.body, { key: "Enter" })
    expect(mockAct).toHaveBeenCalledWith({ action_id: "accept", payload: { candidate_id: "c1" } })
  })
})

describe("ReconciliationExceptionDisplay — coding accept", () => {
  it("Accept coding sends the note as payload; disabled until non-empty", () => {
    render(<ReconciliationExceptionDisplay item={codingItem()} />)
    const btn = screen.getByRole("button", { name: "Accept coding" })
    expect(btn).toBeDisabled()
    fireEvent.change(screen.getByLabelText("Coding"), { target: { value: "6100 · Bank interest" } })
    expect(btn).not.toBeDisabled()
    fireEvent.click(btn)
    expect(mockAct).toHaveBeenCalledWith({ action_id: "accept", payload: { coding: "6100 · Bank interest" } })
  })
})
