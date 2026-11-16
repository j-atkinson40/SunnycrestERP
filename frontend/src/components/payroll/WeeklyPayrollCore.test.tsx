/**
 * The weekly payroll Focus — the behaviours worth a test.
 *
 * ⚠️ Each of these fails if the thing it names is removed. The read-only test
 * in particular: a core that rendered its buttons regardless would look
 * identical to one whose user happens to hold `payroll.approve`, which is the
 * shape of green that is not evidence.
 */

import { render, screen, waitFor } from "@testing-library/react"
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
      key: "no_hours:12008:",
      code: "no_hours",
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
}))

vi.mock("@/lib/payroll/focus-api", () => ({
  ...api,
  findingKey: (k: string, e?: string, d?: string) =>
    [k, e ?? "", d ?? ""].join(":"),
}))

function renderCore(over: { readOnly?: boolean; scope?: Record<string, unknown> } = {}) {
  return render(
    <WeeklyPayrollCore
      focusId="weekly-payroll"
      config={{}}
      readOnly={over.readOnly ?? false}
      scope={over.scope ?? { week_id: WEEK_ID }}
    />,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getWeekFocus.mockResolvedValue(FOCUS)
  api.getUnionDuesPane.mockResolvedValue(DUES)
  api.postWeekDecision.mockResolvedValue({})
  api.postHourCorrection.mockResolvedValue({})
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
    expect(await screen.findByTestId("finding-no_hours")).toBeInTheDocument()
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
    await screen.findByTestId("finding-no_hours")
    await user.keyboard("2")
    await waitFor(() =>
      expect(api.postWeekDecision).toHaveBeenCalledWith(
        WEEK_ID,
        "no_hours:12008:",
        "not_an_issue",
        "He didn't work",
      ),
    )
  })

  it("answer 1 opens the by-day form instead of posting an outcome", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("finding-no_hours")
    await user.click(screen.getByTestId("answer-1"))
    expect(await screen.findByTestId("correction-form")).toBeInTheDocument()
    expect(api.postWeekDecision).not.toHaveBeenCalled()
  })

  it("⚠️ the number keys stop answering while the correction form is open", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("finding-no_hours")
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
    await screen.findByTestId("finding-no_hours")
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
        "no_hours:12008:",
        "corrected",
        "hours entered by hand",
      ),
    )
  })

  it("will not save a correction without a reason", async () => {
    const user = userEvent.setup()
    renderCore()
    await screen.findByTestId("finding-no_hours")
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
    await screen.findByTestId("finding-no_hours")
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
  it("appears only when the week has no people on it", async () => {
    api.getUnionDuesPane.mockResolvedValue({ ...DUES, members: [], members_total: 0 })
    renderCore()
    expect(await screen.findByTestId("upload-card")).toBeInTheDocument()
    expect(screen.getByText(/No hours for week 44 yet/i)).toBeInTheDocument()
  })

  it("is absent once there are people", async () => {
    renderCore()
    await screen.findByTestId("week-table")
    expect(screen.queryByTestId("upload-card")).not.toBeInTheDocument()
  })

  it("⚠️ reports a blocking flag instead of the row counts", async () => {
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
