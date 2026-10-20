/**
 * The four multi-pane rules, from James's dispatch of 2026-10-19:
 *
 *   1. Opening a record that's already open focuses that pane; never a duplicate.
 *   2. A new pane is placed in the first free space, not on top of another.
 *   3. Click anywhere on a pane to bring it to the front.          (opas-slice.test.tsx)
 *   4. "close" in the bar closes the front pane; Esc behaviour unchanged.
 *
 * ⚠️ RULE 3 IS NOT RE-TESTED HERE. `opas-slice.test.tsx` already covers raise-on-click
 * and the drag exclusions; a second copy would be two tests of one behaviour, free to
 * disagree about which is authoritative.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useOpas } from "@/contexts/opas-context"
import type { OrderListSnapshot } from "@/services/order-list-service"

const askOrderList = vi.fn()
const getSalesOrderSummary = vi.fn()
const resolvePhrase = vi.fn()
const getVariant = vi.fn()
const listVariants = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  askOrderList: (...args: unknown[]) => askOrderList(...args),
  getSalesOrderSummary: (...args: unknown[]) => getSalesOrderSummary(...args),
}))
vi.mock("@/services/opas-catalog-service", () => ({
  listVariants: (...args: unknown[]) => listVariants(...args),
  getVariant: (...args: unknown[]) => getVariant(...args),
  resolvePhrase: (...args: unknown[]) => resolvePhrase(...args),
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
  startCapture: vi.fn(), setCaptureText: vi.fn(), addLine: vi.fn(),
  choosePick: vi.fn(), readCapture: vi.fn(), completeCapture: vi.fn(),
  approveCapture: vi.fn(), abandonCapture: vi.fn(),
  fetchVocabulary: vi.fn().mockResolvedValue([]),
}))

/** One order per id, each naming the SAME vault, so rule 1 can be tested on the chain. */
function detail(id: string, number: string, name: string) {
  return {
    id, number, deceased_name: name.toLowerCase(), funeral_home: "Hopkins Funeral Home",
    stands_at: "No driver yet", title: name,
    state: {
      kind: "steps", stage: "scheduled",
      steps: [
        { id: "confirmed", label: "Confirmed", done: true },
        { id: "delivered", label: "Delivered", done: false },
        { id: "invoiced", label: "Invoiced", done: false },
      ],
    },
    order: [{
      label: "Vault", value: "Monticello Burial Vault",
      link: { kind: "product", variant_template_id: "variant-monticello" },
    }],
    billing: { lines: [], total: "$1,405", sentence: "Not invoiced yet." },
    can_undo_confirm: true,
  }
}

const LIST: OrderListSnapshot = {
  kind: "question",
  layout: "flat",
  title: "Hopkins orders",
  surface: "pane",
  question: { funeral_home: "Hopkins", title: "Hopkins orders" },
  orders: [
    {
      id: "o1", number: "SO-2026-0003", deceased_name: "Smith", stage: "scheduled",
      stage_label: "Scheduled", dots_filled: 1, invoiced: false,
      service_date: "2026-10-23",
    },
    {
      id: "o2", number: "SO-2026-0004", deceased_name: "Hart", stage: "scheduled",
      stage_label: "Scheduled", dots_filled: 1, invoiced: false,
      service_date: "2026-10-24",
    },
  ],
  footer: "Times and drivers are changed in scheduling, not from a list.",
}

beforeEach(() => {
  askOrderList.mockReset()
  getSalesOrderSummary.mockReset()
  resolvePhrase.mockReset()
  getVariant.mockReset()
  listVariants.mockReset()
  listVariants.mockResolvedValue([])
  // ⚠️ THE CATALOG RESOLVER NEEDS A DEFAULT EVEN IN A FILE ABOUT PANES. Any phrase that
  // is neither a capture opener, the catalog, an order question nor "close" falls
  // through to `resolvePhrase` — "close it out" is one, because it contains no order
  // word. An unmocked call returned `undefined` and `routeResolution` threw on
  // `r.candidates`, which vitest reports as an unhandled rejection and which exits 1
  // whatever the tests did (CLAUDE.md §11, the WidgetChrome correction).
  resolvePhrase.mockResolvedValue({
    phrase: "", normalized: "", resolved: false, candidates: [], discriminators: [],
  })
  getVariant.mockResolvedValue({
    variant_template_id: "variant-monticello", name: "Monticello Burial Vault",
    kind: "burial_vault",
  })
  askOrderList.mockResolvedValue(LIST)
  getSalesOrderSummary.mockImplementation((id: string) =>
    Promise.resolve(
      id === "o1" ? detail("o1", "SO-2026-0003", "Smith") : detail("o2", "SO-2026-0004", "Hart"),
    ),
  )
})

async function mount() {
  const { OpasProvider } = await import("@/contexts/opas-context")
  const { OpasHost } = await import("./OpasHost")
  const out = render(
    <OpasProvider>
      <OpasHost />
    </OpasProvider>,
  )
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

function panes(): HTMLElement[] {
  return Array.from(screen.getByTestId("opas-desk").children) as HTMLElement[]
}

function orderPanes(): HTMLElement[] {
  return panes().filter((p) => p.querySelector("[data-testid='opas-sales-order']") !== null)
}

describe("rule 1 — a record already open is focused, not duplicated", () => {
  it("clicking the same order row twice leaves one pane", async () => {
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-row-o1")).toBeTruthy())

    fireEvent.click(screen.getByTestId("opas-order-row-o1"))
    await waitFor(() => expect(orderPanes()).toHaveLength(1))
    const first = orderPanes()[0]

    fireEvent.click(screen.getByTestId("opas-order-row-o1"))
    await waitFor(() => expect(first.getAttribute("data-focused")).toBe("true"))
    expect(orderPanes(), "a second pane opened for the same order").toHaveLength(1)
  })

  it("two DIFFERENT orders open two panes, and both stay open", async () => {
    // ⚠️ THE CONTROL FOR THE TEST ABOVE, and a rule of its own: the loop that closed
    // every other sales-order pane is gone, because panes chain now.
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-row-o1")).toBeTruthy())
    fireEvent.click(screen.getByTestId("opas-order-row-o1"))
    await waitFor(() => expect(orderPanes()).toHaveLength(1))
    fireEvent.click(screen.getByTestId("opas-order-row-o2"))
    await waitFor(() => expect(orderPanes()).toHaveLength(2))
    const text = orderPanes().map((p) => p.textContent ?? "").join(" ")
    expect(text).toContain("Smith")
    expect(text).toContain("Hart")
  })

  it("⚠️ THE SAME VAULT OPENED FROM TWO ORDERS IS ONE PRODUCT PANE", async () => {
    // The defect the dedupe rule was written for. `openSalesOrder` had this check for
    // sales orders only, so the chain the dispatch is testing — order -> vault, twice —
    // made two identical Monticello panes.
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-row-o1")).toBeTruthy())
    fireEvent.click(screen.getByTestId("opas-order-row-o1"))
    await waitFor(() => expect(orderPanes()).toHaveLength(1))
    fireEvent.click(screen.getByTestId("opas-order-row-o2"))
    await waitFor(() => expect(orderPanes()).toHaveLength(2))

    for (const pane of orderPanes()) {
      const vault = pane.querySelector("[data-testid='opas-sales-order-open-vault']")
      fireEvent.click(vault as HTMLElement)
    }
    await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())
    expect(
      screen.getAllByTestId("opas-product-pane"),
      "the same vault opened twice",
    ).toHaveLength(1)
  })
})

describe("rule 2 — the first free space, not on top of another", () => {
  it("two order panes do not overlap", async () => {
    // ⚠️ OPENED BY NUMBER, SO THE ORDER LIST IS NOT ON THE DESK. With the list open
    // there is not room for both — see the four-pane test below, which records that.
    // This asserts the rule where the rule can hold: two panes, a gap between them.
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o1" })
    await mount()
    await ask("SO-2026-0003")
    await waitFor(() => expect(orderPanes()).toHaveLength(1))
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o2" })
    await ask("SO-2026-0004")
    await waitFor(() => expect(orderPanes()).toHaveLength(2))

    const spans = orderPanes()
      .map((p) => ({
        left: parseFloat(p.style.left),
        width: parseFloat(
          String(p.getAttribute("data-pane-width")).match(/\d+/)?.[0] ?? "390",
        ),
      }))
      .sort((x, y) => x.left - y.left)
    expect(spans.every((s) => Number.isFinite(s.left)), "a pane got no placement").toBe(true)
    expect(new Set(spans.map((s) => s.left)).size, "two panes share one slot").toBe(2)
    // ⚠️ AN ACTUAL SPAN COMPARISON, not merely "different lefts". Two panes 18px apart
    // also have different lefts, and that is exactly the old cascade this replaced.
    expect(
      spans[1].left - spans[0].left,
      "the panes overlap",
    ).toBeGreaterThanOrEqual(spans[0].width)
  })

  it("⚠️ FOUR PANES ON A 1440px SCREEN — what happens today, recorded", async () => {
    // James asked for this specifically: "Report what currently happens with 4+ panes
    // open on a 1440px screen. Don't redesign it yet; James walks it first." So this
    // test RECORDS the behaviour rather than asserting a design. It is what the report
    // quotes.
    Object.defineProperty(window, "innerWidth", { value: 1440, configurable: true })
    window.dispatchEvent(new Event("resize"))
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-row-o1")).toBeTruthy())
    fireEvent.click(screen.getByTestId("opas-order-row-o1"))
    await waitFor(() => expect(orderPanes()).toHaveLength(1))
    fireEvent.click(screen.getByTestId("opas-order-row-o2"))
    await waitFor(() => expect(orderPanes()).toHaveLength(2))
    const vault = orderPanes()[0].querySelector("[data-testid='opas-sales-order-open-vault']")
    fireEvent.click(vault as HTMLElement)
    await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())

    const all = panes()
    expect(all.length).toBeGreaterThanOrEqual(4) // list + 2 orders + product
    const spans = all
      .map((p) => ({
        left: parseFloat(p.style.left),
        width: parseFloat(
          String(p.getAttribute("data-pane-width")).match(/\d+/)?.[0] ?? "390",
        ),
      }))
      .filter((s) => Number.isFinite(s.left))
      .sort((x, y) => x.left - y.left)

    // ⚠️ THE RECORDED FACT: with the order list at 592px and three 390px panes, 1440px
    // does NOT fit all four side by side, so the last one cascades and overlaps. That is
    // the thing James walks, and it is asserted so that a future change to the widths or
    // the anchor shows up here rather than on his screen.
    const overlaps = spans.filter((s, i) => i > 0 && s.left < spans[i - 1].left + spans[i - 1].width)
    expect(overlaps.length, "four panes now fit without overlapping — report this").toBeGreaterThan(0)
    // and none of them is off the left edge
    expect(spans[0].left).toBeGreaterThanOrEqual(0)
  })
})

describe('rule 4 — "close" closes the front pane, Esc still tucks', () => {
  it("closes the pane in front and leaves the rest", async () => {
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-row-o1")).toBeTruthy())
    fireEvent.click(screen.getByTestId("opas-order-row-o1"))
    await waitFor(() => expect(orderPanes()).toHaveLength(1))
    const before = panes().length

    await ask("close")
    await waitFor(() => expect(panes()).toHaveLength(before - 1))
    expect(orderPanes(), "the front pane was not the one that closed").toHaveLength(0)
    expect(screen.getByTestId("opas-order-list"), "the list closed too").toBeTruthy()
  })

  it("says so when nothing is open, rather than silently doing nothing", async () => {
    await mount()
    await ask("close")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toContain(
      "Nothing is open",
    ))
  })

  it("⚠️ ESC IS UNCHANGED — it tucks the session, it does not close a pane", async () => {
    // The dispatch is explicit: "Esc behaviour unchanged." Tuck hides without
    // unmounting and the session comes back where it was left.
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-list")).toBeTruthy())
    const count = panes().length
    await act(async () => {
      fireEvent.keyDown(document, { key: "Escape" })
    })
    expect(panes(), "Escape closed a pane instead of tucking").toHaveLength(count)
    expect(panes()[0].getAttribute("data-tucked")).toBe("true")
  })

  it('"close it out" does NOT close a pane', async () => {
    // The order action, not the pane gesture. See `close-request.test.ts`.
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-list")).toBeTruthy())
    await ask("close it out")
    // the list is still there — nothing was closed
    expect(screen.getByTestId("opas-order-list")).toBeTruthy()

    // ⚠️ WHERE IT ACTUALLY GOES, MEASURED RATHER THAN ASSUMED, AND IT IS NOT NOWHERE.
    // "close it out" is not a close phrase and contains no order word, so it falls
    // through to the catalog resolver, matches nothing, and OPENS AN UNFILTERED CATALOG
    // with "no match for …" on the said line. That is pre-existing behaviour for any
    // unmatched phrase and is not changed here — "Close it out" is a BUTTON on an order
    // row, not something anyone types. Recorded because the first version of this test
    // asserted the pane COUNT was unchanged and went red: a pane did arrive, just not
    // by closing anything.
    expect(resolvePhrase).toHaveBeenCalledWith("close it out")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toContain(
      "Nothing matched",
    ))
  })
})

describe("the pane store survives two writes in one tick", () => {
  /**
   * Close one pane and open another in a single handler. The opened pane survives.
   *
   * ⚠️ THIS TEST DOES **NOT** PIN THE BOTH-LAZY DEFECT, AND SAYING SO IS THE POINT.
   * Measured 2026-10-19: with both `openPane` and `closePane` reverted to deferred
   * `setPanes` updaters — the shape that produced an empty desk on the approve path —
   * this test stays GREEN and ends with exactly the product pane. Two earlier versions
   * were written believing otherwise; the first yielded between the two writes (so they
   * were never in one tick), and this one calls the context directly and still does not
   * reproduce it. The approve path evidently carries more into the same batch —
   * `CapturePane`'s own `setState`, the host's `setText`, `setEntryText`, and
   * `closePane`'s `setEntryTextMap` — and that is what tips it.
   *
   * ⚠️ SO THE PIN FOR THE INVARIANT IS ELSEWHERE: `capture-pane.test.tsx`'s "WITH AN
   * ORDER ID THE CAPTURE CLOSES", which goes red under both-lazy and is the only test
   * that does. The invariant itself is stated in `opas-context.tsx`: every writer of
   * `panes` writes the ref at CALL time and hands `setPanes` a value.
   *
   * ⚠️ IT IS KEPT ANYWAY, as coverage of a real path, and it does fail if `openPane`
   * stops returning the pane it created or if `closePane` removes the wrong one.
   */
  function Probe() {
    const opas = useOpas()
    return (
      <button
        type="button"
        data-testid="probe-close-then-open"
        onClick={() => {
          // one handler, no await: close the first pane and open a second
          const first = opas.panes[0]
          if (first !== undefined) opas.closePane(first.id)
          opas.openPane({ kind: "product", label: "Product", variantTemplateId: "v-probe" })
        }}
      >
        go
      </button>
    )
  }

  it("close-then-open in ONE synchronous handler leaves the opened pane on the desk", async () => {
    const { OpasProvider } = await import("@/contexts/opas-context")
    const { OpasHost } = await import("./OpasHost")
    render(
      <OpasProvider>
        <OpasHost />
        <Probe />
      </OpasProvider>,
    )
    fireEvent.click(screen.getByTestId("opas-sphere"))
    await ask("the catalog")
    await waitFor(() => expect(panes()).toHaveLength(1))

    await act(async () => {
      fireEvent.click(screen.getByTestId("probe-close-then-open"))
    })
    // ⚠️ EXACTLY ONE, AND IT IS THE NEW ONE. (Both-lazy also produces exactly one here
    // — see the docstring. This asserts the behaviour, not the ref mechanism.)
    await waitFor(() => expect(panes()).toHaveLength(1))
    await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())
    expect(screen.queryByTestId("opas-product-list")).toBeNull()
  })
})

describe("opening by order number", () => {
  it("a typed number opens the order's pane and never reaches the catalog", async () => {
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o1" })
    await mount()
    await ask("SO-2026-0003")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.getByTestId("opas-sales-order").textContent).toContain("Smith")
    expect(askOrderList).toHaveBeenCalledWith({ phrase: "SO-2026-0003", question: undefined })
    // ⚠️ THE CATALOG RESOLVER MUST NOT SEE IT. Before the order-number gate, "SO-2026-0003"
    // went to `resolvePhrase`, matched no product, and opened an unfiltered catalog.
    expect(resolvePhrase).not.toHaveBeenCalled()
  })

  it("the short form works too", async () => {
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o2" })
    await mount()
    await ask("0004")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.getByTestId("opas-sales-order").textContent).toContain("Hart")
    expect(resolvePhrase).not.toHaveBeenCalled()
  })
})
