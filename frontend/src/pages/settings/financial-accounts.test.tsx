/**
 * financial-accounts round-trip tests — Ledger Posting L-2.1a.
 *
 * The bug this pins is CLIENT-side and invisible from the server: `payload()`
 * writes every optional field as `x || null`, sending an EXPLICIT null, and the
 * server's `exclude_unset` reads an explicit null as a deliberate clear. So any
 * field the form fails to hydrate on open is destroyed on the next save — with
 * no error, from an edit that touched something else entirely.
 *
 * `statement_closing_day` was exactly that. It has no input control at all; the
 * form has always SENT it and never FILLED it.
 *
 * This layer is where that class of bug lives, so this is where it is pinned.
 * The server-side contract (omitted preserves, explicit null clears) is pinned
 * separately in backend/tests/test_reconciliation_gl_l1.py and
 * test_reconciliation_account_form.py.
 */
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mockApiGet = vi.fn()
const mockApiPatch = vi.fn()
const mockApiPost = vi.fn()

vi.mock("@/lib/api-client", () => ({
  default: {
    get: (...args: unknown[]) => mockApiGet(...args),
    patch: (...args: unknown[]) => mockApiPatch(...args),
    post: (...args: unknown[]) => mockApiPost(...args),
  },
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import FinancialAccountsSettings from "./financial-accounts"

const ACCOUNT = {
  id: "acct-1",
  account_type: "checking",
  account_name: "Operating",
  institution_name: "First Platypus",
  last_four: "1234",
  is_primary: true,
  credit_limit: null,
  statement_closing_day: 15,
  last_reconciled_date: null,
  days_since_reconciled: null,
  status: "never",
}

function renderPage() {
  return render(
    <MemoryRouter>
      <FinancialAccountsSettings />
    </MemoryRouter>,
  )
}

async function openEditDialog() {
  const user = userEvent.setup()
  renderPage()
  await screen.findByText("Operating")
  // The pencil button is the only ghost button on the card.
  const editButtons = screen.getAllByRole("button")
  const pencil = editButtons.find((b) => b.querySelector("svg.lucide-pencil"))
  await user.click(pencil ?? editButtons[1])
  await screen.findByText("Edit account")
  return user
}

describe("financial-accounts edit round trip", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApiGet.mockResolvedValue({ data: [ACCOUNT] })
    mockApiPatch.mockResolvedValue({ data: { status: "updated" } })
  })

  it("preserves statement_closing_day through an edit that changes only the name", async () => {
    const user = await openEditDialog()

    const nameInput = screen.getByDisplayValue("Operating")
    await user.clear(nameInput)
    await user.type(nameInput, "Renamed")
    await user.click(screen.getByRole("button", { name: /^save$/i }))

    await waitFor(() => expect(mockApiPatch).toHaveBeenCalled())
    const [url, body] = mockApiPatch.mock.calls[0]
    expect(url).toBe("/reconciliation/accounts/acct-1")
    expect(body.account_name).toBe("Renamed")
    // THE PIN. Pre-fix this was null — an unrelated rename cleared the column,
    // because openEdit hardcoded "" and `|| null` turned that into a clear.
    expect(body.statement_closing_day).toBe(15)
  })

  it("never sends null for a field it did not hydrate", async () => {
    // Generalizes the pin past the one field that was broken: whatever the
    // server returns for an account, an untouched edit must not send null for
    // it. This is the assertion that catches the NEXT column added to the
    // response and forgotten in openEdit.
    await openEditDialog()
    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: /^save$/i }))

    await waitFor(() => expect(mockApiPatch).toHaveBeenCalled())
    const [, body] = mockApiPatch.mock.calls[0]
    for (const [key, value] of Object.entries(body)) {
      if (!(key in ACCOUNT)) continue
      const served = ACCOUNT[key as keyof typeof ACCOUNT]
      if (served === null) continue
      expect(
        value,
        `${key} was served as ${JSON.stringify(served)} but sent back as null — ` +
          `an untouched edit would clear it`,
      ).not.toBeNull()
    }
  })

  it("hydrates the account's own values into the form", async () => {
    await openEditDialog()
    expect(screen.getByDisplayValue("Operating")).toBeTruthy()
    expect(screen.getByDisplayValue("First Platypus")).toBeTruthy()
    expect(screen.getByDisplayValue("1234")).toBeTruthy()
  })
})
