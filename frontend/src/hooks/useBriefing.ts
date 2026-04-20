/**
 * Phase 6 — useBriefing hook (Phase 7: adds auto-retry-once on failure).
 *
 * Single-source of truth for the latest briefing on any page that
 * wants to display it. Returns `{briefing, loading, error, reload}`.
 *
 * Phase 7 — wraps `useRetryableFetch` so transient failures self-heal
 * once before bothering the user. The BriefingPage component also
 * exposes a "Regenerate" button that bypasses retry logic by calling
 * `generateBriefing()` directly and then `reload()`.
 */

import { useMemo } from "react";
import { getLatestBriefing } from "@/services/briefing-service";
import { useRetryableFetch } from "@/hooks/useRetryableFetch";
import type { BriefingSummary, BriefingType } from "@/types/briefing";

export interface UseBriefingResult {
  briefing: BriefingSummary | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useBriefing(
  briefingType: BriefingType = "morning",
): UseBriefingResult {
  const deps = useMemo(() => [briefingType], [briefingType]);
  const { data, loading, error, reload } = useRetryableFetch<
    BriefingSummary | null
  >(() => getLatestBriefing(briefingType), deps);

  return { briefing: data ?? null, loading, error, reload };
}
