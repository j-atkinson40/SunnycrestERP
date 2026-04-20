/**
 * Phase 7 — Retryable async-fetch hook.
 *
 * Generic wrapper for "run this async, auto-retry-once on failure,
 * expose retry button for manual second attempt." Used on surfaces
 * that load expensive-to-regenerate content (briefings) where we want
 * to recover from transient failures before bothering the user.
 *
 * Contract:
 *   - `fn` is an async function that returns T. Called on mount + on
 *     manual retry.
 *   - First failure triggers one automatic retry after ~1s backoff.
 *   - Second failure surfaces `error` for the UI + enables the user
 *     retry via `reload()`.
 *   - `reload()` is idempotent — safe to call during in-flight.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const AUTO_RETRY_DELAY_MS = 1000;

export interface UseRetryableFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** Manual retry trigger — resets state + re-runs. */
  reload: () => Promise<void>;
  /** True while an automatic retry is in flight. */
  isAutoRetrying: boolean;
}

export function useRetryableFetch<T>(
  fn: () => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
): UseRetryableFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAutoRetrying, setIsAutoRetrying] = useState(false);
  const timerRef = useRef<number | null>(null);
  // Guard against stale setState after unmount.
  const mountedRef = useRef(true);
  // Keep fn stable across renders — callers rarely memoize.
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async (isAutoRetry: boolean) => {
    setLoading(true);
    setError(null);
    if (isAutoRetry) setIsAutoRetrying(true);
    try {
      const result = await fnRef.current();
      if (!mountedRef.current) return;
      setData(result);
      setError(null);
    } catch (e) {
      if (!mountedRef.current) return;
      const msg = e instanceof Error ? e.message : "Request failed";
      if (!isAutoRetry) {
        // First failure — schedule an auto-retry-once.
        if (timerRef.current !== null) {
          window.clearTimeout(timerRef.current);
        }
        timerRef.current = window.setTimeout(() => {
          timerRef.current = null;
          void run(true);
        }, AUTO_RETRY_DELAY_MS);
        // Keep loading=true until the auto-retry completes.
        return;
      }
      // Second failure — surface to user.
      setError(msg);
    } finally {
      if (mountedRef.current) {
        if (isAutoRetry) setIsAutoRetrying(false);
        setLoading(false);
      }
    }
  }, []);

  const reload = useCallback(async () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    await run(false);
  }, [run]);

  useEffect(() => {
    mountedRef.current = true;
    void run(false);
    return () => {
      mountedRef.current = false;
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, reload, isAutoRetrying };
}
