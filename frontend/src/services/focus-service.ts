/**
 * Focus primitive API client — Phase A Session 4.
 *
 * Five endpoints under `/api/v1/focus`. Mirrors
 * `backend/app/api/routes/focus.py`.
 *
 * Frontend doesn't see the 3-tier resolution (active → recent →
 * default → null) — the GET /layout and POST /open responses carry
 * `source` metadata for diagnostics but the caller just uses
 * `layout_state` directly.
 */

import apiClient from "@/lib/api-client"
import type { LayoutState } from "@/contexts/focus-registry"


export type LayoutSource = "active" | "recent" | "default" | null


export interface FocusSessionDTO {
  id: string
  focus_type: string
  layout_state: Record<string, unknown>
  is_active: boolean
  opened_at: string
  closed_at: string | null
  last_interacted_at: string
}


export interface FocusLayoutResponse {
  layout_state: Record<string, unknown> | null
  source: LayoutSource
}


export interface FocusOpenResponse {
  session: FocusSessionDTO
  layout_state: Record<string, unknown> | null
  source: LayoutSource
}


/** Resolve the 3-tier layout for this user + focus_type. */
export async function fetchFocusLayout(
  focusType: string,
): Promise<FocusLayoutResponse> {
  const r = await apiClient.get<FocusLayoutResponse>(
    `/focus/${focusType}/layout`,
  )
  return r.data
}


/** Open (or resume) an active session. Returns session + layout in
 *  one round-trip so the frontend can seed its state in a single
 *  call. */
export async function openFocusSession(
  focusType: string,
): Promise<FocusOpenResponse> {
  const r = await apiClient.post<FocusOpenResponse>(
    `/focus/${focusType}/open`,
  )
  return r.data
}


/** Write layout state to the session. Ownership enforced server-side. */
export async function updateFocusLayout(
  sessionId: string,
  layoutState: LayoutState,
): Promise<FocusSessionDTO> {
  const r = await apiClient.patch<FocusSessionDTO>(
    `/focus/sessions/${sessionId}/layout`,
    { layout_state: layoutState },
  )
  return r.data
}


/** Close an active session. Idempotent. */
export async function closeFocusSession(
  sessionId: string,
): Promise<FocusSessionDTO> {
  const r = await apiClient.post<FocusSessionDTO>(
    `/focus/sessions/${sessionId}/close`,
  )
  return r.data
}


/** Recently-closed sessions across all focus_types. Powers Cmd+K
 *  history surface. */
export async function listRecentFocusSessions(
  limit: number = 10,
): Promise<FocusSessionDTO[]> {
  const r = await apiClient.get<FocusSessionDTO[]>("/focus/recent", {
    params: { limit },
  })
  return r.data
}
