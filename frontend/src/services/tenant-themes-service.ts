/**
 * Tenant-realm theme resolve client — R-2.5.
 *
 * Mirrors `themesService.resolve` from
 * `@/bridgeable-admin/services/themes-service` but uses the tenant
 * `apiClient` (per-request URL resolution + tenant JWT) instead of
 * `adminApi` (PlatformUser JWT).
 *
 * Tenants call `GET /api/v1/themes/resolve?mode=light|dark`. The
 * server infers vertical + tenant_id from the caller's company; the
 * tenant CANNOT request resolution for a different tenant.
 *
 * Returns the same `ResolvedTheme` shape the visual editor's
 * theme-resolver helpers (`stackFromResolved`, `composeEffective`,
 * `applyThemeToElement`) consume — so PresetThemeProvider can reuse
 * those helpers verbatim, no shape adaptation needed.
 */

import apiClient from "@/lib/api-client"


export type ThemeMode = "light" | "dark"

export type ThemeScope =
  | "platform_default"
  | "vertical_default"
  | "tenant_override"


export interface TenantResolvedTheme {
  mode: ThemeMode
  vertical: string | null
  tenant_id: string | null
  tokens: Record<string, unknown>
  sources: Array<{
    scope: ThemeScope
    id: string
    version: number
    applied_keys: string[]
    vertical?: string
    tenant_id?: string
  }>
}


export const tenantThemesService = {
  /** R-2.5 — fetch the resolved theme for the caller's own tenant
   *  context. Server infers vertical + tenant_id from the JWT's
   *  `current_user.company`. Empty `tokens` + `sources` arrays mean
   *  no authored overrides at any scope; frontend falls through to
   *  `tokens.css` static defaults via `composeEffective`'s default
   *  layer.
   *
   *  Errors propagate through `apiClient`'s standard error handling.
   *  PresetThemeProvider's effect catches + console.warns to keep
   *  the boot path resilient — failed theme resolution should never
   *  block the app from rendering. */
  async resolve(mode: ThemeMode): Promise<TenantResolvedTheme> {
    const response = await apiClient.get<TenantResolvedTheme>(
      "/themes/resolve",
      { params: { mode } },
    )
    return response.data
  },
}
