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
