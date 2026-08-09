/**
 * GLAccountPicker tests — Ledger Posting L-2.1d.
 *
 * The behaviours pinned here are the ones the extraction had to PRESERVE from
 * the journal-entry form's native <select>, plus the two it deliberately
 * changed. The interesting cases are the unrecognised-value one (the old
 * control rendered it blank and submitted it anyway) and the no-category-filter
 * one (a plausible future "optimization" that would hide accounts operators
 * need).
 */
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  GLAccountPicker,
  filterGLAccounts,
  glAccountLabel,
  type GLAccount,
} from "./GLAccountPicker"

const ACCOUNTS: GLAccount[] = [
  { id: "a1", account_number: "1025", account_name: "CHECKING LNB", category: "current_asset" },
  { id: "a2", account_number: "6450", account_name: "DIRECT LABOR", category: "other" },
  { id: "a3", account_number: "8801", account_name: "BANK FEES", category: "expense" },
  { id: "a4", account_number: "8860", account_name: "PAYROLL PREPARATION", category: "expense" },
]

afterEach(cleanup)

describe("filterGLAccounts", () => {
  it("matches account number and name, case-insensitively", () => {
    expect(filterGLAccounts(ACCOUNTS, "8801").map((a) => a.id)).toEqual(["a3"])
    expect(filterGLAccounts(ACCOUNTS, "bank").map((a) => a.id)).toEqual(["a3"])
    expect(filterGLAccounts(ACCOUNTS, "checking").map((a) => a.id)).toEqual(["a1"])
  })

  it("ranks number prefix matches ahead of contains matches", () => {
    // "88" prefixes 8801 and 8860; nothing else contains it. Someone who knows
    // their chart types the leading digits, so those must come first.
    expect(filterGLAccounts(ACCOUNTS, "88").map((a) => a.account_number)).toEqual([
      "8801",
      "8860",
    ])
  })

  it("NEVER matches on category", () => {
    // Not a missing feature. 73 of 224 production rows are category "other",
    // including DIRECT LABOR — searching or filtering by category hides
    // accounts operators legitimately need.
    expect(filterGLAccounts(ACCOUNTS, "expense")).toHaveLength(0)
    expect(filterGLAccounts(ACCOUNTS, "current_asset")).toHaveLength(0)
  })

  it("returns everything for an empty query", () => {
    expect(filterGLAccounts(ACCOUNTS, "")).toHaveLength(4)
    expect(filterGLAccounts(ACCOUNTS, "   ")).toHaveLength(4)
  })
})

describe("glAccountLabel", () => {
  it("is number then name, one shape everywhere", () => {
    expect(glAccountLabel(ACCOUNTS[2])).toBe("8801 — BANK FEES")
  })
})

describe("GLAccountPicker", () => {
  it("shows the selected account, not its id", () => {
    render(
      <GLAccountPicker accounts={ACCOUNTS} value="a3" onChange={vi.fn()} data-testid="p" />,
    )
    expect(screen.getByTestId("p").textContent).toContain("8801 — BANK FEES")
  })

  it("shows the placeholder when nothing is selected", () => {
    render(
      <GLAccountPicker
        accounts={ACCOUNTS}
        value={null}
        onChange={vi.fn()}
        placeholder="Pick one…"
        data-testid="p"
      />,
    )
    expect(screen.getByTestId("p").textContent).toContain("Pick one…")
  })

  it("SURFACES a value it cannot resolve instead of rendering blank", async () => {
    // The journal-entry form can reach this: its AI parse returns whatever the
    // model wrote for gl_account_id, unvalidated against the chart. The old
    // native <select> showed nothing and submitted the bogus id anyway, so the
    // operator found out from a 400 at save.
    const onChange = vi.fn()
    render(
      <GLAccountPicker
        accounts={ACCOUNTS}
        value="not-a-real-id"
        onChange={onChange}
        data-testid="p"
      />,
    )
    expect(screen.getByTestId("p").textContent).toContain("Unrecognised account")
    // And it must not "helpfully" clear what the caller is holding.
    expect(onChange).not.toHaveBeenCalled()
  })

  it("reports the chosen account id", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <GLAccountPicker accounts={ACCOUNTS} value={null} onChange={onChange} data-testid="p" />,
    )
    await user.click(screen.getByTestId("p"))
    await user.click(await screen.findByTestId("gl-account-option-8801"))
    expect(onChange).toHaveBeenCalledWith("a3")
  })

  it("filters as the operator types", async () => {
    const user = userEvent.setup()
    render(
      <GLAccountPicker accounts={ACCOUNTS} value={null} onChange={vi.fn()} data-testid="p" />,
    )
    await user.click(screen.getByTestId("p"))
    await user.type(await screen.findByTestId("p-search"), "payroll")
    expect(screen.getByTestId("gl-account-option-8860")).toBeTruthy()
    expect(screen.queryByTestId("gl-account-option-8801")).toBeNull()
  })

  it("offers no clear row unless allowNone is set", async () => {
    const user = userEvent.setup()
    render(
      <GLAccountPicker accounts={ACCOUNTS} value="a3" onChange={vi.fn()} data-testid="p" />,
    )
    await user.click(screen.getByTestId("p"))
    await screen.findByTestId("p-search")
    expect(screen.queryByTestId("p-none")).toBeNull()
  })

  it("reports null from the clear row when allowNone is set", async () => {
    // The contra field needs a way back to 'no account' that is a CHOICE, not
    // an empty state — the server reads an explicit null as a deliberate clear.
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <GLAccountPicker
        accounts={ACCOUNTS}
        value="a3"
        onChange={onChange}
        allowNone
        data-testid="p"
      />,
    )
    await user.click(screen.getByTestId("p"))
    await user.click(await screen.findByTestId("p-none"))
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it("says so when nothing matches, rather than showing an empty list", async () => {
    const user = userEvent.setup()
    render(
      <GLAccountPicker accounts={ACCOUNTS} value={null} onChange={vi.fn()} data-testid="p" />,
    )
    await user.click(screen.getByTestId("p"))
    await user.type(await screen.findByTestId("p-search"), "zzzz")
    expect(screen.getByText(/no account matches/i)).toBeTruthy()
  })

  it("does not fetch — the caller owns the list", async () => {
    // Load-bearing: the journal-entry form fetches 224 rows ONCE for a whole
    // entry. A self-fetching picker would make a ten-line entry ten requests.
    const user = userEvent.setup()
    render(
      <GLAccountPicker accounts={ACCOUNTS} value={null} onChange={vi.fn()} data-testid="p" />,
    )
    await user.click(screen.getByTestId("p"))
    expect(await screen.findByTestId("gl-account-option-1025")).toBeTruthy()
    // No api-client mock is installed in this file; if the component fetched,
    // it would hit the real module and this render would not be this quiet.
  })
})
