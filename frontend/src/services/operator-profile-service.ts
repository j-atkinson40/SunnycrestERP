/**
 * Phase W-4a operator profile API client.
 *
 * Two endpoints: GET to read current state, PATCH for partial updates
 * (auto-save friendly). Pydantic `model_fields_set` semantics
 * preserved on the wire — only fields explicitly included in the
 * request body are mutated server-side; omitting a field leaves it
 * untouched.
 *
 * Per BRIDGEABLE_MASTER §3.26.3 — drives Pulse composition once
 * Phase W-4a Commit 3 ships the composition engine.
 */

import apiClient from "@/lib/api-client"
import type {
  OperatorProfile,
  OperatorProfileUpdateRequest,
} from "@/types/operator-profile"


const BASE_URL = "/operator-profile"


export async function getOperatorProfile(): Promise<OperatorProfile> {
  const response = await apiClient.get<OperatorProfile>(BASE_URL)
  return response.data
}


export async function updateOperatorProfile(
  body: OperatorProfileUpdateRequest,
): Promise<OperatorProfile> {
  const response = await apiClient.patch<OperatorProfile>(BASE_URL, body)
  return response.data
}
