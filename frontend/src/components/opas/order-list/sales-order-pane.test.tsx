/**
 * The Sales Order Pane renders what the order establishes, and nothing else.
 *
 * ⚠️ THE FIXTURES COME FROM THE SERVER'S CONTRACT, not from reading the component.
 * `detail.order_detail` decides the shape; the backend suite
 * (`test_sales_order_pane.py`) pins it against real rows. A double built by reading
 * `SalesOrderPane.tsx` would agree with it by construction and assert nothing.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const getSalesOrderSummary = vi.fn()
const updateSalesOrder = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  getSalesOrderSummary: (...args: unknown[]) => getSalesOrderSummary(...args),
}))
vi.mock("@/services/sales-service", () => ({
  salesService: { updateSalesOrder: (...args: unknown[]) => updateSalesOrder(...args) },
}))

import { SalesOrderPane } from "./SalesOrderPane"

/** A confirmed Hopkins order with everything the pane can show. */
function confirmed(over: Record<string, unknown> = {}) {
  return {
    id: "o1",
    number: "SO-2026-0003",
    deceased_name: "smith",
    funeral_home: "Hopkins Funeral Home",
    stands_at: "No driver yet",
    title: "Smith",
    state: {
      kind: "steps",
      stage: "scheduled",
      steps: [
        { id: "confirmed", label: "Confirmed", done: true },
        { id: "delivered", label: "Delivered", done: false },
        { id: "invoiced", label: "Invoiced", done: false },
      ],
    },
    order: [
      {
        label: "Vault",
        value: "Monticello Burial Vault",
        link: { kind: "product", variant_template_id: "variant-1" },
      },
      {
        label: "Cemetery",
        value: "St. Mary's Cemetery, Skaneateles",
        link: { kind: "cemetery", cemetery_id: "m1" },
      },
      { label: "Service", value: "Fri Oct 23 · 11:00 AM church" },
      { label: "Equipment", value: "Full Equipment" },
      { label: "Total", value: "$1,705" },
    ],
    billing: {
      lines: [
        { description: "Monticello Burial Vault", quantity: "1", unit_price: "$1,405", line_total: "$1,405" },
        { description: "Full Equipment", quantity: "1", unit_price: "$300", line_total: "$300" },
      ],
      total: "$1,705",
      sentence: "Not invoiced yet. It goes out at month end with the October statement.",
    },
    can_undo_confirm: true,
    ...over,
  }
}

beforeEach(() => {
  getSalesOrderSummary.mockReset()
  updateSalesOrder.mockReset()
  getSalesOrderSummary.mockResolvedValue(confirmed())
  updateSalesOrder.mockResolvedValue({})
})

async function mount(props: Record<string, unknown> = {}) {
  const out = render(<SalesOrderPane orderId="o1" {...props} />)
  await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
  return out
}

describe("the header", () => {
  it("shows the title-cased name in the serif, with the number and the funeral home", async () => {
    await mount()
    const title = screen.getByTestId("opas-sales-order-title")
    expect(title.textContent).toBe("Smith")
    // ⚠️ THE SERIF IS THE PROTOTYPE'S `.dec` CLASS AND IT IS THE ONLY SERIF ON THE
    // PANE. Asserted because "title-cased, in the serif" is half of what the dispatch
    // says about this line, and the other half is already covered by the text.
    expect(title.getAttribute("style")).toContain("IBM Plex Serif")
    expect(screen.getByTestId("opas-sales-order-number").textContent).toBe("SO-2026-0003")
    expect(screen.getByTestId("opas-sales-order-fh").textContent).toBe("Hopkins Funeral Home")
  })

  it("⚠️ THE FUNERAL HOME IS NOT A BUTTON YET — the Customer Pane is the next slice", async () => {
    await mount()
    const fh = screen.getByTestId("opas-sales-order-fh")
    expect(fh.tagName).toBe("SPAN")
    expect(fh.querySelector("button")).toBeNull()
    expect(fh.querySelector("a")).toBeNull()
  })
})

describe("the status steps", () => {
  it("renders Confirmed, Delivered, Invoiced with their real state", async () => {
    await mount()
    expect(screen.getByTestId("opas-sales-order-step-confirmed").getAttribute("data-done")).toBe("true")
    expect(screen.getByTestId("opas-sales-order-step-delivered").getAttribute("data-done")).toBe("false")
    expect(screen.getByTestId("opas-sales-order-step-invoiced").getAttribute("data-done")).toBe("false")
    // ⚠️ NOT THE PROTOTYPE'S FOUR. `Proof` and `Scheduled` are the prototype's first two
    // steps; the dispatch replaced them with `Confirmed`, and this is the assertion that
    // would catch a revert to the prototype.
    const steps = screen.getByTestId("opas-sales-order-steps").textContent ?? ""
    expect(steps).not.toContain("Proof")
    expect(steps).not.toContain("Scheduled")
  })

  it("names the state for a screen reader rather than leaving dots unlabelled", async () => {
    await mount()
    const label = screen.getByTestId("opas-sales-order-steps").getAttribute("aria-label")
    expect(label).toContain("Confirmed done")
    expect(label).toContain("Delivered not yet")
  })

  it("a draft shows as Draft, with no steps and no Undo confirm", async () => {
    getSalesOrderSummary.mockResolvedValue(
      confirmed({
        state: { kind: "draft", label: "Draft" },
        can_undo_confirm: false,
      }),
    )
    await mount()
    expect(screen.getByTestId("opas-sales-order-state-draft").textContent).toBe("Draft")
    expect(screen.queryByTestId("opas-sales-order-steps")).toBeNull()
    expect(screen.queryByTestId("opas-sales-order-undo-confirm")).toBeNull()
  })

  it("a cancelled order shows as Cancelled", async () => {
    getSalesOrderSummary.mockResolvedValue(
      confirmed({
        state: { kind: "cancelled", label: "Cancelled" },
        can_undo_confirm: false,
      }),
    )
    await mount()
    expect(screen.getByTestId("opas-sales-order-state-cancelled").textContent).toBe("Cancelled")
    expect(screen.queryByTestId("opas-sales-order-steps")).toBeNull()
  })
})

describe('"the order"', () => {
  it("renders every row the server sent, in the server's order", async () => {
    await mount()
    const labels = Array.from(
      screen.getByTestId("opas-sales-order-rows").querySelectorAll("dt"),
    ).map((dt) => dt.textContent)
    expect(labels).toEqual(["Vault", "Cemetery", "Service", "Equipment", "Total"])
  })

  it("renders no row the server omitted, and still renders the ones it sent", async () => {
    // ⚠️ THE POSITIVE CONTROL IN THE SAME TEST. Without it, "no Equipment row" passes
    // against a pane that renders no rows at all.
    getSalesOrderSummary.mockResolvedValue(
      confirmed({
        order: [
          { label: "Vault", value: "Monticello Burial Vault" },
          { label: "Total", value: "$1,405" },
        ],
      }),
    )
    await mount()
    const text = screen.getByTestId("opas-sales-order-rows").textContent ?? ""
    expect(text).not.toContain("Equipment")
    expect(text).not.toContain("Cemetery")
    expect(text).not.toContain("—")
    expect(text).toContain("Monticello Burial Vault")
    expect(text).toContain("$1,405")
  })

  it("the vault opens the Product Pane", async () => {
    const onOpenProduct = vi.fn()
    await mount({ onOpenProduct })
    fireEvent.click(screen.getByTestId("opas-sales-order-open-vault"))
    expect(onOpenProduct).toHaveBeenCalledWith("variant-1")
  })

  it("⚠️ A VAULT WITH NO RESOLVED VARIANT IS PLAIN TEXT, NOT A DEAD BUTTON", async () => {
    // Production has `Continental Burial Vault`, which resolves to two variants
    // differing by size — so the server sends no link and the name must not look
    // clickable.
    getSalesOrderSummary.mockResolvedValue(
      confirmed({
        order: [{ label: "Vault", value: "Continental Burial Vault" }],
      }),
    )
    const onOpenProduct = vi.fn()
    await mount({ onOpenProduct })
    expect(screen.queryByTestId("opas-sales-order-open-vault")).toBeNull()
    expect(screen.getByTestId("opas-sales-order-rows").textContent).toContain(
      "Continental Burial Vault",
    )
  })

  it("the cemetery opens its pane", async () => {
    // ⚠️ SUPERSEDES "THE CEMETERY IS INERT AND SAYS WHY — no dead click" (2026-10-26).
    // That test asserted a SPAN with `title="The cemetery pane isn't built yet."` and
    // was still GREEN after the link went live, because its own fixture supplied
    // `inert: true` — a shape the server stopped producing. A fixture pinned to the old
    // implementation tests a case nobody will ever see, which is why it was rewritten
    // rather than deleted: the row is still the thing under test.
    const onOpenCemetery = vi.fn()
    await mount({ onOpenCemetery })
    expect(screen.queryByTestId("opas-sales-order-inert-cemetery")).toBeNull()
    const open = screen.getByTestId("opas-sales-order-open-cemetery")
    expect(open.tagName).toBe("BUTTON")
    expect(open.textContent).toBe("St. Mary's Cemetery, Skaneateles")
    fireEvent.click(open)
    expect(onOpenCemetery).toHaveBeenCalledWith("m1", "St. Mary's Cemetery, Skaneateles")
  })

  it("a cemetery with no id stays plain text", async () => {
    // ⚠️ THE BRANCH THE LEFT JOIN MAKES REACHABLE. `_order_extras` LEFT JOINs the
    // cemetery, so an order can carry a NAME the join did not resolve to a row. A
    // button there would 404; the dispatch's rule is plain text instead.
    //
    // ⚠️ THE FIXTURE IS NARROWED HERE, NOT THE PROPS. `mount` spreads into the
    // component; the link lives in the SERVER's payload, so this swaps the mock.
    getSalesOrderSummary.mockResolvedValue(confirmed({
      order: [{ label: "Cemetery", value: "St. Mary's Cemetery, Skaneateles" }],
    }))
    await mount({ onOpenCemetery: vi.fn() })
    expect(screen.queryByTestId("opas-sales-order-open-cemetery")).toBeNull()
    expect(screen.queryByTestId("opas-sales-order-inert-cemetery")).toBeNull()
    expect(screen.getByText("St. Mary's Cemetery, Skaneateles")).toBeTruthy()
  })
})

describe("the tabs", () => {
  it("Billing opens on click and shows the lines, the total and the real sentence", async () => {
    await mount()
    expect(screen.queryByTestId("opas-sales-order-billing")).toBeNull()
    fireEvent.click(screen.getByTestId("opas-sales-order-tab-bill"))
    const billing = screen.getByTestId("opas-sales-order-billing")
    expect(billing.textContent).toContain("Monticello Burial Vault")
    expect(billing.textContent).toContain("Full Equipment")
    expect(screen.getByTestId("opas-sales-order-billing-total").textContent).toBe("$1,705")
    expect(screen.getByTestId("opas-sales-order-billing-sentence").textContent).toBe(
      "Not invoiced yet. It goes out at month end with the October statement.",
    )
  })

  it("clicking the open tab closes it again", async () => {
    await mount()
    fireEvent.click(screen.getByTestId("opas-sales-order-tab-bill"))
    expect(screen.getByTestId("opas-sales-order-billing")).toBeTruthy()
    fireEvent.click(screen.getByTestId("opas-sales-order-tab-bill"))
    expect(screen.queryByTestId("opas-sales-order-billing")).toBeNull()
  })

  it("⚠️ NO HISTORY TAB WHEN THERE IS NO TRAIL — the tab is left out, not empty", async () => {
    await mount()
    expect(screen.queryByTestId("opas-sales-order-tab-hist")).toBeNull()
    // ⚠️ THE CONTROL: the tab row exists and Billing is in it, so "no History tab" is
    // about History rather than about the tabs failing to render.
    expect(screen.getByTestId("opas-sales-order-tab-bill")).toBeTruthy()
  })

  it("History appears with its count when the trail exists", async () => {
    getSalesOrderSummary.mockResolvedValue(
      confirmed({
        history: [
          {
            action: "Created", who: "Jim Atkinson",
            when: "2026-10-19T12:03:59+00:00",
            detail: "$1,705 · from Opas capture",
          },
          {
            action: "Updated", who: "Jim Atkinson",
            when: "2026-10-19T13:00:00+00:00",
            detail_absent: "no fields recorded",
          },
        ],
      }),
    )
    await mount()
    const tab = screen.getByTestId("opas-sales-order-tab-hist")
    expect(tab.textContent).toContain("2")
    fireEvent.click(tab)
    const history = screen.getByTestId("opas-sales-order-history")
    expect(history.textContent).toContain("from Opas capture")
    expect(history.textContent).toContain("Jim Atkinson")
    expect(history.textContent).toContain("Oct 19")
    // ⚠️ AN UPDATE SAYS IT RECORDED NOTHING rather than implying it knows what changed.
    expect(screen.getByTestId("opas-sales-order-history-no-detail").textContent).toContain(
      "no fields recorded",
    )
  })
})

describe("Undo confirm", () => {
  it("sends the draft transition and says what happened", async () => {
    await mount()
    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-sales-order-undo-confirm"))
    })
    expect(updateSalesOrder).toHaveBeenCalledWith("o1", { status: "draft" })
    await waitFor(() =>
      expect(screen.getByTestId("opas-sales-order-notice").textContent).toContain(
        "SO-2026-0003 is a draft again",
      ),
    )
    // and it re-reads, so the pane shows the new state rather than the stale one
    expect(getSalesOrderSummary).toHaveBeenCalledTimes(2)
  })

  it("⚠️ SHOWS THE SERVER'S OWN REFUSAL, which names the remedy", async () => {
    // ⚠️ THE SERVER OWNS THE RULE. `undo_confirm_blocker` returns a sentence saying
    // whether to void the invoice or cancel instead; replacing it with "could not undo"
    // would throw away the only part the office can act on.
    updateSalesOrder.mockRejectedValue({
      response: {
        data: {
          detail:
            "SO-2026-0003 already has invoice INV-2026-0009. Void it first, or cancel the order instead.",
        },
      },
    })
    await mount()
    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-sales-order-undo-confirm"))
    })
    await waitFor(() =>
      expect(screen.getByTestId("opas-sales-order-notice").textContent).toContain(
        "Void it first, or cancel the order instead.",
      ),
    )
  })

  it("falls back to a plain sentence when the server sent no detail", async () => {
    updateSalesOrder.mockRejectedValue(new Error("network"))
    await mount()
    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-sales-order-undo-confirm"))
    })
    await waitFor(() =>
      expect(screen.getByTestId("opas-sales-order-notice").textContent).toBe(
        "Could not undo the confirmation.",
      ),
    )
  })
})

describe("reading the order", () => {
  it("says it is reading, then shows the order", async () => {
    let settle: (v: unknown) => void = () => {}
    getSalesOrderSummary.mockReturnValue(new Promise((r) => { settle = r }))
    render(<SalesOrderPane orderId="o1" />)
    expect(screen.getByTestId("opas-sales-order-loading")).toBeTruthy()
    await act(async () => { settle(confirmed()) })
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
  })

  it("says so when it cannot be read", async () => {
    getSalesOrderSummary.mockRejectedValue(new Error("404"))
    render(<SalesOrderPane orderId="o1" />)
    await waitFor(() => expect(screen.getByTestId("opas-sales-order-failed")).toBeTruthy())
  })
})
