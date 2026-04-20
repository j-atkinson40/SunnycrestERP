/**
 * Phase 7 — Global offline banner.
 *
 * Mounted at the App root (inside CommandBarProvider) so every
 * tenant surface inherits the banner. Displays as a thin
 * warning-tinted strip at the top when `navigator.onLine` flips to
 * false; disappears when connectivity restores.
 *
 * Scope boundary: this is event-based (online/offline browser events)
 * — not a proactive connectivity probe. Real-world flaky wifi
 * detection is post-arc observability.
 */

import { WifiOff } from "lucide-react";
import { useOnlineStatus } from "@/hooks/useOnlineStatus";

export function OfflineBanner() {
  const online = useOnlineStatus();
  if (online) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="offline-banner"
      className="fixed left-0 right-0 top-0 z-[70] flex items-center justify-center gap-2 bg-amber-500 px-3 py-1.5 text-xs font-medium text-amber-950 shadow"
    >
      <WifiOff className="h-3.5 w-3.5" aria-hidden="true" />
      <span>
        You appear to be offline. Changes will sync when reconnected.
      </span>
    </div>
  );
}
