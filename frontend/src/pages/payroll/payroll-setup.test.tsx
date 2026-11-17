/**
 * Payroll setup — the three turn-on controls.
 *
 * ⚠️ **WHAT THESE TESTS ARE ACTUALLY FOR.** The three endpoints behind this
 * page already have backend coverage of who may call them
 * (`test_payroll_upload_permission.py` asserts the payroll role gets 403 on
 * the switch and the reconcile, and that nothing uploads while the switch is
 * off). None of that is re-asserted here, because a vitest mock cannot
 * enforce a permission and a test that appeared to would be worse than its
 * absence.
 *
 * What is NEW and only testable here is the page's *honesty* about state:
 * that it never claims the switch is off when it could not read it, that it
 * confirms before every write, that it reports what changed rather than going
 * quiet, and that nothing is blank.
 */

import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import PayrollSetup from "./payroll-setup"

const setupApi = vi.hoisted(() => ({
  getDataEnabled: vi.fn(),
  setDataEnabled: vi.fn(),
  reconcileRegisterPeople: vi.fn(),
}))
vi.mock("@/lib/payroll/setup-api", () => setupApi)

const focusApi = vi.hoisted(() => ({ uploadRegister: vi.fn() }))
vi.mock("@/lib/payroll/focus-api", () => focusApi)

const IMPORT_CLEAN = {
  import_id: "imp-1",
  pages: 7,
  checks_parsed: 11,
  checks_inserted: 11,
  checks_duplicate: 0,
  checks_failed: 0,
  summary_blocks_skipped: 2,
  report: { employees: 11, inserted: 11 },
}

const RECONCILE_DRY = {
  employees_seen: 11,
  union_members_proved: 9,
  applied: [],
  proposals: [
    { emp_id: "12001", field: "display_name", register_says: "A Smith",
      roster_says: null, verdict: "fill", why: "roster blank" },
    { emp_id: "12002", field: "is_union_member", register_says: "True",
      roster_says: null, verdict: "fill", why: "dues deducted" },
    { emp_id: "12003", field: "display_name", register_says: "B Jones",
      roster_says: "Robert Jones", verdict: "conflict", why: "disagree" },
  ],
  conflicts: [
    { emp_id: "12003", field: "display_name", register_says: "B Jones",
      roster_says: "Robert Jones", verdict: "conflict", why: "disagree" },
  ],
  ambiguous_names: {},
  dry_run: true,
}

function refused(code: string, message: string) {
  return { response: { data: { detail: { code, message } } } }
}

beforeEach(() => {
  vi.clearAllMocks()
  setupApi.getDataEnabled.mockResolvedValue({
    setting: "payroll_data_enabled",
    enabled: false,
  })
  setupApi.setDataEnabled.mockResolvedValue({
    setting: "payroll_data_enabled",
    enabled: true,
    changed: true,
  })
  setupApi.reconcileRegisterPeople.mockResolvedValue(RECONCILE_DRY)
  focusApi.uploadRegister.mockResolvedValue(IMPORT_CLEAN)
})

// ── the switch's state is the one fact this page exists to show ──────────────

describe("the data switch", () => {
  it("says OFF when it is off, and what that means", async () => {
    render(<PayrollSetup />)
    const state = await screen.findByTestId("switch-state")
    expect(state).toHaveTextContent("OFF")
    expect(state).toHaveTextContent(/no payroll export can be imported/i)
    expect(screen.getByTestId("switch-on")).toBeInTheDocument()
  })

  it("says ON when it is on, and offers the way back off", async () => {
    setupApi.getDataEnabled.mockResolvedValue({
      setting: "payroll_data_enabled",
      enabled: true,
    })
    render(<PayrollSetup />)
    const state = await screen.findByTestId("switch-state")
    expect(state).toHaveTextContent("ON")
    expect(screen.getByTestId("switch-off")).toBeInTheDocument()
    expect(screen.queryByTestId("switch-on")).not.toBeInTheDocument()
  })

  it("⚠️ an UNREADABLE switch is not reported as OFF, and offers no button", async () => {
    // The shape this guards: `enabled` defaulting to false on a failed read
    // would render a turn-on button next to the word OFF, which is a claim
    // about this company's settings that nothing measured.
    setupApi.getDataEnabled.mockRejectedValue(new Error("boom"))
    render(<PayrollSetup />)
    expect(await screen.findByTestId("switch-unreadable")).toBeInTheDocument()
    expect(screen.queryByTestId("switch-state")).not.toBeInTheDocument()
    expect(screen.queryByTestId("switch-on")).not.toBeInTheDocument()
    expect(screen.queryByTestId("switch-off")).not.toBeInTheDocument()
  })

  it("confirms before turning it on, and names what is being accepted", async () => {
    const user = userEvent.setup()
    render(<PayrollSetup />)
    await user.click(await screen.findByTestId("switch-on"))

    // Nothing has been written yet.
    expect(setupApi.setDataEnabled).not.toHaveBeenCalled()
    const panel = screen.getByTestId("switch-on-confirm")
    expect(panel).toHaveTextContent(/pay rates, hours, union dues/i)
    expect(panel).toHaveTextContent(/recorded against the change/i)

    await user.click(screen.getByTestId("switch-on-yes"))
    await waitFor(() => expect(setupApi.setDataEnabled).toHaveBeenCalledWith(true))
    expect(await screen.findByTestId("switch-said")).toHaveTextContent(/now ON/)
  })

  it("cancelling writes nothing", async () => {
    const user = userEvent.setup()
    render(<PayrollSetup />)
    await user.click(await screen.findByTestId("switch-on"))
    await user.click(screen.getByTestId("switch-on-no"))
    expect(setupApi.setDataEnabled).not.toHaveBeenCalled()
    expect(screen.queryByTestId("switch-said")).not.toBeInTheDocument()
    expect(screen.getByTestId("switch-on")).toBeInTheDocument()
  })

  it("a no-op write says so rather than claiming a change", async () => {
    const user = userEvent.setup()
    setupApi.setDataEnabled.mockResolvedValue({
      setting: "payroll_data_enabled",
      enabled: true,
      changed: false,
    })
    render(<PayrollSetup />)
    await user.click(await screen.findByTestId("switch-on"))
    await user.click(screen.getByTestId("switch-on-yes"))
    expect(await screen.findByTestId("switch-said")).toHaveTextContent(
      /No change — it was already on/i,
    )
  })

  it("a refused write is reported in the server's own words", async () => {
    const user = userEvent.setup()
    setupApi.setDataEnabled.mockRejectedValue(
      refused("forbidden", "Admin privileges required"),
    )
    render(<PayrollSetup />)
    await user.click(await screen.findByTestId("switch-on"))
    await user.click(screen.getByTestId("switch-on-yes"))
    expect(await screen.findByTestId("switch-said")).toHaveTextContent(
      "Admin privileges required",
    )
  })

  it("turning it OFF says plainly that nothing is deleted", async () => {
    const user = userEvent.setup()
    setupApi.getDataEnabled.mockResolvedValue({
      setting: "payroll_data_enabled",
      enabled: true,
    })
    render(<PayrollSetup />)
    await user.click(await screen.findByTestId("switch-off"))
    expect(screen.getByTestId("switch-off-confirm")).toHaveTextContent(
      /already loaded stay exactly as they are/i,
    )
  })
})

// ── the register upload ──────────────────────────────────────────────────────

describe("the register upload", () => {
  async function switchedOn() {
    setupApi.getDataEnabled.mockResolvedValue({
      setting: "payroll_data_enabled",
      enabled: true,
    })
    render(<PayrollSetup />)
    await screen.findByTestId("switch-state")
  }

  it("while the switch is off, says so and offers no file picker", async () => {
    render(<PayrollSetup />)
    expect(await screen.findByTestId("register-blocked")).toHaveTextContent(
      /Turn it on in step 1 first/i,
    )
    expect(screen.queryByTestId("register-file")).not.toBeInTheDocument()
  })

  it("with no file chosen, says what to do next rather than nothing", async () => {
    await switchedOn()
    expect(screen.getByTestId("register-no-file")).toHaveTextContent(
      /Choose a register PDF/i,
    )
  })

  it("confirms, then reports checks, people and pages", async () => {
    const user = userEvent.setup()
    await switchedOn()
    const file = new File(["%PDF-1.4"], "register.pdf", {
      type: "application/pdf",
    })
    await user.upload(screen.getByTestId("register-file"), file)

    await user.click(screen.getByTestId("register-upload"))
    expect(focusApi.uploadRegister).not.toHaveBeenCalled()
    expect(screen.getByTestId("register-upload-confirm")).toHaveTextContent(
      "register.pdf",
    )

    await user.click(screen.getByTestId("register-upload-yes"))
    const result = await screen.findByTestId("register-result")
    expect(result).toHaveTextContent("11 checks")
    expect(result).toHaveTextContent("11 people")
    expect(result).toHaveTextContent("7 pages")
    expect(screen.getByTestId("register-clean")).toBeInTheDocument()
  })

  it("⚠️ failed checks are reported as NOT stored, never summarised away", async () => {
    // The shape this guards: an import that reports only its successes reads
    // as a clean load. 2 checks that did not add up are 2 people whose pay is
    // not in the system, and nothing else on this page would say so.
    const user = userEvent.setup()
    focusApi.uploadRegister.mockResolvedValue({
      ...IMPORT_CLEAN,
      checks_inserted: 9,
      checks_duplicate: 3,
      checks_failed: 2,
      report: {
        employees: 11,
        ambiguous_names: { "12004": ["R Jones", "Robert Jones"] },
        unknown_codes: { XTRA: 2 },
        union_salary_anomalies: [
          { emp_id: "12005", check_number: "9001", check_date: "2026-11-05" },
        ],
      },
    })
    await switchedOn()
    await user.upload(
      screen.getByTestId("register-file"),
      new File(["%PDF"], "r.pdf", { type: "application/pdf" }),
    )
    await user.click(screen.getByTestId("register-upload"))
    await user.click(screen.getByTestId("register-upload-yes"))

    expect(await screen.findByTestId("register-failures")).toHaveTextContent(
      /2 checks did not add up and were NOT stored/,
    )
    expect(screen.getByTestId("register-duplicates")).toHaveTextContent(
      /3 already loaded and skipped/,
    )
    expect(screen.getByTestId("register-ambiguous")).toHaveTextContent("12004")
    expect(screen.getByTestId("register-unknown-codes")).toHaveTextContent("XTRA")
    expect(screen.getByTestId("register-anomalies")).toHaveTextContent(
      /salary and union dues/i,
    )
    // Not "nothing needs your attention" — five things do.
    expect(screen.queryByTestId("register-clean")).not.toBeInTheDocument()
  })

  it("a refusal from the switch is shown verbatim, not as a generic failure", async () => {
    const user = userEvent.setup()
    focusApi.uploadRegister.mockRejectedValue(
      refused(
        "payroll_data_disabled",
        "Payroll data loading is turned off for this company.",
      ),
    )
    await switchedOn()
    await user.upload(
      screen.getByTestId("register-file"),
      new File(["%PDF"], "r.pdf", { type: "application/pdf" }),
    )
    await user.click(screen.getByTestId("register-upload"))
    await user.click(screen.getByTestId("register-upload-yes"))
    expect(await screen.findByTestId("register-said")).toHaveTextContent(
      /turned off for this company/i,
    )
  })
})

// ── the roster reconcile ─────────────────────────────────────────────────────

describe("creating the employee list", () => {
  async function switchedOn() {
    setupApi.getDataEnabled.mockResolvedValue({
      setting: "payroll_data_enabled",
      enabled: true,
    })
    render(<PayrollSetup />)
    await screen.findByTestId("switch-state")
  }

  it("while the switch is off, says so and offers no preview", async () => {
    render(<PayrollSetup />)
    expect(await screen.findByTestId("roster-blocked")).toBeInTheDocument()
    expect(screen.queryByTestId("roster-preview")).not.toBeInTheDocument()
  })

  it("before it is run, says nothing has been read yet", async () => {
    await switchedOn()
    expect(screen.getByTestId("roster-not-run")).toHaveTextContent(
      /Nothing has been read yet/i,
    )
  })

  it("⚠️ the preview is a DRY RUN — it writes nothing", async () => {
    const user = userEvent.setup()
    await switchedOn()
    await user.click(screen.getByTestId("roster-preview"))
    await waitFor(() =>
      expect(setupApi.reconcileRegisterPeople).toHaveBeenCalledWith(false),
    )
    expect(setupApi.reconcileRegisterPeople).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId("roster-applied")).not.toBeInTheDocument()
  })

  it("reports what it would create and what it inferred", async () => {
    const user = userEvent.setup()
    await switchedOn()
    await user.click(screen.getByTestId("roster-preview"))

    const preview = await screen.findByTestId("roster-preview-result")
    expect(preview).toHaveTextContent("11 people")
    // The inference, named as what proves it.
    expect(preview).toHaveTextContent(/9/)
    expect(preview).toHaveTextContent(/union dues deducted — which proves membership/i)
    expect(screen.getByTestId("roster-fills")).toHaveTextContent("2")
    expect(screen.getByTestId("roster-fills")).toHaveTextContent("display_name")
    expect(screen.getByTestId("roster-fills")).toHaveTextContent("is_union_member")
  })

  it("⚠️ conflicts are shown as NOT written, with both sides named", async () => {
    const user = userEvent.setup()
    await switchedOn()
    await user.click(screen.getByTestId("roster-preview"))
    const conflicts = await screen.findByTestId("roster-conflicts")
    expect(conflicts).toHaveTextContent(/not written/i)
    expect(conflicts).toHaveTextContent("12003")
    expect(conflicts).toHaveTextContent("B Jones")
    expect(conflicts).toHaveTextContent("Robert Jones")
  })

  it("confirms before applying, counting the fills and the conflicts left behind", async () => {
    const user = userEvent.setup()
    await switchedOn()
    await user.click(screen.getByTestId("roster-preview"))
    await user.click(await screen.findByTestId("roster-apply"))

    expect(setupApi.reconcileRegisterPeople).toHaveBeenCalledTimes(1)
    const panel = screen.getByTestId("roster-apply-confirm")
    expect(panel).toHaveTextContent(/writes the 2 blank fields/i)
    expect(panel).toHaveTextContent(/1 disagreement/)

    setupApi.reconcileRegisterPeople.mockResolvedValue({
      ...RECONCILE_DRY,
      applied: RECONCILE_DRY.proposals.filter((p) => p.verdict === "fill"),
      dry_run: false,
    })
    await user.click(screen.getByTestId("roster-apply-yes"))
    await waitFor(() =>
      expect(setupApi.reconcileRegisterPeople).toHaveBeenLastCalledWith(true),
    )
    const applied = await screen.findByTestId("roster-applied")
    expect(applied).toHaveTextContent("2 entries")
    expect(applied).toHaveTextContent(/1 disagreement/)
  })

  it("⚠️ 'nothing to create' distinguishes an empty register from a complete roster", async () => {
    // The shape this guards: one "No changes" line would read identically
    // whether the roster was already right or no register had been loaded —
    // and those need opposite actions.
    const user = userEvent.setup()
    setupApi.reconcileRegisterPeople.mockResolvedValue({
      ...RECONCILE_DRY,
      employees_seen: 0,
      union_members_proved: 0,
      proposals: [],
      conflicts: [],
    })
    await switchedOn()
    await user.click(screen.getByTestId("roster-preview"))
    expect(await screen.findByTestId("roster-nothing-to-fill")).toHaveTextContent(
      /Load a register in step 2 first/i,
    )

    setupApi.reconcileRegisterPeople.mockResolvedValue({
      ...RECONCILE_DRY,
      proposals: [],
      conflicts: [],
    })
    await user.click(screen.getByTestId("roster-preview"))
    await waitFor(() =>
      expect(screen.getByTestId("roster-nothing-to-fill")).toHaveTextContent(
        /roster already knows everything/i,
      ),
    )
    expect(screen.queryByTestId("roster-apply")).not.toBeInTheDocument()
  })

  it("a stated refusal (no rulebook) is shown rather than a generic failure", async () => {
    const user = userEvent.setup()
    setupApi.reconcileRegisterPeople.mockRejectedValue({
      response: { data: { detail: "no rule set effective on 2026-11-05" } },
    })
    await switchedOn()
    await user.click(screen.getByTestId("roster-preview"))
    expect(await screen.findByTestId("roster-said")).toHaveTextContent(
      /no rule set effective/i,
    )
  })
})
