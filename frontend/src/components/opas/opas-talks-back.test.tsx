/**
 * Opas talks back. James's four rules of 2026-10-20, through the real host.
 *
 *   1. The bar keeps focus.
 *   2. One voice above the bar.
 *   3. Choices sit with the question.
 *   4. Context from the front pane.
 *
 * ⚠️ `document.activeElement` IS THE INSTRUMENT FOR RULE 1, and it is the only one that
 * answers the question asked. A test that asserted a `focus` spy had been called would
 * pass while the element was then blurred by something later in the same tick — which is
 * the failure mode "the bar lost the cursor" actually has.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { OrderListSnapshot } from "@/services/order-list-service"
import { REPLY_FADE_MS } from "./reply"

const askOrderList = vi.fn()
const getSalesOrderSummary = vi.fn()
const resolvePhrase = vi.fn()
const getVariant = vi.fn()
const listVariants = vi.fn()
const updateSalesOrder = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  askOrderList: (...a: unknown[]) => askOrderList(...a),
  getSalesOrderSummary: (...a: unknown[]) => getSalesOrderSummary(...a),
}))
vi.mock("@/services/opas-catalog-service", () => ({
  listVariants: (...a: unknown[]) => listVariants(...a),
  getVariant: (...a: unknown[]) => getVariant(...a),
  resolvePhrase: (...a: unknown[]) => resolvePhrase(...a),
}))
vi.mock("@/services/sales-service", () => ({
  salesService: { updateSalesOrder: (...a: unknown[]) => updateSalesOrder(...a) },
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

/** A confirmed order, as `detail.order_detail` produces one. */
function order(id: string, number: string, title: string, over: Record<string, unknown> = {}) {
  return {
    id, number, title,
    deceased_name: title.toLowerCase(),
    funeral_home: "Hopkins Funeral Home",
    stands_at: "No driver yet",
    state: {
      kind: "steps", stage: "scheduled",
      steps: [
        { id: "confirmed", label: "Confirmed", done: true },
        { id: "delivered", label: "Delivered", done: false },
        { id: "invoiced", label: "Invoiced", done: false },
      ],
    },
    order: [
      {
        label: "Vault", value: "Monticello Burial Vault",
        link: { kind: "product", variant_template_id: "variant-monticello" },
      },
      {
        label: "Cemetery", value: "St. Mary's Cemetery, Skaneateles",
        link: { kind: "cemetery", inert: true, why: "The cemetery pane isn't built yet." },
      },
      { label: "Service", value: "Fri Oct 23 · 11:00 AM church" },
      { label: "Total", value: "$1,705" },
    ],
    billing: { lines: [], total: "$1,705", sentence: "Not invoiced yet." },
    can_undo_confirm: true,
    ...over,
  }
}

/** Two Hopkins orders, both for Smith — the dispatch's own ambiguous case. */
const TWO_PICKS: OrderListSnapshot = {
  kind: "picks",
  layout: "picks",
  title: "Which one?",
  hint: "Which Hopkins order do you mean?",
  orders: [], groups: [], pills: [],
  picks: [
    { n: 1, label: "Smith · SO-2026-0001 · Fri Oct 16", order_id: "o1" },
    { n: 2, label: "Hart · SO-2026-0004 · Wed Oct 28", order_id: "o4" },
  ],
}

beforeEach(() => {
  askOrderList.mockReset()
  getSalesOrderSummary.mockReset()
  resolvePhrase.mockReset()
  getVariant.mockReset()
  listVariants.mockReset()
  updateSalesOrder.mockReset()
  listVariants.mockResolvedValue([])
  updateSalesOrder.mockResolvedValue({})
  getVariant.mockResolvedValue({
    variant_template_id: "variant-monticello", name: "Monticello Burial Vault",
    kind: "burial_vault",
  })
  resolvePhrase.mockResolvedValue({
    phrase: "", normalized: "", resolved: false, candidates: [], discriminators: [],
  })
  getSalesOrderSummary.mockImplementation((id: string) =>
    Promise.resolve(
      id === "o4" ? order("o4", "SO-2026-0004", "Hart") : order("o1", "SO-2026-0001", "Smith"),
    ),
  )
})

afterEach(() => {
  vi.useRealTimers()
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

function bar(): HTMLTextAreaElement {
  return screen.getByTestId("opas-input") as HTMLTextAreaElement
}

async function ask(phrase: string) {
  const input = bar()
  fireEvent.change(input, { target: { value: phrase } })
  await act(async () => {
    fireEvent.keyDown(input, { key: "Enter" })
  })
}

function panes(): HTMLElement[] {
  return Array.from(screen.getByTestId("opas-desk").children) as HTMLElement[]
}

// ───────────────────────────────────────────────────────────────────────────
// 1 — the bar keeps focus
// ───────────────────────────────────────────────────────────────────────────

describe("1 — the bar keeps focus", () => {
  it("after a pane opens from the bar", async () => {
    // ⚠️ THE BAR IS BLURRED MID-FLIGHT, AND THAT IS WHAT MAKES THIS DISCRIMINATING. My
    // first version typed and then asserted focus — which was already on the bar,
    // because typing into it never moved it, and a break test neutering `focusBar`
    // left the assertion GREEN. It was passing for a reason unrelated to what it named
    // (CLAUDE.md §11 shape 6). Blurring after the keypress and before the await makes
    // the assertion about focus RETURNING.
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    const input = bar()
    fireEvent.change(input, { target: { value: "riverside order" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
      input.blur()
      expect(document.activeElement).not.toBe(input)
    })
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(document.activeElement).toBe(bar())
  })

  it("and after a pane opens from a CLICK in another pane", async () => {
    // The other direction, where focus genuinely is elsewhere: a row in the order list.
    askOrderList.mockResolvedValue({
      kind: "question", layout: "flat", title: "Hopkins orders", surface: "pane",
      question: { funeral_home: "Hopkins", title: "Hopkins orders" },
      orders: [{
        id: "o4", number: "SO-2026-0004", deceased_name: "Hart", stage: "scheduled",
        stage_label: "Scheduled", dots_filled: 1, invoiced: false,
        service_date: "2026-10-28",
      }],
      footer: "f",
    })
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-row-o4")).toBeTruthy())
    ;(document.activeElement as HTMLElement).blur()
    fireEvent.click(screen.getByTestId("opas-order-row-o4"))
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(document.activeElement).toBe(bar())
  })

  it("after a pane closes from the bar", async () => {
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    await ask("close")
    await waitFor(() => expect(panes()).toHaveLength(0))
    expect(document.activeElement).toBe(bar())
  })

  it("after a click on a button inside a pane", async () => {
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order-open-vault")).toBeTruthy())
    // move focus away first, so the assertion is about the click and not about where
    // focus already was
    ;(document.activeElement as HTMLElement).blur()
    expect(document.activeElement).not.toBe(bar())
    fireEvent.click(screen.getByTestId("opas-sales-order-open-vault"))
    await waitFor(() => expect(document.activeElement).toBe(bar()))
  })

  it("and after a click on a pane's empty space", async () => {
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    ;(document.activeElement as HTMLElement).blur()
    fireEvent.click(screen.getByTestId("opas-sales-order-rows"))
    await waitFor(() => expect(document.activeElement).toBe(bar()))
  })

  it("⚠️ EXCEPT AN EDITABLE FIELD INSIDE A PANE, which keeps it", async () => {
    // The ruling's one exception: "an editable field inside a pane that the user clicked
    // into keeps focus until Esc or blur."
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    const pane = await screen.findByTestId("opas-sales-order")
    // There is no editable field in this pane today, so one is planted — the rule is
    // about the CLASS of element, and a test that waited for a pane to grow a text box
    // would be a test of nothing until it did.
    const input = document.createElement("input")
    input.setAttribute("data-testid", "planted-field")
    pane.appendChild(input)
    input.focus()
    expect(document.activeElement).toBe(input)
    fireEvent.click(input)
    expect(document.activeElement, "the bar stole a pane field's focus").toBe(input)
  })

  it("⚠️ AND A KEYPRESS WHILE A PANE'S FIELD HAS FOCUS STAYS THERE", async () => {
    // ⚠️ A SECOND GUARD, AND IT HAD NO TEST. The editable-field exception is enforced in
    // TWO places — the pane's `onClick` and the document `keydown` — and the test above
    // only exercises the click. A break test removing the keydown guard left everything
    // green, so this is the half that was uncovered: focus is already in the field and
    // a letter must not be redirected out of it.
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    const pane = await screen.findByTestId("opas-sales-order")
    const field = document.createElement("input")
    pane.appendChild(field)
    field.focus()
    fireEvent.keyDown(field, { key: "z" })
    expect(document.activeElement, "the bar stole the keystroke").toBe(field)
    expect(bar().value, "the character was redirected into the bar").toBe("")
  })

  it("a printable keypress with nothing focused goes to the bar, FIRST CHARACTER AND ALL", async () => {
    // ⚠️ THE FIRST CHARACTER IS THE WHOLE POINT. `focus()` during a keydown does not
    // deliver that keydown to the newly-focused element, so a handler that only focused
    // would swallow the first letter of every sentence typed after a click.
    await mount()
    ;(document.activeElement as HTMLElement).blur()
    fireEvent.keyDown(document.body, { key: "h" })
    expect(document.activeElement).toBe(bar())
    expect(bar().value).toBe("h")
    // and typing continues normally from there
    fireEvent.change(bar(), { target: { value: "hopkins" } })
    expect(bar().value).toBe("hopkins")
  })

  it("⚠️ AND IT LEAVES THE NON-PRINTABLE KEYS ALONE", async () => {
    await mount()
    ;(document.activeElement as HTMLElement).blur()
    for (const key of ["Enter", "Tab", "ArrowLeft", "F5", "Shift"]) {
      fireEvent.keyDown(document.body, { key })
    }
    expect(bar().value).toBe("")
    // ⚠️ THE CONTROL, in the same test: one printable key does land, so "nothing was
    // typed" is about the keys above rather than about a dead listener.
    fireEvent.keyDown(document.body, { key: "x" })
    expect(bar().value).toBe("x")
  })

  it("⚠️ AND A MODIFIER COMBINATION IS SOMEONE ELSE'S", async () => {
    // ⚠️ NOT ⌘K, WHICH IS OPAS'S OWN. My first version of this test pressed ⌘K as an
    // example of "someone else's" key and TUCKED THE OVERLAY — the host binds it in the
    // capture phase to toggle itself (and takes it from the command bar deliberately).
    // The test then failed looking for the bar, which had gone. ⌘A and ⌃A are the ones
    // nobody here claims.
    await mount()
    ;(document.activeElement as HTMLElement).blur()
    fireEvent.keyDown(document.body, { key: "a", metaKey: true })
    fireEvent.keyDown(document.body, { key: "a", ctrlKey: true })
    expect(bar().value).toBe("")
    // ⚠️ THE CONTROL: the overlay is still open and the plain key still lands, so the
    // empty value above is about the modifier rather than about a closed overlay.
    fireEvent.keyDown(document.body, { key: "a" })
    expect(bar().value).toBe("a")
  })
})

// ───────────────────────────────────────────────────────────────────────────
// 2 — one voice above the bar
// ───────────────────────────────────────────────────────────────────────────

describe("2 — one voice, above the bar", () => {
  it("a miss is said in the reply line, and nothing floats", async () => {
    askOrderList.mockResolvedValue({ kind: "unrecognized", hint: "No order for Riverside" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toBe(
      "No order for Riverside",
    ))
    expect(screen.getByTestId("opas-reply").getAttribute("data-reply-kind")).toBe("miss")
    // ⚠️ NOT A PANE. "Nothing Opas says appears as a toast or a floating pane anymore."
    expect(panes()).toHaveLength(0)
  })

  it("the reply sits ABOVE the bar, not inside it", async () => {
    // ⚠️ IT MOVED OUT OF THE GLASS PILL. The old `opas-said` was a child of
    // `opas-command-line`; a question needs room for options underneath, and the pill is
    // the thing they have to sit above.
    askOrderList.mockResolvedValue({ kind: "unrecognized", hint: "No order for Riverside" })
    await mount()
    await ask("riverside order")
    const said = await screen.findByTestId("opas-said")
    expect(screen.getByTestId("opas-command-line").contains(said)).toBe(false)
    const reply = screen.getByTestId("opas-reply")
    expect(reply.style.bottom).not.toBe("")
  })

  it("an acknowledgement fades, and a question does not", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    askOrderList.mockResolvedValue({ kind: "unrecognized", hint: "No order for Riverside" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.queryByTestId("opas-said")).toBeTruthy())
    await act(async () => { vi.advanceTimersByTime(REPLY_FADE_MS + 50) })
    expect(screen.queryByTestId("opas-said"), "a miss did not fade").toBeNull()

    // ⚠️ AND THE QUESTION STAYS, which is the asymmetry: the director is mid-answer and
    // a question that vanished would take its options with it.
    askOrderList.mockResolvedValue(TWO_PICKS)
    await ask("hopkins order")
    await waitFor(() => expect(screen.getByTestId("opas-options")).toBeTruthy())
    await act(async () => { vi.advanceTimersByTime(REPLY_FADE_MS * 3) })
    expect(screen.getByTestId("opas-options"), "the question faded").toBeTruthy()
    expect(screen.getByTestId("opas-said").textContent).toContain("Which Hopkins order")
  })
})

// ───────────────────────────────────────────────────────────────────────────
// 3 — choices sit with the question
// ───────────────────────────────────────────────────────────────────────────

describe("3 — choices sit with the question", () => {
  async function askedWhich() {
    askOrderList.mockResolvedValue(TWO_PICKS)
    await mount()
    await ask("hopkins order")
    await waitFor(() => expect(screen.getByTestId("opas-options")).toBeTruthy())
  }

  it("the options are numbered, above the bar, and show what tells them apart", async () => {
    await askedWhich()
    expect(screen.getByTestId("opas-said").textContent).toBe("Which Hopkins order do you mean?")
    expect(screen.getByTestId("opas-option-1").textContent).toContain("Smith")
    expect(screen.getByTestId("opas-option-1").textContent).toContain("Fri Oct 16")
    expect(screen.getByTestId("opas-option-2").textContent).toContain("Hart")
    expect(screen.getByTestId("opas-option-1").textContent).toMatch(/^1/)
    // ⚠️ AND NOT IN A PANE. The old order-list pane rendered these as
    // `opas-order-picks` and stayed open after the answer.
    expect(screen.queryByTestId("opas-order-picks")).toBeNull()
    expect(panes()).toHaveLength(0)
  })

  it("a click answers, and the list goes", async () => {
    await askedWhich()
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await act(async () => { fireEvent.click(screen.getByTestId("opas-option-2")) })
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.queryByTestId("opas-options"), "the answered list stayed open").toBeNull()
    expect(document.activeElement).toBe(bar())
  })

  it("⌘1 answers", async () => {
    await askedWhich()
    await act(async () => {
      fireEvent.keyDown(document, { key: "1", metaKey: true })
    })
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.queryByTestId("opas-options")).toBeNull()
  })

  it("a bare digit answers, while the bar is empty", async () => {
    await askedWhich()
    await act(async () => {
      fireEvent.keyDown(document, { key: "2" })
    })
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.getByTestId("opas-sales-order").textContent).toContain("Hart")
  })

  it("⚠️ BUT NOT MID-PHRASE — a digit in a half-typed request is text", async () => {
    // ⚠️ AN IN-RANGE DIGIT, AND THE FIRST VERSION OF THIS TEST USED "8". With two
    // options, 8 is out of range and the handler refuses it for that reason alone — so
    // a break test removing the empty-bar guard left the test GREEN. "2" is a real
    // choice, which makes the guard the only thing that can refuse it.
    await askedWhich()
    fireEvent.change(bar(), { target: { value: "monticello" } })
    await act(async () => {
      fireEvent.keyDown(document, { key: "2" })
    })
    // ⚠️ "monticello 2" IS THE START OF A SIZE. Consuming the 2 would answer the wrong
    // question AND eat a character out of the sentence.
    expect(screen.getByTestId("opas-options"), "a mid-phrase digit answered").toBeTruthy()
    // ⚠️ THE CONTROL, in the same test: emptying the bar makes the same key answer, so
    // "it did not answer" is about the guard rather than about a dead handler.
    fireEvent.change(bar(), { target: { value: "" } })
    await act(async () => {
      fireEvent.keyDown(document, { key: "2" })
    })
    await waitFor(() => expect(screen.queryByTestId("opas-options")).toBeNull())
  })

  it("typed words answer when they name one option", async () => {
    await askedWhich()
    await ask("hart")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(screen.getByTestId("opas-sales-order").textContent).toContain("Hart")
    expect(screen.queryByTestId("opas-options")).toBeNull()
    // ⚠️ AND THE ANSWER WAS NOT SENT TO THE SERVER AS A NEW QUESTION. `askOrderList` was
    // called once, for "hopkins order"; "hart" was an ANSWER. Without this the test
    // passes if the phrase falls through and the server happens to return an order —
    // which is a different behaviour that looks the same on screen.
    expect(askOrderList).toHaveBeenCalledTimes(1)
  })

  it("and NARROW when they still do not — the question stays", async () => {
    // "oct" is on both rows.
    await askedWhich()
    await ask("oct")
    await waitFor(() => expect(screen.getByTestId("opas-options")).toBeTruthy())
    expect(screen.getByTestId("opas-option-2"), "the list did not keep both").toBeTruthy()
    expect(screen.getByTestId("opas-said").textContent).toContain("Which Hopkins order")
    // the typed text is cleared, because the next word is another narrowing
    expect(bar().value).toBe("")
  })

  it("⚠️ AND UNRELATED TEXT DROPS THE QUESTION AND IS HANDLED AS A NEW REQUEST", async () => {
    await askedWhich()
    await ask("the catalog")
    await waitFor(() => expect(screen.getByTestId("opas-product-list")).toBeTruthy())
    expect(screen.queryByTestId("opas-options"), "the question survived a new request").toBeNull()
  })

  it("Esc cancels the question and does NOT tuck the session", async () => {
    // ⚠️ THE PROTOTYPE'S OWN ORDER, unchanged by this slice:
    //   if(pending){cancelPick();return}  … tuck()
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    askOrderList.mockResolvedValue(TWO_PICKS)
    await ask("hopkins order")
    await waitFor(() => expect(screen.getByTestId("opas-options")).toBeTruthy())

    await act(async () => { fireEvent.keyDown(document, { key: "Escape" }) })
    await waitFor(() => expect(screen.queryByTestId("opas-options")).toBeNull())
    // the pane is still there and NOT tucked
    expect(panes()[0].getAttribute("data-tucked")).toBe("false")
  })
})

// ───────────────────────────────────────────────────────────────────────────
// 4 — context from the front pane
// ───────────────────────────────────────────────────────────────────────────

describe("4 — context from the front pane", () => {
  async function withOrderInFront() {
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
  }

  it('"the vault" opens the Product Pane for THAT order', async () => {
    await withOrderInFront()
    await ask("the vault")
    await waitFor(() => expect(screen.getByTestId("opas-product-pane")).toBeTruthy())
    expect(screen.getByTestId("opas-said").textContent).toContain("Monticello")
    expect(document.activeElement).toBe(bar())
  })

  it('"when\'s the service" is ANSWERED and opens nothing', async () => {
    await withOrderInFront()
    const before = panes().length
    await ask("when's the service")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toContain(
      "Fri Oct 23",
    ))
    expect(screen.getByTestId("opas-said").textContent).toContain("Hart")
    expect(panes(), "answering opened a pane").toHaveLength(before)
    expect(screen.queryByTestId("opas-options")).toBeNull()
  })

  it('"what\'s the total" and "who\'s it for" too', async () => {
    await withOrderInFront()
    await ask("what's the total")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toContain("$1,705"))
    await ask("who's it for")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toContain(
      "Hopkins Funeral Home",
    ))
  })

  it('"undo confirm" runs the pane\'s own action, with the pane\'s own message', async () => {
    await withOrderInFront()
    await ask("undo confirm")
    await waitFor(() => expect(updateSalesOrder).toHaveBeenCalledWith("o4", { status: "draft" }))
    // ⚠️ THE PANE'S NOTICE, not a second message from the bar. One place owns the
    // wording, the refusal and the re-read.
    await waitFor(() => expect(screen.getByTestId("opas-sales-order-notice").textContent).toContain(
      "SO-2026-0004 is a draft again",
    ))
  })

  it("⚠️ WITH NO ORDER IN FRONT, THE SAME PHRASES ASK", async () => {
    await mount()
    await ask("the vault")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toContain(
      "No order is open",
    ))
    // ⚠️ AND IT DOES NOT REACH THE CATALOG RESOLVER, which is what used to happen —
    // "the vault" matched no product and opened an unfiltered catalog.
    expect(resolvePhrase).not.toHaveBeenCalled()
    expect(panes()).toHaveLength(0)
  })

  it("with an order open but NOT in front, it asks WHICH, with the open orders as options", async () => {
    await withOrderInFront()
    // open the catalog so the order is no longer in front
    await ask("the catalog")
    await waitFor(() => expect(screen.getByTestId("opas-product-list")).toBeTruthy())
    await ask("the total")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toBe("Which order?"))
    expect(screen.getByTestId("opas-option-1").textContent).toContain("Hart")
    // and answering it does the thing
    await act(async () => { fireEvent.click(screen.getByTestId("opas-option-1")) })
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toContain("$1,705"))
  })

  it('⚠️ "how much" WITH A LIST IN FRONT STILL TOTALS THE LIST', async () => {
    // ⚠️ THE PRESERVED BEHAVIOUR, AND THE REASON CONTEXT IS GATED ON THE FRONT PANE.
    // "how much" is the order list's own total question; a context rule that fired
    // regardless of what is in front would have broken it.
    askOrderList.mockResolvedValue({
      kind: "question", layout: "grouped", title: "Open orders", surface: "pane",
      question: { is_default: true, title: "Open orders" },
      groups: [], orders: [], footer: "f",
    })
    await mount()
    await ask("orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-list")).toBeTruthy())
    askOrderList.mockResolvedValue({ kind: "total", hint: "3 orders · $5,115" })
    await ask("how much")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toBe(
      "3 orders · $5,115",
    ))
    expect(askOrderList).toHaveBeenLastCalledWith(
      expect.objectContaining({ phrase: "how much" }),
    )
  })

  it('⚠️ AND WITH AN ORDER PANE OPEN BEHIND THE LIST, "how much" STILL TOTALS THE LIST', async () => {
    // ⚠️ THE CASE THE TEST ABOVE CANNOT COVER, and a break test found the gap. With no
    // order pane open at all, a context rule that ignored the front pane would have
    // nothing to act on and the list would answer anyway — so that test stayed green
    // under the break. Here an order IS open and the LIST is in front, which is the only
    // arrangement that distinguishes "gated on the front pane" from "gated on an order
    // existing".
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())

    askOrderList.mockResolvedValue({
      kind: "question", layout: "grouped", title: "Open orders", surface: "pane",
      question: { is_default: true, title: "Open orders" },
      groups: [], orders: [], footer: "f",
    })
    await ask("orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-list")).toBeTruthy())

    askOrderList.mockResolvedValue({ kind: "total", hint: "3 orders · $5,115" })
    await ask("how much")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toBe(
      "3 orders · $5,115",
    ))
    // ⚠️ AND NOT the order's own $1,705, which is what the order-in-front reading says.
    expect(screen.getByTestId("opas-said").textContent).not.toContain("1,705")
  })
})

// ───────────────────────────────────────────────────────────────────────────
// 5 — capture speaks in the same voice (James, 2026-10-20)
// ───────────────────────────────────────────────────────────────────────────

describe("5 — capture's question is in the reply line and stays while typing", () => {
  /**
   * ⚠️ IT WAS NEVER ON SCREEN BEFORE THIS, and that is the finding rather than the
   * feature. The question was rendered as the bar's textarea `placeholder`, which a
   * browser shows ONLY when the field is empty, while `placeholderFor` returned the
   * question only when the text was NON-empty. Four of its nine return values could
   * not appear at all — the server's `next_question` among them, which is what the
   * 2026-10-15 ruling was written to put on screen.
   */
  async function capturing(next: string) {
    const svc = await import("@/services/opas-capture-service")
    // ⚠️ THE FULL SERVER SHAPE, NOT A HAND-PICKED SUBSET. My first version listed only
    // the keys this test reads and the pane threw `Cannot read properties of undefined
    // (reading 'trim')` — it consumes several more. A fixture narrower than the
    // contract tests the fixture.
    const st = {
      session_id: "s1",
      status: "capturing",
      object_type: "sales_order",
      typed_lines: [],
      full_text: null,
      resolutions: {},
      conflicts: [],
      values: {},
      answered: [],
      missing: ["cemetery"],
      missing_labels: ["Cemetery"],
      next_question: next,
      unanswered_optional: [],
      not_applicable: [],
      indeterminate: [],
      is_complete: false,
      unrecognized: [],
      pending_picks: [],
      vault_resolution: { resolved: false, candidates: [], discriminators: [] },
      surface: {
        id: "capture",
        rows: [
          { row_id: "funeral_home", label: "Funeral Home", state: "done",
            value: "Hopkins Funeral Home", secondary_value: null },
          { row_id: "cemetery", label: "Cemetery", state: "not_mentioned",
            value: null, secondary_value: null },
        ],
      },
    }
    vi.mocked(svc.startCapture).mockResolvedValue(st as never)
    vi.mocked(svc.setCaptureText).mockResolvedValue(st as never)
    vi.mocked(svc.readCapture).mockResolvedValue(st as never)
    await mount()
    fireEvent.change(bar(), { target: { value: "start an order for hopkins" } })
    await act(async () => {
      fireEvent.keyDown(bar(), { key: "Enter" })
    })
    await waitFor(() => expect(screen.getByTestId("capture-pane")).toBeTruthy())
  }

  it("says the server's question above the bar, WITH TEXT IN THE BAR", async () => {
    await capturing("What day is the service?")
    await waitFor(() => expect(screen.getByTestId("opas-said").textContent).toBe(
      "What day is the service?",
    ))
    // ⚠️ THE BAR IS NOT EMPTY, which is the state the old surface could not render in.
    expect(bar().value).not.toBe("")
    // and the question persists — it is a `question`, which never fades
    expect(screen.getByTestId("opas-reply").getAttribute("data-reply-kind")).toBe("question")
  })

  it("and it survives more typing", async () => {
    await capturing("What day is the service?")
    await waitFor(() => expect(screen.getByTestId("opas-said")).toBeTruthy())
    fireEvent.change(bar(), { target: { value: "start an order for hopkins monticello" } })
    await act(async () => { await Promise.resolve() })
    expect(screen.getByTestId("opas-said").textContent).toBe("What day is the service?")
  })

  it("the bar's own placeholder is a PLAIN PROMPT, not the question", async () => {
    await capturing("What day is the service?")
    await waitFor(() => expect(screen.getByTestId("opas-said")).toBeTruthy())
    expect(bar().getAttribute("placeholder")).toBe("Say what the director said")
    expect(bar().getAttribute("placeholder")).not.toContain("service")
  })

  it("⚠️ AND THE QUESTION GOES WHEN THE CAPTURE DOES, without wiping what comes next", async () => {
    await capturing("What day is the service?")
    await waitFor(() => expect(screen.getByTestId("opas-said")).toBeTruthy())
    const pane = screen.getByTestId("capture-pane").closest("[data-testid^='opas-pane-']")!
    await act(async () => {
      fireEvent.click(pane.querySelector("[data-testid^='opas-pane-close-']") as HTMLElement)
    })
    await waitFor(() => expect(screen.queryByTestId("opas-said")).toBeNull())
  })
})

const LIST_ANSWER: OrderListSnapshot = {
  kind: "question", layout: "flat", title: "Hopkins orders", surface: "pane",
  question: { funeral_home: "Hopkins", title: "Hopkins orders" },
  orders: [{
    id: "o4", number: "SO-2026-0004", deceased_name: "Hart", stage: "scheduled",
    stage_label: "Scheduled", dots_filled: 1, invoiced: false,
    service_date: "2026-10-28",
  }],
  footer: "f",
} as unknown as OrderListSnapshot

// ───────────────────────────────────────────────────────────────────────────
// 5 — the decision log's one unreachable fact
// ───────────────────────────────────────────────────────────────────────────

describe("5 — what was in front travels with the phrase", () => {
  /**
   * ⚠️ THE SERVER CANNOT DERIVE THIS, WHICH IS THE WHOLE REASON IT IS SENT. "only
   * hopkins" is a refinement with a list open and a new request in a cold bar. Both
   * reach `/order-list/ask`; the request body is the only thing that distinguishes
   * them, so a decision log without it holds rows with no single right answer — and
   * that log is the evidence the rulebook is supposed to be built from.
   *
   * ⚠️ AND THE VOCABULARY IS THE PANE KIND, NOT A SECOND SET OF NAMES. `surface_for`
   * reads "sales-order" / "catalog" / anything-else; sending a translated label would
   * be two spellings of one concept, free to drift.
   */
  it("a cold bar sends no front at all", async () => {
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    expect(askOrderList).toHaveBeenCalledTimes(1)
    // ⚠️ ABSENT, NOT "bar". The server defaults a missing value, so an older bundle
    // records `bar` rather than refusing the request — and a client that invented the
    // string would be asserting something it had not observed.
    expect(askOrderList.mock.calls[0][0].front).toBeUndefined()
  })

  it("with the order's pane in front it sends sales-order", async () => {
    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await mount()
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order-steps")).toBeTruthy())

    // A second phrase, typed with that pane in front.
    askOrderList.mockResolvedValue({ kind: "unrecognized", hint: "No order for Riverside" })
    await ask("orders this month")
    expect(askOrderList.mock.calls[1][0].front).toBe("sales-order")
  })

  it("⚠️ IT IS THE FRONT PANE, NOT THE FIRST ONE ON THE DESK", async () => {
    /**
     * ⚠️ TWO PANES, AND THE FRONT ONE IS NOT FIRST — which is the only arrangement that
     * can tell the two apart. My first version of this test opened ONE pane and
     * asserted the sequence `[undefined, undefined, "sales-order"]`; a break test
     * replacing the lookup with `opas.panes[0]?.kind` left it GREEN, because with a
     * single pane the first pane IS the front pane and with none both read undefined.
     * It asserted a true thing about an arrangement that could not discriminate.
     *
     * Here the order list opens first and the sales order opens on top of it, so
     * `panes[0]` is "order-list" while the front is "sales-order". Any implementation
     * that reads a position rather than `frontPaneId` now records the wrong surface.
     */
    askOrderList.mockResolvedValue(LIST_ANSWER)
    await mount()
    await ask("hopkins orders")
    await waitFor(() => expect(screen.getByTestId("opas-order-list")).toBeTruthy())

    askOrderList.mockResolvedValue({ kind: "open_order", open_order_id: "o4" })
    await ask("riverside order")
    await waitFor(() => expect(screen.getByTestId("opas-sales-order-steps")).toBeTruthy())

    // ⚠️ THE CONTROL, AND IT ASSERTS THE ARRANGEMENT DIRECTLY RATHER THAN THE KINDS:
    // two panes, and the FRONT one is the second. Without this the test could pass over
    // a desk holding one pane, which is exactly the hole the previous version had.
    const focused = panes().map((p) => p.getAttribute("data-focused"))
    expect(focused).toEqual(["false", "true"])

    askOrderList.mockResolvedValue({ kind: "unrecognized", hint: "No order for Riverside" })
    await ask("orders since june")
    const fronts = askOrderList.mock.calls.map((c) => c[0].front)
    // THE SEQUENCE IS THE ASSERTION — which phrase saw which pane, not how many did.
    expect(fronts).toEqual([undefined, "order-list", "sales-order"])
  })
})

// ───────────────────────────────────────────────────────────────────────────
// 6 — the OS does not mark up what the director types
// ───────────────────────────────────────────────────────────────────────────

describe("6 — spell check is off in the bar", () => {
  /**
   * ⚠️ RULED 2026-10-21 AFTER A SCREENSHOT WAS MISREAD — MINE AS MUCH AS ANYONE'S.
   * James saw a red dotted underline under "hopk monti thursday" and reported it as
   * Opas marking those words not-understood. Measured on production, the engine could
   * not have drawn it: that span came back `captured` for `service_date` with
   * `unrecognized` empty, and the mirror's unrecognized mark is a GREY dotted
   * underline, never red. It was macOS spell check — "hopk" and "monti" are not words
   * and a lowercase "thursday" is flagged too.
   *
   * ⚠️ WHICH MAKES IT WORSE THAN COSMETIC, AND IS WHY IT IS A RULING RATHER THAN A
   * TIDY-UP: the OS was saying "not a word" in almost exactly the visual language Opas
   * uses for "not understood", about an abbreviation Opas had just understood. Two
   * different claims, one underline, and no way for the director to tell them apart.
   *
   * ⚠️ THE PROTOTYPE HAD IT OFF AND WE DID NOT COPY THAT. Measured:
   * `2026-10-01-opas-overlay.html` carries `spellcheck="false"` and
   * `autocomplete="off"`.
   */
  it("the bar carries spellCheck=false and the three keyboard attributes", async () => {
    await mount()
    const input = bar()
    // ⚠️ THE RENDERED ATTRIBUTE, NOT THE JSX PROP. React maps `spellCheck={false}` to
    // the attribute `spellcheck="false"`; asserting the prop I wrote would assert my
    // own source back to me.
    //
    // ⚠️ AND IT IS THE ATTRIBUTE RATHER THAN `input.spellcheck` BECAUSE JSDOM DOES NOT
    // IMPLEMENT THAT PROPERTY — my first version read it and got `undefined`, which is
    // falsy and would have passed a `toBeFalsy()`. An absent property and a disabled
    // spell checker are the same value to a loose assertion, and only one of them is
    // what the browser acts on.
    expect(input.getAttribute("spellcheck")).toBe("false")
    expect(input.getAttribute("autocorrect")).toBe("off")
    expect(input.getAttribute("autocapitalize")).toBe("off")
    expect(input.getAttribute("autocomplete")).toBe("off")
  })

  it("⚠️ AND IT IS STILL OFF IN CAPTURE MODE, which is where the abbreviations go", async () => {
    // The same element serves both modes, but a future split into two inputs would
    // land the attribute on one of them — and capture is the mode where a director
    // types "hopk monti" and the OS has the most to complain about.
    await mount()
    const input = bar()
    // ⚠️ "order for hopk", NOT "order hopk". The forgiving opener needs the tenant's
    // funeral-home names, which this suite does not stub — so the bare form routes to
    // the order list and the pane never opens. `CAPTURE_START` matches "order for"
    // with no vocabulary at all, which is the form that works here.
    fireEvent.change(input, { target: { value: "order for hopk monti thursday" } })
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    const after = bar()
    expect(after.getAttribute("data-entry-mode")).toBe("true")
    expect(after.getAttribute("spellcheck")).toBe("false")
  })
})

// ───────────────────────────────────────────────────────────────────────────
// 7 — a click on a row reaches the row (James's walk, 2026-10-23)
// ───────────────────────────────────────────────────────────────────────────

describe("7 — clicking an order row opens its pane", () => {
  const LIST = {
    kind: "question", layout: "flat", title: "Hopkins orders", surface: "pane",
    question: { funeral_home: "Hopkins", title: "Hopkins orders" },
    orders: [{
      id: "o4", number: "SO-2026-0004", deceased_name: "Hart", stage: "scheduled",
      stage_label: "Scheduled", dots_filled: 1, invoiced: false,
      service_date: "2026-10-28",
    }],
    footer: "f",
  } as unknown as OrderListSnapshot

  /**
   * ⚠️ IT ASSERTS THE POINTER IS NEVER CAPTURED, NOT THAT THE PANE OPENS, AND THAT IS
   * THE WHOLE REASON THIS TEST IS WORTH ANYTHING.
   *
   * James's row click did nothing in Chrome on 2026-10-23. `dragStart`'s guard excluded
   * the TAGS `button,textarea,input,a`; the order row is a `div role="button"` — the only
   * such element in Opas, measured — so pointerdown fell through, `setPointerCapture`
   * captured the pointer on the PANE, and the browser dispatched the `click` to the
   * capturing element instead of the row.
   *
   * ⚠️ AND THE OBVIOUS TEST CANNOT FAIL. jsdom does not implement `setPointerCapture`
   * (hence the optional call in `dragStart`), so no capture happens and the click lands
   * on the row regardless. Measured four ways against the BROKEN code — bare click, full
   * pointerdown/up/click, with a 2px move, and after a refinement — and all four opened
   * the pane. An "assert the pane opens" test is green before and after the fix: it is
   * documentation, not coverage (CLAUDE.md §11).
   *
   * So the capture itself is stubbed and watched. That IS discriminating: with the old
   * tag-only selector the row's pointerdown captures, with the fix it does not.
   */
  async function openListAndWatchCapture() {
    askOrderList.mockResolvedValue(LIST)
    await mount()
    await ask("hopkins orders")
    const row = await waitFor(() => screen.getByTestId("opas-order-row-o4"))
    const captured: number[] = []
    // ⚠️ STUBBED ON THE PROTOTYPE, so every element in the tree has it — the capture
    // happens on `e.currentTarget`, which is the pane, not the row.
    const proto = window.Element.prototype as unknown as Record<string, unknown>
    const had = Object.prototype.hasOwnProperty.call(proto, "setPointerCapture")
    const prev = proto.setPointerCapture
    proto.setPointerCapture = function (id: number) { captured.push(id) }
    const restore = () => {
      if (had) proto.setPointerCapture = prev
      else delete proto.setPointerCapture
    }
    return { row, captured, restore }
  }

  it("⚠️ POINTERDOWN ON A ROW DOES NOT CAPTURE THE POINTER", async () => {
    const { row, captured, restore } = await openListAndWatchCapture()
    try {
      await act(async () => {
        fireEvent.pointerDown(row, { clientX: 120, clientY: 200, button: 0, pointerId: 7 })
      })
      expect(captured).toEqual([])
    } finally {
      restore()
    }
  })

  it("⚠️ THE CONTROL: pointerdown on the pane's own chrome DOES capture", async () => {
    // Without this the test above is satisfied by a stub that is never reached at all —
    // a `dragStart` that returned on its first line, or a pane that stopped handling
    // pointerdown, would also produce an empty list. CLAUDE.md §11: require the control
    // to be NON-ZERO and read it before the result it vouches for.
    const { captured, restore } = await openListAndWatchCapture()
    try {
      const pane = screen.getByTestId("opas-order-list").closest("[data-pane-width]")
      expect(pane).toBeTruthy()
      await act(async () => {
        fireEvent.pointerDown(pane as Element, {
          clientX: 300, clientY: 120, button: 0, pointerId: 9,
        })
      })
      expect(captured).toEqual([9])
    } finally {
      restore()
    }
  })

  it("and the click opens the order's pane, with focus back on the bar", async () => {
    // ⚠️ GREEN BEFORE THE FIX TOO — kept because it is the BEHAVIOUR, and the two tests
    // above are what pin the mechanism. Labelled so nobody reads it as the regression
    // test it cannot be.
    askOrderList.mockResolvedValue(LIST)
    await mount()
    await ask("hopkins orders")
    const row = await waitFor(() => screen.getByTestId("opas-order-row-o4"))
    ;(document.activeElement as HTMLElement).blur()
    await act(async () => {
      fireEvent.pointerDown(row, { clientX: 120, clientY: 200, button: 0, pointerId: 1 })
      fireEvent.pointerUp(row, { clientX: 120, clientY: 200, button: 0, pointerId: 1 })
      fireEvent.click(row, { clientX: 120, clientY: 200, button: 0 })
    })
    await waitFor(() => expect(screen.getByTestId("opas-sales-order")).toBeTruthy())
    expect(document.activeElement).toBe(bar())
  })

  it("⚠️ AND A REFINEMENT DOES NOT CHANGE IT — filtering was not the variable", async () => {
    // James asked whether the refinement mattered. Measured: it does not. The cause is
    // the row's SHAPE, not the list's state, so the same assertion holds after
    // "only hopkins".
    askOrderList.mockResolvedValue(LIST)
    await mount()
    await ask("hopkins orders")
    await waitFor(() => screen.getByTestId("opas-order-row-o4"))
    askOrderList.mockResolvedValue(LIST)
    await ask("only hopkins")
    const row = await waitFor(() => screen.getByTestId("opas-order-row-o4"))
    const proto = window.Element.prototype as unknown as Record<string, unknown>
    const had = Object.prototype.hasOwnProperty.call(proto, "setPointerCapture")
    const prev = proto.setPointerCapture
    const captured: number[] = []
    proto.setPointerCapture = function (id: number) { captured.push(id) }
    try {
      await act(async () => {
        fireEvent.pointerDown(row, { clientX: 120, clientY: 200, button: 0, pointerId: 3 })
      })
      expect(captured).toEqual([])
    } finally {
      if (had) proto.setPointerCapture = prev
      else delete proto.setPointerCapture
    }
  })
})
