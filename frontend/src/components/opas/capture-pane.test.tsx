/**
 * The capture pane, driven through the real provider tree.
 *
 * ⚠️ THE REAL `OpasProvider` AND THE REAL `OpasHost`, not a harness. The entrance, the
 * pane registration and the session-id write-back are three separate pieces of wiring,
 * and testing the pane in isolation would exercise none of them — the defect that would
 * survive is "the pane works but nothing opens it".
 *
 * ⚠️ THE MOCKED RESPONSES ARE THE REAL ENDPOINT SHAPES, copied from
 * `session_service.read_state`'s return. A fixture invented here would be the
 * fixtures-modelled-on-the-implementation failure: the two halves would agree with each
 * other and with nothing else. The server's own tests
 * (`test_capture_endpoints.py::test_read_state_returns_all_five_sets_and_the_surface_rows`)
 * pin the keys this file assumes.
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"

import { CAPTURE_SESSION_KEY, OpasProvider } from "@/contexts/opas-context"
import { OpasHost } from "./OpasHost"

vi.mock("@/services/opas-capture-service", () => ({
  startCapture: vi.fn(),
  addLine: vi.fn(),
  choosePick: vi.fn(),
  answerCapture: vi.fn(),
  readCapture: vi.fn(),
  // ⚠️ ADDED WHEN THE PANE MOVED TO WHOLE-TEXT EXTRACTION. A mock that omits a
  // function the component imports does not fail at import — it fails when the
  // component CALLS it, as `undefined is not a function`, mid-effect, which
  // surfaces as the pane rendering nothing. `opas-capture-service.test.ts` is what
  // pins this module's real exports; this double only has to keep up with them.
  setCaptureText: vi.fn(),
  // ⚠️ ADDED WHEN CLOSING OPAS BEGAN ENDING THE CAPTURE AND THE FORM DEFAULT GAINED
  // A SWITCH (both ruled 2026-10-13). Same reasoning as `setCaptureText` above, and
  // this file's own warning was right: the omission does not fail at import, it
  // fails as `undefined is not a function` inside an effect — which the director
  // sees as a pane that does not appear.
  takeSwitch: vi.fn(),
  // ⚠️ ADDED WHEN THE BAR GAINED GHOST COMPLETION. Same reasoning this file already
  // records twice: a mock omitting a function the component imports does not fail at
  // import — it fails when the component CALLS it, inside an effect, as
  // `undefined is not a function`, which surfaces as a pane that renders nothing.
  fetchVocabulary: vi.fn(async () => []),
  abandonCapture: vi.fn(),
  approveCapture: vi.fn(),
  completeCapture: vi.fn(),
}))
vi.mock("@/services/opas-catalog-service", () => ({
  resolvePhrase: vi.fn(async () => ({ candidates: [], discriminators: [] })),
  listVariants: vi.fn(async () => []),
  getVariant: vi.fn(async () => null),
}))
// ⚠️ THE SAME THREE CONTEXT DOUBLES `opas-slice.test.tsx` USES, and they are needed for
// the same reason: `OpasHost` reads admin-ness, the command bar and Focus, none of which
// this file is about. Mounting the real providers would make every test here depend on
// three unrelated trees — and the sphere is admin-only, so without the auth double the
// overlay never opens and all fifteen tests fail identically. They did.
vi.mock("@/contexts/auth-context", () => ({ useAuth: () => ({ isAdmin: true }) }))
vi.mock("@/core/CommandBarProvider", () => ({
  useCommandBar: () => ({ isOpen: false, close: () => {} }),
}))
vi.mock("@/contexts/focus-context", () => ({ useFocus: () => ({ isOpen: false }) }))

import {
  abandonCapture,
  addLine,
  approveCapture,
  completeCapture,
  answerCapture,
  choosePick,
  readCapture,
  setCaptureText,
  startCapture,
} from "@/services/opas-capture-service"

/** The real shape, with the five sets and a four-state surface. */
/**
 * A RESPONSE FROM AN OLDER SERVER MUST STILL RENDER.
 *
 * ⚠️ THIS IS A REGRESSION TEST FOR A REAL BLANK PANE, found 2026-10-13 by running
 * this suite after the switch control shipped. `switches` arrived in r209 and
 * `conflicts` in the gated pass. A browser holding a cached bundle while the server
 * is older — the normal state for the seconds around a deploy, and for any tab not
 * hard-refreshed since — receives a payload with those keys ABSENT. Reading
 * `.length` off an absent key throws during render and React unmounts the tree: the
 * director sees NO PANE, with nothing in the bar to explain it. That symptom has
 * cost three walk rounds already.
 *
 * ⚠️ IT ASSERTS THE ROWS ARE THERE, not that nothing threw. "It didn't crash" is
 * satisfied by a component that renders an empty div, which is the bug.
 */
describe("the pick hint", () => {
  it("tells the office that typing the number PICKS", async () => {
    /**
     * ⚠️ THE COPY SHIPPED WRONG FOR A ROUND BECAUSE NOTHING ASSERTED IT. It read
     * "Typed digits go into the text" — the superseded ruling — while the code did
     * the opposite. A hint that contradicts the behaviour is worse than none, and
     * only reading the pane in a real browser caught it.
     *
     * ⚠️ IT ASSERTS THE OLD SENTENCE IS ABSENT, not just that the new one is present.
     * Both could sit in the pane at once, which is the state that confuses somebody.
     */
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({
        pending_picks: [
          {
            field_id: "vault",
            phrase: "Continental",
            options: [["a", "A"], ["b", "B"]],
            discriminator: "size",
          },
        ],
        // ⚠️ WHAT THE SERVER ACTUALLY SENDS WITH A PENDING PICK. `_guided` turns the
        // first pick into the same pills any other question gets, so a fixture with
        // `pending_picks` and no `pills` describes a response that cannot occur.
        question_field_id: "vault",
        question: "Which one did you mean by “Continental”?",
        question_hint:
          "More than one matches. Pick one, and the rest of what you typed stays put.",
        pills: [{ value: "a", label: "A" }, { value: "b", label: "B" }],
      }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")

    /**
     * ⚠️ THE HINT IS THE SERVER'S NOW, AND THAT IS THE REAL FIX FOR THE DEFECT THIS
     * TEST WAS WRITTEN FOR. The copy shipped wrong because it lived in the client,
     * where nothing related it to the behaviour it described. `PICK_HINT` in
     * `session_service.py` is composed beside the rule it explains, which is the
     * standing arrangement for every other sentence Opas says.
     */
    const hint = await screen.findByTestId("opas-guided-hint")
    expect(hint).toHaveTextContent(/pick one/i)
    // ⚠️ STILL ASSERTING THE SUPERSEDED SENTENCE IS ABSENT, not merely that the new
    // one is present. Both could be on screen at once, which is the state that
    // confuses somebody.
    expect(hint.textContent).not.toMatch(/go into the text/i)
  })
})

describe("a payload missing the newest fields", () => {
  it("renders the rows when switches and conflicts are BOTH absent", async () => {
    const user = userEvent.setup()
    const old = state() as Record<string, unknown>
    delete old.conflicts
    // ⚠️ `switches` IS ALREADY ABSENT — the fixture never carried it, and that is
    // exactly how a pane that crashed on every real response reached a green suite.
    expect("switches" in old).toBe(false)
    vi.mocked(setCaptureText).mockResolvedValue(old as never)
    openOverlay()

    await type(user, "start an order for Hopkins")

    await waitFor(() =>
      expect(screen.getByTestId("capture-rows")).toBeInTheDocument(),
    )
  })
})

function state(over: Record<string, unknown> = {}) {
  return {
    session_id: "sess-1",
    status: "capturing",
    object_type: "sales_order",
    typed_lines: [],
    // ⚠️ `null`, NOT `""`, AND THE DISTINCTION IS THE DEFAULT FOR A REASON. A fresh
    // session has NO whole-text record, which is what the server returns and what
    // makes the pane fall back to the lines. Defaulting to `""` here would have the
    // fixture assert "the director cleared the bar" on every test that does not
    // mention text — and would hide the branch entirely.
    full_text: null,
    resolutions: {},
    conflicts: [],
    values: {},
    answered: [],
    missing: [],
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
        { row_id: "vault", label: "Vault / Product", state: "needed",
          value: null, secondary_value: null },
        { row_id: "cemetery", label: "Cemetery", state: "not_mentioned",
          value: null, secondary_value: null },
        { row_id: "personalization", label: "Personalization",
          state: "not_configured", value: null, secondary_value: null },
      ],
    },
    ...over,
  }
}

function openOverlay() {
  // ⚠️ THE ROUTER IS PART OF THE FIXTURE BECAUSE IT IS PART OF THE APP. `App.tsx`
  // mounts `OpasHost` inside `<BrowserRouter>` (:500-541), and this helper did not —
  // so the fixture was LESS faithful than production, which is the fixtures-modelled-
  // on-the-implementation defect pointing the other way. It surfaced the moment the
  // receipt's order number became a `<Link>` (James, 2026-10-14): every assertion
  // still passed except that one, with `Cannot destructure property 'basename'`.
  //
  // ⚠️ ADDED AFTER CHECKING THE APP, NOT TO MAKE A TEST GREEN. A `<Link>` outside a
  // router throws, so if `OpasHost` had been mounted outside `<BrowserRouter>` the
  // right fix was to drop the link — wrapping the test would have shipped a pane
  // that crashed on every approval.
  return render(
    <MemoryRouter>
      <OpasProvider>
        <OpasHost />
      </OpasProvider>
    </MemoryRouter>,
  )
}

/** Open the overlay and type a line into the command line. */
async function type(user: ReturnType<typeof userEvent.setup>, text: string) {
  // ⚠️ VIA THE SPHERE, and the testid is `opas-input` — not `opas-command-input`, which I
  // invented. The sphere is the entrance the slice ships; Cmd+K also opens the overlay
  // but goes through a capture-phase listener that userEvent's synthetic keyboard does
  // not reliably reach in jsdom.
  await user.click(screen.getByTestId("opas-sphere"))
  const input = await screen.findByTestId("opas-input")
  // ⚠️ NO TRAILING `{Enter}` SINCE 2026-10-14. It was incidental — Enter was a hard
  // no-op in the bar, so appending it cost nothing and documented that. Enter now
  // means Complete, so leaving it here made every test finish its own order and
  // replace its custom fixture with whatever `completeCapture` resolved. Tests about
  // Enter press it themselves.
  await user.type(input, text)
}

beforeEach(() => {
  vi.clearAllMocks()
  // ⚠️ CLEARED BETWEEN TESTS. sessionStorage persists across tests in jsdom, so a stored
  // id from one test would silently restore a pane in the next and the entrance tests
  // would pass for the wrong reason.
  window.sessionStorage.clear()
  vi.mocked(startCapture).mockResolvedValue(state() as never)
  vi.mocked(addLine).mockResolvedValue(state() as never)
  vi.mocked(setCaptureText).mockResolvedValue(state() as never)
  vi.mocked(choosePick).mockResolvedValue(state() as never)
  vi.mocked(readCapture).mockResolvedValue(state() as never)
  // ⚠️ THESE TWO MUST RESOLVE A STATE, AND ENTER IS WHY. The `type()` helper below
  // ends every phrase with `{Enter}` — harmless while Enter was a no-op in the bar,
  // and as of 2026-10-14 Enter means Complete. A bare `vi.fn()` returns `undefined`,
  // the component does `setState(await completeCapture(...))`, and the pane then
  // threw `Cannot read properties of undefined (reading 'status')` on its next
  // effect — sixteen tests red for a mock that did not keep the real contract.
  vi.mocked(completeCapture).mockResolvedValue(state() as never)
  vi.mocked(approveCapture).mockResolvedValue(state() as never)
})

describe("the entrance", () => {
  it("opens the capture pane on a start-an-order phrase and passes the WHOLE line", async () => {
    const user = userEvent.setup()
    openOverlay()

    await type(user, "start an order for Hopkins")

    await waitFor(() => expect(screen.getByTestId("capture-pane")).toBeInTheDocument())
    // ⚠️ THE WHOLE LINE STILL ARRIVES — BY A DIFFERENT MECHANISM SINCE 2026-10-12, and
    // the claim in this test's name is unchanged. It used to assert
    // `startCapture("start an order for Hopkins")`: the phrase rode in as an
    // `openingLine` and was extracted through the LINE model. The pane now opens from
    // typing and the phrase is carried into it as the order's TEXT, so it arrives via
    // `setCaptureText` and `startCapture` takes nothing. One write path instead of
    // two — see the host's opening effect for why.
    // ⚠️ THE FIRST ARGUMENT, NOT THE WHOLE CALL. This read
    // `toHaveBeenCalledWith(undefined)` and went red on 2026-10-24 when `startCapture`
    // gained a second parameter (`prefill`) — the claim was still true and the
    // assertion was about the arity. Positional keeps it about the opening line.
    expect(vi.mocked(startCapture).mock.calls[0][0]).toBeUndefined()
    expect(screen.getByTestId("opas-input")).toHaveValue("start an order for Hopkins")
  })

  it("does NOT open a capture pane for a catalog phrase", async () => {
    const user = userEvent.setup()
    openOverlay()

    await type(user, "the catalog")

    await waitFor(() =>
      expect(screen.queryByTestId("capture-pane")).not.toBeInTheDocument(),
    )
    expect(startCapture).not.toHaveBeenCalled()
  })

  it("starts exactly ONE session for one phrase", async () => {
    // ⚠️ THE STRICTMODE / RE-RENDER GUARD. A second start would orphan the first
    // session — a half-typed order nobody can reach — and nothing would report it.
    const user = userEvent.setup()
    openOverlay()

    await type(user, "new order")

    await waitFor(() => expect(startCapture).toHaveBeenCalledTimes(1))
  })
})

describe("the rows", () => {
  it("renders a row per field with its state, including not_configured", async () => {
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order")

    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())
    expect(screen.getByTestId("capture-row-funeral_home")).toHaveAttribute(
      "data-state", "done",
    )
    expect(screen.getByTestId("capture-row-vault")).toHaveAttribute(
      "data-state", "needed",
    )
    expect(screen.getByTestId("capture-row-cemetery")).toHaveAttribute(
      "data-state", "not_mentioned",
    )
    // ⚠️ THE FOURTH STATE. It is NOT a variant of `needed`: "still needed" means the
    // answer exists and nobody gave it; "not configured" means the licensee's setup is
    // what is missing.
    expect(screen.getByTestId("capture-row-personalization")).toHaveAttribute(
      "data-state", "not_configured",
    )
  })

  it("words each state the way the prototype does", async () => {
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order")

    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())
    expect(screen.getByTestId("capture-row-vault")).toHaveTextContent("Still needed")
    expect(screen.getByTestId("capture-row-cemetery")).toHaveTextContent(
      "Not mentioned yet",
    )
  })

  it("shows a PARTIAL value rather than the state wording, unlike the prototype", async () => {
    // ⚠️ A DELIBERATE DEVIATION, FOUND BY WALKING IT ON DEV. The prototype shows a value
    // only when `done` (`:409`) — right for its ONE-FIELD rows. Our Service row composes
    // location + date + time, and the server returned it `not_mentioned` WITH
    // `value: "2027-03-02 · 10:00"` after a date and time but no location. Printing "Not
    // mentioned yet" over a value the director just gave would make them retype it.
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(
      state({
        surface: {
          id: "capture",
          rows: [{ row_id: "service", label: "Service", state: "not_mentioned",
                   value: "2027-03-02 · 10:00", secondary_value: null }],
        },
      }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    await waitFor(() =>
      expect(screen.getByTestId("capture-row-service")).toHaveTextContent("2027-03-02"),
    )
    expect(screen.getByTestId("capture-row-service")).not.toHaveTextContent(
      "Not mentioned yet",
    )
    // ⚠️ THE STATE STILL DRIVES THE CHROME, which is what says the row is unfinished.
    expect(screen.getByTestId("capture-row-service")).toHaveAttribute(
      "data-state", "not_mentioned",
    )
  })

  it("shows a done row's value", async () => {
    // ⚠️ SEPARATED OUT. This assertion was stranded inside the partial-value test by a
    // mis-placed boundary when I inserted it, and the test then looked for a row the
    // single-row fixture did not have. It belongs with the default fixture.
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order")

    await waitFor(() =>
      expect(screen.getByTestId("capture-row-funeral_home")).toHaveTextContent(
        "Hopkins Funeral Home",
      ),
    )
  })

  it("counts ROWS, not fields — two missing fields on one row is ONE needed", async () => {
    /**
     * ⚠️ THE PILL COUNTED FIELDS AND THE AMBER BELONGS TO ROWS, AND THAT IS WHAT
     * JAMES READ OFF THE SCREEN. "2 needed" with nothing highlighted, because his two
     * missing fields were `service_date` (on the Service row) and `grave_location`
     * (on the Burial row) — and before that, a row only turned `needed` after a done
     * signal, so the pane showed **"0 needed" with nine rows empty**.
     *
     * Ruled 2026-10-14: the pill count always equals the number of amber-able rows.
     * Both now read each row's own `missing_field_ids`, so they cannot disagree.
     *
     * ⚠️ THE CASE THAT DISTINGUISHES THE TWO RULES IS TWO FIELDS ON ONE ROW. A fixture
     * with one missing field per row passes under either, which is why this one puts
     * `service_date` and `service_time` on the same Service row and expects ONE.
     */
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(
      state({
        missing: ["service_date", "service_time"],
        surface: {
          id: "capture",
          rows: [
            { row_id: "funeral_home", label: "Funeral Home", state: "done",
              value: "Hopkins Funeral Home", secondary_value: null,
              missing_field_ids: [] },
            { row_id: "service", label: "Service", state: "partial",
              value: "Church", secondary_value: null,
              missing_field_ids: ["service_date", "service_time"] },
            { row_id: "burial", label: "Burial", state: "not_mentioned",
              value: null, secondary_value: null, missing_field_ids: [] },
          ],
        },
      }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    await waitFor(() =>
      expect(screen.getByTestId("capture-captured-pill")).toHaveTextContent("1"),
    )
    // two missing FIELDS, one amber-able ROW
    expect(screen.getByTestId("capture-needed-pill")).toHaveTextContent("1")
  })

  it("THE PILL COUNT EQUALS THE NUMBER OF AMBER ROWS, in every state", async () => {
    /**
     * ⚠️ THE RULING'S OWN TEST: "test the pill count equals the highlighted rows on
     * every state". Asserted as a property over several shapes rather than one case,
     * because the two numbers come from one list and the thing worth pinning is that
     * they keep coming from one list.
     *
     * ⚠️ THE PILL IS CLICKED TO LIGHT THE ROWS, which is also the ruling: the count
     * has to answer "which ones". Before the click nothing is amber — a half-typed
     * order must not look alarming — so the click is what makes the rows countable.
     */
    const shapes = [
      { rows: [["a", []], ["b", []]], expected: 0 },
      { rows: [["a", ["x"]], ["b", []]], expected: 1 },
      { rows: [["a", ["x", "y"]], ["b", []]], expected: 1 },
      { rows: [["a", ["x"]], ["b", ["y"]]], expected: 2 },
    ] as const

    for (const shape of shapes) {
      const user = userEvent.setup()
      vi.mocked(startCapture).mockResolvedValue(
        state({
          surface: {
            id: "capture",
            rows: shape.rows.map(([id, miss]) => ({
              row_id: id, label: id.toUpperCase(), state: "not_mentioned",
              value: null, secondary_value: null, missing_field_ids: miss,
            })),
          },
        }) as never,
      )
      const view = openOverlay()
      await type(user, "start an order")
      const pill = await screen.findByTestId("capture-needed-pill")
      expect(pill).toHaveTextContent(String(shape.expected))

      // ⚠️ NOTHING IS AMBER UNTIL ASKED. The pill lights its own rows on click.
      expect(document.querySelectorAll('[data-amber="true"]')).toHaveLength(0)
      await user.click(pill)
      expect(document.querySelectorAll('[data-amber="true"]')).toHaveLength(
        shape.expected,
      )
      view.unmount()
    }
  })


  it("shows a follow-up row appearing once the server reports it", async () => {
    // ⚠️ THE "FOLLOW-UPS APPEAR" BEHAVIOUR, and it is the SERVER's doing: before a vault
    // resolves the personalization row is absent entirely (8 rows, measured), and it
    // arrives with the vault. The pane renders what it is given; this asserts it does
    // not filter the new row out.
    const user = userEvent.setup()
    const withFollowUp = state({
      surface: {
        id: "capture",
        rows: [
          ...state().surface.rows,
          { row_id: "legacy_series", label: "Legacy series", state: "not_mentioned",
            value: null, secondary_value: null },
        ],
      },
    })
    // ⚠️ DRIVEN THROUGH THE BAR, NOT A PANE TEXT BOX. The pane has no field of its own
    // — the bar is the only input, by ruling (2026-10-12). This test used to type into
    // `capture-input` and assert `addLine`; both are gone, and the replacement asserts
    // the same CLAIM through the new seam.
    vi.mocked(setCaptureText).mockResolvedValue(withFollowUp as never)
    openOverlay()
    await type(user, "start an order")
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())

    await user.type(screen.getByTestId("opas-input"), "legacy print")

    await waitFor(() =>
      expect(screen.getByTestId("capture-row-legacy_series")).toBeInTheDocument(),
    )
  })

  it("the pane has NO text field of its own — the bar is the only input", async () => {
    // ⚠️ THE RULING, ASSERTED AS AN ABSENCE, AND THE POSITIVE CONTROL IS WHAT MAKES THE
    // ABSENCE MEAN ANYTHING. `queryByTestId(...)` returning null is also what a pane
    // that failed to render returns, so the rows are asserted PRESENT first. Without
    // that, this test passes against a blank pane.
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order")
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())

    // ⚠️ THERE IS NO PANE TEXT BOX IN ANY STATE NOW (the bar is the only input), so
    // this assertion no longer distinguishes review from capturing. Kept because it
    // still holds, and the review-specific claim is the absent Approve above.
    expect(screen.queryByTestId("capture-input")).not.toBeInTheDocument()
    // exactly one text input in the whole overlay, and it is the bar
    const inputs = screen.getAllByRole("textbox")
    expect(inputs).toHaveLength(1)
    expect(inputs[0]).toBe(screen.getByTestId("opas-input"))
  })

  it("the bar becomes the ORDER'S field when an entry pane is in front", async () => {
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order")
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())

    const bar = screen.getByTestId("opas-input")
    // ⚠️ `data-entry-mode` IS THE OBSERVABLE FORM OF "which job is the bar doing". It
    // is derived from the FRONT pane's TYPE (`pane-mode.ts`), not from a flag anyone
    // sets, so there is no state in which the attribute and the behaviour disagree.
    expect(bar).toHaveAttribute("data-entry-mode", "true")
    // ⚠️ CLEARED FIRST SINCE 2026-10-12. The opening phrase is now CARRIED into the
    // pane as the order's text, so the bar legitimately holds it and typing appends.
    // Without the clear this asserted "tent only" against "start an ordertent only"
    // — the harness reporting a real behaviour change, not a problem with it.
    await user.clear(bar)
    await user.type(bar, "tent only")
    expect(bar).toHaveValue("tent only")
  })
})

describe("the ambiguity choices, as pills above the bar", () => {
  /**
   * ⚠️ THESE TWO MOVED OUT OF THE PANE ON 2026-10-27, BY RULING. James: "The ambiguity
   * choice list becomes these same pills." They asserted
   * `capture-pick-option-vault-N` and a "2 matches" sentence inside the pane; both
   * were real behaviour and both are now the pills row's.
   *
   * ⚠️ AND THE CHANGE IS NOT COSMETIC — THE PANE CAN BE TUCKED. A choice list that
   * disappears with the pane takes the only way to answer with it, which is the same
   * reasoning that moved the QUESTION out of the pane on 2026-10-20.
   */
  it("sends the VALUE, not the index, because pills are reranked on every read", async () => {
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(
      state({
        pending_picks: [{
          field_id: "vault",
          phrase: "Bronze Triune",
          options: [["Bronze Triune Burial Vault", "BV-BTRI — Bronze Triune Burial Vault"],
                    ["Bronze Triune Urn Vault", "UV-BTRI — Bronze Triune Urn Vault"]],
          discriminator: "form",
        }],
        question_field_id: "vault",
        question: "Which one did you mean by “Bronze Triune”?",
        pills: [
          { value: "Bronze Triune Burial Vault", label: "BV-BTRI — Bronze Triune Burial Vault" },
          { value: "Bronze Triune Urn Vault", label: "UV-BTRI — Bronze Triune Urn Vault" },
        ],
      }) as never,
    )
    vi.mocked(answerCapture).mockResolvedValue(state() as never)
    openOverlay()
    await type(user, "start an order")

    await waitFor(() =>
      expect(screen.getByTestId("opas-guided-pill-2")).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId("opas-guided-pill-2"))

    // ⚠️ THE VALUE. An index would settle whichever answer happened to be second by
    // the time it arrived — pills are ranked from live order history and recomputed on
    // every read, unlike a pending pick's stored options.
    await waitFor(() =>
      expect(answerCapture).toHaveBeenCalledWith("sess-1", "vault", "Bronze Triune Urn Vault"),
    )
  })

  it("shows the TOWN, because two identical labels are not a choice", async () => {
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(
      state({
        pending_picks: [{
          field_id: "cemetery",
          phrase: "St Mary's",
          options: [["St. Mary's Cemetery", "St. Mary's Cemetery — Auburn"],
                    ["St. Mary's Cemetery", "St. Mary's Cemetery — Skaneateles"]],
          discriminator: "city",
        }],
        question_field_id: "cemetery",
        question: "Which one did you mean by “St Mary's”?",
        pills: [
          { value: "St. Mary's Cemetery", label: "St. Mary's Cemetery — Auburn" },
          { value: "St. Mary's Cemetery", label: "St. Mary's Cemetery — Skaneateles" },
        ],
      }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    // ⚠️ THE TOWN IS IN THE LABEL, NOT IN THE `sub`, AND THAT IS THE SERVER'S CHOICE
    // RATHER THAN AN OVERSIGHT. `CapturePick.options` is `[value, label]` and its own
    // comment says "the label carries the town for a party" — so a pick's pills carry
    // it inside the label, while a RANKED cemetery pill carries the town in `sub`
    // because its label is the bare name. Two shapes, both correct, and this test is
    // the record that the difference is deliberate.
    const row = await screen.findByTestId("opas-guided-pills")
    expect(row).toHaveTextContent("Auburn")
    expect(row).toHaveTextContent("Skaneateles")
  })
})

describe("never dropped", () => {
  it("COUNTS unrecognized text in the header", async () => {
    /**
     * ⚠️ REWRITTEN 2026-10-16. It asserted the "Not understood" BOX, which James
     * ruled away: the words now carry a dotted underline in the bar, where the
     * director is already looking, and a list underneath repeated them in a second
     * place.
     *
     * ⚠️ THE RULE IT GUARDS IS UNCHANGED AND IS WHY THIS WAS REWRITTEN RATHER THAN
     * DELETED. E1's never-dropped guarantee is only worth something if the director
     * can SEE what was not understood. What moved is the surface, not the duty — so
     * the count carries the words in its tooltip and the mirror underlines them.
     */
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(
      state({ unrecognized: ["oversized"] }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    const count = await screen.findByTestId("capture-unrecognized-count")
    expect(count).toHaveTextContent("1")
    expect(count).toHaveTextContent("not understood")
    // the words themselves are still reachable, not merely tallied
    expect(count).toHaveAttribute("title", "oversized")
    // and the box is gone
    expect(screen.queryByTestId("capture-unrecognized")).not.toBeInTheDocument()
  })

  it("shows NO count when nothing is unrecognized", async () => {
    // ⚠️ A PERSISTENT "0 not understood" WOULD BE THE NOISE THE BOX WAS REMOVED FOR.
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(state({ unrecognized: [] }) as never)
    openOverlay()
    await type(user, "start an order")
    await screen.findByTestId("capture-pane")
    expect(
      screen.queryByTestId("capture-unrecognized-count"),
    ).not.toBeInTheDocument()
  })

  it("shows a re-statement as a correction naming the settled field", async () => {
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(
      state({
        unrecognized: ["tent only — cemetery_equipment is already 'Full Equipment'"],
      }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    // ⚠️ A RE-STATEMENT RIDES THE SAME CHANNEL AS UNRECOGNIZED TEXT, so it moved to
    // the same place. The sentence naming the settled field is in the tooltip.
    await waitFor(() =>
      expect(screen.getByTestId("capture-unrecognized-count")).toHaveAttribute(
        "title",
        expect.stringContaining("already"),
      ),
    )
  })

  it("renders nothing when there is nothing unplaced", async () => {
    // ⚠️ THE CONTROL. A panel that always rendered would satisfy both tests above.
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order")

    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())
    expect(screen.queryByTestId("capture-unrecognized")).not.toBeInTheDocument()
  })
})

describe("the done signal and the summary", () => {
  it("sends the done phrase as TEXT and renders the summary when the server advances", async () => {
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(state({ status: "review" }) as never)
    openOverlay()
    await type(user, "start an order")
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())

    // ⚠️ NO `{Enter}`, AND THAT IS THE RULING RATHER THAN AN OMISSION. Enter is a hard
    // no-op while capturing; the done phrase reaches the server because it is IN THE
    // TEXT, which the pane re-reads on a pause. A test that pressed Enter would pass
    // today for the wrong reason — the debounce would have fired anyway.
    //
    // ⚠️ CLEARED FIRST — the opening phrase is carried into the pane since
    // 2026-10-12, so without this the text sent is the phrase plus the done signal.
    await user.clear(screen.getByTestId("opas-input"))
    await user.type(screen.getByTestId("opas-input"), "that's everything")

    // ⚠️ THE SERVER DECIDES. The pane does not test the phrase itself — the done-signal
    // regex lives in `session_service.DONE_SIGNAL`, and a second copy here could
    // disagree with it.
    await waitFor(() =>
      expect(setCaptureText).toHaveBeenCalledWith(
        "sess-1",
        "that's everything",
        expect.any(Number),
      ),
    )
    await waitFor(() => expect(screen.getByTestId("capture-summary")).toBeInTheDocument())
  })

  /** Dispatch Enter at the bar and report whether anything claimed it. */
  function pressEnter(): boolean {
    const e = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
    })
    screen.getByTestId("opas-input").dispatchEvent(e)
    return e.defaultPrevented
  }

  it("ENTER IS A HARD NO-OP in entry mode — the keypress is CLAIMED, not merely ignored", async () => {
    // ⚠️ `defaultPrevented` IS THE ASSERTION BECAUSE NOTHING ELSE DISTINGUISHES.
    //
    // My first version typed "the catalog{Enter}" and asserted no second pane opened
    // and the bar kept its text. It passed with `preventDefault` DELETED — because in
    // entry mode the bar's keystrokes go to `opas.setEntryText`, so the request-text
    // state is empty, and `submit()` returns at `if (phrase === "")` before doing
    // anything. The test was asserting an outcome that was already guaranteed by an
    // unrelated fact, which is a check whose success condition is invariant under the
    // failure it catches (CLAUDE.md §11, shape 7).
    //
    // The ruling says Enter does NOTHING, and "nothing" includes not reaching the
    // browser's default handling inside the form-like layouts this bar sits in. That
    // is `preventDefault`, and it is directly observable.
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order")
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())
    const before = vi.mocked(startCapture).mock.calls.length

    expect(pressEnter()).toBe(true)

    // and nothing happened: no second pane, no new session, text untouched
    expect(
      document.querySelectorAll('[data-testid^="opas-pane-opas-pane-"]'),
    ).toHaveLength(1)
    expect(vi.mocked(startCapture).mock.calls.length).toBe(before)
  })

  it("Enter is NOT claimed with no entry pane in front — the positive control", async () => {
    // ⚠️ WITHOUT THIS, THE TEST ABOVE PASSES AGAINST A BAR THAT SWALLOWS EVERY ENTER
    // ALWAYS — which would break the request line for good and leave the catalog
    // unreachable by keyboard.
    const user = userEvent.setup()
    openOverlay()
    // ⚠️ THE SPHERE FIRST. The command line only renders while the overlay is open, so
    // without this the bar does not exist — and my first version of this control
    // failed with "unable to find opas-input", which is the right failure: a control
    // that cannot find its subject must not report a verdict about it.
    await user.click(screen.getByTestId("opas-sphere"))
    await screen.findByTestId("opas-input")

    expect(pressEnter()).toBe(false)
  })

  it("SHOWS the approve control when nothing blocks it", async () => {
    /**
     * ⚠️ THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-10-13, under ruling E5: no
     * Approve in the summary, "and no disabled placeholder either — a greyed button
     * reads as a feature that exists and is temporarily unavailable." The first half
     * is superseded (Approve is built), and the SECOND HALF STILL GOVERNS — which is
     * why the control is ABSENT when blocked rather than disabled. See the blocked
     * case below.
     */
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({
        status: "review",
        lines: [
          { kind: "vault", description: "Monticello Burial Vault", product_id: "p1",
            unit_price: "1250.00", quantity: "1", line_total: "1250.00" },
          { kind: "equipment", description: "Full Equipment", product_id: "p2",
            unit_price: "300.00", quantity: "1", line_total: "300.00" },
        ],
        total: "1550.00",
        blockers: [],
        can_approve: true,
      }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")

    await waitFor(() => expect(screen.getByTestId("capture-summary")).toBeInTheDocument())
    expect(screen.getByTestId("capture-approve")).toBeInTheDocument()
    // the pane still has no field of its own — the bar is the only input
    expect(screen.queryByTestId("capture-input")).not.toBeInTheDocument()
  })

  it("shows a priced line per billable thing, and the total", async () => {
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({
        status: "review",
        lines: [
          { kind: "vault", description: "Monticello Burial Vault", product_id: "p1",
            unit_price: "1250.00", quantity: "1", line_total: "1250.00" },
          { kind: "equipment", description: "Full Equipment", product_id: "p2",
            unit_price: "300.00", quantity: "1", line_total: "300.00" },
        ],
        total: "1550.00",
        blockers: [],
        can_approve: true,
      }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")

    const items = await screen.findByTestId("capture-lineitems")
    expect(items).toHaveTextContent("Monticello Burial Vault")
    expect(items).toHaveTextContent("$1,250.00")
    expect(items).toHaveTextContent("Full Equipment")
    expect(items).toHaveTextContent("$300.00")
    // ⚠️ THE TOTAL IS THE SERVER'S, FORMATTED — never summed in the browser. Money
    // added up in a float is where cents go missing.
    expect(screen.getByTestId("capture-total")).toHaveTextContent("$1,550.00")
  })

  it("HIDES approve and names every blocker when something is wrong", async () => {
    // ⚠️ ABSENT, NOT DISABLED — the surviving half of ruling E5. And the reasons are
    // on screen, because the office cannot add a product it has not been told about.
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({
        status: "review",
        lines: [],
        total: "0.00",
        blockers: [
          "Veteran Triune Burial Vault has no product on this tenant — the order line would have no price.",
          "Still needed: burial date",
        ],
        can_approve: false,
      }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")

    await waitFor(() => expect(screen.getByTestId("capture-blockers")).toBeInTheDocument())
    expect(screen.queryByTestId("capture-approve")).not.toBeInTheDocument()
    const shown = screen.getAllByTestId("capture-blocker").map((n) => n.textContent)
    expect(shown).toHaveLength(2)
    expect(shown.join(" ")).toContain("Veteran Triune Burial Vault")
    expect(shown.join(" ")).toContain("burial date")
  })

  it("⚠️ WITH AN ORDER ID THE CAPTURE CLOSES — the order's own pane takes over", async () => {
    // ⚠️ RE-POINTED 2026-10-19. It was "shows the order number and total once approved"
    // and asserted `capture-approved` plus a `capture-approved-link` href of
    // `/ar/orders/so-1`. Both are gone on this path, by James's third opening path:
    // "After Approve on the capture Review: the capture closes and the new order's pane
    // opens in its place." The old assertions are preserved in the no-id test below,
    // which is the branch that still shows the footer.
    //
    // ⚠️ IT ASSERTS THE PANE IS GONE *AND* WHY — `onApproved` received the id. Asserting
    // only the absence would pass if the whole overlay had failed to render.
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({
        status: "review", lines: [
          { kind: "vault", description: "Monticello Burial Vault", product_id: "p1",
            unit_price: "1250.00", quantity: "1", line_total: "1250.00" },
        ], total: "1250.00", blockers: [], can_approve: true,
      }) as never,
    )
    vi.mocked(approveCapture).mockResolvedValue(
      state({
        status: "approved", lines: [], total: "1250.00", blockers: [],
        can_approve: false, sales_order_id: "so-1",
        sales_order_number: "SO-2026-0001",
      }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")
    await user.click(await screen.findByTestId("capture-approve"))

    await waitFor(() => expect(screen.queryByTestId("capture-pane")).not.toBeInTheDocument())
    expect(screen.queryByTestId("capture-approved")).not.toBeInTheDocument()
    // The pane the host opened in its place. It reads the order over the network, which
    // this suite does not mock, so its loading state is what proves it mounted.
    await waitFor(() =>
      expect(
        screen.queryByTestId("opas-sales-order-loading")
        ?? screen.queryByTestId("opas-sales-order-failed")
        ?? screen.queryByTestId("opas-sales-order"),
      ).toBeTruthy(),
    )
  })

  it("prints the number as PLAIN TEXT when the server sent no order id", async () => {
    // ⚠️ AN OLDER SERVER DOES NOT SEND `sales_order_id`, and this is the same shape
    // as the blank-pane defect from 2026-10-12: the pane read a key an older server
    // omitted. Here the cost of guessing would be an anchor to
    // `/ar/orders/undefined` — a link that looks live and lands nowhere, which is
    // worse than the text it replaced.
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({
        status: "review", lines: [
          { kind: "vault", description: "Monticello Burial Vault", product_id: "p1",
            unit_price: "1250.00", quantity: "1", line_total: "1250.00" },
        ], total: "1250.00", blockers: [], can_approve: true,
      }) as never,
    )
    vi.mocked(approveCapture).mockResolvedValue(
      state({
        status: "approved", lines: [], total: "1250.00", blockers: [],
        can_approve: false, sales_order_number: "SO-2026-0002",
      }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")
    await user.click(await screen.findByTestId("capture-approve"))

    const done = await screen.findByTestId("capture-approved")
    expect(done).toHaveTextContent("SO-2026-0002")
    expect(done).toHaveTextContent("$1,250.00")
    // ⚠️ AND THERE IS NO ANCHOR AT ALL ANY MORE, not merely none on this branch. The
    // 2026-10-14 "the order number links to the order" ruling is superseded: the link
    // needed an id, and an id now makes the host close this pane before anyone could
    // click it. See the block comment in `CapturePane`'s after-approve section.
    expect(screen.queryByTestId("capture-approved-link")).not.toBeInTheDocument()
  })

  it("shows the server's blockers when approve is REFUSED", async () => {
    // ⚠️ THE SERVER RE-CHECKS INSIDE THE TRANSACTION, so it can refuse for a reason
    // the pane had not seen — a product deleted a second ago. The 409's list is what
    // the office must read, not "something went wrong".
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({
        status: "review", lines: [
          { kind: "vault", description: "Monticello Burial Vault", product_id: "p1",
            unit_price: "1250.00", quantity: "1", line_total: "1250.00" },
        ], total: "1250.00", blockers: [], can_approve: true,
      }) as never,
    )
    vi.mocked(approveCapture).mockRejectedValue({
      response: { data: { detail: { blockers: ["No customer record for Hopkins Funeral Home — add it before approving."] } } },
    })
    openOverlay()
    await type(user, "start an order for Hopkins")
    await user.click(await screen.findByTestId("capture-approve"))

    await waitFor(() =>
      expect(screen.getByTestId("capture-error")).toHaveTextContent(
        /No customer record for Hopkins/i,
      ),
    )
  })

})

describe("surviving a tuck and a reload", () => {
  it("ESCAPE ENDS THE CAPTURE — it does not tuck an order away", async () => {
    /**
     * ⚠️ THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-10-13, and it was right at the
     * time: Escape tucked the pane and the order survived, because tuck is a CSS
     * state and not a teardown. James ruled the behaviour the other way — "closing
     * Opas should clear everything" — so the claim is inverted here rather than
     * deleted, and the mechanism it documented (`tucked` hides without unmounting)
     * is still what INFO panes do. Only ENTRY panes end.
     *
     * ⚠️ IT ASSERTS THREE THINGS BECAUSE CLOSING IS THREE THINGS: the pane is gone,
     * the bar is empty, and the server is told. A close that dropped the pane and
     * left the text would re-extract the old order into the next one.
     */
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order for Hopkins")
    await waitFor(() => expect(screen.getByTestId("capture-pane")).toBeInTheDocument())

    await user.keyboard("{Escape}")
    await user.click(screen.getByTestId("opas-sphere"))

    await waitFor(() =>
      expect(screen.queryByTestId("capture-pane")).not.toBeInTheDocument(),
    )
    expect(screen.getByTestId("opas-input")).toHaveValue("")
    // ⚠️ ABANDONED, NOT DELETED. The row stays for the office to look at later; what
    // ends is this browser's claim on it.
    expect(abandonCapture).toHaveBeenCalledWith("sess-1")
  })

  it("stores NO session id — a reload must not come back to an order", async () => {
    /**
     * ⚠️ SUPERSEDED RULING, 2026-10-13. This test used to require the id be stored so
     * a reload could restore the pane, and the reasoning was that losing a half-typed
     * order loses the way back to a row that still exists. James ruled against it:
     * "no order pane until you start an order". The row does still exist on the
     * server, so nothing is destroyed — what is removed is the pane appearing
     * uninvited, which is what made one of his tabs unable to start a new order at
     * all.
     *
     * ⚠️ IT ASSERTS THE KEY IS ABSENT, not that restore-on-mount is gone. A build
     * that kept writing the key would restore again the moment anyone re-added a
     * mount effect, and this is the cheap guard against that.
     */
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order for Hopkins")
    await waitFor(() => expect(screen.getByTestId("capture-pane")).toBeInTheDocument())

    expect(window.sessionStorage.getItem(CAPTURE_SESSION_KEY)).toBeNull()
  })

  it("IGNORES a stored id left by an older build — no pane, no read", async () => {
    /**
     * ⚠️ THE STORED KEY OUTLIVES THE BUILD THAT WROTE IT. Nothing writes
     * `CAPTURE_SESSION_KEY` any more, but a director's tab can still be carrying one
     * from a deploy that did — James's was, for three walk rounds. So the absence of
     * a writer is not enough; the reader has to be gone too, and that is what this
     * asserts.
     */
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "sess-1")
    openOverlay()
    const user = userEvent.setup()
    await user.click(screen.getByTestId("opas-sphere"))

    await waitFor(() => expect(screen.getByTestId("opas-input")).toBeInTheDocument())
    expect(screen.queryByTestId("capture-pane")).not.toBeInTheDocument()
    // ⚠️ AND IT NEVER ASKED THE SERVER. A read that happened and was then discarded
    // would still be a tab announcing an order nobody opened.
    expect(readCapture).not.toHaveBeenCalled()
  })

  it("OPENING OPAS SHOWS NO CAPTURE PANE, whatever is stored", async () => {
    /**
     * ⚠️ THIS TEST ASSERTED THE DEFECT UNTIL 2026-10-13. It read:
     *
     *     await waitFor(() => expect(screen.getByTestId("capture-error"))...)
     *     expect(...).toHaveTextContent("no longer on the server")
     *
     * — i.e. it required the dead pane to STAY and show an error, which is exactly
     * what made a tab permanently unable to start a new order. A capture pane is an
     * ENTRY pane, so while it exists it is the front pane, which puts the bar in
     * entry mode, which makes the opening effect return before it ever looks at the
     * phrase. James hit this on production in the tab he had walked the day before;
     * `sessionStorage` survives a reload and dies only with the tab, so his hard
     * refreshes never cleared it.
     *
     * ⚠️ IT USES A DEAD ID ON PURPOSE. Under the current ruling no stored id is read
     * at all, so a stale one and a live one must behave identically — and asserting
     * the stale case is the stronger of the two, because that is the state a real
     * tab is in.
     */
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "gone")
    vi.mocked(readCapture).mockRejectedValue(new Error("404"))
    openOverlay()
    const user = userEvent.setup()
    await user.click(screen.getByTestId("opas-sphere"))

    await waitFor(() => expect(screen.getByTestId("opas-input")).toBeInTheDocument())
    expect(
      document.querySelectorAll('[data-testid^="opas-pane-opas-pane-"]'),
    ).toHaveLength(0)
    expect(screen.queryByTestId("capture-error")).not.toBeInTheDocument()
  })
})

describe("finishing an order", () => {
  /**
   * ⚠️ ONE ACTION, THREE ENTRANCES, BY RULING (2026-10-14). The button, ⌘Enter and a
   * trailing typed phrase all call the same thing. James's note is the reason: the
   * only way to finish was to type the right phrase, and "approve" — the phrase most
   * people would reach for — was the one that did nothing until a separate "that's
   * everything" had been typed first.
   */
  function completable(over: Record<string, unknown> = {}) {
    return state({
      missing: ["service_date"],
      missing_labels: ["Service date"],
      surface: {
        id: "capture",
        rows: [
          { row_id: "funeral_home", label: "Funeral Home", state: "done",
            value: "Hopkins Funeral Home", secondary_value: null,
            missing_field_ids: [] },
          { row_id: "service", label: "Service", state: "partial",
            value: "Church", secondary_value: null,
            missing_field_ids: ["service_date"] },
        ],
      },
      ...over,
    })
  }

  it("the Complete order button is ALWAYS visible while capturing", async () => {
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(completable() as never)
    openOverlay()
    await type(user, "start an order for Hopkins")
    expect(await screen.findByTestId("capture-complete")).toBeInTheDocument()
  })

  it("pressing it turns the missing rows amber and NAMES them", async () => {
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(completable() as never)
    vi.mocked(completeCapture).mockResolvedValue(
      completable({ completion_attempt: true }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")

    // ⚠️ NOTHING IS AMBER BEFORE THE PRESS. Colouring a half-typed order's gaps
    // while the director is still speaking would make every order start alarming.
    expect(document.querySelectorAll('[data-amber="true"]')).toHaveLength(0)

    await user.click(screen.getByTestId("capture-complete"))

    await waitFor(() =>
      expect(document.querySelectorAll('[data-amber="true"]')).toHaveLength(1),
    )
    expect(screen.getByTestId("capture-row-service")).toHaveAttribute(
      "data-amber", "true",
    )
    expect(screen.getByTestId("capture-still-need")).toHaveTextContent(
      /still need: service date/i,
    )
  })

  it("an OPTIONAL empty row stays quiet, not amber", async () => {
    // ⚠️ THE DISTINCTION JAMES ASKED FOR. Dates without personalization, the grave
    // location and the contact are all optional; an empty one of those must not look
    // like something outstanding.
    const user = userEvent.setup()
    const withOptional = completable({
      surface: {
        id: "capture",
        rows: [
          { row_id: "service", label: "Service", state: "partial", value: "Church",
            secondary_value: null, missing_field_ids: ["service_date"] },
          { row_id: "burial", label: "Burial", state: "not_mentioned", value: null,
            secondary_value: null, missing_field_ids: [] },
          { row_id: "dates", label: "Dates", state: "not_mentioned", value: null,
            secondary_value: null, missing_field_ids: [] },
        ],
      },
    })
    vi.mocked(setCaptureText).mockResolvedValue(withOptional as never)
    vi.mocked(completeCapture).mockResolvedValue(withOptional as never)
    openOverlay()
    await type(user, "start an order for Hopkins")
    await user.click(screen.getByTestId("capture-complete"))

    await waitFor(() =>
      expect(screen.getByTestId("capture-row-service")).toHaveAttribute(
        "data-amber", "true",
      ),
    )
    expect(screen.getByTestId("capture-row-burial")).not.toHaveAttribute("data-amber")
    expect(screen.getByTestId("capture-row-dates")).not.toHaveAttribute("data-amber")
  })

  it("a complete order goes to the summary with Approve FOCUSED", async () => {
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(completable() as never)
    vi.mocked(completeCapture).mockResolvedValue(
      state({
        status: "review",
        missing: [],
        missing_labels: [],
        lines: [
          { kind: "vault", description: "Monticello Burial Vault", product_id: "p1",
            unit_price: "1250.00", quantity: "1", line_total: "1250.00" },
        ],
        total: "1250.00",
        blockers: [],
        can_approve: true,
      }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")
    await user.click(screen.getByTestId("capture-complete"))

    const approve = await screen.findByTestId("capture-approve")
    // ⚠️ FOCUSED SO ENTER APPROVES, which is the ruling's own wording: "you see the
    // summary and press Enter or Approve".
    expect(approve).toHaveFocus()
  })

  it("Cmd+Enter completes while capturing", async () => {
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(completable() as never)
    vi.mocked(completeCapture).mockResolvedValue(completable() as never)
    openOverlay()
    await type(user, "start an order for Hopkins")
    vi.mocked(completeCapture).mockClear()

    await user.keyboard("{Meta>}{Enter}{/Meta}")

    await waitFor(() => expect(completeCapture).toHaveBeenCalledTimes(1))
  })

  it("Cmd+Enter APPROVES from the summary", async () => {
    // ⚠️ THE SAME CHORD, AND WHICH ACTION DEPENDS ON THE STAGE — the prototype binds
    // it that way, which is what a director already has in their fingers.
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({ status: "review", missing: [], lines: [], total: "0.00",
              blockers: [], can_approve: true }) as never,
    )
    vi.mocked(approveCapture).mockResolvedValue(
      state({ status: "approved", sales_order_number: "SO-2026-0007",
              total: "1250.00" }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")
    await waitFor(() => expect(screen.getByTestId("capture-summary")).toBeInTheDocument())

    await user.keyboard("{Meta>}{Enter}{/Meta}")

    await waitFor(() => expect(approveCapture).toHaveBeenCalledTimes(1))
  })
})

describe("Enter finishes the order", () => {
  /**
   * ⚠️ RULED 2026-10-14, SUPERSEDING "Enter is a hard no-op while capturing". That
   * ruling reserved Enter for "whatever ends an order later"; this is it.
   *
   * ⚠️ THE SAFETY PROPERTY IS THAT COMPLETE NEVER APPROVES FROM CAPTURE. An
   * accidental Enter mid-sentence shows the director their own order; it cannot
   * create one. That is asserted directly below rather than left as reasoning.
   */
  it("Enter in the bar COMPLETES while capturing", async () => {
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order for Hopkins")
    vi.mocked(completeCapture).mockClear()

    await user.keyboard("{Enter}")

    await waitFor(() => expect(completeCapture).toHaveBeenCalledTimes(1))
  })

  it("and NEVER approves — a stray Enter cannot create an order", async () => {
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order for Hopkins")
    vi.mocked(approveCapture).mockClear()

    await user.keyboard("{Enter}")
    await user.keyboard("{Enter}")
    await user.keyboard("{Enter}")

    expect(approveCapture).not.toHaveBeenCalled()
  })

  it("Enter APPROVES from the Review", async () => {
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({ status: "review", missing: [], lines: [], total: "0.00",
              blockers: [], can_approve: true }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")
    await waitFor(() =>
      expect(screen.getByTestId("capture-summary")).toBeInTheDocument(),
    )
    vi.mocked(approveCapture).mockClear()

    await user.keyboard("{Enter}")

    await waitFor(() => expect(approveCapture).toHaveBeenCalledTimes(1))
  })

  it("and a SECOND Enter is not swallowed", async () => {
    // ⚠️ THE REQUEST IS COUNTER-STAMPED FOR THIS REASON. A bare boolean would be
    // compared by value and the repeat press would be a no-op — the same trap
    // `pickRequest` documents.
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order for Hopkins")
    vi.mocked(completeCapture).mockClear()

    await user.keyboard("{Enter}")
    await waitFor(() => expect(completeCapture).toHaveBeenCalledTimes(1))
    await user.keyboard("{Enter}")
    await waitFor(() => expect(completeCapture).toHaveBeenCalledTimes(2))
  })
})

describe("the Review shows everything captured", () => {
  it("renders the deceased name from the SUBJECT slot", async () => {
    /**
     * ⚠️ THE NAME LIVES ONLY IN THE SUBJECT, which is why the Review had none.
     * `deceased_name` is not on any summary ROW — it is the subject, "Smith" over
     * "1948 — 2026" from the prototype — and this render had never read it.
     */
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({
        status: "review", missing: [], blockers: [], can_approve: true,
        total: "1250.00", lines: [],
        surface: {
          id: "summary",
          subject_primary: "Smith",
          subject_secondary: "1948 — 2026",
          rows: [
            { row_id: "funeral_home", label: "Funeral home", state: "done",
              value: "Hopkins Funeral Home", secondary_value: null,
              missing_field_ids: [] },
          ],
        },
      }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")

    const subject = await screen.findByTestId("capture-subject")
    expect(subject).toHaveTextContent("Smith")
    expect(subject).toHaveTextContent("1948 — 2026")
  })
})

describe("the Approve button", () => {
  it("has a READABLE label — dark text on the light pill", async () => {
    /**
     * ⚠️ IT RENDERED AS A BLANK WHITE BLOCK, and the cause was two tokens agreeing:
     * `bg-accent` resolves near-white on this overlay and `text-content-inverse` is
     * also near-white, so the label was white on white. James's screenshot showed an
     * empty box where the primary action was.
     *
     * ⚠️ ASSERTED AS A CONTRAST RELATIONSHIP, not as an exact hex. The claim worth
     * holding is "the text is not the same colour as the background"; pinning the
     * literal would fail the next time the glass is retuned without saying anything
     * about readability.
     */
    const user = userEvent.setup()
    vi.mocked(setCaptureText).mockResolvedValue(
      state({ status: "review", missing: [], blockers: [], can_approve: true,
              total: "1250.00", lines: [] }) as never,
    )
    openOverlay()
    await type(user, "start an order for Hopkins")

    const approve = await screen.findByTestId("capture-approve")
    expect(approve).toHaveTextContent(/approve/i)
    const bg = approve.style.background
    const fg = approve.style.color
    expect(bg).toBeTruthy()
    expect(fg).toBeTruthy()
    expect(fg).not.toBe(bg)
    // the prototype's primary: a near-white pill with near-black text
    expect(fg).toMatch(/#0a0a0a|rgb\(10, 10, 10\)/)
  })
})

describe("why something was just cleared", () => {
  it("says it once, in the pane footer, in the server's words", async () => {
    /**
     * James's dispatch of 2026-10-27, clause 4: "clears what no longer fits (urn after
     * burial clears equipment; a vault without that personalization clears it) and says
     * why in one line in the pane footer."
     *
     * ⚠️ THE SENTENCE IS THE SERVER'S. `clears.py` composes it beside the rule it
     * explains — the arrangement that the pick hint's wrong-for-a-round copy is the
     * argument for.
     *
     * ⚠️ AND IT ARRIVES ON THE ANSWER THAT CAUSED IT, not on a plain read. It is the
     * answer to "what just happened", so a read with no `cleared_note` must not show
     * one — asserted below, because a latched note that survives a reload would explain
     * a change made yesterday.
     */
    const user = userEvent.setup()
    // ⚠️ THE OPENING STATE MUST HAVE A QUESTION WITH ANSWERS, or there is no pill to
    // click and the test fails on the fixture rather than on the behaviour. Found that
    // way: `state()` alone renders no guided surface at all.
    vi.mocked(startCapture).mockResolvedValue(
      state({
        question_field_id: "cemetery_equipment",
        question: "What equipment?",
        pills: [{ value: "full_equipment", label: "Full Equipment" }],
      }) as never,
    )
    vi.mocked(answerCapture).mockResolvedValue(
      state({
        cleared_note: "Full Equipment cleared: an urn vault means a cremation setup.",
        question_field_id: "cemetery_equipment",
        question: "What cremation setup?",
        pills: [{ value: "tent_only", label: "Tent Only" }],
      }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    // ⚠️ THE CONTROL: nothing cleared yet, so no note. Without this the assertion
    // below is satisfied by a note that is always on screen.
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())
    expect(screen.queryByTestId("capture-cleared-note")).toBeNull()

    await waitFor(() =>
      expect(screen.getByTestId("opas-guided-pill-1")).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId("opas-guided-pill-1"))

    const note = await screen.findByTestId("capture-cleared-note")
    expect(note.textContent).toBe(
      "Full Equipment cleared: an urn vault means a cremation setup.",
    )
    // ⚠️ IN THE PANE, NOT BESIDE THE QUESTION. One voice: the same sentence in two
    // places is two things to read and two to keep in step.
    expect(screen.queryByTestId("opas-cleared-note")).toBeNull()
  })
})
