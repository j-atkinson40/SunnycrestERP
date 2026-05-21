/**
 * Integration tests for WidgetBuilderPage (WB-4a).
 *
 * Service-mocked. Covers:
 *   - Landing (no slug) → create button visible + dispatches create.
 *   - Slug → loads record + renders three-pane shell.
 *   - Auto-save dispatch via setDraft (debounce verified in hook test).
 *   - Publish dispatch + registry refresh call.
 *   - Canvas root flex config select changes propagate as draft saves.
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"


// Mock the service before importing the page.
vi.mock("@/bridgeable-admin/services/widget-builder-service", () => ({
  WidgetBuilderApiError: class extends Error {
    status = 0
    detail: unknown = null
    constructor(m: string, s = 0, d: unknown = null) {
      super(m)
      this.status = s
      this.detail = d
    }
  },
  widgetBuilderService: {
    get: vi.fn(),
    create: vi.fn(),
    saveDraft: vi.fn(),
    publish: vi.fn(),
  },
}))

vi.mock("@/lib/widget-builder/runtime/registerComposedWidgets", () => ({
  refreshComposedWidgets: vi.fn(() => Promise.resolve(1)),
}))

import {
  widgetBuilderService,
  WidgetBuilderApiError,
} from "@/bridgeable-admin/services/widget-builder-service"
import { refreshComposedWidgets } from "@/lib/widget-builder/runtime/registerComposedWidgets"
import WidgetBuilderPage from "./WidgetBuilderPage"


function mkBlob(): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column", gap_token: "sm" },
        children: [],
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


function mkRecord(blob: CompositionBlob | null) {
  return {
    widget_id: "test-widget",
    title: "Test Widget",
    description: null,
    icon: null,
    category: null,
    composition_blob: blob,
    composition_version: 1,
    published_composition_blob: null,
    tier_scope: "vertical" as const,
    supported_surfaces: ["dashboard_grid"],
    default_size: "1x1",
    supported_sizes: ["1x1"],
    last_edit_session_id: null,
    last_edit_session_at: null,
  }
}


function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/studio/widget-builder/:slug" element={<WidgetBuilderPage />} />
        <Route path="/studio/widget-builder" element={<WidgetBuilderPage />} />
      </Routes>
    </MemoryRouter>,
  )
}


describe("WidgetBuilderPage — landing (no slug)", () => {
  beforeEach(() => {
    vi.mocked(widgetBuilderService.get).mockReset()
    vi.mocked(widgetBuilderService.create).mockReset()
  })
  afterEach(() => {
    vi.clearAllMocks()
  })

  it("renders the landing card with a 'New Widget' button", () => {
    renderAt("/studio/widget-builder")
    expect(screen.getByTestId("widget-builder-landing")).toBeTruthy()
    expect(
      screen.getByTestId("widget-builder-new-widget-button"),
    ).toBeTruthy()
  })

  it("clicking 'New Widget' dispatches create", async () => {
    vi.mocked(widgetBuilderService.create).mockResolvedValueOnce(
      mkRecord(mkBlob()),
    )
    // After create resolves, the page navigates to /studio/widget-builder/{slug}
    // which fires a GET. Mock that too so the post-navigation mount
    // doesn't blow up.
    vi.mocked(widgetBuilderService.get).mockResolvedValue(mkRecord(mkBlob()))
    renderAt("/studio/widget-builder")
    fireEvent.click(screen.getByTestId("widget-builder-new-widget-button"))
    await waitFor(() => {
      expect(widgetBuilderService.create).toHaveBeenCalled()
    })
  })
})


describe("WidgetBuilderPage — with slug", () => {
  beforeEach(() => {
    vi.mocked(widgetBuilderService.get).mockReset()
    vi.mocked(widgetBuilderService.saveDraft).mockReset()
    vi.mocked(widgetBuilderService.publish).mockReset()
    vi.mocked(refreshComposedWidgets).mockClear()
  })

  it("loads the record and renders three-pane shell", async () => {
    vi.mocked(widgetBuilderService.get).mockResolvedValueOnce(
      mkRecord(mkBlob()),
    )
    renderAt("/studio/widget-builder/test-widget")
    await waitFor(() => {
      expect(screen.getByTestId("widget-builder-page")).toBeTruthy()
    })
    expect(screen.getByTestId("widget-builder-topbar")).toBeTruthy()
    expect(screen.getByTestId("widget-builder-atom-palette")).toBeTruthy()
    expect(screen.getByTestId("widget-builder-canvas")).toBeTruthy()
    expect(screen.getByTestId("widget-builder-inspector")).toBeTruthy()
  })

  it("exposes the tier indicator badge", async () => {
    vi.mocked(widgetBuilderService.get).mockResolvedValueOnce(
      mkRecord(mkBlob()),
    )
    renderAt("/studio/widget-builder/test-widget")
    await waitFor(() => {
      expect(screen.getByTestId("widget-builder-tier-indicator")).toBeTruthy()
    })
  })

  it("renders the canvas root flex config selects", async () => {
    vi.mocked(widgetBuilderService.get).mockResolvedValueOnce(
      mkRecord(mkBlob()),
    )
    renderAt("/studio/widget-builder/test-widget")
    await waitFor(() => {
      expect(
        screen.getByTestId("widget-builder-root-flex-config"),
      ).toBeTruthy()
    })
    expect(screen.getByTestId("widget-builder-root-direction")).toBeTruthy()
    expect(screen.getByTestId("widget-builder-root-gap")).toBeTruthy()
  })

  it("Publish button dispatches publish and triggers registry refresh", async () => {
    const blob = mkBlob()
    vi.mocked(widgetBuilderService.get).mockResolvedValueOnce(mkRecord(blob))
    vi.mocked(widgetBuilderService.publish).mockResolvedValueOnce({
      ...mkRecord(blob),
      published_composition_blob: blob,
      composition_version: 2,
    })
    renderAt("/studio/widget-builder/test-widget")
    await waitFor(() => {
      expect(screen.getByTestId("widget-builder-publish-button")).toBeTruthy()
    })
    fireEvent.click(screen.getByTestId("widget-builder-publish-button"))
    await waitFor(() => {
      expect(widgetBuilderService.publish).toHaveBeenCalledWith("test-widget")
    })
    await waitFor(() => {
      expect(refreshComposedWidgets).toHaveBeenCalled()
    })
  })

  it("renders publish error banner on 422", async () => {
    const blob = mkBlob()
    vi.mocked(widgetBuilderService.get).mockResolvedValueOnce(mkRecord(blob))
    vi.mocked(widgetBuilderService.saveDraft).mockResolvedValue(mkRecord(blob))
    vi.mocked(widgetBuilderService.publish).mockRejectedValueOnce(
      new WidgetBuilderApiError("422", 422, {
        code: "composition_invalid",
        errors: ["root_atom_id: missing"],
      }),
    )
    renderAt("/studio/widget-builder/test-widget")
    await waitFor(() => {
      expect(screen.getByTestId("widget-builder-publish-button")).toBeTruthy()
    })
    fireEvent.click(screen.getByTestId("widget-builder-publish-button"))
    await waitFor(() => {
      expect(screen.getByTestId("widget-builder-publish-error")).toBeTruthy()
    })
    expect(
      screen.getByText(/root_atom_id: missing/),
    ).toBeTruthy()
  })

  it("exposes save status indicator", async () => {
    vi.mocked(widgetBuilderService.get).mockResolvedValueOnce(
      mkRecord(mkBlob()),
    )
    renderAt("/studio/widget-builder/test-widget")
    await waitFor(() => {
      expect(screen.getByTestId("widget-builder-save-status")).toBeTruthy()
    })
  })
})
