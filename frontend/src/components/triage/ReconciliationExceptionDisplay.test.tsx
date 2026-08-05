import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

const { mockAct } = vi.hoisted(() => ({ mockAct: vi.fn() }))

vi.mock("@/contexts/triage-session-context", () => ({
  useTriageSession: () => ({ act: mockAct, status: "idle" }),
}))

import {
  ReconciliationExceptionDisplay,
  SETTINGS_DESTINATION,
} from "./ReconciliationExceptionDisplay"
import { getAllNavItemsFlat, getNavigation } from "@/services/navigation-service"
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

/**
 * L-2 CONFIG item: the keyword ladder classified it, but there is nowhere to
 * book it. Note `candidates: []` — the SAME shape that routes an ordinary item
 * to the coding card. The classification is the only thing separating them,
 * which is exactly why these tests exist.
 */
function configItem(blockedReason = "keyword_gl_unmapped"): TriageItem {
  return {
    entity_type: "reconciliation_exception",
    entity_id: "txn-9",
    title: "MONTHLY SERVICE CHARGE",
    subtitle: "2026-06-16",
    extras: {
      amount: "-15.00",
      candidates: [],
      keyword_classification: "bank_fee",
      blocked_reason: blockedReason,
    },
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

describe("ReconciliationExceptionDisplay — L-2 CONFIG card (the third form)", () => {
  it("does NOT fall through to the coding card when the row is classified", () => {
    // The regression this whole form exists to prevent: a blocked keyword row
    // has zero candidates, so without the classification check it would render
    // as a coding card and ask the operator to code a row the system has
    // already identified.
    render(<ReconciliationExceptionDisplay item={configItem()} />)
    expect(screen.getByTestId("reconciliation-config-card")).toBeInTheDocument()
    expect(screen.queryByTestId("reconciliation-coding-card")).not.toBeInTheDocument()
    expect(screen.queryByTestId("reconciliation-ranked-card")).not.toBeInTheDocument()
  })

  it("names what the row is and what configuration is missing", () => {
    render(<ReconciliationExceptionDisplay item={configItem()} />)
    expect(screen.getByText("Bank fee")).toBeInTheDocument()
    expect(
      screen.getByText("No GL account is configured for bank fees.")
    ).toBeInTheDocument()
    // L-2.1e: the destination is now NAMED, matching the nav label exactly,
    // rather than described in prose that matched nothing on screen.
    expect(
      screen.getByText(new RegExp(SETTINGS_DESTINATION.replace("→", "."))),
    ).toBeInTheDocument()
  })

  it("offers no Accept — a row that cannot post cannot be accepted", () => {
    // Fail-closed at the UI as well as the service. Flag and Skip remain
    // available from the palette; "ask someone" is the right move when the fix
    // belongs to an administrator.
    render(<ReconciliationExceptionDisplay item={configItem()} />)
    expect(screen.queryByText("Accept coding")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Coding")).not.toBeInTheDocument()
  })

  it("distinguishes a dangling mapping from an absent one", () => {
    // Different operator action — re-map vs configure — so different copy.
    render(<ReconciliationExceptionDisplay item={configItem("keyword_gl_dangling")} />)
    expect(
      screen.getByText("The GL account configured for bank fees is no longer active.")
    ).toBeInTheDocument()
  })

  it("names the bank account, not the keyword map, when the contra leg is missing", () => {
    render(<ReconciliationExceptionDisplay item={configItem("contra_gl_unset")} />)
    expect(
      screen.getByText("This bank account has no GL cash account set.")
    ).toBeInTheDocument()
  })

  it("says a locked period is not a configuration gap", () => {
    render(<ReconciliationExceptionDisplay item={configItem("period_locked")} />)
    expect(
      screen.getByText("The accounting period for this date is closed.")
    ).toBeInTheDocument()
    expect(screen.getByText(/not a configuration gap/)).toBeInTheDocument()
  })

  it("still renders a truthful card for an unrecognised reason", () => {
    render(<ReconciliationExceptionDisplay item={configItem("something_new")} />)
    expect(screen.getByTestId("reconciliation-config-card")).toBeInTheDocument()
    expect(screen.getByText("Bank fee")).toBeInTheDocument()
    expect(
      screen.getByText("This item could not be posted to the ledger.")
    ).toBeInTheDocument()
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

function groupItem(entityId = "txn-7"): TriageItem {
  return {
    entity_type: "reconciliation_exception",
    entity_id: entityId,
    title: "deposit",
    subtitle: "2026-07-15",
    extras: {
      amount: "$4,847.50",
      candidates: [
        {
          id: "g1",
          candidate_record_type: "payment_group",
          candidate_record_id: "grp_abc",
          score: "0.850",
          rank: 1,
          rejection_reason: null,
          rejection_detail: {
            member_count: 3,
            member_total: "4847.50",
            members: [
              { type: "customer_payment", id: "pay-11111111", amount: "1890.00" },
              { type: "customer_payment", id: "pay-22222222", amount: "2142.50" },
              { type: "customer_payment", id: "pay-33333333", amount: "815.00" },
            ],
          },
        },
      ],
    },
  } as unknown as TriageItem
}

describe("ReconciliationExceptionDisplay — one-to-many (payment_group)", () => {
  it("shows a group summary; expanding reveals members WITHOUT accepting", () => {
    render(<ReconciliationExceptionDisplay item={groupItem()} />)
    expect(screen.getByText(/3 payments totalling/)).toBeInTheDocument()
    expect(screen.queryByText("2142.50")).not.toBeInTheDocument() // hidden until expanded
    fireEvent.click(screen.getByText("Show"))
    expect(screen.getByText("2142.50")).toBeInTheDocument() // member now visible
    expect(mockAct).not.toHaveBeenCalled() // expanding is not accepting
  })

  it("clicking the group summary accepts the group", () => {
    render(<ReconciliationExceptionDisplay item={groupItem()} />)
    fireEvent.click(screen.getByText(/3 payments totalling/))
    expect(mockAct).toHaveBeenCalledWith({ action_id: "accept", payload: { candidate_id: "g1" } })
  })

  it("expanded state does not survive the item changing", () => {
    const { rerender } = render(<ReconciliationExceptionDisplay item={groupItem("txn-7")} />)
    fireEvent.click(screen.getByText("Show"))
    expect(screen.getByText("2142.50")).toBeInTheDocument()
    rerender(<ReconciliationExceptionDisplay item={groupItem("txn-99")} />)
    expect(screen.queryByText("2142.50")).not.toBeInTheDocument() // collapsed on the new item
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

// ── L-2.1c: the deliberately-unmapped variant ──────────────────────────────
//
// Five of the six blocked reasons name a fixable problem. This one does not: it
// means an operator already decided this class does not post automatically,
// which for payroll and NSF is the CORRECT answer on a real chart. The tests
// below are mostly negative on purpose — what the copy must not say matters more
// than its exact wording, because the failure mode is telling someone to fix
// what they deliberately chose.

function intentionalItem(classification = "payroll"): TriageItem {
  return {
    entity_type: "reconciliation_exception",
    entity_id: "txn-11",
    title: "ACH Electronic CreditGUSTO PAY 123456",
    subtitle: "2026-07-12",
    extras: {
      amount: "-5850.00",
      candidates: [],
      keyword_classification: classification,
      blocked_reason: "keyword_gl_intentional",
    },
  } as unknown as TriageItem
}

describe("ReconciliationExceptionDisplay — deliberately unmapped", () => {
  it("renders the config card, not the coding card", () => {
    render(<ReconciliationExceptionDisplay item={intentionalItem()} />)
    expect(screen.getByTestId("reconciliation-config-card")).toBeInTheDocument()
    expect(screen.queryByTestId("reconciliation-coding-card")).not.toBeInTheDocument()
  })

  it("does NOT read as a gap someone should close", () => {
    render(<ReconciliationExceptionDisplay item={intentionalItem()} />)
    const card = screen.getByTestId("reconciliation-config-card")
    const text = card.textContent ?? ""
    // The exact words are free to change; these claims are not. Each one would
    // tell the operator to fix a setting they already chose.
    expect(text).not.toMatch(/no gl account is configured/i)
    expect(text).not.toMatch(/an administrator sets this/i)
    expect(text).not.toMatch(/missing/i)
    expect(text).not.toMatch(/no longer active/i)
    expect(text).not.toMatch(/not posted/i)
  })

  it("says the setting is deliberate and that a person handles it", () => {
    render(<ReconciliationExceptionDisplay item={intentionalItem()} />)
    const text = screen.getByTestId("reconciliation-config-card").textContent ?? ""
    expect(text).toMatch(/deliberate/i)
    expect(text).toMatch(/person/i)
  })

  it("reads grammatically for every classification, including payroll", () => {
    // "payroll" takes a singular verb where "bank fees" and "returned items"
    // take a plural one, so copy of the form "X don't post" breaks on one third
    // of the vocabulary. Pin the shape that survives all three.
    for (const c of ["bank_fee", "payroll", "nsf"]) {
      cleanup()
      render(<ReconciliationExceptionDisplay item={intentionalItem(c)} />)
      const text = screen.getByTestId("reconciliation-config-card").textContent ?? ""
      expect(text).toMatch(/posting is turned off for /i)
    }
  })

  it("still offers no Accept — nothing has changed about fail-closed", () => {
    render(<ReconciliationExceptionDisplay item={intentionalItem()} />)
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /accept/i }),
    ).not.toBeInTheDocument()
  })

  it("distinguishes itself from never-configured", () => {
    render(<ReconciliationExceptionDisplay item={intentionalItem()} />)
    const deliberate = screen.getByTestId("reconciliation-config-card").textContent
    cleanup()
    render(<ReconciliationExceptionDisplay item={configItem("keyword_gl_unmapped")} />)
    const unconfigured = screen.getByTestId("reconciliation-config-card").textContent
    expect(deliberate).not.toEqual(unconfigured)
  })
})

// ── L-2.1e: the card and the navigation must agree ─────────────────────────


describe("the blocked card names a destination the operator can reach", () => {
  it("uses the nav label for /settings/accounts verbatim", () => {
    // The loop this sub-arc closes: the card names an action, the nav makes it
    // reachable. If someone renames the nav entry and not the copy, the card
    // sends an operator hunting for a page that no longer goes by that name —
    // which is the original failure, restored.
    const nav = getNavigation(
      "manufacturing", new Set(), new Set(), {}, undefined, true, new Set(),
    )
    const entry = getAllNavItemsFlat(nav).find((i) => i.href === "/settings/accounts")
    expect(entry, "/settings/accounts must be in the navigation").toBeTruthy()
    expect(SETTINGS_DESTINATION).toContain(entry!.label)
  })

  it("every configuration variant points at the same place", () => {
    for (const reason of [
      "keyword_gl_unmapped",
      "keyword_gl_dangling",
      "contra_gl_unset",
      "contra_gl_dangling",
    ]) {
      cleanup()
      render(<ReconciliationExceptionDisplay item={configItem(reason)} />)
      expect(
        screen.getByTestId("reconciliation-config-card").textContent,
      ).toContain(SETTINGS_DESTINATION)
    }
  })

  it("does NOT send the operator to settings for the two non-config reasons", () => {
    // period_locked is a policy gate and keyword_gl_intentional is a settled
    // decision. Neither is fixed on the settings page, so neither may name it.
    for (const reason of ["period_locked", "keyword_gl_intentional"]) {
      cleanup()
      render(<ReconciliationExceptionDisplay item={configItem(reason)} />)
      expect(
        screen.getByTestId("reconciliation-config-card").textContent,
      ).not.toContain(SETTINGS_DESTINATION)
    }
  })
})
