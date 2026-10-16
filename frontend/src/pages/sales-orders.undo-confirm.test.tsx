/**
 * "Undo confirm" on the order list row — James's step-3 addendum, item 1.
 *
 * Confirming is what puts an order in front of the end-of-day batch. Before this the
 * only way back from a mis-confirm was cancelling, which loses the order number and the
 * capture's own record of what the director said.
 *
 * ⚠️ THE ASSERTION THAT MATTERS IS THE PAYLOAD ONE, NOT THE RENDER ONE. A button can
 * exist, be clickable, and send the wrong thing — so what is pinned is what
 * `updateSalesOrder` was CALLED WITH. Verified by changing the payload to
 * `{status: "cancelled"}` and watching it fail.
 *
 * ⚠️ AND THE SERVER OWNS THE RULE. The page does not decide whether undo is allowed —
 * the backend refuses once the order is delivered or already invoiced, with a sentence
 * naming the remedy. So the other load-bearing test here is that the server's 409 detail
 * reaches the operator instead of a generic "could not undo": that message is the only
 * thing telling them to void the invoice first.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"

import SalesOrdersPage from "./sales-orders"
import { salesService } from "@/services/sales-service"
import { toast } from "sonner"

vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ company: { name: "Sunnycrest" }, isAdmin: true, hasPermission: () => true }),
}))
vi.mock("@/contexts/preset-theme-context", () => ({
  usePresetTheme: () => ({ tenantSettings: {} }),
}))
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function order(overrides: Record<string, unknown> = {}) {
  return {
    id: "ord-1",
    number: "SO-2026-0001",
    customer_name: "Hopkins Funeral Home",
    order_date: "2026-10-14",
    required_date: "2026-10-20",
    status: "confirmed",
    total: "1550.00",
    ...overrides,
  }
}

function mockList(items: Record<string, unknown>[]) {
  vi.spyOn(salesService, "getSalesOrders").mockResolvedValue({
    items,
    total: items.length,
    page: 1,
    per_page: 20,
  } as never)
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <SalesOrdersPage />
    </MemoryRouter>,
  )
}

describe("undo confirm on the order list row", () => {
  it("offers it on a confirmed order", async () => {
    mockList([order()])
    renderPage()
    expect(await screen.findByTestId("undo-confirm-ord-1")).toBeTruthy()
  })

  it("does NOT offer it on a draft", async () => {
    mockList([order({ status: "draft" })])
    renderPage()
    await screen.findByText("SO-2026-0001")
    expect(screen.queryByTestId("undo-confirm-ord-1")).toBeNull()
  })

  it("does NOT offer it on a delivered order", async () => {
    // ⚠️ THE ONE THE SERVER WOULD REFUSE. A button that is usually refused is worse
    // than no button — it reads as available and fails on use.
    mockList([order({ status: "delivered" })])
    renderPage()
    await screen.findByText("SO-2026-0001")
    expect(screen.queryByTestId("undo-confirm-ord-1")).toBeNull()
  })

  it("does NOT offer it on a completed order", async () => {
    mockList([order({ status: "completed" })])
    renderPage()
    await screen.findByText("SO-2026-0001")
    expect(screen.queryByTestId("undo-confirm-ord-1")).toBeNull()
  })

  it("sends status: draft and nothing else", async () => {
    mockList([order()])
    const update = vi
      .spyOn(salesService, "updateSalesOrder")
      .mockResolvedValue(order({ status: "draft" }) as never)
    renderPage()

    await userEvent.click(await screen.findByTestId("undo-confirm-ord-1"))

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update).toHaveBeenCalledWith("ord-1", { status: "draft" })
  })

  it("reloads the list afterwards, so the row stops offering it", async () => {
    mockList([order()])
    const list = salesService.getSalesOrders as unknown as ReturnType<typeof vi.fn>
    vi.spyOn(salesService, "updateSalesOrder").mockResolvedValue(
      order({ status: "draft" }) as never,
    )
    renderPage()
    await userEvent.click(await screen.findByTestId("undo-confirm-ord-1"))
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1))
  })

  it("shows the SERVER's refusal, which names the remedy", async () => {
    // ⚠️ THE LOAD-BEARING ONE. The backend's 409 says *which* invoice to void. A generic
    // "could not undo" leaves the office with no next step — and this page's sibling
    // handler was exactly that until 2026-10-16.
    mockList([order()])
    vi.spyOn(salesService, "updateSalesOrder").mockRejectedValue({
      response: {
        data: {
          detail:
            "Order SO-2026-0001 already has invoice INV-2026-0009 (open), so it cannot go back to draft. Void the invoice first if this order should not have been confirmed.",
        },
      },
    })
    renderPage()
    await userEvent.click(await screen.findByTestId("undo-confirm-ord-1"))

    await waitFor(() => expect(toast.error).toHaveBeenCalled())
    expect(vi.mocked(toast.error).mock.calls[0][0]).toContain("INV-2026-0009")
    expect(vi.mocked(toast.error).mock.calls[0][0]).toContain("Void the invoice first")
  })

  it("falls back to its own wording when the server sends no detail", async () => {
    mockList([order()])
    vi.spyOn(salesService, "updateSalesOrder").mockRejectedValue(new Error("network"))
    renderPage()
    await userEvent.click(await screen.findByTestId("undo-confirm-ord-1"))
    await waitFor(() => expect(toast.error).toHaveBeenCalled())
    expect(vi.mocked(toast.error).mock.calls[0][0]).toBe(
      "Could not undo the confirmation.",
    )
  })

  it("only the clicked row shows Working…, not every row", async () => {
    // A single boolean would disable the whole column; `undoing` holds the id.
    mockList([order(), order({ id: "ord-2", number: "SO-2026-0002" })])
    let release: (v: unknown) => void = () => {}
    vi.spyOn(salesService, "updateSalesOrder").mockImplementation(
      () => new Promise((r) => (release = r)) as never,
    )
    renderPage()
    await userEvent.click(await screen.findByTestId("undo-confirm-ord-1"))

    await waitFor(() =>
      expect(screen.getByTestId("undo-confirm-ord-1").textContent).toContain("Working"),
    )
    expect(screen.getByTestId("undo-confirm-ord-2").textContent).toContain("Undo confirm")
    release(order({ status: "draft" }))
  })
})
