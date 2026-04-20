/**
 * Phase 5 — Public API for the action registry.
 *
 * Importing this module side-effects every per-vertical file below,
 * which populates the singleton registry via `registerActions()`.
 * Once imported, callers use the helpers exported from `registry.ts`:
 *   - `getActionsForVertical()` — render-time `CommandAction[]` for
 *     the current tenant's preset.
 *   - `filterActionsByRole()` — role-gated filter.
 *   - `matchLocalActions()` — fuzzy local matcher for offline
 *     fallback + keyword bootstrapping.
 *   - `getActionsSupportingNLCreation()` — Phase 4 NL overlay source.
 */

import { registerActions } from "./registry";
import { manufacturingActions as manufacturingEntries } from "./manufacturing";
import { funeralHomeActions as funeralHomeEntries } from "./funeral_home";
import { sharedActions as sharedEntries } from "./shared";
import { triageActions as triageEntries } from "./triage";

// Side-effect: populate the singleton at module import time.
registerActions(manufacturingEntries);
registerActions(funeralHomeEntries);
registerActions(sharedEntries);
registerActions(triageEntries);

// Public API re-exports.
export type { ActionRegistryEntry, ActionKind } from "./types";
export {
  type CommandAction,
  type RecentAction,
  getRecentActions,
  addRecentAction,
  registerAction,
  registerActions,
  getAction,
  listAllActions,
  getActionsSupportingNLCreation,
  toCommandAction,
  getActionsForVertical,
  getAllVerticalsActions,
  filterActionsByRole,
  matchLocalActions,
  __resetRegistry,
} from "./registry";

// Raw entry exports for tests. Call sites should prefer
// `getActionsForVertical()` which returns render-time `CommandAction`
// objects filtered and sorted by display_order.
export {
  manufacturingEntries,
  funeralHomeEntries,
  sharedEntries,
  triageEntries,
};
