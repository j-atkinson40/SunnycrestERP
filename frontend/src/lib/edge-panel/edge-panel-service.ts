/**
 * R-5.0 — edge panel tenant-realm API client.
 *
 * Uses the existing tenant `apiClient` (per-request URL resolution
 * via `resolveApiBaseUrl()` per R-1.6.7) — sends the tenant JWT.
 * Routes the platform admin to the admin-realm endpoints at
 * `/api/platform/admin/visual-editor/compositions/` for authoring;
 * this module is read + per-user-override write only.
 */
import apiClient from "@/lib/api-client"
import type {
  EdgePanelTenantConfig,
  EdgePanelUserOverride,
  ResolvedEdgePanel,
} from "./types"


export async function resolveEdgePanel(
  panelKey: string,
): Promise<ResolvedEdgePanel> {
  const r = await apiClient.get<ResolvedEdgePanel>(
    `/edge-panel/resolve`,
    { params: { panel_key: panelKey } },
  )
  return r.data
}


/**
 * R-5.1 — resolve the tenant default unmodified by the caller's own
 * per-user overrides. Used by the `/settings/edge-panel` page (R-5.1b)
 * to compute the diff for ownership-badge rendering.
 *
 * Tenant + vertical + platform inheritance still applies; only the
 * per-user override layer is bypassed.
 */
export async function resolveEdgePanelTenantDefault(
  panelKey: string,
): Promise<ResolvedEdgePanel> {
  const r = await apiClient.get<ResolvedEdgePanel>(
    `/edge-panel/resolve`,
    { params: { panel_key: panelKey, ignore_user_overrides: true } },
  )
  return r.data
}


export async function getEdgePanelPreferences(): Promise<{
  edge_panel_overrides: Record<string, EdgePanelUserOverride>
}> {
  const r = await apiClient.get<{
    edge_panel_overrides: Record<string, EdgePanelUserOverride>
  }>(`/edge-panel/preferences`)
  return r.data
}


export async function patchEdgePanelPreferences(
  edgePanelOverrides: Record<string, EdgePanelUserOverride>,
): Promise<{
  edge_panel_overrides: Record<string, EdgePanelUserOverride>
}> {
  const r = await apiClient.patch<{
    edge_panel_overrides: Record<string, EdgePanelUserOverride>
  }>(`/edge-panel/preferences`, {
    edge_panel_overrides: edgePanelOverrides,
  })
  return r.data
}


export async function getEdgePanelTenantConfig(): Promise<EdgePanelTenantConfig> {
  const r = await apiClient.get<EdgePanelTenantConfig>(
    `/edge-panel/tenant-config`,
  )
  return r.data
}
