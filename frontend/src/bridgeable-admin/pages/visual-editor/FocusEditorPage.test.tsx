/**
 * Arc 3a — FocusEditorPage return-to banner tests.
 *
 * Verifies bidirectional deep-link contract:
 * - When launched with `?return_to=...` URL param, the editor renders
 *   a "Back to runtime editor" affordance.
 * - Click navigates to the decoded return_to value (preserves inspector
 *   state because the runtime editor route stays mounted in the
 *   originating tab).
 * - When launched without return_to, the banner is hidden + behavior
 *   is identical to pre-Arc-3a.
 * - When launched with `?focus_type=scheduling`, the matching focus-
 *   template pre-selects (forward-compat scaffolding).
 *
 * Mocks `focusCompositionsService` to avoid network. Uses MemoryRouter
 * with initial URL carrying query params per react-router-dom v7
 * canonical pattern.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"

import "@/lib/visual-editor/registry/auto-register"

import FocusEditorPage from "./FocusEditorPage"


vi.mock(
  "@/bridgeable-admin/services/focus-compositions-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/bridgeable-admin/services/focus-compositions-service")
    >("@/bridgeable-admin/services/focus-compositions-service")
    return {
      ...actual,
      focusCompositionsService: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
        resolve: vi.fn().mockResolvedValue({
          focus_type: "scheduling",
          vertical: null,
          tenant_id: null,
          source: null,
          source_id: null,
          source_version: null,
          rows: [],
          canvas_config: { gap_size: 12, background_treatment: "surface-base" },
        }),
        create: vi.fn(),
        update: vi.fn(),
      },
    }
  },
)

vi.mock(
  "@/bridgeable-admin/services/component-configurations-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/bridgeable-admin/services/component-configurations-service")
    >("@/bridgeable-admin/services/component-configurations-service")
    return {
      ...actual,
      componentConfigurationsService: {
        list: vi.fn().mockResolvedValue([]),
        resolve: vi.fn().mockResolvedValue({
          component_kind: "focus-template",
          component_name: "funeral-scheduling",
          vertical: null,
          tenant_id: null,
          props: {},
          orphaned_keys: [],
          sources: [],
        }),
        create: vi.fn(),
        update: vi.fn(),
      },
    }
  },
)

vi.mock("@/bridgeable-admin/components/TenantPicker", () => ({
  TenantPicker: () => null,
}))


// Location capture for route navigation assertion
function LocationProbe({ onLocation }: { onLocation: (path: string) => void }) {
  const loc = useLocation()
  onLocation(loc.pathname + loc.search)
  return null
}


afterEach(() => {
  vi.clearAllMocks()
})


describe("FocusEditorPage — Arc 3a return-to banner", () => {
  it("does NOT render return-to banner when no return_to URL param", async () => {
    const result = render(
      <MemoryRouter initialEntries={["/visual-editor/focuses"]}>
        <FocusEditorPage />
      </MemoryRouter>,
    )
    // Banner test-id should NOT be present
    await waitFor(() => {
      expect(result.getByTestId("focus-editor")).toBeTruthy()
    })
    expect(
      result.queryByTestId("focus-editor-return-to-banner"),
    ).toBeFalsy()
  })

  it("renders 'Back to runtime editor' affordance when return_to param present", async () => {
    const returnTo = encodeURIComponent(
      "/bridgeable-admin/runtime-editor/?tenant=hopkins-fh&user=u1",
    )
    const result = render(
      <MemoryRouter
        initialEntries={[
          `/visual-editor/focuses?return_to=${returnTo}&focus_type=scheduling`,
        ]}
      >
        <FocusEditorPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(
        result.getByTestId("focus-editor-return-to-banner"),
      ).toBeTruthy()
    })
    expect(
      result.getByTestId("focus-editor-return-to-back"),
    ).toBeTruthy()
  })

  it("click 'Back to runtime editor' navigates to decoded return_to value", async () => {
    let capturedPath = ""
    const returnTo =
      "/bridgeable-admin/runtime-editor/?tenant=hopkins-fh&user=u1"
    const encoded = encodeURIComponent(returnTo)

    const result = render(
      <MemoryRouter
        initialEntries={[
          `/visual-editor/focuses?return_to=${encoded}&focus_type=scheduling`,
        ]}
      >
        <Routes>
          <Route
            path="/visual-editor/focuses"
            element={
              <>
                <LocationProbe onLocation={(p) => (capturedPath = p)} />
                <FocusEditorPage />
              </>
            }
          />
          <Route
            path="/bridgeable-admin/runtime-editor/"
            element={
              <LocationProbe onLocation={(p) => (capturedPath = p)} />
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    const backBtn = await waitFor(() =>
      result.getByTestId("focus-editor-return-to-back"),
    )
    fireEvent.click(backBtn)
    await waitFor(() => {
      expect(capturedPath).toContain("/bridgeable-admin/runtime-editor")
      expect(capturedPath).toContain("tenant=hopkins-fh")
    })
  })

  it("pre-selects focus-template when focus_type URL param matches a registered compositionFocusType", async () => {
    const result = render(
      <MemoryRouter
        initialEntries={[
          "/visual-editor/focuses?focus_type=scheduling",
        ]}
      >
        <FocusEditorPage />
      </MemoryRouter>,
    )
    // funeral-scheduling registers compositionFocusType="scheduling"
    // → editor should pre-select that template
    await waitFor(() => {
      const label = result.queryByTestId("focus-preview-template-label")
      expect(label).toBeTruthy()
      expect(label?.textContent).toContain("Funeral Scheduling")
    })
  })

  it("standalone behavior unchanged when no URL params (smoke)", async () => {
    const result = render(
      <MemoryRouter initialEntries={["/visual-editor/focuses"]}>
        <FocusEditorPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(result.getByTestId("focus-editor")).toBeTruthy()
      expect(result.getByTestId("focus-editor-browser")).toBeTruthy()
    })
    // No banner; default category Decision selected
    expect(
      result.queryByTestId("focus-editor-return-to-banner"),
    ).toBeFalsy()
  })
})
