/**
 * "orders" opens the order list from the real Opas host.
 * The catalog resolver is not asked. A second question updates the same pane.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { OrderListSnapshot } from "@/services/order-list-service"

const askOrderList = vi.fn()
const getSalesOrderSummary = vi.fn()
const resolvePhrase = vi.fn()
const openFocus = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  askOrderList: (...args: unknown[]) => askOrderList(...args),
  getSalesOrderSummary: (...args: unknown[]) => getSalesOrderSummary(...args),
}))
vi.mock("@/services/opas-catalog-service", () => ({
  listVariants: vi.fn(),
  getVariant: vi.fn(),
  resolvePhrase: (...args: unknown[]) => resolvePhrase(...args),
}))
vi.mock("@/contexts/auth-context", () => ({ useAuth: () => ({ isAdmin: true }) }))
vi.mock("@/core/CommandBarProvider", () => ({
  useCommandBar: () => ({ isOpen: false, open: vi.fn(), close: vi.fn() }),
}))
vi.mock("@/contexts/focus-context", () => ({
  useFocus: () => ({ isOpen: false, open: openFocus }),
  useFocusOptional: () => ({ isOpen: false, open: openFocus }),
}))

const OPEN: OrderListSnapshot = {
  kind: "question",
  layout: "grouped",
  title: "Open orders",
  surface: "pane",
  question: { is_default: true, title: "Open orders", about_money: false },
  groups: [{
    id: "needs_something",
    label: "Needs something",
    count: 1,
    orders: [{
      id: "so-1",
      number: "SO-1",
      deceased_name: "Walter Penn",
      stage: "scheduled",
      stage_label: "Scheduled",
      dots_filled: 1,
      invoiced: false,
      flag: "nodriver",
      flag_label: "No driver yet",
      action: "scheduling",
      action_label: "Open scheduling",
      service_date: "2026-10-16",
    }],
  }],
  footer: "Invoiced orders and orders further out don't show here.",
}

beforeEach(() => {
  askOrderList.mockReset()
  getSalesOrderSummary.mockReset()
  resolvePhrase.mockReset()
  openFocus.mockReset()
  askOrderList.mockResolvedValue(OPEN)
  getSalesOrderSummary.mockResolvedValue({
    id: "so-1",
    number: "SO-1",
    deceased_name: "Walter Penn",
    funeral_home: "Hopkins",
    stands_at: "No driver yet",
  })
})

async function mount() {
  const { OpasProvider } = await import("@/contexts/opas-context")
  const { OpasHost } = await import("../OpasHost")
  return render(
    <OpasProvider>
      <OpasHost />
    </OpasProvider>,
  )
}

async function ask(phrase: string) {
  fireEvent.click(screen.getByTestId("opas-sphere"))
  const input = screen.getByTestId("opas-input")
  fireEvent.change(input, { target: { value: phrase } })
  await act(async () => {
    fireEvent.keyDown(input, { key: "Enter" })
  })
}

describe("the order list opens from Opas", () => {
  it("orders opens one list and does not resolve a product", async () => {
    await mount()
    await ask("orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-list")).toBeTruthy())
    expect(screen.getByTestId("opas-order-title").textContent).toBe("Open orders")
    expect(resolvePhrase).not.toHaveBeenCalled()
    expect(askOrderList).toHaveBeenCalledWith({ phrase: "orders", question: undefined })
    const pane = screen.getByTestId("opas-order-list").closest("[data-pane-width]")
    expect(pane?.getAttribute("data-pane-width")).toContain("37rem")
  })

  it("a row opens the sales order beside the list, and the fix does not", async () => {
    await mount()
    await ask("orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-row-so-1")).toBeTruthy())
    fireEvent.click(screen.getByTestId("opas-order-action-so-1"))
    expect(openFocus).toHaveBeenCalledWith("funeral-scheduling", {
      params: { orderId: "so-1", date: "2026-10-16" },
    })
    expect(screen.queryByTestId("opas-sales-order")).toBeNull()
    fireEvent.click(screen.getByTestId("opas-order-row-so-1"))
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.getByTestId("opas-sales-order").textContent).toContain("Walter Penn")
  })

  it("an unrecognized order phrase is said, and the catalog is not opened", async () => {
    askOrderList.mockResolvedValue({
      kind: "unrecognized",
      hint: "Try: Hopkins orders this month · going out Friday",
    })
    await mount()
    await ask("orders blah blah")
    await waitFor(() => expect(screen.getByTestId("opas-said")).toBeTruthy())
    expect(screen.getByTestId("opas-said").textContent).toContain("going out Friday")
    expect(screen.queryByTestId("opas-order-list")).toBeNull()
    expect(resolvePhrase).not.toHaveBeenCalled()
  })

  it("a narrow screen keeps the list and the sales order on one track", async () => {
    const original = window.matchMedia.bind(window)
    window.matchMedia = ((query: string) => ({
      matches: query.includes("640"),
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    })) as typeof window.matchMedia
    try {
      await mount()
      await ask("orders")
      await waitFor(() => expect(screen.getByTestId("opas-order-list")).toBeTruthy())
      expect(screen.getByTestId("opas-order-list").getAttribute("data-layout")).toBe("phone")
      fireEvent.click(screen.getByTestId("opas-order-row-so-1"))
      await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
      expect(screen.getByTestId("opas-order-track")).toBeTruthy()
      expect(screen.getByTestId("opas-order-track-dots")).toBeTruthy()
    } finally {
      window.matchMedia = original
    }
  })
})
