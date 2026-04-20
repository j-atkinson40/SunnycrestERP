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
  CreateSpaceBody,
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
