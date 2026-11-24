/**
 * Typed access to the Payroll 5a Focus endpoints (backend PR #27).
 *
 * ⚠️ ONE MODULE, SO THE SHAPES ARE DECLARED ONCE. Four reads on
 * `payroll.view`, two writes on `payroll.approve`, all six behind the tenant
 * payroll data switch. A component that built its own URL would be a second
 * place for a route to be renamed.
 *
 * ⚠️ MONEY AND HOURS ARE STRINGS, END TO END. The server sends decimals as
 * strings deliberately — `Number("193.93")` is fine to display and lethal to
 * add up, and the one number Susan reads off this screen is a total. Nothing
 * here converts them; the server's own totals are rendered as given.
 */

import apiClient from "@/lib/api-client"

const BASE = "/payroll-reports"

/** A decimal the server formatted. Kept as a string on purpose — see above. */
export type Money = string
export type Hours = string

export interface DuesBasis {
  percent: string
  cap_multiplier: string
  per_hour: string
  rule_set_effective: string
  sentence: string
}

export interface DuesMemberRow {
  employee_id: string
  file_number: string | null
  display_name: string | null
  dept: string | null
  dues_wage: Money | null
  dues_hours: Hours | null
  component_a: Money | null
  component_b: Money | null
  component_c: Money | null
  binds: string | null
  initiation_fee: Money | null
  dues: Money | null
  ot_rate_used: string | null
  ot_rate_derived: boolean | null
}

export interface UnionDuesPane {
  week_number: number
  week_end_date: string
  check_date: string
  status: string
  members: DuesMemberRow[]
  members_total: number
  members_paying: number
  total_dues: Money | null
  total_dues_hours: Hours | null
  basis: DuesBasis
}

export interface MemberPane {
  employee_id: string
  display_name: string | null
  file_number: string | null
  dept: string | null
  week_number: number
  hours: {
    reg: Hours | null
    ot: Hours | null
    personal: Hours | null
    sick: Hours | null
    vacation: Hours | null
    dues_hours: Hours | null
  }
  dues_wage: Money | null
  ot_rate_used: string | null
  ot_rate_derived: boolean | null
  working: {
    component_a: Money | null
    component_b: Money | null
    component_c: Money | null
    binds: string | null
    initiation_fee: Money | null
  }
  dues: Money | null
  union_member: boolean | null
}

export interface TimecardDay {
  work_date: string
  pay_type: string
  parsed_hours: Hours
  corrected_hours: Hours
  total_hours: Hours
  punch_count: number
  any_punch_has_location: boolean
}

export interface TimecardPane {
  employee_id: string
  week_number: number
  week_end_date: string
  days: TimecardDay[]
  total_parsed: Hours
  total_corrected: Hours
  punch_data_present: boolean
  source: string
}

export interface WeekFocus {
  findings: WeekFinding[]
  week_id: string
  week_number: number
  week_end_date: string
  check_date: string
  status: string
  approved_at: string | null
  dues: {
    total: Money | null
    members_paying: number
    members_total: number
  }
  decisions: {
    finding_key: string
    outcome: string
    note: string
    decided_at: string | null
  }[]
  corrections: {
    emp_id: string
    work_date: string
    pay_type: string
    hours: Hours
    reason: string
    entered_at: string | null
  }[]
  /** The declared outcome set, served so the client renders the same words the
   *  server validates against rather than a list of its own that drifts. */
  decision_outcomes: Record<string, string>
}

export interface WeekRow {
  id: string
  week_number: number
  week_end_date: string
  check_date: string
  status: string
}

/** Every payroll week this tenant has. Typed here because the Focus needs it
 *  to answer "did my hours upload land?" when no reply came back. */
/**
 * The week being worked today, whether or not it has a row yet.
 *
 * ⚠️ **THE ONLY PAYROLL READ THAT DOES NOT NEED A `week_id`**, which is the
 * whole reason it exists: every other one does, and that row is created BY the
 * upload. Before this, a tenant with nothing uploaded had no way to reach the
 * upload card, because the card lives inside the Focus and the Focus opens on
 * an id that does not exist yet.
 */
export interface CurrentWeek {
  week_number: number
  week_start_date: string
  week_end_date: string
  check_date: string
  /** Wednesday 17:00 before the checks. An `assumed` rule — see provenance. */
  cutoff_at: string
  exists: boolean
  week_id: string | null
  status: string
  cutoff_provenance: { status: string; source: string }
}

/**
 * The week being worked, or — given `weekEnd` — the descriptor for that week.
 *
 * ⚠️ **THE ARGUMENT EXISTS BECAUSE `week_end` WAS HONOURED AS A FLAG AND
 * IGNORED AS A VALUE.** The Focus reads `?week_end=` to decide it is on a week
 * with no row, then called this with no argument and uploaded against whatever
 * today's week was. `week_end=2026-10-31` rendered "Week 47" and posted week
 * 47; the importer refused, correctly, about a week nobody asked for — and a
 * late week could not be uploaded at all.
 */
export async function getCurrentWeek(weekEnd?: string | null) {
  const r = await apiClient.get<CurrentWeek>(`${BASE}/weeks/current`, {
    params: weekEnd ? { week_end: weekEnd } : undefined,
  })
  return r.data
}

export async function listWeeks() {
  const r = await apiClient.get<{ weeks: WeekRow[] }>(`${BASE}/weeks`)
  return r.data
}

export async function getWeekFocus(weekId: string) {
  const r = await apiClient.get<WeekFocus>(`${BASE}/weeks/${weekId}/focus`)
  return r.data
}

export async function getUnionDuesPane(weekId: string) {
  const r = await apiClient.get<UnionDuesPane>(
    `${BASE}/weeks/${weekId}/panes/union-dues`,
  )
  return r.data
}

export async function getMemberPane(weekId: string, employeeId: string) {
  const r = await apiClient.get<MemberPane>(
    `${BASE}/weeks/${weekId}/panes/member/${encodeURIComponent(employeeId)}`,
  )
  return r.data
}

export async function getTimecardPane(weekId: string, employeeId: string) {
  const r = await apiClient.get<TimecardPane>(
    `${BASE}/weeks/${weekId}/panes/timecard/${encodeURIComponent(employeeId)}`,
  )
  return r.data
}

/**
 * ⚠️ **FORM-ENCODED, AND THE HEADER MUST BE SET EXPLICITLY.**
 *
 * The backend declares these with `Form(...)`. `apiClient` sets a default
 * `Content-Type: application/json`, which WINS over the one axios would infer
 * from a `URLSearchParams` body — so the bytes go out correctly form-encoded
 * under a JSON content type and FastAPI reports EVERY FIELD MISSING while the
 * request body plainly contains them.
 *
 * That 422 reads as a client bug and is an encoding mismatch. It shipped once:
 * the same request succeeded under curl and failed from the page, which is the
 * only reason it was found.
 */
const FORM_HEADERS = {
  "Content-Type": "application/x-www-form-urlencoded",
} as const

function form(fields: Record<string, string>) {
  const body = new URLSearchParams()
  for (const [k, v] of Object.entries(fields)) body.append(k, v)
  return body
}

export interface HourCorrectionInput {
  empId: string
  workDate: string
  payType: string
  /** Signed, and a DELTA against what Payentry printed — never a replacement. */
  hours: string
  reason: string
}

export async function postHourCorrection(
  weekId: string,
  input: HourCorrectionInput,
) {
  const r = await apiClient.post(
    `${BASE}/weeks/${weekId}/corrections`,
    form({
      emp_id: input.empId,
      work_date: input.workDate,
      pay_type: input.payType,
      hours: input.hours,
      reason: input.reason,
    }),
    { headers: FORM_HEADERS },
  )
  return r.data
}

export async function postWeekDecision(
  weekId: string,
  findingKey: string,
  outcome: string,
  note = "",
) {
  const r = await apiClient.post(
    `${BASE}/weeks/${weekId}/decisions`,
    form({ finding_key: findingKey, outcome, note }),
    { headers: FORM_HEADERS },
  )
  return r.data
}

/** Mirrors `week_focus.finding_key` on the server: `kind:emp_id:date`, with
 *  the separators kept even when a part is absent, so a kind with no date
 *  cannot collide with a different kind that has one. */
export function findingKey(
  kind: string,
  empId?: string | null,
  onDate?: string | null,
) {
  return [kind, empId ?? "", onDate ?? ""].join(":")
}


export interface WeekFinding {
  key: string
  code: string
  severity: string
  message: string
  file_number: string | null
  employee_id: string | null
  detail: Record<string, unknown>
}

/**
 * ⚠️ **TWO SHAPES BEHIND ONE BUTTON, AND THIS TYPE DESCRIBED ONLY THE DEAD
 * ONE.** `POST /weeks/upload` has a legacy delimited-text branch (`week`,
 * `import`) and the Employee Hours PDF branch (`import_id`, `week_id`,
 * `report`). The PDF branch is the one Susan's upload takes, and it returned
 * neither `summary` nor `flags` — so the card's sentence rendered "Week 44
 * loaded: — people, — hours." on a week that had just loaded correctly.
 *
 * The server now returns `summary` and `flags` from BOTH branches, so the
 * screen does not have to know which parser ran. The branch-specific fields
 * stay optional and are not read by the card.
 */
export interface WeekUploadResult {
  /** Legacy delimited-text branch only. */
  week?: { id: string; week_number: number; status: string }
  import?: Record<string, unknown>
  /** Employee Hours PDF branch only. */
  import_id?: string
  week_id?: string
  report?: Record<string, unknown>
  /** ⚠️ `people` is everyone the export LISTS; `with_hours` is how many of
   *  them have hours. Week 44 is 25 and 18 — different populations, both
   *  returned, so neither can drift into standing for the other. */
  summary: {
    people?: number
    with_hours?: number
    listed_without_hours?: number
    hours?: string
    rows_stored?: number
  } & Record<string, unknown>
  flags: { code: string; severity: string; message: string }[]
  /** ⚠️ Present only when a Punch Location file was attached. `stored` is
   *  FALSE — ingestion is unbuilt — and the reason says so, because a success
   *  that does not mention the file is how somebody comes to believe it
   *  loaded. */
  /** ⚠️ `stored` IS A BOOLEAN AND `punches_stored` IS A COUNT. They were one
   *  field called `stored` and the server's dict spread silently replaced the
   *  boolean with the count — one name for two meanings, decided by which
   *  spread won. */
  punch_file?: {
    filename: string | null
    stored: boolean
    punches_stored: number
    /** ⚠️ Punches whose name nobody has confirmed. They ARE stored, with no
     *  employee attached — dropping them would delete the evidence along with
     *  the finding. */
    unattached: number
    people_matched: number
    findings: {
      kind: string
      raw_name: string
      candidates: string[]
      detail: string
    }[]
  } | null
}

/** Multipart, because it carries the Employee Hours PDF. Punch Location is
 *  optional — the week can be worked without it, and the timecard pane says so
 *  rather than looking empty. */
export async function uploadWeekHours(args: {
  weekNumber: number
  weekEndDate: string
  hoursFile: File
  punchFile?: File | null
}) {
  const fd = new FormData()
  fd.append("week_number", String(args.weekNumber))
  fd.append("week_end_date", args.weekEndDate)
  fd.append("file", args.hoursFile)
  if (args.punchFile) fd.append("punch_file", args.punchFile)
  // ⚠️ `multipart/form-data` IS PASSED DELIBERATELY AND IS NEVER SENT.
  // Its only job is to stop `apiClient`'s instance-level JSON content-type
  // from reaching axios's `transformRequest`, which JSON-stringifies a
  // FormData body when the content type says JSON — a `File` becomes `{}`.
  // Axios then clears this header so the browser supplies the real one with
  // its boundary. 21 of the 22 FormData callers in this app pass it; these two
  // payroll uploads did not, and could never upload anything.
  //
  // `api-client.ts` now strips the JSON type for any FormData body, which is
  // the load-bearing fix. This stays for consistency with the other 21 callers
  // and so a revert there cannot silently re-break payroll.
  const r = await apiClient.post<WeekUploadResult>(`${BASE}/weeks/upload`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return r.data
}

export async function approveWeek(weekId: string) {
  const r = await apiClient.post(`${BASE}/weeks/${weekId}/approve`)
  return r.data
}

/**
 * What an import reports back. Typed here, next to the call, because the
 * payroll setup page renders these figures rather than discarding them.
 *
 * `report` is also STORED on the import row — a finding that lived only in a
 * response body would be a finding nobody could audit later — so the shape is
 * the server's, not this page's.
 */
export interface RegisterImportResult {
  import_id: string
  pages: number
  checks_parsed: number
  checks_inserted: number
  checks_duplicate: number
  checks_failed: number
  summary_blocks_skipped: number
  /**
   * New effective-dated rate rows this import wrote.
   *
   * ⚠️ **THE SERVER HAS RETURNED THIS SINCE #53 AND NO SURFACE READ IT.** The
   * route's own comment says it is reported "because a backfill upload inserts
   * ZERO checks" — and the saying-out-loud stopped at the API boundary, so the
   * one upload this number exists for still read as "0 inserted, nothing
   * happened". Card 2 renders it unconditionally; see `register-rates`.
   */
  rates_written: number
  report: {
    /** Distinct people the file accounts for, inserted and duplicate together. */
    employees?: number
    inserted?: number
    unknown_codes?: Record<string, number>
    ambiguous_names?: Record<string, string[]>
    union_salary_anomalies?: {
      emp_id: string
      check_number: string | null
      check_date: string | null
    }[]
    failed_checks?: {
      emp_id: string | null
      check_number: string | null
      page: number | null
      why: string
    }[]
    duplicate_checks?: {
      check_number: string | null
      check_date: string | null
      emp_id: string | null
    }[]
    /**
     * What the rate writer did, beyond the headline `rates_written`.
     *
     * `corrected` is a rate CHANGED on an effective date already recorded —
     * a repair of stored data rather than a new row, and the one outcome here
     * that nobody asked for. It is surfaced because a silent repair of a pay
     * rate is worse than an extra line. `no_roster_row` carries employee
     * numbers whose rate could not be stored at all.
     */
    rates?: {
      written: number
      corrected: number
      unchanged: number
      no_roster_row: string[]
    }
  }
}

export async function uploadRegister(file: File) {
  const fd = new FormData()
  fd.append("file", file)
  // See the note on `uploadWeekHours` — same reason, same header, and this is
  // the call that answered 422 in 41 ms on production having delivered 1,156
  // bytes of a 1,708,810-byte register.
  const r = await apiClient.post<RegisterImportResult>(
    `${BASE}/register/upload`,
    fd,
    { headers: { "Content-Type": "multipart/form-data" } },
  )
  return r.data
}


/* ── an employee's payroll status ────────────────────────────────────────
 *
 * ⚠️ **THE FIRST WRITER THESE COLUMNS HAVE EVER HAD.** `payroll_status` and
 * `payroll_status_since` shipped with r234; measured on production
 * 2026-11-21, 0 of 30 employees carried a value, because nothing could set
 * one. The R-115's line 1 falls back to counting checks and says so, and
 * `roster_coverage`'s excused branch had never once been taken.
 */

/** ⚠️ `null` IS NOT `"active"`. `null` means nobody has said; `active` means
 *  somebody looked and said they are working. The R-115's line-1 fallback
 *  turns on exactly that difference, so the client never collapses it. */
export type PayrollEmployeeStatus = "active" | "left" | "workers_comp" | "leave"

export interface StatusChange {
  id: string
  status: PayrollEmployeeStatus
  /** The day the status BEGAN — not the day it was recorded. */
  since: string
  previous_status: PayrollEmployeeStatus | null
  previous_since: string | null
  reason: string
  /** The day somebody typed it in. Routinely months after `since`. */
  changed_at: string | null
  changed_by_user_id: string | null
  changed_by_name: string | null
}

export interface EmployeeStatus {
  employee_id: string
  display_name: string | null
  status: PayrollEmployeeStatus | null
  since: string | null
  history: StatusChange[]
}

export async function getEmployeeStatus(employeeId: string) {
  const r = await apiClient.get<EmployeeStatus>(
    `${BASE}/employees/${encodeURIComponent(employeeId)}/status`,
  )
  return r.data
}

export async function setEmployeeStatus(
  employeeId: string,
  input: { status: PayrollEmployeeStatus; since: string; reason: string },
) {
  const r = await apiClient.put<StatusChange>(
    `${BASE}/employees/${encodeURIComponent(employeeId)}/status`,
    form(input),
    { headers: FORM_HEADERS },
  )
  return r.data
}


/* ── vacation (Payroll 5c) ───────────────────────────────────────────────
 *
 * ⚠️ **BEFORE 5c, VACATION PAY WAS COMPUTED NOWHERE.** The rulebook keys, the
 * engine and the goldens existed; no table, no writer, no surface and no
 * caller. Fourth unprovisioned entrance of the arc.
 */

export interface VacationEntitlement {
  /** ⚠️ `null` IS NOT ZERO. Nobody has a hire date yet, so for most people
   *  this is "not established" and the pane must not render it as "0 left". */
  hours: string | null
  basis: "override" | "service_tiers" | "unavailable"
  source: string | null
  years_of_service: number | null
  why_not: string | null
}

export interface PriorYearBasis {
  year: number
  basis: "registers" | "entered" | "unavailable"
  gross: string | null
  hours: string | null
  source: string | null
  usable: boolean
  /** ⚠️ ALWAYS PRESENT. "Registers cover 2025-11-13 – 2025-12-31 only" is what
   *  turns a refusal into something a person can act on. */
  coverage: string
  covers_year: boolean
  register_gross: string | null
  register_hours: string | null
}

export interface VacationRow {
  id: string
  start_date: string
  end_date: string
  hours: string
  status: "scheduled" | "paid" | "cancelled"
  source: string
}

export interface VacationPaymentRow {
  id: string
  vacation_id: string
  part_index: number
  part_count: number
  week_end_date: string
  vac_pay: string
  vac_bonus: string
  rate: string | null
  hours: string
}

export interface VacationYear {
  employee_id: string
  display_name: string | null
  union_member: boolean
  hire_date: string | null
  year: number
  entitlement: VacationEntitlement
  used_hours: string
  scheduled_hours: string
  /** `null` when the allowance is not known — never a bare number. */
  remaining_hours: string | null
  vacations: VacationRow[]
  payments: VacationPaymentRow[]
  prior_year: PriorYearBasis
}

export interface VacationPayPart {
  index: number
  count: number
  hours: string
  vac_pay: string
  vac_bonus: string
  total: string
}

export interface VacationWorking {
  union: boolean
  hours: string
  rate: string | null
  rate_truncate_dp: number | null
  prior_year_gross: string | null
  prior_year_hours: string | null
  entitlement_hours: string | null
  bonus_year_total: string | null
  vac_total: string
  bonus_total: string
  parts: VacationPayPart[]
}

export interface VacationPayView {
  vacation: VacationRow
  checks: number
  union: boolean | null
  working: VacationWorking | null
  /** ⚠️ A SENTENCE, not a bare null — it names what is missing and who can
   *  supply it. The Focus renders this instead of the working. */
  unavailable: string | null
  already_paid_parts: number
}

export async function getVacationYear(employeeId: string, year?: number) {
  const r = await apiClient.get<VacationYear>(
    `${BASE}/employees/${encodeURIComponent(employeeId)}/vacation`,
    { params: year ? { year } : undefined },
  )
  return r.data
}

export async function addVacation(
  employeeId: string,
  input: { startDate: string; endDate: string; hours: string; source: string },
) {
  const r = await apiClient.post<VacationRow>(
    `${BASE}/employees/${encodeURIComponent(employeeId)}/vacation`,
    form({
      start_date: input.startDate,
      end_date: input.endDate,
      hours: input.hours,
      source: input.source,
    }),
    { headers: FORM_HEADERS },
  )
  return r.data
}

export async function setPriorYear(
  employeeId: string,
  year: number,
  input: { gross: string; hours: string; source: string },
) {
  const r = await apiClient.put(
    `${BASE}/employees/${encodeURIComponent(employeeId)}/prior-year/${year}`,
    form(input),
    { headers: FORM_HEADERS },
  )
  return r.data
}

export async function setEntitlement(
  employeeId: string,
  year: number,
  input: { hours: string; source: string },
) {
  const r = await apiClient.put(
    `${BASE}/employees/${encodeURIComponent(employeeId)}/entitlement/${year}`,
    form(input),
    { headers: FORM_HEADERS },
  )
  return r.data
}

export async function getVacationPay(vacationId: string, checks: number) {
  const r = await apiClient.get<VacationPayView>(
    `${BASE}/vacations/${encodeURIComponent(vacationId)}/pay`,
    { params: { checks } },
  )
  return r.data
}

export async function approveVacationPay(
  vacationId: string,
  input: { checks: number; weekEndDate: string },
) {
  const r = await apiClient.post<{
    vacation: VacationRow
    payments: VacationPaymentRow[]
  }>(
    `${BASE}/vacations/${encodeURIComponent(vacationId)}/approve`,
    form({ checks: String(input.checks), week_end_date: input.weekEndDate }),
    { headers: FORM_HEADERS },
  )
  return r.data
}
