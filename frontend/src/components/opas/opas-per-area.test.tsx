/**
 * ⚠️ SUSAN'S OPAS KNOWS PAYROLL AND NOTHING ELSE — James's ruling 2, 2026-11-17.
 *
 * The list comes from `GET /opas/capabilities`, composed per area on the
 * server. These tests assert, for an AREA-LIMITED user:
 *
 *   - the offerings are the SERVER'S, by label
 *   - the hardcoded "New order" pill is ABSENT — it is an orders-area offering
 *     that was never area-gated, and for her the server would refuse it
 *   - picking one, and typing one, both open the surface it names
 *   - a failed read says the list is coming, and does NOT claim there is
 *     nothing she can do
 *
 * ⚠️ AND THAT AN UNLIMITED USER'S OPAS IS UNCHANGED, which is the other half of
 * the decision: the registry holds payroll entries only today, so driving every
 * user's Opas from it would delete the live order entrance.
 *
 * The mock block below is lifted from `opas-idle-done.test.tsx` because the
 * pane reads the whole `CaptureState` shape and a partial double crashes it —
 * that file's own comments record the three crashes that taught it.
 */
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, useLocation } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { IDLE_PILL_LABEL, IDLE_QUESTION } from "./opas-prompts"

/** Swapped per test. `isAdmin: false` throughout: the point is the AREA. */
let limitedToAreas: string[] | null | undefined = ["payroll"]

vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ isAdmin: false, limitedToAreas }),
}))

/** The server's answer, and a counter so a retry can be observed. */
const served: { list: unknown[] | null; reads: number } = {
  list: [
    { id: "payroll_week_review", label: "This week's payroll",
      hint: "Hours, questions and dues for the week being processed",
      area: "payroll", level: "view",
      phrases: ["this week's payroll", "weekly payroll", "payroll", "dues"],
      target: "focus:weekly-payroll" },
    { id: "payroll_hours_upload", label: "Upload hours",
      hint: "The Employee Hours file from Payentry",
      area: "payroll", level: "change",
      phrases: ["upload hours", "hours", "employee hours"],
      target: "focus:weekly-payroll#upload" },
    { id: "payroll_dues_report", label: "Dues reports",
      area: "payroll", level: "view",
      phrases: ["dues report", "past weeks", "reports"],
      target: "/payroll" },
  ],
  reads: 0,
}

vi.mock("@/services/opas-capabilities-service", async () => {
  // ⚠️ THE REAL `matchCapability` AND `hrefForTarget` ARE KEPT. Only the READ is
  // doubled. Doubling the matcher would make these tests assert my fixture's
  // idea of matching instead of the shipped rule — the fixtures-modelled-on-the-
  // implementation failure in CLAUDE.md §11.
  const real = await vi.importActual<
    typeof import("@/services/opas-capabilities-service")
  >("@/services/opas-capabilities-service")
  return {
    ...real,
    fetchCapabilities: vi.fn(async () => {
      served.reads += 1
      return served.list
    }),
  }
})

/* ⚠️ THE auth-context MOCK FROM THE COPIED BLOCK IS DELETED HERE, NOT KEPT.
   It declared `{ isAdmin: true }`, and a SECOND vi.mock for the same module
   silently wins over the first — so my `{ isAdmin: false, limitedToAreas }`
   above was registered and then overridden, and every test ran as an ADMIN.
   The symptom was the pane offering "New order" and `served.reads === 0`,
   found by printing the DOM rather than by reading the file. A dead mock that
   looks like it controls something is CLAUDE.md §11's shape 6, and this is the
   second one in this arc — the first pointed at a module path that did not
   exist. */
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

//: ⚠️ A MUTABLE STORED PREFERENCE, SO A TEST CAN MAKE THE FIRST READ FAIL. James's bug
//: of 2026-10-29 was precisely a first read that failed and never retried, and a mock
//: that always succeeds cannot express it.
const storedPreference: {
  value: { pick_modifier: "option" | "control" | "command"
           pick_modifier_glyph: string
           pick_modifier_event_flag: "altKey" | "ctrlKey" | "metaKey" } | null
  reads: number
} = {
  value: {
    pick_modifier: "control",
    pick_modifier_glyph: "⌃",
    pick_modifier_event_flag: "ctrlKey",
  },
  reads: 0,
}

vi.mock("@/services/opas-capture-service", () => ({
  fetchCapturePreferences: vi.fn(async () => {
    storedPreference.reads += 1
    return storedPreference.value
  }),
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


/** Reports the current path, so "it opened the right surface" is read off the
 *  router rather than off a spy that could be called with anything. */
function Where() {
  const loc = useLocation()
  return <div data-testid="where">{loc.pathname + loc.search}</div>
}

async function mount() {
  const { OpasProvider } = await import("@/contexts/opas-context")
  const { OpasHost } = await import("./OpasHost")
  return render(
    <MemoryRouter initialEntries={["/home"]}>
      <OpasProvider>
        <OpasHost />
        <Where />
      </OpasProvider>
    </MemoryRouter>,
  )
}

async function openOpas() {
  await userEvent.click(screen.getByTestId("opas-sphere"))
}

beforeEach(() => {
  limitedToAreas = ["payroll"]
  served.reads = 0
  served.list = [
    { id: "payroll_week_review", label: "This week's payroll",
      hint: "Hours, questions and dues for the week being processed",
      area: "payroll", level: "view",
      phrases: ["this week's payroll", "weekly payroll", "payroll", "dues"],
      target: "focus:weekly-payroll" },
    { id: "payroll_hours_upload", label: "Upload hours",
      hint: "The Employee Hours file from Payentry",
      area: "payroll", level: "change",
      phrases: ["upload hours", "hours", "employee hours"],
      target: "focus:weekly-payroll#upload" },
    { id: "payroll_dues_report", label: "Dues reports",
      area: "payroll", level: "view",
      phrases: ["dues report", "past weeks", "reports"],
      target: "/payroll" },
  ]
})

describe("an area-limited user's Opas", () => {
  it("offers the SERVER'S list, and asks the same opening question", async () => {
    await mount()
    await openOpas()
    expect(await screen.findByText("This week's payroll")).toBeTruthy()
    expect(screen.getByText("Upload hours")).toBeTruthy()
    expect(screen.getByText("Dues reports")).toBeTruthy()
    expect(screen.getByText(IDLE_QUESTION)).toBeTruthy()
  })

  it("⚠️ does NOT offer New order", async () => {
    await mount()
    await openOpas()
    await screen.findByText("This week's payroll")
    // Control: the list arrived, so the absence below is about suppression and
    // not about an empty pane.
    expect(served.reads).toBeGreaterThan(0)
    expect(screen.queryByText(IDLE_PILL_LABEL)).toBeNull()
  })

  it("shows an entry's hint when it has one, and nothing when it has not", async () => {
    await mount()
    await openOpas()
    expect(await screen.findByText("The Employee Hours file from Payentry")).toBeTruthy()
    // `payroll_dues_report` has no hint in this fixture; its label renders and
    // no stray empty element claims to be its hint.
    expect(screen.getByText("Dues reports")).toBeTruthy()
  })

  it("opens the surface a picked entry names", async () => {
    await mount()
    await openOpas()
    const pill = await screen.findByText("Dues reports")
    await userEvent.click(pill)
    await waitFor(() => {
      expect(screen.getByTestId("where").textContent).toBe("/payroll")
    })
  })

  it("opens the surface a TYPED entry names, scoped", async () => {
    await mount()
    await openOpas()
    await screen.findByText("Upload hours")
    await userEvent.type(screen.getByTestId("opas-input"), "upload hours{Enter}")
    await waitFor(() => {
      expect(screen.getByTestId("where").textContent).toBe(
        "/home?focus=weekly-payroll&step=upload",
      )
    })
  })

  it('⚠️ "dues report" reaches the REPORTS entry, not the week', async () => {
    // The discriminating input from the shared case table, end to end through
    // the pane rather than through the matcher alone.
    await mount()
    await openOpas()
    await screen.findByText("Dues reports")
    await userEvent.type(screen.getByTestId("opas-input"), "dues report{Enter}")
    await waitFor(() => {
      expect(screen.getByTestId("where").textContent).toBe("/payroll")
    })
  })

  it("⚠️ a FAILED read says the list is coming, not that there is nothing", async () => {
    served.list = null
    await mount()
    await openOpas()
    expect(await screen.findByText("Reading what you can do here…")).toBeTruthy()
    expect(screen.queryByText("There is nothing here for your role yet.")).toBeNull()
    expect(screen.queryByText(IDLE_PILL_LABEL)).toBeNull()
  })

  it("⚠️ the command line does NOT invite her to type about orders", async () => {
    /* Found in the PR C walk-through SCREENSHOT, not by an assertion: her Opas
       listed three payroll entries above a command line reading
       "orders · the catalog". A placeholder is an example of what to type, so
       an out-of-area one is an instruction she cannot follow. */
    await mount()
    await openOpas()
    await screen.findByText("Dues reports")
    const input = screen.getByTestId("opas-input") as HTMLTextAreaElement
    expect(input.placeholder).not.toContain("orders")
    expect(input.placeholder).not.toContain("catalog")
    // It names things she actually has.
    expect(input.placeholder).toContain("this week's payroll")
  })

  it("⚠️ typing BEFORE the list arrives gets an answer, not silence", async () => {
    /* Found by the PR C walk-through: ⌘K then type immediately is the fast
       path, and it submitted against an unread list. The match resolved
       nothing and `submit` returned — no navigation, no message. A silent
       no-op on her only entrance.

       The read is held open here so the window the walk hit is the window
       under test, rather than a timing accident. */
    let release: (v: unknown[] | null) => void = () => {}
    served.list = []                               // irrelevant; never resolved
    const svc = await import("@/services/opas-capabilities-service")
    vi.mocked(svc.fetchCapabilities).mockImplementationOnce(
      () => new Promise((r) => { release = r as typeof release }),
    )

    await mount()
    await openOpas()
    expect(await screen.findByText("Reading what you can do here…")).toBeTruthy()

    await userEvent.type(screen.getByTestId("opas-input"), "dues report{Enter}")
    expect(
      await screen.findByText(/Still reading what you can do here/),
    ).toBeTruthy()
    // It did NOT navigate on a guess.
    expect(screen.getByTestId("where").textContent).toBe("/home")

    release([])
  })

  it("an EMPTY list says so plainly — a real answer, not a failure", async () => {
    served.list = []
    await mount()
    await openOpas()
    expect(await screen.findByText("There is nothing here for your role yet.")).toBeTruthy()
  })
})

describe("an unlimited user's Opas is unchanged", () => {
  it("still offers New order, and asks for no capability list", async () => {
    limitedToAreas = null
    await mount()
    // An unlimited non-admin cannot open Opas at all (mayUseOpas), so the
    // sphere is absent — which is itself the unchanged behaviour.
    expect(screen.queryByTestId("opas-sphere")).toBeNull()
    expect(served.reads).toBe(0)
  })
})


