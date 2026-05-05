/**
 * PersonalizationStudioTenantConfigContext — Phase 1G chrome-canvas
 * runtime wiring.
 *
 * Per Phase 1D scope-deferral closure + Phase 1G build prompt: at
 * studio shell mount, fetches canonical per-tenant
 * `TenantPersonalizationConfig` for the canonical template_type +
 * provides via React context to canonical canvas chrome consumers
 * (CanonicalOptionsPalette + FontEditor + EmblemEditor).
 *
 * **Canonical runtime path per §3.26.14 Workshop primitive canon**:
 *   - Studio shell mounts <PersonalizationStudioTenantConfigProvider>
 *   - Provider fires GET /api/v1/workshop/personalization-studio/
 *     {templateType}/tenant-config at mount
 *   - CanonicalOptionsPalette + FontEditor + EmblemEditor read via
 *     `usePersonalizationStudioTenantConfig()`; per-tenant catalogs
 *     + display labels canonical-flow into canonical chrome surfaces
 *
 * **Canonical anti-pattern guards explicit at FE substrate**:
 *   - §2.5.4 Anti-pattern 14 (portal-specific feature creep within
 *     Spaces canon rejected) — context provider canonical-shared
 *     across canonical 3 authoring contexts (FH-tenant
 *     funeral_home_with_family + Mfg-tenant manufacturer_without_family +
 *     Mfg-tenant manufacturer_from_fh_share); does NOT introduce
 *     authoring-context-specific provider variant.
 *   - §3.26.11.12.16 Anti-pattern 12 (parallel architectures rejected)
 *     — single canonical provider serves canonical Step 1 + canonical
 *     Step 2 (Urn Vault Personalization Studio inheritance) via
 *     canonical templateType parameterization; no parallel
 *     architecture per template_type.
 *
 * **Canonical fallback discipline**: when tenant config fetch fails
 * (network error, 403, etc.), provider canonical-falls-back to
 * undefined config + downstream consumers canonical-fall-back to
 * canonical default catalogs + canonical default display labels per
 * Phase 1B existing canonical-default discipline (CanonicalOptionsPalette
 * `displayLabels?` prop + canonical CANONICAL_FONT_CATALOG /
 * CANONICAL_EMBLEM_CATALOG at ElementEditorSurface).
 */

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { getTenantPersonalizationConfig } from "@/services/workshop-service"
import type {
  TenantPersonalizationConfig,
  WorkshopTemplateType,
} from "@/types/workshop"


export interface PersonalizationStudioTenantConfigValue {
  /** Canonical resolved per-tenant config; undefined while loading
   *  OR on canonical fallback (network error). */
  config: TenantPersonalizationConfig | undefined
  /** Canonical loading state surfaces canonical pre-config-resolved
   *  state for canonical chrome consumer canonical-discipline. */
  isLoading: boolean
  /** Canonical error state surfaces canonical fallback mode for
   *  canonical chrome consumer canonical-discipline. */
  error: Error | undefined
}


const PersonalizationStudioTenantConfigContext = createContext<
  PersonalizationStudioTenantConfigValue | null
>(null)


interface ProviderProps {
  /** Canonical Workshop template_type per §3.26.14 substrate
   *  registration. Step 2 Urn Vault inherits canonical context via
   *  canonical templateType parameterization. */
  templateType: WorkshopTemplateType
  /**
   *  Canonical pre-resolved config for canonical test / Storybook
   *  scope (canonical-bypasses fetch). Production callers omit
   *  per canonical fetch-on-mount discipline.
   */
  initialConfig?: TenantPersonalizationConfig
  children: ReactNode
}


export function PersonalizationStudioTenantConfigProvider({
  templateType,
  initialConfig,
  children,
}: ProviderProps) {
  const [config, setConfig] = useState<
    TenantPersonalizationConfig | undefined
  >(initialConfig)
  const [isLoading, setIsLoading] = useState<boolean>(
    initialConfig === undefined,
  )
  const [error, setError] = useState<Error | undefined>(undefined)

  useEffect(() => {
    if (initialConfig !== undefined) return
    let cancelled = false
    setIsLoading(true)
    setError(undefined)

    async function load() {
      try {
        const data = await getTenantPersonalizationConfig(templateType)
        if (cancelled) return
        setConfig(data)
      } catch (err) {
        if (cancelled) return
        // Canonical fallback discipline — fetch failure surfaces
        // canonical undefined config + downstream consumer canonical-
        // falls-back to canonical default catalogs.
        setError(err as Error)
        setConfig(undefined)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [templateType, initialConfig])

  const value = useMemo<PersonalizationStudioTenantConfigValue>(
    () => ({ config, isLoading, error }),
    [config, isLoading, error],
  )

  return (
    <PersonalizationStudioTenantConfigContext.Provider value={value}>
      {children}
    </PersonalizationStudioTenantConfigContext.Provider>
  )
}


/** Canonical hook for canonical chrome consumers (CanonicalOptionsPalette
 *  + FontEditor + EmblemEditor). Returns canonical config value OR
 *  null when canonical provider absent (canonical Storybook / test
 *  scope canonical-fallback to default catalogs). */
export function usePersonalizationStudioTenantConfig(): PersonalizationStudioTenantConfigValue | null {
  return useContext(PersonalizationStudioTenantConfigContext)
}
