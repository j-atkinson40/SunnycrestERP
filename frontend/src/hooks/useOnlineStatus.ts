/**
 * Phase 7 — Online/offline detection.
 *
 * Thin wrapper around `navigator.onLine` with `online`/`offline`
 * event listeners. No axios/fetch error integration — browsers
 * already fire these events when connectivity changes, and that's
 * the signal we act on for the global offline banner.
 *
 * Side note: navigator.onLine is imperfect (can be `true` when on
 * a captive-portal wifi that blocks real internet), but it's the
 * simplest honest signal available. Full connectivity detection
 * (periodic backend ping) is post-arc observability territory.
 */

import { useEffect, useState } from "react";

export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState<boolean>(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return online;
}
