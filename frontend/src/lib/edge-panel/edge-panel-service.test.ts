/**
 * R-5.0 — edge-panel-service vitest coverage.
 *
 * Verifies the tenant API client routes through `apiClient` (per-request
 * URL resolution + tenant JWT) and never hits adminApi paths.
 */
import { describe, it, expect, vi, beforeEach } from "vitest"


const apiGet = vi.fn()
const apiPatch = vi.fn()


vi.mock("@/lib/api-client", () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => apiGet(...args),
    patch: (...args: unknown[]) => apiPatch(...args),
  },
}))


import {
  resolveEdgePanel,
  getEdgePanelPreferences,
  patchEdgePanelPreferences,
  getEdgePanelTenantConfig,
} from "./edge-panel-service"


beforeEach(() => {
  apiGet.mockReset()
  apiPatch.mockReset()
})


describe("edge-panel-service", () => {
  it("resolveEdgePanel calls /edge-panel/resolve with panel_key", async () => {
    apiGet.mockResolvedValue({
      data: { panel_key: "default", pages: [], canvas_config: {} },
    })
    const out = await resolveEdgePanel("default")
    expect(apiGet).toHaveBeenCalledWith(
      "/edge-panel/resolve",
      expect.objectContaining({
        params: { panel_key: "default" },
      }),
    )
    expect(out.panel_key).toBe("default")
  })

  it("getEdgePanelPreferences calls /edge-panel/preferences", async () => {
    apiGet.mockResolvedValue({
      data: { edge_panel_overrides: {} },
    })
    const out = await getEdgePanelPreferences()
    expect(apiGet).toHaveBeenCalledWith("/edge-panel/preferences")
    expect(out.edge_panel_overrides).toEqual({})
  })

  it("patchEdgePanelPreferences sends overrides body", async () => {
    apiPatch.mockResolvedValue({
      data: {
        edge_panel_overrides: { default: { hidden_page_ids: ["x"] } },
      },
    })
    const out = await patchEdgePanelPreferences({
      default: { hidden_page_ids: ["x"] },
    })
    expect(apiPatch).toHaveBeenCalledWith("/edge-panel/preferences", {
      edge_panel_overrides: { default: { hidden_page_ids: ["x"] } },
    })
    expect(out.edge_panel_overrides).toEqual({
      default: { hidden_page_ids: ["x"] },
    })
  })

  it("getEdgePanelTenantConfig returns tenant config", async () => {
    apiGet.mockResolvedValue({ data: { enabled: true, width: 360 } })
    const out = await getEdgePanelTenantConfig()
    expect(apiGet).toHaveBeenCalledWith("/edge-panel/tenant-config")
    expect(out.enabled).toBe(true)
    expect(out.width).toBe(360)
  })
})
