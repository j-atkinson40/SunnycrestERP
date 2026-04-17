// FH tenant API helpers — thin wrapper around the shared apiClient.

import apiClient from "@/lib/api-client"

export interface CaseSummary {
  id: string
  case_number: string
  deceased_name: string
  status: string
  current_step: string
  director_id: string | null
  location_id: string | null
  opened_at: string | null
}

export interface StaircaseStep {
  key: string
  name: string
  status: "completed" | "current" | "pending"
  is_current: boolean
}

export interface NeedsAttentionItem {
  case_id: string
  case_number: string
  deceased_name: string
  reasons: string[]
  days_open: number
  current_step: string
}

export interface UpcomingService {
  case_id: string
  case_number: string
  deceased_name: string
  service_date: string | null
  service_time: string | null
  service_location_name: string | null
  service_type: string | null
}

export interface ActiveCaseBriefRow {
  case_id: string
  case_number: string
  deceased_name: string
  current_step: string
  current_step_label: string
  days_open: number
  director_id: string | null
  location_id: string | null
}

export interface BriefingData {
  active_cases: ActiveCaseBriefRow[]
  needs_attention: NeedsAttentionItem[]
  upcoming_services: UpcomingService[]
}

export const fhApi = {
  listCases: (params?: { status?: string; director_id?: string; location_id?: string; search?: string }) =>
    apiClient.get<CaseSummary[]>("/fh/cases", { params }).then((r) => r.data),

  createCase: (location_id?: string) =>
    apiClient.post<{ id: string; case_number: string }>("/fh/cases", { location_id }).then((r) => r.data),

  getCase: (caseId: string, includeSsn = false) =>
    apiClient.get(`/fh/cases/${caseId}`, { params: { include_ssn: includeSsn } }).then((r) => r.data),

  getStaircase: (caseId: string) =>
    apiClient.get<StaircaseStep[]>(`/fh/cases/${caseId}/staircase`).then((r) => r.data),

  advanceStep: (caseId: string, stepKey: string) =>
    apiClient.post(`/fh/cases/${caseId}/staircase/advance`, { step_key: stepKey }).then((r) => r.data),

  updateDeceased: (caseId: string, payload: Record<string, unknown>) =>
    apiClient.patch(`/fh/cases/${caseId}/deceased`, payload).then((r) => r.data),

  updateService: (caseId: string, payload: Record<string, unknown>) =>
    apiClient.patch(`/fh/cases/${caseId}/service`, payload).then((r) => r.data),

  addInformant: (caseId: string, payload: Record<string, unknown>) =>
    apiClient.post(`/fh/cases/${caseId}/informants`, payload).then((r) => r.data),

  signAuthorization: (caseId: string, informantId: string, method: string) =>
    apiClient.post(`/fh/cases/${caseId}/informants/${informantId}/sign`, null, { params: { method } }).then((r) => r.data),

  listInformants: (caseId: string) =>
    apiClient.get(`/fh/cases/${caseId}/informants`).then((r) => r.data),

  listNotes: (caseId: string) =>
    apiClient.get(`/fh/cases/${caseId}/notes`).then((r) => r.data),

  addNote: (caseId: string, content: string, noteType = "general") =>
    apiClient.post(`/fh/cases/${caseId}/notes`, { content, note_type: noteType }).then((r) => r.data),

  scribeProcess: (caseId: string, transcript: string) =>
    apiClient.post(`/fh/cases/${caseId}/scribe/process`, { transcript }).then((r) => r.data),

  scribeExtract: (caseId: string, transcript: string) =>
    apiClient.post(`/fh/cases/${caseId}/scribe/extract`, { transcript }).then((r) => r.data),

  compileStory: (caseId: string) =>
    apiClient.post(`/fh/cases/${caseId}/story/compile`).then((r) => r.data),

  approveAll: (caseId: string) =>
    apiClient.patch(`/fh/cases/${caseId}/story/approve`).then((r) => r.data),

  briefing: (location_id?: string) =>
    apiClient.get<BriefingData>("/fh/cases/-/briefing", { params: { location_id } }).then((r) => r.data),

  // Cemetery + plot map (FH-1b)
  cemeteryMap: (cemeteryCompanyId: string) =>
    apiClient.get(`/fh/cemetery/${cemeteryCompanyId}/map`).then((r) => r.data),

  reservePlot: (plotId: string, caseId: string) =>
    apiClient.post(`/fh/cemetery/plots/${plotId}/reserve`, { case_id: caseId }).then((r) => r.data),

  completePlotPayment: (plotId: string, caseId: string) =>
    apiClient.post(`/fh/cemetery/plots/${plotId}/complete-payment`, { case_id: caseId }).then((r) => r.data),

  // Network
  networkConnections: () =>
    apiClient.get("/fh/network/connections").then((r) => r.data),

  // Monument catalog
  monumentShapes: () => apiClient.get("/fh/monument/shapes").then((r) => r.data),
  monumentEngravings: (category?: string) =>
    apiClient.get("/fh/monument/engravings", { params: category ? { category } : {} }).then((r) => r.data),
  monumentSuggestForCase: (caseId: string) =>
    apiClient.get(`/fh/monument/suggest/${caseId}`).then((r) => r.data),
}

/** Check whether the current tenant is a funeral home based on company data. */
export function isFuneralHomeTenant(company: { vertical?: string | null; tenant_type?: string | null } | null | undefined): boolean {
  if (!company) return false
  const v = (company.vertical || company.tenant_type || "").toLowerCase()
  return v === "funeral_home" || v === "funeralhome"
}
