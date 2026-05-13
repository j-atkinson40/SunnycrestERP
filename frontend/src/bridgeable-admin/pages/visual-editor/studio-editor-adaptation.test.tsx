/**
 * Studio 1a-i.B — per-editor adaptation tests.
 *
 * Each editor consumes useStudioRail() and hides its own left pane when
 * railExpanded && inStudioContext. These tests mount each editor in two
 * provider states:
 *   - rail-expanded + in-studio  → left pane HIDDEN
 *   - rail-collapsed (or standalone) → left pane VISIBLE
 *
 * For editors with no separate left pane (Registry, PluginRegistry),
 * the test asserts the editor mounts successfully under provider
 * variants (no-op consumer pattern).
 *
 * Heavy services are mocked aggressively to keep the test fast.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { render, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import "@/lib/visual-editor/registry/auto-register"

import { StudioRailContext } from "@/bridgeable-admin/components/studio/StudioRailContext"


// ─── Service mocks (top-level, vitest auto-hoists) ──────────────

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

vi.mock(
  "@/bridgeable-admin/services/document-blocks-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/bridgeable-admin/services/document-blocks-service")
    >("@/bridgeable-admin/services/document-blocks-service")
    return {
      ...actual,
      documentBlocksService: {
        listDocumentTypes: vi.fn().mockResolvedValue({
          categories: [],
          types: [],
        }),
        listBlockKinds: vi.fn().mockResolvedValue([]),
        listBlocks: vi.fn().mockResolvedValue([]),
      },
    }
  },
)

vi.mock(
  "@/services/documents-v2-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/services/documents-v2-service")
    >("@/services/documents-v2-service")
    return {
      ...actual,
      documentsV2Service: {
        listTemplates: vi.fn().mockResolvedValue({ items: [] }),
        getTemplate: vi.fn(),
        getTemplateVersion: vi.fn(),
      },
    }
  },
)

vi.mock(
  "@/bridgeable-admin/services/workflow-templates-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/bridgeable-admin/services/workflow-templates-service")
    >("@/bridgeable-admin/services/workflow-templates-service")
    return {
      ...actual,
      workflowTemplatesService: {
        list: vi.fn().mockResolvedValue([]),
        get: vi.fn(),
        update: vi.fn(),
        create: vi.fn(),
        getDependentForks: vi.fn().mockResolvedValue([]),
      },
    }
  },
)

vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: {
    // Default get returns shape-safe defaults for the editor surfaces
    // exercised here: themes resolve (sources + tokens), generic list.
    get: vi.fn().mockImplementation((url: string) => {
      if (url.includes("/themes/resolve")) {
        return Promise.resolve({
          data: {
            mode: "light",
            vertical: null,
            tenant_id: null,
            tokens: {},
            sources: [],
          },
        })
      }
      if (url.includes("/themes")) {
        return Promise.resolve({ data: { items: [] } })
      }
      return Promise.resolve({ data: { items: [], rows: [] } })
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    patch: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}))


// ─── Editor imports (after mocks so services resolve correctly) ──

import FocusEditorPage from "./FocusEditorPage"
import DocumentsEditorPage from "./DocumentsEditorPage"
import ClassEditorPage from "./ClassEditorPage"
import WidgetEditorPage from "./WidgetEditorPage"
import WorkflowEditorPage from "./WorkflowEditorPage"
import EdgePanelEditorPage from "./EdgePanelEditorPage"
import RegistryDebugPage from "./RegistryDebugPage"
import PluginRegistryBrowser from "./PluginRegistryBrowser"
import ThemeEditorPage from "./themes/ThemeEditorPage"


function renderWithRail(
  ui: React.ReactElement,
  opts: { railExpanded: boolean; inStudioContext: boolean },
) {
  return render(
    <MemoryRouter>
      <StudioRailContext.Provider value={opts}>
        {ui}
      </StudioRailContext.Provider>
    </MemoryRouter>,
  )
}


afterEach(() => {
  vi.clearAllMocks()
})


// ─── Editors with a hideable left pane ─────────────────────────

describe("FocusEditorPage — Studio rail adaptation", () => {
  it("hides focus-editor-browser when rail expanded + in studio", async () => {
    const r = renderWithRail(<FocusEditorPage />, {
      railExpanded: true,
      inStudioContext: true,
    })
    await waitFor(() => expect(r.getByTestId("focus-editor")).toBeTruthy())
    expect(r.queryByTestId("focus-editor-browser")).toBeFalsy()
  })

  it("shows focus-editor-browser when rail collapsed", async () => {
    const r = renderWithRail(<FocusEditorPage />, {
      railExpanded: false,
      inStudioContext: true,
    })
    await waitFor(() =>
      expect(r.getByTestId("focus-editor-browser")).toBeTruthy(),
    )
  })

  it("shows focus-editor-browser when standalone (inStudioContext=false)", async () => {
    const r = renderWithRail(<FocusEditorPage />, {
      railExpanded: true,
      inStudioContext: false,
    })
    await waitFor(() =>
      expect(r.getByTestId("focus-editor-browser")).toBeTruthy(),
    )
  })
})


describe("DocumentsEditorPage — Studio rail adaptation", () => {
  it("hides documents-editor-browser when rail expanded + in studio", async () => {
    const r = renderWithRail(<DocumentsEditorPage />, {
      railExpanded: true,
      inStudioContext: true,
    })
    await waitFor(() => expect(r.getByTestId("documents-editor")).toBeTruthy())
    expect(r.queryByTestId("documents-editor-browser")).toBeFalsy()
  })

  it("shows documents-editor-browser when rail collapsed", async () => {
    const r = renderWithRail(<DocumentsEditorPage />, {
      railExpanded: false,
      inStudioContext: true,
    })
    await waitFor(() =>
      expect(r.getByTestId("documents-editor-browser")).toBeTruthy(),
    )
  })
})


describe("ClassEditorPage — Studio rail adaptation", () => {
  it("hides class-browser when rail expanded + in studio", async () => {
    const r = renderWithRail(<ClassEditorPage />, {
      railExpanded: true,
      inStudioContext: true,
    })
    await waitFor(() => expect(r.getByTestId("class-editor")).toBeTruthy())
    expect(r.queryByTestId("class-browser")).toBeFalsy()
  })

  it("shows class-browser when rail collapsed", async () => {
    const r = renderWithRail(<ClassEditorPage />, {
      railExpanded: false,
      inStudioContext: true,
    })
    await waitFor(() => expect(r.getByTestId("class-browser")).toBeTruthy())
  })
})


describe("WidgetEditorPage — Studio rail adaptation (individual mode)", () => {
  it("hides widget-editor-browser when rail expanded + in studio (individual mode)", async () => {
    const r = renderWithRail(<WidgetEditorPage />, {
      railExpanded: true,
      inStudioContext: true,
    })
    await waitFor(() => expect(r.getByTestId("widget-editor")).toBeTruthy())
    // Default mode is "individual"; the individual editor's browser pane
    // should be hidden under rail-expanded.
    expect(r.queryByTestId("widget-editor-browser")).toBeFalsy()
  })

  it("shows widget-editor-browser when rail collapsed (individual mode)", async () => {
    const r = renderWithRail(<WidgetEditorPage />, {
      railExpanded: false,
      inStudioContext: true,
    })
    await waitFor(() =>
      expect(r.getByTestId("widget-editor-browser")).toBeTruthy(),
    )
  })
})


describe("WorkflowEditorPage — Studio rail adaptation", () => {
  it("hides workflow-editor-selector-pane when rail expanded + in studio", async () => {
    const r = renderWithRail(<WorkflowEditorPage />, {
      railExpanded: true,
      inStudioContext: true,
    })
    await waitFor(() =>
      expect(r.getByTestId("workflow-editor-page")).toBeTruthy(),
    )
    expect(r.queryByTestId("workflow-editor-selector-pane")).toBeFalsy()
  })

  it("shows workflow-editor-selector-pane when rail collapsed", async () => {
    const r = renderWithRail(<WorkflowEditorPage />, {
      railExpanded: false,
      inStudioContext: true,
    })
    await waitFor(() =>
      expect(r.getByTestId("workflow-editor-selector-pane")).toBeTruthy(),
    )
  })
})


describe("ThemeEditorPage — Studio rail adaptation", () => {
  it("hides theme-editor-scope-pane when rail expanded + in studio", async () => {
    const r = renderWithRail(<ThemeEditorPage />, {
      railExpanded: true,
      inStudioContext: true,
    })
    // Editor mounts even when scope pane hidden; just check no scope pane.
    await waitFor(() => {
      expect(r.queryByTestId("theme-editor-scope-pane")).toBeFalsy()
    })
  })

  it("shows theme-editor-scope-pane when rail collapsed", async () => {
    const r = renderWithRail(<ThemeEditorPage />, {
      railExpanded: false,
      inStudioContext: true,
    })
    await waitFor(() =>
      expect(r.getByTestId("theme-editor-scope-pane")).toBeTruthy(),
    )
  })
})


describe("EdgePanelEditorPage — Studio rail adaptation", () => {
  it("hides edge-panel-editor-page-list when rail expanded + in studio", async () => {
    const r = renderWithRail(<EdgePanelEditorPage />, {
      railExpanded: true,
      inStudioContext: true,
    })
    // Editor renders; just check PageList not present.
    await waitFor(() => {
      expect(r.queryByTestId("edge-panel-editor-page-list")).toBeFalsy()
    })
  })

  it("shows edge-panel-editor-page-list when rail collapsed", async () => {
    const r = renderWithRail(<EdgePanelEditorPage />, {
      railExpanded: false,
      inStudioContext: true,
    })
    await waitFor(() =>
      expect(r.getByTestId("edge-panel-editor-page-list")).toBeTruthy(),
    )
  })
})


// ─── No-op consumers (no left pane to hide) ────────────────────

describe("RegistryDebugPage — Studio rail adaptation (no-op consumer)", () => {
  it("renders successfully under rail-expanded + in-studio (no left pane to hide)", () => {
    const r = renderWithRail(<RegistryDebugPage />, {
      railExpanded: true,
      inStudioContext: true,
    })
    // Page mounts without throwing; consumer is a no-op.
    expect(r.container).toBeTruthy()
  })

  it("renders successfully under rail-collapsed", () => {
    const r = renderWithRail(<RegistryDebugPage />, {
      railExpanded: false,
      inStudioContext: true,
    })
    expect(r.container).toBeTruthy()
  })
})


describe("PluginRegistryBrowser — Studio rail adaptation (no-op consumer)", () => {
  it("renders successfully under rail-expanded + in-studio (no left pane to hide)", () => {
    const r = renderWithRail(<PluginRegistryBrowser />, {
      railExpanded: true,
      inStudioContext: true,
    })
    expect(r.container).toBeTruthy()
  })

  it("renders successfully under rail-collapsed", () => {
    const r = renderWithRail(<PluginRegistryBrowser />, {
      railExpanded: false,
      inStudioContext: true,
    })
    expect(r.container).toBeTruthy()
  })
})
