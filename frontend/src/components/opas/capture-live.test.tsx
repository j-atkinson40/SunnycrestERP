/**
 * Live extraction through the real overlay: debounce, stale drops, ⌘1..9, restore.
 *
 * ⚠️ REAL TIMERS, AND THE FAKE-TIMER VERSION OF THIS FILE WAS ABANDONED FOR CAUSE. Two
 * independent things in this stack do not survive `vi.useFakeTimers()`:
 *
 *   `@testing-library/dom`'s `waitFor` only advances a fake clock when it detects
 *   JEST's fake timers (`typeof jest !== "undefined"`), which is false under vitest —
 *   so it polls a clock nobody moves.
 *
 *   `userEvent`'s own inter-event delays wait on the same stalled clock even when
 *   `advanceTimers: vi.advanceTimersByTime` is passed.
 *
 * Measured: all 18 tests failed at exactly 5000 ms, twice, on two different harness
 * designs — once inside `waitFor` and once inside `user.click`. A uniform timeout
 * across every test in a file is a statement about the harness, not the component, and
 * the second attempt (a clock-advancing poller) fixed the half that was not the cause.
 * Real timers cost about 470 ms per test here and remove the entire class.
 *
 * ⚠️ THE RULE THE SEQUENCER ENFORCES IS TESTED IN `capture-sequence.test.ts`, without
 * timers or a DOM. THIS FILE TESTS THE WIRING — that the pane consults it at all, and
 * applies the drop to what the director sees. A sequencer that is correct and never
 * called is the shape this pair exists to separate.
 *
 * ⚠️ `waitFor` IS NOT USED HERE AND CANNOT BE. `@testing-library/dom` only advances a
 * fake clock when it detects JEST's fake timers (`typeof jest !== "undefined"`), which
 * is false under vitest — so `waitFor` polls a clock nobody is moving and every call
 * hangs for the full test timeout. Measured: all 18 tests in this file failed at
 * exactly 5000 ms on the first run, inside the shared helper, which reads as the
 * component being broken and is entirely the harness. `until()` below is the
 * fake-timer equivalent: it advances the clock between attempts.
 */
import { StrictMode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { CAPTURE_SESSION_KEY, OpasProvider } from "@/contexts/opas-context"
import { BAR_WIDTH, OpasHost } from "./OpasHost"
import { EXTRACT_DEBOUNCE_MS } from "./capture-sequence"

vi.mock("@/services/opas-capture-service", () => ({
  startCapture: vi.fn(),
  addLine: vi.fn(),
  choosePick: vi.fn(),
  readCapture: vi.fn(),
  setCaptureText: vi.fn(),
  // ⚠️ A DOUBLE THAT OMITS WHAT THE COMPONENT IMPORTS FAILS AT CALL TIME, NOT IMPORT
  // TIME. Omitting `abandonCapture` here did not fail loudly — it made the close
  // button's handler throw mid-click, so the pane stayed open and the next order
  // could not start. Exactly the production symptom, found only by running this.
  takeSwitch: vi.fn(),
  // ⚠️ ADDED WHEN THE BAR GAINED GHOST COMPLETION. Same reasoning this file already
  // records twice: a mock omitting a function the component imports does not fail at
  // import — it fails when the component CALLS it, inside an effect, as
  // `undefined is not a function`, which surfaces as a pane that renders nothing.
  fetchVocabulary: vi.fn(async () => []),
  abandonCapture: vi.fn(),
  // ⚠️ ADDED 2026-10-27 WITH THE PILLS, and this file's own comment above says why it
  // has to be: a double that omits what the component imports fails at CALL time, not
  // import time — which surfaces as a click that throws mid-handler and a question
  // that never gets answered.
  answerCapture: vi.fn(),
}))
vi.mock("@/services/opas-catalog-service", () => ({
  resolvePhrase: vi.fn(async () => ({ candidates: [], discriminators: [] })),
  listVariants: vi.fn(async () => []),
  getVariant: vi.fn(async () => null),
}))
vi.mock("@/contexts/auth-context", () => ({ useAuth: () => ({ isAdmin: true }) }))
vi.mock("@/core/CommandBarProvider", () => ({
  useCommandBar: () => ({ isOpen: false, close: () => {} }),
}))
vi.mock("@/contexts/focus-context", () => ({ useFocus: () => ({ isOpen: false }) }))

import {
  answerCapture,
  choosePick,
  readCapture,
  setCaptureText,
  startCapture,
} from "@/services/opas-capture-service"

function state(over: Record<string, unknown> = {}) {
  return {
    session_id: "sess-1",
    status: "capturing",
    object_type: "sales_order",
    typed_lines: [],
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
        { row_id: "funeral_home", label: "Funeral Home", state: "not_mentioned",
          value: null, secondary_value: null },
      ],
    },
    ...over,
  }
}

/** A surface with one row carrying a given value, so "what the pane shows" is checkable. */
function withValue(value: string, over: Record<string, unknown> = {}) {
  return state({
    surface: {
      id: "capture",
      rows: [
        { row_id: "funeral_home", label: "Funeral Home", state: "done",
          value, secondary_value: null },
      ],
    },
    ...over,
  })
}

let user: ReturnType<typeof userEvent.setup>

beforeEach(() => {
  vi.clearAllMocks()
  window.sessionStorage.clear()
  user = userEvent.setup()
  vi.mocked(startCapture).mockResolvedValue(state() as never)
  vi.mocked(readCapture).mockResolvedValue(state() as never)
  vi.mocked(setCaptureText).mockResolvedValue(state() as never)
})

/**
 * The open panes, by their shared testid prefix.
 *
 * ⚠️ NEVER HARDCODE `opas-pane-opas-pane-1`. `paneSeq` in `opas-context.tsx` is a
 * MODULE-LEVEL counter that keeps climbing across every test in a file, so a literal
 * id is correct only in the first test that opens a pane. My first version of the
 * positioning tests asserted on pane 1 from test 19 and failed with "unable to find"
 * — which is the lucky outcome. The dangerous one is an ABSENCE assertion against a
 * hardcoded id: `queryByTestId("opas-pane-opas-pane-2")` returning null proves
 * nothing when the ids in play are 21 and 22.
 */
function panes(): HTMLElement[] {
  return Array.from(
    document.querySelectorAll<HTMLElement>('[data-testid^="opas-pane-opas-pane-"]'),
  )
}

/** Real-clock sleep. ⚠️ Used instead of a fake-clock advance — see the docstring. */
function sleep(ms: number): Promise<void> {
  return new Promise((r) => {
    setTimeout(r, ms)
  })
}

/** Open the overlay and get an order pane up. */
async function openOrder() {
  render(
    <OpasProvider>
      <OpasHost />
    </OpasProvider>,
  )
  await user.click(screen.getByTestId("opas-sphere"))
  await user.type(screen.getByTestId("opas-input"), "start an order")
  await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())
  // ⚠️ THE BAR IS CLEARED, AND IT HAS TO BE SINCE 2026-10-12. The pane now opens on
  // the PHRASE with no Enter, and the phrase is carried into the pane as the order's
  // text — so after this helper the bar legitimately holds "start an order", and a
  // test that then typed "tent only" would be sending "start an ordertent only".
  // Two tests in this file failed exactly that way when the opening changed, which
  // is the harness telling the truth about a real behaviour change rather than a
  // problem with it.
  //
  // ⚠️ THE `{Enter}` THAT USED TO BE HERE IS GONE, deliberately. Enter was never what
  // opened the pane in a director's hands — it was what every TEST did, which is why
  // "no pane without Enter" shipped. Leaving it would keep that blind spot in the
  // one helper every test in this file goes through.
  await user.clear(screen.getByTestId("opas-input"))
  return screen.getByTestId("opas-input")
}

/** Push past the debounce and let the promise chain settle. */
async function settle() {
  // ⚠️ A MARGIN OVER THE DEBOUNCE, not exactly the debounce. The timer fires at
  // EXTRACT_DEBOUNCE_MS and the request's promise chain then has to settle; waiting
  // the exact figure is a race that would fail intermittently rather than clearly.
  await sleep(EXTRACT_DEBOUNCE_MS + 120)
}

describe("the debounce", () => {
  it("does NOT extract before the pause elapses", async () => {
    const bar = await openOrder()
    vi.mocked(setCaptureText).mockClear()

    await user.type(bar, "tent only")
    await sleep(EXTRACT_DEBOUNCE_MS - 150)

    expect(setCaptureText).not.toHaveBeenCalled()
  })

  it("extracts ONCE for a run of keystrokes, with the whole text", async () => {
    // ⚠️ ONCE, NOT NINE TIMES. This is the difference between a debounce and a
    // throttle, and it is the whole reason the pane is affordable: nine keystrokes
    // inside the window produce one request carrying the final text.
    const bar = await openOrder()
    vi.mocked(setCaptureText).mockClear()

    await user.type(bar, "tent only")
    await settle()

    expect(setCaptureText).toHaveBeenCalledTimes(1)
    expect(setCaptureText).toHaveBeenCalledWith(
      // ⚠️ A FOURTH ARGUMENT SINCE 2026-10-27 — the field a clicked row focused, so the
      // response composes that question rather than the server's next. It is `null`
      // while nothing is focused, which is the ordinary case and the one asserted here.
      "sess-1", "tent only", expect.any(Number), null,
    )
  })

  it("SENDS AN EMPTY STRING when the bar is cleared", async () => {
    // ⚠️ THE CLEARED BAR IS A REAL EDIT. Skipping the call would leave the rows
    // showing values for words that are no longer on screen — the exact defect
    // whole-text re-extraction exists to remove.
    const bar = await openOrder()
    await user.type(bar, "tent only")
    await settle()
    vi.mocked(setCaptureText).mockClear()

    await user.clear(bar)
    await settle()

    expect(setCaptureText).toHaveBeenCalledWith("sess-1", "", expect.any(Number), null)
  })

  it("sends STRICTLY INCREASING sequence numbers", async () => {
    const bar = await openOrder()
    vi.mocked(setCaptureText).mockClear()

    await user.type(bar, "aa")
    await settle()
    await user.type(bar, "bb")
    await settle()
    await user.type(bar, "cc")
    await settle()

    const seqs = vi.mocked(setCaptureText).mock.calls.map((c) => c[2])
    expect(seqs.length).toBe(3)
    expect(seqs).toEqual([...seqs].sort((a, b) => a - b))
    expect(new Set(seqs).size).toBe(seqs.length)
  })
})

describe("stale responses are dropped", () => {
  it("IGNORES A RESPONSE THAT ARRIVES BEHIND A NEWER ONE", async () => {
    // ⚠️ THE RACE, STAGED RATHER THAN HOPED FOR. Both requests are held; the SECOND
    // is resolved first, then the first. Applying the first would make the pane show
    // an older reading of text the director has already changed, which looks like the
    // extractor failing to see words that are plainly on screen.
    const bar = await openOrder()

    let resolveFirst: (v: unknown) => void = () => {}
    let resolveSecond: (v: unknown) => void = () => {}
    vi.mocked(setCaptureText)
      .mockImplementationOnce(
        () => new Promise((res) => { resolveFirst = res }) as never,
      )
      .mockImplementationOnce(
        () => new Promise((res) => { resolveSecond = res }) as never,
      )

    await user.type(bar, "first")
    await settle()
    await user.type(bar, " second")
    await settle()
    expect(setCaptureText).toHaveBeenCalledTimes(2)

    // the newer one lands first
    resolveSecond(withValue("NEWER"))
    await waitFor(() =>
      expect(screen.getByTestId("capture-row-funeral_home")).toHaveTextContent("NEWER"),
    )

    // then the older one arrives — and must not win
    resolveFirst(withValue("OLDER"))
    await sleep(80)

    expect(screen.getByTestId("capture-row-funeral_home")).toHaveTextContent("NEWER")
    expect(screen.getByTestId("capture-row-funeral_home")).not.toHaveTextContent("OLDER")
  })

  it("applies an in-order response — the positive control for the test above", async () => {
    // ⚠️ WITHOUT THIS, THE DROP TEST PASSES AGAINST A PANE THAT APPLIES NOTHING AT
    // ALL. "the older value is not shown" is also true of a pane whose extraction is
    // broken, so one of the pair has to prove a response can get through.
    const bar = await openOrder()
    vi.mocked(setCaptureText).mockResolvedValue(withValue("APPLIED") as never)

    await user.type(bar, "hopkins")
    await settle()

    await waitFor(() =>
      expect(screen.getByTestId("capture-row-funeral_home")).toHaveTextContent("APPLIED"),
    )
  })

  it("the SERVER'S echoed seq is what is compared, not the client's local guess", async () => {
    // ⚠️ THE PANE READS `next.seq`. If it compared the seq it ISSUED instead, two
    // responses arriving out of order would each be judged against their own number
    // and both would be applied — the sequencer would be present and useless.
    const bar = await openOrder()
    vi.mocked(setCaptureText).mockResolvedValue(
      withValue("FROM SEQ 99", { seq: 99 }) as never,
    )
    await user.type(bar, "a")
    await settle()
    await waitFor(() =>
      expect(screen.getByTestId("capture-row-funeral_home")).toHaveTextContent("FROM SEQ 99"),
    )

    // a later request whose response carries a LOWER seq must be dropped
    vi.mocked(setCaptureText).mockResolvedValue(
      withValue("FROM SEQ 2", { seq: 2 }) as never,
    )
    await user.type(bar, "b")
    await settle()
    await sleep(80)

    expect(screen.getByTestId("capture-row-funeral_home")).toHaveTextContent("FROM SEQ 99")
  })
})

/**
 * ⚠️ RE-POINTED FROM THE PLACEHOLDER TO THE REPLY LINE ON 2026-10-20, BY RULING, AND ALL
 * FOUR WERE GREEN WITHOUT BEING EVIDENCE.
 *
 * They asserted `toHaveAttribute("placeholder", …)` on the bar — with text typed INTO the
 * bar, which the second test's own comment explains was necessary to get past
 * `placeholderFor`'s empty-bar short-circuit. That combination is the defect: a browser
 * renders a textarea's placeholder ONLY when the field is empty, so every one of these
 * assertions read an attribute that was present in the DOM and invisible on screen. jsdom
 * paints nothing, so the attribute check passed.
 *
 * ⚠️ THE CLAIMS ARE UNCHANGED AND ARE STILL WORTH HOLDING — what the bar says while a
 * pick is pending, that it counts the missing SET rather than `needed` rows, that the
 * pill and the voice agree, and that "nothing needed" waits for an empty set. Only the
 * surface moved, and now it is one a director can see.
 */
describe("Opas's voice says what is happening and is never stale", () => {
  it("asks the question while a pick is pending, naming the keys", async () => {
    vi.mocked(startCapture).mockResolvedValue(
      state({
        pending_picks: [{
          field_id: "vault",
          phrase: "Continental",
          options: [["a", "A"], ["b", "B"], ["c", "C"]],
          discriminator: "size",
        }],
      }) as never,
    )
    await openOrder()
    await waitFor(() =>
      expect(screen.getByTestId("opas-said").textContent).toContain("Which one?"),
    )
    expect(screen.getByTestId("opas-said").textContent).toContain("1–3")
  })

  it("counts the MISSING SET, not rows in the `needed` state", async () => {
    // ⚠️ THE DEFECT, SEEN IN A REAL BROWSER ON THE WALK PHRASE. The bar read
    // "Nothing needed — say "that's it"" while EIGHT required fields were
    // unanswered. A row only reaches the `needed` state AFTER a done signal; before
    // that a required-and-unanswered row renders `not_mentioned`. So counting rows
    // in the `needed` state answers "has the director said they are finished", not
    // "is anything outstanding" — and the bar invited them to finish an order that
    // could not be completed.
    //
    // ⚠️ THE FIXTURE IS THE POINT: `missing` is non-empty and NO row is in the
    // `needed` state, which is exactly the state the whole walk happens in. A
    // fixture with `needed` rows would pass under either implementation.
    vi.mocked(startCapture).mockResolvedValue(
      state({
        missing: ["vault", "deceased_name", "cemetery"],
        surface: {
          id: "capture",
          rows: [
            { row_id: "funeral_home", label: "Funeral Home", state: "done",
              value: "Hopkins Funeral Home", secondary_value: null },
            { row_id: "vault", label: "Vault / Product", state: "not_mentioned",
              value: null, secondary_value: null },
          ],
        },
      }) as never,
    )
    // ⚠️ TYPED AND NOT CLEARED, AND THIS COMMENT IS THE EVIDENCE THAT THE OLD SURFACE
    // WAS WRONG. It read: "`placeholderFor` short-circuits to 'Say what the director
    // said' on an EMPTY bar, before it ever reaches the missing count — so
    // `openOrder()`, which clears, makes this unmeasurable." True, and the conclusion
    // drawn from it was to type into the bar — which is the one state where a browser
    // hides the placeholder entirely. The short-circuit is gone and the voice is its
    // own element now, so the typing is no longer load-bearing; it is kept because a
    // half-typed order is the realistic state.
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await user.type(screen.getByTestId("opas-input"), "order for hopkins")
    await waitFor(() =>
      expect(screen.getByTestId("capture-rows")).toBeInTheDocument(),
    )

    await waitFor(() =>
      expect(screen.getByTestId("opas-said").textContent).toContain("3 still needed"),
    )
    expect(screen.getByTestId("opas-said").textContent).not.toContain("Nothing needed")
  })

  it("THE PILL AND THE BAR AGREE — one counts rows, the other NAMES them", async () => {
    /**
     * ⚠️ TESTED TOGETHER BY RULING, because they are two readouts of one fact and
     * only one of them was ever fixed. On 2026-10-13 the bar said "8 still needed"
     * while the chip said "0 needed" with nine rows empty.
     *
     * ⚠️ AND THE AGREEMENT IS NOW STRUCTURAL RATHER THAN NUMERIC. Ruled 2026-10-14:
     * the pill counts amber-able ROWS (two missing fields can share one) and the bar
     * NAMES the missing fields. Two numbers for one fact is what let them drift; one
     * number and one sentence cannot contradict each other, and both read the same
     * server-side missing set.
     */
    vi.mocked(startCapture).mockResolvedValue(
      state({
        missing: ["service_date", "service_time", "vault"],
        missing_labels: ["Service date", "Service time", "Vault"],
        surface: {
          id: "capture",
          rows: [
            { row_id: "funeral_home", label: "Funeral Home", state: "done",
              value: "Hopkins Funeral Home", secondary_value: null,
              missing_field_ids: [] },
            // ⚠️ TWO MISSING FIELDS ON ONE ROW, which is the case that separates
            // counting rows from counting fields.
            { row_id: "service", label: "Service", state: "partial",
              value: "Church", secondary_value: null,
              missing_field_ids: ["service_date", "service_time"] },
            { row_id: "vault", label: "Vault / Product", state: "not_mentioned",
              value: null, secondary_value: null, missing_field_ids: ["vault"] },
          ],
        },
      }) as never,
    )
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await user.type(screen.getByTestId("opas-input"), "order for hopkins")
    await waitFor(() =>
      expect(screen.getByTestId("capture-rows")).toBeInTheDocument(),
    )

    // three missing FIELDS across two amber-able ROWS
    expect(screen.getByTestId("capture-needed-pill")).toHaveTextContent("2")
    // and the bar names them rather than printing a third number
    expect(screen.getByTestId("opas-said").textContent).toContain("Still need:")
    expect(screen.getByTestId("opas-said").textContent).toContain("service date")
  })


  it("says nothing is needed only when the missing set is EMPTY", async () => {
    // ⚠️ THE POSITIVE CONTROL. Without it the test above passes against a bar that
    // never says "Nothing needed" at all, which would be a different bug.
    vi.mocked(startCapture).mockResolvedValue(state({ missing: [] }) as never)
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await user.type(screen.getByTestId("opas-input"), "order for hopkins")
    await waitFor(() =>
      expect(screen.getByTestId("capture-rows")).toBeInTheDocument(),
    )

    await waitFor(() =>
      expect(screen.getByTestId("opas-said").textContent).toContain("Nothing needed"),
    )
  })

  it("STOPS saying 'reading' once the response lands, including a DROPPED one", async () => {
    // ⚠️ A DROPPED RESPONSE STILL CLEARS THE IN-FLIGHT FLAG. Gating that on `accept`
    // would leave "Reading what you typed…" on screen forever after one out-of-order
    // delivery — a message outliving its cause, which is the one thing the
    // placeholder ruling forbade and the 2026-10-20 reply-line ruling still does.
    const bar = await openOrder()
    vi.mocked(setCaptureText).mockResolvedValue(
      withValue("x", { seq: 1 }) as never,
    )
    await user.type(bar, "aa")
    await settle()
    // a response carrying an older seq — dropped
    vi.mocked(setCaptureText).mockResolvedValue(
      withValue("y", { seq: 1 }) as never,
    )
    await user.type(bar, "bb")
    await settle()
    await sleep(80)

    expect(screen.getByTestId("opas-said").textContent).not.toContain("Reading")
  })
})

describe("⌘1..9 settles a pick", () => {
  const PICK = {
    field_id: "vault",
    phrase: "Continental",
    options: [["a", "A"], ["b", "B"], ["c", "C"]],
    discriminator: "size",
  }

  /** ⚠️ WHAT THE SERVER SENDS ALONGSIDE A PENDING PICK, AS OF 2026-10-27. `_guided`
   *  turns the first pending pick into the SAME pills any other question gets —
   *  "The ambiguity choice list becomes these same pills" (James) — so a fixture with
   *  `pending_picks` and no `pills` describes a response the server cannot produce.
   *
   *  ⚠️ AND THE OPTIONS ARE NOT RE-ORDERED. A pick's options are the candidates the
   *  extractor found for a phrase the director typed; ranking them by what this home
   *  usually orders would reorder an answer to "which of these two did you mean". */
  const PICK_STATE = {
    pending_picks: [PICK],
    question_field_id: "vault",
    question: "Which one did you mean by “Continental”?",
    question_hint:
      "More than one matches. Pick one, and the rest of what you typed stays put.",
    pills: PICK.options.map(([value, label]) => ({ value, label })),
  }

  it("shows ⌥ AND THE NUMBER on each pill, because the shortcut needs it visible", async () => {
    /**
     * ⚠️ REWRITTEN 2026-10-27 WHEN THE CHOICE LIST MOVED. It asserted
     * `capture-pick-number-vault-N` inside the pane; the options are now pills above
     * the bar, by ruling ("The ambiguity choice list becomes these same pills"), and
     * the pane can be tucked — a choice list that disappears with it takes the only
     * way to answer with it.
     *
     * ⚠️ AND THE KEY IS ⌥, NOT A BARE NUMBER. James, 2026-10-27: "Chrome keeps ⌘1–8
     * for switching tabs, so ⌘ would only ever work in a desktop app." The label has
     * to name the chord that actually works, in the one place a director reads to
     * learn it.
     */
    vi.mocked(startCapture).mockResolvedValue(state(PICK_STATE) as never)
    await openOrder()
    await waitFor(() =>
      expect(screen.getByTestId("opas-guided-pill-1")).toBeInTheDocument(),
    )
    for (const n of [1, 2, 3]) {
      expect(screen.getByTestId(`opas-guided-pill-key-${n}`)).toHaveTextContent(`⌥${n}`)
    }
    // the server's hint, carried through rather than re-worded by the client
    expect(screen.getByTestId("opas-guided-hint")).toHaveTextContent(
      "the rest of what you typed stays put",
    )
  })

  it("⌘2 chooses the SECOND option, one-based", async () => {
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    vi.mocked(choosePick).mockResolvedValue(state() as never)
    await openOrder()

    await user.keyboard("{Meta>}2{/Meta}")

    await waitFor(() => expect(choosePick).toHaveBeenCalledWith("sess-1", "vault", 2))
  })

  /** Dispatch ⌘<digit> and report whether anything claimed it. */
  function pressMetaDigit(digit: string): boolean {
    const e = new KeyboardEvent("keydown", {
      key: digit,
      metaKey: true,
      bubbles: true,
      cancelable: true,
    })
    document.dispatchEvent(e)
    return e.defaultPrevented
  }

  it("CLAIMS ⌘2 while a pick is pending — the positive control for the next test", async () => {
    // ⚠️ THIS PAIR EXISTS BECAUSE "choosePick was not called" CANNOT TELL "the keys are
    // not bound" FROM "the keys are bound and crashed". A break test removing the
    // pick guard produced no named red for exactly that reason — the handler threw on
    // `picks[0].options` and the absence assertion still held. `defaultPrevented`
    // distinguishes them: only an attached, working listener claims the event.
    vi.mocked(startCapture).mockResolvedValue(state(PICK_STATE) as never)
    vi.mocked(choosePick).mockResolvedValue(state() as never)
    await openOrder()

    // ⚠️ WAIT FOR THE PICK TO BE ON SCREEN BEFORE PRESSING, AND THIS WAS A REAL FLAKE
    // RATHER THAN CAUTION. The ⌘ listener is attached by an effect whose dependency
    // is the pick list, which reaches the host through the pane's status callback —
    // pane render, parent setState, parent render, effect. `openOrder` only waits for
    // the ROWS, so under full-suite load the keypress arrived before the listener
    // existed and this failed `expected false to be true`. It passed in isolation
    // and in the Opas-only run, and failed once in 4613; a timing assumption that
    // holds on a quiet machine is the shape that fails in CI.
    //
    // ⚠️ THE PICK NUMBER IS THE RIGHT THING TO WAIT FOR, not an arbitrary delay: it
    // renders from the same `pending_picks` the listener's effect depends on, so its
    // presence is evidence about the listener rather than about the clock.
    await waitFor(() =>
      expect(screen.getByTestId("opas-guided-pill-2")).toBeInTheDocument(),
    )

    expect(pressMetaDigit("2")).toBe(true)
  })

  it("DOES NOT CLAIM ⌘2 when no pick is pending — the keys are not bound at other times", async () => {
    await openOrder()

    expect(pressMetaDigit("2")).toBe(false)
    await sleep(80)
    expect(choosePick).not.toHaveBeenCalled()
  })

  it("does not claim a digit PAST the option count, so the key stays free", async () => {
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    await openOrder()

    expect(pressMetaDigit("7")).toBe(false)
    expect(choosePick).not.toHaveBeenCalled()
  })

  it("IGNORES a number past the option count rather than clamping it", async () => {
    // ⚠️ CLAMPING WOULD SETTLE THE QUESTION WITH AN ANSWER NOBODY CHOSE. ⌘7 against a
    // 3-option question is a mis-press, and the right response to a mis-press is
    // nothing.
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    await openOrder()

    await user.keyboard("{Meta>}7{/Meta}")
    await sleep(80)

    expect(choosePick).not.toHaveBeenCalled()
  })

  it("A PLAIN NUMBER PICKS, and the number LEAVES the text", async () => {
    /**
     * ⚠️ THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-10-13, and quoted the ruling it
     * was built on: "a bare 3 is text the director may be typing — a grave depth, a
     * vault size, a time — so stealing it would make numbers untypable for as long
     * as a question is open." James superseded that: pressing 1 to choose from a
     * numbered list is what a person expects. The old reasoning was not wrong, which
     * is why the replacement is NARROW — the five conditions live in
     * `pick-digit.ts` and are tested exhaustively in `pick-digit.test.ts`. The two
     * tests below this one are the cases that reasoning was protecting, and they
     * still pass.
     *
     * ⚠️ IT ASSERTS THE NUMBER IS GONE FROM THE BAR, not just that the pick fired.
     * A version that selected the option and left the digit in place would send
     * "monticello 1" to the next extraction, where the 1 reads as a size.
     */
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    const bar = await openOrder()

    await user.type(bar, "monticello 1")
    await settle()

    expect(choosePick).toHaveBeenCalledWith("sess-1", PICK.field_id, 1)
    expect(bar).toHaveValue("monticello")
  })

  it("A NUMBER THAT IS NOT AN OPTION STAYS IN THE TEXT", async () => {
    // ⚠️ THE CASE THE OLD RULING EXISTED TO PROTECT. A 2-option pick is showing and
    // the director types a vault size; it must survive untouched.
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    const bar = await openOrder()

    await user.type(bar, "depth 34")
    await settle()

    expect(choosePick).not.toHaveBeenCalled()
    expect(bar).toHaveValue("depth 34")
    expect(setCaptureText).toHaveBeenCalledWith(
      "sess-1", "depth 34", expect.any(Number), null,
    )
  })

  it("A NUMBER AFTER A PLACE WORD STAYS IN THE TEXT", async () => {
    // ⚠️ "lot 2" IS A GRAVE LOCATION, and 2 is in range for this pick. Range alone
    // would have eaten it; the preceding word is what saves it.
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    const bar = await openOrder()

    await user.type(bar, "lot 2")
    await settle()

    expect(choosePick).not.toHaveBeenCalled()
    expect(bar).toHaveValue("lot 2")
  })

  it("a CLICK settles the same pick — both routes, per the ruling", async () => {
    /**
     * ⚠️ IT GOES THROUGH `answerCapture` NOW, NOT `choosePick`, AND THE DIFFERENCE IS
     * THE VALUE RATHER THAN THE INDEX. The options are pills, and pills are recomputed
     * from live order history on every read — an index into a list the next response
     * may have reordered would settle whichever answer happened to be third.
     *
     * ⚠️ THE SERVER WRITE IS THE SAME WRITE. `choose` stores `options[index-1][0]` into
     * `resolutions`; `answer` stores the value directly. Two handles, one resolution —
     * which is why ⌘1..9 can keep using `choosePick` while the pills use this.
     */
    vi.mocked(startCapture).mockResolvedValue(state(PICK_STATE) as never)
    vi.mocked(answerCapture).mockResolvedValue(state() as never)
    await openOrder()

    await waitFor(() =>
      expect(screen.getByTestId("opas-guided-pill-3")).toBeInTheDocument(),
    )
    await user.click(screen.getByTestId("opas-guided-pill-3"))

    await waitFor(() => expect(answerCapture).toHaveBeenCalledWith("sess-1", "vault", "c"))
  })
})

describe("under StrictMode, as the app actually mounts", () => {
  /**
   * ⚠️ THIS BLOCK EXISTS BECAUSE 147 GREEN TESTS MISSED A STUCK PANE. Driving real
   * Chrome over CDP showed the pane opening from typing and then sitting on
   * "Starting the order…" forever, with `POST /capture/sessions` returning 200 in the
   * network log. Cause: `main.tsx` wraps the app in `<StrictMode>`, which in
   * development runs effect -> cleanup -> effect, and `CapturePane`'s mount effect
   * assigned `mounted.current = false` in its cleanup without setting it back to
   * `true` in the body. After the double-invoke the ref was stuck in the blocking
   * position, so the resolved start call returned before `setState`.
   *
   * ⚠️ TESTING LIBRARY DOES NOT RENDER IN STRICTMODE, so no test in this file could
   * double-invoke anything. The whole suite passed. That is the gap, and these tests
   * close it by rendering the way `main.tsx` does.
   *
   * ⚠️ IT IS A DEVELOPMENT-ONLY DEFECT AND THAT WAS MEASURED, NOT ASSUMED. With the
   * fix reverted, a PRODUCTION build served by `vite preview` and driven by the same
   * real browser rendered the rows correctly — React only double-invokes effects in
   * development. So it never reached James on production; the "no pane" he reported
   * was the Enter-only path, which is a different fix.
   */
  async function typeOnlyStrict(phrase: string) {
    render(
      <StrictMode>
        <OpasProvider>
          <OpasHost />
        </OpasProvider>
      </StrictMode>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await user.type(screen.getByTestId("opas-input"), phrase)
  }

  it("THE SESSION STARTS — the pane does not sit on \"Starting the order…\"", async () => {
    vi.mocked(setCaptureText).mockResolvedValue(withValue("Hopkins Funeral Home") as never)
    await typeOnlyStrict("Order for hopkins")

    // ⚠️ THE ROWS ARE THE ASSERTION. `capture-rows` renders only once `state` is
    // non-null, which is exactly what the double-invoked effect prevented.
    await waitFor(() =>
      expect(screen.getByTestId("capture-rows")).toBeInTheDocument(),
    )
    expect(screen.queryByTestId("capture-loading")).not.toBeInTheDocument()
  })

  it("starts exactly ONE session despite the double-invoked effect", async () => {
    // ⚠️ THE OTHER HALF. The `started` ref exists so StrictMode's second mount does
    // not open a second session and orphan the first — a half-typed order nobody can
    // reach. Fixing the `mounted` ref must not cost that.
    await typeOnlyStrict("Order for hopkins")
    await waitFor(() =>
      expect(screen.getByTestId("capture-rows")).toBeInTheDocument(),
    )
    expect(vi.mocked(startCapture).mock.calls.length).toBe(1)
  })

  it("still extracts the carried text under StrictMode", async () => {
    await typeOnlyStrict("Order for hopkins")
    await waitFor(() =>
      expect(screen.getByTestId("capture-rows")).toBeInTheDocument(),
    )
    await settle()
    expect(setCaptureText).toHaveBeenCalledWith(
      "sess-1", "Order for hopkins", expect.any(Number), null,
    )
  })
})

describe("an order pane opens from TYPING, with no Enter", () => {
  /**
   * ⚠️ THE DEFECT JAMES HIT ON PRODUCTION, 2026-10-12 13:54 ET. He typed
   * "order for hopkins" in the bar and waited. No pane, no error. `openPane` for a
   * capture pane was reachable from exactly two places — the reload-restore effect
   * and `submit()` — and `submit()` ran only inside `if (e.key === "Enter")`. There
   * was no path from typing to a pane, and his own walk instruction said to type it
   * WITHOUT Enter.
   *
   * ⚠️ WHY NO TEST CAUGHT IT. Every frontend test pressed Enter. The helper in
   * `capture-pane.test.tsx` is `user.type(input, `${text}{Enter}`)` — Enter is
   * APPENDED to every phrase it is ever given — and `openOrder()` in this file sends
   * an explicit `{Enter}`. The backend's `test_the_whole_sentence_James_walks` calls
   * `session_service` directly and never touches the bar at all. So the one thing
   * the walk instruction asked for was the one thing nothing exercised.
   */

  /** ⚠️ TYPES AND DOES NOT PRESS ENTER. That is the entire point of this block, so
   *  it deliberately does not reuse `openOrder()`, which presses it. */
  async function typeOnly(phrase: string) {
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await user.type(screen.getByTestId("opas-input"), phrase)
  }

  it.each([
    "order for hopkins",
    // ⚠️ CAPITAL O — THE EXACT STRING FROM THE 14:28 WALK NOTE. The lowercase form
    // was already covered and the capitalised one was not; `CAPTURE_START` is tested
    // against `phrase.toLowerCase()`, so both must reach the same place, and "both
    // must" is not the same as "both were tried".
    "Order for hopkins",
  ])("opens a pane on %j — NO ENTER, waiting past the debounce", async (phrase) => {
    await typeOnly(phrase)

    await waitFor(() => expect(panes()).toHaveLength(1))
    await settle()
    await waitFor(() =>
      expect(screen.getByTestId("capture-rows")).toBeInTheDocument(),
    )
  })

  it("MOVES THE TYPED TEXT INTO THE PANE, so the words are not lost", async () => {
    // ⚠️ WITHOUT THIS THE DIRECTOR WATCHES THEIR WORDS VANISH at the moment the pane
    // appears — which would read as a worse bug than no pane at all.
    await typeOnly("order for hopkins")

    await waitFor(() =>
      expect(screen.getByTestId("opas-input")).toHaveValue("order for hopkins"),
    )
    expect(screen.getByTestId("opas-input")).toHaveAttribute("data-entry-mode", "true")
  })

  it("the opened pane EXTRACTS the carried text, so rows fill in", async () => {
    vi.mocked(setCaptureText).mockResolvedValue(withValue("Hopkins Funeral Home") as never)
    await typeOnly("order for hopkins")
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())

    await settle()

    expect(setCaptureText).toHaveBeenCalledWith(
      "sess-1", "order for hopkins", expect.any(Number), null,
    )
  })

  it("does NOT send an openingLine — one write path, not two", async () => {
    // ⚠️ `startCapture(undefined)`. Passing the phrase would extract it through
    // `add_line` (FIRST_WINS, the line model) and the pane's own re-extraction would
    // then replace that reading through the text model (LAST_WINS). One of the two
    // would always be redundant, and `typed_lines` would carry a row the text model
    // does not own.
    await typeOnly("order for hopkins")
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())

    // ⚠️ THE FIRST ARGUMENT, NOT THE WHOLE CALL. This read
    // `toHaveBeenCalledWith(undefined)` and went red on 2026-10-24 when `startCapture`
    // gained a second parameter (`prefill`) — the claim was still true and the
    // assertion was about the arity. Positional keeps it about the opening line.
    expect(vi.mocked(startCapture).mock.calls[0][0]).toBeUndefined()
  })

  it("opens ONCE for a phrase typed continuously, not once per keystroke", async () => {
    // ⚠️ THE MATCH FIRES ON "order for" AND EVERY LATER KEYSTROKE STILL MATCHES. A
    // guard that only checked the regex would open a pane per character from that
    // point on.
    await typeOnly("order for hopkins, mary smith, tent only")

    await waitFor(() => expect(panes()).toHaveLength(1))
    await settle()
    expect(panes()).toHaveLength(1)
  })

  it("opens a SECOND order after the bar is cleared — the guard re-arms", async () => {
    // ⚠️ WITHOUT RE-ARMING, one order per session would be the limit and the second
    // "order for ..." would silently do nothing — the same symptom James reported,
    // reintroduced one step along.
    await typeOnly("order for hopkins")
    await waitFor(() => expect(panes()).toHaveLength(1))

    // close it, which clears that pane's text, then type a fresh order
    await user.click(
      screen.getByTestId(`opas-pane-close-${panes()[0].getAttribute("data-testid")!.replace("opas-pane-", "")}`),
    )
    await waitFor(() => expect(panes()).toHaveLength(0))
    await user.type(screen.getByTestId("opas-input"), "order for riverside")

    await waitFor(() => expect(panes()).toHaveLength(1))
  })

  it("does NOT open a pane for a phrase that is not an order", async () => {
    // ⚠️ THE POSITIVE CONTROL. A host that opened an entry pane on ANY typing would
    // satisfy every test above, and would make the catalog unreachable.
    await typeOnly("the catalog")

    await settle()
    expect(panes()).toHaveLength(0)
    expect(screen.getByTestId("opas-input")).toHaveAttribute("data-entry-mode", "false")
  })

  it("does NOT open while the bar is empty", async () => {
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await settle()
    expect(panes()).toHaveLength(0)
  })
})

describe("a combination the vault forbids is shown, not swallowed", () => {
  const CONFLICT = {
    field_id: "personalization",
    value: "nameplate_and_lifes_reflections",
    permitted: ["nameplate_only"],
    message:
      "personalization='nameplate_and_lifes_reflections' is not permitted on this " +
      "vault; permitted: ['nameplate_only'] (plus 'none')",
  }

  it("renders the conflict with what IS available", async () => {
    // ⚠️ THIS IS THE DEFECT THAT RETURNED HTTP 500 FROM THE LIVE PANE. The server
    // now reports it instead of raising; a client that ignored the list would make
    // the fix invisible — the pane would simply show nothing where the director's
    // words went.
    vi.mocked(startCapture).mockResolvedValue(
      state({ conflicts: [CONFLICT] }) as never,
    )
    await openOrder()

    expect(screen.getByTestId("capture-conflicts")).toBeInTheDocument()
    expect(screen.getByTestId("capture-conflict-personalization")).toHaveTextContent(
      "nameplate_only",
    )
  })

  it("does NOT file it under 'not understood'", async () => {
    // ⚠️ THE DISTINCTION, ASSERTED. Both phrases were read correctly; the pairing is
    // what the vault does not offer. Showing it as unreadable text would send the
    // director back to retype words the extractor got right.
    vi.mocked(startCapture).mockResolvedValue(
      state({ conflicts: [CONFLICT] }) as never,
    )
    await openOrder()

    expect(screen.queryByTestId("capture-unrecognized")).not.toBeInTheDocument()
  })

  it("renders nothing when there is no conflict — the positive control", async () => {
    await openOrder()
    expect(screen.queryByTestId("capture-conflicts")).not.toBeInTheDocument()
  })
})

describe("an entry pane grows from the bar", () => {
  it("is anchored to the BAR'S CORNER, not cascaded from the top", async () => {
    // ⚠️ THE BAR IS A PILL AT right:24 / bottom:24. An entry pane sits directly above
    // it at right:24 / bottom:96, so it comes out of the thing the director is typing
    // into. An info pane cascades from top:72 — asserted in the sibling test below,
    // because "it is at the bottom" is only meaningful against something that is not.
    await openOrder()
    expect(panes()).toHaveLength(1)
    const pane = panes()[0]
    // ⚠️ ON THE BAR, NOT AT A FIXED OFFSET. This asserted `bottom: 96px` — a guess
    // against a bar that is nearer 46px tall, which is exactly why the pane floated
    // above it. The bottom is now 24 (the bar's own offset) plus the bar's MEASURED
    // height, so the two touch; jsdom reports no layout, so the measurement falls
    // back to 46 and the assertion is 70px here. What is pinned is that the pane is
    // positioned FROM THE BOTTOM against the bar, not that the number is 96.
    expect(pane.style.bottom).toBe("70px")
    expect(pane.style.right).toBe("24px")
    expect(pane.style.top).toBe("")
    // ⚠️ AND AT THE BAR'S WIDTH, which was 390px against a 600px bar. Asserted via
    // `data-pane-width` because JSDOM'S CSS PARSER REJECTS `min()` — `style.width`
    // reads as the empty string, so the CSS line itself is unassertable here.
    //
    // ⚠️ THE ATTRIBUTE CARRIES THE WIDTH VALUE, and it has to. It held the word
    // "bar" first, derived from the same `isEntryPane` condition as the width — so a
    // break that narrowed the pane to 390px produced NO RED. Asserting the value
    // against the shared constant is what makes this about the width.
    expect(pane).toHaveAttribute("data-pane-width", BAR_WIDTH)
    // ⚠️ NO SCROLL CONTAINER, EVER, on an entry pane.
    expect(pane.style.overflowY).toBe("")
    expect(pane.style.maxHeight).toBe("")
    // the origin is what makes the growth read as unfolding from the bar rather than
    // fading in place
    expect(pane.style.transformOrigin).toBe("100% 100%")
  })

  it("an INFO pane still cascades from the top right — the contrast is the claim", async () => {
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await user.type(screen.getByTestId("opas-input"), "the catalog")
    await user.keyboard("{Enter}")

    await waitFor(() => expect(panes()).toHaveLength(1))
    const pane = panes()[0]
    expect(pane.style.top).toBe("72px")
    expect(pane.style.bottom).toBe("")
    expect(pane.style.transformOrigin).toBe("100% 0%")
  })

  it("the bar is NOT in entry mode with only an info pane open", async () => {
    // ⚠️ THE OTHER HALF OF THE PANE-TYPE RULING. With a catalog pane in front the bar
    // is still a request line, so Enter must still route a request — the thing the
    // entry-mode no-op suppresses.
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await user.type(screen.getByTestId("opas-input"), "the catalog")
    await user.keyboard("{Enter}")
    await waitFor(() => expect(panes()).toHaveLength(1))

    expect(screen.getByTestId("opas-input")).toHaveAttribute("data-entry-mode", "false")
  })
})

describe("opening Opas never shows a capture pane", () => {
  /**
   * ⚠️ THIS BLOCK REPLACES SIX TESTS OF RESTORE-ON-MOUNT, which James removed on
   * 2026-10-13 ("no order pane until you start an order"). They were not wrong
   * tests — they were careful tests of machinery that is now deleted, and they
   * documented the production-only failure that led here: James typed "order for
   * hopkins" in the SAME TAB he had walked the day before, and nothing opened,
   * because a stored session id restored a capture pane on mount, an entry pane
   * holds the bar in entry mode, and the opening effect returns before it looks at
   * the phrase. `sessionStorage` dies with the tab and not with a hard refresh, so
   * his refreshes never cleared it.
   *
   * ⚠️ WHAT IS KEPT IS THE CLAIM, NOT THE MECHANISM. The old tests asserted that a
   * stale or abandoned session did not block a new order. That claim is now true by
   * construction — nothing is restored — and these tests pin the construction,
   * including for a tab still carrying a key an older build wrote.
   */
  it("opens no pane on mount with NOTHING stored", async () => {
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await waitFor(() => expect(screen.getByTestId("opas-input")).toBeInTheDocument())

    expect(panes()).toHaveLength(0)
    expect(readCapture).not.toHaveBeenCalled()
  })

  it("opens no pane on mount with a LIVE session id stored by an older build", async () => {
    // ⚠️ A LIVE ID, NOT A DEAD ONE. A build that only skipped restore when the read
    // FAILED would pass a stale-id test and still resurrect this one.
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "sess-1")
    vi.mocked(readCapture).mockResolvedValue(state() as never)
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await waitFor(() => expect(screen.getByTestId("opas-input")).toBeInTheDocument())

    expect(panes()).toHaveLength(0)
    expect(readCapture).not.toHaveBeenCalled()
  })

  it("AND A NEW ORDER STILL OPENS in that tab — the claim the old tests protected", async () => {
    // ⚠️ THE POSITIVE CONTROL, AND THE WHOLE POINT. A build that opened no pane ever
    // would satisfy both tests above. This is the one that says the feature works in
    // the exact tab state that broke on production.
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "sess-1")
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await user.type(screen.getByTestId("opas-input"), "order for hopkins")

    await waitFor(() => expect(panes()).toHaveLength(1))
  })
})


describe("a reload restores NOTHING", () => {
  /**
   * ⚠️ THIS BLOCK ASSERTED THE REVERSE UNTIL 2026-10-13 — three tests of putting the
   * server's text back into the bar on reload. James removed the feature ("no order
   * pane until you start an order"), so the tests go with it, but the hazard the
   * first of them documented is worth keeping written down: a pane restored WITHOUT
   * its text shows every captured row above an empty bar, and the next keystroke
   * re-extracts from one character, un-capturing the whole order. Restore was only
   * ever safe if the text came back with it. Not restoring at all removes the pairing
   * problem instead of solving it, and the server row is untouched either way.
   */
  it("leaves the bar EMPTY and opens no pane, however much text the session has", async () => {
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "sess-1")
    vi.mocked(readCapture).mockResolvedValue(
      state({ full_text: "tent only, nameplate only" }) as never,
    )
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await waitFor(() => expect(screen.getByTestId("opas-input")).toBeInTheDocument())
    await settle()

    expect(screen.getByTestId("opas-input")).toHaveValue("")
    expect(panes()).toHaveLength(0)
    // ⚠️ AND NO WRITE WENT OUT. A restore that re-sent the text it had just read
    // would issue a sequence number for a reading nobody asked for; a build that
    // restored and then cleared would do worse — it would blank the order's text on
    // the server. Neither can happen if nothing is read.
    expect(readCapture).not.toHaveBeenCalled()
    expect(setCaptureText).not.toHaveBeenCalled()
  })
})

describe("the bar shows the whole order", () => {
  /**
   * ⚠️ WALK NOTE, James 2026-10-13: a long order scrolled out of view to the left, so
   * he could not see the start of what he had typed. An `<input>` can only scroll; a
   * textarea wraps. That is the structural claim, and these tests assert the
   * structure plus the two behaviours the change could have broken.
   *
   * ⚠️ THE GROWTH ITSELF IS NOT ASSERTED HERE, DELIBERATELY. jsdom reports
   * `scrollHeight` as 0 for every element, so a height computed from it is 0 in this
   * environment and an assertion about pixels would be measuring the harness. The
   * real-browser harness checks the height and the pane's position; this file checks
   * what jsdom can actually see.
   */
  it("is a TEXTAREA, which is what lets it wrap", async () => {
    const bar = await openOrder()
    expect(bar.tagName).toBe("TEXTAREA")
  })

  it("does not scroll — it has no resize handle and hides overflow", async () => {
    const bar = await openOrder()
    // ⚠️ `overflow: hidden` IS LOAD-BEARING, not cosmetic: the height is set from
    // `scrollHeight`, and a visible scrollbar feeds its own width back into that
    // measurement.
    expect(bar.style.resize).toBe("none")
    expect(bar.style.overflow).toBe("hidden")
    expect(bar.style.maxHeight).toBe("40vh")
  })

  it("ENTER IS STILL A HARD NO-OP, and a textarea makes that matter more", async () => {
    // ⚠️ AN INPUT IGNORED ENTER BY ITS NATURE; A TEXTAREA INSERTS A NEWLINE. So the
    // same `preventDefault` now does strictly more work, and losing it would put a
    // line break into the middle of an order instead of merely doing nothing.
    const bar = await openOrder()
    await user.type(bar, "tent only")
    await user.keyboard("{Enter}")
    await settle()

    expect(bar).toHaveValue("tent only")
    expect((bar as HTMLTextAreaElement).value).not.toContain("\n")
  })

  it("keeps the whole long order in its value", async () => {
    const bar = await openOrder()
    const long =
      "monticello burial vault Mary Smith 1948 to 2026 going to St. Mary's " +
      "section 4 lot 12 burial friday 11am service at the church thursday 10am"
    await user.type(bar, long)
    await settle()

    // ⚠️ THE VALUE, NOT THE PIXELS. What James lost was sight of the beginning; the
    // value always held it. This pins that the component never truncates, which is
    // the half a browser cannot tell you about.
    expect((bar as HTMLTextAreaElement).value.startsWith("monticello")).toBe(true)
    expect((bar as HTMLTextAreaElement).value.endsWith("10am")).toBe(true)
  })
})
