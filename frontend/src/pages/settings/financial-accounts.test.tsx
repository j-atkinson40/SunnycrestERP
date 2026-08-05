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
const mockApiPut = vi.fn()

vi.mock("@/lib/api-client", () => ({
  default: {
    get: (...args: unknown[]) => mockApiGet(...args),
    patch: (...args: unknown[]) => mockApiPatch(...args),
    post: (...args: unknown[]) => mockApiPost(...args),
    put: (...args: unknown[]) => mockApiPut(...args),
  },
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

// The keyword-GL section reads isAdmin (admin writes, everyone reads). Mocked
// rather than wrapped in a real provider — these tests are about the request
// body the form builds, not about auth.
const mockIsAdmin = vi.fn(() => true)
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ isAdmin: mockIsAdmin() }),
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
  gl_account_id: "gl-cash",
  last_reconciled_date: null,
  days_since_reconciled: null,
  status: "never",
}

const GL_ACCOUNTS = [
  { id: "gl-cash", account_number: "1025", account_name: "CHECKING LNB", category: "current_asset" },
  { id: "gl-fees", account_number: "8801", account_name: "BANK FEES", category: "expense" },
]

const KEYWORD_ROWS = [
  {
    classification: "bank_fee", state: "mapped", gl_account_id: "gl-fees",
    account_number: "8801", account_name: "BANK FEES",
  },
  {
    classification: "payroll", state: "intentional", gl_account_id: null,
    account_number: null, account_name: null,
  },
  {
    classification: "nsf", state: "unmapped", gl_account_id: null,
    account_number: null, account_name: null,
  },
]

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
    mockIsAdmin.mockReturnValue(true)
    mockApiGet.mockImplementation((url: string) => {
      if (url === "/reconciliation/accounts") return Promise.resolve({ data: [ACCOUNT] })
      if (url === "/journal-entries/gl-accounts") return Promise.resolve({ data: GL_ACCOUNTS })
      if (url === "/reconciliation/keyword-gl") {
        return Promise.resolve({ data: { classifications: KEYWORD_ROWS } })
      }
      return Promise.resolve({ data: [] })
    })
    mockApiPatch.mockResolvedValue({ data: { status: "updated" } })
    mockApiPut.mockResolvedValue({ data: { classifications: KEYWORD_ROWS } })
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

// ── L-2.1e: the contra picker and the keyword→GL section ───────────────────

describe("contra GL picker", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsAdmin.mockReturnValue(true)
    mockApiGet.mockImplementation((url: string) => {
      if (url === "/reconciliation/accounts") return Promise.resolve({ data: [ACCOUNT] })
      if (url === "/journal-entries/gl-accounts") return Promise.resolve({ data: GL_ACCOUNTS })
      if (url === "/reconciliation/keyword-gl") {
        return Promise.resolve({ data: { classifications: KEYWORD_ROWS } })
      }
      return Promise.resolve({ data: [] })
    })
    mockApiPatch.mockResolvedValue({ data: { status: "updated" } })
    mockApiPut.mockResolvedValue({ data: { classifications: KEYWORD_ROWS } })
  })

  it("sends an EXPLICIT null only when the operator clears it", async () => {
    // The distinction the whole three-valued field exists for. `undefined`
    // preserves; `null` clears. Getting this wrong unmaps the bank account and
    // every subsequent reconciliation JE refuses to book.
    const user = await openEditDialog()
    await user.click(screen.getByTestId("contra-gl-picker"))
    await user.click(await screen.findByTestId("contra-gl-picker-none"))
    await user.click(screen.getByRole("button", { name: /^save$/i }))

    await waitFor(() => expect(mockApiPatch).toHaveBeenCalled())
    const [, body] = mockApiPatch.mock.calls[0]
    expect("gl_account_id" in body).toBe(true)
    expect(body.gl_account_id).toBeNull()
  })

  it("sends the chosen account when one is picked", async () => {
    const user = await openEditDialog()
    await user.click(screen.getByTestId("contra-gl-picker"))
    await user.click(await screen.findByTestId("gl-account-option-8801"))
    await user.click(screen.getByRole("button", { name: /^save$/i }))

    await waitFor(() => expect(mockApiPatch).toHaveBeenCalled())
    expect(mockApiPatch.mock.calls[0][1].gl_account_id).toBe("gl-fees")
  })

  it("fetches the GL account list ONCE for the whole page", async () => {
    // Four pickers on this page (contra + three keyword rows). Caller-supplied
    // is what keeps that one request for 224 rows instead of four.
    renderPage()
    await screen.findByTestId("keyword-gl-section")
    const glCalls = mockApiGet.mock.calls.filter(
      (c) => c[0] === "/journal-entries/gl-accounts",
    )
    expect(glCalls).toHaveLength(1)
  })
})

describe("keyword → GL section", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsAdmin.mockReturnValue(true)
    mockApiGet.mockImplementation((url: string) => {
      if (url === "/reconciliation/accounts") return Promise.resolve({ data: [ACCOUNT] })
      if (url === "/journal-entries/gl-accounts") return Promise.resolve({ data: GL_ACCOUNTS })
      if (url === "/reconciliation/keyword-gl") {
        return Promise.resolve({ data: { classifications: KEYWORD_ROWS } })
      }
      return Promise.resolve({ data: [] })
    })
    mockApiPut.mockResolvedValue({ data: { classifications: KEYWORD_ROWS } })
  })

  it("says WHY a classification might correctly have no account", async () => {
    // Three empty slots read as an unfinished form. Without this copy the next
    // person maps payroll to the nearest plausible expense line precisely
    // because the UI presented a blank to fill.
    renderPage()
    await screen.findByTestId("keyword-gl-section")
    const payroll = screen.getByTestId("keyword-gl-payroll").textContent ?? ""
    expect(payroll).toMatch(/gross wages plus employer taxes/i)
    expect(payroll).toMatch(/no single right account/i)

    const nsf = screen.getByTestId("keyword-gl-nsf").textContent ?? ""
    expect(nsf).toMatch(/accounts receivable/i)
  })

  it("states that leaving one unset is a real answer", async () => {
    renderPage()
    const section = await screen.findByTestId("keyword-gl-section")
    expect(section.textContent).toMatch(/not an unfinished one/i)
  })

  it("distinguishes deliberately-unmapped from not-decided in the row copy", async () => {
    renderPage()
    await screen.findByTestId("keyword-gl-section")
    expect(screen.getByTestId("keyword-gl-payroll").textContent)
      .toMatch(/handled by a person/i)
    expect(screen.getByTestId("keyword-gl-nsf").textContent)
      .toMatch(/not decided yet/i)
  })

  it("PUTs an explicit null when told these don't post automatically", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByTestId("keyword-gl-section")
    await user.click(screen.getByTestId("keyword-gl-unmap-nsf"))

    await waitFor(() => expect(mockApiPut).toHaveBeenCalled())
    const [url, body] = mockApiPut.mock.calls[0]
    expect(url).toBe("/reconciliation/keyword-gl")
    expect(body.classification).toBe("nsf")
    expect("gl_account_id" in body).toBe(true)
    expect(body.gl_account_id).toBeNull()
  })

  it("offers no unmap control on a row already deliberately unmapped", async () => {
    renderPage()
    await screen.findByTestId("keyword-gl-section")
    expect(screen.queryByTestId("keyword-gl-unmap-payroll")).toBeNull()
  })

  it("PUTs the account id when one is chosen", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByTestId("keyword-gl-section")
    await user.click(screen.getByTestId("keyword-gl-picker-nsf"))
    await user.click(await screen.findByTestId("gl-account-option-8801"))

    await waitFor(() => expect(mockApiPut).toHaveBeenCalled())
    expect(mockApiPut.mock.calls[0][1]).toEqual({
      classification: "nsf",
      gl_account_id: "gl-fees",
    })
  })

  it("is read-only for a non-admin", async () => {
    mockIsAdmin.mockReturnValue(false)
    renderPage()
    await screen.findByTestId("keyword-gl-section")
    // State is still visible — everyone reads.
    expect(screen.getByTestId("keyword-gl-bank_fee").textContent).toContain("8801")
    // But nothing is editable.
    expect(screen.queryByTestId("keyword-gl-picker-bank_fee")).toBeNull()
    expect(screen.queryByTestId("keyword-gl-unmap-nsf")).toBeNull()
  })
})
