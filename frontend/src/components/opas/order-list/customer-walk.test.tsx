/**
 * The walk, through the host: "hopkins" -> the pane -> New order.
 *
 * ⚠️ IT EXISTS BECAUSE A BREAK TEST SAID NOTHING WAS WATCHING THE HOST. Removing
 * `opas.setEntryText(id, openingLine)` from `startOrderFor` turned nothing red:
 * `capture-prefill.test.tsx` renders `CapturePane` directly and hands it `text`, so the
 * host's own job — putting the opening line in the BAR — was untested. That line is half
 * the fix for James's 2026-10-24 bug ("The bar shows 'order Hopkins Funeral Home ' with
 * the cursor at the end, so what's on screen matches what was captured").
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const askOrderList = vi.fn()
const getCustomerDetail = vi.fn()
const getSalesOrderSummary = vi.fn()
const startCapture = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  askOrderList: (...a: unknown[]) => askOrderList(...a),
  getCustomerDetail: (...a: unknown[]) => getCustomerDetail(...a),
  getSalesOrderSummary: (...a: unknown[]) => getSalesOrderSummary(...a),
}))
// ⚠️ `resolvePhrase` RESOLVES A MISS, NOT `undefined`. The host feeds its result
// straight into `routeResolution`, which reads `.candidates` — a bare `vi.fn()` returns
// undefined and the walk dies with "Cannot read properties of undefined". A MISS is also
// the shape this walk needs: a bare customer name is not a product, so the catalog comes
// back empty and the host falls through to its last resort, `/order-list/ask`, which is
// where the customer rule lives.
const resolvePhrase = vi.fn()
vi.mock("@/services/opas-catalog-service", () => ({
  listVariants: vi.fn().mockResolvedValue([]),
  getVariant: vi.fn(),
  resolvePhrase: (...a: unknown[]) => resolvePhrase(...a),
}))
vi.mock("@/services/sales-service", () => ({
  salesService: { updateSalesOrder: vi.fn().mockResolvedValue({}) },
}))
vi.mock("@/contexts/auth-context", () => ({ useAuth: () => ({ isAdmin: true }) }))
vi.mock("@/core/CommandBarProvider", () => ({
  useCommandBar: () => ({ isOpen: false, open: vi.fn(), close: vi.fn() }),
}))
vi.mock("@/contexts/focus-context", () => ({
  useFocus: () => ({ isOpen: false, open: vi.fn() }),
  useFocusOptional: () => ({ isOpen: false, open: vi.fn() }),
}))
vi.mock("@/services/opas-capture-service", () => ({
  startCapture: (...a: unknown[]) => startCapture(...a),
  setCaptureText: vi.fn(), addLine: vi.fn(), choosePick: vi.fn(), readCapture: vi.fn(),
  completeCapture: vi.fn(), approveCapture: vi.fn(), abandonCapture: vi.fn(),
  chooseSwitch: vi.fn(), fetchVocabulary: vi.fn().mockResolvedValue([]),
}))

import { OpasProvider } from "@/contexts/opas-context"
import { OpasHost } from "../OpasHost"

const HOME = "Hopkins Funeral Home"
const OPENING = "order " + HOME + " "

function customer(over: Record<string, unknown> = {}) {
  return {
    id: "c1",
    name: HOME,
    action: {
      kind: "new_order", label: "New order", opening_line: OPENING,
      prefill: { funeral_home: HOME },
    },
    open_orders: [],
    overdue: [],
    overdue_label: "Service day passed, not delivered",
    account: { none: "No invoices yet" },
    knows: { not_enough: "Not enough orders yet", orders: 1 },
    recent: [],
    ...over,
  }
}

function openOverlay() {
  const out = render(<OpasProvider><OpasHost /></OpasProvider>)
  fireEvent.click(screen.getByTestId("opas-sphere"))
  return out
}

async function ask(phrase: string) {
  const input = screen.getByTestId("opas-input")
  fireEvent.change(input, { target: { value: phrase } })
  await act(async () => {
    fireEvent.keyDown(input, { key: "Enter" })
  })
}

beforeEach(() => {
  resolvePhrase.mockReset()
  resolvePhrase.mockImplementation((phrase: string) =>
    Promise.resolve({ phrase, candidates: [], discriminators: [] }),
  )
  askOrderList.mockReset()
  getCustomerDetail.mockReset()
  startCapture.mockReset()
  getCustomerDetail.mockResolvedValue(customer())
  startCapture.mockResolvedValue({
    session_id: "s1", status: "capturing", object_type: "sales_order",
    typed_lines: [], full_text: OPENING, resolutions: {}, conflicts: {},
    values: { funeral_home: HOME }, answered: [], missing: [],
    unanswered_optional: [], not_applicable: [], indeterminate: [],
    is_complete: false, unrecognized: [], pending_picks: [], switches: [],
    vault_resolution: { resolved: false, candidates: [], discriminators: [] },
    surface: { id: "capture", rows: [] },
  })
})

describe("a bare name opens the Customer Pane", () => {
  it("opens it from the bar and never twice", async () => {
    askOrderList.mockResolvedValue({
      kind: "open_customer", customer_id: "c1", customer_name: HOME,
    })
    openOverlay()
    await ask("hopkins")
    await waitFor(() => expect(screen.getByTestId("opas-customer-title")).toBeTruthy())
    expect(screen.getByTestId("opas-customer-title").textContent).toBe(HOME)

    // ⚠️ "Opening one already open focuses it; never a duplicate" — asking again must
    // not stack a second pane.
    await ask("hopkins")
    await waitFor(() => {
      expect(screen.getAllByTestId("opas-customer-title")).toHaveLength(1)
    })
  })
})

describe("New order puts the line in the bar", () => {
  it("fills the bar with what was captured, and sends the prefill", async () => {
    askOrderList.mockResolvedValue({
      kind: "open_customer", customer_id: "c1", customer_name: HOME,
    })
    openOverlay()
    await ask("hopkins")
    await waitFor(() => expect(screen.getByTestId("opas-customer-new-order")).toBeTruthy())

    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-customer-new-order"))
    })

    // ⚠️ THE ASSERTION THE BREAK TEST WANTED. Without `setEntryText` the bar stays
    // empty, the capture pane is handed `text=""`, and the debounced whole-text re-read
    // rebuilds every value from an empty string — James's vanishing funeral home.
    await waitFor(() => {
      const input = screen.getByTestId("opas-input") as HTMLTextAreaElement
      expect(input.value).toBe(OPENING)
    })

    // and the prefill the SERVER named travelled with it
    await waitFor(() => expect(startCapture).toHaveBeenCalled())
    expect(startCapture).toHaveBeenCalledWith(OPENING, { funeral_home: HOME })
  })

  it("leaves the cursor after the trailing space", async () => {
    askOrderList.mockResolvedValue({
      kind: "open_customer", customer_id: "c1", customer_name: HOME,
    })
    openOverlay()
    await ask("hopkins")
    await waitFor(() => expect(screen.getByTestId("opas-customer-new-order")).toBeTruthy())
    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-customer-new-order"))
    })
    await waitFor(() => {
      const input = screen.getByTestId("opas-input") as HTMLTextAreaElement
      expect(input.value).toBe(OPENING)
      // ⚠️ AFTER the space, so the next word the director types is a new token rather
      // than running into the home's name.
      expect(input.selectionStart).toBe(OPENING.length)
    })
  })
})

describe("a lone generic word asks, even with one match", () => {
  it("renders Did you mean… as a question and opens only on confirm", async () => {
    // ⚠️ ONE PICK, NOT TWO, AND THAT IS THE RULING. "A generic word on its own shows
    // 'Did you mean…' with every customer it matches as a choice, EVEN A SINGLE ONE; the
    // person confirms. It never opens anything directly" (James, 2026-10-24). The host
    // maps `customer_picks` of any length, so this pins that a one-entry list is still a
    // question rather than being shortcut into an opening somewhere on the way.
    askOrderList.mockResolvedValue({
      kind: "customer_picks",
      hint: "Did you mean\u2026",
      customer_picks: [{ label: "Riverside Memorial Chapel", customer_id: "c1" }],
    })
    openOverlay()
    await ask("memorial")

    await waitFor(() =>
      expect(screen.getByText("Did you mean\u2026")).toBeTruthy(),
    )
    // nothing opened on its own
    expect(screen.queryByTestId("opas-customer-title")).toBeNull()
    expect(getCustomerDetail).not.toHaveBeenCalled()

    await act(async () => {
      fireEvent.click(screen.getByText("Riverside Memorial Chapel"))
    })
    await waitFor(() => expect(getCustomerDetail).toHaveBeenCalledWith("c1"))
  })
})

describe("two customers are a choice, not a guess", () => {
  it("offers both and opens the one chosen", async () => {
    askOrderList.mockResolvedValue({
      kind: "customer_picks",
      hint: "Which one?",
      customer_picks: [
        { label: "Riverside Memorial Chapel", customer_id: "c1" },
        { label: "Riverside Burial Services", customer_id: "c2" },
      ],
    })
    openOverlay()
    await ask("riverside")
    await waitFor(() =>
      expect(screen.getByText("Riverside Memorial Chapel")).toBeTruthy(),
    )
    await act(async () => {
      fireEvent.click(screen.getByText("Riverside Memorial Chapel"))
    })
    await waitFor(() => expect(getCustomerDetail).toHaveBeenCalledWith("c1"))
  })
})
