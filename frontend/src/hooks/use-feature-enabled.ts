/**
 * Unified feature check — checks both feature flags AND the extension catalog.
 *
 * Components that check for 'funeral_kanban_scheduler' still work exactly as
 * before — they now also check the extension catalog as the source of truth.
 */

import { useFeatureFlag } from "@/contexts/feature-flag-context";
import { useExtensionEnabled } from "@/contexts/extension-context";

/**
 * Returns true if the key is enabled via feature flags OR the extension catalog.
 */
export function useIsFeatureEnabled(key: string): boolean {
  const flagEnabled = useFeatureFlag(key);
  const extEnabled = useExtensionEnabled(key);
  return flagEnabled || extEnabled;
}
