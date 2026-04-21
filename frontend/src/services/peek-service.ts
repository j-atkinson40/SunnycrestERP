/**
 * Peek API client — follow-up 4 of the UI/UX arc (arc finale).
 *
 * Single endpoint `GET /api/v1/peek/{entity_type}/{entity_id}`.
 * AbortSignal pass-through so the PeekProvider can cancel
 * in-flight fetches when the user closes a peek before the response
 * lands (or rapid-hovers across multiple peek triggers).
 */

import apiClient from "@/lib/api-client";
import type { PeekEntityType, PeekResponse } from "@/types/peek";


export async function fetchPeek(
  entityType: PeekEntityType,
  entityId: string,
  options?: { signal?: AbortSignal },
): Promise<PeekResponse> {
  const resp = await apiClient.get<PeekResponse>(
    `/peek/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
    { signal: options?.signal },
  );
  return resp.data;
}
