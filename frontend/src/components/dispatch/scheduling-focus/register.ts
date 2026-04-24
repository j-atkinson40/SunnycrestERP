/**
 * Funeral Scheduling Focus registration — Phase B Session 4 Phase 4.2.
 *
 * Side-effect module: importing this file registers the Focus in the
 * singleton registry so `useFocus().open("funeral-scheduling", ...)`
 * resolves to the SchedulingKanbanCore. Same pattern as the Phase A
 * seed in focus-registry.ts for the `test-<mode>` stubs.
 *
 * Imported once at app bootstrap (see App.tsx) alongside other
 * registries that follow the side-effect-on-import pattern.
 */

import { registerFocus } from "@/contexts/focus-registry"

import { SchedulingKanbanCore } from "./SchedulingKanbanCore"


registerFocus({
  id: "funeral-scheduling",
  mode: "kanban",
  displayName: "Funeral Scheduling",
  coreComponent: SchedulingKanbanCore,
  // Phase 4.2 doesn't ship pins (canvas widgets) — ancillary pin lands
  // in Phase 4.3. No defaultLayout configured; Focus primitive
  // handles the empty-widgets case gracefully (core renders
  // full-width with no pins around it).
})
