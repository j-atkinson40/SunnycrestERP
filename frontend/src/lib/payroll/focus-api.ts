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

export async function getCurrentWeek() {
  const r = await apiClient.get<CurrentWeek>(`${BASE}/weeks/current`)
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

export interface WeekUploadResult {
  week: { id: string; week_number: number; status: string }
  import: Record<string, unknown>
  summary: Record<string, number>
  flags: { code: string; severity: string; message: string }[]
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
