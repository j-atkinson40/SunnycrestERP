/**
 * Bridgeable Admin Visual Editor — Registry Introspection API.
 *
 * The query layer the admin debug page + future visual editor
 * consume. All return values are frozen registry entries (or
 * primitives derived from them); consumers cannot mutate the
 * registry through these methods.
 *
 * Naming follows the prompt: `getAllRegistered`, `getByType`,
 * `getByVertical`, `getByName`, `getTokensConsumedBy`,
 * `getComponentsConsumingToken`, `getAcceptedChildrenForSlot`,
 * `getRegistrationVersion`.
 */

import {
  _internal_count,
  _internal_getEntry,
  _internal_listAll,
  _internal_listByToken,
  _internal_listByType,
  _internal_listKnownTokens,
} from "./registry"
import type {
  ComponentKind,
  RegistryEntry,
  VerticalScope,
} from "./types"


/** Return every registered component as a flat list. Order is
 * insertion order within each `(type, name)` bucket, but no
 * stronger guarantee — consumers should sort if rendering. */
export function getAllRegistered(): readonly RegistryEntry[] {
  return _internal_listAll()
}

/** Filter by component type. */
export function getByType(type: ComponentKind): readonly RegistryEntry[] {
  return _internal_listByType(type)
}

/** Filter by vertical applicability. A component matches if
 * its `verticals` array contains the requested vertical OR
 * contains the `"all"` sentinel.
 *
 * Pass `"all"` to receive every cross-vertical component (i.e.,
 * components explicitly tagged universal) — NOT the full registry. */
export function getByVertical(
  vertical: VerticalScope,
): readonly RegistryEntry[] {
  return _internal_listAll().filter((entry) => {
    const verticals = entry.metadata.verticals
    if (vertical === "all") return verticals.includes("all")
    return verticals.includes(vertical) || verticals.includes("all")
  })
}

/** Lookup a specific component by `(type, name)`. */
export function getByName(
  type: ComponentKind,
  name: string,
): RegistryEntry | undefined {
  return _internal_getEntry(type, name)
}

/** Tokens this component reads from (component-level + every
 * variant's additional tokens, deduped). Returns an empty array
 * for unknown components rather than throwing — the editor calls
 * this in tight render paths where transient unknowns happen. */
export function getTokensConsumedBy(
  type: ComponentKind,
  name: string,
): readonly string[] {
  const entry = _internal_getEntry(type, name)
  if (!entry) return []
  const seen = new Set<string>(entry.metadata.consumedTokens)
  for (const variant of entry.metadata.variants ?? []) {
    for (const tok of variant.additionalConsumedTokens ?? []) seen.add(tok)
  }
  return Array.from(seen).sort()
}

/** Inverse query: every component reading from a given token.
 * Used by the editor to show "changing this token affects N
 * components" before the user commits a token edit. */
export function getComponentsConsumingToken(
  token: string,
): readonly RegistryEntry[] {
  return _internal_listByToken(token)
}

/** Component types that may be placed in a given slot of a
 * given component. Returns `[]` when the component is unknown
 * OR the slot doesn't exist (the latter is a programmer error
 * but we don't crash — slots are sometimes added across phases). */
export function getAcceptedChildrenForSlot(
  type: ComponentKind,
  name: string,
  slotName: string,
): readonly ComponentKind[] {
  const entry = _internal_getEntry(type, name)
  if (!entry) return []
  const slot = entry.metadata.slots?.find((s) => s.name === slotName)
  if (!slot) return []
  return slot.acceptedTypes
}

/** Schema version recorded against a registration. Drives
 * future migration logic — when the registry schema changes,
 * older registrations can be detected and either auto-upgraded
 * or flagged. */
export function getRegistrationVersion(
  type: ComponentKind,
  name: string,
): { schemaVersion: number; componentVersion: number } | undefined {
  const entry = _internal_getEntry(type, name)
  if (!entry) return undefined
  return {
    schemaVersion: entry.metadata.schemaVersion,
    componentVersion: entry.metadata.componentVersion,
  }
}


// ─── Aggregation helpers (debug page consumers) ──────────────────

/** Total registration count. */
export function getTotalCount(): number {
  return _internal_count()
}

/** Map of `type` → count. Useful for the debug page header. */
export function getCountByType(): Record<ComponentKind, number> {
  const all = _internal_listAll()
  const out: Partial<Record<ComponentKind, number>> = {}
  for (const entry of all) {
    out[entry.metadata.type] = (out[entry.metadata.type] ?? 0) + 1
  }
  return out as Record<ComponentKind, number>
}

/** Map of `vertical` → count. A component tagged `["all"]`
 * counts toward every vertical bucket because it would render
 * for every tenant. The `"all"` bucket holds the count of
 * components explicitly tagged universal. */
export function getCoverageByVertical(): Record<VerticalScope, number> {
  const all = _internal_listAll()
  const out: Record<VerticalScope, number> = {
    all: 0,
    manufacturing: 0,
    funeral_home: 0,
    cemetery: 0,
    crematory: 0,
  }
  for (const entry of all) {
    for (const v of entry.metadata.verticals) {
      out[v] = (out[v] ?? 0) + 1
    }
  }
  return out
}

/** Every token name any registered component reads from. */
export function getKnownTokens(): readonly string[] {
  return Array.from(_internal_listKnownTokens()).sort()
}


/** Effective class memberships for a registration: explicit
 * `componentClasses` if declared, else `[type]`. v1 invariant:
 * every component has exactly one class. The array shape exists
 * for future multi-class extensibility — see CLAUDE.md §4 class
 * configuration architecture subsection. */
export function getEffectiveComponentClasses(
  entry: RegistryEntry,
): readonly string[] {
  const declared = entry.metadata.componentClasses
  if (declared && declared.length > 0) return declared
  return [entry.metadata.type]
}


/** All components registered in a given class. Walks every
 * registration and includes those whose effective class membership
 * contains `className`. */
export function getComponentsInClass(
  className: string,
): readonly RegistryEntry[] {
  return getAllRegistered().filter((e) =>
    getEffectiveComponentClasses(e).includes(className),
  )
}
