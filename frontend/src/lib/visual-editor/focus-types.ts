/**
 * Focus-type taxonomy + core-slug→focus-type map (sub-arc F-1).
 *
 * Per investigation 2026-05-18-focus-builder Q-2 + Q-3 (LOCKED b/b):
 *   - Focus-type taxonomy is a curated frontend constant. Adding a
 *     new focus-type = one row here + the mapping table below.
 *   - Each core is classified into a focus-type via
 *     CORE_SLUG_TO_FOCUS_TYPE; unmapped cores fall back to "production"
 *     (Q-7 surfaced "Other" but the canonical fallback we ship in F-1
 *     is "production" per the prompt's locked decision; tree-build can
 *     still bucket truly-orphan cores into an "Other" sub-group via
 *     metadata if desired by the consumer).
 *
 * Vertical-association is NOT part of focus-type taxonomy — verticals
 * are first-class registry rows (verticals.slug). Focus-types are
 * UX-level grouping inside a vertical's subtree.
 */

import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"


export const FOCUS_TYPES = [
  { id: "decision", label: "Decision" },
  { id: "coordination", label: "Coordination" },
  { id: "production", label: "Production" },
  { id: "triage", label: "Triage" },
  { id: "scribe", label: "Scribe" },
] as const

export type FocusType = (typeof FOCUS_TYPES)[number]["id"]


/**
 * Stable lookup of core_slug → FocusType. Cores not present here
 * fall back to "production" (the canonical default per prompt).
 *
 * Adding a new core = (a) ship the platform-default core row in the
 * focus_cores table via seed, (b) add the core_slug → FocusType row
 * here.
 */
export const CORE_SLUG_TO_FOCUS_TYPE: Record<string, FocusType> = {
  "scheduling-kanban": "production",
  "scheduling-kanban-core": "production",
}


export function focusTypeForCore(core: CoreRecord): FocusType {
  return CORE_SLUG_TO_FOCUS_TYPE[core.core_slug] ?? "production"
}


export function focusTypeLabel(focusType: FocusType): string {
  return FOCUS_TYPES.find((ft) => ft.id === focusType)?.label ?? "Other"
}
