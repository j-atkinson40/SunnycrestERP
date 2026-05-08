/**
 * R-4.0 — parameter binding resolver.
 *
 * Pure resolver: takes a `BindingContext` (already-pulled-from-React-
 * hooks data) + a list of `ParameterBinding`s, returns a flat object
 * mapping parameter names to resolved values. No React imports here
 * — the calling component (RegisteredButton) gathers context via
 * hooks, then passes it down. Pure functions are vitest-friendly.
 *
 * Missing context for a binding source returns `null` for that
 * parameter (rather than throwing). Dispatch handlers receive
 * partials gracefully; the user-facing failure mode is a single
 * dispatch with a null-valued parameter, not a crash before the
 * dispatch fires.
 */

import type {
  ParameterBinding,
  ParameterBindingSource,
} from "./types"


/** Snapshot of React-hook-derived data passed to the resolver.
 *  RegisteredButton populates this at click-time. Each field is
 *  optional because some hooks return null in some contexts (e.g.
 *  `useFocus().currentFocus` is null when no Focus is open). */
export interface BindingContext {
  user?: {
    id?: string | null
    email?: string | null
    role?: string | null
  } | null
  tenant?: {
    id?: string | null
    slug?: string | null
    vertical?: string | null
  } | null
  /** Date.now() snapshot. The resolver formats per binding.dateFormat. */
  nowMs?: number
  /** Output of useParams(). */
  routeParams?: Readonly<Record<string, string | undefined>>
  /** Output of useSearchParams()[0]. */
  queryParams?: URLSearchParams
  /** useFocus().currentFocus?.id. */
  currentFocusId?: string | null
}


/** Resolved value type. Strings dominate; numbers + booleans appear
 *  for literal bindings + epoch-ms date format. `null` when the
 *  binding's source is unavailable in the current context. */
export type ResolvedValue = string | number | boolean | null


/** Resolve a single binding against the current context. */
export function resolveBinding(
  binding: ParameterBinding,
  ctx: BindingContext,
): ResolvedValue {
  const src: ParameterBindingSource = binding.source
  switch (src) {
    case "literal": {
      // Defensive default: if `value` is undefined (configuration
      // bug), surface as null rather than passing `undefined` into
      // the dispatch payload (URLSearchParams + JSON serializers
      // handle null cleanly; undefined is dropped silently).
      return binding.value ?? null
    }
    case "current_user": {
      const u = ctx.user ?? null
      if (!u) return null
      const field = binding.userField ?? "id"
      return u[field] ?? null
    }
    case "current_tenant": {
      const t = ctx.tenant ?? null
      if (!t) return null
      const field = binding.tenantField ?? "id"
      return t[field] ?? null
    }
    case "current_date": {
      const ms = ctx.nowMs ?? Date.now()
      const fmt = binding.dateFormat ?? "iso-date"
      if (fmt === "epoch-ms") return ms
      const iso = new Date(ms).toISOString()
      if (fmt === "iso") return iso
      // iso-date: YYYY-MM-DD
      return iso.slice(0, 10)
    }
    case "current_route_param": {
      if (!binding.paramName) return null
      const params = ctx.routeParams ?? {}
      return params[binding.paramName] ?? null
    }
    case "current_query_param": {
      if (!binding.paramName) return null
      const qp = ctx.queryParams
      if (!qp) return null
      const v = qp.get(binding.paramName)
      return v ?? null
    }
    case "current_focus_id": {
      return ctx.currentFocusId ?? null
    }
    default: {
      // Exhaustive switch guard. TS should catch any new
      // ParameterBindingSource value at compile time; this branch
      // is the runtime safety net.
      const _exhaust: never = src
      void _exhaust
      return null
    }
  }
}


/** Resolve an array of bindings into a flat name→value map. */
export function resolveBindings(
  bindings: readonly ParameterBinding[],
  ctx: BindingContext,
): Record<string, ResolvedValue> {
  const out: Record<string, ResolvedValue> = {}
  for (const b of bindings) {
    if (!b.name) continue
    out[b.name] = resolveBinding(b, ctx)
  }
  return out
}


/** Substitute `{name}` placeholders in a string template with
 *  resolved binding values. Used by navigate-action route templates
 *  and create_vault_item field templates.
 *
 *  Behavior:
 *    - `{name}` replaced when `name` is present in `values` AND the
 *      value is not null. URL-encodes string values.
 *    - `{name}` left as literal (no replacement) when missing/null,
 *      so a partially-bound template surfaces visibly rather than
 *      silently sending an empty path segment.
 */
export function substituteTemplate(
  template: string,
  values: Record<string, ResolvedValue>,
): string {
  return template.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, (match, name) => {
    const v = values[name]
    if (v === null || v === undefined) return match
    return encodeURIComponent(String(v))
  })
}
