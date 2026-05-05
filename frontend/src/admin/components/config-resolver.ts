/**
 * Component configuration resolver — Phase 3.
 *
 * Frontend-side inheritance walker for the editor's draft state.
 * Mirrors `platform_themes`'s `theme-resolver.ts` shape — same
 * 4-layer stack (platform / vertical / tenant / draft), same
 * merge order (deeper wins), same `composeEffective` floor of
 * registration defaults.
 *
 * Both editors share architectural patterns; configuration adds
 * registry-default seeding (catalog → defaults map per
 * component) on top.
 */

import { getByName } from "@/admin/registry"
import type { ComponentKind, RegistryEntry } from "@/admin/registry"
import type { ResolvedConfiguration } from "@/services/component-configurations-service"


export type PropOverrideMap = Record<string, unknown>


export interface ConfigStack {
  platform: PropOverrideMap
  vertical: PropOverrideMap
  tenant: PropOverrideMap
  /** Operator's unsaved draft on top of all server-resolved layers. */
  draft: PropOverrideMap
}


export function emptyConfigStack(): ConfigStack {
  return { platform: {}, vertical: {}, tenant: {}, draft: {} }
}


/** Merge in canonical order: platform → vertical → tenant → draft.
 * Last-wins per key. Returns a fresh object — never mutates inputs. */
export function mergeConfigStack(stack: ConfigStack): PropOverrideMap {
  return {
    ...stack.platform,
    ...stack.vertical,
    ...stack.tenant,
    ...stack.draft,
  }
}


/** Compute the registration-default map for a component. The
 * editor uses this as the floor underneath the override stack —
 * every prop has SOMETHING to render, even when no override
 * exists at any scope. */
export function registrationDefaults(
  kind: ComponentKind,
  name: string,
): PropOverrideMap {
  const entry = getByName(kind, name)
  if (!entry) return {}
  return propsToDefaults(entry)
}


function propsToDefaults(entry: RegistryEntry): PropOverrideMap {
  const out: PropOverrideMap = {}
  const props = entry.metadata.configurableProps ?? {}
  for (const [key, schema] of Object.entries(props)) {
    out[key] = (schema as { default: unknown }).default
  }
  return out
}


/** Compose registration defaults with the override stack to
 * produce the final effective props map. */
export function composeEffectiveProps(
  kind: ComponentKind,
  name: string,
  stack: ConfigStack,
): PropOverrideMap {
  return {
    ...registrationDefaults(kind, name),
    ...mergeConfigStack(stack),
  }
}


export type PropSource =
  | "registration-default"
  | "platform-default"
  | "vertical-default"
  | "tenant-override"
  | "draft"


export function resolvePropSource(
  propName: string,
  stack: ConfigStack,
): PropSource {
  if (propName in stack.draft) return "draft"
  if (propName in stack.tenant) return "tenant-override"
  if (propName in stack.vertical) return "vertical-default"
  if (propName in stack.platform) return "platform-default"
  return "registration-default"
}


/** Translate a backend `ResolvedConfiguration` into the
 * frontend's stack shape. Mirrors `stackFromResolved` in the
 * Phase 2 theme-resolver. */
export function stackFromResolvedConfig(
  resolved: ResolvedConfiguration,
  draft: PropOverrideMap = {},
): ConfigStack {
  const out = emptyConfigStack()
  out.draft = { ...draft }

  for (const src of resolved.sources) {
    const layer: PropOverrideMap = {}
    for (const k of src.applied_keys) {
      if (k in resolved.props) layer[k] = resolved.props[k]
    }
    if (src.scope === "platform_default") out.platform = layer
    else if (src.scope === "vertical_default") out.vertical = layer
    else if (src.scope === "tenant_override") out.tenant = layer
  }

  return out
}


/** List the keys whose values differ between two override maps.
 * Used by the editor to render "unsaved changes" indicators. */
export function diffPropOverrides(
  before: PropOverrideMap,
  after: PropOverrideMap,
): string[] {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)])
  const out: string[] = []
  for (const k of keys) {
    if (!deepEqual(before[k], after[k])) out.push(k)
  }
  return out.sort()
}


function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a == null || b == null) return false
  if (typeof a !== typeof b) return false
  if (typeof a !== "object") return false
  // Arrays + objects via JSON.stringify is good enough for the
  // editor's diff use case (no functions, dates, or cyclic data).
  try {
    return JSON.stringify(a) === JSON.stringify(b)
  } catch {
    return false
  }
}
