/**
 * useResolvedComposition — frontend hook that fetches a resolved
 * composition for a Focus type at the current scope context.
 *
 * Mirrors the backend's `resolve_composition` semantics: walks
 * tenant_override → vertical_default → platform_default; returns
 * the first match (composition is a complete layout, not a partial
 * overlay). When no composition exists at any scope, source is null
 * and placements is empty — the caller falls back to its hard-coded
 * layout.
 *
 * Used by:
 *   - Composition editor preview (already consumes via its own state)
 *   - Focus runtime integration (the canonical consumer): a Focus
 *     React component invokes this hook with its focus_type +
 *     vertical (from tenant context) + tenant_id (from auth) and
 *     either renders via CompositionRenderer or falls back to its
 *     hard-coded layout.
 */
import { useEffect, useState } from "react"
import { focusCompositionsService } from "@/bridgeable-admin/services/focus-compositions-service"
import type { ResolvedComposition } from "./types"


export interface UseResolvedCompositionResult {
  composition: ResolvedComposition | null
  isLoading: boolean
  error: string | null
  /** True iff a composition exists at any scope. False means caller
   * should render its hard-coded fallback. */
  hasComposition: boolean
}


/**
 * Note on which API client this calls: composition resolution uses
 * the platform admin axios instance because the resolve endpoint
 * lives under /api/platform/admin/visual-editor/compositions/. For
 * tenant runtime usage (the eventual production wiring), a parallel
 * tenant-side endpoint OR a public-readable resolve endpoint would
 * be added — composition resolution is read-only and tenant-scoped
 * (a tenant can only resolve compositions for its own vertical +
 * tenant_id), so a tenant-readable endpoint is appropriate.
 *
 * For v1 in this phase: the hook is wired to the admin path and
 * useful for the composition editor's preview + admin-side
 * inspection. Production tenant runtime integration ships when the
 * tenant-readable resolver endpoint lands alongside the production
 * Focus refactor.
 */
export function useResolvedComposition(params: {
  focusType: string
  vertical?: string | null
  tenantId?: string | null
  /** Pass false to skip the fetch (e.g., when a Focus knows it
   * should always render its hard-coded layout). */
  enabled?: boolean
}): UseResolvedCompositionResult {
  const { focusType, vertical, tenantId, enabled = true } = params
  const [composition, setComposition] = useState<ResolvedComposition | null>(
    null,
  )
  const [isLoading, setIsLoading] = useState<boolean>(enabled)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false)
      return
    }
    let cancelled = false
    setIsLoading(true)
    setError(null)

    const resolveParams: {
      focus_type: string
      vertical?: string
      tenant_id?: string
    } = { focus_type: focusType }
    if (vertical) resolveParams.vertical = vertical
    if (tenantId) resolveParams.tenant_id = tenantId

    focusCompositionsService
      .resolve(resolveParams)
      .then((result) => {
        if (cancelled) return
        setComposition(result)
        setIsLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[useResolvedComposition] resolve failed", err)
        setError(err instanceof Error ? err.message : "Resolve failed")
        setComposition(null)
        setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [enabled, focusType, vertical, tenantId])

  return {
    composition,
    isLoading,
    error,
    hasComposition: !!composition && composition.source !== null,
  }
}
