/**
 * Opas asks "why?", through the host — the conversation above the bar.
 *
 *   approve  ->  "You changed the vault from Monticello to Continental. Why?"
 *   a reason ->  "Just today, or always?"   (⌘1 / ⌘2 / a click)
 *   Always   ->  a drafted sentence, Enter to keep it or type another
 *   the rule ->  in the rulebook
 *
 * ⚠️ IT DRIVES THE HOST, because the question lives in the BAR and nothing else can see
 * it. `CapturePane` only hands it up; the state machine, the "is this a reason or a new
 * request" decision, and both scope paths are all host code — and a `useCallback` that
 * had dropped `whyAsk` from its dependency array would make every piece work and the
 * feature do nothing.
 *
 * ⚠️ AND TWO TESTS HERE ASSERT THAT IT GOES AWAY. "Never blocks" and "never asks twice"
 * are most of what the dispatch promises, and a question that cannot be dismissed is
 * worse than no question.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const askOrderList = vi.fn()
const getCustomerDetail = vi.fn()
const getCemeteryDetail = vi.fn()
const getSalesOrderSummary = vi.fn()
const startCapture = vi.fn()
const approveCapture = vi.fn()
const answerWhy = vi.fn()
const getRulebook = vi.fn()
const setCaptureText = vi.fn()

vi.mock("@/services/order-list-service", () => ({
  askOrderList: (...a: unknown[]) => askOrderList(...a),
  getCustomerDetail: (...a: unknown[]) => getCustomerDetail(...a),
  getCemeteryDetail: (...a: unknown[]) => getCemeteryDetail(...a),
  getRulebook: (...a: unknown[]) => getRulebook(...a),
  updateRule: vi.fn(),
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
  approveCapture: (...a: unknown[]) => approveCapture(...a),
  answerWhy: (...a: unknown[]) => answerWhy(...a),
  setCaptureText: (...a: unknown[]) => setCaptureText(...a), addLine: vi.fn(), choosePick: vi.fn(), readCapture: vi.fn(),
  completeCapture: vi.fn(), abandonCapture: vi.fn(),
  chooseSwitch: vi.fn(), fetchVocabulary: vi.fn().mockResolvedValue([]),
}))

import { OpasProvider } from "@/contexts/opas-context"
import { OpasHost } from "../OpasHost"

const PROMPT = "You changed the vault from Monticello Burial Vault to Continental Burial Vault. Why?"
const ASK = {
  field: "vault",
  label: "Vault",
  was: "Monticello Burial Vault",
  now: "Continental Burial Vault",
  source: "default",
  prompt: PROMPT,
}

/** A capture state, as the server sends it. */
function state(over: Record<string, unknown> = {}) {
  return {
    session_id: "s1",
    // ⚠️ `review`, AND THE TWO SURFACES ARE MUTUALLY EXCLUSIVE. `capture-rows` renders
    // under `{!reviewing && …}` and `capture-approve` under `{reviewing && …}`
    // (CapturePane.tsx:877 and :1191), so a test cannot wait for both. This walk is
    // about what happens AFTER an approve, so it opens straight into the review the
    // Approve button lives on. Measured against a throwaway diagnostic rather than
    // reasoned about — three fixture guesses failed before this one.
    status: "review",
    object_type: "sales_order",
    full_text: "order for hopkins continental thursday 10am",
    typed_lines: [],
    resolutions: {},
    conflicts: [],
    values: { vault: "Continental Burial Vault" },
    answered: [], missing: [], unanswered_optional: [], not_applicable: [],
    indeterminate: [], is_complete: false, unrecognized: [], pending_picks: [],
    switches: [],
    vault_resolution: { resolved: true, candidates: [], discriminators: [] },
    // ⚠️ AT LEAST ONE ROW, OR THE PANE RENDERS NO `capture-rows` AT ALL. Copied from
    // `capture-live.test.tsx`'s fixture rather than invented: an empty `rows` array is a
    // shape the server does not send once a capture has started, and my first version
    // of this fixture had one — nine tests could not find the pane.
    surface: {
      id: "capture",
      rows: [
        { row_id: "vault", label: "Vault", state: "captured",
          value: "Continental Burial Vault", secondary_value: null },
      ],
    },
    lines: null,
    // ⚠️ THE APPROVE BUTTON ONLY RENDERS WITH THIS, and with no blockers. Measured from
    // `CapturePane.tsx:1301` rather than guessed — `state.approve_effect && blockers
    // .length === 0`. Without it the pane renders and `capture-approve` does not exist.
    approve_effect: "This will create SO-2026-0007.",
    blockers: [],
    ...over,
  }
}

function openOverlay() {
  const out = render(<OpasProvider><OpasHost /></OpasProvider>)
  fireEvent.click(screen.getByTestId("opas-sphere"))
  return out
}

/** Submit what is in the bar. */
async function type(phrase: string) {
  const input = screen.getByTestId("opas-input")
  fireEvent.change(input, { target: { value: phrase } })
  await act(async () => {
    fireEvent.keyDown(input, { key: "Enter" })
  })
}

/**
 * Type into the bar WITHOUT submitting, and let the capture open.
 *
 * ⚠️ A CAPTURE OPENS ON TYPING, NOT ON ENTER — the host watches `text` in an effect.
 * Pressing Enter as well takes the submit path, and my first version of this helper did
 * both: nine tests could not find the pane.
 */
async function typeOnly(phrase: string) {
  const input = screen.getByTestId("opas-input")
  await act(async () => {
    fireEvent.change(input, { target: { value: phrase } })
  })
  await act(async () => {
    await new Promise((r) => setTimeout(r, 20))
  })
}

/** Open a capture and approve it, so the question arrives. */
async function approveWithAChange() {
  openOverlay()
    // ⚠️ "order for", NOT "order hopkins". `CAPTURE_START` needs a verb before "order"
  // or the exact phrase "order for"; the bare form opens a capture only via
  // `startsCaptureWithParty`, which needs the tenant's funeral-home vocabulary — and
  // `fetchVocabulary` is mocked empty here. Measured, not guessed.
  await typeOnly("order for hopkins continental thursday 10am")
  await waitFor(() => expect(screen.getByTestId("capture-approve")).toBeInTheDocument())
  await act(async () => {
    fireEvent.click(screen.getByTestId("capture-approve"))
  })
  await waitFor(() => expect(screen.getByText(PROMPT)).toBeTruthy())
}

beforeEach(() => {
  askOrderList.mockReset()
  answerWhy.mockReset()
  approveCapture.mockReset()
  startCapture.mockReset()
  setCaptureText.mockReset()
  getRulebook.mockReset()
  resolvePhrase.mockReset()
  resolvePhrase.mockImplementation((phrase: string) =>
    Promise.resolve({ phrase, candidates: [], discriminators: [] }),
  )
  startCapture.mockResolvedValue(state())
  setCaptureText.mockResolvedValue(state())
  // ⚠️ THE APPROVE RESPONSE CARRIES THE QUESTION. "once, right after you approve" —
  // this is the only moment the bar is told to ask.
  approveCapture.mockResolvedValue(state({
    sales_order_id: "o1", sales_order_number: "SO-2026-0007", total: "1705.00",
    ask_why: ASK,
  }))
  answerWhy.mockResolvedValue({ stored: true, scope: "today" })
  // ⚠️ THE APPROVE OPENS THE ORDER'S OWN PANE, so this mock is not optional — without a
  // resolved value `SalesOrderPane` throws "Cannot read properties of undefined
  // (reading 'then')" and every test in this file fails with no mention of the thing
  // under test. `vi.mock` omitting a resolution fails at CALL time, not at import.
  getSalesOrderSummary.mockReset()
  getSalesOrderSummary.mockResolvedValue({
    id: "o1", number: "SO-2026-0007", deceased_name: "smith",
    funeral_home: "Hopkins Funeral Home", stands_at: "No driver yet", title: "Smith",
    state: { kind: "steps", stage: "confirmed", steps: [] },
    order: [], billing: { lines: [], total: "$1,705", sentence: "Not invoiced yet." },
    can_undo_confirm: false,
  })
  getRulebook.mockResolvedValue({ rules: [], footer: "Opas doesn’t use these yet", empty: "No rules yet" })
})

describe("the question", () => {
  it("is asked after the approve, in the bar", async () => {
    await approveWithAChange()
    expect(screen.getByText(PROMPT)).toBeTruthy()
  })

  it("is NOT asked when the approve carries no change", async () => {
    // ⚠️ THE CONTROL FOR EVERYTHING ELSE HERE. The server decides there was no change;
    // the bar must then say nothing at all.
    approveCapture.mockResolvedValue(state({
      sales_order_id: "o1", sales_order_number: "SO-2026-0008", total: "1705.00",
    }))
    openOverlay()
    await typeOnly("order for hopkins monticello thursday 10am")
    await waitFor(() => expect(screen.getByTestId("capture-approve")).toBeInTheDocument())
    await act(async () => {
      fireEvent.click(screen.getByTestId("capture-approve"))
    })
    await waitFor(() => expect(approveCapture).toHaveBeenCalled())
    expect(screen.queryByText(PROMPT)).toBeNull()
    expect(answerWhy).not.toHaveBeenCalled()
  })
})

describe("a reason, then its scope", () => {
  it("Just today stores the reason and says so", async () => {
    await approveWithAChange()
    await type("the family asked for it on the phone")
    await waitFor(() => expect(screen.getByText("Just today, or always?")).toBeTruthy())

    await act(async () => {
      fireEvent.click(screen.getByText("Just today"))
    })
    await waitFor(() =>
      expect(answerWhy).toHaveBeenCalledWith("s1", {
        reason: "the family asked for it on the phone",
        scope: "today",
      }),
    )
    await waitFor(() => expect(screen.getByText("Noted for today.")).toBeTruthy())
  })

  it("Always drafts a sentence, and Enter keeps it", async () => {
    await approveWithAChange()
    answerWhy.mockResolvedValueOnce({
      stored: true, scope: "always",
      draft: "Veterans take the Continental rather than the Monticello.",
    })
    await type("they always take the continental for a veteran")
    await waitFor(() => expect(screen.getByText("Just today, or always?")).toBeTruthy())
    await act(async () => {
      fireEvent.click(screen.getByText("Always"))
    })
    await waitFor(() =>
      expect(screen.getByText(/Veterans take the Continental rather than the Monticello/))
        .toBeTruthy(),
    )

    // ⚠️ A BARE ENTER KEEPS IT, which is why the confirm branch sits ABOVE `submit`'s
    // empty-phrase guard — a confirm below that line could never fire.
    answerWhy.mockResolvedValueOnce({ stored: true, scope: "always", rule_id: "r1" })
    const input = screen.getByTestId("opas-input")
    await act(async () => {
      fireEvent.keyDown(input, { key: "Enter" })
    })
    await waitFor(() =>
      expect(answerWhy).toHaveBeenLastCalledWith("s1", {
        reason: "Veterans take the Continental rather than the Monticello.",
        scope: "always",
        rule_text: "Veterans take the Continental rather than the Monticello.",
      }),
    )
    await waitFor(() => expect(screen.getByText(/In the rulebook/)).toBeTruthy())
  })

  it("typing a different sentence replaces the draft", async () => {
    await approveWithAChange()
    answerWhy.mockResolvedValueOnce({ stored: true, scope: "always", draft: "A draft." })
    await type("because veterans")
    await waitFor(() => expect(screen.getByText("Just today, or always?")).toBeTruthy())
    await act(async () => {
      fireEvent.click(screen.getByText("Always"))
    })
    await waitFor(() => expect(screen.getByText(/A draft\./)).toBeTruthy())

    answerWhy.mockResolvedValueOnce({ stored: true, scope: "always", rule_id: "r2" })
    await type("Veterans take the Continental.")
    await waitFor(() =>
      expect(answerWhy).toHaveBeenLastCalledWith("s1", {
        reason: "A draft.",
        scope: "always",
        rule_text: "Veterans take the Continental.",
      }),
    )
  })

  it("⌘2 answers the scope without a click", async () => {
    // ⚠️ "⌘1 Just today / ⌘2 Always (digit or click)". The host's digit handler treats a
    // META-held digit as an answer even with text in the bar, which is what makes this
    // work mid-sentence.
    await approveWithAChange()
    answerWhy.mockResolvedValueOnce({ stored: true, scope: "always", draft: "D." })
    await type("a reason")
    await waitFor(() => expect(screen.getByText("Just today, or always?")).toBeTruthy())
    await act(async () => {
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "2", metaKey: true, bubbles: true }),
      )
    })
    await waitFor(() => expect(answerWhy).toHaveBeenCalledWith("s1", {
      reason: "a reason", scope: "always",
    }))
  })
})

describe("it never blocks", () => {
  it("a phrase that is clearly a new request skips the question and is routed", async () => {
    // ⚠️ "Esc, or typing something that's clearly a new request, skips it silently
    // (logged as skipped)." And "clearly a request" is decided by the routes that
    // already exist, not by a new guess.
    await approveWithAChange()
    askOrderList.mockResolvedValue({ kind: "open_rulebook" })
    await type("rules")
    await waitFor(() => expect(answerWhy).toHaveBeenCalledWith("s1", { scope: "skipped" }))
    // and the phrase did what it says: the rulebook opened
    await waitFor(() => expect(screen.getByTestId("opas-rulebook-title")).toBeTruthy())
    expect(screen.queryByText(PROMPT)).toBeNull()
  })

  it("an order-list question skips it too", async () => {
    await approveWithAChange()
    askOrderList.mockResolvedValue({
      kind: "question", layout: "grouped", title: "Orders", groups: [], totals: null,
    })
    await type("what orders are going out this week")
    await waitFor(() => expect(answerWhy).toHaveBeenCalledWith("s1", { scope: "skipped" }))
  })

  it("prose is a reason, not a request", async () => {
    // The control for the two above: an ordinary sentence must NOT be routed.
    await approveWithAChange()
    await type("the church was not free until eleven")
    await waitFor(() => expect(screen.getByText("Just today, or always?")).toBeTruthy())
    expect(askOrderList).not.toHaveBeenCalled()
    expect(answerWhy).not.toHaveBeenCalled()
  })
})

describe("the rulebook from the bar", () => {
  it('"rules" opens it without a round trip', async () => {
    openOverlay()
    await type("rules")
    await waitFor(() => expect(screen.getByTestId("opas-rulebook-title")).toBeTruthy())
    // ⚠️ THE CLIENT DECIDES. `ask` would also answer `open_rulebook`, but the bar needs
    // the predicate locally to tell a reason from a request, so it short-circuits here
    // exactly as `isOrderListPhrase` does.
    expect(askOrderList).not.toHaveBeenCalled()
    expect(screen.getByTestId("opas-rulebook-footer").textContent)
      .toBe("Opas doesn’t use these yet")
  })

  it("never opens twice", async () => {
    openOverlay()
    await type("rules")
    await waitFor(() => expect(screen.getByTestId("opas-rulebook-title")).toBeTruthy())
    await type("the rulebook")
    await waitFor(() =>
      expect(screen.getAllByTestId("opas-rulebook-title")).toHaveLength(1),
    )
  })
})
