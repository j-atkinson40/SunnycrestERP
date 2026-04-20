/**
 * Phase 6 — briefing v2 API client.
 *
 * 7 endpoints under `/api/v1/briefings/v2/*`. Each function unwraps
 * the axios `response.data`. Legacy endpoints (`/briefings/briefing`,
 * `/briefings/action-items`) are NOT consumed here — they stay wired
 * to `morning-briefing-card.tsx` per the coexist strategy.
 */

import apiClient from "@/lib/api-client";
import type {
  BriefingPreferences,
  BriefingSummary,
  BriefingType,
} from "@/types/briefing";

const BASE = "/briefings/v2";

export async function listBriefings(params?: {
  briefing_type?: BriefingType;
  limit?: number;
}): Promise<BriefingSummary[]> {
  const { data } = await apiClient.get<BriefingSummary[]>(BASE, { params });
  return data;
}

export async function getLatestBriefing(
  briefingType: BriefingType = "morning",
): Promise<BriefingSummary | null> {
  const { data } = await apiClient.get<BriefingSummary | null>(
    `${BASE}/latest`,
    { params: { briefing_type: briefingType } },
  );
  return data ?? null;
}

export async function getBriefing(id: string): Promise<BriefingSummary> {
  const { data } = await apiClient.get<BriefingSummary>(
    `${BASE}/${encodeURIComponent(id)}`,
  );
  return data;
}

export async function markBriefingRead(
  id: string,
): Promise<BriefingSummary> {
  const { data } = await apiClient.post<BriefingSummary>(
    `${BASE}/${encodeURIComponent(id)}/mark-read`,
  );
  return data;
}

export async function generateBriefing(
  briefingType: BriefingType,
  deliver = false,
): Promise<BriefingSummary> {
  const { data } = await apiClient.post<BriefingSummary>(`${BASE}/generate`, {
    briefing_type: briefingType,
    deliver,
  });
  return data;
}

export async function getPreferences(): Promise<BriefingPreferences> {
  const { data } = await apiClient.get<BriefingPreferences>(
    `${BASE}/preferences`,
  );
  return data;
}

export async function updatePreferences(
  updates: Partial<BriefingPreferences>,
): Promise<BriefingPreferences> {
  const { data } = await apiClient.patch<BriefingPreferences>(
    `${BASE}/preferences`,
    updates,
  );
  return data;
}
