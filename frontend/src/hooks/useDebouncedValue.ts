/**
 * useDebouncedValue — return a value that lags the input by `delayMs`.
 *
 * Ships with follow-up 3 of the UI/UX arc for the saved-view builder
 * live preview. Reusable anywhere a rapidly-changing value should
 * drive an expensive downstream effect (network call, computation)
 * without firing on every keystroke.
 *
 * Contract:
 *   - `value` is re-projected into `debouncedValue` only when it has
 *     remained unchanged for `delayMs` since the last change.
 *   - Deep equality is deliberately NOT used — callers pass a value
 *     whose identity changes when it should trigger a re-fire (e.g.
 *     a new config object on every edit). If a caller wants
 *     "fire only when content changes", pass a stable serialization
 *     (JSON.stringify or a fingerprint) as the `value` arg instead.
 *   - Unmount clears the pending timer (no setState on unmounted).
 *
 * Post-arc: migration of existing ad-hoc setTimeout debouncers
 * (cemetery-picker, funeral-home-picker, cemetery-name-autocomplete,
 * useDashboard) onto this hook is explicitly NOT in this follow-up's
 * scope — they rewrite when next touched for unrelated reasons.
 */

import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebounced(value);
    }, delayMs);
    return () => {
      window.clearTimeout(handle);
    };
  }, [value, delayMs]);

  return debounced;
}
