/**
 * Phase 8e.1 — affinity visit recording with client-side throttle.
 *
 * Fire-and-forget contract: callers invoke `recordVisit(...)` and
 * don't await. Throttle runs on the client side at 60 seconds per
 * (target_type, target_id) per session; server also throttles at
 * 60s as defense-in-depth. Matching the windows avoids client/
 * server throttle divergence surprises.
 *
 * Storage for the throttle bucket is an in-module Map keyed on
 * `${target_type}:${target_id}` — process-local (i.e. per tab).
 * A user with 5 tabs open can record 5 visits for the same target
 * in 60 seconds; the server-side throttle catches the extra 4.
 *
 * Callers:
 *   - PinnedSection pin click
 *   - PinStar toggle → pinned
 *   - Command bar result navigate (with active_space_id)
 *   - AffinityVisitWatcher (URL-change detector for pinned nav /
 *     pinned saved views / pinned triage queues)
 */

import { useCallback } from "react";

import {
  recordAffinityVisit as apiRecordAffinityVisit,
} from "@/services/spaces-service";
import type { AffinityTargetType } from "@/types/spaces";
import { useActiveSpaceId } from "@/contexts/space-context";

// Throttle window — matches server-side _THROTTLE_WINDOW_SECONDS.
const THROTTLE_WINDOW_MS = 60_000;

// Module-scoped bucket. Persists across hook instances within a tab.
// Not persisted across page loads — a reload lets the user record
// the same visit again immediately, which is fine (server still
// throttles if the first one was processed).
const _bucket = new Map<string, number>();

function _key(type: AffinityTargetType, id: string): string {
  return `${type}:${id}`;
}

function _shouldThrottle(type: AffinityTargetType, id: string): boolean {
  const now = Date.now();
  const last = _bucket.get(_key(type, id));
  if (last !== undefined && now - last < THROTTLE_WINDOW_MS) {
    return true;
  }
  _bucket.set(_key(type, id), now);
  return false;
}

export interface UseAffinityVisitResult {
  /**
   * Record a deliberate-intent visit. Fire-and-forget — the caller
   * must NOT await. No-op when no active space is set (affinity
   * requires a space context) or when throttled.
   */
  recordVisit: (args: {
    targetType: AffinityTargetType;
    targetId: string;
    /** Optional override — defaults to the user's active space. */
    spaceId?: string;
  }) => void;
}

/**
 * Hook wrapping the fire-and-forget affinity visit API. Callers
 * invoke `recordVisit({...})` without awaiting. Behavior:
 *
 *   1. If no active space is set, no-op. Affinity only makes sense
 *      with a space context.
 *   2. If the same (target_type, target_id) was recorded in the
 *      last 60 seconds by this tab, no-op (client throttle).
 *   3. Otherwise, fire POST /spaces/affinity/visit asynchronously.
 *      Errors are swallowed.
 */
export function useAffinityVisit(): UseAffinityVisitResult {
  const activeSpaceId = useActiveSpaceId();

  const recordVisit = useCallback(
    (args: {
      targetType: AffinityTargetType;
      targetId: string;
      spaceId?: string;
    }) => {
      const spaceId = args.spaceId ?? activeSpaceId;
      if (!spaceId) return;
      if (!args.targetId) return;
      if (_shouldThrottle(args.targetType, args.targetId)) return;

      apiRecordAffinityVisit({
        space_id: spaceId,
        target_type: args.targetType,
        target_id: args.targetId,
      });
    },
    [activeSpaceId],
  );

  return { recordVisit };
}

/** Test-only — clear the module-scoped throttle bucket. */
export function __clearAffinityThrottleForTests(): void {
  _bucket.clear();
}
