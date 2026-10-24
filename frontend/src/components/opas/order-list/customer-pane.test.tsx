/**
 * The Customer Pane renders what the record establishes, and nothing else.
 *
 * ⚠️ THE FIXTURES COME FROM THE SERVER'S CONTRACT, not from reading the component.
 * `customer.customer_detail` decides the shape and the backend suite
 * (`test_customer_pane.py`, `test_customer_pane_reads.py`) pins it against real rows. A
 * double built by reading `CustomerPane.tsx` would agree with it by construction and
 * assert nothing — CLAUDE.md §11, fixtures modelled on the implementation.
 *
 * ⚠️ AND THE SPARSE FIXTURE IS THE PRODUCTION ONE. Measured 2026-10-24: every address,
 * town, director and kind is NULL for all five of Sunnycrest's customers and there are
 * zero contacts, so `hopkinsBare()` — no meta, no people, "Not enough orders yet" — is
 * what James will actually see. The full fixture is the one that does NOT exist yet.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const getCustomerDetail = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  getCustomerDetail: (...args: unknown[]) => getCustomerDetail(...args),
}))

import { CustomerPane } from "./CustomerPane"

/** Production's shape: a name, two lists, an account, and nothing else recorded. */
function hopkinsBare(over: Record<string, unknown> = {}) {
  return {
    id: "c1",
    name: "Hopkins Funeral Home",
    action: {
      kind: "new_order",
      label: "New order",
      opening_line: "order Hopkins Funeral Home ",
      // ⚠️ THE SERVER SENDS THIS UNCONDITIONALLY (`customer.py`, the `new_order`
      // action) and this fixture predated it, so the pane's forwarding of it was
      // untested — the one assertion that looked at the call was asserting the arity.
      prefill: { funeral_home: "Hopkins Funeral Home" },
    },
    open_orders: [],
    overdue: [
      {
        id: "o1", number: "SO-2026-0001", short: "0001", deceased_name: "smith",
        what: "Monticello Burial Vault · St. Mary's Cemetery",
        status: "Draft", date_primary: "Fri Oct 16",
      },
    ],
    overdue_label: "Service day passed, not delivered",
    account: { line: "$0 balance", past_due: false, invoices: 1 },
    knows: { not_enough: "Not enough orders yet", orders: 2 },
    recent: [{ kind: "invoice", label: "INV-2026-0009", when: "2026-10-23T22:00:00Z", detail: "draft" }],
    ...over,
  }
}

beforeEach(() => {
  getCustomerDetail.mockReset()
})

describe("what the record establishes", () => {
  it("shows the name, and no meta line when nothing is recorded", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare())
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-title"))
    expect(screen.getByTestId("opas-customer-title").textContent).toBe("Hopkins Funeral Home")
    // ⚠️ ABSENT, NOT EMPTY. An empty <p> leaves a gap that reads as still loading.
    expect(screen.queryByTestId("opas-customer-meta")).toBeNull()
  })

  it("shows the meta line when the record has one", async () => {
    getCustomerDetail.mockResolvedValue(
      hopkinsBare({ meta: "Funeral home · 12 Genesee St, Skaneateles, NY · Ruth Hopkins, director" }),
    )
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-meta"))
    expect(screen.getByTestId("opas-customer-meta").textContent).toContain("Ruth Hopkins, director")
  })

  it("says nothing is coming up rather than showing an empty list", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare())
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-open-empty"))
    expect(screen.getByTestId("opas-customer-open-empty").textContent).toBe("Nothing coming up.")
  })

  it("heads the overdue group with the order list's own wording", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare())
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-group-overdue"))
    const group = screen.getByTestId("opas-customer-group-overdue")
    expect(group.textContent).toContain("Service day passed, not delivered")
    // The row: short number, deceased, vault · cemetery · day, and the REAL status.
    const row = screen.getByTestId("opas-customer-order-SO-2026-0001")
    expect(row.textContent).toContain("0001")
    expect(row.textContent).toContain("smith")
    expect(row.textContent).toContain("Monticello Burial Vault · St. Mary's Cemetery · Fri Oct 16")
    expect(row.textContent).toContain("Draft")
    // ⚠️ AND NOT THE FUNERAL HOME. We are inside its pane.
    expect(row.textContent).not.toContain("Hopkins")
  })

  it("leaves the overdue group out entirely when there is nothing overdue", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare({ overdue: [] }))
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer"))
    expect(screen.queryByTestId("opas-customer-group-overdue")).toBeNull()
    // The control: "Open orders" still announces itself when empty, because that IS
    // the answer to the question the director asked by opening the pane.
    expect(screen.getByTestId("opas-customer-group-open")).not.toBeNull()
  })
})

describe("the account", () => {
  it("says there are no invoices rather than inventing a balance", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare({ account: { none: "No invoices yet" } }))
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-account-none"))
    expect(screen.getByTestId("opas-customer-account-none").textContent).toBe("No invoices yet")
    expect(screen.queryByTestId("opas-customer-account")).toBeNull()
  })

  it("renders the server's line and colours a past-due account", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare({
      account: { line: "$400 balance · $400 past due · Net 30", past_due: true, invoices: 2 },
    }))
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-account"))
    const el = screen.getByTestId("opas-customer-account")
    expect(el.textContent).toBe("$400 balance · $400 past due · Net 30")
    expect(el.getAttribute("style")).toContain("rgb(204, 116, 82)")
  })
})

describe("the one action", () => {
  it("starts an order with the funeral home already filled", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare())
    const onNewOrder = vi.fn()
    render(<CustomerPane customerId="c1" onNewOrder={onNewOrder} />)
    await waitFor(() => screen.getByTestId("opas-customer-new-order"))
    fireEvent.click(screen.getByTestId("opas-customer-new-order"))
    // ⚠️ INCLUDING THE TRAILING SPACE. "as if the bar said 'order <name> '" — the space
    // is what leaves the capture ready for the next word rather than mid-token.
    //
    // ⚠️ AND THE PREFILL TRAVELS WITH IT, which is the second half of the same action
    // and the fix for James's vanishing funeral home (2026-10-24). The line alone is
    // not enough: re-extraction rebuilds every value from the bar's text, and a name
    // that is only IN THE TEXT can be re-read away. The prefill is the durable record
    // that the director chose this home.
    expect(onNewOrder).toHaveBeenCalledWith("order Hopkins Funeral Home ", {
      funeral_home: "Hopkins Funeral Home",
    })
  })

  it("opens one of the customer's orders", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare())
    const onOpenOrder = vi.fn()
    render(<CustomerPane customerId="c1" onOpenOrder={onOpenOrder} />)
    await waitFor(() => screen.getByTestId("opas-customer-order-SO-2026-0001"))
    fireEvent.click(screen.getByTestId("opas-customer-order-SO-2026-0001"))
    expect(onOpenOrder).toHaveBeenCalledWith("o1")
  })
})

describe("the tabs", () => {
  it("leaves People out when the record has no contacts", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare())
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-tabs"))
    expect(screen.queryByTestId("opas-customer-tab-people")).toBeNull()
    // The controls: the other two are there.
    expect(screen.getByTestId("opas-customer-tab-recent")).not.toBeNull()
    expect(screen.getByTestId("opas-customer-tab-knows")).not.toBeNull()
  })

  it("shows People when there are contacts", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare({
      people: [{ name: "Ruth Hopkins", detail: "Director · (315) 555-0118" }],
    }))
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-tab-people"))
    fireEvent.click(screen.getByTestId("opas-customer-tab-people"))
    expect(screen.getByTestId("opas-customer-people").textContent).toContain("Ruth Hopkins")
  })

  it("says there are not enough orders rather than showing a thin percentage", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare())
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-tab-knows"))
    fireEvent.click(screen.getByTestId("opas-customer-tab-knows"))
    expect(screen.getByTestId("opas-customer-knows-not-enough").textContent)
      .toBe("Not enough orders yet")
    expect(screen.queryByTestId("opas-customer-knows")).toBeNull()
  })

  it("shows the counts once there are three orders", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare({
      knows: {
        orders: 3,
        usual_vault: [
          { name: "Monticello", count: 2, of: 3, line: "Monticello · 2 of 3 orders" },
          { name: "Venetian", count: 1, of: 3, line: "Venetian · 1 of 3 orders" },
        ],
        usual_cemeteries: [
          { name: "St. Mary's Cemetery", count: 3, of: 3, line: "St. Mary's Cemetery · 3 of 3 orders" },
        ],
      },
    }))
    render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-tab-knows"))
    fireEvent.click(screen.getByTestId("opas-customer-tab-knows"))
    const knows = screen.getByTestId("opas-customer-knows")
    expect(knows.textContent).toContain("Usual vault")
    expect(knows.textContent).toContain("Monticello · 2 of 3 orders · Venetian · 1 of 3 orders")
    expect(knows.textContent).toContain("St. Mary's Cemetery · 3 of 3 orders")
    // ⚠️ THE PROTOTYPE'S FORMAT IS THE THING BEING REFUSED, by the dispatch.
    expect(knows.textContent).not.toContain("%")
  })
})

describe("reading", () => {
  it("says so while reading and says so when it cannot", async () => {
    let resolve!: (v: unknown) => void
    getCustomerDetail.mockReturnValue(new Promise((r) => { resolve = r }))
    const { unmount } = render(<CustomerPane customerId="c1" />)
    expect(screen.getByTestId("opas-customer-loading")).not.toBeNull()
    resolve(hopkinsBare())
    await waitFor(() => screen.getByTestId("opas-customer"))
    unmount()

    getCustomerDetail.mockRejectedValue(new Error("boom"))
    render(<CustomerPane customerId="c2" />)
    await waitFor(() => screen.getByTestId("opas-customer-failed"))
    expect(screen.getByTestId("opas-customer-failed").textContent)
      .toBe("This customer could not be read.")
  })

  it("re-reads when the customer changes and resets the tab", async () => {
    getCustomerDetail.mockResolvedValue(hopkinsBare())
    const { rerender } = render(<CustomerPane customerId="c1" />)
    await waitFor(() => screen.getByTestId("opas-customer-tab-knows"))
    fireEvent.click(screen.getByTestId("opas-customer-tab-knows"))
    expect(screen.getByTestId("opas-customer-knows-not-enough")).not.toBeNull()

    getCustomerDetail.mockResolvedValue(hopkinsBare({ id: "c2", name: "Riverside Memorial Chapel" }))
    rerender(<CustomerPane customerId="c2" />)
    await waitFor(() =>
      expect(screen.getByTestId("opas-customer-title").textContent).toBe("Riverside Memorial Chapel"),
    )
    // ⚠️ THE TAB RESETS WITH THE CUSTOMER, or a second customer opens on a tab it may
    // not have — the People tab is absent for most accounts.
    expect(screen.queryByTestId("opas-customer-knows-not-enough")).toBeNull()
    expect(getCustomerDetail).toHaveBeenCalledTimes(2)
  })
})
