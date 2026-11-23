/**
 * The weekly payroll Focus — the behaviours worth a test.
 *
 * ⚠️ Each of these fails if the thing it names is removed. The read-only test
 * in particular: a core that rendered its buttons regardless would look
 * identical to one whose user happens to hold `payroll.approve`, which is the
 * shape of green that is not evidence.
 */

import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { WeeklyPayrollCore } from "./WeeklyPayrollCore"

const WEEK_ID = "week-44-id"

const FOCUS = {
  week_id: WEEK_ID,
  week_number: 44,
  week_end_date: "2026-10-31",
  check_date: "2026-11-05",
  status: "calculated",
  approved_at: null,
  dues: { total: "193.93", members_paying: 11, members_total: 13 },
  decisions: [],
  corrections: [],
  findings: [
    {
      // ⚠️ A REAL FLAG CODE, read from app/services/payroll/validation.py.
      // This fixture used to say `no_hours`, which does not exist — so the
      // test was green against a fiction while the live screen would have
      // shown the generic answers.
      key: "configured_member_missing_from_export:12008:",
      code: "configured_member_missing_from_export",
      severity: "warning",
      message: "Stevenson has no hours this week.",
      file_number: "12008",
      employee_id: "emp-12008",
      detail: {},
    },
  ],
  decision_outcomes: {
    settled: "Looked at and correct as it stands.",
    corrected: "Hours were corrected; see the correction.",
    asked: "Asked someone and waiting on an answer.",
    not_an_issue: "Looked at and not a problem.",
  },
}

const DUES = {
  week_number: 44,
  week_end_date: "2026-10-31",
  check_date: "2026-11-05",
  status: "calculated",
  members: [
    {
      employee_id: "emp-1",
      file_number: "9001",
      display_name: "Member 9001",
      dept: "PRECAST",
      dues_wage: "900.00",
      dues_hours: "40.0000",
      component_a: "13.05",
      component_b: "20.00",
      component_c: "0.80",
      binds: "a",
      initiation_fee: "0.00",
      dues: "13.85",
      ot_rate_used: "33.750",
      ot_rate_derived: true,
    },
  ],
  members_total: 1,
  members_paying: 1,
  total_dues: "13.85",
  total_dues_hours: "40.0000",
  basis: {
    percent: "0.0145",
    cap_multiplier: "0.6461",
    per_hour: "0.02",
    rule_set_effective: "2026-01-01",
    sentence: "Each member's dues: the lower of the percentage and the cap.",
  },
}

const PENDING_WEEK = {
  week_number: 46,
  week_start_date: "2026-11-08",
  week_end_date: "2026-11-14",
  check_date: "2026-11-19",
  cutoff_at: "2026-11-18T17:00:00",
  exists: false,
  week_id: null,
  status: "no_hours_yet",
  cutoff_provenance: { status: "assumed", source: "James, 2026-11-17" },
}

const api = vi.hoisted(() => ({
  getWeekFocus: vi.fn(),
  getUnionDuesPane: vi.fn(),
  getMemberPane: vi.fn(),
  getTimecardPane: vi.fn(),
  postWeekDecision: vi.fn(),
  postHourCorrection: vi.fn(),
  approveWeek: vi.fn(),
  uploadWeekHours: vi.fn(),
  uploadRegister: vi.fn(),
  listWeeks: vi.fn(),
  getCurrentWeek: vi.fn(),
  // ⚠️ THE STATUS ROW'S TWO CALLS. Omitting them did not make the row inert —
  // vitest threw "No getEmployeeStatus export is defined on the mock" as an
  // UNHANDLED error, which failed the pane test with "unable to find
  // payroll-pane-member-emp-1" and said nothing about the real cause. The
  // mock is a hand-kept list of exports, so every new export lands here.
  getEmployeeStatus: vi.fn(),
  setEmployeeStatus: vi.fn(),
}))

const setupApi = vi.hoisted(() => ({ listRegisterImports: vi.fn() }))
vi.mock("@/lib/payroll/setup-api", () => setupApi)

vi.mock("@/lib/payroll/focus-api", () => ({
  ...api,
  findingKey: (k: string, e?: string, d?: string) =>
    [k, e ?? "", d ?? ""].join(":"),
}))

/**
 * ⚠️ **RENDERED INSIDE A ROUTER, BECAUSE THE APP ALWAYS IS.** Added
 * 2026-11-23 when the core gained `useNavigate` — the vacation pane opens the
 * vacation pay Focus by URL, since a Focus needs its own entrances and its own
 * read-only answer and would get neither nested in a pane.
 *
 * All 30 tests here failed at once on the missing context. That is the harness
 * having rendered the component in a world that does not exist rather than a
 * defect in the change: nothing mounts this outside a router.
 */
function renderCore(over: { readOnly?: boolean; scope?: Record<string, unknown> } = {}) {
  return render(
    <MemoryRouter>
      <WeeklyPayrollCore
        focusId="weekly-payroll"
        config={{}}
        readOnly={over.readOnly ?? false}
        scope={over.scope ?? { week_id: WEEK_ID }}
      />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getWeekFocus.mockResolvedValue(FOCUS)
  api.getUnionDuesPane.mockResolvedValue(DUES)
  api.postWeekDecision.mockResolvedValue({})
  api.listWeeks.mockResolvedValue({ weeks: [] })
  api.getCurrentWeek.mockResolvedValue(PENDING_WEEK)
  setupApi.listRegisterImports.mockResolvedValue({ imports: [], count: 0 })
  api.postHourCorrection.mockResolvedValue({})
  // No status recorded — which is what every employee on production carries,
  // so it is the right default for a pane test rather than the convenient one.
  api.getEmployeeStatus.mockResolvedValue({
    employee_id: "emp-1",
    display_name: "Nobody, Test",
    status: null,
    since: null,
    history: [],
  })
})


describe("scope", () => {
  it("says so when no week was passed, rather than rendering an empty week", async () => {
    renderCore({ scope: {} })
    expect(await screen.findByText(/No week chosen/i)).toBeInTheDocument()
    expect(api.getWeekFocus).not.toHaveBeenCalled()
  })
})


describe("findings, one at a time", () => {
  it("shows the open finding with a why line and numbered answers", async () => {
    renderCore()
    expect(await screen.findByTestId("finding-configured_member_missing_from_export")).toBeInTheDocument()
    expect(screen.getByText(/Stevenson has no hours/)).toBeInTheDocument()
    // The "why", keyed on the code rather than buried in the server message.
    expect(screen.getByText(/unpaid week is the one mistake/i)).toBeInTheDocument()
    expect(screen.getByTestId("answer-1")).toHaveTextContent("Enter hours")
    expect(screen.getByTestId("answer-2")).toHaveTextContent("He didn't work")
    expect(screen.getByTestId("answer-3")).toHaveTextContent("Leave for now")
  })

  it("answers on the number keys, not only on click", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("finding-configured_member_missing_from_export")
    await user.keyboard("2")
    await waitFor(() =>
      expect(api.postWeekDecision).toHaveBeenCalledWith(
        WEEK_ID,
        "configured_member_missing_from_export:12008:",
        "not_an_issue",
        "He didn't work",
      ),
    )
  })

  it("answer 1 opens the by-day form instead of posting an outcome", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("finding-configured_member_missing_from_export")
    await user.click(screen.getByTestId("answer-1"))
    expect(await screen.findByTestId("correction-form")).toBeInTheDocument()
    expect(api.postWeekDecision).not.toHaveBeenCalled()
  })

  it("⚠️ the number keys stop answering while the correction form is open", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("finding-configured_member_missing_from_export")
    await user.click(screen.getByTestId("answer-1"))
    await screen.findByTestId("correction-form")

    // Typing "2" into the hours field must enter a 2, not answer the finding
    // with option 2. The handler is unbound while `correcting` — proved by a
    // break test: removing that early return reddens this.
    await user.type(screen.getByTestId("correction-hours"), "2")
    expect(screen.getByTestId("correction-hours")).toHaveValue("2")
    expect(api.postWeekDecision).not.toHaveBeenCalled()
  })

  it("a correction posts the hours AND records the answer", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("finding-configured_member_missing_from_export")
    await user.click(screen.getByTestId("answer-1"))
    await screen.findByTestId("correction-form")
    await user.type(screen.getByTestId("correction-date"), "2026-10-28")
    await user.type(screen.getByTestId("correction-hours"), "8")
    await user.type(screen.getByTestId("correction-reason"), "clocked in, never out")
    await user.click(screen.getByTestId("correction-save"))
    await waitFor(() =>
      expect(api.postHourCorrection).toHaveBeenCalledWith(WEEK_ID, {
        empId: "12008",
        workDate: "2026-10-28",
        payType: "REG",
        hours: "8",
        reason: "clocked in, never out",
      }),
    )
    // ⚠️ Two writes. The ANSWER is what takes the finding off the list, and it
    // records `corrected` rather than `settled` so the week reads back as
    // "hours were corrected".
    await waitFor(() =>
      expect(api.postWeekDecision).toHaveBeenCalledWith(
        WEEK_ID,
        "configured_member_missing_from_export:12008:",
        "corrected",
        "hours entered by hand",
      ),
    )
  })

  it("will not save a correction without a reason", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("finding-configured_member_missing_from_export")
    await user.click(screen.getByTestId("answer-1"))
    await screen.findByTestId("correction-form")
    await user.type(screen.getByTestId("correction-date"), "2026-10-28")
    await user.type(screen.getByTestId("correction-hours"), "8")
    expect(screen.getByTestId("correction-save")).toBeDisabled()
  })

  it("says nothing was flagged rather than showing a blank section", async () => {
    api.getWeekFocus.mockResolvedValue({ ...FOCUS, findings: [] })
    renderCore()
    expect(await screen.findByText(/Nothing flagged on week 44/i)).toBeInTheDocument()
  })
})


describe("read-only", () => {
  it("⚠️ offers no answer, no approve and no upload, and names the permission", async () => {
    api.getWeekFocus.mockResolvedValue({ ...FOCUS, status: "calculated" })
    renderCore({ readOnly: true })
    await screen.findByTestId("finding-configured_member_missing_from_export")
    expect(screen.queryByTestId("answer-1")).not.toBeInTheDocument()
    expect(screen.queryByTestId("approve-week")).not.toBeInTheDocument()
    expect(screen.getAllByText(/payroll\.approve/).length).toBeGreaterThan(0)
  })
})


describe("the week and the panes", () => {
  it("opens the member pane from a name and the dues pane from the total", async () => {
    const user = userEvent.setup()
    api.getMemberPane.mockResolvedValue({
      employee_id: "emp-1",
      display_name: "Member 9001",
      file_number: "9001",
      dept: "PRECAST",
      week_number: 44,
      hours: { reg: "40", ot: "0", personal: "0", sick: "0", vacation: "0", dues_hours: "40" },
      dues_wage: "900.00",
      ot_rate_used: "33.750",
      ot_rate_derived: true,
      working: { component_a: "13.05", component_b: "20.00", component_c: "0.80", binds: "a", initiation_fee: "0.00" },
      dues: "13.85",
      union_member: true,
    })
    renderCore()
    await screen.findByTestId("week-table")
    await user.click(screen.getByTestId("week-row-9001"))
    expect(await screen.findByTestId("payroll-pane-member-emp-1")).toBeInTheDocument()

    await user.click(screen.getByTestId("open-dues-pane"))
    expect(await screen.findByTestId("payroll-pane-union-dues")).toBeInTheDocument()

    // Closable, and closing one leaves the other.
    await user.click(screen.getByTestId("payroll-pane-close-union-dues"))
    await waitFor(() =>
      expect(screen.queryByTestId("payroll-pane-union-dues")).not.toBeInTheDocument(),
    )
    expect(screen.getByTestId("payroll-pane-member-emp-1")).toBeInTheDocument()
  })

  it("opening the same pane twice does not stack a duplicate", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("week-table")
    await user.click(screen.getByTestId("open-dues-pane"))
    await screen.findByTestId("payroll-pane-union-dues")
    await user.click(screen.getByTestId("open-dues-pane"))
    expect(screen.getAllByTestId("payroll-pane-union-dues")).toHaveLength(1)
  })
})


describe("the upload card", () => {
  it("appears when the HOURS have not arrived — not when the dues are empty", async () => {
    // ⚠️ **THIS TEST PINNED THE DEFECT, AND ITS OLD NAME SAID SO: "appears
    // only when the week has no PEOPLE on it".** People come from calculated
    // dues; hours come from the import. The week-44 dress rehearsal showed
    // the Focus header reading "Week 44 · imported" with 708.61 hours loaded
    // and, directly beneath it, "No hours for week 44 yet" — because nobody
    // had a pay rate, so there were no dues rows.
    api.getUnionDuesPane.mockResolvedValue({ ...DUES, members: [], members_total: 0 })
    api.getWeekFocus.mockResolvedValue({ ...FOCUS, status: "awaiting_hours" })
    renderCore()
    expect(await screen.findByTestId("upload-card")).toBeInTheDocument()
    expect(screen.getByText(/No hours for week 44 yet/i)).toBeInTheDocument()
  })

  it("⚠️ does NOT claim 'no hours' on an imported week with no dues", async () => {
    // The regression the rehearsal found, stated as its own case.
    api.getUnionDuesPane.mockResolvedValue({ ...DUES, members: [], members_total: 0 })
    api.getWeekFocus.mockResolvedValue({ ...FOCUS, status: "imported" })
    renderCore()
    await screen.findByTestId("findings")
    expect(screen.queryByText(/No hours for week 44 yet/i)).not.toBeInTheDocument()
    // ⚠️ AND THE DUES CHIP SAYS SO RATHER THAN "$0.00", which reads as "they
    // owe nothing" and means "this could not be worked out".
    expect(screen.getByText(/not calculated/i)).toBeInTheDocument()
  })

  it("is absent once there are people", async () => {
    renderCore()
    await screen.findByTestId("week-table")
    expect(screen.queryByTestId("upload-card")).not.toBeInTheDocument()
  })

  it("⚠️ reports a blocking flag instead of the row counts", async () => {
    // ⚠️ The upload card now renders on the HOURS state, not on an
    // empty dues list — see the rehearsal note above. The week has to
    // be awaiting hours for the card to be there to drive.
    api.getWeekFocus.mockResolvedValue({ ...FOCUS, status: "awaiting_hours" })
    const user = userEvent.setup()
    api.getUnionDuesPane.mockResolvedValue({ ...DUES, members: [], members_total: 0 })
    api.uploadWeekHours.mockResolvedValue({
      week: { id: WEEK_ID, week_number: 44, status: "imported" },
      import: {},
      summary: { people: 24, hours: 980 },
      flags: [{ code: "unknown_emp_id", severity: "error", message: "12008 is not on the roster." }],
    })
    renderCore()
    await screen.findByTestId("upload-card")
    const file = new File(["%PDF-1.4"], "hours.pdf", { type: "application/pdf" })
    await user.upload(screen.getByTestId("hours-file"), file)
    await user.click(screen.getByTestId("upload-hours"))
    // "24 people loaded" beside an error is a success message covering a failure.
    expect(await screen.findByTestId("focus-error")).toHaveTextContent(
      /not on the roster/i,
    )
  })
})


describe("approve, then Payentry", () => {
  it("shows the checks before approving, and approves", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("approve-section")
    expect(screen.getByText(/Findings still open/i)).toBeInTheDocument()
    await user.click(screen.getByTestId("approve-week"))
    await waitFor(() => expect(api.approveWeek).toHaveBeenCalledWith(WEEK_ID))
  })

  it("shows the deduction list only once the week is approved", async () => {
    api.getWeekFocus.mockResolvedValue({
      ...FOCUS,
      status: "approved",
      approved_at: "2026-11-04T17:00:00Z",
      corrections: [
        { emp_id: "12008", work_date: "2026-10-28", pay_type: "REG",
          hours: "8.0000", reason: "clocked in, never out", entered_at: "2026-11-03T10:00:00Z" },
      ],
    })
    renderCore()
    expect(await screen.findByTestId("deduction-list")).toBeInTheDocument()
    expect(screen.getByTestId("copy-deductions")).toHaveTextContent("Copy all 1")
    // The corrections are listed as things to enter in Payentry too — a
    // corrected hour that nobody enters is a correction that did not happen.
    expect(screen.getByTestId("corrections-to-enter")).toHaveTextContent("12008")
  })
})


describe("the answer map is keyed on codes the server actually sends", () => {
  it("⚠️ every ANSWERS key is a flag code that exists in validation.py", async () => {
    // Read from the backend source rather than restated here, so the day a
    // code is renamed this fails instead of the screen quietly falling back to
    // the generic three. That fallback is exactly what hid the first version's
    // invented codes (`no_hours`, `missing_lunch`, `probation`).
    const fs = await import("node:fs")
    const path = await import("node:path")
    const src = fs.readFileSync(
      path.resolve(
        process.cwd(),
        "../backend/app/services/payroll/validation.py",
      ),
      "utf8",
    )
    const mod = await import("./WeeklyPayrollCore")
    const keys = (mod as unknown as { __ANSWER_CODES__: string[] })
      .__ANSWER_CODES__
    expect(keys.length).toBeGreaterThan(0)
    for (const k of keys) {
      expect(src, `${k} is not a flag code in validation.py`).toContain(`"${k}"`)
    }
  })
})


describe("the fragment's target_key names a Focus this app registers", () => {
  it("⚠️ weekly_dues opens a Focus that exists", async () => {
    // ⚠️ CROSS-BOUNDARY, READ FROM THE BACKEND SOURCE. The server declares a
    // `target_key`; the client decides openability by looking it up in its own
    // registry and renders NOTHING when the lookup misses. That is correct
    // fail-closed behaviour and it is silent — the link simply does not
    // appear, with no error on either side.
    //
    // This shipped once: the fragment said `weekly_payroll`, the registry said
    // `weekly-payroll`, every test passed, and the note's only way into the
    // Focus was absent. Found by walking the page.
    const fs = await import("node:fs")
    const path = await import("node:path")
    const src = fs.readFileSync(
      path.resolve(
        process.cwd(),
        "../backend/app/services/fragments/platform_defaults.py",
      ),
      "utf8",
    )
    const m = src.match(/fragment_id=WEEKLY_DUES[\s\S]*?target_key="([^"]+)"/)
    expect(m, "could not find weekly_dues' target_key in the backend").toBeTruthy()
    const targetKey = m![1]

    const { getFocusConfig } = await import("@/contexts/focus-registry")
    await import("@/contexts/focus-registry")
    expect(
      getFocusConfig(targetKey),
      `the note declares target_key "${targetKey}" and no Focus is registered under it — the "Open" link will not render`,
    ).toBeTruthy()
  })
})

// ── no reply means UNKNOWN, never "nothing changed" (2026-11-17) ────────────
//
// ⚠️ All four writes in this Focus used to assert an outcome they could not
// know. Three were named in the ruling; the hours upload was a FOURTH, found
// by asking the file rather than the bug report. Each now splits on whether a
// reply arrived, and on a no-reply asks the SERVER what it holds.

const NO_REPLY = new Error("Network Error")
const REFUSED = {
  response: { status: 409, data: { detail: "the week is already approved" } },
}

describe("a write whose reply never arrived", () => {
  async function openAnswers(user: ReturnType<typeof userEvent.setup>) {
    renderCore()
    await screen.findByTestId("finding-configured_member_missing_from_export")
    return user
  }

  it("⚠️ the week answer: no reply + it DID land is reported as landed", async () => {
    // Telling Susan "that answer was not recorded" here makes her answer again,
    // superseding a decision the server already holds.
    const user = userEvent.setup()
    api.postWeekDecision.mockRejectedValue(NO_REPLY)
    // ⚠️ ORDER MATTERS: the FIRST load is the page opening and must show the
    // finding unanswered, or it never renders and there is nothing to click.
    // Only the follow-up check sees the decision on the server.
    api.getWeekFocus.mockResolvedValueOnce(FOCUS).mockResolvedValue({
      ...FOCUS,
      decisions: [{
        finding_key: "configured_member_missing_from_export:12008:",
        outcome: "not_an_issue", note: "", decided_at: "2026-11-17T15:00:00Z",
      }],
    })
    await openAnswers(user)
    await user.click(screen.getByTestId("answer-2"))
    expect(await screen.findByTestId("focus-error")).toHaveTextContent(
      /the answer WAS recorded/i,
    )
  })

  it("the week answer: no reply + it did NOT land says answer again", async () => {
    const user = userEvent.setup()
    api.postWeekDecision.mockRejectedValue(NO_REPLY)
    api.getWeekFocus.mockResolvedValue({ ...FOCUS, decisions: [] })
    await openAnswers(user)
    await user.click(screen.getByTestId("answer-2"))
    expect(await screen.findByTestId("focus-error")).toHaveTextContent(
      /not on the server — answer it again/i,
    )
  })

  it("⚠️ the week answer: the CHECK failing says unknown, not 'nothing changed'", async () => {
    const user = userEvent.setup()
    api.postWeekDecision.mockRejectedValue(NO_REPLY)
    // First load succeeds (the page must render); the follow-up check fails.
    api.getWeekFocus.mockResolvedValueOnce(FOCUS).mockRejectedValue(NO_REPLY)
    renderCore()
    await screen.findByTestId("finding-configured_member_missing_from_export")
    await user.click(screen.getByTestId("answer-2"))
    const err = await screen.findByTestId("focus-error")
    expect(err).toHaveTextContent(/unknown/i)
    expect(err.textContent?.toLowerCase()).not.toContain("nothing has been changed")
  })

  it("a REFUSED answer shows the server's own words", async () => {
    const user = userEvent.setup()
    api.postWeekDecision.mockRejectedValue(REFUSED)
    await openAnswers(user)
    await user.click(screen.getByTestId("answer-2"))
    expect(await screen.findByTestId("focus-error")).toHaveTextContent(
      "the week is already approved",
    )
    // The server answered, so there is nothing to go and check.
    expect(api.listWeeks).not.toHaveBeenCalled()
  })

  it("⚠️ the HOURS upload: the fourth site, not named in the ruling", async () => {
    // ⚠️ The upload card now renders on the HOURS state, not on an
    // empty dues list — see the rehearsal note above. The week has to
    // be awaiting hours for the card to be there to drive.
    api.getWeekFocus.mockResolvedValue({ ...FOCUS, status: "awaiting_hours" })
    const user = userEvent.setup()
    // The upload card appears when the week has NO people on it — the same
    // setup the working upload tests above use.
    api.getUnionDuesPane.mockResolvedValue({ ...DUES, members: [], members_total: 0 })
    api.uploadWeekHours.mockRejectedValue(NO_REPLY)
    api.listWeeks.mockResolvedValue({
      weeks: [{ id: "w44", week_number: 44, week_end_date: "2026-10-31",
                check_date: "2026-11-05", status: "calculated" }],
    })
    renderCore()
    const card = await screen.findByTestId("upload-card")
    await user.upload(
      card.querySelector('[data-testid="hours-file"]') as HTMLInputElement,
      new File(["%PDF"], "hours.pdf", { type: "application/pdf" }),
    )
    await user.click(screen.getByTestId("upload-hours"))
    expect(await screen.findByText(/IS on the server/i)).toBeInTheDocument()
  })

  it("the REGISTER upload: no reply + it did not land says retry is safe", async () => {
    const user = userEvent.setup()
    api.uploadRegister.mockRejectedValue(NO_REPLY)
    setupApi.listRegisterImports.mockResolvedValue({ imports: [], count: 0 })
    renderCore()
    const sec = await screen.findByTestId("register-section")
    await user.upload(
      sec.querySelector('[data-testid="register-file"]') as HTMLInputElement,
      new File(["%PDF"], "register.pdf", { type: "application/pdf" }),
    )
    await user.click(screen.getByTestId("upload-register"))
    expect(await screen.findByText(/safe to try again/i)).toBeInTheDocument()
  })

  it("⚠️ the REGISTER upload: no reply + it DID land says do not re-upload", async () => {
    const user = userEvent.setup()
    api.uploadRegister.mockRejectedValue(NO_REPLY)
    setupApi.listRegisterImports.mockResolvedValue({
      count: 1,
      imports: [{ import_id: "i1", filename: "register.pdf", pages: 262,
                  checks_parsed: 1275, checks_inserted: 1275, checks_duplicate: 0,
                  checks_failed: 0, created_at: null, report: {} }],
    })
    renderCore()
    const sec = await screen.findByTestId("register-section")
    await user.upload(
      sec.querySelector('[data-testid="register-file"]') as HTMLInputElement,
      new File(["%PDF"], "register.pdf", { type: "application/pdf" }),
    )
    await user.click(screen.getByTestId("upload-register"))
    expect(await screen.findByText(/DID load the register/i)).toBeInTheDocument()
  })
})


// ── a week with no row yet: the path that did not exist ────────────────────

describe("opening the Focus on a week END rather than an id", () => {
  function renderPending(over: Record<string, unknown> = {}) {
    // ⚠️ A SECOND RENDER HELPER IN THE SAME FILE, and it needed the router
    // too. I fixed the first and re-ran: 30 failures became 7, all of them
    // here. CLAUDE.md §11 — "ask where else this pattern appears OF THE FILE
    // before closing" — and the siblings are 460 lines apart.
    return render(
      <MemoryRouter>
        <WeeklyPayrollCore
          focusId="weekly-payroll"
          config={{}}
          readOnly={false}
          scope={{ week_end: "2026-11-14", ...over }}
        />
      </MemoryRouter>,
    )
  }

  it("⚠️ shows the upload card as step 1 — the blocker this closes", async () => {
    // Measured on production 2026-11-17: switch on, register loaded, roster
    // reconciled, and STILL no way to upload hours, because the card lives in
    // a Focus that opened only on the row the upload creates.
    renderPending()
    const card = await screen.findByTestId("pending-week")
    expect(card).toHaveTextContent("Week 46")
    expect(card).toHaveTextContent("2026-11-08")
    expect(card).toHaveTextContent("2026-11-14")
    expect(screen.getByTestId("upload-card")).toBeInTheDocument()
    expect(screen.getByTestId("hours-file")).toBeInTheDocument()
  })

  it("states the check date and the Payentry deadline", async () => {
    renderPending()
    const card = await screen.findByTestId("pending-week")
    expect(card).toHaveTextContent("2026-11-19")
    expect(card).toHaveTextContent(/Wednesday/i)
  })

  it("⚠️ says the cutoff is ASSUMED — a stated deadline names its provenance", async () => {
    renderPending()
    expect(await screen.findByTestId("pending-week")).toHaveTextContent(
      /assumed, not confirmed/i,
    )
  })

  it("⚠️ an unreadable week shows nothing rather than a guessed one", async () => {
    api.getCurrentWeek.mockRejectedValue(new Error("boom"))
    renderPending()
    expect(await screen.findByTestId("week-unresolved")).toHaveTextContent(
      /could not be read/i,
    )
    expect(screen.queryByTestId("upload-card")).not.toBeInTheDocument()
  })

  it("⚠️ the upload's own words are visible in THIS branch", async () => {
    // `setError` is read at the bottom of the main branch, which this state
    // never reaches — so without its own render the upload would report into
    // a message nobody could see, a refusal included.
    const user = userEvent.setup()
    api.uploadWeekHours.mockResolvedValue({
      week: { id: "w46", week_number: 46, status: "imported" },
      import: {}, summary: { people: 24, hours: 980 }, flags: [],
    })
    renderPending()
    await screen.findByTestId("upload-card")
    await user.upload(
      screen.getByTestId("hours-file"),
      new File(["%PDF"], "hours.pdf", { type: "application/pdf" }),
    )
    await user.click(screen.getByTestId("upload-hours"))
    expect(await screen.findByTestId("focus-error")).toHaveTextContent(/24 people/)
  })

  it("⚠️ after the upload it switches to the REAL week without a reload", async () => {
    const user = userEvent.setup()
    api.uploadWeekHours.mockResolvedValue({
      week: { id: "w46", week_number: 46, status: "imported" },
      import: {}, summary: { people: 24, hours: 980 }, flags: [],
    })
    // The row now exists, so the next read returns its id.
    api.getCurrentWeek
      .mockResolvedValueOnce(PENDING_WEEK)
      .mockResolvedValue({ ...PENDING_WEEK, exists: true, week_id: WEEK_ID })
    renderPending()
    await screen.findByTestId("upload-card")
    await user.upload(
      screen.getByTestId("hours-file"),
      new File(["%PDF"], "hours.pdf", { type: "application/pdf" }),
    )
    await user.click(screen.getByTestId("upload-hours"))
    // The real Focus, read by id.
    expect(await screen.findByTestId("the-week")).toBeInTheDocument()
    expect(api.getWeekFocus).toHaveBeenCalledWith(WEEK_ID)
  })

  it("an id still wins over a week end, so existing links are unchanged", async () => {
    renderPending({ week_id: WEEK_ID })
    expect(await screen.findByTestId("the-week")).toBeInTheDocument()
    expect(screen.queryByTestId("pending-week")).not.toBeInTheDocument()
    expect(api.getCurrentWeek).not.toHaveBeenCalled()
  })
})
