/**
 * The three admin-only payroll setup endpoints, typed.
 *
 * ⚠️ **ALL THREE ALREADY EXISTED.** Nothing here is a new capability — the
 * switch, the register upload and the roster reconcile shipped with Payroll 3
 * and 4 and have been reachable only by a Terminal snippet carrying an admin
 * bearer token. This module and its page replace that snippet, which is the
 * whole of the change: a credential that has to be pasted into a shell is a
 * credential that transits something, and the browser session already holds
 * one legitimately.
 *
 * ⚠️ **TWO OF THE THREE ARE `require_admin`; THE UPLOAD IS NOT.** The switch
 * (GET + PUT) and the reconcile are admin-only on the server. The register
 * upload is `payroll.upload`, because Susan pulls the Check Register from
 * Payentry today and importing it is the same act. The PAGE is admin-only
 * regardless, so the upload card is reachable here by an admin and also
 * reachable by Susan inside the weekly Focus — that is deliberate, not a gap.
 *
 * ⚠️ **FORM-ENCODED, EXPLICITLY.** Both writes declare `Form(...)` on the
 * server. `api-client.ts` sets a JSON `Content-Type` default that beats axios's
 * own URLSearchParams inference, so a request that plainly contains the fields
 * arrives with every one of them reported missing. Found once by the same
 * request succeeding under curl and failing from the page.
 */

import apiClient from "@/lib/api-client"
import type { RegisterImportResult } from "@/lib/payroll/focus-api"

const BASE = "/payroll-reports"

const FORM_HEADERS = {
  "Content-Type": "application/x-www-form-urlencoded",
} as const

// ── (1) the data switch ──────────────────────────────────────────────────────

export interface DataSwitchState {
  setting: string
  enabled: boolean
}

export interface DataSwitchWriteResult extends DataSwitchState {
  /** False on a no-op write. The server records no audit row for one, and the
   *  page says "it was already on" rather than claiming a change. */
  changed: boolean
}

export async function getDataEnabled() {
  const r = await apiClient.get<DataSwitchState>(`${BASE}/settings/data-enabled`)
  return r.data
}

export async function setDataEnabled(enabled: boolean) {
  const body = new URLSearchParams()
  body.append("enabled", String(enabled))
  const r = await apiClient.put<DataSwitchWriteResult>(
    `${BASE}/settings/data-enabled`,
    body,
    { headers: FORM_HEADERS },
  )
  return r.data
}

// ── (3) the roster reconcile ─────────────────────────────────────────────────

export interface ReconcileProposal {
  emp_id: string
  field: string
  register_says: string
  roster_says: string | null
  /** `fill` (roster had nothing), `agree` (already says this), or `conflict`
   *  (they disagree — returned and never written). */
  verdict: string
  why: string
}

export interface ReconcileResult {
  employees_seen: number
  union_members_proved: number
  applied: ReconcileProposal[]
  proposals: ReconcileProposal[]
  conflicts: ReconcileProposal[]
  ambiguous_names: Record<string, string[]>
  dry_run: boolean
}

/**
 * Dry run unless `apply` is true, and even then the server writes only `fill`
 * proposals — never a value that would overwrite a curated fact.
 *
 * ⚠️ The page ALWAYS runs the dry run first and shows it. "Create employee
 * list from register" with no preview would be a button whose effect is only
 * knowable afterwards.
 */
export async function reconcileRegisterPeople(apply: boolean) {
  const body = new URLSearchParams()
  body.append("apply", String(apply))
  const r = await apiClient.post<ReconcileResult>(
    `${BASE}/register/people/reconcile`,
    body,
    { headers: FORM_HEADERS },
  )
  return r.data
}

// ── the import log — so a page can CHECK rather than guess ───────────────────

export interface RegisterImportRow {
  import_id: string
  filename: string | null
  pages: number | null
  checks_parsed: number | null
  checks_inserted: number | null
  checks_duplicate: number | null
  checks_failed: number | null
  created_at: string | null
  report: RegisterImportResult["report"]
}

/**
 * Recent register imports, newest first.
 *
 * ⚠️ **FOR THE CASE WHERE THE CLIENT'S OWN ACCOUNT IS WORTH LEAST.** A CORS
 * rejection, a timeout or a reset on the RETURN leg gives the browser an error
 * for work the server may already have committed. The server's record is the
 * only trustworthy account of whether a request arrived, so when no response
 * comes back the page asks this instead of asserting that nothing changed.
 */
export async function listRegisterImports(limit = 5) {
  const r = await apiClient.get<{ imports: RegisterImportRow[]; count: number }>(
    `${BASE}/register/imports`,
    { params: { limit } },
  )
  return r.data
}

export type { RegisterImportResult }
