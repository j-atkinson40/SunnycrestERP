/**
 * Phase 7 — first-run onboarding touches (server-side, cross-device).
 *
 * Unlike `HelpTooltip` (device-local via localStorage), this hook
 * persists dismissals server-side in `User.preferences.onboarding_touches_shown`.
 * A tooltip dismissed on desktop stays dismissed on mobile.
 *
 * Contract:
 *   const { shouldShow, dismiss } = useOnboardingTouch("command_bar_intro");
 *
 *   - `shouldShow` — true when the tooltip hasn't been dismissed yet.
 *     False while loading (we never flash before we know).
 *   - `dismiss()` — marks dismissed server-side. Optimistic: local state
 *     updates immediately; server call is fire-and-forget.
 *
 * The server-side list is fetched once per session + cached in a
 * module-scoped promise so 5 tooltips on 5 different pages don't
 * hammer the endpoint.
 */

import { useCallback, useEffect, useState } from "react";
import apiClient from "@/lib/api-client";

interface TouchesResponse {
  shown: string[];
}

let _sessionCache: Promise<Set<string>> | null = null;
// Local source-of-truth mirror so optimistic dismiss() updates
// propagate to other hook instances without another fetch.
let _localMirror: Set<string> | null = null;
const _listeners = new Set<() => void>();

function _notify() {
  for (const l of _listeners) l();
}

async function _loadShown(): Promise<Set<string>> {
  if (_localMirror) return _localMirror;
  if (!_sessionCache) {
    _sessionCache = apiClient
      .get<TouchesResponse>("/onboarding-touches")
      .then((r) => {
        const set = new Set(r.data.shown ?? []);
        _localMirror = set;
        return set;
      })
      .catch(() => {
        // Fail open — if we can't reach the API, don't block the UI.
        const empty = new Set<string>();
        _localMirror = empty;
        return empty;
      });
  }
  return _sessionCache;
}

export interface UseOnboardingTouchResult {
  shouldShow: boolean;
  dismiss: () => void;
}

export function useOnboardingTouch(touchKey: string): UseOnboardingTouchResult {
  const [shouldShow, setShouldShow] = useState<boolean>(false);
  const [loaded, setLoaded] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    void _loadShown().then((set) => {
      if (cancelled) return;
      setShouldShow(!set.has(touchKey));
      setLoaded(true);
    });
    const listener = () => {
      if (cancelled) return;
      setShouldShow(!_localMirror?.has(touchKey));
    };
    _listeners.add(listener);
    return () => {
      cancelled = true;
      _listeners.delete(listener);
    };
  }, [touchKey]);

  const dismiss = useCallback(() => {
    // Optimistic: update local state + mirror immediately.
    if (!_localMirror) _localMirror = new Set();
    _localMirror.add(touchKey);
    setShouldShow(false);
    _notify();
    // Fire-and-forget server write.
    void apiClient
      .post(`/onboarding-touches/${encodeURIComponent(touchKey)}`)
      .catch(() => {
        // Rollback is deliberately NOT done — a second client fetch
        // will see the unchanged server state if the write failed,
        // and the user's local dismissal is preserved for the session.
      });
  }, [touchKey]);

  // While loading, shouldShow stays false to avoid flashing.
  return { shouldShow: loaded && shouldShow, dismiss };
}

/**
 * Test-only: clears the session cache so a fresh fetch occurs.
 * Not exported via barrel — accessed via direct import in tests.
 */
export function __resetOnboardingTouchCacheForTests() {
  _sessionCache = null;
  _localMirror = null;
}
