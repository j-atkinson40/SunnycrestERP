/**
 * James's walk for the Cemetery Pane slice, through the host — all four panes chained.
 *
 *   1. "st marys"  -> the Cemetery Pane opens
 *   2. click an order in "Coming up here" -> the Sales Order Pane
 *   3. that order's cemetery link -> St. Mary's comes back TO THE FRONT, not a second copy
 *   4. the funeral home on the order -> Hopkins
 *
 * ⚠️ IT DRIVES THE HOST, NOT THE PANES, which is the lesson of the 2026-10-24 slice:
 * `cemetery-pane.test.tsx` renders `CemeteryPane` directly and hands it its callbacks,
 * so the host's own wiring — `openCemetery`, the dedupe, `settleOrderAnswer`'s two new
 * kinds — is invisible to it. Break P10 of the prefill work read "GREEN — NOT WATCHED"
 * for exactly that reason.
 *
 * ⚠️ STEP 3 IS THE ONE WORTH HAVING. "Opening one already open focuses it; never a
 * duplicate" is satisfied by `pane-identity`'s `cemetery:<id>` row, and a missing row
 * there is a silent `undefined` — two St. Mary's on the desk and nothing failing.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const askOrderList = vi.fn()
const getCustomerDetail = vi.fn()
const getCemeteryDetail = vi.fn()
const getSalesOrderSummary = vi.fn()
const startCapture = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  askOrderList: (...a: unknown[]) => askOrderList(...a),
  getCustomerDetail: (...a: unknown[]) => getCustomerDetail(...a),
  getCemeteryDetail: (...a: unknown[]) => getCemeteryDetail(...a),
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
  // ⚠️ THE THIRD INSTANCE OF THE LESSON THIS FILE ALREADY RECORDS TWICE: a double that
  // omits what the component imports fails at CALL time, not import time. `OpasHost`
  // reads the pick-modifier preference in an effect and calls `.then` on the result,
  // so omitting this here throws inside the effect and the pane renders nothing.
  //
  // ⚠️ AND IT MUST RESOLVE A VALUE, NOT JUST BE A `vi.fn()`. A bare mock returns
  // `undefined`, and `undefined.then` is the same crash one line later.
  fetchCapturePreferences: vi.fn(async () => ({
    pick_modifier: "option" as const,
    pick_modifier_glyph: "⌥",
    pick_modifier_event_flag: "altKey" as const,
  })),
  setCapturePickModifier: vi.fn(async () => ({
    pick_modifier: "control" as const,
    pick_modifier_glyph: "⌃",
    pick_modifier_event_flag: "ctrlKey" as const,
  })),
  startCapture: (...a: unknown[]) => startCapture(...a),
  setCaptureText: vi.fn(), addLine: vi.fn(), choosePick: vi.fn(), readCapture: vi.fn(),
  completeCapture: vi.fn(), approveCapture: vi.fn(), abandonCapture: vi.fn(),
  chooseSwitch: vi.fn(), fetchVocabulary: vi.fn().mockResolvedValue([]),
}))

import { OpasProvider } from "@/contexts/opas-context"
import { OpasHost } from "../OpasHost"

const MARY = "St. Mary's Cemetery"

/** What `cemetery_detail` sends for sunnycrest's St. Mary's — measured 2026-10-26. */
function mary(over: Record<string, unknown> = {}) {
  return {
    id: "m1",
    name: MARY,
    meta: "Skaneateles, NY",
    essentials_empty: "Nothing recorded about getting in yet",
    coming: [{
      id: "o1", number: "SO-2026-0004", short: "0004", deceased_name: "hart",
      funeral_home: "Hopkins Funeral Home", customer_id: "c1",
      status: "Confirmed", date_in_week: true, date_primary: "Wed", time_label: "10:00",
    }],
    overdue: [],
    overdue_label: "Service day passed, not delivered",
    knows: { deliveries_this_year: 1, year: 2026 },
    ...over,
  }
}

/** The order, with its cemetery row LIVE — `inert` is retired. */
function order(over: Record<string, unknown> = {}) {
  return {
    id: "o1",
    number: "SO-2026-0004",
    customer_id: "c1",
    deceased_name: "hart",
    funeral_home: "Hopkins Funeral Home",
    stands_at: "No driver yet",
    title: "Hart",
    state: { kind: "steps", stage: "confirmed", steps: [
      { id: "confirmed", label: "Confirmed", done: true },
      { id: "delivered", label: "Delivered", done: false },
      { id: "invoiced", label: "Invoiced", done: false },
    ] },
    order: [
      { label: "Cemetery", value: MARY, link: { kind: "cemetery", cemetery_id: "m1" } },
      { label: "Service", value: "Wed Oct 28 · 10:00 AM graveside" },
    ],
    billing: { lines: [], total: "$1,705", sentence: "Not invoiced yet." },
    can_undo_confirm: false,
    ...over,
  }
}

function customer() {
  return {
    id: "c1",
    name: "Hopkins Funeral Home",
    action: {
      kind: "new_order", label: "New order",
      opening_line: "order Hopkins Funeral Home ",
      prefill: { funeral_home: "Hopkins Funeral Home" },
    },
    open_orders: [],
    overdue: [],
    overdue_label: "Service day passed, not delivered",
    account: { none: "No invoices yet" },
    knows: { not_enough: "Not enough orders yet", orders: 1 },
    recent: [],
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
  askOrderList.mockReset()
  getCemeteryDetail.mockReset()
  getCustomerDetail.mockReset()
  getSalesOrderSummary.mockReset()
  resolvePhrase.mockReset()
  resolvePhrase.mockImplementation((phrase: string) =>
    Promise.resolve({ phrase, candidates: [], discriminators: [] }),
  )
  getCemeteryDetail.mockResolvedValue(mary())
  getCustomerDetail.mockResolvedValue(customer())
  getSalesOrderSummary.mockResolvedValue(order())
  askOrderList.mockResolvedValue({
    kind: "open_cemetery", cemetery_id: "m1", cemetery_name: MARY,
  })
})

describe("a bare cemetery name opens the pane", () => {
  it("opens from the bar and never twice", async () => {
    openOverlay()
    await ask("st marys")
    await waitFor(() => expect(screen.getByTestId("opas-cemetery-title")).toBeTruthy())
    expect(screen.getByTestId("opas-cemetery-title").textContent).toBe(MARY)
    expect(screen.getByTestId("opas-cemetery-meta").textContent).toContain("Skaneateles, NY")

    // ⚠️ ASKED AGAIN, SAME PANE. The dispatch's "already open: focus, no duplicate".
    await ask("st marys")
    await waitFor(() => {
      expect(screen.getAllByTestId("opas-cemetery-title")).toHaveLength(1)
    })
  })

  it("shows the production emptiness rather than blank labels", async () => {
    openOverlay()
    await ask("st marys")
    await waitFor(() => expect(screen.getByTestId("opas-cemetery-title")).toBeTruthy())
    expect(screen.getByTestId("opas-cemetery-essentials-empty").textContent)
      .toBe("Nothing recorded about getting in yet")
    expect(screen.queryByTestId("opas-cemetery-directions")).toBeNull()
  })
})

describe("two cemeteries sharing a name are a question", () => {
  it("offers both with the town, and opens the one chosen", async () => {
    askOrderList.mockResolvedValue({
      kind: "cemetery_picks",
      hint: "Which one?",
      cemetery_picks: [
        { label: MARY, cemetery_id: "m1", detail: "Skaneateles" },
        { label: "St Marys Cemetery", cemetery_id: "m2", detail: "Auburn" },
      ],
    })
    openOverlay()
    await ask("st marys")
    await waitFor(() => expect(screen.getByText("Which one?")).toBeTruthy())
    // ⚠️ THE TOWN IS ON THE OPTIONS, which is the only thing telling them apart.
    expect(screen.getByText("Skaneateles")).toBeTruthy()
    expect(screen.getByText("Auburn")).toBeTruthy()
    // nothing opened on its own
    expect(screen.queryByTestId("opas-cemetery-title")).toBeNull()

    await act(async () => {
      fireEvent.click(screen.getByText("St Marys Cemetery"))
    })
    await waitFor(() => expect(getCemeteryDetail).toHaveBeenCalledWith("m2"))
  })
})

describe("the walk: four panes chained", () => {
  it("cemetery -> order -> back to the SAME cemetery -> the funeral home", async () => {
    openOverlay()

    // 1. the cemetery
    await ask("st marys")
    await waitFor(() => expect(screen.getByTestId("opas-cemetery-title")).toBeTruthy())

    // 2. an order in "Coming up here"
    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-cemetery-order-SO-2026-0004"))
    })
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(getSalesOrderSummary).toHaveBeenCalledWith("o1")

    // 3. the order's cemetery link — and the SAME pane comes back, not a second one.
    const link = screen.getByTestId("opas-sales-order-open-cemetery")
    expect(link.tagName).toBe("BUTTON")
    await act(async () => {
      fireEvent.click(link)
    })
    await waitFor(() => {
      expect(screen.getAllByTestId("opas-cemetery-title")).toHaveLength(1)
    })
    // ⚠️ READ ONCE, NOT TWICE. A second pane would re-read the same id, so the call
    // count is what distinguishes "focused the open one" from "opened another".
    expect(getCemeteryDetail.mock.calls.filter((c) => c[0] === "m1")).toHaveLength(1)

    // 4. the funeral home on the order row opens Hopkins
    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-cemetery-home-SO-2026-0004"))
    })
    await waitFor(() => expect(getCustomerDetail).toHaveBeenCalledWith("c1"))
    await waitFor(() =>
      expect(screen.getByTestId("opas-customer-title").textContent)
        .toBe("Hopkins Funeral Home"),
    )

    // all four on the desk at once
    expect(screen.getByTestId("opas-cemetery-title")).toBeTruthy()
    expect(screen.getByTestId("opas-sales-order")).toBeTruthy()
    expect(screen.getByTestId("opas-customer-title")).toBeTruthy()
  })
})

describe("the cemetery with an order in front", () => {
  it('"the cemetery" opens it from the order', async () => {
    // ⚠️ THE ORDER IS OPENED FIRST AND THE CEMETERY IS NOT, WHICH A BREAK TEST FORCED.
    // My first version of this test walked "st marys" -> the row -> "the cemetery", so
    // the Cemetery Pane was ALREADY OPEN before the phrase was typed. Both assertions
    // then passed with the handler deleted — `toHaveLength(1)` is true of a pane that
    // was already there, and the read count was already 1. Break C21 turned NOTHING red.
    //
    // Opening only the order means the pane must arrive from the phrase or not at all.
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o1" })
    openOverlay()
    await ask("SO-2026-0004")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.queryByTestId("opas-cemetery-title")).toBeNull()

    // ⚠️ AND THIS CASE SAID "the cemetery pane isn't built yet" UNTIL 2026-10-26, which
    // it could not have done otherwise — the row carried a name and no id. It reads
    // `cemetery_id` off the row's own link now rather than resolving the name again.
    await ask("the cemetery")
    await waitFor(() => expect(screen.getByTestId("opas-cemetery-title")).toBeTruthy())
    expect(screen.getByTestId("opas-cemetery-title").textContent).toBe(MARY)
    expect(getCemeteryDetail).toHaveBeenCalledWith("m1")
  })

  it("says so when the order's cemetery did not resolve to a record", async () => {
    // The LEFT JOIN's reachable branch: a NAME with no link.
    getSalesOrderSummary.mockResolvedValue(order({
      order: [{ label: "Cemetery", value: MARY }],
    }))
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o1" })
    openOverlay()
    await ask("SO-2026-0004")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.queryByTestId("opas-sales-order-open-cemetery")).toBeNull()

    // ⚠️ AND "the cemetery" SAYS SO RATHER THAN OPENING NOTHING. Same reasoning as the
    // test above: with no pane pre-opened, an absence here is the handler's answer.
    await ask("the cemetery")
    await waitFor(() => expect(screen.getByTestId("opas-reply")).toBeTruthy())
    expect(screen.queryByTestId("opas-cemetery-title")).toBeNull()
  })
})
