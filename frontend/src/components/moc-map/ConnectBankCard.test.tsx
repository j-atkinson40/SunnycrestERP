/**
 * ConnectBankCard — the setup card's honest states (Plaid B-1).
 *
 *   * loading claims nothing; empty + admin = the CTA; empty + non-admin
 *     = who to ask (gated, not hidden); connected = the minimal honest
 *     state with credit badge; degraded items named.
 *   * No token ever appears in the component's inputs — the service
 *     shape carries none (backend contract).
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"

import { ConnectBankCard } from "./ConnectBankCard"
import type { PlaidItemSummary } from "@/services/plaid-service"

const getPlaidItems = vi.fn()
vi.mock("@/services/plaid-service", () => ({
  getPlaidItems: (...a: unknown[]) => getPlaidItems(...a),
  createLinkToken: vi.fn(),
  exchangePublicToken: vi.fn(),
  getReconciliationAccounts: vi.fn().mockResolvedValue([]),
  linkBankAccount: vi.fn(),
  disconnectPlaidItem: vi.fn(),
}))

vi.mock("react-plaid-link", () => ({
  usePlaidLink: () => ({ open: vi.fn(), ready: false }),
}))

function item(over: Partial<PlaidItemSummary>): PlaidItemSummary {
  return {
    id: "pi-1",
    institution_name: "First Platypus Bank",
    institution_id: "ins_109508",
    status: "active",
    last_synced_at: null,
    accounts: [
      {
        id: "a1", name: "Plaid Checking", mask: "0000",
        account_type: "depository", account_subtype: "checking",
        is_credit: false, financial_account_id: null,
      current_balance: null, available_balance: null, balance_as_of: null,
      },
      {
        id: "a2", name: "Plaid Credit Card", mask: "3333",
        account_type: "credit", account_subtype: "credit card",
        is_credit: true, financial_account_id: null,
      current_balance: null, available_balance: null, balance_as_of: null,
      },
    ],
    ...over,
  }
}

beforeEach(() => {
  getPlaidItems.mockReset()
})

describe("ConnectBankCard", () => {
  it("empty + admin shows the connect CTA", async () => {
    getPlaidItems.mockResolvedValue([])
    render(<ConnectBankCard isAdmin />)
    await waitFor(() => screen.getByTestId("connect-bank-cta"))
    expect(screen.getByText("Connect your bank")).toBeTruthy()
  })

  it("empty + non-admin shows who to ask — gated, not hidden", async () => {
    getPlaidItems.mockResolvedValue([])
    render(<ConnectBankCard isAdmin={false} />)
    await waitFor(() => screen.getByTestId("connect-bank-nonadmin"))
    expect(screen.queryByTestId("connect-bank-cta")).toBeNull()
  })

  it("connected shows the honest minimal state with the credit badge", async () => {
    getPlaidItems.mockResolvedValue([item({})])
    render(<ConnectBankCard isAdmin />)
    await waitFor(() => screen.getByTestId("connect-bank-connected"))
    expect(
      screen.getByText(/Connected: First Platypus Bank/).textContent,
    ).toBeTruthy()
    expect(screen.getByText(/2 accounts/)).toBeTruthy()
    expect(screen.getAllByText(/credit card/).length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByTestId("connect-bank-degraded")).toBeNull()
  })

  it("a degraded item is named, not hidden", async () => {
    getPlaidItems.mockResolvedValue([item({ status: "login_required" })])
    render(<ConnectBankCard isAdmin />)
    await waitFor(() => screen.getByTestId("connect-bank-degraded"))
    expect(screen.getByText("needs re-connecting")).toBeTruthy()
  })
})
