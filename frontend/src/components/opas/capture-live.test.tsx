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
import { OpasHost } from "./OpasHost"
import { EXTRACT_DEBOUNCE_MS } from "./capture-sequence"

vi.mock("@/services/opas-capture-service", () => ({
  startCapture: vi.fn(),
  addLine: vi.fn(),
  choosePick: vi.fn(),
  readCapture: vi.fn(),
  setCaptureText: vi.fn(),
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
    expect(setCaptureText).toHaveBeenCalledWith("sess-1", "tent only", expect.any(Number))
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

    expect(setCaptureText).toHaveBeenCalledWith("sess-1", "", expect.any(Number))
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

describe("the placeholder says what is happening and is never stale", () => {
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
      expect(screen.getByTestId("opas-input")).toHaveAttribute(
        "placeholder",
        expect.stringContaining("Which one?"),
      ),
    )
    expect(screen.getByTestId("opas-input")).toHaveAttribute(
      "placeholder",
      expect.stringContaining("1–3"),
    )
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
    // ⚠️ TYPED AND NOT CLEARED. `placeholderFor` short-circuits to "Say what the
    // director said" on an EMPTY bar, before it ever reaches the missing count — so
    // `openOrder()`, which clears, makes this unmeasurable. My first version used it
    // and both of these failed in the control, which is the harness saying so.
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
      expect(screen.getByTestId("opas-input")).toHaveAttribute(
        "placeholder", expect.stringContaining("3 still needed"),
      ),
    )
    expect(screen.getByTestId("opas-input")).not.toHaveAttribute(
      "placeholder", expect.stringContaining("Nothing needed"),
    )
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
      expect(screen.getByTestId("opas-input")).toHaveAttribute(
        "placeholder", expect.stringContaining("Nothing needed"),
      ),
    )
  })

  it("STOPS saying 'reading' once the response lands, including a DROPPED one", async () => {
    // ⚠️ A DROPPED RESPONSE STILL CLEARS THE IN-FLIGHT FLAG. Gating that on `accept`
    // would leave "Reading what you typed…" on screen forever after one out-of-order
    // delivery — a message outliving its cause, which is the one thing the
    // placeholder ruling forbids.
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

    expect(screen.getByTestId("opas-input")).not.toHaveAttribute(
      "placeholder",
      expect.stringContaining("Reading"),
    )
  })
})

describe("⌘1..9 settles a pick", () => {
  const PICK = {
    field_id: "vault",
    phrase: "Continental",
    options: [["a", "A"], ["b", "B"], ["c", "C"]],
    discriminator: "size",
  }

  it("shows the NUMBER next to each option, because the shortcut needs it visible", async () => {
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    await openOrder()
    for (const n of [1, 2, 3]) {
      expect(screen.getByTestId(`capture-pick-number-vault-${n}`)).toHaveTextContent(
        String(n),
      )
    }
    expect(screen.getByTestId("capture-pick-hint-vault")).toBeInTheDocument()
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
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
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
      expect(screen.getByTestId("capture-pick-number-vault-2")).toBeInTheDocument(),
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

  it("A TYPED DIGIT GOES INTO THE TEXT, even while a pick is open", async () => {
    // ⚠️ THE OTHER HALF OF THE RULING, AND THE REASON ⌘ IS REQUIRED. A bare "3" is
    // text the director may be typing — a grave depth, a vault size, a time — so
    // stealing it would make numbers untypable for as long as a question is open.
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    const bar = await openOrder()

    await user.type(bar, "depth 3")
    await settle()

    expect(bar).toHaveValue("depth 3")
    expect(choosePick).not.toHaveBeenCalled()
    expect(setCaptureText).toHaveBeenCalledWith("sess-1", "depth 3", expect.any(Number))
  })

  it("a CLICK settles the same pick — both routes, per the ruling", async () => {
    vi.mocked(startCapture).mockResolvedValue(state({ pending_picks: [PICK] }) as never)
    vi.mocked(choosePick).mockResolvedValue(state() as never)
    await openOrder()

    await user.click(screen.getByTestId("capture-pick-option-vault-3"))

    await waitFor(() => expect(choosePick).toHaveBeenCalledWith("sess-1", "vault", 3))
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
      "sess-1", "Order for hopkins", expect.any(Number),
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
      "sess-1", "order for hopkins", expect.any(Number),
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

    expect(startCapture).toHaveBeenCalledWith(undefined)
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
    expect(pane.style.bottom).toBe("96px")
    expect(pane.style.right).toBe("24px")
    expect(pane.style.top).toBe("")
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

describe("a reload restores the bar", () => {
  it("puts the server's full text back into the bar", async () => {
    // ⚠️ WITHOUT THIS, A RELOAD SHOWS EVERY CAPTURED ROW ABOVE AN EMPTY BAR, and the
    // first keystroke re-extracts from one character — un-capturing the whole order.
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

    await waitFor(() =>
      expect(screen.getByTestId("opas-input")).toHaveValue("tent only, nameplate only"),
    )
  })

  it("does NOT re-send the restored text as a fresh edit", async () => {
    // ⚠️ THE SERVER ALREADY HAS THIS TEXT. Re-sending it is a wasted round trip on
    // every reload, and it would also issue a sequence number for a reading nobody
    // asked for.
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "sess-1")
    vi.mocked(readCapture).mockResolvedValue(
      state({ full_text: "tent only" }) as never,
    )
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await waitFor(() => expect(screen.getByTestId("opas-input")).toHaveValue("tent only"))

    await settle()

    expect(setCaptureText).not.toHaveBeenCalled()
  })

  it("leaves the bar EMPTY when the session has no whole-text record", async () => {
    // ⚠️ `full_text: null` IS NOT `""`. A line-captured session has no text to
    // restore, and handing the bar an empty string is correct — but it must come
    // from there being no record, not from a `|| ""` that would also fire on a
    // cleared bar.
    window.sessionStorage.setItem(CAPTURE_SESSION_KEY, "sess-1")
    vi.mocked(readCapture).mockResolvedValue(
      state({ full_text: null, typed_lines: ["tent only"] }) as never,
    )
    render(
      <OpasProvider>
        <OpasHost />
      </OpasProvider>,
    )
    await user.click(screen.getByTestId("opas-sphere"))
    await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())

    expect(screen.getByTestId("opas-input")).toHaveValue("")
    // the lines are still shown — they are all there is for that session
    expect(screen.getByTestId("capture-lines")).toHaveTextContent("tent only")
  })
})
