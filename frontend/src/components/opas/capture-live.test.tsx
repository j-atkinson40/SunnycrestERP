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
  await user.keyboard("{Enter}")
  await waitFor(() => expect(screen.getByTestId("capture-rows")).toBeInTheDocument())
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
