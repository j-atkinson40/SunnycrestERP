import { act, fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { OrderListSnapshot, OrderRow } from "@/services/order-list-service"

import { formatMoney, totalsLine } from "./order-list-format"
import { OrderListPane } from "./OrderListPane"
import { isOrderListPhrase, isOrderRefinement } from "./order-list-routing"

const ROW: OrderRow = {
  id: "so-1",
  number: "SO-2026-0412",
  deceased_name: "John R. Albright",
  meta: "Hopkins · St. Mary's, Skaneateles · Monticello",
  // ⚠️ THE LADDER RUNG AND THE STATUS ARE SEPARATE SINCE 2026-10-23, and this row is
  // the shape the backend actually emits for the two together: `stage: "proof"` (no
  // driver, a change requested on the legacy proof) fills none of the four dots, while
  // the order IS confirmed and says so. `stage_label: "Proof"` is no longer producible
  // by any server — a rung is not a status — so a fixture saying it would be testing an
  // input the system cannot make. CLAUDE.md §11.
  stage: "proof",
  status: "confirmed",
  stage_label: "Confirmed",
  dots_filled: 0,
  invoiced: false,
  service_date: "2026-10-09",
  date_in_week: true,
  date_primary: "Fri",
  time_label: "9:00",
  flag: "change",
  flag_label: "Legacy change requested",
  action: "proof",
  action_label: "Open the proof",
}

const GROUPED: OrderListSnapshot = {
  kind: "question",
  layout: "grouped",
  title: "Open orders",
  surface: "pane",
  groups: [
    {
      id: "needs_something",
      label: "Needs something",
      count: 1,
      orders: [ROW],
    },
    {
      id: "delivered_not_invoiced",
      label: "Delivered, not invoiced yet",
      count: 1,
      orders: [{
        ...ROW,
        id: "so-2",
        deceased_name: "Harold Brandt",
        stage: "delivered",
        status: "delivered",
        stage_label: "Delivered",
        dots_filled: 2,
        flag: "close",
        flag_label: "Delivered, not closed out",
        action: "close",
        action_label: "Close it out",
        date_in_week: false,
        date_primary: "Tue Sep 29",
        date_head: "Tue Sep",
        date_day: "29",
      }],
    },
  ],
  orders: [],
  footer: 'Invoiced orders and orders further out don\'t show here. Ask for them: "Hopkins orders this month".',
}

describe("order list routing is only a gate", () => {
  it("sends the spec's questions to the order list", () => {
    expect(isOrderListPhrase("orders")).toBe(true)
    expect(isOrderListPhrase("Hopkins orders this month")).toBe(true)
    expect(isOrderListPhrase("what's going out Friday")).toBe(true)
    expect(isOrderListPhrase("delivered, not invoiced")).toBe(true)
    expect(isOrderListPhrase("Monticellos since June")).toBe(true)
  })

  it("leaves a catalog phrase alone", () => {
    expect(isOrderListPhrase("the catalog")).toBe(false)
    expect(isOrderListPhrase("wilbert bronze")).toBe(false)
    expect(isOrderRefinement("wilbert bronze")).toBe(false)
  })

  it("treats a narrowing phrase as a refinement", () => {
    expect(isOrderRefinement("only Hopkins")).toBe(true)
    expect(isOrderRefinement("not invoiced")).toBe(true)
    expect(isOrderRefinement("last month")).toBe(true)
    expect(isOrderListPhrase("only Hopkins")).toBe(false)
  })
})

describe("money is formatted from the server's string", () => {
  it("drops cents on a whole dollar amount", () => {
    expect(formatMoney("6840.00")).toBe("$6,840")
    expect(formatMoney("120.50")).toBe("$120.50")
  })

  it("a schedule total is a count", () => {
    expect(totalsLine({ count: 4, show_money: false, total: null, show_not_invoiced: false })).toBe("4 orders")
  })

  it("a money question names the uninvoiced count and the dollars", () => {
    expect(totalsLine({
      count: 5, not_invoiced: 5, show_money: true, total: "6840.00", show_not_invoiced: true,
    })).toBe("5 orders · 5 not invoiced · $6,840")
  })
})

describe("OrderListPane", () => {
  it("renders groups in the order the server sent, with stage dots", () => {
    render(<OrderListPane snapshot={GROUPED} layout="desktop" onOpenOrder={() => {}} />)
    const groups = screen.getAllByTestId(/opas-order-group-/)
    expect(groups[0].getAttribute("data-testid")).toBe("opas-order-group-needs_something")
    expect(groups[1].getAttribute("data-testid")).toBe("opas-order-group-delivered_not_invoiced")
    const dots = screen.getAllByTestId("opas-order-dots")
    expect(dots[0].getAttribute("data-filled")).toBe("0")
    // The dots' accessible name is the STATUS, not the rung — so a reader using a
    // screen reader and a reader looking at the row are told the same thing.
    expect(dots[0].getAttribute("aria-label")).toBe("Confirmed")
    expect(dots[1].getAttribute("data-filled")).toBe("2")
    expect(screen.getByTestId("opas-order-footer").textContent).toContain("Hopkins orders this month")
  })

  it("a fix action does not open the order", () => {
    const onOpen = vi.fn()
    const onFix = vi.fn()
    const scheduling: OrderListSnapshot = {
      ...GROUPED,
      groups: [{
        id: "needs_something",
        label: "Needs something",
        count: 1,
        orders: [{
          ...ROW,
          flag: "nodriver",
          flag_label: "No driver yet",
          action: "scheduling",
          action_label: "Open scheduling",
        }],
      }],
    }
    render(<OrderListPane snapshot={scheduling} layout="desktop" onOpenOrder={onOpen} onFix={onFix} />)
    fireEvent.click(screen.getByTestId("opas-order-action-so-1"))
    expect(onFix).toHaveBeenCalledOnce()
    expect(onOpen).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId("opas-order-row-so-1"))
    expect(onOpen).toHaveBeenCalledWith("so-1")
  })

  it("a proof action is a link, and the row still opens the order", () => {
    const onOpen = vi.fn()
    render(<OrderListPane snapshot={GROUPED} layout="desktop" onOpenOrder={onOpen} />)
    const link = screen.getByTestId("opas-order-action-so-1")
    expect(link.getAttribute("href")).toBe("/legacy/proof/so-1")
    fireEvent.click(link)
    expect(onOpen).not.toHaveBeenCalled()
  })

  it("shows the question, its pills, and the total", () => {
    const onRemove = vi.fn()
    const onAsk = vi.fn()
    const asked: OrderListSnapshot = {
      kind: "question",
      layout: "flat",
      title: "Hopkins orders this month",
      surface: "pane",
      pills: [
        { id: "funeral_home", label: "Hopkins" },
        { id: "when", label: "This month" },
      ],
      orders: [ROW],
      totals: { count: 5, not_invoiced: 5, show_money: true, total: "6840.00", show_not_invoiced: true },
      footer: "Times and drivers are changed in scheduling, not from a list.",
    }
    render(
      <OrderListPane
        snapshot={asked}
        layout="desktop"
        onOpenOrder={() => {}}
        onRemovePill={onRemove}
        onAskHint={onAsk}
      />,
    )
    expect(screen.getByTestId("opas-order-title").textContent).toBe("Hopkins orders this month")
    expect(screen.getByTestId("opas-order-pill-funeral_home").textContent).toContain("Hopkins")
    fireEvent.click(screen.getByTestId("opas-order-pill-remove-funeral_home"))
    expect(onRemove).toHaveBeenCalledWith("funeral_home")
    fireEvent.click(screen.getByTestId("opas-order-ask"))
    expect(onAsk).toHaveBeenCalledOnce()
    expect(screen.getByTestId("opas-order-totals").textContent).toContain("5 not invoiced")
    expect(screen.getByTestId("opas-order-totals").textContent).toContain("$6,840")
  })

  it("stacks a phone row under the name", () => {
    render(<OrderListPane snapshot={GROUPED} layout="phone" onOpenOrder={() => {}} />)
    expect(screen.getByTestId("opas-order-list").getAttribute("data-layout")).toBe("phone")
    expect(screen.getByText("Tue Sep")).toBeTruthy()
    expect(screen.getByText("29")).toBeTruthy()
  })

  it("comfortable density is a property of the pane", () => {
    render(
      <OrderListPane snapshot={GROUPED} layout="desktop" density="comfortable" onOpenOrder={() => {}} />,
    )
    expect(screen.getByTestId("opas-order-list").getAttribute("data-density")).toBe("comfortable")
  })

  it("the lens advances three at a time", () => {
    vi.useFakeTimers()
    try {
      const lens: OrderListSnapshot = {
        kind: "question",
        layout: "flat",
        title: "Going out Friday",
        surface: "lens",
        lens: {
          heading: "GOING OUT FRIDAY · 5",
          cue: "tap: next three · double tap: on the iPad",
          first_order_id: "so-1",
          pages: [
            { items: ["Albright 9:00", "Carr 11:30", "Fenn 1:00"], more: 2 },
            { items: ["Prisco 2:30", "Shaw 11:00"], more: 0 },
          ],
        },
      }
      render(<OrderListPane snapshot={lens} layout="desktop" onOpenOrder={() => {}} />)
      expect(screen.getByTestId("opas-order-lens-bits").textContent).toContain("Albright 9:00")
      fireEvent.click(screen.getByTestId("opas-order-lens"))
      act(() => {
        vi.advanceTimersByTime(250)
      })
      expect(screen.getByTestId("opas-order-lens-bits").textContent).toContain("Prisco 2:30")
    } finally {
      vi.useRealTimers()
    }
  })

  it("a double tap on the lens returns to the list", () => {
    const lens: OrderListSnapshot = {
      kind: "question",
      layout: "flat",
      title: "Going out Friday",
      surface: "lens",
      orders: [ROW],
      lens: {
        heading: "GOING OUT FRIDAY · 2",
        cue: "tap: open the first",
        first_order_id: "so-1",
        pages: [{ items: ["Albright 9:00", "Carr 11:30"], more: 0 }],
      },
    }
    render(<OrderListPane snapshot={lens} layout="desktop" onOpenOrder={() => {}} />)
    fireEvent.doubleClick(screen.getByTestId("opas-order-lens"))
    expect(screen.queryByTestId("opas-order-lens")).toBeNull()
    expect(screen.getByTestId("opas-order-row-so-1")).toBeTruthy()
  })
})
