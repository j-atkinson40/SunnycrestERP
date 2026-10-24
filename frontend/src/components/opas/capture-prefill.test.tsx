/**
 * A funeral home filled from the Customer Pane survives the whole cycle.
 *
 * James's bug of 2026-10-24: "'New order' in the Hopkins Customer Pane opens the
 * capture, shows Funeral Home = Hopkins for about a second, then Funeral Home goes back
 * to blank."
 *
 * ⚠️ THE TEST RUNS THE WHOLE SEQUENCE, WHICH IS THE ONLY WAY TO SEE IT. The dispatch
 * says so and it is the point: the FIRST render is correct. What breaks it is the
 * debounced whole-text re-extraction that fires ~400 ms later, so a test that renders
 * and asserts passes against the bug. Fake timers are what make the second request
 * happen inside the test.
 *
 * ⚠️ AND IT NEEDS THE BAR TO BE EMPTY TO REPRODUCE. The cause is that the host opened
 * the capture without putting the opening line in the bar, so the pane's `text` prop was
 * "" and the re-read rebuilt every value from an empty string. A fixture that passed the
 * opening line as `text` would be green against the bug — the fixture modelled on the
 * fix rather than on the failure. `renderWithEmptyBar` is deliberately the old shape.
 */
import { act, render } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const startCapture = vi.fn()
const setCaptureText = vi.fn()

// ⚠️ EVERY EXPORT THE PANE IMPORTS, the sibling's lesson: an omitted function fails
// when CALLED, mid-effect, as "undefined is not a function".
vi.mock("@/services/opas-capture-service", () => ({
  startCapture: (...a: unknown[]) => startCapture(...a),
  setCaptureText: (...a: unknown[]) => setCaptureText(...a),
  addLine: vi.fn(),
  choosePick: vi.fn(),
  readCapture: vi.fn(),
  chooseSwitch: vi.fn(),
  abandonCapture: vi.fn(),
  completeCapture: vi.fn(),
  approveCapture: vi.fn(),
}))

import { EXTRACT_DEBOUNCE_MS } from "./capture-sequence"
import { CapturePane } from "./CapturePane"

const HOME = "Johnson Funeral Home"
const OPENING = `order ${HOME} `

/**
 * The server's state after `start(opening_line, prefill)`.
 *
 * ⚠️ THE SHAPE IS TAKEN FROM `capture-pane.test.tsx`'s own fixture, not invented here.
 * My first version listed the handful of keys I thought the pane read, and the render
 * died on `Cannot read properties of undefined (reading 'length')` — a double that omits
 * a field the component iterates fails at USE, not at import, which surfaces as the pane
 * rendering nothing. `opas-capture-service.test.ts` pins the real exports; this shape
 * follows the sibling fixture so there is one place to keep up with.
 */
function state(over: Record<string, unknown> = {}) {
  return {
    session_id: "s1",
    status: "capturing",
    object_type: "sales_order",
    typed_lines: [],
    // ⚠️ NULL, AND IT IS LOAD-BEARING FOR THIS BUG. `start` goes through `add_line`,
    // which never sets `full_text` — so the pane's guard `state.full_text === text`
    // compares `null === ""`, is false, and the re-extraction ALWAYS fires. Measured on
    // the server, 2026-10-24.
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
    surface: { id: "capture", rows: [] },
    ...over,
  }
}

const withHome = (over: Record<string, unknown> = {}) =>
  state({ values: { funeral_home: HOME }, ...over })

beforeEach(() => {
  vi.useFakeTimers()
  startCapture.mockReset()
  setCaptureText.mockReset()
})
afterEach(() => {
  vi.useRealTimers()
})

/**
 * Let effects and resolved promises settle under FAKE timers.
 *
 * ⚠️ `waitFor` DOES NOT WORK HERE AND TIMED OUT THREE TESTS AT 5 s EACH. It polls on a
 * real interval, and the clock is frozen — so it waits for a tick that never comes. With
 * fake timers the test has to advance the clock itself, which is also the only way the
 * debounce under test can fire at all.
 */
async function flush(ms = 0) {
  await act(async () => {
    vi.advanceTimersByTime(ms)
    await Promise.resolve()
  })
}

/** The host's OLD behaviour: a capture opened from a pane, with nothing in the bar. */
function renderWithEmptyBar(prefill?: Record<string, string>) {
  return render(
    <CapturePane openingLine={OPENING} prefill={prefill} text="" />,
  )
}

describe("the prefill survives the debounced re-extraction", () => {
  it("is still filled after the whole sequence settles", async () => {
    startCapture.mockResolvedValue(withHome())
    // ⚠️ THE SERVER KEEPS IT, because `prefill` is stored on the session and re-applied
    // beneath the text. That is the behaviour under test here; the server side is
    // asserted directly in `test_capture_prefill.py`.
    setCaptureText.mockResolvedValue(withHome({ full_text: "", seq: 1 }))

    renderWithEmptyBar({ funeral_home: HOME })
    await flush()

    // the prefill reached the server with the opening line
    expect(startCapture).toHaveBeenCalledWith(OPENING, { funeral_home: HOME })

    // ⚠️ NOW RUN THE CLOCK PAST THE DEBOUNCE — the step that makes this a cycle test.
    await act(async () => {
      vi.advanceTimersByTime(EXTRACT_DEBOUNCE_MS + 50)
    })
    await flush()

    // and the re-read was sent the BAR's text, which is what wiped it before
    expect(setCaptureText.mock.calls[0][1]).toBe("")

    const after = setCaptureText.mock.results[0].value
    await expect(after).resolves.toMatchObject({ values: { funeral_home: HOME } })
  })

  it("sends no prefill for a capture the director typed", async () => {
    startCapture.mockResolvedValue(state())
    setCaptureText.mockResolvedValue(state({ full_text: "order for hopkins", seq: 1 }))
    render(<CapturePane openingLine="order for hopkins" text="order for hopkins" />)
    await flush()
    // ⚠️ `undefined`, NOT `{}`. The service omits the key entirely so a typed capture's
    // request is byte-for-byte what it was before this change.
    expect(startCapture).toHaveBeenCalledWith("order for hopkins", undefined)
  })

  it("does not re-extract at all when the bar matches what was captured", async () => {
    // The host now puts the opening line in the bar, so the pane's own guard fires and
    // the request that used to wipe the field is never made.
    startCapture.mockResolvedValue(withHome({ full_text: OPENING }))
    render(<CapturePane openingLine={OPENING} prefill={{ funeral_home: HOME }} text={OPENING} />)
    await flush()
    await act(async () => {
      vi.advanceTimersByTime(EXTRACT_DEBOUNCE_MS + 50)
    })
    expect(setCaptureText).not.toHaveBeenCalled()
  })
})
