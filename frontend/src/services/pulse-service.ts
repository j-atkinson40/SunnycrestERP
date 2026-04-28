/**
 * Phase W-4a Pulse API client.
 *
 *   GET  /api/v1/pulse/composition[?refresh=true]
 *   POST /api/v1/pulse/signals/dismiss
 *   POST /api/v1/pulse/signals/navigate
 *
 * Tenant + user scoping enforced server-side via the auth token —
 * these requests never carry user_id / company_id.
 */

import apiClient from "@/lib/api-client"
import type {
  DismissSignalRequest,
  LayerName,
  NavigateSignalRequest,
  PulseComposition,
  TimeOfDaySignal,
} from "@/types/pulse"


const BASE = "/pulse"


export async function fetchPulseComposition(
  refresh = false,
): Promise<PulseComposition> {
  const url = refresh
    ? `${BASE}/composition?refresh=true`
    : `${BASE}/composition`
  const response = await apiClient.get<PulseComposition>(url)
  return response.data
}


/**
 * Fire-and-forget signal write. Errors are swallowed (signal
 * tracking must never block UX); a server failure here means a
 * future Tier 2 algorithm has slightly less data — not a user-
 * facing concern.
 */
export async function recordDismiss(
  componentKey: string,
  layer: LayerName,
  timeOfDay: TimeOfDaySignal,
  workAreasAtDismiss?: string[],
): Promise<void> {
  const body: DismissSignalRequest = {
    component_key: componentKey,
    layer,
    time_of_day: timeOfDay,
    ...(workAreasAtDismiss
      ? { work_areas_at_dismiss: workAreasAtDismiss }
      : {}),
  }
  try {
    await apiClient.post(`${BASE}/signals/dismiss`, body)
  } catch {
    // Swallow — signal failures don't block UX.
  }
}


export async function recordNavigation(
  fromComponentKey: string,
  toRoute: string,
  dwellTimeSeconds: number,
  layer: LayerName,
): Promise<void> {
  const body: NavigateSignalRequest = {
    from_component_key: fromComponentKey,
    to_route: toRoute,
    dwell_time_seconds: dwellTimeSeconds,
    layer,
  }
  try {
    await apiClient.post(`${BASE}/signals/navigate`, body)
  } catch {
    // Swallow per fire-and-forget contract.
  }
}
