/**
 * Bridgeable Admin Visual Editor — Phase 1 Component Registry.
 *
 * The singleton registry. Components register at module import
 * (via `registerComponent`); the admin debug page + future visual
 * editor read via the introspection API.
 *
 * Storage shape: a `Map<type, Map<name, RegistryEntry>>` keyed
 * for O(1) lookups by type + name. A second flat `Map<token,
 * Set<RegistryEntry>>` powers the inverse "which components
 * consume this token?" query without iterating the full registry
 * at lookup time. Both indexes are maintained in lockstep on
 * register / unregister.
 *
 * Hot-reload safety: re-registration of the same `(type, name)`
 * key replaces the existing entry and warns on metadata drift.
 * No accumulation of stale registrations during HMR.
 *
 * SSR safety: registrations don't touch DOM / window. The module
 * is safe to import on a server render path even though the
 * admin editor consumes it on the client.
 */

import type {
  ComponentKind,
  RegistrationMetadata,
  RegistryEntry,
} from "./types"


// ─── Internal storage ────────────────────────────────────────────

/** type → name → entry */
const _byType: Map<ComponentKind, Map<string, RegistryEntry>> = new Map()

/** token-name → set of entries consuming it. Token names here
 * match `consumedTokens` verbatim (no leading `--`). */
const _byToken: Map<string, Set<RegistryEntry>> = new Map()


// ─── Logging helper ──────────────────────────────────────────────

/** Console output guarded behind a one-time `import.meta.env`
 * lookup so registrations stay quiet in production builds.
 * `import.meta.env.DEV` is a Vite compile-time constant. */
const _isDev = (() => {
  try {
    // Vite injects `import.meta.env` at build time; SSR / Node
    // tooling might not have it. Cast through unknown so the
    // optional access doesn't depend on the host env's typings.
    const meta = import.meta as unknown as
      | { env?: { DEV?: boolean } }
      | undefined
    return Boolean(meta?.env?.DEV)
  } catch {
    return false
  }
})()


// ─── Registry mutation API (internal — only `register.ts` uses these) ─

export function _internal_register(entry: RegistryEntry): void {
  const { type, name } = entry.metadata
  let typeBucket = _byType.get(type)
  if (!typeBucket) {
    typeBucket = new Map()
    _byType.set(type, typeBucket)
  }

  const existing = typeBucket.get(name)
  if (existing) {
    // Hot-reload path. Drop the prior entry from the inverse index
    // before reinserting, so stale token associations don't accumulate.
    _removeFromTokenIndex(existing)
    if (_isDev) {
      const drift = _detectMetadataDrift(existing.metadata, entry.metadata)
      if (drift.length > 0) {
        // eslint-disable-next-line no-console
        console.warn(
          `[admin-registry] re-registering ${type}:${name} — metadata drift: ${drift.join(", ")}`,
        )
      }
    }
  }

  typeBucket.set(name, entry)
  _addToTokenIndex(entry)
}

export function _internal_unregister(type: ComponentKind, name: string): void {
  const bucket = _byType.get(type)
  if (!bucket) return
  const entry = bucket.get(name)
  if (!entry) return
  _removeFromTokenIndex(entry)
  bucket.delete(name)
}

function _addToTokenIndex(entry: RegistryEntry): void {
  for (const token of entry.metadata.consumedTokens) {
    let bucket = _byToken.get(token)
    if (!bucket) {
      bucket = new Set()
      _byToken.set(token, bucket)
    }
    bucket.add(entry)
  }
  for (const variant of entry.metadata.variants ?? []) {
    for (const token of variant.additionalConsumedTokens ?? []) {
      let bucket = _byToken.get(token)
      if (!bucket) {
        bucket = new Set()
        _byToken.set(token, bucket)
      }
      bucket.add(entry)
    }
  }
}

function _removeFromTokenIndex(entry: RegistryEntry): void {
  for (const token of entry.metadata.consumedTokens) {
    const bucket = _byToken.get(token)
    if (bucket) {
      bucket.delete(entry)
      if (bucket.size === 0) _byToken.delete(token)
    }
  }
  for (const variant of entry.metadata.variants ?? []) {
    for (const token of variant.additionalConsumedTokens ?? []) {
      const bucket = _byToken.get(token)
      if (bucket) {
        bucket.delete(entry)
        if (bucket.size === 0) _byToken.delete(token)
      }
    }
  }
}


// ─── Read API (consumed by `introspection.ts`) ────────────────────

export function _internal_getEntry(
  type: ComponentKind,
  name: string,
): RegistryEntry | undefined {
  return _byType.get(type)?.get(name)
}

export function _internal_listAll(): readonly RegistryEntry[] {
  const out: RegistryEntry[] = []
  for (const bucket of _byType.values()) {
    for (const entry of bucket.values()) out.push(entry)
  }
  return out
}

export function _internal_listByType(
  type: ComponentKind,
): readonly RegistryEntry[] {
  const bucket = _byType.get(type)
  if (!bucket) return []
  return Array.from(bucket.values())
}

export function _internal_listByToken(
  token: string,
): readonly RegistryEntry[] {
  const bucket = _byToken.get(token)
  if (!bucket) return []
  return Array.from(bucket)
}

export function _internal_listKnownTokens(): readonly string[] {
  return Array.from(_byToken.keys())
}

export function _internal_count(): number {
  let total = 0
  for (const bucket of _byType.values()) total += bucket.size
  return total
}

/** Test-only — wipes registry state. Production code never calls
 * this; tests use it between cases to avoid cross-test pollution. */
export function _internal_clear(): void {
  _byType.clear()
  _byToken.clear()
}


// ─── Drift detection (HMR diagnostic) ────────────────────────────

function _detectMetadataDrift(
  before: RegistrationMetadata,
  after: RegistrationMetadata,
): string[] {
  const changed: string[] = []
  if (before.displayName !== after.displayName) changed.push("displayName")
  if (before.description !== after.description) changed.push("description")
  if (before.category !== after.category) changed.push("category")
  if (before.componentVersion !== after.componentVersion) {
    changed.push(`componentVersion(${before.componentVersion}->${after.componentVersion})`)
  }
  if (before.schemaVersion !== after.schemaVersion) {
    changed.push(`schemaVersion(${before.schemaVersion}->${after.schemaVersion})`)
  }
  if (
    JSON.stringify(before.consumedTokens.slice().sort())
      !== JSON.stringify(after.consumedTokens.slice().sort())
  ) {
    changed.push("consumedTokens")
  }
  if (
    JSON.stringify(before.verticals.slice().sort())
      !== JSON.stringify(after.verticals.slice().sort())
  ) {
    changed.push("verticals")
  }
  return changed
}
