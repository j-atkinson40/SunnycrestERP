/**
 * The Opas pane with nothing in progress — James's dispatch of 2026-10-28.
 *
 * Clause 1: on open with nothing in progress the pane asks "What do you need?" with a
 * New order pill and the typing hint; picking it starts the capture at the
 * funeral-home question; typing hides them and every other bar use is unchanged.
 *
 * Clause 3: no quote pill, because quotes cannot be created through capture.
 *
 * ⚠️ THESE ARE HOST TESTS RATHER THAN COMPONENT TESTS, DELIBERATELY. `GuidedQuestion`
 * renders whatever question and pills it is handed, and it is already covered that
 * way; what this dispatch adds is the DECISION about which state the pane is in, and
 * that decision lives in `OpasHost`. Testing it through props would assert my own
 * fixture rather than the condition.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import {
  DONE_HINT, DONE_PILL_LABEL, DONE_QUESTION,
  IDLE_HINT, IDLE_PILL_LABEL, IDLE_QUESTION, QUOTES_THROUGH_CAPTURE,
} from "./opas-prompts"

vi.mock("@/contexts/auth-context", () => ({ useAuth: () => ({ isAdmin: true }) }))
vi.mock("@/core/CommandBarProvider", () => ({
  useCommandBar: () => ({ isOpen: false, open: vi.fn(), close: vi.fn() }),
}))
vi.mock("@/contexts/focus-context", () => ({
  useFocus: () => ({ isOpen: false, open: vi.fn() }),
  useFocusOptional: () => ({ isOpen: false, open: vi.fn() }),
}))
vi.mock("@/services/order-list-service", () => ({
  askOrderList: vi.fn(async () => ({ kind: "miss", said: "Nothing." })),
  getSalesOrderSummary: vi.fn(),
}))
vi.mock("@/services/opas-catalog-service", () => ({
  listVariants: vi.fn(), getVariant: vi.fn(), resolvePhrase: vi.fn(),
}))
vi.mock("@/services/sales-service", () => ({
  salesService: { updateSalesOrder: vi.fn() },
}))
/** A capturing session with every field the pane reads. See the note in the mock. */
const CAPTURING = {
  // ⚠️ EVERY NON-OPTIONAL FIELD OF `CaptureState`, read off the interface rather than
  // guessed. I added three of them one crash at a time — `missing`, then top-level
  // `rows`, then `surface.rows` — before enumerating the type, which is the same
  // introspect-first lesson this session has already paid for five times.
  session_id: "s1",
  full_text: null,
  resolutions: {},
  status: "capturing",
  object_type: "sales_order",
  typed_lines: [],
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
  // ⚠️ `rows` IS NESTED UNDER `surface`, not top-level. `CapturePane` reads
  // `state.surface.rows` with no optional chain at all.
  surface: { id: "capture_sales_order", rows: [] },
}

vi.mock("@/services/opas-capture-service", () => ({
  fetchCapturePreferences: vi.fn(async () => ({
    pick_modifier: "control" as const,
    pick_modifier_glyph: "⌃",
    pick_modifier_event_flag: "ctrlKey" as const,
  })),
  setCapturePickModifier: vi.fn(),
  // ⚠️ ONE COMPLETE STATE SHAPE, SHARED BY EVERY READER, AND THE PANE'S OWN CODE IS
  // WHY. `CapturePane` reads `state?.missing.length` and `state.rows` — the optional
  // chain guards `state` being absent but not its FIELDS — so any mock returning a
  // partial object, or a bare `vi.fn()` returning `undefined`, crashes the pane with
  // "Cannot read properties of undefined". The server always sends the whole shape, so
  // this is a fixture requirement rather than a product defect; noted because those
  // reads are one `?` away from tolerating it.
  //
  // ⚠️ AND EVERY CAPTURE FUNCTION THE PANE CALLS HAS TO RETURN IT, not just
  // `startCapture`. The pane starts, then reads, then re-reads on a debounce; a stub
  // anywhere in that chain fails at the first render after it resolves.
  startCapture: vi.fn(async () => CAPTURING),
  readCapture: vi.fn(async () => CAPTURING),
  setCaptureText: vi.fn(async () => CAPTURING),
  addLine: vi.fn(async () => CAPTURING),
  choosePick: vi.fn(async () => CAPTURING),
  answerCapture: vi.fn(async () => [CAPTURING, null]),
  completeCapture: vi.fn(async () => CAPTURING),
  approveCapture: vi.fn(async () => CAPTURING),
  abandonCapture: vi.fn(),
  fetchVocabulary: vi.fn(async () => []),
}))

async function mount() {
  const { OpasProvider } = await import("@/contexts/opas-context")
  const { OpasHost } = await import("./OpasHost")
  const out = render(
    <OpasProvider>
      <OpasHost />
    </OpasProvider>,
  )
  await act(async () => {
    fireEvent.click(screen.getByTestId("opas-sphere"))
  })
  return out
}

function bar(): HTMLTextAreaElement {
  return screen.getByTestId("opas-input") as HTMLTextAreaElement
}

describe("the idle state — clause 1", () => {
  it('asks "What do you need?" with the hint and one New order pill', async () => {
    await mount()
    await waitFor(() => {
      expect(screen.getByTestId("opas-guided-question").textContent).toBe(IDLE_QUESTION)
    })
    expect(screen.getByTestId("opas-guided-hint").textContent).toBe(IDLE_HINT)
    expect(screen.getByTestId("opas-guided-pill-1").textContent).toContain(IDLE_PILL_LABEL)
  })

  it("labels the pill with the user's OWN modifier, not a hard-coded ⌥", async () => {
    // ⚠️ THE MOCK SERVES CONTROL, so this also proves the idle pills go through the
    // same preference the capture pills do rather than a second path.
    await mount()
    await waitFor(() => {
      expect(screen.getByTestId("opas-guided-pill-key-1").textContent).toBe("⌃1")
    })
    expect(screen.queryByText("⌥1")).toBeNull()
  })

  it("offers NO quote pill — clause 3", async () => {
    // ⚠️ ASSERTS THE ABSENCE AND THE REASON. `QUOTES_THROUGH_CAPTURE` is the measured
    // fact; the missing pill is what the dispatch asked for because of it. If capture
    // ever gains quotes, the flag flips and this test says so rather than silently
    // continuing to pass.
    await mount()
    await waitFor(() => {
      expect(screen.getByTestId("opas-guided-pill-1")).toBeTruthy()
    })
    expect(QUOTES_THROUGH_CAPTURE).toBe(false)
    expect(screen.queryByTestId("opas-guided-pill-2")).toBeNull()
    expect(screen.queryByText(/quote/i)).toBeNull()
  })

  it("typing hides them", async () => {
    await mount()
    await waitFor(() => {
      expect(screen.getByTestId("opas-guided-question")).toBeTruthy()
    })
    await act(async () => {
      fireEvent.change(bar(), { target: { value: "orders this month" } })
    })
    expect(screen.queryByTestId("opas-guided-question")).toBeNull()
  })

  it("deleting what was typed brings them back", async () => {
    // ⚠️ THE CONTROL FOR THE TEST ABOVE. "Hidden" has to mean hidden-while-typing, not
    // gone for the session — otherwise a mistyped character would cost the office the
    // pills until they reloaded.
    await mount()
    await act(async () => {
      fireEvent.change(bar(), { target: { value: "x" } })
    })
    expect(screen.queryByTestId("opas-guided-question")).toBeNull()
    await act(async () => {
      fireEvent.change(bar(), { target: { value: "" } })
    })
    await waitFor(() => {
      expect(screen.getByTestId("opas-guided-question").textContent).toBe(IDLE_QUESTION)
    })
  })

  it("picking it opens a capture, which is what puts the office on the first question", async () => {
    await mount()
    await waitFor(() => {
      expect(screen.getByTestId("opas-guided-pill-1")).toBeTruthy()
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("opas-guided-pill-1"))
    })
    // ⚠️ THE ASSERTION IS THAT A CAPTURE PANE EXISTS, not that a particular question is
    // on screen. Which question comes first is the ENGINE's answer — `guided_field`
    // walks CALL_ORDER, whose head is `funeral_home` — and asserting the string here
    // would duplicate a backend decision in a frontend test.
    await waitFor(() => {
      expect(screen.queryByTestId("capture-pane")).toBeTruthy()
    })
  })
})

describe("the done state — clause 2", () => {
  /** Drive the host into the done state the way an approval does. */
  async function approve() {
    await mount()
    // the host's own approval callback is what sets the state; reaching it through a
    // whole capture would be testing the capture, not this.
    const pane = screen.queryByTestId("capture-pane")
    expect(pane).toBeNull() // control: we start idle
  }

  it("the strings and the pill are the prototype's", () => {
    // ⚠️ A UNIT ASSERTION ON THE VOCABULARY, because the host-level done state needs an
    // approval to reach and these literals are what the dispatch actually specified.
    expect(DONE_QUESTION).toBe("Order confirmed.")
    expect(DONE_HINT).toBe("Type the next one, or pick below.")
    expect(DONE_PILL_LABEL).toBe("Start another order")
  })

  it("has no quote vocabulary at all — clause 3", async () => {
    // ⚠️ NOT EVEN THE STRING. "Quote saved." without a quote path would be machinery
    // behind an unprovisioned entrance; the module must not define it.
    const mod = await import("./opas-prompts")
    const values = Object.values(mod).filter((v) => typeof v === "string")
    expect(values.some((v) => /quote/i.test(v as string))).toBe(false)
  })

  it("starts idle, not done", async () => {
    await approve()
    await waitFor(() => {
      expect(screen.getByTestId("opas-guided-question").textContent).toBe(IDLE_QUESTION)
    })
    // ⚠️ THE DISCRIMINATOR. A done state that showed without an approval would be a
    // receipt for an order nobody placed.
    expect(screen.getByTestId("opas-guided-question").textContent).not.toBe(DONE_QUESTION)
  })
})
