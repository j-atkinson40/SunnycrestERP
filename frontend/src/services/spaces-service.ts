/**
 * Spaces API client.
 *
 * Ten endpoints under `/api/v1/spaces`. Mirrors
 * `backend/app/api/routes/spaces.py`. Live queries, no local
 * cache — spaces change rarely but react to role updates and
 * mutation from other tabs (space pin added in another window
 * should be visible on next mount).
 */

import apiClient from "@/lib/api-client";
import type {
  AddPinBody,
  AffinityClearResponse,
  AffinityCountResponse,
  AffinityVisitBody,
  AffinityVisitResponse,
  CreateSpaceBody,
  ReapplyDefaultsResponse,
  ResolvedPin,
  Space,
  SpacesListResponse,
  UpdateSpaceBody,
} from "@/types/spaces";

export async function listSpaces(): Promise<SpacesListResponse> {
  const r = await apiClient.get<SpacesListResponse>("/spaces");
  return r.data;
}

export async function getSpace(spaceId: string): Promise<Space> {
  const r = await apiClient.get<Space>(`/spaces/${spaceId}`);
  return r.data;
}

export async function createSpace(body: CreateSpaceBody): Promise<Space> {
  const r = await apiClient.post<Space>("/spaces", body);
  return r.data;
}

export async function updateSpace(
  spaceId: string,
  body: UpdateSpaceBody,
): Promise<Space> {
  const r = await apiClient.patch<Space>(`/spaces/${spaceId}`, body);
  return r.data;
}

export async function deleteSpace(spaceId: string): Promise<void> {
  await apiClient.delete(`/spaces/${spaceId}`);
}

export async function activateSpace(spaceId: string): Promise<Space> {
  const r = await apiClient.post<Space>(`/spaces/${spaceId}/activate`);
  return r.data;
}

export async function reorderSpaces(
  spaceIds: string[],
): Promise<SpacesListResponse> {
  const r = await apiClient.post<SpacesListResponse>("/spaces/reorder", {
    space_ids: spaceIds,
  });
  return r.data;
}

export async function addPin(
  spaceId: string,
  body: AddPinBody,
): Promise<ResolvedPin> {
  const r = await apiClient.post<ResolvedPin>(
    `/spaces/${spaceId}/pins`,
    body,
  );
  return r.data;
}

export async function removePin(
  spaceId: string,
  pinId: string,
): Promise<void> {
  await apiClient.delete(`/spaces/${spaceId}/pins/${pinId}`);
}

export async function reorderPins(
  spaceId: string,
  pinIds: string[],
): Promise<Space> {
  const r = await apiClient.post<Space>(
    `/spaces/${spaceId}/pins/reorder`,
    { pin_ids: pinIds },
  );
  return r.data;
}

/**
 * Phase 8e — opt-in re-run of Phase 2 (saved_views) + Phase 3
 * (spaces) + Phase 6 (briefings) role-based seeding for the caller.
 * Idempotent via the underlying seed functions' per-role
 * preferences arrays. Returns per-subsystem counts of new rows
 * created.
 */
export async function reapplyDefaults(): Promise<ReapplyDefaultsResponse> {
  const r = await apiClient.post<ReapplyDefaultsResponse>(
    "/spaces/reapply-defaults",
  );
  return r.data;
}

// ── Phase 8e.1 — affinity endpoints ─────────────────────────────────

/**
 * Fire-and-forget affinity visit record. Callers do NOT await — the
 * UI should never block on this write. Errors are swallowed to
 * honor the fire-and-forget contract; brief server downtime simply
 * loses the signal for that interaction (acceptable — affinity is
 * a signal, not transactional state).
 */
export function recordAffinityVisit(body: AffinityVisitBody): void {
  // Deliberately not returning the promise. Don't await.
  apiClient
    .post<AffinityVisitResponse>("/spaces/affinity/visit", body)
    .catch(() => {
      // Silent — fire-and-forget.
    });
}

/**
 * Returns the count of active affinity signals tracked for the
 * caller. Powers the "N tracked signals" counter on /settings/spaces.
 * Optional space_id narrows to a single space.
 */
export async function getAffinityCount(
  spaceId?: string,
): Promise<AffinityCountResponse> {
  const query = spaceId ? `?space_id=${encodeURIComponent(spaceId)}` : "";
  const r = await apiClient.get<AffinityCountResponse>(
    `/spaces/affinity/count${query}`,
  );
  return r.data;
}

/**
 * "Clear command bar learning history" action. Returns count
 * deleted. Optional space_id narrows to a single space.
 */
export async function clearAffinityHistory(
  spaceId?: string,
): Promise<AffinityClearResponse> {
  const query = spaceId ? `?space_id=${encodeURIComponent(spaceId)}` : "";
  const r = await apiClient.delete<AffinityClearResponse>(
    `/spaces/affinity${query}`,
  );
  return r.data;
}
