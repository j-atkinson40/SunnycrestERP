/**
 * Entity-portal hydration fetch — S-1 (§4.2).
 *
 * Second-call hydration: `/command-bar/query` stays cheap; the card
 * payload comes from this endpoint when a result is HIGHLIGHTED
 * (150ms debounce + abort handled by usePortalHydration).
 */

import apiClient from "@/lib/api-client";
import type { PortalResponse } from "@/types/entity-portal";

export async function fetchEntityPortal(
  entityType: string,
  entityId: string,
  signal?: AbortSignal,
): Promise<PortalResponse> {
  const res = await apiClient.get<PortalResponse>(
    `/command-bar/portal/${entityType}/${entityId}`,
    { signal },
  );
  return res.data;
}
