/**
 * Calendar PTR consent upgrade UI write-side service client —
 * Phase W-4b Layer 1 Step 4.1.
 *
 * Mirrors backend Pydantic shapes in
 * ``backend/app/api/routes/calendar_consent.py``.
 */

import apiClient from "@/lib/api-client";

export type ConsentValue = "free_busy_only" | "full_details";

export type ConsentState =
  | "default"
  | "pending_outbound"
  | "pending_inbound"
  | "active";

export interface PartnerConsentRow {
  relationship_id: string;
  relationship_type: string;
  partner_tenant_id: string;
  partner_tenant_name: string | null;
  this_side_consent: ConsentValue;
  partner_side_consent: ConsentValue | null;
  state: ConsentState;
  updated_at: string | null;
  updated_by_user_id: string | null;
}

export interface ConsentListResponse {
  partners: PartnerConsentRow[];
}

export interface ConsentTransitionResponse {
  relationship_id: string;
  partner_tenant_id: string;
  prior_state: ConsentState;
  new_state: ConsentState;
}

const BASE = "/calendar/consent";

export async function listConsentStates(): Promise<ConsentListResponse> {
  const r = await apiClient.get<ConsentListResponse>(BASE);
  return r.data;
}

export async function requestUpgrade(
  relationshipId: string,
): Promise<ConsentTransitionResponse> {
  const r = await apiClient.post<ConsentTransitionResponse>(
    `${BASE}/${relationshipId}/request`,
  );
  return r.data;
}

export async function acceptUpgrade(
  relationshipId: string,
): Promise<ConsentTransitionResponse> {
  const r = await apiClient.post<ConsentTransitionResponse>(
    `${BASE}/${relationshipId}/accept`,
  );
  return r.data;
}

export async function revokeUpgrade(
  relationshipId: string,
): Promise<ConsentTransitionResponse> {
  const r = await apiClient.post<ConsentTransitionResponse>(
    `${BASE}/${relationshipId}/revoke`,
  );
  return r.data;
}
