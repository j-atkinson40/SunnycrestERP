/**
 * R-5.1 — EdgePanelSettingsPage vitest coverage.
 *
 * Mocks the edge-panel-service module + useAuth context. Covers
 * happy-path render, save round-trip, discard, reset-all, and
 * disabled/empty edge cases.
 */
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { MemoryRouter } from "react-router-dom"
import type { ReactElement } from "react"


function renderWithRouter(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

const mockResolveTenantDefault = vi.fn()
const mockGetPreferences = vi.fn()
const mockGetTenantConfig = vi.fn()
const mockPatchPreferences = vi.fn()

vi.mock("@/lib/edge-panel/edge-panel-service", () => ({
  resolveEdgePanelTenantDefault: (...args: unknown[]) =>
    mockResolveTenantDefault(...args),
  getEdgePanelPreferences: (...args: unknown[]) => mockGetPreferences(...args),
  getEdgePanelTenantConfig: (...args: unknown[]) => mockGetTenantConfig(...args),
  patchEdgePanelPreferences: (...args: unknown[]) =>
    mockPatchPreferences(...args),
}))

const mockUseAuth = vi.fn()
vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => mockUseAuth(),
  // RegisteredButton (rendered indirectly via CompositionRenderer
  // for the live preview pane) calls useAuthOptional. Mock it as
  // a noop returning null so the preview render doesn't crash in
  // jsdom.
  useAuthOptional: () => null,
}))

import "@/lib/visual-editor/registry/auto-register"
import EdgePanelSettingsPage from "./EdgePanelSettingsPage"


function buildTenantDefault() {
  return {
    panel_key: "default",
    vertical: "manufacturing",
    tenant_id: "t1",
    source: "platform_default" as const,
    source_id: "src",
    source_version: 1,
    pages: [
      {
        page_id: "pg1",
        name: "Quick Actions",
        rows: [
          {
            row_id: "r1",
            column_count: 1,
            row_height: "auto" as const,
            column_widths: null,
            nested_rows: null,
            placements: [
              {
                placement_id: "p1",
                component_kind: "button" as const,
                component_name: "navigate-to-pulse",
                starting_column: 0,
                column_span: 1,
                prop_overrides: {},
                display_config: {},
                nested_rows: null,
              },
            ],
          },
        ],
        canvas_config: {},
      },
    ],
    canvas_config: {},
  }
}


describe("EdgePanelSettingsPage", () => {
  beforeEach(() => {
    mockResolveTenantDefault.mockReset()
    mockGetPreferences.mockReset()
    mockGetTenantConfig.mockReset()
    mockPatchPreferences.mockReset()
    mockUseAuth.mockReturnValue({
      user: { id: "u1", email: "u@example.com" },
      company: { id: "t1", vertical: "manufacturing" },
    })
  })

  it("renders loading then page list + editor + preview", async () => {
    mockResolveTenantDefault.mockResolvedValue(buildTenantDefault())
    mockGetPreferences.mockResolvedValue({ edge_panel_overrides: {} })
    mockGetTenantConfig.mockResolvedValue({ enabled: true, width: 320 })

    renderWithRouter(<EdgePanelSettingsPage />)
    expect(screen.getByTestId("edge-panel-settings-page")).toBeTruthy()

    await waitFor(() => {
      expect(
        screen.getByTestId("edge-panel-settings-page-list"),
      ).toBeTruthy()
    })
    expect(screen.getByTestId("edge-panel-settings-page-editor")).toBeTruthy()
    expect(screen.getByTestId("edge-panel-settings-preview")).toBeTruthy()
    // Tenant page row visible.
    expect(screen.getByTestId("edge-panel-settings-page-row-pg1")).toBeTruthy()
  })

  it("disabled tenant config renders the disabled notice", async () => {
    mockResolveTenantDefault.mockResolvedValue(buildTenantDefault())
    mockGetPreferences.mockResolvedValue({ edge_panel_overrides: {} })
    mockGetTenantConfig.mockResolvedValue({ enabled: false, width: 320 })
    renderWithRouter(<EdgePanelSettingsPage />)
    await waitFor(() => {
      expect(screen.getByText(/Edge panel is disabled/i)).toBeTruthy()
    })
  })

  it("no tenant default renders the no-panel notice", async () => {
    mockResolveTenantDefault.mockResolvedValue({
      panel_key: "default",
      vertical: null,
      tenant_id: null,
      source: null,
      source_id: null,
      source_version: null,
      pages: [],
      canvas_config: {},
    })
    mockGetPreferences.mockResolvedValue({ edge_panel_overrides: {} })
    mockGetTenantConfig.mockResolvedValue({ enabled: true, width: 320 })
    renderWithRouter(<EdgePanelSettingsPage />)
    await waitFor(() => {
      expect(screen.getByText(/no edge panel configured/i)).toBeTruthy()
    })
  })

  it("hiding a placement surfaces the unsaved indicator", async () => {
    mockResolveTenantDefault.mockResolvedValue(buildTenantDefault())
    mockGetPreferences.mockResolvedValue({ edge_panel_overrides: {} })
    mockGetTenantConfig.mockResolvedValue({ enabled: true, width: 320 })

    renderWithRouter(<EdgePanelSettingsPage />)
    await waitFor(() => {
      expect(
        screen.getByTestId("edge-panel-settings-placement-toggle-hide-p1"),
      ).toBeTruthy()
    })
    await act(async () => {
      fireEvent.click(
        screen.getByTestId("edge-panel-settings-placement-toggle-hide-p1"),
      )
    })
    expect(
      screen.getByTestId("edge-panel-settings-unsaved-indicator"),
    ).toBeTruthy()
    expect(screen.getByTestId("edge-panel-settings-save")).toBeTruthy()
  })

  it("Save calls patchEdgePanelPreferences with the override", async () => {
    mockResolveTenantDefault.mockResolvedValue(buildTenantDefault())
    mockGetPreferences.mockResolvedValue({ edge_panel_overrides: {} })
    mockGetTenantConfig.mockResolvedValue({ enabled: true, width: 320 })
    // Server returns the just-saved shape on PATCH.
    mockPatchPreferences.mockImplementation(async (overrides: Record<string, unknown>) => ({
      edge_panel_overrides: overrides,
    }))

    renderWithRouter(<EdgePanelSettingsPage />)
    await waitFor(() => {
      expect(
        screen.getByTestId("edge-panel-settings-placement-toggle-hide-p1"),
      ).toBeTruthy()
    })
    await act(async () => {
      fireEvent.click(
        screen.getByTestId("edge-panel-settings-placement-toggle-hide-p1"),
      )
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("edge-panel-settings-save"))
    })
    expect(mockPatchPreferences).toHaveBeenCalledTimes(1)
    const [body] = mockPatchPreferences.mock.calls[0]
    expect(body.default.page_overrides.pg1.hidden_placement_ids).toEqual(["p1"])
  })

  it("Discard reverts to last-saved state", async () => {
    mockResolveTenantDefault.mockResolvedValue(buildTenantDefault())
    mockGetPreferences.mockResolvedValue({ edge_panel_overrides: {} })
    mockGetTenantConfig.mockResolvedValue({ enabled: true, width: 320 })

    renderWithRouter(<EdgePanelSettingsPage />)
    await waitFor(() => {
      expect(
        screen.getByTestId("edge-panel-settings-placement-toggle-hide-p1"),
      ).toBeTruthy()
    })
    await act(async () => {
      fireEvent.click(
        screen.getByTestId("edge-panel-settings-placement-toggle-hide-p1"),
      )
    })
    expect(
      screen.queryByTestId("edge-panel-settings-unsaved-indicator"),
    ).toBeTruthy()

    await act(async () => {
      fireEvent.click(screen.getByTestId("edge-panel-settings-discard"))
    })
    // Indicator should be gone after discard.
    expect(
      screen.queryByTestId("edge-panel-settings-unsaved-indicator"),
    ).toBeNull()
  })

  it("Reset-all opens confirmation dialog", async () => {
    mockResolveTenantDefault.mockResolvedValue(buildTenantDefault())
    mockGetPreferences.mockResolvedValue({ edge_panel_overrides: {} })
    mockGetTenantConfig.mockResolvedValue({ enabled: true, width: 320 })

    renderWithRouter(<EdgePanelSettingsPage />)
    await waitFor(() => {
      expect(screen.getByTestId("edge-panel-settings-reset-all")).toBeTruthy()
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId("edge-panel-settings-reset-all"))
    })
    await waitFor(() => {
      expect(
        screen.getByTestId("edge-panel-reset-dialog-panel"),
      ).toBeTruthy()
    })
  })
})
