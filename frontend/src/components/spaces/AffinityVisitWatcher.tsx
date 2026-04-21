/**
 * Phase 8e.1 — AffinityVisitWatcher.
 *
 * Mounted once inside SpaceProvider (at app root, on the tenant
 * branch). Watches `useLocation().pathname` changes; when a route
 * change matches a pinned target in the active space, fires a
 * fire-and-forget affinity visit.
 *
 * Matching rules (matches backend `_affinity_factor_for_result`):
 *   - nav_item pin with target `/x`: pathname starts with `/x`
 *     (so `/cases` also matches `/cases/123/edit`).
 *   - saved_view pin with target `<uuid>`: pathname equals
 *     `/saved-views/<uuid>` exactly (no prefix match — a user
 *     viewing a different saved view isn't visiting THIS one).
 *   - triage_queue pin with target `<queue_id>`: pathname equals
 *     `/triage/<queue_id>` exactly.
 *
 * Anti-triggers (per Phase 8e.1 audit):
 *   - Nav to a pin target AFTER unpinning: skipped (the match
 *     looks at the CURRENT pin set; if unpinned, no match).
 *   - Route change within a matched nav target (deeper path):
 *     counts as one visit (starts-with match). Client throttle
 *     prevents every sub-navigation from recording.
 *
 * Does not render anything; returns null.
 */

import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

import { useSpaces } from "@/contexts/space-context";
import { useAffinityVisit } from "@/hooks/useAffinityVisit";
import type { AffinityTargetType, ResolvedPin } from "@/types/spaces";

/** Compute the (targetType, targetId) if the pathname matches a
 *  pinned target in the active space. Returns null on no match. */
function matchPinnedRoute(
  pathname: string,
  pins: ResolvedPin[],
): { targetType: AffinityTargetType; targetId: string } | null {
  for (const pin of pins) {
    if (pin.unavailable) continue;
    if (pin.pin_type === "nav_item") {
      // Starts-with match so /cases matches /cases, /cases/X, etc.
      // Careful with `/` — we require either exact match or a
      // trailing slash / deeper segment so `/cases` doesn't
      // match `/casebook`.
      if (
        pathname === pin.target_id ||
        pathname.startsWith(`${pin.target_id}/`)
      ) {
        return { targetType: "nav_item", targetId: pin.target_id };
      }
    } else if (pin.pin_type === "saved_view") {
      // Exact match on /saved-views/<id>
      const expected = `/saved-views/${pin.target_id}`;
      if (pathname === expected) {
        return { targetType: "saved_view", targetId: pin.target_id };
      }
      // Also match on the resolved saved_view_id (target_id for
      // seed-key pins is "" placeholder until resolved).
      if (pin.saved_view_id) {
        const expected2 = `/saved-views/${pin.saved_view_id}`;
        if (pathname === expected2) {
          return {
            targetType: "saved_view",
            targetId: pin.saved_view_id,
          };
        }
      }
    } else if (pin.pin_type === "triage_queue") {
      const expected = `/triage/${pin.target_id}`;
      if (pathname === expected) {
        return { targetType: "triage_queue", targetId: pin.target_id };
      }
    }
  }
  return null;
}

export function AffinityVisitWatcher() {
  const { activeSpace } = useSpaces();
  const { recordVisit } = useAffinityVisit();
  const location = useLocation();

  // Debounce against React strict-mode double-invocation in dev
  // by remembering the last-recorded path. Not a throttle — the
  // useAffinityVisit hook handles time-based throttling.
  const lastPathRef = useRef<string | null>(null);

  useEffect(() => {
    if (!activeSpace) return;
    const path = location.pathname;
    if (lastPathRef.current === path) return;
    lastPathRef.current = path;

    const match = matchPinnedRoute(path, activeSpace.pins);
    if (match) {
      recordVisit({
        targetType: match.targetType,
        targetId: match.targetId,
      });
    }
  }, [activeSpace, location.pathname, recordVisit]);

  return null;
}

/** Exported for unit tests — tests can call directly without mounting. */
export { matchPinnedRoute as __matchPinnedRouteForTests };
