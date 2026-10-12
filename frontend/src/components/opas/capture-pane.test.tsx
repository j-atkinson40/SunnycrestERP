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

import { CAPTURE_SESSION_KEY, OpasProvider } from "@/contexts/opas-context"
import { OpasHost } from "./OpasHost"

vi.mock("@/services/opas-capture-service", () => ({
  startCapture: vi.fn(),
  addLine: vi.fn(),
  choosePick: vi.fn(),
  readCapture: vi.fn(),
  // ⚠️ ADDED WHEN THE PANE MOVED TO WHOLE-TEXT EXTRACTION. A mock that omits a
  // function the component imports does not fail at import — it fails when the
  // component CALLS it, as `undefined is not a function`, mid-effect, which
  // surfaces as the pane rendering nothing. `opas-capture-service.test.ts` is what
  // pins this module's real exports; this double only has to keep up with them.
  setCaptureText: vi.fn(),
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
  addLine,
  choosePick,
  readCapture,
  setCaptureText,
  startCapture,
} from "@/services/opas-capture-service"

/** The real shape, with the five sets and a four-state surface. */
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
  return render(
    <OpasProvider>
      <OpasHost />
    </OpasProvider>,
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
  await user.type(input, `${text}{Enter}`)
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
})

describe("the entrance", () => {
  it("opens the capture pane on a start-an-order phrase and passes the WHOLE line", async () => {
    const user = userEvent.setup()
    openOverlay()

    await type(user, "start an order for Hopkins")

    await waitFor(() => expect(screen.getByTestId("capture-pane")).toBeInTheDocument())
    // ⚠️ THE WHOLE LINE, not a stripped remainder. The prototype feeds the same text it
    // started with (`:568`), which is what captures the funeral home immediately.
    expect(startCapture).toHaveBeenCalledWith("start an order for Hopkins")
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

  it("counts captured and needed in the header", async () => {
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order")

    await waitFor(() =>
      expect(screen.getByTestId("capture-captured-pill")).toHaveTextContent("1"),
    )
    expect(screen.getByTestId("capture-needed-pill")).toHaveTextContent("1")
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
    await user.type(bar, "tent only")
    expect(bar).toHaveValue("tent only")
  })
})

describe("numbered picks", () => {
  it("renders a one-based numbered list and sends the chosen index", async () => {
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
      }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    await waitFor(() => expect(screen.getByTestId("capture-pick-vault")).toBeInTheDocument())
    expect(screen.getByTestId("capture-pick-vault")).toHaveTextContent("2 matches")
    expect(screen.getByTestId("capture-pick-vault")).toHaveTextContent("form")

    await user.click(screen.getByTestId("capture-pick-option-vault-2"))

    // ⚠️ ONE-BASED, matching the prototype's digit keys (`:622`) and the server's
    // validation. Zero-basing here would settle the wrong candidate silently.
    await waitFor(() => expect(choosePick).toHaveBeenCalledWith("sess-1", "vault", 2))
  })

  it("shows the TOWN in a party pick, because two identical labels are not a choice", async () => {
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
      }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    await waitFor(() =>
      expect(screen.getByTestId("capture-pick-cemetery")).toBeInTheDocument(),
    )
    expect(screen.getByTestId("capture-pick-cemetery")).toHaveTextContent("Auburn")
    expect(screen.getByTestId("capture-pick-cemetery")).toHaveTextContent("Skaneateles")
    expect(screen.getByTestId("capture-pick-cemetery")).toHaveTextContent("city")
  })
})

describe("never dropped", () => {
  it("shows unrecognized text", async () => {
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(
      state({ unrecognized: ["oversized"] }) as never,
    )
    openOverlay()
    await type(user, "start an order")

    await waitFor(() =>
      expect(screen.getByTestId("capture-unrecognized")).toHaveTextContent("oversized"),
    )
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

    await waitFor(() =>
      expect(screen.getByTestId("capture-unrecognized")).toHaveTextContent("already"),
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

  it("has NO approve control in the summary, by ruling", async () => {
    const user = userEvent.setup()
    vi.mocked(startCapture).mockResolvedValue(state({ status: "review" }) as never)
    openOverlay()
    await type(user, "start an order")

    await waitFor(() => expect(screen.getByTestId("capture-summary")).toBeInTheDocument())
    // ⚠️ E5: no Approve, and no disabled placeholder either — a greyed button reads as a
    // feature that exists and is temporarily unavailable.
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument()
    expect(screen.getByTestId("capture-no-approve")).toBeInTheDocument()
    expect(screen.queryByTestId("capture-input")).not.toBeInTheDocument()
  })
})

describe("surviving a tuck and a reload", () => {
  it("tuck does NOT unmount the pane, so no re-read is needed", async () => {
    // ⚠️ I ASSERTED THE WRONG MECHANISM FIRST. This test expected `readCapture` on
    // reopen; it failed, and the reason is in `OpasHost.tsx:258-259`: "`tucked` hides
    // without unmounting, so the session survives". Tuck is a CSS state, not a teardown
    // — the prototype's own `.win.tucked`. So tuck-survival needs no round trip, and a
    // test demanding one was testing an implementation I had imagined.
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order for Hopkins")
    await waitFor(() => expect(startCapture).toHaveBeenCalledTimes(1))

    await user.keyboard("{Escape}")
    await user.click(screen.getByTestId("opas-sphere"))

    await waitFor(() => expect(screen.getByTestId("capture-pane")).toBeInTheDocument())
    expect(startCapture).toHaveBeenCalledTimes(1)
    // The pane never unmounted, so it never re-read.
    expect(readCapture).not.toHaveBeenCalled()
  })

  it("stores the session id so a RELOAD can come back to it", async () => {
    // ⚠️ RELOAD IS THE CASE THAT IS GENUINELY LOST WITHOUT HELP. Panes are React state —
    // true of every pane kind — so a reload drops them. Reopening "the catalog" costs a
    // keystroke; losing a half-typed ORDER loses the way back to a row that still exists.
    const user = userEvent.setup()
    openOverlay()
    await type(user, "start an order for Hopkins")

    await waitFor(() =>
      expect(window.sessionStorage.getItem(CAPTURE_SESSION_KEY)).toBe("sess-1"),
    )
  })

  it("re-creates the pane from storage on a fresh mount and RE-READS the session", async () => {
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "sess-1")
    openOverlay()

    await waitFor(() => expect(readCapture).toHaveBeenCalledWith("sess-1"))
    // ⚠️ AND IT DOES NOT START A SECOND SESSION. A restore that called `startCapture`
    // would orphan the order it was restoring.
    expect(startCapture).not.toHaveBeenCalled()
  })

  it("clears a stale stored id instead of resurrecting a ghost pane every reload", async () => {
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "gone")
    vi.mocked(readCapture).mockRejectedValue(new Error("404"))
    openOverlay()

    await waitFor(() => expect(screen.getByTestId("capture-error")).toBeInTheDocument())
    expect(screen.getByTestId("capture-error")).toHaveTextContent("no longer on the server")
    expect(window.sessionStorage.getItem(CAPTURE_SESSION_KEY)).toBeNull()
  })
})
